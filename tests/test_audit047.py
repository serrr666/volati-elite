import pytest
from fastapi.testclient import TestClient
from volstudio import db,runner,catalog
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER

@pytest.fixture
def notebook_client(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'profile');monkeypatch.setattr(runner,'start',lambda:None);monkeypatch.setattr(runner,'shutdown',lambda:None);monkeypatch.setattr(catalog,'refresh',lambda *_:None)
    with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as c:
        for name in ['caseA','caseB']:
            db.execute("INSERT INTO cases(id,name,path,os,kind,size,created,hash_status,notes) VALUES(?,?,?,'windows','demo',0,?,'complete','original')",(name,name,'SYNTHETIC',db.now()))
        yield c

def test_autosaved_case_notes_are_canonical_and_remove_only_their_legacy_draft(notebook_client):
    c=notebook_client
    for name in ['caseA','caseB']:c.put('/api/cases/'+name+'/draft',json={'text':'legacy '+name})
    assert c.get('/api/cases/caseA/notebook').json()=={'text':'original','draft':'legacy caseA'}
    note='Hypothesis / гипотеза\nPID 123\n<&script> literal evidence'
    assert c.put('/api/cases/caseA/notebook',json={'text':note}).status_code==200
    assert c.get('/api/cases/caseA/notebook').json()=={'text':note,'draft':None}
    assert c.get('/api/cases/caseB/notebook').json()=={'text':'original','draft':'legacy caseB'}
    assert db.one("SELECT notes FROM cases WHERE id='caseA'")['notes']==note

def test_shared_notes_do_not_recover_a_stale_draft_after_save(notebook_client):
    c=notebook_client;c.put('/api/workspace/notebook/draft',json={'text':'old draft'})
    assert c.put('/api/workspace/notebook/commit',json={'text':'new notebook'}).status_code==200
    data=c.get('/api/workspace/notebook').json();assert data['text']=='new notebook' and data['draft'] is None
    assert c.get('/api/cases/caseA/notebook').json()['text']=='original'

def test_note_limits_missing_case_and_empty_text(notebook_client):
    c=notebook_client
    assert c.get('/api/cases/missing/notebook').status_code==404
    assert c.put('/api/cases/missing/notebook',json={'text':'x'}).status_code==404
    assert c.put('/api/cases/caseA/notebook',json={'text':'x'*100001}).status_code==422
    assert c.put('/api/cases/caseA/notebook',json={'text':''}).status_code==200
    assert c.get('/api/cases/caseA/notebook').json()['text']==''

def test_failed_atomic_save_keeps_canonical_text_and_draft(notebook_client):
    c=notebook_client;c.put('/api/cases/caseA/draft',json={'text':'keep draft'})
    db.execute("CREATE TRIGGER reject_note_delete BEFORE DELETE ON note_drafts BEGIN SELECT RAISE(ABORT,'simulated disk error'); END")
    with pytest.raises(Exception):c.put('/api/cases/caseA/notebook',json={'text':'must roll back'})
    assert c.get('/api/cases/caseA/notebook').json()=={'text':'original','draft':'keep draft'}
