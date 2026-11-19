import csv
import hashlib
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from volstudio import catalog, db, runner
from volstudio.app import app
from volstudio.security import API_TOKEN, TOKEN_HEADER


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DATA', tmp_path / 'profile')
    monkeypatch.setattr(catalog, 'refresh', lambda *_: None)
    monkeypatch.setattr(runner, 'start', lambda: None)
    monkeypatch.setattr(runner, 'shutdown', lambda: None)
    with TestClient(app, headers={TOKEN_HEADER: API_TOKEN}) as api:
        db.execute("""INSERT INTO cases(id,name,path,os,kind,size,created,hash_status,notes)
            VALUES('case','QA','SYNTHETIC','windows','demo',0,?,'complete','keep notes')""", (db.now(),))
        yield api


def insert_run(run_id, plugin, *, sha='a' * 64, status='completed', error=None, output=None):
    db.execute("""INSERT INTO runs(id,case_id,plugin,params,status,created,input_sha256,error,output_dir)
        VALUES(?,'case',?,'{}',?,?,?,?,?)""", (run_id, plugin, status, db.now(), sha, error, output))


def insert_row(run_id, data):
    db.execute('INSERT INTO result_rows VALUES(?,0,0,?)', (run_id, json.dumps(data)))


def test_preferences_hide_recent_without_losing_case_and_preserve_favorites(client):
    favorite = 'windows.filescan.FileScan'
    result = client.put('/api/preferences', json={'hidden_recent_cases': ['case'], 'favorite_plugins': [favorite]})
    assert result.status_code == 200
    assert result.json()['hidden_recent_cases'] == ['case']
    assert client.put('/api/preferences', json={'theme': 'light'}).json()['favorite_plugins'] == [favorite]
    assert client.get('/api/cases/case/notebook').json()['text'] == 'keep notes'
    restored = client.put('/api/preferences', json={'hidden_recent_cases': []}).json()
    assert restored['hidden_recent_cases'] == [] and restored['favorite_plugins'] == [favorite]


@pytest.mark.parametrize('major,info_sha,offset,parameter', [
    ('6', 'a' * 64, '0x12abcd', 'physaddr'),
    ('10', 'a' * 64, '0xfffff80001800008', 'virtaddr'),
    ('6', 'b' * 64, '0x12abcd', None),
])
def test_dumpfiles_uses_address_kind_from_matching_snapshot(client, major, info_sha, offset, parameter):
    insert_run('info', 'windows.info.Info', sha=info_sha)
    insert_run('files', 'windows.filescan.FileScan')
    insert_row('info', {'Variable': 'NtMajorVersion', 'Value': major})
    insert_row('files', {'Offset': offset, 'Name': 'example.txt'})
    assert client.get('/api/runs/files/rows/0/dumpfiles').json() == {'address': offset, 'parameter': parameter}
    assert client.get('/api/runs/info/rows/0/dumpfiles').status_code == 409


def test_extracted_file_digests_refresh_when_file_changes(client, tmp_path):
    root = tmp_path / 'extracted'
    root.mkdir()
    artifact = root / 'sample.bin'
    insert_run('dump', 'windows.dumpfiles.DumpFiles', output=str(root))
    endpoint = '/api/runs/dump/artifact-hashes'
    for content in (b'test-one', b'test-two'):
        artifact.write_bytes(content)
        stamp = artifact.stat().st_mtime_ns + 2_000_000_000
        os.utime(artifact, ns=(stamp, stamp))
        result = client.get(endpoint, params={'name': artifact.name}).json()
        assert result == {'md5': hashlib.md5(content).hexdigest(), 'sha256': hashlib.sha256(content).hexdigest()}
    (root / 'engine.log').write_text('internal output')
    assert client.get(endpoint, params={'name': 'engine.log'}).status_code == 404


