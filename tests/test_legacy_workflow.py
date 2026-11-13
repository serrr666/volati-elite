import json

import pytest
from fastapi.testclient import TestClient

from volstudio import catalog, db, legacy, runner
from volstudio.app import app
from volstudio.security import API_TOKEN, TOKEN_HEADER


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DATA', tmp_path)
    monkeypatch.setattr(catalog, 'refresh', lambda *_: None)
    monkeypatch.setattr(runner, 'start', lambda: None)
    monkeypatch.setattr(runner, 'shutdown', lambda: None)
    monkeypatch.setattr(legacy, 'runtime', lambda: ('python.exe', 'vol.py'))
    with TestClient(app, headers={TOKEN_HEADER: API_TOKEN}) as client:
        sha = 'a' * 64
        db.execute("""INSERT INTO cases(id,name,path,os,size,sha256,hash_status,created)
            VALUES('case','Evidence','C:/qa.vmss','windows',1,?,'complete',?)""", (sha, db.now()))
        for run_id, plugin, status, error in (
            ('info', 'windows.info.Info', 'completed', None),
            ('consoles', 'windows.consoles.Consoles', 'failed',
             'NotImplementedError: This version of Windows is not supported: 6.1 15.7600!'),
            ('cmdscan', 'windows.cmdscan.CmdScan', 'failed', 'Missing kernel symbols'),
        ):
            db.execute("""INSERT INTO runs(id,case_id,plugin,params,status,created,input_sha256,error,engine_version)
                VALUES(?,'case',?,'{}',?,?,?,?,'2.28.2')""", (run_id, plugin, status, db.now(), sha, error))
        fields = {'NTBuildLab': '7600.16385.x86fre.win7_rtm.090713', 'CSDVersion': '0', 'NtMajorVersion': '6',
                  'NtMinorVersion': '1', 'Is64Bit': 'False'}
        for index, (key, value) in enumerate(fields.items()):
            db.execute("INSERT INTO result_rows VALUES('info',?,0,?)", (index, json.dumps({'Variable': key, 'Value': value})))
        yield client


def test_legacy_fallback_creates_a_separate_reproducible_attempt(api):
    runs = {run['id']: run for run in api.get('/api/cases/case/runs').json()}
    assert runs['consoles']['legacy_console_profile'] == 'Win7SP0x86'
    assert api.get('/api/workspace/activity').json()['completed_runs'] == 1
    response = api.post('/api/runs/consoles/legacy')
    assert response.status_code == 201
    queued = response.json()
    assert (queued['legacy_profile'], queued['legacy_source_run'], queued['engine_version']) == ('Win7SP0x86', 'consoles', '2.6.1')
    assert queued['input_sha256'] == 'a' * 64 and queued['offline'] is True
    assert db.one("SELECT status FROM runs WHERE id='consoles'")['status'] == 'failed'
    assert api.post(f"/api/runs/{queued['id']}/retry").json()['legacy_source_run'] == 'consoles'


def test_fallback_rejects_unrelated_error_and_unverified_profile(api):
    assert api.post('/api/runs/cmdscan/legacy').status_code == 409
    db.execute("UPDATE result_rows SET data=? WHERE run_id='info' AND idx=4",
               (json.dumps({'Variable': 'Is64Bit', 'Value': 'True'}),))
    assert api.post('/api/runs/consoles/legacy').status_code == 409


def test_fallback_checks_the_current_evidence_and_optional_runtime(api, monkeypatch):
    monkeypatch.setattr(legacy, 'runtime', lambda: None)
    assert not api.get('/api/health').json()['legacy_available']
    assert api.post('/api/runs/consoles/legacy').status_code == 409
    db.execute("UPDATE cases SET sha256=? WHERE id='case'", ('b' * 64,))
    runs = {run['id']: run for run in api.get('/api/cases/case/runs').json()}
    assert runs['consoles']['legacy_console_profile'] is None
