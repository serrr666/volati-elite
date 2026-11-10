import pytest
from fastapi.testclient import TestClient
from volstudio import db,runner,catalog
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER

@pytest.fixture
def client43(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'profile')
    monkeypatch.setattr(runner,'start',lambda:None)
    monkeypatch.setattr(runner,'shutdown',lambda:None)
    monkeypatch.setattr(catalog,'refresh',lambda *_:None)
    with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:
        db.execute("INSERT INTO cases(id,name,path,os,kind,size,created,hash_status) VALUES('qa43','Synthetic QA','SYNTHETIC','windows','demo',0,?,'complete')",(db.now(),))
        db.execute("INSERT INTO runs(id,case_id,plugin,params,status,created,row_count) VALUES('run43','qa43','windows.pslist.PsList','{}','completed',?,1)",(db.now(),))
        db.execute("INSERT INTO result_rows VALUES('run43',0,0,'{\"PID\":43}')")
        yield client,'qa43','run43'

def test_quick_bookmark_does_not_erase_an_existing_annotation(client43):
    client,case_id,run_id=client43
    path=f'/api/cases/{case_id}/bookmarks'
    payload={'run_id':run_id,'row_idx':0}
    note='Confirmed finding / проверено / 命令 — keep exact text'
    assert client.post(path,json={**payload,'note':note}).status_code==201
    before=client.get(path).json()[0]
    assert client.post(path,json=payload).status_code==201
    after=client.get(path).json()[0]
    assert after==before

def test_explicit_empty_note_can_still_clear_the_annotation(client43):
    client,case_id,run_id=client43
    path=f'/api/cases/{case_id}/bookmarks';payload={'run_id':run_id,'row_idx':0}
    client.post(path,json={**payload,'note':'old finding'})
    assert client.post(path,json={**payload,'note':''}).status_code==201
    assert client.get(path).json()[0]['note']==''

def test_first_quick_bookmark_defaults_to_empty_note(client43):
    client,case_id,run_id=client43
    path=f'/api/cases/{case_id}/bookmarks'
    assert client.post(path,json={'run_id':run_id,'row_idx':0}).status_code==201
    result=client.get(path).json()
    assert len(result)==1 and result[0]['note']=='' and result[0]['run_id']==run_id
