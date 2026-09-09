"""[lint-guard: pytest-justified] install.ps1／OpenAver-Windows-Setup.bat 是
PowerShell／batch 檔，不是 Python，也不是前端資產——現有 eslint／stylelint／
scripts/*.mjs 都不吃這兩種副檔名。比照 CD-145b-5 的 [lint-guard:ps1-i18n] 先例，
用 pytest 頂替 lint 的角色，驗 T6（QuickEdit 關閉）的承重語意。

與既有 tests/unit/test_installer_script_guard.py（TASK-120b-T3）互不重疊：
那支驗 Exit-WithPause／trap 的結構順序與裸 exit，完全不知道 QuickEdit 這件事；
這支只驗 QuickEdit 區塊本身，不重新驗證 trap 結構。
"""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_INSTALL_PS1 = _ROOT / "install.ps1"
_INSTALL_BAT = _ROOT / "OpenAver-Windows-Setup.bat"


def _ps1_lines() -> list[str]:
    return _INSTALL_PS1.read_text(encoding="utf-8").splitlines()


def test_quickedit_constants_and_call_present():
    """(1) QuickEdit 常數與 SetConsoleMode 呼叫都在。"""
    text = "\n".join(_ps1_lines())
    assert "ENABLE_QUICK_EDIT_MODE" in text, "install.ps1 缺少 ENABLE_QUICK_EDIT_MODE 常數"
    assert "ENABLE_EXTENDED_FLAGS" in text, "install.ps1 缺少 ENABLE_EXTENDED_FLAGS 常數"
    assert "SetConsoleMode(" in text, "install.ps1 缺少 SetConsoleMode 呼叫"


def test_newmode_line_sets_both_flags():
    """(2) 承重行：$newMode 必須同時清 QUICK_EDIT、設 EXTENDED_FLAGS。
    少設 EXTENDED_FLAGS：Win32 文件記載 SetConsoleMode 會整次忽略這兩個旗標，
    等於使用者點一下黑視窗、安裝照樣被凍住——F1 沒有真的修好。
    """
    lines = _ps1_lines()
    newmode_lines = [l for l in lines if re.search(r"\$newMode\s*=", l)]
    assert len(newmode_lines) == 1, f"應該恰好一行 $newMode 賦值，找到 {len(newmode_lines)} 行"
    line = newmode_lines[0]
    # 鎖定運算元配對：-bnot 必須緊接 $ENABLE_QUICK_EDIT_MODE 且被 -band 消費；
    # -bor 必須緊接 $ENABLE_EXTENDED_FLAGS。四個 token 散落同列不算過關。
    assert re.search(
        r"-band\s*\(\s*-bnot\s+\$ENABLE_QUICK_EDIT_MODE\s*\)",
        line,
    ), f"$newMode 那一行沒有以 -band (-bnot $ENABLE_QUICK_EDIT_MODE) 清除 QUICK_EDIT：{line}"
    assert re.search(
        r"-bor\s+\$ENABLE_EXTENDED_FLAGS",
        line,
    ), f"$newMode 那一行沒有以 -bor $ENABLE_EXTENDED_FLAGS 設定 EXTENDED_FLAGS：{line}"


def test_quickedit_between_trap_end_and_title_banner():
    """(3) QuickEdit 區塊行號 > trap 結尾行號，且 < 第一個標題框 Write-Host。"""
    lines = _ps1_lines()
    trap_start = next(i for i, l in enumerate(lines) if re.match(r"^trap\s*\{", l))
    trap_end = next(i for i in range(trap_start + 1, len(lines)) if lines[i] == "}")
    quickedit_idx = next(i for i, l in enumerate(lines) if "ENABLE_QUICK_EDIT_MODE" in l)
    banner_idx = next(i for i, l in enumerate(lines) if l.strip() == 'Write-Host "=============================="')
    assert trap_end < quickedit_idx < banner_idx, (
        f"QuickEdit 區塊（第 {quickedit_idx + 1} 行）必須在 trap 結尾（第 {trap_end + 1} 行）之後、"
        f"標題框（第 {banner_idx + 1} 行）之前"
    )


def test_quickedit_wrapped_in_try_catch():
    """(4) 整段被 try { ... } catch {} 包住，失敗吞掉不觸發 trap。"""
    text = "\n".join(_ps1_lines())
    m = re.search(
        r"try\s*\{.*?ENABLE_QUICK_EDIT_MODE.*?SetConsoleMode\(.*?\}\s*catch\s*\{\}",
        text,
        re.DOTALL,
    )
    assert m is not None, "QuickEdit 區塊必須整段包在 try { ... } catch {} 裡"


def test_bat_chcp_silenced():
    """(5) OpenAver-Windows-Setup.bat 的 chcp 行含 >nul。"""
    text = _INSTALL_BAT.read_text(encoding="utf-8")
    assert re.search(r"chcp 65001\s*>nul", text), "OpenAver-Windows-Setup.bat 的 chcp 65001 沒有加 >nul"
