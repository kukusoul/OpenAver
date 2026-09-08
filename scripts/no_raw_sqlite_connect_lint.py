#!/usr/bin/env python3
"""no_raw_sqlite_connect_lint — 禁止繞過 core.database.get_connection() 的裸
sqlite3 連線／寫入（CD-145a-14），外加對 executescript() 的零容忍（CD-145a-14
擴充，本卡 owner 授權範圍：T2 的 _RevisionTrackingConnection.commit() 覆寫永
遠不會被 executescript() 觸發，它的隱式 commit 完全發生在 SQLite C 層）。

為什麼需要這支守衛：
    CD-145a-10 ①的正確性前提是「get_connection() 是全庫唯一的一般連線工
    廠」——每一筆內部寫入都要經過 _RevisionTrackingConnection.commit()，
    showcase revision 計數器才會準確（F2 的 ETag/304 依賴它：漏算一次
    revision bump 代表剛掃描完的新片永遠不會出現在瀏覽頁，而且重新整理
    也救不回來——瀏覽器會繼續信任手上那個過期的 ETag）。在本 task 之
    前，web/routers/tags.py:33 一直是這句話的反例。這支腳本把「不准繞
    過」從 code review 習慣變成機械檢查。

兩條規則，皆為 AST 掃描（BE-TEST-20：needle 是「呼叫」不是字面字串——
grep/regex 連寫在註解或 docstring 裡「不要這樣寫」的說明文字都會誤判成
違規呼叫）：

  1. 裸 `sqlite3.connect(...)`（或 `from sqlite3 import connect` 之後的裸
     `connect(...)`）出現在 core/ 或 web/ 底下即違規，除非：
       - 帶 `uri=True`，且第一個位置引數的靜態字串片段含 "mode=ro"
         （常數字串或 f-string 皆可；f-string 的 ast.FormattedValue
         插值片段一律跳過，不參與比對，只串接 ast.Constant 片段）；或
       - 帶 `factory=<Name>`，且該名稱等於 _FACTORY_CLASS_NAME，**且該呼叫落在
         _FACTORY_ALLOWED_PATH（core/database/connection.py）**——只認名稱字面
         會被「別的檔案自己定義一個同名但不是真子類的
         _RevisionTrackingConnection」繞過；全庫合法呼叫點只有一個，所以用位
         置收斂取代型別驗證。
     其餘型態的第一引數（變數、函式呼叫組出來的字串……）一律視為無法
     靜態判定 → 當作違規（fail-closed）。

  2. core/ 或 web/ 底下任何 `.executescript(...)` 呼叫一律違規，不分
     receiver 型別——2026-09-09 現況零呼叫點，這是白紙起點的 fail-closed
     空白名單，不是遷移中的過渡期。

用法：
    python scripts/no_raw_sqlite_connect_lint.py
        走 SCAN_ROOTS（core/、web/），回報所有違規，有違規 exit 1。
    python scripts/no_raw_sqlite_connect_lint.py PATH [PATH ...]
        只掃描指定檔案（供 BE-TEST-13「掃描範圍外 fixture」的驗證用，
        見 tests/fixtures/lint/）。
"""
from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = ["core", "web"]
EXCLUDED_DIRS = {"__pycache__", ".git"}
_FACTORY_CLASS_NAME = "_RevisionTrackingConnection"
# factory= 放行只認這一個檔案（T4 review finding ①）——全庫合法的 factory= 呼叫
# 點今天只有這一處（get_connection() 本體）。名稱字面比對本身抓不出「別的檔案
# 自己定義一個同名但不是真子類的 _RevisionTrackingConnection」這種繞法（要真的
# 驗證是不是子類，等於重寫一個 type-checker），但全庫合法呼叫點只有一個，所以
# 不必解析型別——直接把放行收斂到這個檔案即可，fail-closed：未來真有正當的第
# 二處，守衛會擋下來，逼那個人寫進白名單並附理由。
_FACTORY_ALLOWED_PATH = "core/database/connection.py"


@dataclass(frozen=True)
class Violation:
    rel_path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.rel_path}:{self.line}: {self.message}"


def _iter_py_files(roots: list[str]) -> list[Path]:
    files: list[Path] = []
    for root_entry in roots:
        root_path = ROOT / root_entry
        if root_path.is_file():
            files.append(root_path)
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            for fn in filenames:
                if fn.endswith(".py"):
                    files.append(Path(dirpath) / fn)
    return sorted(files)


