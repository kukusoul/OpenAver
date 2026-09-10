"""棘輪：scripts/no_raw_sqlite_connect_lint.py 的 scan_file() 不能被改瞎。

CI 預設只跑 `python scripts/no_raw_sqlite_connect_lint.py`（無參數 → 只掃乾淨的
core/、web/）。tests/fixtures/lint/ 裡的違規樣本不在那個 walk 範圍內，所以把
scan_file() 改成永遠 `return []`、或把 `_is_sqlite_connect_call()` 改成永遠
`return False`，CI 照樣全綠。

本檔直接呼叫 scan_file(fixture_path)（CD-145a-14 DoD）：
  - 每份 lint fixture 至少一筆違規，且行號／訊息對到 fixture 裡真正違規的那一行
    （永遠回一筆假違規也過不了）
  - 合法 factory= 呼叫點（core/database/connection.py）必須回空清單
    （永遠回一筆違規也過不了）
  - 讀不到的路徑、語法錯誤的檔案各恰好一筆（fail-closed，BE-TEST-05）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from no_raw_sqlite_connect_lint import scan_file  # noqa: E402

_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "lint"
_LINT_FIXTURES = sorted(p for p in _FIXTURE_DIR.glob("*.py") if p.is_file())
assert _LINT_FIXTURES, f"expected lint fixtures in {_FIXTURE_DIR}"


def _violating_call_lines(path: Path) -> list[tuple[int, str]]:
    """fixture 原始碼裡真正的違規呼叫行（1-based）與種類。

    不寫死檔名／行號：新加一份 fixture 就自動被 parametrize 吃到。跳過 import
    列（`from sqlite3 import connect as ...` 含 connect 字樣但不是呼叫）。
    """
    hits: list[tuple[int, str]] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        code = raw.split("#", 1)[0]
        stripped = code.strip()
        if "import " in code or stripped.startswith(("def ", "async def ", "class ")):
            continue
        if ".executescript(" in code:
            hits.append((i, "executescript"))
        elif "connect(" in code:
            hits.append((i, "connect"))
    return hits


@pytest.mark.parametrize("fixture", _LINT_FIXTURES, ids=lambda p: p.name)
def test_scan_file_flags_lint_fixture_at_real_line(fixture: Path):
    expected = _violating_call_lines(fixture)
    assert expected, f"{fixture.name}: fixture 裡應有 connect(/executescript( 呼叫"

    violations = scan_file(fixture)
    assert len(violations) >= 1, f"{fixture.name}: expected >=1 violation, got {violations!r}"

    by_line = {v.line: v for v in violations}
    for lineno, kind in expected:
        assert lineno in by_line, (
            f"{fixture.name}: scan_file 回報行 {sorted(by_line)}，"
            f"沒打到 fixture 第 {lineno} 行的 {kind} 呼叫"
        )
        message = by_line[lineno].message
        if kind == "executescript":
            assert "executescript" in message, (
                f"{fixture.name}:{lineno}: expected executescript in message, got {message!r}"
            )
        else:
            assert "sqlite3.connect" in message, (
                f"{fixture.name}:{lineno}: expected sqlite3.connect in message, got {message!r}"
            )


def test_scan_file_clean_on_factory_allowed_path():
    path = _REPO_ROOT / "core" / "database" / "connection.py"
    assert scan_file(path) == []


def test_scan_file_unreadable_path_is_one_violation(tmp_path):
    missing = tmp_path / "nope.py"
    violations = scan_file(missing)
    assert len(violations) == 1
    assert "無法讀取" in violations[0].message


def test_scan_file_syntax_error_is_one_violation(tmp_path):
    bad = tmp_path / "syntax_error.py"
    bad.write_text("def oops(\n", encoding="utf-8")
    violations = scan_file(bad)
    assert len(violations) == 1
    assert "無法解析" in violations[0].message
