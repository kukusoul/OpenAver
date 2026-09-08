"""Fixture（BE-TEST-13／CD-145a-14 executescript 擴充）：刻意違反
no_raw_sqlite_connect_lint 的第二條規則。同上，刻意放在掃描範圍外。
"""
import sqlite3


def bad_executescript(conn: sqlite3.Connection) -> None:
    conn.executescript("CREATE TABLE t (id INTEGER)")
