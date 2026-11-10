"""Test the packaged engine independently from the developer Python environment."""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

exe=Path(sys.argv[1]).resolve()
root=Path(sys.argv[2]).resolve()
root.mkdir(parents=True,exist_ok=True)
cache=root/'cache';cache.mkdir(exist_ok=True)
out=root/'output';out.mkdir(exist_ok=True)
image=root/'frozen память.raw'
data=bytearray(1024*1024)
banner=b'Linux version 6.1.0-studio (builder@lab) (gcc 12.2.0) #1 SMP Tue Oct 28 09:00:00 UTC 2026\x00'
data[8192:8192+len(banner)]=banner
image.write_bytes(data)
before=hashlib.sha256(data).hexdigest()
job={'stdout':str(root/'result.jsonl'),'stderr':str(root/'engine.log'),'args':['-q','--parallelism','off','-r','studio-jsonl','--cache-path',str(cache),'--offline','-o',str(out),'-f',str(image),'banners.Banners']}
jobpath=root/'job.json';jobpath.write_text(json.dumps(job),encoding='utf8')
start=time.monotonic()
p=subprocess.run([str(exe),'--engine-worker',str(jobpath)],timeout=120,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
assert p.returncode==0,(p.returncode,Path(job['stderr']).read_text(encoding='utf8'))
rows=[json.loads(line) for line in Path(job['stdout']).read_text(encoding='utf8').splitlines() if line.strip()]
assert len(rows)==1 and 'Linux version 6.1.0-studio' in rows[0]['Banner'],rows
assert hashlib.sha256(image.read_bytes()).hexdigest()==before
result={'passed':True,'mode':'actual standalone EXE engine worker','fixture':'1 MiB synthetic banner, not a full memory capture','rows':len(rows),'seconds':round(time.monotonic()-start,2),'unicode_path':True,'source_unchanged':True}
(root/'frozen-smoke.json').write_text(json.dumps(result,indent=2),encoding='utf8')
print(json.dumps(result,indent=2))
