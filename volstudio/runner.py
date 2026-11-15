from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from functools import lru_cache
from pathlib import Path

import ijson
import psutil

from . import __version__, catalog, db, demo
from .evidence import read_guard

PROCESSES = {}
STOP = threading.Event()
WAKE = threading.Event()
PROCESS_LOCK = threading.Lock()
WORKER = None


@lru_cache(maxsize=1)
def runtime_provenance():
    # Record the executable that orchestrates this attempt, not the currently
    # installed version when a historical report is generated in the future.
    digest = ""
    if getattr(sys, "frozen", False):
        with Path(sys.executable).open("rb") as source:
            digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {"studio_version": __version__, "studio_sha256": digest}


def log_tail(path,limit=50000):
    with Path(path).open('rb') as source:
        size=source.seek(0,2)
        source.seek(max(0,size-limit))
        return source.read(limit).decode('utf8',errors='replace')


def hash_case(case_id):
    case = db.one("SELECT * FROM cases WHERE id=?", (case_id,))
    try:
        path = Path(case["path"])
        before = path.stat()
        h = hashlib.sha256()
        read_bytes=0
        reported=0
        with read_guard(path),path.open("rb") as source:
            while chunk := source.read(8 * 1024 * 1024):
                h.update(chunk)
                read_bytes+=len(chunk)
                if read_bytes-reported>=64*1024*1024:
                    db.execute("UPDATE cases SET hash_progress=? WHERE id=?",(min(99,read_bytes/max(before.st_size,1)*100),case_id))
                    reported=read_bytes
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Image changed during hashing")
        db.execute("UPDATE cases SET sha256=?,hash_status='complete',hash_progress=100,size=?,mtime_ns=? WHERE id=?",
                   (h.hexdigest(), after.st_size, after.st_mtime_ns, case_id))
    except Exception as exc:
        db.execute("UPDATE cases SET hash_status='failed',hash_error=?,detect_status='unknown',detect_message=? WHERE id=?", (str(exc),"Не удалось прочитать и проверить исходный образ",case_id))
        db.execute("UPDATE runs SET status='failed',finished=?,error='Image could not be hashed',message='Evidence verification failed' WHERE case_id=? AND status='queued'", (db.now(),case_id))
    WAKE.set()


def command_for(case, plugin_id, params, outdir, settings):
    (db.DATA / "symbol-cache").mkdir(parents=True,exist_ok=True)
    cmd = [sys.executable, "-u", "-m", "volatility3.cli", "--parallelism", "off",
           "-r", "studio-jsonl", "--cache-path", str(db.DATA / "symbol-cache"), "-o", str(outdir)]
    if settings["offline"]:
        cmd.append("--offline")
    if settings["symbol_dirs"]:
        cmd += ["-s", ";".join(settings["symbol_dirs"])]
    if settings["plugin_dirs"]:
        cmd += ["-p", ";".join(settings["plugin_dirs"])]
    cmd += ["-f", case["path"], plugin_id]
    for key, value in params.items():
        if isinstance(value, bool):
            if value:
                cmd.append("--" + key.replace("_", "-"))
        elif isinstance(value, list):
            cmd += ["--" + key.replace("_", "-"), *map(str, value)]
        else:
            cmd.append("--" + key.replace("_", "-") + "=" + str(value))
    return cmd


def powershell_command(arguments):
    return '& ' + ' '.join("'"+str(arg).replace("'","''")+"'" for arg in arguments)


def flatten(row, depth=0):
    depth=int(row.pop("__depth",depth))
    children = row.pop("__children", []) or []
    yield depth, row
    for child in children:
        yield from flatten(child, depth + 1)


def ingest(run_id, path):
    from .timeline import index_row,mark_indexed
    columns = []
    count = 0
    with path.open("rb") as source, db.connection() as c:
        trees=(json.loads(line) for line in source if line.strip()) if path.suffix==".jsonl" else ijson.items(source,"item",use_float=True)
        for tree in trees:
            if not isinstance(tree, dict):
                raise ValueError("Unexpected renderer output: expected objects")
            for depth, row in flatten(tree):
                for key in row:
                    if key not in columns:
                        columns.append(key)
                c.execute("INSERT INTO result_rows VALUES (?,?,?,?)",
                          (run_id, count, depth, json.dumps(row, ensure_ascii=False, default=str)))
                index_row(c,run_id,count,row)
                count += 1
                if count%1000==0:
                    c.commit()
                    status=c.execute("SELECT status FROM runs WHERE id=?",(run_id,)).fetchone()[0]
                    if status=="cancelled":
                        return count,columns
                    c.execute("UPDATE runs SET row_count=?,message=? WHERE id=?",(count,f"Indexed {count:,} rows",run_id))
        mark_indexed(c,run_id,count)
    return count, columns


