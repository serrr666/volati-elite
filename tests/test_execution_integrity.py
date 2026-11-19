import hashlib
import os

import pytest

from volstudio import db, runner, symbol_store
from volstudio.evidence import evidence_stamp, read_guard


@pytest.fixture
def stored_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(db, 'DATA', tmp_path/'profile')
    monkeypatch.setattr(runner, 'WORKER', None)
    monkeypatch.setattr(runner, 'STOP', runner.threading.Event())
    db.init()
    path = tmp_path/'evidence.raw'
    path.write_bytes(b'original')
    with read_guard(path) as source:
        size, modified, _ = evidence_stamp(source)
    db.execute("""INSERT INTO cases(id,name,path,os,size,mtime_ns,sha256,hash_status,created)
                  VALUES('evidence','Evidence',?,'windows',?,?,?,'complete',?)""",
               (str(path),size,modified,hashlib.sha256(b'original').hexdigest(),db.now()))
    return path


def queue_run(id='analysis', status='queued'):
    db.execute("""INSERT INTO runs(id,case_id,plugin,params,status,created)
                  VALUES(?,'evidence','windows.pslist.PsList','{}',?,?)""",(id,status,db.now()))
    return db.one("SELECT * FROM runs WHERE id=?", (id,))


def test_legacy_case_checks_original_sha_even_when_timestamp_matches(stored_evidence):
    path = stored_evidence
    stat = path.stat()
    path.write_bytes(b'modified')
    os.utime(path, ns=(stat.st_atime_ns,stat.st_mtime_ns))
    runner.execute(queue_run())
    run = db.one("SELECT * FROM runs WHERE id='analysis'")
    assert run['status'] == 'failed'
    assert 'changed since hashing' in run['error']
    assert run['input_sha256'] is None and not run['worker_command']
    assert db.one("SELECT sha256 FROM cases WHERE id='evidence'")['sha256'] == hashlib.sha256(b'original').hexdigest()


def test_cancelled_selected_run_cannot_restart(stored_evidence):
    selected = queue_run()
    assert runner.cancel(selected['id'])
    runner.execute(selected)
    run = db.one("SELECT * FROM runs WHERE id='analysis'")
    assert run['status'] == 'cancelled'
    assert run['message'] == 'Cancelled by analyst' and run['started'] is None


@pytest.mark.parametrize('closing', [False, True])
def test_terminal_state_survives_symbol_preparation(stored_evidence, monkeypatch, closing):
    selected = queue_run()
    queue_run(id='next')

    def prepare(_paths, progress, stopped):
        assert not stopped()
        if closing:
            runner.shutdown()
        else:
            assert runner.cancel(selected['id'])
        assert stopped()
        progress('Late worker message')
        return []

    monkeypatch.setattr(symbol_store, 'prepare', prepare)
    runner.execute(selected)
    run = db.one("SELECT * FROM runs WHERE id='analysis'")
    assert (run['status'], run['message']) == (
        ('interrupted', 'Application closed during execution') if closing
        else ('cancelled', 'Cancelled by analyst'))
    assert run['finished'] and not run['worker_command']
    if closing:
        runner.execute(db.one("SELECT * FROM runs WHERE id='next'"))
    assert db.one("SELECT status FROM runs WHERE id='next'")['status'] == 'queued'
