"""[lint-guard:ps1-i18n] install.ps1 的四語 key 集合一致性——非 Python 檔案的內部
一致性檢查；現有 eslint/stylelint/scripts/*.mjs 都不吃 .ps1，CD-145b-5 已定案用
pytest 頂替 lint 的角色。
"""
import re
from pathlib import Path

INSTALL_PS1 = Path(__file__).resolve().parent.parent.parent / "install.ps1"
_LANGS = ("zh-TW", "zh-CN", "ja", "en")

_LANG_BLOCK_RE = re.compile(
    r"^    '(zh-TW|zh-CN|ja|en)' = @\{\r?\n(.*?)\r?\n    \}\r?\n",
    re.MULTILINE | re.DOTALL,
)
_KEY_RE = re.compile(r"^        ([A-Za-z0-9_]+)\s*=", re.MULTILINE)


def _extract_lang_keysets(ps1_text: str) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for lang, body in _LANG_BLOCK_RE.findall(ps1_text):
        result[lang] = set(_KEY_RE.findall(body))
    return result


def test_install_ps1_language_keysets_equal():  # [lint-guard:ps1-i18n]
    text = INSTALL_PS1.read_text(encoding="utf-8")
    keysets = _extract_lang_keysets(text)
    assert set(keysets.keys()) == set(_LANGS), (
        f"install.ps1 語言區塊掃描不到全部四語，只抓到 {sorted(keysets.keys())}"
        "——先確認縮排是不是 CD-145b-10 定死的 4/8 空格格式"
    )
    reference_lang, reference_keys = "zh-TW", keysets["zh-TW"]
    assert len(reference_keys) >= 20, "zh-TW key 數量低於預期下限，抽取邏輯可能沒抓到東西（空翻假綠）"
    for lang in _LANGS:
        diff = keysets[lang].symmetric_difference(reference_keys)
        assert not diff, f"{lang} 與 {reference_lang} 的 key 集合不相等，差異：{sorted(diff)}"


_L_TABLE_RE = re.compile(r"^\$L = @\{\r?\n.*?\r?\n\}\r?\n", re.MULTILINE | re.DOTALL)
_CJK_RE = re.compile(r"[぀-ヿ㐀-鿿]")
_HOST_STMT_RE = re.compile(r"\b(Write-Host|Read-Host|throw)\b", re.IGNORECASE)

# T7 已知例外（本卡窮舉時發現，見 TASK-145-T7.md「對 plan 的異議／偏離」）：
# install.ps1 裡 Expand-ZipRobust 的 zip-slip 防護 throw（"ZIP entry 逸出安裝目錄"）
# 刻意不進語言表——既有 tests/unit/test_installer_script_guard.py 的
# test_allows_throw_inside_expand_zip 對這行字面值有精確斷言，是那支既有回歸守衛
# 的白名單依據，本卡明定不改那支測試。這個 throw 只在惡意 zip 的 zip-slip 攻擊情境
# 下才會被觸發，不是一般安裝流程的語言體驗範圍。
_ZIP_SLIP_EXEMPT_MARKER = "ZIP entry 逸出安裝目錄"


