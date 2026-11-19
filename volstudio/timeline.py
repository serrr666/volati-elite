"""Derived timeline index. Source rows remain authoritative and unmodified."""
from __future__ import annotations
import json
from threading import Lock
from datetime import datetime,timezone
from . import db

INDEX_VERSION = 2
INDEX_BATCH_SIZE = 2000
MIGRATION_LOCK = Lock()
MFT_FIELDS = {'updated', 'accessed'}
FIELDS = {'createtime', 'exittime', 'created', 'loadtime', 'lastwritetime',
          'modified', 'timestamp', 'time', 'lastwrite'} | MFT_FIELDS


def field_key(field):
    return field.lower().replace(' ', '')


def utc_time(value):
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00').replace(' UTC', '+00:00'))
        if date.utcoffset() is not None:
            return date.astimezone(timezone.utc).isoformat(timespec='microseconds')
    except (ValueError, OverflowError):
        pass
    return None


def index_row(c,run_id,index,data):
    events=[]
    for field,value in data.items():
        if field_key(field) not in FIELDS or not isinstance(value,str):continue
        timestamp = utc_time(value)
        if timestamp is not None:
            events.append((run_id,index,field,timestamp,value))
    c.executemany('INSERT OR REPLACE INTO timeline_events(run_id,row_idx,field,time,original) VALUES (?,?,?,?,?)',events)

def mark_indexed(c,run_id,count):
    c.execute('INSERT OR REPLACE INTO timeline_index(run_id,row_count,version) VALUES (?,?,?)',
              (run_id,count,INDEX_VERSION))


def add_mft_dates(c, run_id, columns, after, through):
    placeholders = ','.join('?' for _ in columns)
    c.execute(f"""WITH dates AS MATERIALIZED (
        SELECT r.idx,j.key,j.value,studio_utc_time(j.value) AS utc FROM result_rows r
        JOIN json_each(r.data) j
        WHERE r.run_id=? AND r.idx>? AND r.idx<=? AND j.type='text' AND j.key IN ({placeholders})
        )
        INSERT OR REPLACE INTO timeline_events(run_id,row_idx,field,time,original)
        SELECT ?,idx,key,utc,value FROM dates WHERE utc IS NOT NULL""",
        (run_id,after,through,*columns,run_id))


def missing_indexes(c, case_id, run_id):
    return c.execute("""SELECT r.id,r.row_count,r.columns_json,t.version,t.row_count AS indexed_rows
        FROM runs r LEFT JOIN timeline_index t ON t.run_id=r.id
        WHERE r.case_id=? AND r.status='completed' AND (?='' OR r.id=?)
        AND (t.run_id IS NULL OR t.row_count!=r.row_count OR t.version<?)""",
        (case_id,run_id,run_id,INDEX_VERSION)).fetchall()


def write_index_batch(c, run_id, rows, after, mft_columns):
    through = rows[-1]['idx']
    # SQLite's legacy transaction control does not implicitly begin a
    # transaction for the WITH ... INSERT used by the MFT migration.
    c.execute('BEGIN IMMEDIATE')
    if mft_columns:
        add_mft_dates(c, run_id, mft_columns, after, through)
    else:
        c.execute("DELETE FROM timeline_events WHERE run_id=? AND row_idx>? AND row_idx<=?",
                  (run_id,after,through))
        for row in rows:
            index_row(c,run_id,row['idx'],json.loads(row['data']))
    # Let note saves, cancellation and worker progress acquire the writer lock.
    c.commit()
    return through


def migrate_index(c, run):
    run_id = run['id']
    columns = json.loads(run['columns_json'])
    can_extend = run['version'] == 1 and run['indexed_rows'] == run['row_count'] and columns
    mft_columns = [column for column in columns if field_key(column) in MFT_FIELDS]
    if can_extend and mft_columns:
        c.create_function('studio_utc_time', 1, utc_time, deterministic=True)
    if not can_extend or mft_columns:
        after = -1
        selected = 'idx' if can_extend else 'idx,data'
        while True:
            rows = c.execute(f"""SELECT {selected} FROM result_rows WHERE run_id=? AND idx>?
                ORDER BY idx LIMIT ?""", (run_id,after,INDEX_BATCH_SIZE)).fetchall()
            if not rows:
                break
            after = write_index_batch(c, run_id, rows, after, mft_columns if can_extend else None)
    # Timeline readers wait for this marker. Retrying after an interruption
    # revisits the committed chunks safely until it can publish a complete index.
    mark_indexed(c,run_id,run['row_count'])
    c.commit()


def ensure_index(case_id, run_id=''):
    with db.connection() as c:
        if not missing_indexes(c, case_id, run_id):
            return
    with MIGRATION_LOCK, db.connection() as c:
        for run in missing_indexes(c, case_id, run_id):
            migrate_index(c, run)

def page(case_id,offset=0,limit=100,q='',scope='all',run_id=''):
    ensure_index(case_id, run_id)
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
    event_joins = 'FROM timeline_events e JOIN runs r ON r.id=e.run_id'
    source_join = ' JOIN result_rows d ON d.run_id=e.run_id AND d.idx=e.row_idx'
    order = ' ORDER BY e.time,e.run_id,e.row_idx,e.field'
    with db.connection() as c:
        c.execute('BEGIN')  # count and page share one SQLite read snapshot.
        if q:
            joins = event_joins + source_join + ' WHERE ' + where
            total = c.execute('SELECT COUNT(*) ' + joins, args).fetchone()[0]
            records = c.execute('SELECT e.*,r.plugin,r.created AS run_created,d.data ' + joins + order
                                + ' LIMIT ? OFFSET ?', (*args,limit,offset)).fetchall()
        else:
            joins = event_joins + ' WHERE ' + where
            total = c.execute('SELECT COUNT(*) ' + joins, args).fetchone()[0]
            page = 'SELECT e.*,r.plugin,r.created AS run_created ' + joins + order + ' LIMIT ? OFFSET ?'
            records = c.execute('SELECT e.*,d.data FROM (' + page + ') e' + source_join + order,
                                (*args,limit,offset)).fetchall()
        examined=c.execute("SELECT COALESCE(SUM(row_count),0) FROM runs WHERE case_id=? AND status='completed'",(case_id,)).fetchone()[0]
    return {'events':[{**dict(r),'data':json.loads(r['data'])} for r in records],
            'total':total,'offset':offset,'limit':limit,'examined_rows':examined,'limited':False}
