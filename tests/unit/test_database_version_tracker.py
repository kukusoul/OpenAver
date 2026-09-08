"""測試 core/database/version_tracker.py（TASK-145-T2，CD-145a-10）。"""
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

import core.database.version_tracker as version_tracker
from core.database import get_connection, init_db
from core.database.version_tracker import (
    compute_db_fingerprint,
    compute_etag,
    get_showcase_revision,
)


def _insert_one(db_path, number):
    """開一條連線、做一筆真實 INSERT、commit、close。"""
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO videos (path, number) VALUES (?, ?)",
        (f"/fake/{number}.mp4", str(number)),
    )
    conn.commit()
    conn.close()


def test_concurrent_real_writes_bump_revision_exactly_n(tmp_path):
    """20 個 thread 各自一次真實寫入 → revision 恰好 +20，不多不少。"""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    start = get_showcase_revision()

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(_insert_one, db_path, i) for i in range(20)]
        for f in futures:
            f.result()

    end = get_showcase_revision()
    assert end - start == 20


def test_bump_showcase_revision_no_lost_updates_under_heavy_contention():
    """`_bump_showcase_revision()` 本體（不經過真連線／commit，直接高頻呼叫）在極端
    交錯機率下仍不掉更新。

    上面那支「20 thread 各一次真實 commit」是產品級 oracle（驗 DoD 的「+20 恰好」），
    但 20 次呼叫在 CPython 的 GIL 排程粒度下太稀疏，幾乎不可能真的讓兩個 thread 的
    `_revision += 1` 讀寫交錯。這支直接打計數器本體＋把 switch interval 調到最低放大
    交錯機率，仍然只是「量不出壞」的補強證據，不是本檔真正殺 mutation 的那一支
    （見下面 `test_bump_showcase_revision_lock_guards_every_increment` 的說明）——
    這支保留是因為它同時也驗證「高頻並發下計數器本身語意正確」這個獨立性質。
    """
    original_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        start = get_showcase_revision()
        threads_n = 8
        per_thread = 20000

        def worker():
            for _ in range(per_thread):
                version_tracker._bump_showcase_revision()

        threads = [threading.Thread(target=worker) for _ in range(threads_n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        end = get_showcase_revision()
    finally:
        sys.setswitchinterval(original_interval)

    assert end - start == threads_n * per_thread


def test_bump_showcase_revision_lock_guards_every_increment(monkeypatch):
    """`_bump_showcase_revision()` 遞增前後真的有拿到／放掉 module 級 `_lock`——
    這才是實際會因為 `with _lock:` 被換成 `if True:` 而紅的那一支。

    背景（CD-145a-10 mutation 點 idx 3 一度 SURVIVED 的根因）：CPython 3.11+ 的
    eval-breaker 只在迴圈 backward-jump／函式呼叫邊界檢查，`_revision += 1` 本身
    是零呼叫、零迴圈的 3 條直線 bytecode（LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL），
    中間沒有任何安全點可供排程器插入切換。實測：`sys.setswitchinterval(1e-6)`
    拉到極限、16 個 thread 各呼叫 100000 次（累積 160 萬次遞增）直接打
    `_bump_showcase_revision()`，即使把 `with _lock:` 換成 `if True:`，一次都沒有
    掉更新——上面那支「高交錯機率」測試量不出這個 mutation，不是巧合，是這個程式
    碼形狀在這個 Python 版本上天生量不出「自然競態」（拿掉鎖前後結果一樣綠）。

    改用結構性斷言換一個 oracle：把 `_lock` 換成一個包住真 `threading.Lock` 的
    計數器（`__enter__`/`__exit__` 各自 +1，仍然委派給真鎖做實際序列化），逼多個
    thread 去搶，斷言呼叫次數與 enter/exit 次數完全相等。`with _lock:` 被換成
    `if True:` 時，這個包裝鎖完全不會被觸碰，`enter_count`／`exit_count` 會停在
    0，這支測試必定紅——不依賴任何排程時機，100% 決定性。
    """

    class _CountingLock:
        def __init__(self):
            self._real = threading.Lock()
            self._count_lock = threading.Lock()
            self.enter_count = 0
            self.exit_count = 0

        def __enter__(self):
            self._real.acquire()
            with self._count_lock:
                self.enter_count += 1
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            with self._count_lock:
                self.exit_count += 1
            self._real.release()
            return False

    spy_lock = _CountingLock()
    monkeypatch.setattr(version_tracker, "_lock", spy_lock)

    threads_n = 8
    per_thread = 500
    expected = threads_n * per_thread

    def worker():
        for _ in range(per_thread):
            version_tracker._bump_showcase_revision()

    threads = [threading.Thread(target=worker) for _ in range(threads_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert spy_lock.enter_count == expected
    assert spy_lock.exit_count == expected


def test_init_db_noop_commit_does_not_bump_revision(tmp_path):
    """init_db() 對已存在 schema 的第二次呼叫是 no-op commit，不改 revision；
    緊接一筆真實 INSERT 才讓它變動。
    """
    db_path = tmp_path / "test.db"
    init_db(db_path)
    start = get_showcase_revision()

    init_db(db_path)
    assert get_showcase_revision() == start

    _insert_one(db_path, "noop-check")
    assert get_showcase_revision() == start + 1


def test_zero_row_update_does_not_bump_revision(tmp_path):
    """0 列 UPDATE（WHERE 恆不成立）之後 commit() → revision 不變。"""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    start = get_showcase_revision()

    conn = get_connection(db_path)
    conn.execute("UPDATE videos SET title = title WHERE 1 = 0")
    conn.commit()
    conn.close()

    assert get_showcase_revision() == start


def test_repeated_commit_without_new_writes_does_not_double_bump(tmp_path):
    """同一條連線做一次真實寫入＋commit()後，同連線再 commit() 一次（無新變更）
    → revision 不再變動。
    """
    db_path = tmp_path / "test.db"
    init_db(db_path)
    start = get_showcase_revision()

    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO videos (path, number) VALUES (?, ?)",
        ("/fake/repeat.mp4", "repeat"),
    )
    conn.commit()
    assert get_showcase_revision() == start + 1

    conn.commit()
    assert get_showcase_revision() == start + 1
    conn.close()


def test_compute_db_fingerprint_existing_files(tmp_path):
    """存在的檔案 → 回傳含五個真實值的 tuple（主檔／-wal 各一組）。"""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    wal_path = tmp_path / "test.db-wal"
    wal_path.write_bytes(b"fake-wal-content")

    fp = compute_db_fingerprint(db_path)

    assert len(fp) == 2
    main_fp, wal_fp = fp
    assert main_fp[0] is True
    assert len(main_fp) == 5
    assert wal_fp[0] is True
    assert len(wal_fp) == 5


def test_compute_db_fingerprint_stat_oserror_returns_sentinel(tmp_path, monkeypatch):
    """os.stat()/Path.stat() 拋出非 FileNotFoundError 的 OSError（如 PermissionError）
    → 函式本身不拋出，回傳同一固定哨兵。

    排在 test_compute_db_fingerprint_missing_files_returns_sentinel 之前：
    -x 模式下若後者先跑，也會在同一個 mutation 下失敗（FileNotFoundError 本身就是
    OSError 的子類），會搶先中止整條測試，讓這支永遠沒機會被觀察到。
    """
    db_path = tmp_path / "test.db"
    init_db(db_path)

    from pathlib import Path as _Path

    def _raise_permission_error(self, *args, **kwargs):
        raise PermissionError("simulated permission error")

    monkeypatch.setattr(_Path, "stat", _raise_permission_error)

    fp = compute_db_fingerprint(db_path)

    assert fp == ((False, 0, 0, 0, 0), (False, 0, 0, 0, 0))


def test_compute_db_fingerprint_missing_files_returns_sentinel(tmp_path):
    """DB 主檔與 -wal 都不存在 → 兩個元素都是固定「不存在」哨兵。"""
    db_path = tmp_path / "does_not_exist.db"

    fp = compute_db_fingerprint(db_path)

    assert fp == ((False, 0, 0, 0, 0), (False, 0, 0, 0, 0))


def test_compute_db_fingerprint_wal_only_change_differs(tmp_path):
    """只改 -wal 檔（主檔完全不動）→ 兩次呼叫的指紋 tuple 不同
    （主檔那一半相同、-wal 那一半不同）。
    """
    db_path = tmp_path / "test.db"
    init_db(db_path)
    wal_path = tmp_path / "test.db-wal"
    wal_path.write_bytes(b"first-content")

    fp1 = compute_db_fingerprint(db_path)

    wal_path.write_bytes(b"second-content-longer")

    fp2 = compute_db_fingerprint(db_path)

    assert fp1 != fp2
    assert fp1[0] == fp2[0]  # 主檔那一半沒變
    assert fp1[1] != fp2[1]  # -wal 那一半變了


def test_get_connection_pragma_unchanged(tmp_path):
    """factory 改動不影響既有連線行為：journal_mode 仍是 WAL。"""
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"


# ============ compute_etag() (TASK-145-T3) ============

_FP = ((True, 1, 2, 3, 4), (False, 0, 0, 0, 0))
_PROJECTION = {"directories": ["/a"], "path_mappings": {}, "thumbnail_cache_enabled": False}


def test_compute_etag_same_input_same_output():
    """同一組輸入呼叫兩次 → 逐字元相同的字串（快取比對靠這個穩定性）。"""
    a = compute_etag(1, _FP, _PROJECTION)
    b = compute_etag(1, _FP, _PROJECTION)
    assert a == b


def test_compute_etag_revision_change_changes_output():
    a = compute_etag(1, _FP, _PROJECTION)
    b = compute_etag(2, _FP, _PROJECTION)
    assert a != b


def test_compute_etag_db_fingerprint_change_changes_output():
    a = compute_etag(1, _FP, _PROJECTION)
    other_fp = ((True, 1, 2, 3, 999), (False, 0, 0, 0, 0))
    b = compute_etag(1, other_fp, _PROJECTION)
    assert a != b


def test_compute_etag_projection_change_changes_output():
    a = compute_etag(1, _FP, _PROJECTION)
    other_projection = {**_PROJECTION, "thumbnail_cache_enabled": True}
    b = compute_etag(1, _FP, other_projection)
    assert a != b


def test_compute_etag_projection_key_order_does_not_matter():
    """projection dict 的插入順序不影響結果——序列化必須 sort_keys，不能依賴呼叫端湊出的順序。"""
    p1 = {"a": 1, "b": 2}
    p2 = {"b": 2, "a": 1}
    assert compute_etag(1, _FP, p1) == compute_etag(1, _FP, p2)


def test_compute_etag_output_is_quoted_hex_strong_validator():
    """輸出是雙引號包住的十六進位字串，不帶 `W/` 弱驗證前綴。"""
    etag = compute_etag(1, _FP, _PROJECTION)
    assert etag.startswith('"') and etag.endswith('"')
    assert not etag.startswith('W/')
    inner = etag.strip('"')
    assert len(inner) == 64  # sha256 hexdigest
    int(inner, 16)  # 全部是合法十六進位字元，不會拋例外
