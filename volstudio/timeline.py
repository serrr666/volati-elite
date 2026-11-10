"""Derived timeline index. Source rows remain authoritative and unmodified."""
from __future__ import annotations
import json
from datetime import datetime,timezone
from . import db

FIELDS={'createtime','exittime','created','loadtime','lastwritetime','modified','timestamp','time','lastwrite'}

def index_row(c,run_id,index,data):
    events=[]
    for field,value in data.items():
        if field.lower().replace(' ','') not in FIELDS or not isinstance(value,str):continue
        try:
            dt=datetime.fromisoformat(value.replace('Z','+00:00').replace(' UTC','+00:00'))
            if dt.utcoffset() is None:continue
            timestamp=dt.astimezone(timezone.utc).isoformat(timespec='microseconds')
        except (ValueError,OverflowError):continue
        events.append((run_id,index,field,timestamp,value))
    c.executemany('INSERT OR REPLACE INTO timeline_events(run_id,row_idx,field,time,original) VALUES (?,?,?,?,?)',events)

def mark_indexed(c,run_id,count):
    c.execute('INSERT OR REPLACE INTO timeline_index(run_id,row_count) VALUES (?,?)',(run_id,count))

def ensure_index(case_id):
    # Legacy databases are indexed lazily, once per completed immutable run.
    # The lock serializes two concurrent backfills; the worker already uses this
    # index during normal ingestion, before publishing a completed run.
    with db.LOCK,db.connection() as c:
        missing=c.execute("""SELECT r.id,r.row_count FROM runs r LEFT JOIN timeline_index t ON t.run_id=r.id
            WHERE r.case_id=? AND r.status='completed' AND (t.run_id IS NULL OR t.row_count!=r.row_count)""",(case_id,)).fetchall()
        for run in missing:
            c.execute('DELETE FROM timeline_events WHERE run_id=?',(run['id'],))
            for row in c.execute('SELECT idx,data FROM result_rows WHERE run_id=? ORDER BY idx',(run['id'],)):
                index_row(c,run['id'],row['idx'],json.loads(row['data']))
            mark_indexed(c,run['id'],run['row_count'])

def page(case_id,offset=0,limit=100,q='',scope='all',run_id=''):
    ensure_index(case_id)
    where="r.case_id=? AND r.status='completed'"
    args=[case_id]
    if run_id:
        where+=' AND r.id=?';args.append(run_id)
    elif scope=='latest':
        # Only successful runs participate. Equal creation times have a stable
        # ID tie-break; a later failure must not hide usable earlier evidence.
        where+=""" AND NOT EXISTS (SELECT 1 FROM runs newer WHERE newer.case_id=r.case_id
            AND newer.plugin=r.plugin AND newer.status='completed'
            AND (newer.created>r.created OR (newer.created=r.created AND newer.id>r.id)))"""
    if q:
        where+=' AND (studio_contains(d.data,?) OR instr(studio_casefold(e.field),?) OR instr(studio_casefold(r.plugin),?) OR instr(studio_casefold(e.time),?) OR instr(studio_casefold(e.original),?))'
        args.extend([q,*([q.casefold()]*4)])
    joins='FROM timeline_events e JOIN runs r ON r.id=e.run_id JOIN result_rows d ON d.run_id=e.run_id AND d.idx=e.row_idx WHERE '+where
    with db.connection() as c:
        c.execute('BEGIN')  # count and page share one SQLite read snapshot.
        total=c.execute('SELECT COUNT(*) '+joins,args).fetchone()[0]
        records=c.execute('SELECT e.*,r.plugin,r.created AS run_created,d.data '+joins+' ORDER BY e.time,e.run_id,e.row_idx,e.field LIMIT ? OFFSET ?',(*args,limit,offset)).fetchall()
        examined=c.execute("SELECT COALESCE(SUM(row_count),0) FROM runs WHERE case_id=? AND status='completed'",(case_id,)).fetchone()[0]
    return {'events':[{**dict(r),'data':json.loads(r['data'])} for r in records],
            'total':total,'offset':offset,'limit':limit,'examined_rows':examined,'limited':False}
