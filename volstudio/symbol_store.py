"""Stage data-only symbol libraries so Volatility never writes to source folders."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from . import db

SUFFIXES = ('.json', '.json.xz', '.json.gz', '.json.bz2', '.zip')


def candidates(directory):
    root = Path(directory).resolve()
    if not root.is_dir():
        raise FileNotFoundError('Symbol library directory is unavailable: '+str(root))
    count = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        # Junctions and symlinks are not followed outside the selected library.
        dirs[:] = [d for d in dirs if not (Path(base)/d).is_symlink()
                   and not getattr(Path(base)/d,'is_junction',lambda:False)()
                   and (Path(base)/d).resolve().is_relative_to(root)]
        for name in files:
            source = Path(base)/name
            if not name.lower().endswith(SUFFIXES) or source.is_symlink():
                continue
            resolved = source.resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file():
                continue
            stat = resolved.stat()
            count += 1
            if count > 100000:
                raise ValueError('Too many symbol library files (maximum 100,000 per directory)')
            yield resolved, resolved.relative_to(root), stat


def prepare(directories, progress=lambda message: None, cancelled=lambda: False):
    """Return managed search paths, retaining content hashes for each snapshot.

    An unchanged source manifest (path/size/mtime) reuses its existing snapshot.
    Snapshot files are copies, never hard links or symlinks to evidence.
    """
    downloads = db.DATA/'symbol-downloads'
    downloads.mkdir(parents=True, exist_ok=True)
    store = db.DATA/'symbol-libraries'
    store.mkdir(parents=True, exist_ok=True)
    paths = [str(downloads)]
    for directory in directories:
        entries = sorted(candidates(directory), key=lambda item: str(item[1]))
        if cancelled():
            raise InterruptedError('Symbol import cancelled')
        if not entries:
            continue
        metadata = [(str(p), str(relative), stat.st_size, stat.st_mtime_ns) for p, relative, stat in entries]
        key = hashlib.sha256(json.dumps(metadata, ensure_ascii=False).encode('utf8')).hexdigest()
        target = store/key
        manifest = target/'.studio-symbol-manifest'
        if manifest.is_file():
            paths.append(str(target));continue
        staging = store/('.staging-'+uuid.uuid4().hex)
        staging.mkdir()
        copied = []
        try:
            for index, (source, relative, before) in enumerate(entries):
                destination = staging/relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                progress(f'Preparing OS analysis data: {index+1}/{len(entries)}')
                digest = hashlib.sha256()
                with source.open('rb') as src, destination.open('xb') as dst:
                    for block in iter(lambda: src.read(8*1024*1024), b''):
                        if cancelled():
                            raise InterruptedError('Symbol import cancelled')
                        digest.update(block);dst.write(block)
                after = source.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('Symbol library changed while being imported: '+str(source))
                copied.append({'source':str(source),'relative_path':str(relative),'size':before.st_size,'sha256':digest.hexdigest()})
            (staging/'.studio-symbol-manifest').write_text(json.dumps(
                {'method':'data-only copied snapshot; source folders are never passed to the engine',
                 'source_manifest_key':key,'files':copied}, ensure_ascii=False, indent=2), encoding='utf8')
            staging.rename(target)
        except BaseException:
            # This UUID staging directory is created and owned by this operation.
            if staging.parent == store and staging.name.startswith('.staging-'):
                shutil.rmtree(staging)
            raise
        paths.append(str(target))
    return paths
