import hashlib
import json
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from volstudio import catalog,db,runner
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db.DATA=tmp_path_factory.mktemp("studio-state")
    with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as c:
        db.save_settings({"offline":True})
        yield c


def wait(client,case_id,predicate,timeout=45):
    until=time.monotonic()+timeout
    while time.monotonic()<until:
        runs=client.get(f"/api/cases/{case_id}/runs").json()
        if predicate(runs):
            return runs
        time.sleep(.1)
    raise AssertionError(f"Timed out: {runs}")


@pytest.fixture(scope="module")
def image(tmp_path_factory):
    path=tmp_path_factory.mktemp("evidence")/"образ памяти.raw"
    banner=b"Linux version 6.1.0-studio (builder@lab) (gcc 12.2.0) #1 SMP Tue Oct 28 09:00:00 UTC 2026\x00"
    data=bytearray(1024*1024)
    data[8192:8192+len(banner)]=banner
    path.write_bytes(data)
    return path


def test_real_catalog_and_requirements(client):
    h=client.get("/api/health").json()
    assert h["engine_status"]=="ready",h
    assert h["plugin_count"]>=150
    p=next(p for p in client.get("/api/plugins").json()["plugins"] if p["id"]=="windows.pslist.PsList")
    assert next(a for a in p["args"] if a["name"]=="pid")["type"]=="list_int"


@pytest.mark.parametrize('plugin,expected',[
    ('windows.pslist.PsList','process'),('windows.dlllist.DllList','process'),
    ('windows.mftscan.ResidentData','files'),('linux.lsof.Lsof','files'),
    ('mac.ifconfig.Ifconfig','network'),('windows.malware.psxview.PsXView','malware'),
    ('windows.registry.printkey.PrintKey','registry'),('windows.orphan_kernel_threads.Threads','kernel'),
])
def test_categories_use_whole_names(plugin,expected):
    assert catalog.category(plugin)==expected


def test_pipeline_strings_cross_chunk_boundaries(tmp_path,monkeypatch):
    from volstudio import pipeline
    monkeypatch.setattr(pipeline,'CHUNK_SIZE',17)
    path=tmp_path/'строки.raw'
    ascii_text=b'https://example.test/powershell'
    wide='PowerShell кириллица'.encode('utf-16le')
    data=b'\x00'*13+ascii_text+b'\x00'*5+wide+b'\x00\x00'
    path.write_bytes(data)
    rows=list(pipeline.image_rows(path,pipeline.PipelineInput(source='image'),lambda *_:None))
    a=next(r for r in rows if r['Text']==ascii_text.decode())
    w=next(r for r in rows if r['Text']=='PowerShell кириллица')
    assert a['Offset']==hex(13) and w['Offset']==hex(13+len(ascii_text)+5)
    assert w['Encoding']=='utf16le' and path.read_bytes()==data
    # A long printable run is bounded and split, with no byte loss.
    stream=pipeline.StringStream('ascii',4)
    long=b'A'*(pipeline.STRING_FRAGMENT*2+3)
    fragments=[]
    for pos in range(0,len(long),17):fragments+=list(stream.feed(long[pos:pos+17],pos))
    fragments+=list(stream.feed(b'',len(long),eof=True))
    assert ''.join(r['Text'] for r in fragments)==long.decode()
    assert all(len(r['Text'])<=pipeline.STRING_FRAGMENT for r in fragments)
    assert [r['Offset'] for r in fragments]==[hex(0),hex(pipeline.STRING_FRAGMENT),hex(pipeline.STRING_FRAGMENT*2)]


def test_pipeline_result_chain_and_provenance(client,demo_case):
    source=next(r for r in demo_case if 'pslist' in r['plugin'])
    response=client.post('/api/cases/demo/pipeline',json={'source':'results','source_run':source['id'],'steps':[
        {'op':'compare','field':'PID','comparison':'gt','value':'1000'},
        {'op':'contains','field':'ImageFileName','value':'POWERshell'},
        {'op':'select','fields':['PID','ImageFileName']},
        {'op':'unique','fields':['ImageFileName']},
    ]})
    assert response.status_code==201,response.text
    run_id=response.json()['id']
    jobs=wait(client,'demo',lambda rs:any(r['id']==run_id and r['status'] in ('completed','failed') for r in rs))
    job=next(r for r in jobs if r['id']==run_id)
    assert job['status']=='completed',job
    rows=client.get(f'/api/runs/{run_id}/rows').json()['rows']
    assert len(rows)==1 and rows[0]['data']['PID']==4280
    assert rows[0]['data']['_source_run']==source['id'] and isinstance(rows[0]['data']['_source_row'],int)
    assert job['pipeline_summary']['limit_reached'] is False
    # Source results are unchanged, and unknown fields fail before enqueueing.
    assert client.get(f"/api/runs/{source['id']}/rows").json()['total']==17
    assert client.post('/api/cases/demo/pipeline',json={'source_run':source['id'],'steps':[{'op':'select','fields':['typo']}]}).status_code==422


