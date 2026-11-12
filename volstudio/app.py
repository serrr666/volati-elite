from __future__ import annotations

import asyncio
import csv
import hashlib
import html
import io
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, UploadFile, Query
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, ConfigDict

from . import __version__, catalog, db, runner
from .artifact_hashes import ArtifactChanged, artifact_digests
from .pipeline import PipelineInput
from . import result_filters
from .security import API_TOKEN,TOKEN_HEADER,authenticated
from .localization import default_language,default_theme,SUPPORTED_LANGUAGES

ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app):
    db.init()
    await asyncio.to_thread(catalog.refresh, db.settings())
    runner.start()
    yield
    runner.shutdown()


app = FastAPI(title="volati elite", version=__version__, lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", "[::1]"])


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    allowed = {f"http://{request.url.netloc}"}
    if origin and origin not in allowed:
        return JSONResponse({"detail": "Origin is not permitted"}, status_code=403)
    if not authenticated(request.headers.get(TOKEN_HEADER)):
        return JSONResponse({"detail":"Local application session required"},status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), usb=(), serial=()"
    if request.url.path.startswith('/api/'):
        response.headers["Cache-Control"]="no-store"
    return response


def case_or_404(case_id):
    row = db.one("SELECT * FROM cases WHERE id=?", (case_id,))
    if not row:
        raise HTTPException(404, "Case not found")
    return row


def run_or_404(run_id):
    row = db.one("SELECT * FROM runs WHERE id=?", (run_id,))
    if not row:
        raise HTTPException(404, "Run not found")
    return row


class NewCase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    path: str = Field(min_length=1, max_length=4096)
    os: str = "unknown"
    reuse_existing: bool = False


class RunInput(BaseModel):
    plugin: str
    params: dict = Field(default_factory=dict)


class BatchInput(BaseModel):
    runs: list[RunInput] = Field(min_length=1,max_length=50)


class BookmarkInput(BaseModel):
    run_id: str
    row_idx: int = Field(ge=0)
    note: str = Field(default="", max_length=20000)


class NoteDraftInput(BaseModel):
    text: str | None = Field(default=None, max_length=100000)


class CaseUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name: str = Field(default='',min_length=1,max_length=160)
    notes: str = Field(default='',max_length=100000)
    os: Literal['windows','linux','mac','unknown'] = 'unknown'

    @field_validator('name',mode='before')
    @classmethod
    def trim_name(cls,value):
        return value.strip() if isinstance(value,str) else value


class SettingsInput(BaseModel):
    offline: bool = True
    symbol_dirs: list[str] = Field(default_factory=list, max_length=10)
    plugin_dirs: list[str] = Field(default_factory=list, max_length=10)
    memory_limit_mb: int = Field(default=0, ge=0, le=1048576)


class PreferencesInput(BaseModel):
    language: str = Field(default_factory=default_language)
    theme: str = Field(default_factory=default_theme)
    last_case: str = ""
    hide_tip: bool = False
    open_cases: list[str] | None = Field(default=None,max_length=1000)
    hidden_recent_cases: list[str] = Field(default_factory=list, max_length=1000)
    favorite_plugins: list[str] = Field(default_factory=list, max_length=1000)


@app.get("/api/preferences")
def preferences():
    cfg=db.settings()
    ids={r['id'] for r in db.all_rows('SELECT id FROM cases')}
    last=cfg.get('last_case','')
    opened=cfg.get('open_cases')
    if opened is None:opened=[last] if last in ids else []
    opened=list(dict.fromkeys(cid for cid in opened if cid in ids))
    return {"language":cfg.get("language") if cfg.get("language") in SUPPORTED_LANGUAGES else default_language(),"theme":cfg.get("theme",default_theme()),"last_case":last if last in opened else '',"hide_tip":cfg.get("hide_tip",False),'open_cases':opened,
            'hidden_recent_cases': list(dict.fromkeys(cid for cid in cfg.get('hidden_recent_cases', []) if cid in ids)),
            'favorite_plugins': cfg.get('favorite_plugins', [])}


@app.put("/api/preferences")
def save_preferences(value: PreferencesInput):
    if value.language not in SUPPORTED_LANGUAGES or value.theme not in ("light","dark"):
        raise HTTPException(422,"Unsupported language or theme")
    changes=value.model_dump(exclude_unset=True)
    current=preferences()
    opened=changes.get('open_cases',current['open_cases'])
    if opened is None:opened=current['open_cases']
    last=changes.get('last_case',current['last_case'])
    if 'open_cases' not in changes and last and last not in opened:opened=[*opened,last]
    ids={r['id'] for r in db.all_rows('SELECT id FROM cases')}
    if len(opened)!=len(set(opened)) or any(cid not in ids for cid in opened) or (last and last not in opened):
        raise HTTPException(422,'Invalid workspace case selection')
    if 'hidden_recent_cases' in changes:
        changes['hidden_recent_cases'] = list(dict.fromkeys(cid for cid in value.hidden_recent_cases if cid in ids))
    if 'favorite_plugins' in changes:
        if any(not plugin or len(plugin)>256 for plugin in value.favorite_plugins):
            raise HTTPException(422, 'Invalid favorite plugin identifier')
        changes['favorite_plugins'] = list(dict.fromkeys(value.favorite_plugins))
    changes.update(open_cases=opened,last_case=last)
    db.save_settings(changes)
    return preferences()


class WorkspaceNoteInput(BaseModel):
    text: str = Field(max_length=100000)


@app.get('/api/workspace/notebook')
def workspace_notebook():
    row=db.one('SELECT text,draft,updated FROM workspace_notebook WHERE id=1')
    return row or {'text':'','draft':None,'updated':None}


@app.put('/api/workspace/notebook')
def save_workspace_notebook(value:WorkspaceNoteInput):
    db.execute("INSERT INTO workspace_notebook(id,text,updated) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET text=excluded.text,updated=excluded.updated",(value.text,db.now()))
    return workspace_notebook()


@app.put('/api/workspace/notebook/commit')
def commit_workspace_notebook(value:WorkspaceNoteInput):
    db.execute("INSERT INTO workspace_notebook(id,text,updated) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET text=excluded.text,draft=NULL,updated=excluded.updated",(value.text,db.now()))
    return workspace_notebook()


@app.put('/api/workspace/notebook/draft')
def save_workspace_draft(value:NoteDraftInput):
    db.execute("INSERT INTO workspace_notebook(id,draft,updated) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET draft=excluded.draft,updated=excluded.updated",(value.text,db.now()))
    return {'text':value.text}


@app.get('/api/workspace/activity')
def workspace_activity():
    query='SELECT r.*,c.name AS case_name FROM runs r JOIN cases c ON c.id=r.case_id '
    return {'runs':[db.serialize_run(r) for r in db.all_rows(query+'ORDER BY r.created DESC,r.id DESC LIMIT 100')],
            'active':[db.serialize_run(r) for r in db.all_rows(query+"WHERE r.status IN ('queued','running','indexing') ORDER BY r.created,r.id")],
            'total_runs':db.one('SELECT COUNT(*) n FROM runs')['n']}


@app.get('/api/workspace/pulse')
def workspace_pulse():
    return db.one("""SELECT revision,EXISTS(SELECT 1 FROM runs WHERE status IN ('queued','running','indexing'))
        OR EXISTS(SELECT 1 FROM cases WHERE hash_status='pending' OR detect_status IN ('banners','windows','queued')) AS busy
        FROM workspace_revision WHERE id=1""")


@app.get("/api/health")
def health():
    from .build_info import BUILD_DATE
    return {"app": "volati elite", "version": __version__, "build_date":BUILD_DATE, "engine_version": catalog.CATALOG["version"],
            "engine_status": catalog.CATALOG["status"], "plugin_count": len(catalog.CATALOG["plugins"]),
            "warnings": catalog.CATALOG["warnings"], "data_dir": str(db.DATA), "local_only": True}


@app.get("/api/plugins")
def plugins():
    return catalog.CATALOG


@app.get("/api/settings")
def settings():
    return db.settings()


@app.put("/api/settings")
async def save_settings(values: SettingsInput):
    config = values.model_dump()
    for field in ("symbol_dirs", "plugin_dirs"):
        resolved = []
        for path in config[field]:
            p = Path(path).expanduser().resolve()
            if not p.is_dir():
                raise HTTPException(400, f"Directory does not exist: {path}")
            resolved.append(str(p))
        config[field] = resolved
    candidate=await asyncio.to_thread(catalog.refresh,config,False)
    if candidate['status']!='ready':
        raise HTTPException(422,'Настройки не применены. Не удалось загрузить плагины: '+'; '.join(candidate['warnings'])[-2000:])
    db.save_settings(config)
    catalog.CATALOG=candidate
    return {"settings": config, "catalog": candidate}


@app.post("/api/plugins/refresh")
async def refresh_plugins():
    return await asyncio.to_thread(catalog.refresh, db.settings())


@app.get("/api/cases")
def cases():
    return db.all_rows("""SELECT c.*, (SELECT COUNT(*) FROM runs r WHERE r.case_id=c.id) AS run_count,
                       (SELECT COUNT(*) FROM bookmarks b WHERE b.case_id=c.id) AS bookmark_count
                       FROM cases c ORDER BY c.created DESC""")


def attach_case(values):
    if values.os not in ("windows", "linux", "mac", "unknown"):
        raise HTTPException(400, "Unsupported OS")
    path = Path(values.path).expanduser().resolve()
    if not path.is_file():
        raise HTTPException(400, "Файл не найден. Укажите полный локальный путь к дампу.")
    stat = path.stat()
    if stat.st_size == 0:
        raise HTTPException(400, "Файл пуст")
    # Serialize lookup + insert so two simultaneous drops cannot fork the history.
    with db.LOCK:
        if values.reuse_existing:
            matches=db.all_rows("SELECT * FROM cases WHERE kind='evidence' AND size=? AND mtime_ns=? AND hash_status!='failed' ORDER BY created,id",(stat.st_size,stat.st_mtime_ns))
            for previous in matches:
                if os.path.normcase(previous['path'])==os.path.normcase(str(path)) and values.os in ('unknown',previous['os']):
                    return {**previous,'reused':True}
        case_id = uuid.uuid4().hex[:16]
        db.execute("INSERT INTO cases (id,name,path,os,size,mtime_ns,created) VALUES (?,?,?,?,?,?,?)",
                   (case_id, values.name.strip() or path.name, str(path), values.os, stat.st_size, stat.st_mtime_ns, db.now()))
    threading.Thread(target=runner.hash_case, args=(case_id,), daemon=True).start()
    from . import detection
    try:
        detection.start(case_id, auto=values.os=='unknown')
    except OSError as exc:
        db.execute("UPDATE cases SET detect_status='unknown',detect_message=? WHERE id=?",(str(exc),case_id))
    return case_or_404(case_id)


@app.post("/api/cases", status_code=201)
def new_case(values: NewCase):
    result=attach_case(values)
    return JSONResponse(result,status_code=200) if result.get('reused') else result


@app.post('/api/cases/{case_id}/detect')
def redetect(case_id: str):
    case=case_or_404(case_id)
    if case['kind']=='demo':
        raise HTTPException(409,'The training case has no source file')
    if db.one("SELECT id FROM runs WHERE case_id=? AND purpose LIKE 'detection%' AND status IN ('queued','running','indexing')",(case_id,)):
        raise HTTPException(409,'Image identification is already in progress')
    from .detection import start
    start(case_id)
    return case_or_404(case_id)


@app.post("/api/pick-file")
async def pick_file():
    def pick():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        try:
            return filedialog.askopenfilename(title="volati elite · Выберите образ памяти",
                filetypes=[("Memory images", "*.raw *.mem *.vmem *.dmp *.lime *.bin *.aff4 *.elf"), ("All files", "*.*")])
        finally:
            root.destroy()
    try:
        path = await asyncio.to_thread(pick)
        return {"path": path, "name": Path(path).stem if path else ""}
    except Exception as exc:
        raise HTTPException(400, f"Не удалось открыть диалог. Введите путь вручную. {exc}")


@app.post("/api/upload", status_code=201)
async def upload(file: UploadFile, os: str = "windows"):
    directory = db.DATA / "images"
    directory.mkdir(exist_ok=True, parents=True)
    safe_name = re.sub(r"[^\w. -]", "_", Path(file.filename or "memory.raw").name)[:160]
    target = directory / (uuid.uuid4().hex[:12] + "_" + safe_name)
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        return attach_case(NewCase(name=Path(safe_name).stem, path=str(target), os=os))
    except Exception:
        target.unlink(missing_ok=True)
        raise


@app.patch("/api/cases/{case_id}")
def update_case(case_id: str, values: CaseUpdate):
    case_or_404(case_id)
    data=values.model_dump(exclude_unset=True)
    # Validate the entire request before one atomic update; never save a note
    # and then silently ignore another invalid field in the same request.
    if data:
        assignments=[f'{key}=?' for key in data]
        if 'os' in data:
            assignments.extend(["detect_status='manual'","detect_message='ОС выбрана аналитиком'"])
        db.execute('UPDATE cases SET '+','.join(assignments)+' WHERE id=?',(*data.values(),case_id))
    return case_or_404(case_id)


def prepared_run(case, values, cfg):
    case_id=case["id"]
    if case["hash_status"] == "failed":
        raise HTTPException(409, "Не удалось проверить SHA-256 образа. Создайте кейс повторно.")
    plugin = catalog.get_plugin(values.plugin)
    if not plugin:
        raise HTTPException(400, "Plugin is not installed")
    if case.get('source_kind','memory')!='memory' and plugin['os']!='generic':
        raise HTTPException(409, 'Этот источник не распознан как совместимый образ памяти системы. Доступны поиск строк и общие сканеры; проверьте тип файла.')
    if plugin["os"] not in ("generic", case["os"]) and case["os"] != "unknown":
        raise HTTPException(400, "Plugin OS does not match case OS")
    try:
        params = catalog.validate_params(plugin, values.params)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc))
    run_id = uuid.uuid4().hex[:16]
    return (run_id,case_id,values.plugin,json.dumps(params),db.now(),catalog.CATALOG['version'],int(cfg['offline']),json.dumps(cfg))


