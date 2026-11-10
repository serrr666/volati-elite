import json
import pytest
from fastapi.testclient import TestClient
from volstudio import db,runner,catalog
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER

@pytest.fixture
def client46(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'profile')
    monkeypatch.setattr(runner,'start',lambda:None);monkeypatch.setattr(runner,'shutdown',lambda:None)
    monkeypatch.setattr(catalog,'refresh',lambda *_:None)
    monkeypatch.setattr(catalog,'CATALOG',{'version':'test','plugins':[{'id':'windows.pslist.PsList','os':'windows','args':[]},{'id':'windows.required.Required','os':'windows','args':[{'name':'pid','optional':False,'default':None,'type':'integer'}]}]})
    with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:
        db.execute("INSERT INTO cases(id,name,path,os,kind,size,created,hash_status) VALUES('c46','QA','SYNTHETIC','windows','demo',0,?,'complete')",(db.now(),))
        columns=['PID','Port','Process','odd"key']
        db.execute("INSERT INTO runs(id,case_id,plugin,params,status,created,row_count,columns_json) VALUES('r46','c46','windows.pslist.PsList','{}','completed',?,6,?)",(db.now(),json.dumps(columns)))
        rows=[{'PID':i,'Process':'p'+str(i),'odd"key':'a_%\"','Port':v} for i,v in enumerate([443,'443',None,False,80])]
        rows.append({'PID':5,'Process':'missing'})
        with db.connection() as c:c.executemany("INSERT INTO result_rows VALUES('r46',?,0,?)",[(i,json.dumps(row)) for i,row in enumerate(rows)])
        yield client

def rule(column,values,exclude=False):return json.dumps({column:{'exclude':exclude,'values':values}})

def test_facet_types_missing_and_typed_selection(client46):
    c=client46;values=c.get('/api/runs/r46/values',params={'column':'Port'}).json()['values']
    assert {v['token'] for v in values}=={'integer:443','text:443','null:','false:0','integer:80','missing:'}
    for token,index in [('integer:443',0),('text:443',1),('null:',2),('false:0',3),('missing:',5)]:
        response=c.get('/api/runs/r46/rows',params={'filters':rule('Port',[token])}).json()
        assert response['total']==1 and response['rows'][0]['index']==index

def test_exclude_empty_and_other_column_filters(client46):
    c=client46
    assert c.get('/api/runs/r46/rows',params={'filters':rule('Port',[])}).json()['total']==0
    assert c.get('/api/runs/r46/rows',params={'filters':rule('Port',[],True)}).json()['total']==6
    assert c.get('/api/runs/r46/rows',params={'filters':rule('Port',['integer:443'],True)}).json()['total']==5
    filters={'Port':{'exclude':False,'values':['integer:443']},'Process':{'exclude':False,'values':['text:p0']}}
    result=c.get('/api/runs/r46/values',params={'column':'Port','filters':json.dumps(filters)}).json()
    assert result['values'][0]['token']=='integer:443' and len(result['values'])==1

def test_literal_column_names_and_search(client46):
    c=client46;values=c.get('/api/runs/r46/values',params={'column':'odd"key','search':'_%'}).json()['values']
    token=next(v['token'] for v in values if v['type']=='text')
    assert c.get('/api/runs/r46/rows',params={'filters':rule('odd"key',[token]),'q':'_%'}).json()['total']==5
    assert c.get('/api/runs/r46/values',params={'column':'Port); DROP TABLE runs;--'}).status_code==422
    assert c.get('/api/runs/r46/rows',params={'filters':json.dumps({'not a column':{'exclude':False,'values':[]}})}).status_code==422

def test_full_filtered_export_and_unchanged_source(client46):
    c=client46;payload={'filters':rule('Port',['integer:443','text:443']),'q':'p','format':'json'}
    output=c.get('/api/runs/r46/export',params=payload).json()
    assert [r['PID'] for r in output]==[0,1]
    assert c.get('/api/runs/r46/rows').json()['total']==6
    csv=c.get('/api/runs/r46/export',params={**payload,'format':'csv'}).text
    assert len(csv.strip().splitlines())==3

def test_batch_validation_is_atomic_and_order_is_preserved(client46):
    c=client46;url='/api/cases/c46/runs/batch';valid={'plugin':'windows.pslist.PsList','params':{}}
    before=db.one('SELECT COUNT(*) n FROM runs')['n']
    assert c.post(url,json={'runs':[valid,{'plugin':'windows.required.Required','params':{}}]}).status_code==422
    assert db.one('SELECT COUNT(*) n FROM runs')['n']==before
    result=c.post(url,json={'runs':[valid,{'plugin':'windows.required.Required','params':{'pid':42}}]})
    assert result.status_code==201
    assert [r['plugin'] for r in result.json()]==['windows.pslist.PsList','windows.required.Required']
    assert all(r['status']=='queued' for r in result.json())
    assert c.post(url,json={'runs':[]}).status_code==422
    assert c.post(url,json={'runs':[valid]*51}).status_code==422

def test_pulse_is_stable_when_idle_and_changes_with_bookmarks(client46):
    c=client46;before=c.get('/api/workspace/pulse').json()
    assert c.get('/api/workspace/pulse').json()==before
    assert c.post('/api/cases/c46/bookmarks',json={'run_id':'r46','row_idx':0}).status_code==201
    assert c.get('/api/workspace/pulse').json()['revision']>before['revision']


def test_distinct_large_integers_keep_exact_tokens(client46):
    c=client46
    with db.connection() as connection:
        for index,number in enumerate([2**64,2**64+1,2**53+1],6):
            connection.execute("INSERT INTO result_rows VALUES('r46',?,0,?)",(index,json.dumps({'Port':number})))
        connection.execute("UPDATE runs SET row_count=9 WHERE id='r46'")
    values=c.get('/api/runs/r46/values',params={'column':'Port'}).json()['values']
    for number in [2**64,2**64+1,2**53+1]:
        token='integer:'+str(number)
        assert any(v['token']==token and v['value']==str(number) for v in values)
        assert c.get('/api/runs/r46/rows',params={'filters':rule('Port',[token])}).json()['total']==1