def test_pipeline_limit_is_explicit(client,demo_case):
    source=next(r for r in demo_case if 'pslist' in r['plugin'])
    response=client.post('/api/cases/demo/pipeline',json={'source_run':source['id'],'max_rows':2})
    run_id=response.json()['id']
    jobs=wait(client,'demo',lambda rs:any(r['id']==run_id and r['status'] in ('completed','failed') for r in rs))
    job=next(r for r in jobs if r['id']==run_id)
    assert job['status']=='completed' and job['row_count']==2,job
    assert job['pipeline_summary']['limit_reached'] is True
    assert job['message']=='Pipeline row limit reached'
    assert 'PARTIAL (row limit)' in client.get('/api/cases/demo/report').text


def test_pipeline_split_exclude_and_precise_numbers():
    import sqlite3
    from volstudio.pipeline import Step,apply_steps,number
    with sqlite3.connect(':memory:') as distinct:
        result=apply_steps({'Text':'powershell.exe -NoProfile','Address':'9007199254740993'},[
            Step(op='split',field='Text'),
            Step(op='exclude',field='Field1',value='cmd.exe'),
            Step(op='compare',field='Address',comparison='gt',value='9007199254740992'),
            Step(op='select',fields=['Field1','Field2']),
        ],distinct)
        assert result=={'Field1':'powershell.exe','Field2':'-NoProfile'}
    assert number('0xffffa30450000000')==int('ffffa30450000000',16)
    with pytest.raises(ValueError):Step(op='compare',field='PID',comparison='gt',value='NaN')


def test_pipeline_raw_image_worker(client,image):
    case=client.post('/api/cases',json={'name':'Pipeline image fixture','path':str(image),'os':'unknown'}).json()
    response=client.post(f"/api/cases/{case['id']}/pipeline",json={'source':'image','encoding':'both','steps':[
        {'op':'contains','field':'Text','value':'Linux version'},
        {'op':'select','fields':['Offset','Text']},
    ]})
    assert response.status_code==201,response.text
    run_id=response.json()['id']
    jobs=wait(client,case['id'],lambda rs:any(r['id']==run_id and r['status'] in ('completed','failed') for r in rs))
    job=next(r for r in jobs if r['id']==run_id)
    assert job['status']=='completed',job
    rows=client.get(f'/api/runs/{run_id}/rows').json()['rows']
    assert len(rows)==1 and rows[0]['data']['Offset']=='0x2000'
    assert rows[0]['data']['_source_offset']=='0x2000'


def test_custom_memory_budget_is_saved(client):
    config=client.get('/api/settings').json()
    config['memory_limit_mb']=12800
    response=client.put('/api/settings',json=config)
    assert response.status_code==200,response.text
    assert client.get('/api/settings').json()['memory_limit_mb']==12800
    config['memory_limit_mb']=-1
    assert client.put('/api/settings',json=config).status_code==422
    config['memory_limit_mb']=0
    assert client.put('/api/settings',json=config).status_code==200


def test_real_banners_auto_detection_unicode_path(client,image):
    before=image.read_bytes()
    response=client.post("/api/cases",json={"name":"Linux fixture","path":str(image),"os":"unknown"})
    assert response.status_code==201,response.text
    case_id=response.json()["id"]
    runs=wait(client,case_id,lambda r:r and all(x["status"] in ("completed","failed") for x in r))
    assert len(runs)==1,runs
    assert runs[0]["plugin"]=="banners.Banners" and runs[0]["status"]=="completed",runs
    assert runs[0]["row_count"]==1
    case=next(c for c in client.get("/api/cases").json() if c["id"]==case_id)
    assert case["os"]=="linux" and case["detect_status"]=="complete",case
    assert "Linux version 6.1.0-studio" in case["detected_banner"]
    assert case["sha256"]==hashlib.sha256(before).hexdigest()
    assert image.read_bytes()==before
    exported=client.get(f"/api/runs/{runs[0]['id']}/export?format=json").json()
    assert "Linux version" in exported[0]["Banner"]


@pytest.fixture(scope="module")
def demo_case(client):
    assert client.post("/api/demo").status_code==201
    return wait(client,"demo",lambda rs:len(rs)>=3 and all(r["status"]=="completed" for r in rs))


def test_demo_is_labelled_and_not_real_analysis(client,demo_case):
    run=next(r for r in demo_case if "pslist" in r["plugin"])
    assert run["command"].startswith("DEMO fixture:")
    assert "SYNTHETIC" in client.get(f"/api/runs/{run['id']}/logs").json()["text"]
    assert "SYNTHETIC DEMONSTRATION" in client.get("/api/cases/demo/report").text


