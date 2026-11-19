import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from types import SimpleNamespace

import pytest

from volstudio import catalog, db, runner, timeline
from volstudio.app import SettingsInput, refresh_plugins, save_settings


@pytest.fixture
def profile(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATA", tmp_path)
    db.init()
    return tmp_path


def legacy_timeline():
    created = "2026-08-01T10:00:00+00:00"
    raw = {"Created": created, "Updated": "2026-08-01T12:00:00+01:00"}
    indexes = (0, 1, 3, 7, 8)
    with db.connection() as c:
        c.execute("""INSERT INTO cases(id,name,path,os,size,created,hash_status)
            VALUES('case','Test case','fixture','windows',0,?,'complete')""", (created,))
        c.execute("""INSERT INTO runs(id,case_id,plugin,params,status,created,row_count,columns_json)
            VALUES('mft','case','windows.mftscan.MFTScan','{}','completed',?,5,?)""",
            (created,json.dumps(list(raw))))
        c.execute("""INSERT INTO runs(id,case_id,plugin,params,status,created)
            VALUES('pending','case','windows.pslist.PsList','{}','queued',?)""", (created,))
        c.executemany("INSERT INTO result_rows VALUES('mft',?,0,?)",
                      [(index,json.dumps(raw)) for index in indexes])
        c.executemany("INSERT INTO timeline_events VALUES('mft',?,'Created',?,?)",
                      [(index,timeline.utc_time(created),created) for index in indexes])
        c.execute("INSERT INTO timeline_index VALUES('mft',5,1)")
    return indexes


def test_migration_yields_to_notes_and_cancellation_without_partial_results(profile, monkeypatch):
    indexes = legacy_timeline()
    monkeypatch.setattr(timeline, "INDEX_BATCH_SIZE", 2)
    migration_paused, release_migration, second_request_started = Event(), Event(), Event()
    write_index_batch = timeline.write_index_batch

    def pause_second_batch(c, run_id, rows, after, mft_columns):
        if after == 1:
            migration_paused.set()
            assert release_migration.wait(8)
        return write_index_batch(c, run_id, rows, after, mft_columns)

    def save_note_and_cancel():
        db.execute("UPDATE cases SET notes='Investigation in progress' WHERE id='case'")
        return runner.cancel("pending")

    def read_again():
        second_request_started.set()
        return timeline.page("case", run_id="mft")

    monkeypatch.setattr(timeline, "write_index_batch", pause_second_batch)
    with ThreadPoolExecutor(max_workers=3) as pool:
        first = pool.submit(timeline.page, "case", run_id="mft")
        try:
            assert migration_paused.wait(5)
            assert db.one("SELECT version FROM timeline_index WHERE run_id='mft'")["version"] == 1
            assert db.one("SELECT count(*) n FROM timeline_events WHERE field='Updated'")["n"] == 2
            second = pool.submit(read_again)
            assert second_request_started.wait(5)
            assert pool.submit(save_note_and_cancel).result(timeout=5)
            assert not second.done()
        finally:
            release_migration.set()
        response = first.result(timeout=5)
        assert response == second.result(timeout=5)
    assert response["total"] == 10
    assert [event["row_idx"] for event in response["events"] if event["field"] == "Updated"] == list(indexes)
    assert db.one("SELECT notes FROM cases WHERE id='case'")["notes"] == "Investigation in progress"


def test_interrupted_migration_retries_committed_batches_without_duplicate_events(profile, monkeypatch):
    legacy_timeline()
    monkeypatch.setattr(timeline, "INDEX_BATCH_SIZE", 2)
    add_mft_dates = timeline.add_mft_dates

    def interrupt_second_batch(c, run_id, columns, after, through):
        add_mft_dates(c, run_id, columns, after, through)
        if after == 1:
            raise RuntimeError("test interruption")

    with monkeypatch.context() as patch:
        patch.setattr(timeline, "add_mft_dates", interrupt_second_batch)
        with pytest.raises(RuntimeError, match="test interruption"):
            timeline.page("case", run_id="mft")
    assert db.one("SELECT version FROM timeline_index WHERE run_id='mft'")["version"] == 1
    assert db.one("SELECT count(*) n FROM timeline_events WHERE field='Updated'")["n"] == 2
    assert timeline.page("case", run_id="mft")["total"] == 10
    assert db.one("SELECT version FROM timeline_index WHERE run_id='mft'")["version"] == timeline.INDEX_VERSION


def inventory(plugin_id):
    return {"version": "2.28.2", "status": "ready", "plugins": [{"id": plugin_id}], "warnings": []}


def test_refresh_uses_committed_paths_and_discovery_leaves_existing_settings_readable(profile, monkeypatch):
    old_path, new_path = profile/"old", profile/"new"
    old_path.mkdir()
    new_path.mkdir()
    db.save_settings({"plugin_dirs": [str(old_path)]})
    monkeypatch.setattr(catalog, "CATALOG", inventory("old.Plugin"))
    discovery_paused, refresh_requested, release_discovery = Event(), Event(), Event()
    seen = []

    def discover(settings, publish):
        assert not publish
        seen.append(settings["plugin_dirs"])
        if len(seen) == 1:
            discovery_paused.set()
            assert release_discovery.wait(8)
        name = Path(settings["plugin_dirs"][0]).name
        return inventory(f"{name}.Plugin")

    def refresh():
        refresh_requested.set()
        return refresh_plugins()

    monkeypatch.setattr(catalog, "refresh", discover)
    with ThreadPoolExecutor(max_workers=3) as pool:
        save = pool.submit(save_settings, SettingsInput(plugin_dirs=[str(new_path)]))
        try:
            assert discovery_paused.wait(5)
            next_catalog = pool.submit(refresh)
            assert refresh_requested.wait(5)
            config, active = pool.submit(catalog.configuration).result(timeout=5)
            assert config["plugin_dirs"] == [str(old_path)]
            assert active == inventory("old.Plugin")
        finally:
            release_discovery.set()
        assert save.result(timeout=5)["catalog"] == next_catalog.result(timeout=5)
    assert seen == [[str(new_path)], [str(new_path)]]
    assert catalog.CATALOG == inventory("new.Plugin")


def test_failed_refresh_keeps_working_catalog(profile, monkeypatch):
    last_good = inventory("windows.pslist.PsList")
    monkeypatch.setattr(catalog, "CATALOG", last_good)
    error = {"version": None, "status": "error", "plugins": [], "warnings": ["test failure"]}
    monkeypatch.setattr(catalog, "refresh", lambda *_: error)
    assert refresh_plugins() == error
    assert catalog.CATALOG == last_good


def test_frozen_discovery_outputs_are_isolated_and_removed(profile, monkeypatch):
    writers = Barrier(2)
    outputs = []

    def run(command, **_):
        output = Path(command[2])
        outputs.append(output)
        output.write_text(json.dumps(inventory(json.loads(command[3])[0])), encoding="utf-8")
        writers.wait(timeout=5)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(catalog, "sys", SimpleNamespace(frozen=True, executable="fixture.exe"))
    monkeypatch.setattr(catalog, "subprocess", SimpleNamespace(run=run, CREATE_NO_WINDOW=0))
    with ThreadPoolExecutor(max_workers=2) as pool:
        handles = [pool.submit(catalog.refresh, {"plugin_dirs": [plugin]}, False) for plugin in ("a.Plugin", "b.Plugin")]
        assert [handle.result(timeout=8) for handle in handles] == [inventory("a.Plugin"), inventory("b.Plugin")]
    assert len(set(outputs)) == 2 and not any(output.parent.exists() for output in outputs)
