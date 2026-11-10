import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from volstudio import db,runner,pipeline
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER

@pytest.fixture
def client34(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'state')
    with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as c:
        db.save_settings({'offline':True})
        yield c

@pytest.mark.parametrize('lang',['en','ru'])
@pytest.mark.parametrize('detail',['Unsatisfied requirement symbols','YARA import error','FileNotFoundError','Unexpected failure'])
def test_diagnostic_language(client34,lang,detail):
    db.save_settings({'language':lang})
    explanation=runner.friendly_error(detail).split('\n\n')[0]
    assert any('а'<=c.lower()<='я' for c in explanation)==(lang=='ru')

@pytest.mark.parametrize('chunk_size',[1,2,3,7,17,256,4096])
def test_unicode_strings_with_exact_byte_offsets(tmp_path,monkeypatch,chunk_size):
    monkeypatch.setattr(pipeline,'CHUNK_SIZE',chunk_size)
    examples=['ASCII powerShell example','Кириллица forensic','café mémoire','Ελληνικά secret','中文证据','emoji 🔎 evidence','a\u0301bcé evidence']
    data=bytearray(b'\0'*8192);expected=[]
    for i,s in enumerate(examples):
        offset=512*(i+1)+(i%2);raw=s.encode('utf-16le');data[offset:offset+len(raw)]=raw;expected.append((hex(offset),s))
    p=tmp_path/'unicode.raw';p.write_bytes(data)
    config=pipeline.PipelineInput(source='image',encoding='utf16le',unicode=True)
    rows=list(pipeline.image_rows(p,config,lambda *_:None))
    found={(r['Offset'],r['Text']) for r in rows}
    assert set(expected)<=found
    assert p.read_bytes()==data

def test_unicode_fragments_do_not_split_surrogates(tmp_path,monkeypatch):
    monkeypatch.setattr(pipeline,'CHUNK_SIZE',7);monkeypatch.setattr(pipeline,'STRING_FRAGMENT',8)
    text='🔎é证据'*9+'Ωx';raw=text.encode('utf-16le');p=tmp_path/'long.raw';p.write_bytes(b'\0'*8+raw+b'\0'*4)
    rows=[r for r in pipeline.image_rows(p,pipeline.PipelineInput(source='image',encoding='utf16le',unicode=True),lambda *_:None) if int(r['Offset'],16)%2==0]
    assert ''.join(r['Text'] for r in rows)==text
    position=8
    for r in rows:
        assert int(r['Offset'],16)==position and len(r['Text'])<=8
        position+=len(r['Text'].encode('utf-16le'))
    assert position==8+len(raw) and all(r['Fragment'] for r in rows)

def seed_timeline(case_id='large',count=10007):
    with db.connection() as c:
        for case,rid in [(case_id,'large-run'),('unrelated','other-run')]:
            c.execute("INSERT INTO cases(id,name,path,os,kind,size,created,hash_status) VALUES (?,?,?,'windows','demo',0,?,'demo')",(case,case,'SYNTHETIC',db.now()))
            c.execute("INSERT INTO runs(id,case_id,plugin,params,status,created,row_count) VALUES (?,?,?,'{}','completed',?,?)",(rid,case,'qa.Timeline',db.now(),count if case==case_id else 1))
        for i in range(count):
            # Reverse chronology and a non-UTC timezone; first scanned rows are not earliest.
            from datetime import datetime,timedelta,timezone
            time=(datetime(2026,11,1,tzinfo=timezone(timedelta(hours=3)))+timedelta(seconds=count-i)).isoformat()
            data={'PID':i,'CreateTime':time,'ImageFileName':'needle-final' if i==count-1 else 'process.exe','Naive':'2026-11-01T12:00:00'}
            c.execute('INSERT INTO result_rows VALUES (?,?,0,?)',('large-run',i,json.dumps(data)))
        c.execute('INSERT INTO result_rows VALUES (?,0,0,?)',('other-run',json.dumps({'PID':999999,'CreateTime':'2025-01-01T00:00:00Z'})))