def test_pid_filter_and_run_provenance(client,demo_case):
    response=client.post("/api/cases/demo/runs",json={"plugin":"windows.pslist.PsList","params":{"pid":"4280, 4860"}})
    assert response.status_code==201,response.text
    run_id=response.json()["id"]
    runs=wait(client,"demo",lambda rs:any(r["id"]==run_id and r["status"]=="completed" for r in rs))
    run=next(r for r in runs if r["id"]==run_id)
    assert run["params"]=={"pid":[4280,4860]}
    rows=client.get(f"/api/runs/{run_id}/rows").json()
    assert {r["data"]["PID"] for r in rows["rows"]}=={4280,4860}


def test_reject_uninstalled_plugin_and_injected_options(client,demo_case):
    assert client.post("/api/cases/demo/runs",json={"plugin":"powershell.exe -Command calc","params":{}}).status_code==400
    assert client.post("/api/cases/demo/runs",json={"plugin":"windows.pslist.PsList","params":{"unexpected":"; calc"}}).status_code==422
    assert client.post("/api/cases/demo/runs",json={"plugin":"windows.pslist.PsList","params":{"pid":"1;calc"}}).status_code==422


def test_bookmarks_notes_report_escaping_and_case_isolation(client,demo_case,image):
    run=next(r for r in demo_case if "pslist" in r["plugin"])
    note='<script>alert("unsafe")</script>'
    assert client.post("/api/cases/demo/bookmarks",json={"run_id":run["id"],"row_idx":0,"note":note}).status_code==201
    assert client.get("/api/cases/demo/bookmarks").json()[0]["note"]==note
    report=client.get("/api/cases/demo/report").text
    assert note not in report and "&lt;script&gt;" in report
    other=client.post("/api/cases",json={"name":"Separate","path":str(image),"os":"unknown"}).json()
    assert client.post(f"/api/cases/{other['id']}/bookmarks",json={"run_id":run["id"],"row_idx":0}).status_code==400
    assert client.post("/api/cases/demo/bookmarks",json={"run_id":run["id"],"row_idx":999999}).status_code==404


def test_full_dataset_sort_search_pagination_and_csv_formula_safety(client,demo_case,tmp_path):
    run_id=uuid.uuid4().hex[:16]
    out=tmp_path/"output";out.mkdir()
    source=out/"result.json"
    source.write_text(json.dumps([{"PID":i,"Command":"=HYPERLINK(\"https://example.invalid\")" if i==299 else f"process-{i}"} for i in range(300)]))
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created,output_dir) VALUES (?,'demo','fixture','{}','completed',?,?)",(run_id,db.now(),str(out)))
    count,cols=runner.ingest(run_id,source)
    db.update_run(run_id,row_count=count,columns_json=json.dumps(cols))
    rows=client.get(f"/api/runs/{run_id}/rows?sort=PID&direction=desc&offset=100&limit=100").json()
    assert rows["total"]==300 and rows["rows"][0]["data"]["PID"]==199
    assert client.get(f"/api/runs/{run_id}/rows?q=process-250").json()["total"]==1
    assert "'=HYPERLINK" in client.get(f"/api/runs/{run_id}/export").text
    assert client.get(f"/api/runs/{run_id}/artifact?name=../../studio.sqlite3").status_code==404


def test_exports_are_complete_across_pages_and_concurrent_downloads(client,demo_case,tmp_path):
    import concurrent.futures
    import csv
    import io
    run_id=uuid.uuid4().hex[:16]
    out=tmp_path/'export-stress';out.mkdir()
    source=out/'result.json'
    count=2507
    source.write_text(json.dumps([{'PID':i,'Text':f'строка {i}, "quoted"\nnext'} for i in range(count)]),encoding='utf-8')
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created,output_dir) VALUES (?,'demo','export-stress','{}','completed',?,?)",(run_id,db.now(),str(out)))
    n,cols=runner.ingest(run_id,source)
    db.update_run(run_id,row_count=n,columns_json=json.dumps(cols))
    def download(fmt):
        r=client.get(f'/api/runs/{run_id}/export?format={fmt}')
        assert r.status_code==200
        if fmt=='json':
            rows=r.json()
            assert [row['PID'] for row in rows]==list(range(count))
            assert rows[-1]['Text']==f'строка {count-1}, "quoted"\nnext'
        else:
            rows=list(csv.DictReader(io.StringIO(r.content.decode('utf-8-sig'))))
            assert [int(row['_row']) for row in rows]==list(range(count))
            assert rows[-1]['Text']==f'строка {count-1}, "quoted"\nnext'
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(download,['csv','json']*3))


