"""[fixture] `from sqlite3 import connect as <alias>` — 守衛必須抓得到。

放在 tests/fixtures/ 底下（守衛正式掃描範圍 core/、web/ 之外），
所以它不會讓 CI 恆紅，也不需要為它開白名單（BE-TEST-13）。
驗收方式：`python scripts/no_raw_sqlite_connect_lint.py tests/fixtures/lint/aliased_connect_violation.py`
必須 exit 1。
"""
from sqlite3 import connect as db_connect


def bad_aliased_connect():
    conn = db_connect("output/openaver.db")
    return conn