def _static_string_content(node: ast.expr) -> str | None:
    """Call 第一個位置引數的最佳努力靜態字串內容。

    ast.Constant(str) -> 直接取值。ast.JoinedStr（f-string）-> 只串接
    其中的 ast.Constant 片段；ast.FormattedValue（{expr} 插值）一律跳
    過，不參與比對。其餘型態 -> None（無法靜態判定）。
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = [
            v.value
            for v in node.values
            if isinstance(v, ast.Constant) and isinstance(v.value, str)
        ]
        return "".join(parts)
    return None


def _is_sqlite_connect_call(
    node: ast.Call, sqlite_module_names: set[str], bare_connect_ok: bool
) -> bool:
    """比對 ``<name>.connect(...)``（attribute 形狀）或 ``connect(...)``
    （bare-name 形狀）。

    ``sqlite_module_names`` 的 baseline **恆含字面 "sqlite3"**——就算本檔
    完全沒有 ``import sqlite3``（例如把裸連線改掉之後，import 也跟著被
    移除的殘留寫法）也照樣命中，這是刻意的 fail-closed：字面名稱直接
    叫 ``sqlite3`` 而不是 stdlib 模組的情境在本庫不存在，用「有沒有 import」
    當放行條件反而會把「移除 import 但留著呼叫」這種一樣危險的殘留寫法
    漏放。額外的 ``import sqlite3 as <alias>`` 別名也會被加進這個集合
    （見呼叫端組集合的段落）。

    bare-name 形狀僅在本檔確實有 ``from sqlite3 import connect`` 時才算
    （``bare_connect_ok``）——bare "connect" 在本庫另有其他無關用途，例如
    ``core/metatube/state.py`` 的 ``def connect(self, ...)`` 與
    ``web/routers/settings_metatube.py`` 的 ``async def connect(req)``
    endpoint，沒有 import 前提會把它們一起誤殺。
    """
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "connect":
        if isinstance(func.value, ast.Name) and func.value.id in sqlite_module_names:
            return True
    if bare_connect_ok and isinstance(func, ast.Name) and func.id == "connect":
        return True
    return False


def scan_file(path: Path) -> list[Violation]:
    """掃描單一檔案，回傳違規清單。純函式：不管 path 是不是在 core/／web/
    底下——範圍由呼叫端（main()）決定，這讓 BE-TEST-13 的掃描範圍外
    fixture 可以直接被測，不必經過完整目錄 walk。
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    sqlite_module_names: set[str] = {"sqlite3"}  # baseline，恆含，見上方 docstring
    bare_connect_ok = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3" and alias.asname:
                    sqlite_module_names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "sqlite3":
                for alias in node.names:
                    if alias.name == "connect":
                        bare_connect_ok = True

    try:
        rel_path = path.relative_to(ROOT).as_posix()
    except ValueError:
        rel_path = str(path)

    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Attribute) and node.func.attr == "executescript":
            violations.append(
                Violation(
                    rel_path,
                    node.lineno,
                    "executescript() forbidden in core/web (see CD-145a-10 §1 / CD-145a-14)",
                )
            )
            continue

        if not _is_sqlite_connect_call(node, sqlite_module_names, bare_connect_ok):
            continue

        has_uri_true = any(
            kw.arg == "uri" and isinstance(kw.value, ast.Constant) and kw.value.value is True
            for kw in node.keywords
        )
        first_arg_static = _static_string_content(node.args[0]) if node.args else None
        mode_ro_ok = (
            has_uri_true and first_arg_static is not None and "mode=ro" in first_arg_static
        )

        factory_ok = rel_path == _FACTORY_ALLOWED_PATH and any(
            kw.arg == "factory"
            and isinstance(kw.value, ast.Name)
            and kw.value.id == _FACTORY_CLASS_NAME
            for kw in node.keywords
        )

        if mode_ro_ok or factory_ok:
            continue

        violations.append(
            Violation(
                rel_path,
                node.lineno,
                "raw sqlite3.connect() bypasses factory/read-only allowlist",
            )
        )
    return violations


def main(argv: list[str]) -> int:
    if argv:
        files = [Path(a) for a in argv]
    else:
        files = _iter_py_files(SCAN_ROOTS)

    all_violations: list[Violation] = []
    for f in files:
        all_violations.extend(scan_file(f))

    for v in all_violations:
        print(str(v))

    if all_violations:
        print(f"FAIL: {len(all_violations)} violation(s)")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
