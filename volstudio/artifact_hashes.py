import hashlib
import os
from functools import lru_cache
from pathlib import Path


class ArtifactChanged(Exception):
    pass


def _identity(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@lru_cache(maxsize=256)
def _hash_file(path: Path, identity: tuple[int, ...]) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    buffer = bytearray(1024 * 1024)
    view = memoryview(buffer)
    with path.open('rb', buffering=0) as stream:
        opened = _identity(os.fstat(stream.fileno()))
        # On Windows, stat and fstat can report different meanings for ctime.
        if opened[:4] != identity[:4]:
            raise ArtifactChanged
        while count := stream.readinto(buffer):
            md5.update(view[:count])
            sha256.update(view[:count])
        if _identity(os.fstat(stream.fileno())) != opened or _identity(path.stat()) != identity:
            raise ArtifactChanged
    return md5.hexdigest(), sha256.hexdigest()


def artifact_digests(path: Path) -> dict[str, str]:
    identity = _identity(path.stat())
    md5, sha256 = _hash_file(path, identity)
    if _identity(path.stat()) != identity:
        raise ArtifactChanged
    return {'md5': md5, 'sha256': sha256}