def test_timeline_full_pagination_global_order_and_literal_search(client34):
    seed_timeline()
    first=client34.get('/api/cases/large/timeline?limit=100').json()
    assert first['total']==10007 and len(first['events'])==100 and first['limited'] is False
    assert first['events'][0]['row_idx']==10006 and first['events'][0]['time']=='2026-10-31T21:00:01.000000+00:00'
    seen=[]
    for offset in range(0,10007,500):
        page=client34.get(f'/api/cases/large/timeline?offset={offset}&limit=500').json()
        assert page['total']==10007
        seen.extend(e['row_idx'] for e in page['events'])
    assert seen==list(reversed(range(10007)))
    filtered=client34.get('/api/cases/large/timeline',params={'q':'needle-final'}).json()
    assert filtered['total']==1 and filtered['events'][0]['row_idx']==10006
    assert client34.get('/api/cases/large/timeline',params={'q':'.*'}).json()['total']==0
    exact=filtered['events'][0]
    assert client34.get(f"/api/runs/{exact['run_id']}/rows/{exact['row_idx']}").json()['data']==exact['data']
    assert client34.get('/api/cases/large/timeline?limit=501').status_code==422
    assert client34.get('/api/cases/large/timeline?offset=-1').status_code==422

def test_timeline_multiple_fields_invalid_dates_and_cached_legacy_backfill(client34,monkeypatch):
    seed_timeline(count=1)
    with db.connection() as c:
        data={'CreateTime':'2026-01-01T12:00:00+02:00','ExitTime':'2026-01-01T10:00:00Z','LoadTime':'2026-01-01T10:00:00','Modified':'bad date'}
        c.execute('UPDATE result_rows SET data=? WHERE run_id=?',(json.dumps(data),'large-run'))
    first=client34.get('/api/cases/large/timeline').json()
    assert first['total']==2
    assert [e['field'] for e in first['events']]==['CreateTime','ExitTime']
    assert all(e['original']==data[e['field']] for e in first['events'])
    from volstudio import timeline
    def unexpected(*_):raise AssertionError('An unchanged legacy run must not be reindexed')
    monkeypatch.setattr(timeline,'index_row',unexpected)
    second=client34.get('/api/cases/large/timeline').json()
    assert first==second

def test_ingest_builds_timeline_before_completion(client34,tmp_path):
    seed_timeline(count=0)
    path=tmp_path/'result.jsonl'
    path.write_text(json.dumps({'CreateTime':'2026-11-02T12:00:00Z','PID':0})+'\n',encoding='utf8')
    count,columns=runner.ingest('large-run',path)
    db.update_run('large-run',row_count=count)
    with db.connection() as c:
        assert c.execute('SELECT row_count FROM timeline_index WHERE run_id=?',('large-run',)).fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM timeline_events WHERE run_id=?',('large-run',)).fetchone()[0]==1
    event=client34.get('/api/cases/large/timeline').json()['events'][0]
    assert event['data']['PID']==0 and event['row_idx']==0

def test_unicode_invalid_units_boundaries_and_bounded_pending(monkeypatch):
    monkeypatch.setattr(pipeline,'STRING_FRAGMENT',16)
    text='é🔎证据'*45
    raw=text.encode('utf-16le')+b'\x00\xd8\x00\x00'+('Ω'*4).encode('utf-16le')
    for chunk_size in [1,3,7,16,255]:
        stream=pipeline.UnicodeStringStream(4,0);rows=[]
        for start in range(0,len(raw),chunk_size):
            rows.extend(stream.feed(raw[start:start+chunk_size],start))
            assert len(stream.pending)<=16*4+4
        rows.extend(stream.feed(b'',len(raw),True))
        assert ''.join(r['Text'] for r in rows)==text+'Ω'*4
        assert all(not any(0xd800<=ord(c)<=0xdfff for c in r['Text']) for r in rows)