def test_install_ps1_no_hardcoded_cjk_outside_lang_table():  # [lint-guard:ps1-i18n]
    text = INSTALL_PS1.read_text(encoding="utf-8")
    m = _L_TABLE_RE.search(text)
    assert m is not None, (
        "找不到 `$L = @{ ... }` 語言表區塊的起訖——CD-145b-10 的縮排格式可能被"
        "改動，這支測試 fail-closed 直接判失敗，不對整檔掃描"
    )
    stripped = text[: m.start()] + text[m.end():]
    violations = []
    for lineno, line in enumerate(stripped.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        if _ZIP_SLIP_EXEMPT_MARKER in line:
            continue
        if _HOST_STMT_RE.search(line) and _CJK_RE.search(line):
            violations.append((lineno, line))
    assert not violations, (
        "語言表外仍有硬編碼中日文字元的 Write-Host/Read-Host/throw 行"
        f"（漏改成 $T.<key>）：{violations}"
    )

    table_text = text[m.start():m.end()]
    table_body_lines = table_text.splitlines()[1:]
    dollar_violations = [
        (lineno, line)
        for lineno, line in enumerate(table_body_lines, start=2)
        if "$" in line
    ]
    assert not dollar_violations, (
        "語言表內出現 `$` 變數內插——CD-145b-10 規則 5：$L 表的每個 key 的值"
        "一律不得含變數內插（$Version 在表賦值當下還沒被賦值，會固化成空白），"
        f"改成 {{0}}/{{1}} 佔位符，呼叫端用 `-f` 帶入：{dollar_violations}"
    )


INSTALL_SH = Path(__file__).resolve().parent.parent.parent / "install.sh"

_SH_TABLE_RE = re.compile(
    r'^    case "\$\{LANG_KEY\}:\$1" in\n(.*?)\n    esac\n',
    re.MULTILINE | re.DOTALL,
)
_SH_KEY_LINE_RE = re.compile(r'^        (zh-TW|zh-CN|ja|en):([A-Za-z0-9_]+)\) echo "([^"]*)" ;;$', re.MULTILINE)


def _extract_sh_lang_keysets(sh_text: str):
    m = _SH_TABLE_RE.search(sh_text)
    assert m is not None, (
        "install.sh 找不到 `case \"${LANG_KEY}:$1\" in ... esac` 語言表區塊——"
        "CD-145b-17 的縮排格式可能被改動，fail-closed 直接判失敗，不對整檔掃描"
    )
    result: dict[str, set[str]] = {}
    for lang, key, _val in _SH_KEY_LINE_RE.findall(m.group(1)):
        result.setdefault(lang, set()).add(key)
    return result, m


def test_install_sh_language_keysets_equal():  # [lint-guard:ps1-i18n]
    text = INSTALL_SH.read_text(encoding="utf-8")
    keysets, _m = _extract_sh_lang_keysets(text)
    assert set(keysets.keys()) == set(_LANGS), (
        f"install.sh 語言表只抓到 {sorted(keysets.keys())}，缺少的語言 case 分支"
        "可能沒寫全，或縮排不符 CD-145b-17 格式"
    )
    reference_keys = keysets["zh-TW"]
    assert len(reference_keys) >= 15, "zh-TW key 數量低於預期下限，抽取邏輯可能沒抓到東西（空翻假綠）"
    for lang in _LANGS:
        diff = keysets[lang].symmetric_difference(reference_keys)
        assert not diff, f"install.sh：{lang} 與 zh-TW 的 key 集合不相等，差異：{sorted(diff)}"


def test_install_sh_no_hardcoded_cjk_outside_lang_table():  # [lint-guard:ps1-i18n]
    text = INSTALL_SH.read_text(encoding="utf-8")
    _keysets, m = _extract_sh_lang_keysets(text)
    stripped = text[: m.start()] + text[m.end():]
    host_re = re.compile(r"\b(echo|printf|read -p)\b")
    violations = [
        (lineno, line)
        for lineno, line in enumerate(stripped.splitlines(), start=1)
        if not line.strip().startswith("#") and host_re.search(line) and _CJK_RE.search(line)
    ]
    assert not violations, (
        "install.sh 語言表外仍有硬編碼中日文字元的 echo/printf/read -p 行"
        f"（漏改成 \"$(t <key>)\"）：{violations}"
    )


def test_install_sh_no_dollar_in_lang_table():  # [lint-guard:ps1-i18n]
    text = INSTALL_SH.read_text(encoding="utf-8")
    _keysets, m = _extract_sh_lang_keysets(text)
    dollar_violations = [
        (lang, key, val)
        for lang, key, val in _SH_KEY_LINE_RE.findall(m.group(1))
        if "$" in val
    ]
    assert not dollar_violations, (
        "install.sh 語言表內出現 `$` 變數內插——CD-145b-17 佔位符規則：一律用 %s，"
        f"呼叫端 printf 帶入：{dollar_violations}"
    )
