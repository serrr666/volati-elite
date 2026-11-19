"""Small, read-only preview of a VMware snapshot inventory."""
import re
from pathlib import Path


FORMAT = 'VMware snapshot inventory · VMSD metadata'
SNAPSHOT_FIELD = re.compile(r'snapshot(\d{1,9})\.(uid|filename|displayName)\Z', re.I)
LINE = re.compile(r'^\s*([\w.]+)\s*=\s*"([^"\r\n]*)"', re.M)
MAX_BYTES = 256 * 1024


def sibling(path, filename):
    name = Path(filename)
    if (not filename or '\\' in filename or '/' in filename or ':' in filename or '\x00' in filename
            or name.suffix.lower() not in {'.vmsn', '.vmss', '.vmem'}):
        return None
    try:
        candidate = (path.parent / name).resolve(strict=True)
        return str(candidate) if candidate.parent == path.parent and candidate.is_file() else None
    except (OSError, RuntimeError):
        return None


def preview(path):
    path = Path(path).resolve()
    with path.open('rb') as source:
        data = source.read(MAX_BYTES + 1)
    fields = LINE.findall(data[:MAX_BYTES].decode('utf-8-sig', errors='replace'))
    current = next((value for key, value in fields if key.lower() == 'snapshot.current'), None)
    snapshots = {}
    for key, value in fields:
        match = SNAPSHOT_FIELD.fullmatch(key)
        if match:
            snapshots.setdefault(int(match[1]), {})[match[2].lower()] = value

    ordered = sorted(snapshots.values(), key=lambda row: current is None or row.get('uid') != current)
    return {
        'truncated': len(data) > MAX_BYTES or len(ordered) > 64,
        'snapshots': [
            {'name': row.get('displayname', ''), 'filename': row.get('filename', ''),
             'current': current is not None and row.get('uid') == current,
             'path': sibling(path, row.get('filename', ''))}
            for row in ordered[:64]
        ],
    }
