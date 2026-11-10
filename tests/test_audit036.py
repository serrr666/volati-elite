import json
import pytest
from fastapi.testclient import TestClient
from volstudio import db,runner
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER

@pytest.fixture(scope='module')
def workspace36(tmp_path_factory):
    prior=db.DATA;db.DATA=tmp_path_factory.mktemp('workspace36')
    original_start,original_shutdown=runner.start,runner.shutdown
    runner.start=lambda:None;runner.shutdown=lambda:None
    try:
        with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:
            with db.connection() as c:
                for cid in ['a36','b36']:
                    c.execute("INSERT INTO cases(id,name,path,os,kind,size,created,hash_status) VALUES (?,?,?,'windows','demo',0,?,'demo')",(cid,cid,'SYNTHETIC',db.now()))
                c.execute("INSERT INTO runs(id,case_id,plugin,params,status,created) VALUES ('run36','a36','qa.Example','{}','queued',?)",(db.now(),))
            yield client
    finally:
        db.DATA=prior;runner.start,runner.shutdown=original_start,original_shutdown

def test_empty_workspace_and_legacy_preferences_migration(workspace36):
    assert workspace36.get('/api/preferences').json()['open_cases']==[]
    db.save_settings({'last_case':'a36'})
    assert workspace36.get('/api/preferences').json()['open_cases']==['a36']

def test_closing_last_case_persists_empty_without_deleting_history(workspace36):
    c=workspace36
    assert c.put('/api/preferences',json={'last_case':'a36','open_cases':['a36','b36']}).status_code==200
    assert c.put('/api/preferences',json={'last_case':'','open_cases':[]}).status_code==200
    p=c.get('/api/preferences').json();assert p['last_case']=='' and p['open_cases']==[]
    assert len(c.get('/api/cases').json())==2 and c.get('/api/cases/a36/runs').json()[0]['status']=='queued'
    assert c.put('/api/preferences',json={'theme':'light'}).json()['open_cases']==[]
    c.put('/api/preferences',json={'hide_tip':True})
    assert c.put('/api/preferences',json={'theme':'dark'}).json()['hide_tip'] is True

def test_workspace_selection_validation_is_atomic(workspace36):
    c=workspace36;before=c.get('/api/preferences').json()
    for values in [{'last_case':'a36','open_cases':[]},{'last_case':'missing','open_cases':['missing']},{'last_case':'','open_cases':['a36','a36']}]:
        assert c.put('/api/preferences',json=values).status_code==422
        assert c.get('/api/preferences').json()==before

def test_global_notebook_and_draft_are_independent_of_case_notes(workspace36):
    c=workspace36
    assert c.get('/api/workspace/notebook').json()['text']==''
    assert c.put('/api/workspace/notebook',json={'text':'Общий план: <script>alert(1)</script>'}).status_code==200
    assert c.put('/api/workspace/notebook/draft',json={'text':'unsaved α'}).status_code==200
    note=c.get('/api/workspace/notebook').json();assert note['text'].startswith('Общий план') and note['draft']=='unsaved α'
    assert all(x['notes']=='' for x in c.get('/api/cases').json())
    assert c.put('/api/workspace/notebook',json={'text':'saved β'}).status_code==200
    assert c.get('/api/workspace/notebook').json()['draft']=='unsaved α'
    assert c.put('/api/workspace/notebook/draft',json={'text':None}).status_code==200
    assert c.get('/api/workspace/notebook').json()['draft'] is None

def test_workspace_notes_size_validation_preserves_previous(workspace36):
    c=workspace36;before=c.get('/api/workspace/notebook').json()
    assert c.put('/api/workspace/notebook',json={'text':'x'*100001}).status_code==422
    assert c.put('/api/workspace/notebook/draft',json={'text':'x'*100001}).status_code==422
    assert c.get('/api/workspace/notebook').json()==before

def test_workspace_activity_keeps_closed_case_running_job_visible(workspace36):
    data=workspace36.get('/api/workspace/activity').json()
    assert data['total_runs']==1 and data['active'][0]['id']=='run36' and data['runs'][0]['case_name']=='a36'


def test_image_pipeline_cannot_claim_a_stale_parent_run(workspace36):
    c=workspace36
    db.execute("UPDATE cases SET kind='evidence',hash_status='complete' WHERE id='a36'")
    try:
        response=c.post('/api/cases/a36/pipeline',json={'source':'image','source_run':'run36','max_rows':10})
        assert response.status_code==201
        job=next(r for r in c.get('/api/cases/a36/runs').json() if r['plugin']=='studio.Pipeline')
        assert job['params']['source']=='image' and job['params']['source_run']==''
    finally:
        db.execute("UPDATE cases SET kind='demo',hash_status='demo' WHERE id='a36'")
