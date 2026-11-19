"""The output directory and its history of completed extraction attempts."""
import json
import re
from pathlib import Path
from stat import S_ISREG


MANIFEST = 'artifact-manifest.jsonl'
INTERNAL = {
    MANIFEST, 'result.json', 'result.jsonl', 'engine.log', 'worker-job.json',
    'pipeline-distinct.sqlite3', 'pipeline-summary.json', 'legacy-result.part',
    'legacy.conf', 'legacy-cache',
}
OUTPUT_NAME = re.compile(r'[\w][\w .#()+,=@!$%\[\]{}-]*\.[\w-]+\Z')


def public_name(name):
    if not name or '\x00' in name or ':' in name:
        return False
    candidate = Path(name)
    temporary = candidate.name.casefold().startswith('tmp_') and candidate.suffix.casefold() == '.vol3'
    return (not candidate.anchor and '..' not in candidate.parts and bool(candidate.parts)
            and all(part.rstrip(' .').casefold() not in INTERNAL for part in candidate.parts)
            and not temporary)


def path_in_run(root, name):
    if not public_name(name):
        return None
    try:
        target = (root / name).resolve()
        relative = target.relative_to(root)
    except (ValueError, OSError, RuntimeError):
        return None
    return target if public_name(str(relative)) else None


def remember_outputs(root):
    manifest = root / MANIFEST
    if manifest.is_symlink() or not manifest.is_file():
        return None
    entries = {}
    with manifest.open(encoding='utf-8') as stream:
        for line in stream:
            try:
                item = json.loads(line)
                name, size = item['name'], item['size']
            except (ValueError, TypeError, KeyError):
                continue
            if (isinstance(name, str) and Path(name).name == name and public_name(name)
                    and type(size) is int and size >= 0):
                entries[name] = size
    return entries


def recorded_listing(root, historical):
    recorded = remember_outputs(root)
    if recorded is None:
        recorded = {name: None for name in historical() if isinstance(name, str)
                    and OUTPUT_NAME.fullmatch(name) and public_name(name)}
    entries = {name: {'name': name, 'size': size, 'available': False}
               for name, size in recorded.items()}
    for candidate in root.rglob('*'):
        name = str(candidate.relative_to(root))
        target = path_in_run(root, name)
        if target is None:
            continue
        try:
            stat = target.stat()
            if S_ISREG(stat.st_mode):
                entries[name] = {'name': name, 'size': stat.st_size, 'available': True}
        except OSError:
            continue
    return sorted(entries.values(), key=lambda entry: entry['name'].casefold())
