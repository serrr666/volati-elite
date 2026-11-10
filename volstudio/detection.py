"""Observable, conservative image detection: Banners first, Windows Info fallback."""
import json
import uuid
import re
from urllib.parse import unquote
from pathlib import Path
from . import db,catalog


def queue(case_id,plugin,purpose):
    from .runner import WAKE
    if not catalog.get_plugin(plugin):
        db.execute("UPDATE cases SET detect_status='unknown',detect_message=? WHERE id=?",("Required detection plugin is not installed",case_id))
        return
    cfg=db.settings()
    db.execute("""INSERT INTO runs (id,case_id,plugin,params,status,created,engine_version,offline,settings_json,purpose)
                  VALUES (?,?,?,'{}','queued',?,?,?,?,?)""",
               (uuid.uuid4().hex[:16],case_id,plugin,db.now(),catalog.CATALOG["version"],int(cfg["offline"]),json.dumps(cfg),purpose))
    WAKE.set()


def start(case_id, auto=True):
    case=db.one("SELECT * FROM cases WHERE id=?",(case_id,))
    from .preflight import inspect_source
    # Persist canonical messages; the interface translates at display time.
    # A case must not retain the UI language used when it was imported.
    source=inspect_source(case['path'])
    db.execute('UPDATE cases SET source_kind=?,image_format=? WHERE id=?',(source['kind'],source['format'],case_id))
    if source['kind']!='memory':
        db.execute('UPDATE cases SET os=\'unknown\',detected_banner=\'\',detect_status=?,detect_message=? WHERE id=?',(source['kind'],source['message'],case_id))
        return
    if not auto:
        db.execute("UPDATE cases SET detect_status='manual',detect_message=? WHERE id=?",('ОС выбрана аналитиком',case_id))
        return
    db.execute("UPDATE cases SET os='unknown',detected_banner='',detect_status='banners',detect_message='Ищем баннер ядра через Volatility Banners' WHERE id=?",(case_id,))
    queue(case_id,"banners.Banners","detection-banners")


def windows_banner_from_info(run_id):
    for row in db.all_rows('SELECT data FROM result_rows WHERE run_id=?',(run_id,)):
        data=json.loads(row['data'])
        if data.get('Variable')!='Symbols' or not isinstance(data.get('Value'),str):continue
        path=unquote(data['Value']).replace('\\','/')
        match=re.search(r'/([^/]+\.pdb)/([0-9a-f]{32})-(\d+)\.json(?:\.(?:xz|gz|bz2))?$',path,re.I)
        if match:return f'{match[1]}|{match[2].upper()}|{match[3]}'
    return ''


def after_run(run,success):
    case_id=run["case_id"]
    current=db.one("SELECT detect_status FROM cases WHERE id=?",(case_id,))
    if not current or current["detect_status"] in ("manual","cancelled"):
        return
    if run["purpose"]=="detection-banners":
        if success:
            for row in db.all_rows("SELECT data FROM result_rows WHERE run_id=?",(run["id"],)):
                data=json.loads(row["data"])
                for val in data.values():
                    if not isinstance(val,str):
                        continue
                    os_name="linux" if "Linux version " in val else "mac" if "Darwin Kernel Version" in val else None
                    if os_name:
                        db.execute("UPDATE cases SET os=?,detect_status='complete',detected_banner=?,detect_message='ОС определена по баннеру ядра' WHERE id=?",(os_name,val[:4000],case_id))
                        return
        windows_banner=''
        if success:
            for row in db.all_rows('SELECT data FROM result_rows WHERE run_id=?',(run['id'],)):
                for val in json.loads(row['data']).values():
                    if isinstance(val,str) and val.lower().startswith(('ntkr','ntoskrnl')) and '.pdb|' in val.lower():
                        windows_banner=val[:4000]
                        break
        if windows_banner:
            db.execute("UPDATE cases SET os='windows',detected_banner=?,detect_status='windows',detect_message='Найден идентификатор ядра Windows. Проверяем структуры памяти через Info.' WHERE id=?",(windows_banner,case_id))
        else:
            db.execute("UPDATE cases SET detect_status='windows',detect_message='Баннер не найден. Проверяем слой Windows через Info' WHERE id=?",(case_id,))
        queue(case_id,"windows.info.Info","detection-windows")
    elif success and db.one("SELECT row_count FROM runs WHERE id=?",(run["id"],))["row_count"]:
        db.execute("UPDATE cases SET os='windows',detect_status='complete',detected_banner=?,detect_message='Windows определена по успешно разобранному слою памяти' WHERE id=?",(windows_banner_from_info(run['id']),case_id))
    else:
        case=db.one('SELECT os,detected_banner FROM cases WHERE id=?',(case_id,))
        if case['os']=='windows' and case['detected_banner']:
            db.execute("UPDATE cases SET detect_status='identified',detect_message='Ядро Windows обнаружено, но структуры памяти не разобраны. Откройте журнал Info: причина может быть в неполных данных типов или формате памяти.' WHERE id=?",(case_id,))
        else:
            db.execute("UPDATE cases SET detect_status='unknown',detect_message='Автоматически определить ОС не удалось. Проверьте журнал и выберите ОС вручную.' WHERE id=?",(case_id,))