def test_extracted_file_digests_do_not_reuse_hash_after_rewrite_with_restored_mtime(client, tmp_path):
    artifact = tmp_path / 'same-size.bin'
    artifact.write_bytes(b'original')
    metadata = artifact.stat()
    insert_run('dump', 'windows.memmap.Memmap', output=str(tmp_path))
    endpoint = '/api/runs/dump/artifact-hashes'
    initial = client.get(endpoint, params={'name': artifact.name}).json()

    artifact.write_bytes(b'replaced')
    os.utime(artifact, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
    assert artifact.stat().st_mtime_ns == metadata.st_mtime_ns
    assert artifact.stat().st_size == metadata.st_size
    fresh = client.get(endpoint, params={'name': artifact.name}).json()
    assert initial['sha256'] == hashlib.sha256(b'original').hexdigest()
    assert fresh == {'md5': hashlib.md5(b'replaced').hexdigest(),
                     'sha256': hashlib.sha256(b'replaced').hexdigest()}


def test_exports_match_filtered_table_sort_across_pages(client):
    insert_run('sorted', 'qa.Sort')
    records = [
        {'Offset': hex((index % 13) * 16), 'Group': 'выбранная' if index % 5 else 'скрытая',
         'Text': f'след {index}, "quoted"\nnext' if index % 7 else 'skip'}
        for index in range(1800)
    ]
    with db.connection() as conn:
        conn.executemany('INSERT INTO result_rows VALUES(?,?,?,?)',
                         [('sorted',i,i%4,json.dumps(row,ensure_ascii=False)) for i,row in enumerate(records)])
    db.update_run('sorted', row_count=len(records), columns_json=json.dumps(list(records[0])))
    params = {'sort':'Offset', 'direction':'desc', 'q':'СЛЕД',
              'filters':json.dumps({'Group':{'exclude':False,'values':['text:выбранная']}},ensure_ascii=False)}
    base = '/api/runs/sorted'
    expected = sorted((i for i in range(len(records)) if i%5 and i%7),
                      key=lambda i: (-int(records[i]['Offset'],16), i))
    actual = []
    for offset in range(0,len(expected),200):
        table = client.get(base+'/rows',params={**params,'offset':offset,'limit':200}).json()
        assert table['total'] == len(expected)
        actual.extend(row['index'] for row in table['rows'])
    assert actual == expected

    def export(format):
        response = client.get(base+'/export',params={**params,'format':format})
        assert response.status_code == 200
        if format == 'json':
            assert response.json() == [{**records[i],'__depth':i%4} for i in expected]
        else:
            rows = list(csv.DictReader(io.StringIO(response.content.decode('utf-8-sig'))))
            assert [(int(row['_row']),int(row['_depth']),row['Text']) for row in rows] == [
                (i,i%4,records[i]['Text']) for i in expected]

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(export, ('csv','json')))
    assert client.get(base+'/export',params={'format':'jsonl','sort':'Offset'}).status_code == 422
    assert client.get(base+'/export',params={'sort':'unknown'}).status_code == 422


def test_value_search_uses_exact_legacy_unsigned_integer(client):
    insert_run('numbers', 'qa.Legacy')
    db.update_run('numbers', row_count=2, columns_json='["Address"]')
    numbers = [18446744073709551614,18446744073709551615]
    with db.connection() as conn:
        conn.executemany("INSERT INTO result_rows VALUES('numbers',?,0,?)",
                         [(i,json.dumps({'Address':number})) for i,number in enumerate(numbers)])
    result = client.get('/api/runs/numbers/values',params={'column':'Address','search':'551615'})
    assert result.json()['values'] == [{'token':f'integer:{numbers[1]}','type':'integer',
                                       'value':str(numbers[1]),'count':1}]


def test_artifact_history_survives_file_removal_and_keeps_manifest_private(client, tmp_path):
    from volstudio.artifact_files import MANIFEST

    root = tmp_path / 'artifacts'
    root.mkdir()
    artifact = root / 'sample.dmp'
    artifact.write_bytes(b'example')
    (root / MANIFEST).write_text(json.dumps({'name': artifact.name, 'size': 7}) + '\n', encoding='utf-8')
    insert_run('dump', 'windows.memmap.Memmap', output=str(root))

    url = '/api/runs/dump'
    assert client.get(url + '/artifacts').json() == [{'name': 'sample.dmp', 'size': 7, 'available': True}]
    assert client.get(url + '/artifact', params={'name': MANIFEST}).status_code == 404
    artifact.unlink()
    assert client.get(url + '/artifacts').json() == [{'name': 'sample.dmp', 'size': 7, 'available': False}]
    assert client.get(url + '/artifact-hashes', params={'name': artifact.name}).status_code == 404


def test_previous_dumpfiles_run_lists_an_unavailable_file_from_result(client, tmp_path):
    root = tmp_path / 'artifacts'
    root.mkdir()
    insert_run('dump', 'windows.dumpfiles.DumpFiles', output=str(root))
    db.update_run('dump', columns_json='["FileName", "Result"]')
    insert_row('dump', {'FileName': 'example.exe', 'Result': 'file.0x12.example.exe.img'})
    result = client.get('/api/runs/dump/artifacts').json()
    assert result == [{'name': 'file.0x12.example.exe.img', 'size': None, 'available': False}]