def friendly_error(stderr, case_os=None):
    text = stderr.strip()
    low = text.lower()
    ru=db.settings().get('language','en')=='ru'
    if 'symbol type not in' in low:
        missing=re.search(r'SymbolTable:\s*([^\s\r\n]+)',text)
        detail=missing.group(1) if missing else 'unknown'
        tip=(f'В найденных данных ядра отсутствует тип {detail}. Нужны полные данные типов для этой сборки; повтор того же запуска без их замены не поможет.' if ru else
             f'The kernel symbol table is missing type {detail}. Complete symbols for this build are required; repeating the same run without replacing them will not help.')
    elif case_os=='windows' and 'offlineexception' in low and ('symbol_table_name' in low or '.pdb' in low):
        tip='Volatility работает в офлайн-режиме и не нашёл данные ядра Windows. Откройте Настройки → Анализ: добавьте локальные данные ОС или разрешите их загрузку.' if ru else 'Volatility is offline and Windows kernel data is unavailable. Open Settings → Analysis: add local OS data or allow downloads.'
    elif case_os=='linux' and 'symbol_table_name' in low and ('unable to validate' in low or 'unsatisfied requirement' in low):
        tip='Не удалось прочитать структуры Linux. Сначала проверьте ISF JSON для полного баннера ядра и выбранную папку данных ОС. Недостающие данные типов также мешают построению слоя памяти; эта ошибка сама по себе не доказывает повреждение образа.' if ru else 'Linux structures could not be read. First check the ISF JSON for the full kernel banner and the selected OS data directory. Missing type information can also prevent memory-layer construction; this error alone does not prove image corruption.'
    elif re.search(r'plugins\.[\w.]+\.layer_name\b',low) and ('unable to validate' in low or 'unsatisfied requirement' in low):
        tip=('Не удалось построить слой памяти. Проверьте формат и полноту образа; одних данных типов недостаточно.' if ru else
             'A memory translation layer could not be constructed. Check the image format and completeness; symbol files alone cannot repair the memory mapping.')
    elif "unsatisfied requirement" in low or "unable to validate" in low:
        tip = ("Не удалось построить слой памяти или найти данные типов ОС. Проверьте ОС образа и папки данных для анализа." if ru else
               "Could not construct a memory layer or locate OS type information. Check the image OS and analysis data directories.")
    elif "yara" in low and ("import" in low or "install" in low):
        tip = "Плагину требуется YARA. Проверьте зависимости движка." if ru else "This plugin requires YARA. Check the engine dependencies."
    elif "filenotfound" in low or "no such file" in low:
        tip = "Файл или необходимая зависимость не найдены. Проверьте журнал запуска." if ru else "A file or required dependency was not found. Check the run log."
    else:
        tip = "Volatility завершил запуск с ошибкой. Полный вывод сохранён в журнале." if ru else "Volatility failed. The full diagnostic output is available in the run log."
    return tip + "\n\n" + text[-12000:]


