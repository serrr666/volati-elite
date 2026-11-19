"""Hold an evidence file open without allowing concurrent writes/deletion on Windows."""
import os
from hashlib import sha256
from contextlib import contextmanager


@contextmanager
def read_guard(path):
    if os.name!='nt':
        with open(path,'rb') as stream:
            yield stream
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.CreateFileW(str(path),0x80000000,0x00000001,None,3,0x80,None)
    if handle==wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except OSError:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, 'rb') as stream:
        yield stream


def windows_file_id(stream):
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class FileIdInfo(ctypes.Structure):
        _fields_ = [('volume', ctypes.c_uint64), ('file_id', ctypes.c_ubyte * 16)]

    class FileBasicInfo(ctypes.Structure):
        _fields_ = [('created', ctypes.c_int64), ('accessed', ctypes.c_int64),
                    ('written', ctypes.c_int64), ('changed', ctypes.c_int64),
                    ('attributes', wintypes.DWORD)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    get_info = kernel.GetFileInformationByHandleEx
    get_info.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    get_info.restype = wintypes.BOOL
    handle = msvcrt.get_osfhandle(stream.fileno())
    identity, times = FileIdInfo(), FileBasicInfo()
    # Some filesystems only provide part of this information. A missing
    # fingerprint makes the worker verify the hash instead of guessing.
    if (get_info(handle, 18, ctypes.byref(identity), ctypes.sizeof(identity)) and
            get_info(handle, 0, ctypes.byref(times), ctypes.sizeof(times)) and
            times.changed and any(identity.file_id)):
        return f'{identity.volume}:{bytes(identity.file_id).hex()}:{times.written}:{times.changed}'
    return None


def evidence_stamp(stream):
    stat = os.fstat(stream.fileno())
    identity = windows_file_id(stream) if os.name == 'nt' else (
        f'{stat.st_dev}:{stat.st_ino}:{stat.st_mtime_ns}:{stat.st_ctime_ns}')
    return stat.st_size, stat.st_mtime_ns, identity


def matches_case(case, stamp):
    size, modified, fingerprint = stamp
    return ((case['mtime_ns'] is None or (size, modified) == (case['size'], case['mtime_ns']))
            and (not case['file_fingerprint'] or not fingerprint or case['file_fingerprint'] == fingerprint))


def still_current(path, stream, before):
    if evidence_stamp(stream) != before:
        return False
    if os.name != 'nt':
        with read_guard(path) as current:
            return evidence_stamp(current) == before
    return True


def verified_stamp(case, stream, progress=None):
    path = case['path']
    stamp = evidence_stamp(stream)
    if not matches_case(case, stamp):
        raise ValueError('Evidence changed since hashing. Attach a fresh case before analysis.')
    if not case['file_fingerprint'] or not stamp[2]:
        if not case['sha256'] or evidence_hash(stream, progress) != case['sha256'] or not still_current(path, stream, stamp):
            raise ValueError('Evidence changed since hashing. Attach a fresh case before analysis.')
    return stamp


def evidence_hash(stream, progress=None):
    digest = sha256()
    processed = reported = 0
    while chunk := stream.read(8 * 1024 * 1024):
        digest.update(chunk)
        processed += len(chunk)
        if progress and processed - reported >= 64 * 1024 * 1024:
            progress(processed)
            reported = processed
    return digest.hexdigest()