def test_result_search_handles_unicode_and_literal_windows_paths(client,demo_case,tmp_path):
    run_id=uuid.uuid4().hex[:16]
    path=tmp_path/'literal-search.json'
    rows=[{'Text':'ПРОЦЕСС ЁЖ', 'Path':r'C:\Работа\Дамп памяти.raw'},
          {'Text':'He said "quoted"\nnext', 'Path':r'C:\Other\memory.raw'}]
    path.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf8')
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created) VALUES (?,'demo','search-regression','{}','completed',?)",(run_id,db.now()))
    count,columns=runner.ingest(run_id,path);db.update_run(run_id,row_count=count,columns_json=json.dumps(columns))
    for query,expected in [('процесс ёж',0),(r'c:\работа\дамп памяти.raw',0),('"quoted"\nnext',1)]:
        result=client.get(f'/api/runs/{run_id}/rows',params={'q':query}).json()
        assert result['total']==1 and result['rows'][0]['index']==expected


def test_result_hexadecimal_sort_preserves_numeric_address_order(client,demo_case,tmp_path):
    run_id=uuid.uuid4().hex[:16];path=tmp_path/'address-sort.json'
    addresses=['0x100','0x20','0x2','0xFFFFFFFFFFFFFFFF','0x10000000000000000','0x0a']
    path.write_text(json.dumps([{'Offset':a} for a in addresses]),encoding='utf8')
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created) VALUES (?,'demo','sort-regression','{}','completed',?)",(run_id,db.now()))
    count,columns=runner.ingest(run_id,path);db.update_run(run_id,row_count=count,columns_json=json.dumps(columns))
    for direction in ['asc','desc']:
        rows=client.get(f'/api/runs/{run_id}/rows',params={'sort':'Offset','direction':direction}).json()['rows']
        assert [r['data']['Offset'] for r in rows]==sorted(addresses,key=lambda a:int(a,16),reverse=direction=='desc')


def test_logs_distinguish_worker_command_from_volatility_argument_example(client,demo_case):
    run_id=uuid.uuid4().hex[:16]
    worker=[r'C:\Studio\VolatilityStudio.exe','--engine-worker',r"C:\case O'Brien\worker-job.json"]
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created,command,worker_command) VALUES (?,'demo','command-regression','{}','completed',?,?,?)",(run_id,db.now(),"& 'vol' '-f' 'memory.vmss'",json.dumps(worker)))
    result=client.get(f'/api/runs/{run_id}/logs').json()
    assert result['command'].startswith("& 'vol'")
    assert result['worker_command']==runner.powershell_command(worker)
    assert "O''Brien" in result['worker_command'] and '--engine-worker' in result['worker_command']


def test_oversize_notes_fail_without_silently_truncating_the_notebook(client,demo_case):
    original=db.one("SELECT notes FROM cases WHERE id='demo'")['notes']
    response=client.patch('/api/cases/demo',json={'notes':'x'*100001})
    assert response.status_code==422
    assert db.one("SELECT notes FROM cases WHERE id='demo'")['notes']==original


@pytest.mark.parametrize('payload',[
    {'notes':'must not be saved','os':'darwin'},
    {'notes':'must not be saved','name':'   '},
    {'notes':None}, {'name':'x'*161},
    ['notes','invalid body'], {'notes':'must not be saved','path':'other.raw'},
])
def test_invalid_case_patch_is_atomic_and_does_not_coerce_or_truncate(client,demo_case,payload):
    before=db.one("SELECT * FROM cases WHERE id='demo'")
    response=client.patch('/api/cases/demo',json=payload)
    assert response.status_code==422
    assert db.one("SELECT * FROM cases WHERE id='demo'")==before


def test_search_matches_values_not_column_names_json_syntax_or_escaped_storage(client,demo_case,tmp_path):
    rid=uuid.uuid4().hex[:16];source=tmp_path/'values.json'
    source.write_text(json.dumps([{'NeedleKey':'plain','Text':'line\nnext'},
                                  {'NeedleKey':'other','Text':r'literal\nvalue'},
                                  {'NeedleKey':'last','Text':{'nested-key':'СНЕГ'}}],ensure_ascii=True),encoding='utf8')
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created) VALUES (?,'demo','search-values','{}','completed',?)",(rid,db.now()))
    count,cols=runner.ingest(rid,source);db.update_run(rid,row_count=count,columns_json=json.dumps(cols))
    for q,expected in [('NeedleKey',[]),('nested-key',[]),('": "',[]),('line\nnext',[0]),(r'\n',[1]),('снег',[2])]:
        response=client.get(f'/api/runs/{rid}/rows',params={'q':q})
        assert response.status_code==200
        assert [r['index'] for r in response.json()['rows']]==expected
    assert client.get(f'/api/runs/{rid}/rows',params={'q':'x'*1001}).status_code==422