def execute(run):
    case = db.one("SELECT * FROM cases WHERE id=?", (run["case_id"],))
    pipeline = run.get("purpose") == "pipeline"
    params = json.loads(run["params"])
    verify_image = case["kind"] != "demo" and (not pipeline or params["source"] == "image")
    outdir = db.DATA / "cases" / case["id"] / "runs" / run["id"]
    outdir.mkdir(parents=True, exist_ok=True)
    result_path = outdir / ("result.json" if case["kind"]=="demo" and not pipeline else "result.jsonl")
    log_path = outdir / "engine.log"
    cfg = json.loads(run["settings_json"])
    guard=None
    try:
        db.update_run(run["id"], **runtime_provenance())
        if verify_image:
            guard=read_guard(Path(case['path']))
            guard.__enter__()
            s = Path(case["path"]).stat()
            if (s.st_size, s.st_mtime_ns) != (case["size"], case["mtime_ns"]):
                raise ValueError("Evidence changed since hashing. Attach a fresh case before analysis.")
        if not pipeline and case['kind'] != 'demo':
            from .symbol_store import prepare
            db.update_run(run['id'],started=db.now(),status='running',message='Preparing OS analysis data')
            cfg = {**cfg,'symbol_dirs':prepare(cfg.get('symbol_dirs',[]),
                lambda message: db.update_run(run['id'],message=message),
                lambda: db.one('SELECT status FROM runs WHERE id=?',(run['id'],))['status']=='cancelled')}
        cmd = command_for(case, run["plugin"], params, outdir, cfg) if not pipeline else ["studio-pipeline", json.dumps(params)]
        equivalent = ['vol',*cmd[4:]] if not pipeline else cmd
        if not pipeline:
            equivalent[equivalent.index('studio-jsonl')]='json'
        with PROCESS_LOCK:
            if db.one("SELECT status FROM runs WHERE id=?", (run["id"],))["status"] == "cancelled":
                return
            db.update_run(run["id"], started=db.now(), status="running", progress=0,
                          command='Pipeline JSON' if pipeline else powershell_command(equivalent) if case["kind"] != "demo" else "DEMO fixture: " + run["plugin"],
                          output_dir=str(outdir), input_sha256=case["sha256"], message="Preparing analysis")
        if case["kind"] == "demo" and not pipeline:
            for n in range(5):
                if db.one("SELECT status FROM runs WHERE id=?", (run["id"],))["status"] == "cancelled":
                    return
                db.update_run(run["id"], progress=n * 20, message="Synthetic demonstration — no memory image analysed")
                time.sleep(0.14)
            data = demo.rows(run["plugin"])
            params = json.loads(run["params"])
            if params.get("pid"):
                data = [row for row in data if row.get("PID") in params["pid"]]
            result_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            log_path.write_text("SYNTHETIC DEMONSTRATION. Results are fixtures, not Volatility output.\n", encoding="utf-8")
        else:
            job_path = outdir / "worker-job.json"
            job = {"stdout":str(result_path), "stderr":str(log_path), "args":cmd[4:]}
            if pipeline:
                job.update(config=params, image=case["path"], database=str(db.DATA/"studio.sqlite3"), summary=str(outdir/"pipeline-summary.json"))
            job_path.write_text(json.dumps(job),encoding="utf-8")
            mode = "--pipeline-worker" if pipeline else "--engine-worker"
            module = "volstudio.pipeline" if pipeline else "volstudio.engine_worker"
            worker_cmd = [sys.executable,mode,str(job_path)] if getattr(sys,"frozen",False) else [sys.executable,"-u","-m",module,str(job_path)]
            ram=psutil.virtual_memory()
            budget_mb=int(cfg.get("memory_limit_mb",0)) or max(512,int(min(ram.total*.45,ram.available*.7)/(1024**2)))
            db.update_run(run["id"],worker_command=json.dumps(worker_cmd),memory_budget_mb=budget_mb)
            with PROCESS_LOCK:
                if db.one("SELECT status FROM runs WHERE id=?", (run["id"],))["status"] == "cancelled":
                    return
                proc = subprocess.Popen(worker_cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=False,
                    env={**os.environ,"PYTHONUTF8":"1"},creationflags=(subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name=="nt" else 0)
                PROCESSES[run["id"]] = proc
            last_position=0
            peak=0
            while proc.poll() is None:
                try:
                    parent=psutil.Process(proc.pid)
                    rss=sum(p.memory_info().rss for p in [parent,*parent.children(recursive=True)] if p.is_running())
                    if rss>peak+1024*1024:
                        peak=rss
                        db.update_run(run["id"],memory_peak_bytes=peak)
                    if rss>budget_mb*1024**2:
                        kill_tree(proc)
                        raise RuntimeError(f"Memory budget exceeded ({budget_mb} MB). The worker was stopped to keep the interface responsive. Increase the analysis memory budget in Settings if needed.")
                except (psutil.NoSuchProcess,psutil.AccessDenied):
                    pass
                if log_path.exists():
                    with log_path.open("rb") as log:
                        size=log.seek(0,2)
                        log.seek(max(last_position,size-65536))
                        chunk=log.read(65536)
                        last_position=log.tell()
                    matches=list(re.finditer(r"Progress:\s*(\d+(?:\.\d+)?)\s*([^\r\n]*)",chunk.decode("utf-8",errors="replace")))
                    if matches:
                        match=matches[-1]
                        db.update_run(run["id"],progress=min(float(match[1]),99),message=match[2].strip()[:300])
                time.sleep(0.2)
            code=proc.wait()
            if db.one("SELECT status FROM runs WHERE id=?", (run["id"],))["status"] == "cancelled":
                return
            if code != 0:
                raise RuntimeError(friendly_error(log_tail(log_path,12000),case.get("os")))
        if db.one("SELECT status FROM runs WHERE id=?", (run["id"],))["status"] == "cancelled":
            return
        if verify_image:
            final_stat = Path(case["path"]).stat()
            if (final_stat.st_size, final_stat.st_mtime_ns) != (case["size"],case["mtime_ns"]):
                raise ValueError("Evidence changed during analysis; output is not verified")
        db.update_run(run["id"], status="indexing", progress=99, message="Indexing results")
        count, columns = ingest(run["id"], result_path)
        if db.one("SELECT status FROM runs WHERE id=?",(run["id"],))["status"]=="cancelled":
            return
        summary = json.loads((outdir/"pipeline-summary.json").read_text(encoding="utf8")) if pipeline else {}
        with PROCESS_LOCK:
            if db.one("SELECT status FROM runs WHERE id=?",(run["id"],))["status"]=="cancelled":
                return
            db.update_run(run["id"], row_count=count,columns_json=json.dumps(columns),
                          pipeline_summary_json=json.dumps(summary))
            # Publish the detection outcome before exposing a completed run.
            if run.get("purpose", "analysis").startswith("detection"):
                from .detection import after_run
                after_run(run,success=True)
            db.update_run(run["id"], status="completed",progress=100,finished=db.now(),
                          message="Pipeline row limit reached" if summary.get("limit_reached") else "Analysis complete")
    except Exception as exc:
        row = db.one("SELECT status FROM runs WHERE id=?", (run["id"],))
        if row and row["status"] != "cancelled":
            db.update_run(run["id"], status="failed", finished=db.now(), error=str(exc), message="Analysis failed")
            if run.get("purpose", "analysis").startswith("detection"):
                from .detection import after_run
                after_run(run,success=False)
    finally:
        if guard:
            guard.__exit__(None,None,None)
        with PROCESS_LOCK:
            PROCESSES.pop(run["id"], None)


def worker():
    while not STOP.is_set():
        run = db.one("""SELECT r.* FROM runs r JOIN cases c ON c.id=r.case_id
                       WHERE r.status='queued' AND (c.hash_status='complete' OR c.kind='demo'
                       OR (r.purpose='pipeline' AND json_extract(r.params,'$.source')='results'))
                       ORDER BY r.created LIMIT 1""")
        if run:
            execute(run)
        else:
            WAKE.wait(0.5)
            WAKE.clear()


def start():
    global WORKER
    STOP.clear()
    WORKER = threading.Thread(target=worker, name="volatility-queue", daemon=True)
    WORKER.start()
    for case in db.all_rows("SELECT id FROM cases WHERE hash_status='pending' AND kind!='demo'"):
        threading.Thread(target=hash_case, args=(case["id"],), daemon=True).start()


def cancel(run_id):
    with PROCESS_LOCK:
        row = db.one("SELECT status,case_id,purpose FROM runs WHERE id=?", (run_id,))
        if not row or row["status"] not in ("queued", "running", "indexing"):
            return False
        db.update_run(run_id, status="cancelled", finished=db.now(), message="Cancelled by analyst")
        if row.get('purpose') in ('detection-banners','detection-windows'):
            phase='banners' if row['purpose']=='detection-banners' else 'windows'
            db.execute("UPDATE cases SET detect_status='cancelled',detect_message=? WHERE id=? AND detect_status=?",
                       ('Определение образа отменено. Нажмите повторное определение, чтобы продолжить.',row['case_id'],phase))
        proc = PROCESSES.get(run_id)
        if proc and proc.poll() is None:
            kill_tree(proc)
    return True


def kill_tree(proc):
    try:
        parent=psutil.Process(proc.pid)
        for child in reversed(parent.children(recursive=True)):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def shutdown():
    STOP.set()
    WAKE.set()
    for run_id in list(PROCESSES):
        cancel(run_id)
    if WORKER:
        WORKER.join(timeout=5)
