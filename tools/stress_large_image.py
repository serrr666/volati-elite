"""Exercise real Banners against >10 GiB; the fixture is NOT a full memory capture."""
import ctypes
import json
import os
import statistics
import sys
import time
from pathlib import Path

import psutil
from fastapi.testclient import TestClient
from volstudio import db
from volstudio.security import API_TOKEN,TOKEN_HEADER
from volstudio.app import app

root=Path(sys.argv[1]).resolve()
root.mkdir(parents=True,exist_ok=True)
db.DATA=root/"state"
image=root/"large-linux-banner.raw"
size=11*1024**3
sparse=False
with image.open('w+b') as f:
    if os.name=='nt':
        import msvcrt
        returned=ctypes.c_ulong()
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.DeviceIoControl.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong),ctypes.c_void_p]
        sparse=bool(kernel.DeviceIoControl(msvcrt.get_osfhandle(f.fileno()),0x900c4,None,0,None,0,ctypes.byref(returned),None))
    f.truncate(size)
    f.seek(8192)
    f.write(b'Linux version 6.1.0-studio (builder@lab) (gcc 12.2.0) #1 SMP Tue Oct 28 09:00:00 UTC 2026\x00')
print(json.dumps({'stage':'fixture_created','size':size,'sparse':sparse}),flush=True)
latencies=[]
start=time.monotonic()
max_parent=0
with TestClient(app,headers={TOKEN_HEADER:API_TOKEN}) as client:
    db.save_settings({'offline':True,'memory_limit_mb':2048})
    r=client.post('/api/cases',json={'path':str(image),'name':'11 GiB scale test','os':'unknown'})
    assert r.status_code==201,r.text
    case_id=r.json()['id']
    until=time.monotonic()+600
    while time.monotonic()<until:
        t=time.monotonic();h=client.get('/api/health');latencies.append((time.monotonic()-t)*1000)
        assert h.status_code==200
        max_parent=max(max_parent,psutil.Process().memory_info().rss)
        jobs=client.get(f'/api/cases/{case_id}/runs').json()
        if jobs and all(j['status'] in ('completed','failed') for j in jobs):
            break
        time.sleep(.2)
    assert len(jobs)==1 and jobs[0]['status']=='completed',jobs
    case=next(c for c in client.get('/api/cases').json() if c['id']==case_id)
    assert case['os']=='linux' and case['size']==size and jobs[0]['row_count']==1
    # Start a second scan, then cancel a real worker and ensure responsiveness.
    new=client.post(f'/api/cases/{case_id}/runs',json={'plugin':'banners.Banners','params':{}}).json()
    for _ in range(100):
        job=db.one('SELECT * FROM runs WHERE id=?',(new['id'],))
        if job['status']=='running':break
        time.sleep(.05)
    t=time.monotonic()
    assert client.post(f"/api/runs/{new['id']}/cancel").status_code==200
    cancel_ms=(time.monotonic()-t)*1000
    time.sleep(.4)
    assert client.get('/api/health').status_code==200
    result={'fixture':'sparse synthetic kernel-banner file; not a full RAM capture','logical_bytes':size,'sparse':sparse,
            'elapsed_seconds':round(time.monotonic()-start,2),'api_requests':len(latencies),
            'api_p95_ms':round(sorted(latencies)[int((len(latencies)-1)*.95)],2),'api_max_ms':round(max(latencies),2),
            'application_peak_rss_bytes':max_parent,'worker_observed_peak_rss_bytes':jobs[0]['memory_peak_bytes'],
            'cancel_ms':round(cancel_ms,2),'detected_os':case['os'],'rows':jobs[0]['row_count'],'engine':jobs[0]['engine_version'],
            'passed':True}
    (root/'stress-results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result,indent=2),flush=True)