def test_csv_protects_formula_headers_without_changing_json(client,demo_case,tmp_path):
    import csv,io
    rid=uuid.uuid4().hex[:16];source=tmp_path/'header.json';header='=HYPERLINK("https://example.invalid")'
    source.write_text(json.dumps([{header:'unchanged','Text':'safe'}]),encoding='utf8')
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created) VALUES (?,'demo','csv-header','{}','completed',?)",(rid,db.now()))
    count,cols=runner.ingest(rid,source);db.update_run(rid,row_count=count,columns_json=json.dumps(cols))
    rows=list(csv.reader(io.StringIO(client.get(f'/api/runs/{rid}/export').content.decode('utf-8-sig'))))
    assert rows[0][2]=="'"+header and rows[1][2]=='unchanged'
    assert client.get(f'/api/runs/{rid}/export?format=json').json()[0][header]=='unchanged'


def test_artifacts_are_complete_outputs_not_internal_files_or_windows_aliases(client,demo_case,tmp_path):
    out=tmp_path/'artifact-boundary';out.mkdir();(out/'process.dmp').write_bytes(b'QA artifact; never execute')
    for name in ['worker-job.json','engine.log','result.jsonl','pipeline-summary.json']:(out/name).write_text('internal',encoding='utf8')
    rid=uuid.uuid4().hex[:16]
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created,output_dir) VALUES (?,'demo','artifact-check','{}','completed',?,?)",(rid,db.now(),str(out)))
    assert [r['name'] for r in client.get(f'/api/runs/{rid}/artifacts').json()]==['process.dmp']
    assert client.get(f'/api/runs/{rid}/artifact',params={'name':'process.dmp'}).content==b'QA artifact; never execute'
    for name in ['worker-job.json','WORKER-JOB.JSON','worker-job.json.','engine.log','result.jsonl','pipeline-summary.json','../studio.sqlite3',str(tmp_path/'outside.raw'),'process.dmp:stream','bad\x00name']:
        assert client.get(f'/api/runs/{rid}/artifact',params={'name':name}).status_code==404,name
    for status in ['running','indexing','failed','cancelled']:
        db.update_run(rid,status=status)
        assert client.get(f'/api/runs/{rid}/artifacts').json()==[]
        assert client.get(f'/api/runs/{rid}/artifact',params={'name':'process.dmp'}).status_code==409
    db.update_run(rid,status='completed')


def test_legacy_jsonl_export_returns_clear_not_found(client,demo_case):
    rid=uuid.uuid4().hex[:16]
    db.execute("INSERT INTO runs (id,case_id,plugin,params,status,created) VALUES (?,'demo','legacy-no-output','{}','completed',?)",(rid,db.now()))
    assert client.get(f'/api/runs/{rid}/export?format=jsonl').status_code==404


def test_failure_diagnostic_reads_only_a_bounded_log_tail(tmp_path):
    log=tmp_path/'large.log'
    with log.open('wb') as stream:
        stream.seek(32*1024*1024);stream.write(b'\nlast error: QA failure\n')
    tail=runner.log_tail(log,12000)
    assert len(tail.encode('utf8'))<=12000 and tail.endswith('last error: QA failure\n')


def test_note_drafts_persist_separately_from_reports_and_cases(client,demo_case,image):
    text='QA-DRAFT-ONLY: несохранённая гипотеза'
    other=client.post('/api/cases',json={'name':'draft scope','path':str(image),'os':'linux'}).json()['id']
    assert client.put('/api/cases/demo/draft',json={'text':text}).status_code==200
    assert client.get('/api/cases/demo/draft').json()['text']==text
    assert client.get(f'/api/cases/{other}/draft').json()['text'] is None
    # A fresh SQLite connection proves this is independent of browser origin.
    assert db.one("SELECT text FROM note_drafts WHERE case_id='demo'")['text']==text
    assert 'QA-DRAFT-ONLY' not in client.get('/api/cases/demo/report').text
    assert client.put('/api/cases/demo/draft',json={'text':'x'*100001}).status_code==422
    assert client.get('/api/cases/demo/draft').json()['text']==text
    assert client.put('/api/cases/demo/draft',json={'text':None}).status_code==200
    assert client.get('/api/cases/demo/draft').json()['text'] is None
    assert client.put('/api/cases/missing/draft',json={'text':'wrong case'}).status_code==404


def test_zero_rows_is_success_not_false_findings(client,demo_case):
    r=client.post("/api/cases/demo/runs",json={"plugin":"windows.pslist.PsList","params":{"pid":[999999]}}).json()
    jobs=wait(client,"demo",lambda rs:any(x["id"]==r["id"] and x["status"]=="completed" for x in rs))
    job=next(x for x in jobs if x["id"]==r["id"])
    assert job["row_count"]==0
    assert client.get(f"/api/runs/{r['id']}/rows").json()["rows"]==[]


