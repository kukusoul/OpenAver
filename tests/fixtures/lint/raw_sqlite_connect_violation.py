"""Fixture（BE-TEST-13）：刻意違反 no_raw_sqlite_connect_lint 的第一條規則。

刻意放在 tests/fixtures/ 底下、不在 core/ 或 web/ 底下——守衛預設的
core/／web/ walk 永遠不會掃到它，只有透過守衛的單檔 CLI 模式
（`python scripts/no_raw_sqlite_connect_lint.py <path>`）明確指定路徑才會
被掃到，用來證明「這條規則放進 core/／web/ 真的會被抓到」而不需要真的
把違規寫進生產碼。
"""
import sqlite3


def bad_connect(db_path):
    conn = sqlite3.connect(db_path)
    return conn
