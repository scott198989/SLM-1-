"""Capture an exact, quiescent SQLite file set without opening SQLite on sources.

Windows only. A caller must authorize the exact source and private destination.
No source discovery, recovery, checkpoint, row query or release decision occurs.
Reparse points fail closed. Evidence is not a substitute for isolation review.
"""

from contextlib import ExitStack, contextmanager
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import stat


class SnapshotBlocked(RuntimeError):
    """A safe physical snapshot could not be established."""


def _metadata(path: Path) -> dict:
    info = path.lstat()
    return {"bytes": info.st_size, "mtime_ns": info.st_mtime_ns,
            "device": info.st_dev, "inode": info.st_ino,
            "attributes": getattr(info, "st_file_attributes", 0),
            "reparse_tag": getattr(info, "st_reparse_tag", 0)}


def _plain_path(path: Path) -> None:
    for item in (path, *path.parents):
        if item.lstat().st_file_attributes & 0x400:
            raise SnapshotBlocked("reparse_point")


@contextmanager
def locked_reader(path: Path):
    """Hold a regular file open for reading, denying ordinary write/delete opens.

    Existing conflicting writable handles cause failure. The opened handle's
    final path and identity must equal the requested, non-reparse path.
    """
    if os.name != "nt":
        raise SnapshotBlocked("windows_required")
    import msvcrt
    path = Path(os.path.abspath(path))
    _plain_path(path)
    before = _metadata(path)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    final = kernel.GetFinalPathNameByHandleW
    final.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    final.restype = wintypes.DWORD
    handle = create(str(path), 0x80000000, 1, None, 3, 0x00200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise SnapshotBlocked(f"read_lock_failed_{ctypes.get_last_error()}")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = final(handle, buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise SnapshotBlocked("final_path_unavailable")
        actual = buffer.value
        if actual.startswith("\\\\?\\UNC\\"):
            actual = "\\\\" + actual[8:]
        elif actual.startswith("\\\\?\\"):
            actual = actual[4:]
        if os.path.normcase(actual) != os.path.normcase(str(path)):
            raise SnapshotBlocked("final_path_mismatch")
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
        handle = None  # descriptor owns it now
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise SnapshotBlocked("not_regular_file")
            if (opened.st_dev, opened.st_ino) != (before["device"], before["inode"]):
                raise SnapshotBlocked("file_identity_changed")
            _plain_path(path)
            if _metadata(path) != before:
                raise SnapshotBlocked("file_metadata_changed")
            yield stream
            if _metadata(path) != before:
                raise SnapshotBlocked("file_metadata_changed")
    finally:
        if handle is not None:
            close(handle)


def _digest(stream, target=None) -> str:
    stream.seek(0)
    digest = hashlib.sha256()
    while block := stream.read(1024 * 1024):
        digest.update(block)
        if target is not None:
            target.write(block)
    return digest.hexdigest()


def file_identity(path: Path) -> dict:
    """Hash exactly one authorized regular file under a held read lock."""
    path = Path(path)
    with locked_reader(path) as stream:
        metadata = _metadata(path)
        digest = _digest(stream)
        if _digest(stream) != digest:
            raise SnapshotBlocked("bytes_changed")
    return {**metadata, "sha256": digest, "identity_bytes_read": True,
            "semantic_content_read": False, "source_write_opened": False}


def capture_sqlite(source: Path, destination: Path) -> dict:
    """Capture main/-wal/-shm/-journal into a NEW directory, or fail closed.

    Main is locked first and all present components stay locked through two
    complete hash passes. A nonempty rollback journal is not interpreted.
    Captured files must stay unchanged; query a separate disposable derivative
    with ordinary mode=ro so any supplied WAL participates normally.
    Partial output after an I/O failure is unverified and must not be consumed.
    """
    if os.name != "nt":
        raise SnapshotBlocked("windows_required")
    source = Path(os.path.abspath(source))
    destination = Path(os.path.abspath(destination))
    suffixes = ("", "-wal", "-shm", "-journal")
    paths = {s: Path(str(source) + s) for s in suffixes}
    if destination.exists():
        raise SnapshotBlocked("destination_exists")
    _plain_path(destination.parent)
    with ExitStack() as stack:
        main = stack.enter_context(locked_reader(source))
        initial = {}
        streams = {"": main}
        for suffix, path in paths.items():
            try:
                initial[suffix] = _metadata(path)
            except FileNotFoundError:
                initial[suffix] = None
                continue
            if suffix:
                streams[suffix] = stack.enter_context(locked_reader(path))
        if initial["-journal"] and initial["-journal"]["bytes"]:
            raise SnapshotBlocked("nonempty_rollback_journal")
        if main.read(16) != b"SQLite format 3\x00":
            raise SnapshotBlocked("not_sqlite")
        destination.mkdir()
        captured = {}
        for suffix, stream in streams.items():
            target = destination / (source.name + suffix)
            with target.open("xb") as output:
                digest = _digest(stream, output)
            with target.open("rb") as copied:
                copy_digest = _digest(copied)
            if _digest(stream) != digest or copy_digest != digest:
                raise SnapshotBlocked("copy_or_source_changed")
            captured[suffix] = {**initial[suffix], "sha256": digest,
                                "copy_sha256": copy_digest, "copy_path": str(target)}
        for suffix, path in paths.items():
            try:
                after = _metadata(path)
            except FileNotFoundError:
                after = None
            if after != initial[suffix]:
                raise SnapshotBlocked("component_set_changed")
    return {"status": "CAPTURED_QUIESCENT_PHYSICAL_FILE_SET", "components": captured,
            "absent_components": [s for s in suffixes if initial[s] is None],
            "source_sqlite_opened": False, "source_write_opened": False,
            "locking": "CreateFileW GENERIC_READ FILE_SHARE_READ; all handles held",
            "limit": "Ordinary Windows filesystem sharing; not a malicious-writer or physical-disk forensic guarantee."}