def test_cancel_queued_run_and_keep_it_cancelled(client,demo_case):
    with runner.PROCESS_LOCK:
        r=client.post("/api/cases/demo/runs",json={"plugin":"windows.pslist.PsList","params":{}}).json()
        # Cancel directly under the same re-entrant DB lock before worker can launch it.
        db.update_run(r["id"],status="cancelled",finished=db.now())
    time.sleep(.3)
    assert db.one("SELECT status FROM runs WHERE id=?",(r["id"],))["status"]=="cancelled"


def test_origin_and_host_boundaries(client):
    assert client.post("/api/demo",headers={"Origin":"https://example.invalid"}).status_code==403
    assert client.get("/api/health",headers={"Host":"example.invalid"}).status_code==400


def test_session_token_is_required_and_not_exposed(client):
    outsider=TestClient(app)
    assert outsider.get('/api/cases').status_code==403
    assert outsider.post('/api/demo').status_code==403
    assert outsider.get('/').status_code==403
    assert outsider.get('/api/health',headers={TOKEN_HEADER:'wrong'}).status_code==403
    body=client.get('/').text
    assert API_TOKEN not in body
    assert client.get('/api/health').status_code==200


def test_security_headers_and_initial_theme(client):
    assert client.put('/api/preferences',json={'language':'en','theme':'light','hide_tip':True}).status_code==200
    page=client.get('/')
    assert 'data-theme="light"' in page.text and 'data-hide-tip="true"' in page.text
    assert 'script-src \'self\'' in page.headers['content-security-policy']
    assert page.headers['x-frame-options']=='DENY'
    assert client.get('/api/cases').headers['cache-control']=='no-store'


@pytest.mark.skipif(__import__('os').name!='nt',reason='Windows mandatory file sharing semantics')
def test_evidence_guard_allows_reads_and_denies_writes(tmp_path):
    from volstudio.evidence import read_guard
    path=tmp_path/'evidence.raw';path.write_bytes(b'unchanged')
    with read_guard(path):
        assert path.read_bytes()==b'unchanged'
        with pytest.raises(OSError):
            with path.open('r+b'):pass
        with pytest.raises(OSError):path.unlink()
    assert path.read_bytes()==b'unchanged'
    with path.open('r+b') as stream:assert stream.read()==b'unchanged'


def test_manual_os_is_not_overridden(client,image):
    response=client.post('/api/cases',json={'path':str(image),'name':'Manual OS selection','os':'windows'})
    assert response.status_code==201,response.text
    case=response.json()
    assert case['os']=='windows' and case['detect_status']=='manual'
    assert client.get(f"/api/cases/{case['id']}/runs").json()==[]


@pytest.mark.parametrize('payload',['=cmd','  +cmd','\t@cmd','\ufeff=cmd','\x00=cmd','\ufeff \x00\t@cmd'])
def test_csv_formula_prefixes(payload):
    from volstudio.app import csv_safe
    assert csv_safe(payload).startswith("'")


def test_non_ascii_session_key_is_rejected():
    from volstudio.security import authenticated
    assert authenticated('\ufffd') is False


def test_equivalent_commands_quote_literals(tmp_path,client):
    literal="a'$(test) --help"
    cmd=runner.command_for({'path':'memory image.raw'},'yarascan.YaraScan',{'yara-rules':literal},tmp_path,{'offline':True,'symbol_dirs':[],'plugin_dirs':[]})
    assert cmd[-1]=='--yara-rules='+literal
    shown=runner.powershell_command(['vol','--yara-rules='+literal])
    assert shown=="& 'vol' '--yara-rules=a''$(test) --help'"


@pytest.mark.parametrize('languages,expected',[(['en-US'],'en'),(['en-US','ru-RU'],'ru'),(['ru_RU'],'ru'),(['de-DE'],'de'),([],'en')])
def test_initial_language_uses_configured_os_locale(monkeypatch,languages,expected):
    from volstudio import localization
    localization.default_language.cache_clear()
    monkeypatch.setattr(localization,'configured_languages',lambda:languages)
    assert localization.default_language()==expected
    localization.default_language.cache_clear()


def test_language_and_theme_preferences_survive_engine_settings(client):
    preferences = {
        'language': 'en', 'theme': 'light', 'last_case': 'demo', 'hide_tip': False,
        'hidden_recent_cases': ['demo'], 'favorite_plugins': ['windows.filescan.FileScan'],
    }
    assert client.put('/api/preferences', json=preferences).status_code == 200
    cfg=client.get('/api/settings').json()
    cfg['memory_limit_mb']=1024
    assert client.put('/api/settings',json=cfg).status_code==200
    pref=client.get('/api/preferences').json()
    assert pref == {**preferences, 'open_cases': ['demo']}
    assert client.put('/api/preferences',json={'language':'broken','theme':'dark'}).status_code==422
    assert client.put('/api/preferences',json={'language':'en','theme':'light','last_case':'demo','hide_tip':True}).status_code==200
    assert client.get('/api/preferences').json()['hide_tip'] is True