def enqueue_many(case_id, values):
    case=case_or_404(case_id);cfg=db.settings()
    prepared=[prepared_run(case,value,cfg) for value in values]
    with db.connection() as connection:
        connection.executemany("""INSERT INTO runs(id,case_id,plugin,params,status,created,engine_version,offline,settings_json)
            VALUES(?,?,?,?,'queued',?,?,?,?)""",prepared)
    runner.WAKE.set()
    return [db.serialize_run(run_or_404(item[0])) for item in prepared]


def enqueue(case_id,values):
    return enqueue_many(case_id,[values])[0]


@app.post('/api/cases/{case_id}/runs/batch',status_code=201)
def batch(case_id:str,values:BatchInput):
    return enqueue_many(case_id,values.runs)


@app.post("/api/cases/{case_id}/runs", status_code=201)
def run_plugin(case_id: str, values: RunInput):
    return enqueue(case_id, values)


@app.get('/api/cases/{case_id}/notebook')
def case_notebook(case_id:str):
    case=case_or_404(case_id)
    draft=db.one('SELECT text FROM note_drafts WHERE case_id=?',(case_id,))
    return {'text':case['notes'],'draft':draft['text'] if draft else None}


@app.put('/api/cases/{case_id}/notebook')
def save_case_notebook(case_id:str,value:WorkspaceNoteInput):
    case_or_404(case_id)
    with db.connection() as connection:
        connection.execute('UPDATE cases SET notes=? WHERE id=?',(value.text,case_id))
        connection.execute('DELETE FROM note_drafts WHERE case_id=?',(case_id,))
    return {'text':value.text,'draft':None}


