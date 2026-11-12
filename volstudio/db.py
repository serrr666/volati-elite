from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .diagnostics import unsupported_console_build
from .localization import default_language,default_theme

DATA = Path(os.environ.get("VOLSTUDIO_DATA", Path(__file__).resolve().parent.parent / "data")).resolve()
LOCK = threading.RLock()


def compare_text(left, right):
    # Volatility renders addresses as hexadecimal strings. Lexical order puts
    # 0x100 before 0x20; retain arbitrary precision when sorting those values.
    def key(value):
        if re.fullmatch(r"0[xX][0-9a-fA-F]+", value):
            return (0, int(value, 16))
        return (1, value.casefold(), value)
    a, b = key(left), key(right)
    return (a > b) - (a < b)


def now():
    return datetime.now(timezone.utc).isoformat()


def contains_value(encoded, query):
    """Literal search of values, excluding JSON keys, escapes and punctuation."""
    needle=query.casefold()
    def matches(value):
        if isinstance(value,dict):
            return any(matches(v) for v in value.values())
        if isinstance(value,list):
            return any(matches(v) for v in value)
        return value is not None and needle in str(value).casefold()
    return int(matches(json.loads(encoded)))


@contextmanager
def connection():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / "studio.sqlite3", timeout=30)
    conn.row_factory = sqlite3.Row
    conn.create_function("studio_casefold", 1, lambda value: value.casefold() if isinstance(value, str) else value, deterministic=True)
    conn.create_collation("studio_text", compare_text)
    conn.create_function("studio_exact_integer",2,lambda data,key:str(json.loads(data)[key]),deterministic=True)
    conn.create_function("studio_contains", 2, contains_value, deterministic=True)
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with connection() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL, os TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'evidence', size INTEGER NOT NULL, mtime_ns INTEGER,
          sha256 TEXT, hash_status TEXT DEFAULT 'pending', created TEXT NOT NULL,
          notes TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), plugin TEXT NOT NULL,
          params TEXT NOT NULL, status TEXT NOT NULL, progress REAL DEFAULT 0,
          message TEXT DEFAULT '', created TEXT NOT NULL, started TEXT, finished TEXT,
          row_count INTEGER DEFAULT 0, columns_json TEXT DEFAULT '[]', command TEXT DEFAULT '',
          error TEXT, output_dir TEXT, engine_version TEXT, offline INTEGER DEFAULT 1,
          input_sha256 TEXT, settings_json TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS result_rows (
          run_id TEXT NOT NULL REFERENCES runs(id), idx INTEGER NOT NULL,
          depth INTEGER DEFAULT 0, data TEXT NOT NULL, PRIMARY KEY(run_id,idx)
        );
        CREATE TABLE IF NOT EXISTS bookmarks (
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
          run_id TEXT NOT NULL REFERENCES runs(id), row_idx INTEGER NOT NULL,
          note TEXT NOT NULL DEFAULT '', created TEXT NOT NULL,
          UNIQUE(run_id,row_idx)
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workspace_notebook (
          id INTEGER PRIMARY KEY CHECK(id=1),text TEXT NOT NULL DEFAULT '',draft TEXT,updated TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS timeline_events (
          run_id TEXT NOT NULL, row_idx INTEGER NOT NULL, field TEXT NOT NULL,
          time TEXT NOT NULL, original TEXT NOT NULL,
          PRIMARY KEY(run_id,row_idx,field),
          FOREIGN KEY(run_id,row_idx) REFERENCES result_rows(run_id,idx)
        );
        CREATE INDEX IF NOT EXISTS timeline_order ON timeline_events(time,run_id,row_idx,field);
        CREATE TABLE IF NOT EXISTS timeline_index (
          run_id TEXT PRIMARY KEY REFERENCES runs(id),row_count INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS runs_case_status ON runs(case_id,status);
        CREATE INDEX IF NOT EXISTS runs_latest_plugin ON runs(case_id,plugin,status,created,id);
        CREATE TABLE IF NOT EXISTS note_drafts (
          case_id TEXT PRIMARY KEY REFERENCES cases(id),
          text TEXT NOT NULL, updated TEXT NOT NULL
        );
        """)
        for table, additions in {
            "cases": {"source_kind": "TEXT DEFAULT 'memory'", "detect_status": "TEXT DEFAULT 'manual'", "detected_banner": "TEXT DEFAULT ''", "image_format": "TEXT DEFAULT ''", "detect_message": "TEXT DEFAULT ''", "hash_progress": "REAL DEFAULT 0", "hash_error": "TEXT DEFAULT ''"},
            "runs": {"purpose": "TEXT DEFAULT 'analysis'", "memory_peak_bytes": "INTEGER DEFAULT 0", "memory_budget_mb": "INTEGER DEFAULT 0", "pipeline_summary_json": "TEXT DEFAULT '{}'", "worker_command": "TEXT DEFAULT ''", "studio_version": "TEXT DEFAULT ''", "studio_sha256": "TEXT DEFAULT ''"},
        }.items():
            existing = {row[1] for row in c.execute(f"PRAGMA table_info({table})")}
            for name, definition in additions.items():
                if name not in existing:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        c.execute("UPDATE runs SET status='interrupted', finished=?, message='Application restarted during execution' WHERE status IN ('running','indexing')", (now(),))

    with connection() as c:
        c.execute('CREATE TABLE IF NOT EXISTS workspace_revision(id INTEGER PRIMARY KEY,revision INTEGER NOT NULL)')
        c.execute('INSERT OR IGNORE INTO workspace_revision VALUES(1,0)')
        for table in ('cases','runs','bookmarks'):
            for operation in ('INSERT','UPDATE','DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS pulse_{table}_{operation} AFTER {operation} ON {table} BEGIN UPDATE workspace_revision SET revision=revision+1 WHERE id=1; END")


def all_rows(sql, args=()):
    with connection() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(sql, args=()):
    rows = all_rows(sql, args)
    return rows[0] if rows else None


def execute(sql, args=()):
    with LOCK, connection() as c:
        c.execute(sql, args)


def update_run(run_id, **values):
    keys = ",".join(f"{key}=?" for key in values)
    execute(f"UPDATE runs SET {keys} WHERE id=?", (*values.values(), run_id))


def settings():
    stored = {r["key"]: json.loads(r["value"]) for r in all_rows("SELECT * FROM settings")}
    return {"offline": False, "symbol_dirs": [], "plugin_dirs": [], "memory_limit_mb":0,"language":default_language(),"theme":default_theme(), **stored}


def save_settings(values):
    with connection() as c:
        for key, value in values.items():
            c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))


def serialize_run(r):
    return {**r, "params": json.loads(r["params"]), "columns": json.loads(r["columns_json"]),
            "offline": bool(r["offline"]), "settings": json.loads(r["settings_json"]),
            "unsupported_console_build": unsupported_console_build(r['plugin'], r.get('error')) if r['status']=='failed' else None,
            "pipeline_summary": json.loads(r.get("pipeline_summary_json") or '{}')}
