import hashlib,json,os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from volstudio import db,runner,detection
from volstudio.app import app
from volstudio.security import API_TOKEN,TOKEN_HEADER
from volstudio.preflight import inspect_source

@pytest.fixture
def workspace38(tmp_path,monkeypatch):
    monkeypatch.setattr(db,'DATA',tmp_path/'data')
    monkeypatch.setattr(runner,'start',lambda:None)
    monkeypatch.setattr(runner,'shutdown',lambda:None)
    calls=[]
    def hashed(cid):
        calls.append(cid);p=Path(db.one('SELECT path FROM cases WHERE id=?',(cid,))['path'])
        db.execute("UPDATE cases SET hash_status='complete',sha256=? WHERE id=?",(hashlib.sha256(p.read_bytes()).hexdigest(),cid))
    # Synchronous fixture thread: preserve the real API flow while making hash counts deterministic.
    import volstudio.app as appmod
    class Immediate:
        def __init__(self,target,args=(),**_):self.target,self.args=target,args
        def start(self):self.target(*self.args)
    from types import SimpleNamespace
    monkeypatch.setattr(appmod,'threading',SimpleNamespace(Thread=Immediate))
    monkeypatch.setattr(runner,'hash_case',hashed)
    with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:yield client,tmp_path,calls

@pytest.mark.parametrize('filename',['evidence.ad1','renamed.raw'])
def test_ad1_signature_is_recognized_even_when_renamed(tmp_path,filename):
    p=tmp_path/filename;p.write_bytes(b'ADSEGMENTEDFILE\x00'+b'\0'*200)
    for lang in ['ru','en']:
        result=inspect_source(p,lang);assert result['kind']=='unsupported' and 'AD1' in result['format']
        assert 'FTK Imager' in result['message']
        assert any('\u0400'<=c<='\u04ff' for c in result['message'])==(lang=='ru')
    p.write_bytes(b'\0'*216);assert inspect_source(p)['kind']=='memory'

def attach(client,path,**extra):return client.post('/api/cases',json={'name':path.name,'path':str(path),'reuse_existing':True,**extra})

def test_ad1_does_not_queue_os_detection_and_blocks_os_plugins(workspace38):
    c,tmp,calls=workspace38;p=tmp/'capture.ad1';p.write_bytes(b'ADSEGMENTEDFILE\x00'+b'\0'*100)
    response=attach(c,p);assert response.status_code==201
    case=response.json();assert case['source_kind']=='unsupported' and case['detect_status']=='unsupported'
    assert c.get(f"/api/cases/{case['id']}/runs").json()==[]
    assert c.post(f"/api/cases/{case['id']}/runs",json={'plugin':'windows.pslist.PsList'}).status_code==409
    assert len(calls)==1

@pytest.mark.parametrize('phase,purpose',[('banners','detection-banners'),('windows','detection-windows')])
def test_cancelled_identification_stops_the_case_spinner(workspace38,phase,purpose):
    c,tmp,_=workspace38;p=tmp/'memory.raw';p.write_bytes(b'\0'*8192);cid=attach(c,p).json()['id']
    db.execute('UPDATE runs SET status=\'completed\' WHERE case_id=?',(cid,))
    db.execute("UPDATE cases SET detect_status=?,os='windows',detected_banner='ntkrnlmp.pdb|TEST|1' WHERE id=?",(phase,cid))
    db.execute("INSERT INTO runs(id,case_id,plugin,params,status,created,purpose) VALUES ('cancel38',?,'banners.Banners','{}','queued',?,?)",(cid,db.now(),purpose))
    assert c.post('/api/runs/cancel38/cancel').status_code==200
    case=next(r for r in c.get('/api/cases').json() if r['id']==cid)
    assert case['detect_status']=='cancelled' and case['os']=='windows' and case['detected_banner']
    assert not any(r['status']=='queued' for r in c.get(f'/api/cases/{cid}/runs').json())

