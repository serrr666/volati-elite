import json
import pytest
from fastapi.testclient import TestClient
from volstudio import db
from volstudio.app import app
from volstudio.security import TOKEN_HEADER,API_TOKEN

@pytest.fixture
def client35(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'qa35')
    with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:
        db.save_settings({'offline':True})
        with db.connection() as c:
            for cid in ['A','B']:
                c.execute("INSERT INTO cases(id,name,path,os,kind,size,created,hash_status) VALUES (?,?,?,'windows','demo',0,?,'demo')",(cid,cid,'SYNTHETIC',db.now()))
            for rid,cid,plugin,status,created in [
                ('old','A','qa.Processes','completed','2026-11-01T01:00:00Z'),
                ('new-a','A','qa.Processes','completed','2026-11-02T01:00:00Z'),
                ('new-z','A','qa.Processes','completed','2026-11-02T01:00:00Z'),
                ('failed','A','qa.Processes','failed','2026-11-03T01:00:00Z'),
                ('network','A','qa.Network','completed','2026-11-01T01:00:00Z'),
                ('other','B','qa.Processes','completed','2026-11-04T01:00:00Z')]:
                c.execute("INSERT INTO runs(id,case_id,plugin,params,status,created,row_count) VALUES (?,?,?,'{}',?,?,1)",(rid,cid,plugin,status,created))
                c.execute('INSERT INTO result_rows VALUES (?,0,0,?)',(rid,json.dumps({'PID':42,'CreateTime':'2020-01-01T00:00:00Z','Process':'same-fact.exe'})))
        yield client

def test_timeline_latest_successful_per_plugin_is_stable(client35):
    result=client35.get('/api/cases/A/timeline?scope=latest').json()
    assert result['total']==2
    assert {e['run_id'] for e in result['events']}=={'new-z','network'}
    assert all(e['run_created'] and e['run_id'] for e in result['events'])
    assert client35.get('/api/cases/A/timeline?scope=all').json()['total']==4

def test_timeline_exact_run_filter_preserves_full_history(client35):
    result=client35.get('/api/cases/A/timeline?run_id=old').json()
    assert result['total']==1 and result['events'][0]['run_id']=='old'
    assert client35.get('/api/cases/A/timeline?run_id=other').status_code==404
    assert client35.get('/api/cases/A/timeline?run_id=failed').status_code==404
    assert client35.get('/api/cases/A/timeline?scope=latest&run_id=old').status_code==422
    assert client35.get('/api/cases/A/timeline?scope=invalid').status_code==422

def test_timeline_latest_filter_search_does_not_reintroduce_old_run(client35):
    with db.connection() as c:c.execute('UPDATE result_rows SET data=? WHERE run_id=?',(json.dumps({'CreateTime':'2020-01-01T00:00:00Z','Process':'old-only-evidence'}),'old'))
    assert client35.get('/api/cases/A/timeline?scope=latest&q=old-only-evidence').json()['total']==0
    assert client35.get('/api/cases/A/timeline?scope=all&q=old-only-evidence').json()['total']==1

def test_timeline_paging_does_not_change_stored_source_rows(client35):
    with db.connection() as c:before=c.execute('SELECT run_id,idx,data FROM result_rows ORDER BY run_id,idx').fetchall()
    for suffix in ['?scope=latest&limit=1','?scope=latest&limit=1&offset=1','?run_id=old','?scope=all']:
        assert client35.get('/api/cases/A/timeline'+suffix).status_code==200
    with db.connection() as c:after=c.execute('SELECT run_id,idx,data FROM result_rows ORDER BY run_id,idx').fetchall()
    assert [tuple(r) for r in before]==[tuple(r) for r in after]
