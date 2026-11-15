import hashlib
import json
import os

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