def test_cancel_does_not_override_an_analysts_manual_os(workspace38):
    c,tmp,_=workspace38;p=tmp/'manual.raw';p.write_bytes(b'\0'*4096);cid=attach(c,p).json()['id']
    run=c.get(f'/api/cases/{cid}/runs').json()[0]
    assert c.patch(f'/api/cases/{cid}',json={'os':'linux'}).status_code==200
    c.post(f"/api/runs/{run['id']}/cancel")
    row=db.one('SELECT * FROM cases WHERE id=?',(cid,));assert row['os']=='linux' and row['detect_status']=='manual'

def test_reopening_unchanged_file_preserves_notes_and_does_not_rehash(workspace38):
    c,tmp,calls=workspace38;p=tmp/'memory.raw';p.write_bytes(b'\0'*4096)
    first=attach(c,p).json();cid=first['id'];c.patch(f'/api/cases/{cid}',json={'notes':'Evidence observation α'})
    before=c.get(f'/api/cases/{cid}/runs').json()
    second=attach(c,p,name='Ignored new label');assert second.status_code==200
    assert second.json()['id']==cid and second.json()['reused'] and second.json()['notes']=='Evidence observation α'
    assert len(calls)==1 and c.get(f'/api/cases/{cid}/runs').json()==before
    separate=attach(c,p,reuse_existing=False);assert separate.status_code==201 and separate.json()['id']!=cid and len(calls)==2

def test_changed_file_and_failed_verification_get_new_case(workspace38):
    c,tmp,calls=workspace38;p=tmp/'changing.raw';p.write_bytes(b'A'*4096)
    first=attach(c,p).json();stamp=p.stat().st_mtime_ns;p.write_bytes(b'B'*4096);os.utime(p,ns=(stamp+1000000000,stamp+1000000000))
    second=attach(c,p).json();assert first['id']!=second['id']
    db.execute("UPDATE cases SET hash_status='failed' WHERE id=?",(second['id'],))
    third=attach(c,p).json();assert third['id']!=second['id'] and len(calls)==3

def test_simultaneous_attachments_share_one_history(workspace38):
    c,tmp,calls=workspace38;p=tmp/'concurrent.raw';p.write_bytes(b'\0'*8192)
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:attach(c,p).json(),range(4)))
    assert len({r['id'] for r in results})==1 and len(calls)==1
    cid=results[0]['id'];assert len(c.get(f'/api/cases/{cid}/runs').json())==1

@pytest.mark.parametrize('suffix',['.json','.json.xz','.json.gz'])
def test_detection_displays_the_kernel_identity_actually_used_by_info(workspace38,suffix):
    c,tmp,_=workspace38;p=tmp/'info.raw';p.write_bytes(b'\0'*4096);cid=attach(c,p).json()['id']
    db.execute("UPDATE cases SET detect_status='windows',detected_banner='ntoskrnl.pdb|WRONG|1' WHERE id=?",(cid,))
    run=c.get(f'/api/cases/{cid}/runs').json()[0]
    db.update_run(run['id'],purpose='detection-windows',row_count=1)
    guid='1E158A6041094205BE17F93E54DD5E51'
    row={'Variable':'Symbols','Value':f'file:///C:/analysis%20data/windows/ntkrnlmp.pdb/{guid}-1'+suffix}
    db.execute('INSERT INTO result_rows(run_id,idx,depth,data) VALUES (?,0,0,?)',(run['id'],json.dumps(row)))
    detection.after_run({**run,'purpose':'detection-windows'},True)
    case=db.one('SELECT * FROM cases WHERE id=?',(cid,))
    assert case['detected_banner']==f'ntkrnlmp.pdb|{guid}|1' and case['detect_status']=='complete'

def test_late_detection_callback_cannot_restart_cancelled_identification(workspace38):
    c,tmp,_=workspace38;p=tmp/'cancelled.raw';p.write_bytes(b'\0'*4096);cid=attach(c,p).json()['id']
    run=c.get(f'/api/cases/{cid}/runs').json()[0];c.post(f"/api/runs/{run['id']}/cancel")
    detection.after_run(run,False)
    assert db.one('SELECT detect_status FROM cases WHERE id=?',(cid,))['detect_status']=='cancelled'
    assert len(c.get(f'/api/cases/{cid}/runs').json())==1

