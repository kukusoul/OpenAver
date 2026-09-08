"""Fixture（BE-TEST-13／T4 review finding ①）：刻意繞過 no_raw_sqlite_connect_lint
規則①的 factory= 放行條件——定義一個「同名但不是真子類」的
_RevisionTrackingConnection，傳給 factory= 卻不落在
core/database/connection.py（守衛的 _FACTORY_ALLOWED_PATH），必須被守衛抓到。
刻意放在掃描範圍外，同上兩個 fixture 的理由。
"""
import sqlite3


class _RevisionTrackingConnection:
    """同名 decoy——不是 core/database/connection.py 裡真的那個子類。"""


def bad_factory_decoy(db_path):
    conn = sqlite3.connect(db_path, factory=_RevisionTrackingConnection)
    return conn