def test_absent_evidence_clear_validation(client,tmp_path):
    assert client.post("/api/cases",json={"name":"Missing","path":str(tmp_path/"absent.raw")}).status_code==400
    empty=tmp_path/"empty.raw";empty.write_bytes(b"")
    assert client.post("/api/cases",json={"name":"Empty","path":str(empty)}).status_code==400


def test_broken_custom_plugin_does_not_replace_working_settings(client,tmp_path):
    old=client.get('/api/settings').json()
    plugin_dir=tmp_path/'broken_plugins';plugin_dir.mkdir()
    (plugin_dir/'broken.py').write_text('not valid python !!!',encoding='utf8')
    attempt={**old,'plugin_dirs':[str(plugin_dir)]}
    response=client.put('/api/settings',json=attempt)
    assert response.status_code==422,response.text
    assert client.get('/api/settings').json()['plugin_dirs']==old['plugin_dirs']
    assert client.get('/api/health').json()['plugin_count']>=150


def test_timeline_retains_source_and_explicit_utc(client,demo_case):
    data=client.get("/api/cases/demo/timeline").json()
    assert data["events"]
    assert all(e["time"].endswith("+00:00") and e["run_id"] and isinstance(e["row_idx"],int) for e in data["events"])


def test_raw_arguments_are_not_shell_code():
    cmd=runner.command_for({"path":"C:\\Evidence\\image & name.raw"},"windows.cmdline.CmdLine",{"pid":[12,34]},Path("C:/output"),{"offline":True,"symbol_dirs":[],"plugin_dirs":[]})
    assert cmd[-3:]==["--pid","12","34"]
    assert "C:\\Evidence\\image & name.raw" in cmd


def test_exact_source_row_and_auxiliary_preflight(client,demo_case,tmp_path):
    event=client.get('/api/cases/demo/timeline').json()['events'][0]
    exact=client.get(f"/api/runs/{event['run_id']}/rows/{event['row_idx']}")
    assert exact.status_code==200
    assert exact.json()['index']==event['row_idx'] and exact.json()['data']==event['data']
    assert client.get(f"/api/runs/{event['run_id']}/rows/999999999").status_code==404
    source=tmp_path/'System.map-2.6.32-38-server'
    source.write_bytes(b'ffffffff81000000 T start_kernel\n')
    response=client.post('/api/cases',json={'name':source.name,'path':str(source)})
    assert response.status_code==201,response.text
    case=response.json()
    assert case['source_kind']=='auxiliary' and case['detect_status']=='auxiliary'
    assert client.get(f"/api/cases/{case['id']}/runs").json()==[]
    blocked=client.post(f"/api/cases/{case['id']}/runs",json={'plugin':'linux.pslist.PsList','params':{}})
    assert blocked.status_code==409
    assert client.post(f"/api/cases/{case['id']}/detect").json()['source_kind']=='auxiliary'


def test_source_explanation_does_not_pin_import_language(client,tmp_path):
    previous=client.get('/api/preferences').json()
    try:
        client.put('/api/preferences',json={**previous,'language':'en'})
        path=tmp_path/'profile.dwarf';path.write_bytes(b'\n.debug_info\nDW_TAG_compile_unit\n')
        case=client.post('/api/cases',json={'name':path.name,'path':str(path)}).json()
        assert case['source_kind']=='auxiliary' and case['detect_message'].startswith('Это текстовое описание')
        client.put('/api/preferences',json={**previous,'language':'ru'})
        cases=client.get('/api/cases').json()
        assert next(c for c in cases if c['id']==case['id'])['detect_message']==case['detect_message']
        assert client.get(f"/api/cases/{case['id']}/runs").json()==[]
    finally:
        client.put('/api/preferences',json=previous)


@pytest.mark.parametrize('column',['Quote"Field','both."quoted"',r'slash\key','Name.with.dot',' space ','日本語','x") DESC; --'])
def test_literal_column_names_sort_actual_values(client,demo_case,tmp_path,column):
    run_id=uuid.uuid4().hex[:16]
    source=tmp_path/(run_id+'.json')
    source.write_text(json.dumps([{column:n,'Label':str(n)} for n in [100,2,30]],ensure_ascii=False),encoding='utf8')
    db.execute("INSERT INTO runs(id,case_id,plugin,params,status,created) VALUES (?,'demo','quoted-columns','{}','completed',?)",(run_id,db.now()))
    count,columns=runner.ingest(run_id,source)
    db.update_run(run_id,row_count=count,columns_json=json.dumps(columns))
    for direction,expected in [('asc',[2,30,100]),('desc',[100,30,2])]:
        response=client.get(f'/api/runs/{run_id}/rows',params={'sort':column,'direction':direction})
        assert response.status_code==200,response.text
        assert [r['data'][column] for r in response.json()['rows']]==expected