@pytest.mark.parametrize('chunk_size',[1,2,3,7,63,4096,65536])
@pytest.mark.parametrize('minimum',[4,16,256])
def test_ascii_stream_matches_whole_file_oracle_with_noise_and_fragment_boundaries(monkeypatch,chunk_size,minimum):
    import random,re
    from volstudio import pipeline
    rng=random.Random(38);data=rng.randbytes(7000)+b'\0'+b'A'*257+b'\0'+b'B'*(200000 if chunk_size>=63 else 1000)+b'\0tail-at-eof'
    expected=[]
    for match in re.finditer(rb'[\x20-\x7e]{'+str(minimum).encode()+rb',}',data):
        raw=match.group()
        for offset in range(0,len(raw),pipeline.STRING_FRAGMENT):
            expected.append((match.start()+offset,raw[offset:offset+pipeline.STRING_FRAGMENT].decode('ascii'),len(raw)>=pipeline.STRING_FRAGMENT))
    stream=pipeline.StringStream('ascii',minimum);actual=[]
    for start in range(0,len(data),chunk_size):
        actual.extend(stream.feed(data[start:start+chunk_size],start))
        assert len(stream.pending)<=pipeline.STRING_FRAGMENT+minimum
    actual.extend(stream.feed(b'',len(data),True))
    assert [(int(r['Offset'],16),r['Text'],r['Fragment']) for r in actual]==expected

@pytest.mark.parametrize('encoding',['ascii','utf16le','both'])
@pytest.mark.parametrize('ignore_case',[True,False])
def test_pushdown_preserves_filtered_rows_offsets_and_scanned_count(tmp_path,monkeypatch,encoding,ignore_case):
    from volstudio import pipeline
    import random
    monkeypatch.setattr(pipeline,'CHUNK_SIZE',127)
    rng=random.Random(39)
    raw=rng.randbytes(10000)+b'\0Windows alpha\0WINDOWS beta\0'+('Кириллица Windows evidence').encode('utf-16le')+b'\0'*7+b'prefix '+b'A'*70000+b' Windows suffix\0'
    p=tmp_path/'realistic.raw';p.write_bytes(raw)
    config=pipeline.PipelineInput(source='image',encoding=encoding,steps=[{'op':'contains','field':'Text','value':'Windows','ignore_case':ignore_case}])
    baseline=list(pipeline.image_rows(p,config,lambda *_:None))
    stats={};fast=list(pipeline.image_rows(p,config,lambda *_:None,stats))
    matches=lambda rows:[r for r in rows if ('windows' in r['Text'].casefold() if ignore_case else 'Windows' in r['Text'])]
    assert matches(fast)==matches(baseline)
    assert stats['scanned_records']==len(baseline)

@pytest.mark.parametrize('chunk_size',[1,3,17,4096])
def test_utf16_short_run_acceleration_preserves_legacy_greedy_alignment(tmp_path,chunk_size):
    import random,re
    from volstudio import pipeline
    rng=random.Random(40)
    data=rng.randbytes(16000)+('Кириллица windows ASCII mixed '*80).encode('utf-16le')+b'\0'*5
    # Whole-buffer reference uses the original greedy one-unit pattern, including
    # short runs that determine which byte alignment wins overlapping matches.
    expected=[]
    for match in re.finditer(rb'(?:[\x20-\x7e]\x00|[\x00-\xff]\x04)+',data):
        if len(match.group())>=8:expected.append((match.start(),match.group().decode('utf-16le')))
    stream=pipeline.StringStream('utf16le',4);rows=[]
    for start in range(0,len(data),chunk_size):rows.extend(stream.feed(data[start:start+chunk_size],start))
    rows.extend(stream.feed(b'',len(data),True))
    assert [(int(row['Offset'],16),row['Text']) for row in rows]==expected