@app.get('/api/cases/{case_id}/draft')
def note_draft(case_id: str):
    case_or_404(case_id)
    row=db.one('SELECT text FROM note_drafts WHERE case_id=?',(case_id,))
    return {'text':row['text'] if row else None}


@app.put('/api/cases/{case_id}/draft')
def save_note_draft(case_id: str, value: NoteDraftInput):
    case_or_404(case_id)
    if value.text is None:
        db.execute('DELETE FROM note_drafts WHERE case_id=?',(case_id,))
    else:
        db.execute('INSERT OR REPLACE INTO note_drafts (case_id,text,updated) VALUES (?,?,?)',(case_id,value.text,db.now()))
    return {'ok':True}


@app.get("/api/cases/{case_id}/runs")
def runs(case_id: str):
    case_or_404(case_id)
    return [db.serialize_run(r) for r in db.all_rows("SELECT * FROM runs WHERE case_id=? ORDER BY created DESC", (case_id,))]


@app.post("/api/cases/{case_id}/pipeline", status_code=201)
def enqueue_pipeline(case_id: str, values: PipelineInput):
    case = case_or_404(case_id)
    if values.source == "image":
        if case["kind"] == "demo":
            raise HTTPException(422, "Учебный кейс не содержит файла памяти")
        if case["hash_status"] == "failed":
            raise HTTPException(409, "Не удалось проверить SHA-256 образа")
        fields = {"Offset", "Encoding", "Text", "Fragment", "_source_offset"}
    else:
        source = run_or_404(values.source_run)
        if source["case_id"] != case_id:
            raise HTTPException(422, "Источник относится к другому кейсу")
        if source["status"] != "completed":
            raise HTTPException(409, "Дождитесь завершения исходного запуска")
        fields = set(json.loads(source["columns_json"]))
    # Validate each stage against the fields available after its predecessor.
    for step in values.steps:
        if step.field and step.field not in fields:
            raise HTTPException(422, "Поле не найдено: " + step.field)
        if step.op == "split":
            fields.update(f"Field{i}" for i in range(1,201))
        if any(f not in fields for f in step.fields):
            raise HTTPException(422, "Одно из выбранных полей не найдено")
        if step.op == "select":
            fields = set(step.fields)
    run_id = uuid.uuid4().hex[:16]
    cfg = db.settings()
    db.execute("""INSERT INTO runs (id,case_id,plugin,params,status,created,engine_version,offline,settings_json,purpose)
               VALUES (?,?,?,?,'queued',?,?,?,?,'pipeline')""",
               (run_id,case_id,'studio.Pipeline',values.model_dump_json(),db.now(),catalog.CATALOG["version"],int(cfg["offline"]),json.dumps(cfg)))
    runner.WAKE.set()
    return db.serialize_run(run_or_404(run_id))