def test_large_export_cells_survive_stream_boundaries(client,demo_case,tmp_path):
    import csv,io
    run_id=uuid.uuid4().hex[:16]
    source=tmp_path/'large-cells.jsonl'
    records=[{'PID':i,'Text':('я🔎,\n"'*20000 if i==501 else 'café, Ελληνικά, 中文 '+str(i))} for i in range(1003)]
    source.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in records),encoding='utf8')
    db.execute("INSERT INTO runs(id,case_id,plugin,params,status,created) VALUES (?,'demo','large-cells','{}','completed',?)",(run_id,db.now()))
    count,columns=runner.ingest(run_id,source);db.update_run(run_id,row_count=count,columns_json=json.dumps(columns))
    exported=client.get(f'/api/runs/{run_id}/export?format=json').json()
    assert [{k:v for k,v in r.items() if k!='__depth'} for r in exported]==records
    previous=csv.field_size_limit(1000000)
    try:
        csvrows=list(csv.DictReader(io.StringIO(client.get(f'/api/runs/{run_id}/export').content.decode('utf-8-sig'))))
        assert [r['Text'] for r in csvrows]==[r['Text'] for r in records]
        assert [int(r['_row']) for r in csvrows]==list(range(1003))
    finally:
        csv.field_size_limit(previous)


def test_changed_evidence_cannot_be_published_as_success(client,image,tmp_path):
    path=tmp_path/'changed-evidence.raw';path.write_bytes(image.read_bytes())
    attached=client.post('/api/cases',json={'name':'Mutation control','path':str(path),'os':'linux'})
    assert attached.status_code==201,attached.text
    case=attached.json();until=time.monotonic()+10
    while time.monotonic()<until:
        stored=db.one('SELECT * FROM cases WHERE id=?',(case['id'],))
        if stored['hash_status']=='complete':break
        time.sleep(.05)
    assert stored['hash_status']=='complete'
    with path.open('ab') as stream:stream.write(b'MUTATION CONTROL')
    started=client.post(f"/api/cases/{case['id']}/runs",json={'plugin':'banners.Banners','params':{}})
    assert started.status_code==201,started.text
    run=started.json()
    jobs=wait(client,case['id'],lambda rs:any(r['id']==run['id'] and r['status']=='failed' for r in rs))
    failed=next(r for r in jobs if r['id']==run['id'])
    assert 'Evidence changed since hashing' in failed['error'] and failed['row_count']==0
    assert client.get(f"/api/runs/{run['id']}/artifacts").json()==[]
    assert client.get(f"/api/runs/{run['id']}/export").status_code==409


def test_runtime_fingerprint_hashes_frozen_binary(tmp_path,monkeypatch):
    import sys
    from volstudio import __version__
    binary=tmp_path/'Studio.exe';binary.write_bytes(b'SYNTHETIC executable fingerprint fixture')
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(sys,'executable',str(binary))
    runner.runtime_provenance.cache_clear()
    try:
        recorded=runner.runtime_provenance()
        assert recorded=={'studio_version':__version__,'studio_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
    finally:
        runner.runtime_provenance.cache_clear()


def test_execution_version_is_historical_not_the_report_generator_version(client,demo_case,monkeypatch):
    import importlib
    from volstudio import __version__
    legacy_id=uuid.uuid4().hex[:16]
    db.execute("INSERT INTO runs(id,case_id,plugin,params,status,created,engine_version) VALUES (?,'demo','legacy-version-control','{}','completed',?,'2.28.2')",(legacy_id,db.now()))
    legacy=db.one('SELECT * FROM runs WHERE id=?',(legacy_id,))
    assert legacy['studio_version']=='' and legacy['studio_sha256']==''
    queued=client.post('/api/cases/demo/runs',json={'plugin':'windows.pslist.PsList','params':{'pid':[4]}}).json()
    jobs=wait(client,'demo',lambda rs:any(r['id']==queued['id'] and r['status']=='completed' for r in rs))
    executed=next(r for r in jobs if r['id']==queued['id'])
    assert executed['studio_version']==__version__
    assert executed['studio_sha256']==''  # source test process has no frozen EXE
    monkeypatch.setattr(importlib.import_module('volstudio.app'),'__version__','99.99-report-only')
    report=client.get('/api/cases/demo/report').text
    assert 'Report generated by Studio 99.99-report-only' in report
    assert 'Studio used: '+__version__ in report
    assert 'Studio used: not recorded (legacy or not started)' in report
