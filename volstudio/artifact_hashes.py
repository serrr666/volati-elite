import hashlib
from functools import lru_cache
from pathlib import Path

from .evidence import evidence_stamp, read_guard, still_current


class ArtifactChanged(Exception):
    pass


def _digests(stream) -> tuple[str, str]:
    md5 = hashlib.md5(usedforsecurity=False)
    sha256 = hashlib.sha256()
    buffer = bytearray(1024 * 1024)
    view = memoryview(buffer)
    while count := stream.readinto(buffer):
        md5.update(view[:count])
        sha256.update(view[:count])
    return md5.hexdigest(), sha256.hexdigest()


@lru_cache(maxsize=256)
def _cached_digests(path, stamp):
    with read_guard(path) as stream:
        if evidence_stamp(stream) != stamp:
            raise ArtifactChanged
        digests = _digests(stream)
        if not still_current(path, stream, stamp):
            raise ArtifactChanged
        return digests


def artifact_digests(path: Path) -> dict[str, str]:
    with read_guard(path) as stream:
        stamp = evidence_stamp(stream)
        md5, sha256 = _cached_digests(path, stamp) if stamp[2] else _digests(stream)
        if not still_current(path, stream, stamp):
            raise ArtifactChanged
    return {'md5': md5, 'sha256': sha256}