def test_snapshot_inventory_shows_current_state_file_and_missing_siblings(client, tmp_path):
    from hashlib import sha256
    from volstudio.vmsd import FORMAT

    path = tmp_path / 'Snapshot.vmsd'
    companion = tmp_path / 'first.vmsn'
    companion.write_bytes(b'example')
    path.write_text('\n'.join([
        'snapshot.current = "2"',
        'snapshot0.uid = "1"', 'snapshot0.displayName = "First"', 'snapshot0.filename = "first.vmsn"',
        'snapshot1.uid = "2"', 'snapshot1.displayName = "Current"', 'snapshot1.filename = "second.vmsn"',
        'snapshot2.uid = "3"', 'snapshot2.filename = "missing/third.vmsn"',
    ]), encoding='utf-8')
    stat = path.stat()
    db.execute("""UPDATE cases SET path=?,size=?,mtime_ns=?,sha256=?,image_format=?,source_kind='auxiliary'
        WHERE id='case'""", (str(path), stat.st_size, stat.st_mtime_ns, sha256(path.read_bytes()).hexdigest(), FORMAT))
    response = client.get('/api/cases/case/snapshot-inventory')
    assert response.status_code == 200
    assert response.json() == {'truncated': False, 'snapshots': [
        {'name': 'Current', 'filename': 'second.vmsn', 'current': True, 'path': None},
        {'name': 'First', 'filename': 'first.vmsn', 'current': False, 'path': str(companion.resolve())},
        {'name': '', 'filename': 'missing/third.vmsn', 'current': False, 'path': None},
    ]}
    path.write_text('changed', encoding='utf-8')
    assert client.get('/api/cases/case/snapshot-inventory').status_code == 409


def test_existing_console_failures_gain_a_build_specific_diagnosis(client):
    error = 'Volatility failed.\n\nNotImplementedError: This version of Windows is not supported: 6.1 15.7600!'
    for name in ('windows.consoles.Consoles', 'windows.cmdscan.CmdScan', 'windows.info.Info'):
        insert_run(name, name, status='failed', error=error)
    runs = {r['plugin']: r for r in client.get('/api/cases/case/runs').json()}
    assert runs['windows.consoles.Consoles']['unsupported_console_build'] == '6.1.7600'
    assert runs['windows.cmdscan.CmdScan']['unsupported_console_build'] == '6.1.7600'
    assert runs['windows.info.Info']['unsupported_console_build'] is None
    assert runs['windows.consoles.Consoles']['error'] == error


def test_upgrade_keeps_results_and_interrupts_jobs_for_removed_engine(client):
    for column in ('legacy_profile', 'legacy_source_run'):
        db.execute(f'ALTER TABLE runs ADD COLUMN {column} TEXT')
    plugin = 'windows.consoles.Consoles'
    insert_run('previous', plugin)
    insert_run('old_queue', plugin, status='queued')
    insert_run('regular_queue', plugin, status='queued')
    db.execute("UPDATE runs SET legacy_profile='Win7SP0x86',engine_version='2.6.1' WHERE id IN ('previous','old_queue')")
    insert_row('previous', {'Command': 'test'})
    db.execute("INSERT INTO bookmarks VALUES('bookmark','case','previous',0,'history',?)", (db.now(),))

    db.init()
    db.init()

    runs = {run['id']: run for run in client.get('/api/cases/case/runs').json()}
    assert runs['old_queue']['status'] == 'interrupted'
    assert runs['regular_queue']['status'] == 'queued'
    assert (runs['previous']['status'], runs['previous']['engine_version']) == ('completed', '2.6.1')
    assert 'legacy_profile' not in runs['previous'] and 'legacy_source_run' not in runs['previous']
    assert client.get('/api/cases/case/bookmarks').json()[0]['note'] == 'history'
    assert client.post('/api/runs/old_queue/legacy').status_code in (404, 405)


def test_restart_exposes_interrupted_detection_and_preserves_queued_detection(client):
    db.execute("UPDATE cases SET detect_status='windows' WHERE id='case'")
    insert_run('detect', 'windows.info.Info', status='queued')
    db.execute("UPDATE runs SET purpose='detection-windows' WHERE id='detect'")
    db.init()
    assert db.one("SELECT detect_status FROM cases WHERE id='case'")['detect_status'] == 'windows'

    db.execute("UPDATE runs SET status='running' WHERE id='detect'")
    db.init()
    assert db.one("SELECT detect_status FROM cases WHERE id='case'")['detect_status'] == 'interrupted'
    assert db.one("SELECT status FROM runs WHERE id='detect'")['status'] == 'interrupted'
    assert client.get('/api/workspace/pulse').json()['busy'] == 0