@app.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str):
    run_or_404(run_id)
    if not runner.cancel(run_id):
        raise HTTPException(409, "Only running or queued runs can be cancelled")
    return {"ok": True}


@app.post("/api/runs/{run_id}/retry", status_code=201)
def retry(run_id: str):
    run = run_or_404(run_id)
    if run.get("purpose") == "pipeline":
        return enqueue_pipeline(run["case_id"], PipelineInput.model_validate_json(run["params"]))
    return enqueue(run["case_id"], RunInput(plugin=run["plugin"], params=json.loads(run["params"])))


@app.get('/api/runs/{run_id}/values')
def column_values(run_id:str,column:str,q:str='',filters:str='',search:str='',offset:int=0,limit:int=100):
    run=run_or_404(run_id)
    return result_filters.values_page(db,run_id,json.loads(run['columns_json']),column,q,filters,search,offset,limit)


@app.get('/api/runs/{run_id}/rows')
def result_rows(run_id:str,offset:int=0,limit:int=100,q:str='',sort:str='',direction:str='asc',filters:str=''):
    run=run_or_404(run_id);columns=json.loads(run['columns_json'])
    where,args=result_filters.predicate(run_id,columns,q,filters)
    offset,limit=max(0,offset),min(200,max(1,limit))
    count=run['row_count'] if not q and not filters and run['status']=='completed' else db.one('SELECT COUNT(*) n FROM result_rows WHERE '+where,args)['n']
    order='idx';sort_args=[]
    if sort in columns:
        order="(SELECT value FROM json_each(result_rows.data) WHERE key=? LIMIT 1) COLLATE studio_text "+('DESC' if direction=='desc' else 'ASC')+',idx';sort_args=[sort]
    data=db.all_rows('SELECT * FROM result_rows WHERE '+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',[*args,*sort_args,limit,offset])
    return {'rows':[{'index':r['idx'],'depth':r['depth'],'data':json.loads(r['data'])} for r in data],'columns':columns,'total':count,'offset':offset}


@app.get('/api/runs/{run_id}/rows/{row_idx}')
def result_row(run_id: str, row_idx: int):
    run_or_404(run_id)
    row=db.one('SELECT idx,depth,data FROM result_rows WHERE run_id=? AND idx=?',(run_id,row_idx))
    if not row:
        raise HTTPException(404,'Result row not found')
    return {'index':row['idx'],'depth':row['depth'],'data':json.loads(row['data'])}


@app.get('/api/runs/{run_id}/rows/{row_idx}/dumpfiles')
def filescan_target(run_id: str, row_idx: int):
    run = run_or_404(run_id)
    if run['plugin'] != 'windows.filescan.FileScan' or run['status'] != 'completed':
        raise HTTPException(409, 'A completed FileScan result is required')
    data = result_row(run_id, row_idx)['data']
    address = str(data.get('Offset', ''))
    if not re.fullmatch(r'0[xX][0-9a-fA-F]{1,16}|[0-9]{1,20}', address):
        raise HTTPException(422, 'FileScan row has no usable address')
    number = int(address, 16 if address.lower().startswith('0x') else 10)
    if not 0 < number < 2**64:
        raise HTTPException(422, 'FileScan row has no usable address')

    # PoolScanner scans the underlying physical layer before Windows 10.
    # Use Info from the same verified input, never infer the kind from the offset.
    parameter = None
    if run['input_sha256']:
        info = db.one("""SELECT id FROM runs WHERE case_id=? AND input_sha256=?
            AND plugin='windows.info.Info' AND status='completed' ORDER BY created DESC LIMIT 1""",
            (run['case_id'], run['input_sha256']))
        if info:
            major = db.one("""SELECT json_extract(data,'$.Value') value FROM result_rows
                WHERE run_id=? AND json_extract(data,'$.Variable')='NtMajorVersion' LIMIT 1""", (info['id'],))
            if major and re.fullmatch(r'[0-9]{1,3}', str(major['value'])):
                version = int(major['value'])
                if version in (5, 6):
                    parameter = 'physaddr'
                elif version >= 10:
                    parameter = 'virtaddr'
    return {'address': hex(number), 'parameter': parameter}


@app.get("/api/runs/{run_id}/logs")
def logs(run_id: str):
    run = run_or_404(run_id)
    path = Path(run["output_dir"] or db.DATA) / "engine.log"
    text = ""
    if run["output_dir"] and path.is_file():
        with path.open("rb") as f:
            size = f.seek(0, 2)
            f.seek(max(0, size - 50000))
            text = f.read().decode("utf-8", errors="replace")
    command=run["command"]
    if run.get("purpose")=="pipeline":
        command+='\n\n'+json.dumps(json.loads(run['params']),ensure_ascii=False,indent=2)
    try:
        worker_arguments=json.loads(run.get('worker_command') or '[]')
    except (ValueError,TypeError):
        worker_arguments=[]
    return {"text": text, "error": run["error"], "command": command,
            "worker_command":runner.powershell_command(worker_arguments) if worker_arguments else ''}


INTERNAL_RUN_FILES={'result.json','result.jsonl','engine.log','worker-job.json','pipeline-distinct.sqlite3','pipeline-summary.json'}


@app.get("/api/runs/{run_id}/artifacts")
def artifacts(run_id: str):
    run = run_or_404(run_id)
    if not run["output_dir"] or run['status']!='completed':
        return []
    root = Path(run["output_dir"]).resolve()
    return [{"name": str(p.relative_to(root)), "size": p.stat().st_size} for p in root.rglob("*")
            if p.is_file() and root in p.resolve().parents and p.name.rstrip(' .').casefold() not in INTERNAL_RUN_FILES]


def artifact_path(run_id: str, name: str) -> Path:
    run = run_or_404(run_id)
    if run['status']!='completed':
        raise HTTPException(409,'Artifacts are available only after a successful run')
    if not run["output_dir"]:
        raise HTTPException(404, "No output directory")
    root = Path(run["output_dir"]).resolve()
    if '\x00' in name or ':' in name:
        raise HTTPException(404,'Artifact not found')
    try:
        target = (root / name).resolve()
    except (ValueError,OSError):
        raise HTTPException(404,'Artifact not found')
    if root not in target.parents or not target.is_file() or target.name.rstrip(' .').casefold() in INTERNAL_RUN_FILES:
        raise HTTPException(404, "Artifact not found")
    return target


@app.get("/api/runs/{run_id}/artifact")
def artifact(run_id: str, name: str):
    target = artifact_path(run_id, name)
    return FileResponse(target, filename=target.name, media_type="application/octet-stream")


@app.get("/api/runs/{run_id}/artifact-hashes")
def artifact_hashes(run_id: str, name: str):
    target = artifact_path(run_id, name)
    try:
        return artifact_digests(target)
    except ArtifactChanged:
        raise HTTPException(409, 'Extracted file changed during hashing') from None
    except OSError:
        raise HTTPException(404, 'Extracted file could not be read') from None


def csv_safe(value):
    if value is None:
        return ""
    if isinstance(value, str) and re.sub(r'^[\s\ufeff\x00-\x1f]*','',value).startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


async def export_rows(run_id: str,where=None,args=None):
    where=where or 'run_id=?';args=args or [run_id]
    # StreamingResponse may resume synchronous iterators on a different thread.
    # Never keep a SQLite connection/cursor alive across a streaming yield.
    # Completed runs are immutable; keyset pages bound memory without OFFSET scans.
    after = -1
    while True:
        rows = await asyncio.to_thread(
            db.all_rows,
            "SELECT idx,depth,data FROM result_rows WHERE "+where+" AND idx>? ORDER BY idx LIMIT 500",
            (*args, after),
        )
        if not rows:
            break
        for row in rows:
            yield row
        after = rows[-1]["idx"]


@app.get("/api/runs/{run_id}/export")
def export(run_id: str, format: str = "csv",q:str="",filters:str=""):
    run = run_or_404(run_id)
    where,args=result_filters.predicate(run_id,json.loads(run["columns_json"]),q,filters)
    if run["status"] != "completed":
        raise HTTPException(409, "Run has not completed")
    title = run["plugin"].replace(".", "_")
    if format == "json":
        async def json_stream():
            parts=['[']
            size=1
            first=True
            async for row in export_rows(run_id,where,args):
                data=json.loads(row["data"])
                data["__depth"]=row["depth"]
                encoded=('' if first else ',')+json.dumps(data,ensure_ascii=False)
                parts.append(encoded)
                size+=len(encoded)
                first=False
                if size>=65536:
                    yield ''.join(parts)
                    parts=[];size=0
            yield ''.join(parts)+']'
        return StreamingResponse(json_stream(),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="{title}.json"'})
    if format == "jsonl" and (q or filters):
        raise HTTPException(422,"Raw JSONL cannot be filtered; use CSV or JSON")
    if format == "jsonl":
        if not run['output_dir']:
            raise HTTPException(404,"This run has no raw JSONL file")
        path=Path(run["output_dir"])/"result.jsonl"
        if not path.exists():
            raise HTTPException(404,"This run uses the legacy JSON renderer")
        return FileResponse(path,filename=title+".jsonl",media_type="application/x-ndjson")
    if format != "csv":
        raise HTTPException(400, "Supported formats: csv, json")
    columns = json.loads(run["columns_json"])
    async def stream():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["_row", "_depth", *[csv_safe(col) for col in columns]])
        yield "\ufeff" + buffer.getvalue()
        buffer.seek(0); buffer.truncate(0)
        async for row in export_rows(run_id,where,args):
            data = json.loads(row["data"])
            writer.writerow([row["idx"], row["depth"], *[csv_safe(data.get(col)) for col in columns]])
            if buffer.tell()>=65536:
                yield buffer.getvalue()
                buffer.seek(0); buffer.truncate(0)
        if buffer.tell():
            yield buffer.getvalue()
    return StreamingResponse(stream(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{title}.csv"'})


@app.get("/api/cases/{case_id}/bookmarks")
def bookmarks(case_id: str):
    case_or_404(case_id)
    rows = db.all_rows("""SELECT b.*,r.plugin,d.data FROM bookmarks b JOIN runs r ON r.id=b.run_id
                        JOIN result_rows d ON d.run_id=b.run_id AND d.idx=b.row_idx
                        WHERE b.case_id=? ORDER BY b.created DESC""", (case_id,))
    return [{**r, "data": json.loads(r["data"])} for r in rows]


@app.post("/api/cases/{case_id}/bookmarks", status_code=201)
def bookmark(case_id: str, values: BookmarkInput):
    run = run_or_404(values.run_id)
    if run["case_id"] != case_id:
        raise HTTPException(400, "Row belongs to a different case")
    if not db.one("SELECT idx FROM result_rows WHERE run_id=? AND idx=?", (values.run_id, values.row_idx)):
        raise HTTPException(404, "Row not found")
    db.execute("""INSERT INTO bookmarks VALUES (?,?,?,?,?,?)
               ON CONFLICT(run_id,row_idx) DO UPDATE SET note=CASE WHEN ? THEN excluded.note ELSE bookmarks.note END""",
               (uuid.uuid4().hex[:16], case_id, values.run_id, values.row_idx, values.note, db.now(), "note" in values.model_fields_set))
    return {"ok": True}


@app.delete("/api/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: str):
    db.execute("DELETE FROM bookmarks WHERE id=?", (bookmark_id,))
    return {"ok": True}


@app.get("/api/cases/{case_id}/report", response_class=HTMLResponse)
def report(case_id: str):
    case = case_or_404(case_id)
    jobs = runs(case_id)
    saved = bookmarks(case_id)
    esc = lambda v: html.escape(str(v if v is not None else ""))
    rows = "".join(f"<tr><td>{esc(r['plugin'])}</td><td>{esc(r['status'] + (' · PARTIAL (row limit)' if r.get('pipeline_summary',{}).get('limit_reached') else ''))}</td><td>{r['row_count']}</td><td>{esc(r['started'])}</td></tr>" for r in jobs)
    findings = "".join(f"<article><h3>{esc(b['plugin'])} · row {b['row_idx']+1}</h3><p>{esc(b['note'])}</p><pre>{esc(json.dumps(b['data'],ensure_ascii=False,indent=2))}</pre></article>" for b in saved)
    provenance = "".join(f"<details><summary>{esc(r['plugin'])} · {esc(r['id'])}</summary><pre>{esc(r['command'])}\n\nParameters: {esc(json.dumps(r['params'],ensure_ascii=False,indent=2))}\nWorker argv: {esc(r.get('worker_command',''))}\nPipeline summary: {esc(json.dumps(r.get('pipeline_summary',{}),ensure_ascii=False))}</pre><p>Studio used: {esc(r.get('studio_version') or 'not recorded (legacy or not started)')}<br>Studio EXE SHA-256: {esc(r.get('studio_sha256') or 'not recorded (source, legacy or not started)')}<br>Engine: {esc(r['engine_version'])} · SHA-256: {esc(r['input_sha256'])} · Offline: {r['offline']}</p></details>" for r in jobs)
    content = f"""<!doctype html><html lang="ru"><meta charset="utf-8"><title>{esc(case['name'])} · volati elite</title>
    <style>body{{font:15px/1.6 system-ui;max-width:1100px;margin:60px auto;padding:0 30px;color:#18212e}}h1{{letter-spacing:-1px;overflow-wrap:anywhere}}p{{overflow-wrap:anywhere}}.brand{{color:#d96c2e;font-weight:800}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;border-bottom:1px solid #ddd;padding:12px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5f7;padding:18px;border-radius:8px}}article{{border:1px solid #ddd;padding:20px;margin:20px 0;border-radius:12px}}.demo{{background:#fff1dd;padding:15px}}@media print{{body{{margin:0}}details{{display:block}}}}</style>
    <div class="brand">VOLATILITY STUDIO / CASE REPORT</div><h1>{esc(case['name'])}</h1>
    {'<p class="demo">SYNTHETIC DEMONSTRATION. No memory image was analysed.</p>' if case['kind']=='demo' else ''}
    <p>Generated: {esc(db.now())} · Report generated by Studio {esc(__version__)} · Times retain UTC offsets.</p><p>Image: {esc(case['path'])}<br>SHA-256: {esc(case['sha256'])}<br>Hash status: {esc(case['hash_status'])}</p>
    <h2>Analyst notes</h2><pre>{esc(case['notes'])}</pre><h2>Plugin runs</h2><table><tr><th>Plugin</th><th>Status</th><th>Rows</th><th>Started (UTC)</th></tr>{rows}</table>
    <h2>Bookmarked observations</h2>{findings or '<p>No observations bookmarked.</p>'}<h2>Execution provenance</h2>{provenance}
    <p>Independent interface powered by Volatility 3. Plugin output and analyst interpretations are distinct. An empty result does not establish absence of malicious activity.</p></html>"""
    return HTMLResponse(content, headers={"Content-Disposition": f'attachment; filename="case-{case_id}.html"'})


@app.get("/api/cases/{case_id}/timeline")
def timeline(case_id: str,offset: int=Query(default=0,ge=0),limit: int=Query(default=100,ge=1,le=500),q: str=Query(default='',max_length=512),scope: Literal['all','latest']='all',run_id: str=Query(default='',max_length=64)):
    case_or_404(case_id)
    if run_id:
        if scope!='all':raise HTTPException(422,'Choose a run or the latest-runs view, not both')
        run=run_or_404(run_id)
        if run['case_id']!=case_id or run['status']!='completed':raise HTTPException(404,'Completed run not found in this case')
    from .timeline import page
    return page(case_id,offset,limit,q,scope,run_id)


@app.post("/api/demo", status_code=201)
def open_demo():
    existing = db.one("SELECT * FROM cases WHERE id='demo'")
    if not existing:
        db.execute("""INSERT INTO cases (id,name,path,os,kind,size,created,hash_status,notes)
                   VALUES ('demo','Northstar · Memory investigation','SYNTHETIC / northstar-workstation.raw','windows','demo',8589934592,?,'demo',?)""",
                   (db.now(), "Учебный кейс. Все записи синтетические; IP из диапазонов документации. Закладки — наблюдения аналитика, не автоматический вердикт."))
        for suffix in ("info.Info", "pslist.PsList", "netscan.NetScan"):
            p = next((p for p in catalog.CATALOG["plugins"] if p["id"] == "windows." + suffix), None)
            if p:
                enqueue("demo", RunInput(plugin=p["id"]))
    return case_or_404("demo")


DIST = ROOT / "frontend" / "dist"
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}")
def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "API route not found")
    if DIST.is_dir():
        candidate = (DIST / path).resolve()
        if candidate.is_file() and DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        prefs=db.settings()
        language=prefs.get('language') if prefs.get('language') in SUPPORTED_LANGUAGES else default_language()
        theme='light' if prefs.get('theme')=='light' else 'dark'
        content=(DIST/'index.html').read_text(encoding='utf8')
        content=content.replace('<html lang="ru">',f'<html lang="{language}" data-theme="{theme}" data-hide-tip="{str(bool(prefs.get("hide_tip"))).lower()}">')
        return HTMLResponse(content,headers={'Cache-Control':'no-store'})
    return HTMLResponse("<h1>volati elite</h1><p>Frontend not built. Run npm install and npm run build in frontend/.</p>", status_code=503)
