"""Opt-in Volatility 2 support for verified Windows 7 x86 console cases."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import db
from .diagnostics import unsupported_console_build

VERSION = '2.6.1'
PLUGINS = {'windows.consoles.Consoles': 'consoles', 'windows.cmdscan.CmdScan': 'cmdscan'}
PROFILE = 'Win7SP0x86'


def runtime():
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent
    root = base / 'legacy-volatility2'
    python = root / 'python27' / 'python.exe'
    entry = root / f'volatility-{VERSION}' / 'vol.py'
    if sys.platform == 'win32' and python.is_file() and entry.is_file():
        return python, entry
    return None


def supported_profile(case, source):
    if (case['kind'] == 'demo' or case['os'] != 'windows' or case['hash_status'] != 'complete' or
        not case['sha256'] or source.get('input_sha256') != case['sha256'] or
        source.get('legacy_profile') or source['status'] != 'failed' or
        unsupported_console_build(source['plugin'], source.get('error')) != '6.1.7600'):
        return None
    params = json.loads(source['params'])
    defaults = {'max_history': [50], 'no_registry': False}
    if PLUGINS[source['plugin']] == 'consoles':
        defaults['max_buffers'] = [4]
    if any(key not in defaults or value != defaults[key] for key, value in params.items()):
        return None
    info = db.one("""SELECT id FROM runs WHERE case_id=? AND input_sha256=? AND status='completed'
        AND plugin='windows.info.Info' ORDER BY created DESC LIMIT 1""", (case['id'], case['sha256']))
    if not info:
        return None
    fields = {str(row.get('Variable', '')).casefold(): str(row.get('Value', '')) for row in
              (json.loads(item['data']) for item in db.all_rows('SELECT data FROM result_rows WHERE run_id=?', (info['id'],)))}
    if (fields.get('is64bit', '').casefold() == 'false' and fields.get('csdversion') == '0' and
        fields.get('ntmajorversion') == '6' and fields.get('ntminorversion') == '1' and
        fields.get('ntbuildlab', '').startswith('7600.')):
        return PROFILE
    return None
