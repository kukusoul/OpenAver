"""process-global 版本追蹤：showcase revision 計數器 + DB/-wal 指紋 + 開機隨機值。

供 web/routers/showcase.py 的 ETag 計算使用（CD-145a-8/10/12）。
"""
import secrets
import sqlite3
import threading
from pathlib import Path

_lock = threading.Lock()
_revision = 0

_BOOT_SECRET = secrets.token_bytes(32)


class _RevisionTrackingConnection(sqlite3.Connection):
    """sqlite3.Connection 子類：commit() 成功後，若該連線的 total_changes
    相對上次 commit 有增加（＝真的寫入了東西），process-global revision 計數器 +1。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_committed_total_changes = 0

    def commit(self):
        super().commit()
        current = self.total_changes
        if current > self._last_committed_total_changes:
            _bump_showcase_revision()
        self._last_committed_total_changes = current


def _bump_showcase_revision() -> None:
    global _revision
    with _lock:
        _revision += 1


def get_showcase_revision() -> int:
    with _lock:
        return _revision


def _stat_fingerprint(path: Path) -> tuple:
    try:
        st = path.stat()
        return (True, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    except OSError:
        return (False, 0, 0, 0, 0)


def compute_db_fingerprint(db_path: Path) -> tuple:
    wal_path = db_path.with_name(db_path.name + "-wal")
    return (_stat_fingerprint(db_path), _stat_fingerprint(wal_path))
