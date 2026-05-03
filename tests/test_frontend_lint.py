"""
前端遷移守衛測試 — 確保 Alpine 遷移過程不引入反模式

這些測試建立 baseline（V0），在後續 V1-V5 修復過程中逐步消除違規，
最終達到全部通過。
"""

import pytest
from pathlib import Path
from typing import List, Tuple
import re

# 專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent

# Vanilla inline event handlers (禁止)
# (?i) case-insensitive; (?<=\s) 前方需為空白，避免誤抓 data-onclick / x-onclick
VANILLA_HANDLER_PATTERN = r'(?i)(?<=\s)on(?:click|change|submit|keydown|input)\s*=\s*["\']'


def find_pattern_in_file(file_path: Path, regex: str,
                         exclude_lines: callable = None) -> List[Tuple[int, str]]:
    """
    在檔案中尋找符合 regex 的行

    Args:
        file_path: 檔案路徑
        regex: 正則表達式 pattern
        exclude_lines: 排除規則函數，接收 (line, line_number) 回傳 True 表示排除

    Returns:
        List of (line_number, line_content) tuples
    """
    violations = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if re.search(regex, line):
                    # 套用排除規則
                    if exclude_lines and exclude_lines(line, i):
                        continue
                    violations.append((i, line.rstrip()))
    except Exception as e:
        pytest.fail(f"無法讀取檔案 {file_path}: {e}")

    return violations


class TestNoVanillaHandlers:
    """確認所有 template 無 inline vanilla event handler"""

    def test_no_vanilla_handlers(self):
        """掃描所有 HTML template，確認無 onclick/onchange 等 inline handler"""
        templates_dir = PROJECT_ROOT / "web" / "templates"
        violations = []

        # 掃描主目錄 HTML 檔案（排除 design_system 子目錄）
        html_files = [f for f in templates_dir.glob("*.html")]

        for html_file in html_files:
            matches = find_pattern_in_file(
                html_file, VANILLA_HANDLER_PATTERN
            )
            for line_num, line_content in matches:
                violations.append(f"{html_file.name}:{line_num} — {line_content[:80]}")

        assert len(violations) == 0, (
            f"發現 {len(violations)} 個 vanilla inline handler 違規:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )


class TestNoHardcodedColors:
    """確認 CSS/HTML 無 hardcoded hex color"""

    def is_css_variable_definition(self, line: str, line_num: int) -> bool:
        """
        檢查是否為 CSS variable 定義行 (例外)

        CRITICAL FIX: 原本的 '--' in line and ':' in line 會誤判
        像 "background: linear-gradient(135deg, var(--accent) 0%, #007aff 100%)"
        這種只是「引用」CSS variable 的行（因為包含 var(--accent)）。

        必須檢查行是否「定義」CSS variable（以 --variable: 開頭）。
        """
        # 檢查是否為 CSS variable 定義（--variable-name: value;）
        return bool(re.match(r'\s*--[\w-]+\s*:', line))

    def is_svg_data_uri(self, line: str, line_num: int) -> bool:
        """檢查是否在 SVG data-uri 中 (例外)"""
        return 'data:image/svg' in line

    def is_intentional_color(self, line: str) -> bool:
        """檢查行內是否有 lint-ignore 或 VS Code 等已知例外註解"""
        # VS Code diff 配色、或任何帶 lint-ignore 標記的行
        return bool(re.search(r'/\*.*(?:VS Code|lint-ignore).*\*/', line))

    # CSS-scan method removed in T55b — superseded by stylelint `color-no-hex` rule.
    # HTML inline-scan method below stays as C-class deferral (T55d).

    def test_no_hardcoded_colors_in_html(self):
        """掃描 HTML inline styles，確認無 hardcoded hex color"""
        violations = []
        templates_dir = PROJECT_ROOT / "web" / "templates"
        html_files = [f for f in templates_dir.glob("*.html")]

        for html_file in html_files:
            # 跳過參考頁（design-system / motion-lab 是 demo 用途）
            if html_file.name in ("design-system.html", "motion_lab.html"):
                continue

            # 回參照確保同型引號閉合，避免 url('...') 巢狀引號漏判
            matches = find_pattern_in_file(
                html_file,
                r"""style\s*=\s*(["'])(?:(?!\1).)*#[0-9a-fA-F]{3,8}"""
            )

            for line_num, line_content in matches:
                violations.append(f"{html_file.name}:{line_num} — {line_content[:100]}")

        assert len(violations) == 0, (
            f"發現 {len(violations)} 個 hardcoded hex color 違規 (HTML inline):\n" +
            "\n".join(f"  - {v}" for v in violations)
        )


class TestSearchCssHardcoded:
    """Phase 51 T2.4 — search.css §1/§2/§3/§4 hardcoded 守衛

    確保 T2.1（color/rgba）/ T2.2（spacing 6px layout）修齊結果不被回退；
    新加違規會被擋下。allow-list 為 (line_num: reason) dict，新增例外
    必須提供 reason 字串說明（§3 角色色白名單 / §2 drop-shadow 例外 /
    var() fallback / §4 micro chip optical 之一）。

    T55b: blur / border-radius 兩支已由 stylelint 接管（無法表達 line-allowlist
    的 RGBA 與 6px layout 守衛保留 pytest）。
    """

    SEARCH_CSS = PROJECT_ROOT / "web/static/css/pages/search.css"

    HARDCODED_RGBA_ALLOWLIST = {
        # T2.1 commit 41f2a5b 後狀態：
        90: "drop-shadow rgba 0.3 — §2 例外（drop-shadow 跟封面去背形狀，非矩形 box-shadow 無法用 --fluent-shadow-* token）",
        780: "var(--bg-card, rgba(0, 0, 0, 0.05)) fallback — defensive fallback，非硬編碼違規",
    }

    SIX_PX_ALLOWLIST = {
        # T2.2 commit 89d52b6 後狀態：
        235: "row inline btn optical 6px — T2.2 加 optical 註記（btn-sm 12px padding 對 row inline 太寬）",
        516: ".batch-progress-bar height: 6px — intrinsic dimension（非 §4 spacing）",
        571: "chip optical 6px — T2.2 加 optical 註記（對齊 showcase .lb-tag-add-btn）",
    }

    def _scan(self, regex: str, allowlist=None):
        violations = []
        text = self.SEARCH_CSS.read_text(encoding='utf-8')
        for i, line in enumerate(text.splitlines(), 1):
            # 跳過純註解行（CSS comment 不是實際 declaration，提及 6px / rgba 為文檔說明）
            stripped = line.lstrip()
            if stripped.startswith('/*') or stripped.startswith('*'):
                continue
            if re.search(regex, line):
                if allowlist and i in allowlist:
                    continue
                violations.append((i, line.rstrip()))
        return violations

    def test_no_hardcoded_rgba_in_search_css(self):
        """禁 search.css 出現 rgba(0,0,0,...) 硬編碼（須走 var(--overlay-*) 角色色 token）"""
        violations = self._scan(
            r'rgba\(\s*0\s*,\s*0\s*,\s*0\s*,',
            allowlist=self.HARDCODED_RGBA_ALLOWLIST,
        )
        assert not violations, (
            f"search.css 出現新 rgba(0,0,0,...) 硬編碼違規 ({len(violations)} 處)：\n"
            + "\n".join(f"  L{n}: {l[:100]}" for n, l in violations)
            + "\n\n請改用 var(--overlay-*) 角色色 token；如為 §2 drop-shadow 例外 / "
            + "var() fallback，請更新 HARDCODED_RGBA_ALLOWLIST + 說明理由。"
        )

    def test_no_hardcoded_six_px_layout_in_search_css(self):
        """禁 search.css 出現 6px layout 違規（padding/margin/gap/etc.）"""
        # `[:\s]6px(?:\s|;|$)` 限定 6px 出現在 property value 上下文，避免 16px/26px/0.6px 誤抓
        violations = self._scan(
            r'[:\s]6px(?:\s|;|$)',
            allowlist=self.SIX_PX_ALLOWLIST,
        )
        assert not violations, (
            f"search.css 出現新 6px layout 違規 ({len(violations)} 處)：\n"
            + "\n".join(f"  L{n}: {l[:100]}" for n, l in violations)
            + "\n\n請改 layout 8pt grid / micro 4px / 加 /* ... optical 6px ... */ 註記 + 更新 SIX_PX_ALLOWLIST。"
        )


class TestNoInlineStyleDisplay:
    """確認 template 不用 style='display:none' 搭配 x-show"""

    @staticmethod
    def _parse_elements(html_text: str) -> List[Tuple[int, str]]:
        """
        將 HTML 中每個開標籤（可跨行）提取為 (起始行號, 完整標籤文字) 清單。
        只處理 < ... > 範圍，不解析 CDATA / script 等。
        """
        elements = []
        # 容許屬性值內有 > (如 x-show="a > 0")：跳過引號區段再匹配 >
        tag_re = re.compile(r'<[a-zA-Z](?:[^>"\'`]|"[^"]*"|\'[^\']*\'|`[^`]*`)*>', re.DOTALL)
        # 預建行號對照表：offset → line number
        line_starts = [0]
        for i, ch in enumerate(html_text):
            if ch == '\n':
                line_starts.append(i + 1)

        def offset_to_line(offset: int) -> int:
            lo, hi = 0, len(line_starts) - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if line_starts[mid] <= offset:
                    lo = mid
                else:
                    hi = mid - 1
            return lo + 1  # 1-based

        for m in tag_re.finditer(html_text):
            elements.append((offset_to_line(m.start()), m.group()))
        return elements

    def test_no_inline_style_display_with_x_show(self):
        """掃描所有 HTML，確認無 style display:none + x-show 重複（支援跨行、單/雙引號）"""
        # 回參照 \1 確保開閉引號一致，避免 url('...') 提前中斷
        display_none_re = re.compile(r"""style\s*=\s*(["'])(?:(?!\1).)*display:\s*none""")
        violations = []
        templates_dir = PROJECT_ROOT / "web" / "templates"
        html_files = list(templates_dir.rglob("*.html"))

        for html_file in html_files:
            try:
                html_text = html_file.read_text(encoding='utf-8')
            except Exception as e:
                pytest.fail(f"無法讀取 {html_file}: {e}")

            for line_num, tag_text in self._parse_elements(html_text):
                if 'x-show' in tag_text and display_none_re.search(tag_text):
                    preview = ' '.join(tag_text.split())[:100]
                    violations.append(
                        f"{html_file.relative_to(PROJECT_ROOT)}:{line_num} — {preview}"
                    )

        assert len(violations) == 0, (
            f"發現 {len(violations)} 個 style='display:none' + x-show 重複:\n" +
            "\n".join(f"  - {v}" for v in violations) +
            "\n\n提示：應該移除 style='display:none'，改用 x-cloak 處理初始隱藏"
        )


class TestMotionInfra:
    """確認 GSAP motion 基礎設施完整"""

    def test_motion_js_files_contain(self):
        """motion-prefs.js 和 motion-adapter.js 存在且包含必要 API / 函數"""
        for js_file, expected_strings in [
            (
                PROJECT_ROOT / "web" / "static" / "js" / "components" / "motion-prefs.js",
                ['prefersReducedMotion', 'openaver:motion-pref-change', 'addListener'],
            ),
            (
                PROJECT_ROOT / "web" / "static" / "js" / "components" / "motion-adapter.js",
                ['createContext', 'playEnter', 'playLeave', 'playStagger', 'playModal', '_shouldAnimate'],
            ),
        ]:
            assert js_file.exists(), f"{js_file.name} 不存在: {js_file}"
            content = js_file.read_text(encoding='utf-8')
            for expected in expected_strings:
                assert expected in content, f"{js_file.name} missing: {expected!r}"

    def test_base_html_loads_gsap_and_adapters(self):
        """base.html 載入 GSAP CDN + motion-prefs + motion-adapter，且順序正確"""
        base_html = PROJECT_ROOT / "web" / "templates" / "base.html"
        assert base_html.exists(), f"base.html 不存在: {base_html}"

        content = base_html.read_text(encoding='utf-8')

        assert 'gsap.min.js' in content, "base.html 缺少 GSAP CDN script"
        assert 'motion-prefs.js' in content, "base.html 缺少 motion-prefs.js"
        assert 'motion-adapter.js' in content, "base.html 缺少 motion-adapter.js"
        assert 'alpinejs' in content, "base.html 缺少 Alpine.js"

        # 驗證載入順序：GSAP → motion-prefs → motion-adapter → Alpine
        idx_gsap = content.index('gsap.min.js')
        idx_prefs = content.index('motion-prefs.js')
        idx_adapter = content.index('motion-adapter.js')
        idx_alpine = content.index('alpinejs')

        assert idx_gsap < idx_prefs, \
            "載入順序錯誤：gsap.min.js 應在 motion-prefs.js 之前"
        assert idx_prefs < idx_adapter, \
            "載入順序錯誤：motion-prefs.js 應在 motion-adapter.js 之前"
        assert idx_adapter < idx_alpine, \
            "載入順序錯誤：motion-adapter.js 應在 alpinejs 之前"

    def test_no_direct_gsap_calls_in_pages(self):
        """頁面/元件 JS 不直接呼叫 GSAP API — 必須透過 motion adapter"""
        # 共同根目錄，所有 allowed_files 相對路徑以此為基準
        js_root = PROJECT_ROOT / "web" / "static" / "js"
        scan_dirs = [
            js_root / "pages",
            js_root / "components",
        ]
        # motion-adapter.js 本身是合法 GSAP 呼叫點
        # motion-lab.js 和 search/animations.js 因動態座標計算需求，直接呼叫 GSAP
        # 相對路徑以 js_root 為基準，包含 pages/ 或 components/ 前綴，避免跨目錄衝突
        allowed_files = {
            Path('components') / 'motion-adapter.js',   # components/motion-adapter.js
            Path('pages') / 'motion-lab.js',            # pages/motion-lab.js（T1 新增）
            Path('pages') / 'motion-lab-state.js',      # pages/motion-lab-state.js（39b-T1 Alpine state 含 GSAP 委派呼叫）
            Path('pages') / 'search' / 'animations.js', # pages/search/animations.js（T6 預先加入）
            Path('pages') / 'showcase' / 'animations.js', # pages/showcase/animations.js（B6 動畫模組）
        }
        violations = []

        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for js_file in scan_dir.rglob("*.js"):
                rel = js_file.relative_to(js_root)  # 相對於 js_root，非 scan_dir
                if rel in allowed_files:
                    continue
                matches = find_pattern_in_file(
                    js_file,
                    r'(?:gsap\.(to|from|fromTo|set|timeline)\(|ScrollTrigger\.(create|batch)\()'
                )
                for line_num, line_content in matches:
                    violations.append(
                        f"{js_file.relative_to(PROJECT_ROOT)}:{line_num} — {line_content[:80]}"
                    )

        assert len(violations) == 0, (
            f"發現 {len(violations)} 個直接 GSAP 呼叫（應透過 OpenAver.motion.*）:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )


class TestNoDuplicateNativeDialog:
    """確認 duplicate modal 使用 Alpine state-driven pattern（不使用原生 showModal/close）"""

    def test_duplicate_modal_uses_modal_open_class(self):
        """search.html 的 duplicate modal 應使用 :class=\"{ 'modal-open': ... }\" pattern"""
        html_path = PROJECT_ROOT / "web/templates/search.html"
        content = html_path.read_text(encoding="utf-8")
        assert "duplicateModalOpen" in content, \
            "search.html 未找到 duplicateModalOpen — duplicate modal 應使用 Alpine state"


class TestTranslateAll:
    """確認 translateAll 前端基礎設施完整"""

    def test_translate_all_infra_contains(self):
        """search.html / base.js / batch.js 包含 translateAll 基礎設施（字串指紋守衛）"""
        search_html = PROJECT_ROOT / "web" / "templates" / "search.html"
        base_js = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "search" / "state" / "base.js"
        batch_js = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "search" / "state" / "batch.js"

        for path, expected_list in [
            (search_html, ["translateAll()", "listMode === 'search'"]),
            (base_js, ["translateState", "listMode === 'search'"]),
            (batch_js, ["async translateAll"]),
        ]:
            content = path.read_text(encoding='utf-8')
            for expected in expected_list:
                assert expected in content, f"{path.name} missing: {expected!r}"

        # 字串指紋守衛：殘留舊 fileList 判斷邏輯應已移除
        base_content = base_js.read_text(encoding='utf-8')
        assert "fileList.length === 0 && this.searchResults.length > 0" not in base_content, \
            "base.js should not contain: 'fileList.length === 0 && this.searchResults.length > 0'"


class TestJellyfinFrontend:
    """確認 Jellyfin 前端基礎設施完整"""

    def test_jellyfin_toggle_in_settings(self):
        """settings.html 包含 jellyfinMode 的 Alpine 綁定"""
        html_file = PROJECT_ROOT / "web" / "templates" / "settings.html"
        content = html_file.read_text(encoding='utf-8')
        assert 'jellyfinMode' in content, \
            "settings.html 缺少 jellyfinMode 綁定（Jellyfin 圖片模式開關）"

    def test_jellyfin_update_in_scanner(self):
        """scanner/state-scan.js 包含 runJellyfinImageUpdate method"""
        js_file = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "scanner" / "state-scan.js"
        content = js_file.read_text(encoding='utf-8')
        assert 'runJellyfinImageUpdate' in content, \
            "scanner/state-scan.js 缺少 runJellyfinImageUpdate（T6d Jellyfin 批次補齊）"

    def test_jellyfin_settings_hint_has_extrafanart(self):
        """settings.html Jellyfin 模式描述文字應包含 extrafanart/ 說明（T5b）
        i18n 後文字移至 locale JSON，檢查 zh_TW.json 或 HTML 中含 extrafanart"""
        html_file = PROJECT_ROOT / "web" / "templates" / "settings.html"
        html_content = html_file.read_text(encoding='utf-8')
        locale_file = PROJECT_ROOT / "locales" / "zh_TW.json"
        locale_content = locale_file.read_text(encoding='utf-8') if locale_file.exists() else ''
        assert 'extrafanart' in html_content or 'extrafanart' in locale_content, \
            "settings.html 或 locales/zh_TW.json Jellyfin 圖片模式描述缺少 extrafanart/ 說明（T5b）"


class TestOpenLocalGuard:
    """確認 openLocal() 綁定和 open_folder() API 的結構完整性（T5a / T5b）"""

    def test_open_local_in_search(self):
        """search.html 包含 openLocal( 綁定（Detail badge + Grid overlay 兩處）"""
        html_file = PROJECT_ROOT / "web" / "templates" / "search.html"
        content = html_file.read_text(encoding='utf-8')
        assert 'openLocal(' in content, \
            "search.html 缺少 openLocal( 綁定（T5b：Detail badge + Grid overlay）"

    def test_open_local_in_showcase(self):
        """showcase.html 包含 openLocal( 綁定（Grid overlay + Lightbox 兩處）"""
        html_file = PROJECT_ROOT / "web" / "templates" / "showcase.html"
        content = html_file.read_text(encoding='utf-8')
        assert 'openLocal(' in content, \
            "showcase.html 缺少 openLocal( 綁定（T5b：Grid overlay + Lightbox）"

    def test_open_local_method_exists(self):
        """result-card.js 和 showcase/state-videos.js 均包含 openLocal(path) method 定義"""
        result_card = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "search" / "state" / "result-card.js"
        showcase_videos = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "showcase" / "state-videos.js"

        rc_content = result_card.read_text(encoding='utf-8')
        assert 'openLocal(path)' in rc_content, \
            "result-card.js 缺少 openLocal(path) method 定義（T5b）"

        sc_content = showcase_videos.read_text(encoding='utf-8')
        assert 'openLocal(path)' in sc_content, \
            "showcase/state-videos.js 缺少 openLocal(path) method 定義（T5b）"

    def test_open_folder_pywebview_api(self):
        """windows/pywebview_api.py 包含 def open_folder（T5a）"""
        api_file = PROJECT_ROOT / "windows" / "pywebview_api.py"
        content = api_file.read_text(encoding='utf-8')
        assert 'def open_folder' in content, \
            "pywebview_api.py 缺少 def open_folder（T5a）"

    def test_no_stale_copy_local_path(self):
        """search.html 不包含 copyLocalPath( 呼叫（確認舊 call 已清除）"""
        html_file = PROJECT_ROOT / "web" / "templates" / "search.html"
        content = html_file.read_text(encoding='utf-8')
        assert 'copyLocalPath(' not in content, \
            "search.html 仍包含 copyLocalPath( — T5b 應已將其改為 openLocal()"

    def test_open_local_checks_return_value(self):
        """openLocal() 的 .then() 必須檢查 open_folder 回傳值（不能無條件當成功）"""
        for js_file in [
            PROJECT_ROOT / "web" / "static" / "js" / "pages" / "search" / "state" / "result-card.js",
            PROJECT_ROOT / "web" / "static" / "js" / "pages" / "showcase" / "state-videos.js",
        ]:
            content = js_file.read_text(encoding='utf-8')
            assert '.then(async (opened)' in content, \
                f"{js_file.name} openLocal() 的 .then() 缺少 opened 參數檢查"

    def test_open_local_cross_platform_path(self):
        """openLocal() 必須偵測 Windows drive letter 而非一律轉反斜線"""
        for js_file in [
            PROJECT_ROOT / "web" / "static" / "js" / "pages" / "search" / "state" / "result-card.js",
            PROJECT_ROOT / "web" / "static" / "js" / "pages" / "showcase" / "state-videos.js",
        ]:
            content = js_file.read_text(encoding='utf-8')
            assert 'displayPath' in content, \
                f"{js_file.name} openLocal() 缺少跨平台路徑格式偵測（displayPath）"


class TestPathContract:
    """路徑契約守衛測試 — 確保路徑處理邏輯集中在 path_utils.py（T7.0）

    4 個守衛測試掃描 production code 禁止模式（T7a-T7e 已全部修正通過）。
    """

    # 掃描範圍：core/ web/ windows/（排除 path_utils.py 本身）
    _SCAN_DIRS = ['core', 'web', 'windows']
    _ALLOWED_FILE = 'path_utils.py'

    def _collect_py_files(self):
        """收集 core/、web/、windows/ 下所有 .py 檔（排除 path_utils.py）"""
        files = []
        for dir_name in self._SCAN_DIRS:
            scan_dir = PROJECT_ROOT / dir_name
            if not scan_dir.exists():
                continue
            for py_file in scan_dir.rglob('*.py'):
                if py_file.name == self._ALLOWED_FILE:
                    continue
                files.append(py_file)
        return files

    def test_no_raw_uri_strip(self):
        """掃描 Python 檔，確認無 path[8:] 或 path[len('file:///'):]  手動 URI strip"""
        # 符合 [8:] 或 [len('file:///'):]
        pattern = r'''\[8:\]|\[len\(['"]file:///['"]\):\]'''
        violations = []
        for py_file in self._collect_py_files():
            matches = find_pattern_in_file(py_file, pattern)
            for line_num, line_content in matches:
                violations.append(
                    f"{py_file.relative_to(PROJECT_ROOT)}:{line_num} — {line_content[:80]}"
                )
        assert len(violations) == 0, (
            f"發現 {len(violations)} 個手動 URI strip 違規（應改用 uri_to_fs_path()）:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_manual_uri_construct(self):
        """掃描 Python 檔，確認無 f\"file:///{ 手動 URI 建構"""
        pattern = r'f["\']file:///'
        violations = []
        for py_file in self._collect_py_files():
            matches = find_pattern_in_file(py_file, pattern)
            for line_num, line_content in matches:
                violations.append(
                    f"{py_file.relative_to(PROJECT_ROOT)}:{line_num} — {line_content[:80]}"
                )
        assert len(violations) == 0, (
            f"發現 {len(violations)} 個手動 URI 建構違規（應改用 to_file_uri()）:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_shadow_path_helpers(self):
        """掃描 Python 檔，確認無 def wsl_to_windows_path / def to_file_uri shadow helper"""
        pattern = r'def wsl_to_windows_path|def to_file_uri'
        violations = []
        for py_file in self._collect_py_files():
            matches = find_pattern_in_file(py_file, pattern)
            for line_num, line_content in matches:
                violations.append(
                    f"{py_file.relative_to(PROJECT_ROOT)}:{line_num} — {line_content[:80]}"
                )
        assert len(violations) == 0, (
            f"發現 {len(violations)} 個 shadow path helper 定義（應集中在 path_utils.py）:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_path_to_display_js_no_optional_slash(self):
        """pathToDisplay JS 工具不應使用 /? regex（會錯誤吸收路徑前導斜線）"""
        # 搜尋所有 path-utils / pathUtils JS 檔
        candidates = list(PROJECT_ROOT.rglob('path-utils.js')) + \
                     list(PROJECT_ROOT.rglob('pathUtils.js'))
        # 排除 venv/、node_modules/
        js_files = [
            f for f in candidates
            if 'venv' not in f.parts and 'node_modules' not in f.parts
        ]
        if not js_files:
            pytest.skip("pathToDisplay JS 工具尚未建立（T7d 前）")
        violations = []
        for js_file in js_files:
            matches = find_pattern_in_file(js_file, r'\/\?')
            for line_num, line_content in matches:
                violations.append(
                    f"{js_file.relative_to(PROJECT_ROOT)}:{line_num} — {line_content[:80]}"
                )
        assert len(violations) == 0, (
            f"pathToDisplay 使用了 /? regex（會錯誤匹配路徑前導斜線）:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestVideoPlaybackGuard:
    """確認影片播放走 API proxy，不直接開 file:/// URI（瀏覽器安全策略會靜默阻擋）"""

    def test_no_window_open_file_uri_in_js(self):
        """前端 JS 不應有 window.open 搭配 file:/// URI（應走 /api/gallery/player）"""
        js_dirs = [
            PROJECT_ROOT / "web" / "static" / "js" / "pages",
            PROJECT_ROOT / "web" / "static" / "js" / "components",
        ]
        # window.open(path  或 window.open(file:/// 或 location.href = path（且 path 含 file:）
        pattern = r'window\.open\s*\(\s*path\s*,'
        violations = []
        for js_dir in js_dirs:
            if not js_dir.exists():
                continue
            for js_file in js_dir.rglob("*.js"):
                matches = find_pattern_in_file(js_file, pattern)
                for line_num, line_content in matches:
                    violations.append(
                        f"{js_file.relative_to(PROJECT_ROOT)}:{line_num} — {line_content[:80]}"
                    )
        assert len(violations) == 0, (
            f"發現 {len(violations)} 個 window.open(path, ...) 直接開啟路徑（瀏覽器會阻擋 file:/// URI）:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\n提示：瀏覽器模式應使用 /api/gallery/player?path= 代理播放"
        )

    def test_video_api_files_contain(self):
        """showcase/state-videos.js 和 scanner.py 包含必要 API proxy + 安全守衛字串"""
        for path, expected_list in [
            (
                PROJECT_ROOT / "web" / "static" / "js" / "pages" / "showcase" / "state-videos.js",
                ['/api/gallery/player'],
            ),
            (
                PROJECT_ROOT / "web" / "routers" / "scanner.py",
                ['async def get_video(', 'async def video_player(', 'os.path.normpath',
                 'get_proxy_extensions', 'is_path_under_dir'],
            ),
        ]:
            content = path.read_text(encoding='utf-8')
            for expected in expected_list:
                assert expected in content, f"{path.name} missing: {expected!r}"

    def test_no_hardcoded_video_extensions_in_modules(self):
        """gallery_scanner.py, scanner.py, pywebview_api.py must NOT contain hardcoded video extension sets
        (dict entries like '.mp4': 'video/mp4' are OK — those are MIME mappings, not extension sets)"""
        files_to_check = [
            PROJECT_ROOT / "core" / "gallery_scanner.py",
            PROJECT_ROOT / "web" / "routers" / "scanner.py",
            PROJECT_ROOT / "windows" / "pywebview_api.py",
        ]
        import re
        for file_path in files_to_check:
            content = file_path.read_text(encoding='utf-8')
            # Find set literals: = {'.mp4', '.avi', ...} (bare extension strings, no colon after)
            # This looks for lines with extension-only assignments
            # e.g., VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mkv', ...}
            # But NOT: video_mime = {'.mp4': 'video/mp4', ...}
            set_pattern = re.compile(r"""=\s*\{[^}]*'\.mp4'[^}:]*'\.avi'[^}:]*\}""", re.DOTALL)
            matches = set_pattern.findall(content)
            assert len(matches) == 0, \
                f"{file_path.name} still contains hardcoded video extension set — should import from core.video_extensions"


class TestSettingsSimplify:
    """T4a 守衛 — Settings 不再包含版本/更新 UI"""

    def test_settings_excludes(self):
        """settings.html/state-config.js 不含已搬移的 checkUpdate / loadVersion / restartTutorial"""
        html = (PROJECT_ROOT / 'web/templates/settings.html').read_text(encoding='utf-8')
        js = (PROJECT_ROOT / 'web/static/js/pages/settings/state-config.js').read_text(encoding='utf-8')
        for forbidden, content, fname in [
            ('checkUpdate', html, 'settings.html'),
            ('loadVersion', js, 'settings/state-config.js'),
            ('restartTutorial', js, 'settings/state-config.js'),
        ]:
            assert forbidden not in content, \
                f"{fname} should not contain: {forbidden!r}"


class TestHelpPage:
    """T4b 守衛 — Help 頁必要元素"""

    def test_help_html_contains(self):
        """help.html 含 helpPage / checkUpdate / hero-terminal / help.hero.ai_instruction；help.js script 無 defer"""
        html = (PROJECT_ROOT / 'web/templates/help.html').read_text(encoding='utf-8')
        for expected in ['helpPage', 'checkUpdate', 'hero-terminal', 'help.hero.ai_instruction']:
            assert expected in html, f"help.html missing: {expected!r}"
        assert (PROJECT_ROOT / 'web/static/js/pages/help.js').exists(), \
            "help.js missing: file does not exist"
        matches = re.findall(r'<script[^>]*help\.js[^>]*>', html)
        assert len(matches) == 1, \
            f"help.html 應恰好有 1 個 help.js script tag，找到 {len(matches)} 個"
        assert 'defer' not in matches[0], \
            "help.js script tag 帶有 defer — Alpine 會在 helpPage() 定義前初始化"

    def test_help_js_contains(self):
        """help.js 含 copyCurlCommand / execCommand"""
        js = (PROJECT_ROOT / 'web/static/js/pages/help.js').read_text(encoding='utf-8')
        for expected in ['copyCurlCommand', 'execCommand']:
            assert expected in js, f"help.js missing: {expected!r}"


class TestScannerClearCache:
    """清除快取守衛 — scanner 頁面必要元素"""

    def test_scanner_clear_cache_js_contains(self):
        """scanner/state-scan.js 含 clearCache() + DELETE /api/gallery/cache"""
        js = (PROJECT_ROOT / 'web/static/js/pages/scanner/state-scan.js').read_text(encoding='utf-8')
        for expected in ['clearCache()', '/api/gallery/cache', 'DELETE']:
            assert expected in js, f"scanner/state-scan.js missing: {expected!r}"


class TestSearchCoreFacade:
    """T3.2 守衛 → T4 更新：SearchCore facade 已完全消除"""

    def test_search_core_facade_files_excludes(self):
        """bridge.js 已刪除；persistence.js 不含 coreState?."""
        js_file = PROJECT_ROOT / "web/static/js/pages/search/state/bridge.js"
        assert not js_file.exists(), \
            "search/state/bridge.js should not exist: T4 Step 8 應已刪除此檔案"
        persistence = PROJECT_ROOT / "web/static/js/pages/search/state/persistence.js"
        content = persistence.read_text(encoding='utf-8')
        assert 'coreState?.' not in content, \
            "persistence.js should not contain: 'coreState?.'"

    def test_search_core_js_excludes(self):
        """core.js（若存在）不含 Alpine.$data / _legacyState / window.SearchCore = {"""
        js_file = PROJECT_ROOT / "web/static/js/pages/search/core.js"
        if not js_file.exists():
            return  # core.js 已刪除，通過
        content = js_file.read_text(encoding='utf-8')
        for forbidden in ['Alpine.$data', '_legacyState', 'window.SearchCore = {']:
            assert forbidden not in content, \
                f"search/core.js should not contain: {forbidden!r}"


class TestPageLifecycleGuard:
    """page-lifecycle.js 存在性守衛 — 確保 script tag 及三頁 __registerPage 呼叫不被移除"""

    def test_base_html_loads_page_lifecycle(self):
        """base.html 必須引用 page-lifecycle.js"""
        base_html = PROJECT_ROOT / "web" / "templates" / "base.html"
        content = base_html.read_text(encoding='utf-8')
        assert 'page-lifecycle.js' in content, \
            "base.html 缺少 page-lifecycle.js script tag — 刪除會導致三頁 __registerPage 呼叫靜默失敗"

    def test_settings_js_calls_register_page(self):
        """settings/state-config.js 必須呼叫 __registerPage"""
        js_file = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "settings" / "state-config.js"
        content = js_file.read_text(encoding='utf-8')
        assert '__registerPage' in content, \
            "settings/state-config.js 缺少 __registerPage 呼叫 — dirty-check lifecycle 會失效"

    def test_search_main_js_calls_register_page(self):
        """search/main.js 必須呼叫 __registerPage"""
        js_file = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "search" / "main.js"
        content = js_file.read_text(encoding='utf-8')
        assert '__registerPage' in content, \
            "search/main.js 缺少 __registerPage 呼叫 — Search 離頁 save/cleanup 會失效"

    def test_showcase_core_calls_register_page(self):
        """showcase/state-base.js 必須呼叫 __registerPage"""
        js_file = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "showcase" / "state-base.js"
        content = js_file.read_text(encoding='utf-8')
        assert '__registerPage' in content, \
            "showcase/state-base.js 缺少 __registerPage 呼叫 — Showcase lightbox cleanup lifecycle 會失效"

    def test_scanner_html_calls_register_page(self):
        """scanner/state-scan.js 必須呼叫 __registerPage"""
        js_file = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "scanner" / "state-scan.js"
        content = js_file.read_text(encoding='utf-8')
        assert '__registerPage' in content, \
            "scanner/state-scan.js 缺少 __registerPage 呼叫 — Scanner lifecycle 未接入統一機制"


class TestSettingsSourceBadge:
    """37d T2 守衛 — Settings radio 區塊已移除，badge 改為 primarySource 選擇器"""

    def test_settings_source_badge_html_contains(self):
        """settings.html badge 選擇器：不含 radio name=primarySource；含 primarySource 綁定"""
        html = (PROJECT_ROOT / 'web/templates/settings.html').read_text(encoding='utf-8')
        assert 'name="primarySource"' not in html, \
            "settings.html should not contain: 'name=\"primarySource\"'"
        assert 'primarySource' in html, \
            "settings.html missing: 'primarySource'"


class TestScannerLifecycleGuard:
    """T5.1 守衛 — Scanner 已接入 __registerPage，不再使用舊 shim"""

    SCANNER_HTML = PROJECT_ROOT / "web" / "templates" / "scanner.html"
    PAGE_LIFECYCLE_JS = PROJECT_ROOT / "web" / "static" / "js" / "components" / "page-lifecycle.js"

    def test_scanner_no_confirm_leaving_scanner(self):
        """scanner.html 不含 confirmLeavingScanner（舊 shim 已刪除）"""
        content = self.SCANNER_HTML.read_text(encoding='utf-8')
        assert 'confirmLeavingScanner' not in content, \
            "scanner.html 仍含 confirmLeavingScanner — T5.1 應已刪除舊離頁 shim"

    def test_scanner_no_self_added_beforeunload(self):
        """scanner.html 不自掛 addEventListener('beforeunload'（由 page-lifecycle.js 統一管理）"""
        content = self.SCANNER_HTML.read_text(encoding='utf-8')
        assert "addEventListener('beforeunload'" not in content, \
            "scanner.html 仍自掛 beforeunload listener — T5.1 應刪除，改由 onBeforeUnload hook 處理"

    def test_scanner_no_skip_before_unload(self):
        """scanner.html 不含 _skipBeforeUnload（隨舊 shim 一起刪除）"""
        content = self.SCANNER_HTML.read_text(encoding='utf-8')
        assert '_skipBeforeUnload' not in content, \
            "scanner.html 仍含 _skipBeforeUnload — T5.1 應已隨舊 shim 一起刪除"

    def test_page_lifecycle_no_confirm_leaving_scanner_shim(self):
        """page-lifecycle.js 不含 confirmLeavingScanner compatibility shim"""
        content = self.PAGE_LIFECYCLE_JS.read_text(encoding='utf-8')
        assert 'confirmLeavingScanner' not in content, \
            "page-lifecycle.js 仍含 confirmLeavingScanner shim — T5.1 Scanner 接入後應刪除"


class TestEventSourceTracking:
    """T4.1 守衛 — 所有 EventSource 建立都透過 _trackConnection 包裝"""

    def test_event_source_tracking_js_contains(self):
        """base.js / search-flow.js / file-list.js 含 T4.1 連線追蹤必要字串"""
        base = (PROJECT_ROOT / "web/static/js/pages/search/state/base.js").read_text(encoding='utf-8')
        assert '_activeConnections' in base, \
            "base.js missing: '_activeConnections'"
        sf = (PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js").read_text(encoding='utf-8')
        for expected in ['_trackConnection', '_untrackConnection', '_closeAllConnections',
                         '_trackConnection(new EventSource(', '_closeAllConnections()']:
            assert expected in sf, f"search-flow.js missing: {expected!r}"
        fl = (PROJECT_ROOT / "web/static/js/pages/search/state/file-list.js").read_text(encoding='utf-8')
        assert '_trackConnection(' in fl, \
            "file-list.js missing: '_trackConnection('"

    def test_no_bare_new_event_source_in_search_state(self):
        """search/state/ 下所有 JS 的 new EventSource 都應在 _trackConnection 內"""
        state_dir = PROJECT_ROOT / "web/static/js/pages/search/state"
        violations = []
        for js_file in state_dir.glob("*.js"):
            content = js_file.read_text(encoding='utf-8')
            for i, line in enumerate(content.splitlines(), 1):
                if 'new EventSource(' in line and '_trackConnection' not in line:
                    violations.append(f"{js_file.name}:{i} — {line.strip()[:80]}")
        assert len(violations) == 0, (
            f"發現 {len(violations)} 個 bare new EventSource（未包在 _trackConnection 內）:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestTimerTracking:
    """T4.2 守衛 — 所有 setTimeout 都透過 _timers registry 管理"""

    def test_timer_tracking_js_contains(self):
        """base/search-flow/result-card/persistence/file-list: _timers registry 必要字串"""
        base = (PROJECT_ROOT / "web/static/js/pages/search/state/base.js").read_text(encoding='utf-8')
        assert '_timers: {}' in base, "base.js missing: '_timers: {}'"
        sf = (PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js").read_text(encoding='utf-8')
        for expected in ['_setTimer(', '_clearAllTimers(', '_clearAllTimers()']:
            assert expected in sf, f"search-flow.js missing: {expected!r}"
        rc = (PROJECT_ROOT / "web/static/js/pages/search/state/result-card.js").read_text(encoding='utf-8')
        assert "_setTimer('toast'" in rc, "result-card.js missing: \"_setTimer('toast'\""
        ps = (PROJECT_ROOT / "web/static/js/pages/search/state/persistence.js").read_text(encoding='utf-8')
        assert "_setTimer('autosave'" in ps, "persistence.js missing: \"_setTimer('autosave'\""
        fl = (PROJECT_ROOT / "web/static/js/pages/search/state/file-list.js").read_text(encoding='utf-8')
        assert "_setTimer('loadFavorite'" in fl, "file-list.js missing: \"_setTimer('loadFavorite'\""

    def test_timer_tracking_js_excludes(self):
        """base/result-card/persistence: 舊 _toastTimer / saveTimeout 已移除"""
        base = (PROJECT_ROOT / "web/static/js/pages/search/state/base.js").read_text(encoding='utf-8')
        assert '_toastTimer: null' not in base, \
            "base.js should not contain: '_toastTimer: null'"
        rc = (PROJECT_ROOT / "web/static/js/pages/search/state/result-card.js").read_text(encoding='utf-8')
        assert '_toastTimer =' not in rc, \
            "result-card.js should not contain: '_toastTimer ='"
        ps = (PROJECT_ROOT / "web/static/js/pages/search/state/persistence.js").read_text(encoding='utf-8')
        assert 'saveTimeout' not in ps, \
            "persistence.js should not contain: 'saveTimeout'"


class TestWindowGlobalCleanup:
    """T3.3 守衛 — bridge.js 不再設定多餘的 window.xxx 全域函數"""

    BRIDGE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/bridge.js"
    FILE_LIST_JS = PROJECT_ROOT / "web/static/js/pages/search/state/file-list.js"
    PERSISTENCE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/persistence.js"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"
    INIT_JS = PROJECT_ROOT / "web/static/js/pages/search/init.js"

    def test_window_global_cleanup_js_contains_and_excludes(self):
        """bridge/file-list/persistence/search-flow/init: window.SearchCore 全域函數已清除，this.xxx 直接呼叫已植入"""
        # bridge.js（T4 已刪除則通過）
        if self.BRIDGE_JS.exists():
            bc = self.BRIDGE_JS.read_text(encoding='utf-8')
            for forbidden in [
                'window.translateWithAI', 'window.startEditTitle', 'window.confirmEditTitle',
                'window.cancelEditTitle', 'window.startEditChineseTitle',
                'window.confirmEditChineseTitle', 'window.cancelEditChineseTitle',
                'window.showAddTagInput', 'window.confirmAddTag', 'window.cancelAddTag',
                'window.removeUserTag', 'window.SearchCore.initProgress',
                'window.SearchCore.updateLog', 'window.SearchCore.handleSearchStatus',
            ]:
                assert forbidden not in bc, \
                    f"bridge.js should not contain: {forbidden!r}"
        # file-list.js: direct this.xxx calls + no window.SearchCore calls
        fl = self.FILE_LIST_JS.read_text(encoding='utf-8')
        for expected in ['this.initProgress(', 'this.updateLog(', 'this.handleSearchStatus(']:
            assert expected in fl, f"file-list.js missing: {expected!r}"
        for forbidden in ['window.SearchCore.initProgress', 'window.SearchCore.updateLog',
                          'window.SearchCore.handleSearchStatus', 'window.SearchCore.updateClearButton']:
            assert forbidden not in fl, f"file-list.js should not contain: {forbidden!r}"
        # persistence / search-flow: no updateClearButton
        for js_file in [self.PERSISTENCE_JS, self.SEARCH_FLOW_JS]:
            content = js_file.read_text(encoding='utf-8')
            assert 'window.SearchCore.updateClearButton' not in content, \
                f"{js_file.name} should not contain: 'window.SearchCore.updateClearButton'"
        # init.js（T4 已刪除則通過）
        if self.INIT_JS.exists():
            ic = self.INIT_JS.read_text(encoding='utf-8')
            for forbidden in ['window.SearchCore.initProgress =', 'window.SearchCore.updateLog =',
                              'window.SearchCore.handleSearchStatus =']:
                assert forbidden not in ic, \
                    f"init.js should not contain: {forbidden!r}"


class TestFetchAbortController:
    """T4.3 守衛 — fetch 可取消化（AbortController per-key）（method folded）"""
    BASE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/base.js"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"
    NAVIGATION_JS = PROJECT_ROOT / "web/static/js/pages/search/state/navigation.js"
    BATCH_JS = PROJECT_ROOT / "web/static/js/pages/search/state/batch.js"
    FILE_LIST_JS = PROJECT_ROOT / "web/static/js/pages/search/state/file-list.js"

    def test_abort_controller_js_contains(self):
        """base/search-flow: _abortControllers state + abort methods"""
        base = self.BASE_JS.read_text(encoding='utf-8')
        assert '_abortControllers: {}' in base, "base.js missing: '_abortControllers: {}'"
        sf = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        for expected in ["_getAbortSignal(", "_abortAllFetches(", "_abortAllFetches()"]:
            assert expected in sf, f"search-flow.js missing: {expected!r}"

    def test_abort_signal_usage_js_contains(self):
        """navigation/batch/file-list: signal 傳遞 + AbortError 處理"""
        nav = self.NAVIGATION_JS.read_text(encoding='utf-8')
        for expected in ["_getAbortSignal('loadMore')", "AbortError"]:
            assert expected in nav, f"navigation.js missing: {expected!r}"
        batch = self.BATCH_JS.read_text(encoding='utf-8')
        for expected in ["_getAbortSignal('translateAll')", "AbortError"]:
            assert expected in batch, f"batch.js missing: {expected!r}"
        fl = self.FILE_LIST_JS.read_text(encoding='utf-8')
        for expected in ["_getAbortSignal('setFileList')", "_getAbortSignal('loadFavorite')"]:
            assert expected in fl, f"file-list.js missing: {expected!r}"
        assert fl.count('AbortError') >= 2, \
            "file-list.js missing: 'AbortError' × 2"

class TestStreamState:
    """T4 Frontend State + Skeleton Grid 靜態守衛測試

    確認 SSE stream state 的 contract 存在：
    - base.js 宣告 stream state 欄位
    - search-flow.js 處理三種 SSE 事件類型
    - search.html 包含 skeleton template 綁定
    - failed slot 使用 visibility 而非 x-show（C10 約束）
    - search.css 包含 skeleton 動畫樣式
    """

    BASE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/base.js"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"
    SEARCH_HTML = PROJECT_ROOT / "web/templates/search.html"
    SEARCH_CSS = PROJECT_ROOT / "web/static/css/pages/search.css"

    def test_base_js_core_stream_state(self):
        """base.js 宣告核心 stream state 欄位"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        assert 'streamSlots' in content, "缺少 streamSlots 宣告"
        assert 'streamComplete' in content, "缺少 streamComplete 宣告"
        assert 'isStreaming' in content, "缺少 isStreaming 宣告"

    def test_base_js_staging_buffer_state(self):
        """base.js 宣告 U2 staging buffer state 欄位"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        assert 'streamBuffer' in content, "缺少 streamBuffer 宣告"
        assert 'streamBurstTimer' in content, "缺少 streamBurstTimer 宣告"
        assert 'streamBurstedSlots' in content, "缺少 streamBurstedSlots 宣告"
        assert 'stagingVisible' in content, "缺少 stagingVisible 宣告"

    def test_base_js_staging_display_state(self):
        """base.js 宣告 U3 staging display state 欄位，並確保已移除 streamFilled"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        assert 'streamFilled' not in content, "仍含 streamFilled — 應已移除"
        assert 'stagingCover' in content, "缺少 stagingCover 宣告"
        assert 'stagingNumber' in content, "缺少 stagingNumber 宣告"
        assert 'stagingReceivedCount' in content, "缺少 stagingReceivedCount 宣告"

    def test_result_item_uses_stream_buffer(self):
        """result-item handler 推入 streamBuffer，不直接更新 searchResults（U2 batching 約束）；U3 新增 staging state 更新"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        assert 'streamBuffer' in content, \
            "search-flow.js 缺少 streamBuffer 引用 — U2 batching 邏輯"
        assert 'streamBurstTimer' in content, \
            "search-flow.js 缺少 streamBurstTimer 引用 — U2 時間窗口 timer"
        # U3: result-item handler 更新 staging state
        assert 'stagingCover' in content, \
            "search-flow.js 缺少 stagingCover 引用 — U3 result-item handler 更新 staging display state"
        assert 'stagingNumber' in content, \
            "search-flow.js 缺少 stagingNumber 引用 — U3 result-item handler 更新 staging display state"

    def test_search_flow_handles_seed_event(self):
        """search-flow.js 包含 seed、result-item、result-complete 三種 SSE 事件 handler"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        assert "data.type === 'seed'" in content, \
            "search-flow.js 缺少 data.type === 'seed' handler — T4 SSE protocol"
        assert "data.type === 'result-item'" in content, \
            "search-flow.js 缺少 data.type === 'result-item' handler — T4 SSE protocol"
        assert "data.type === 'result-complete'" in content, \
            "search-flow.js 缺少 data.type === 'result-complete' handler — T4 SSE protocol"

    def test_search_html_has_skeleton_template(self):
        """search.html 包含 :data-slot 屬性、_skeleton class 綁定、_failed 相關綁定"""
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        assert ':data-slot' in content, \
            "search.html 缺少 :data-slot 屬性綁定 — T4 skeleton grid slot 識別"
        assert '_skeleton' in content, \
            "search.html 缺少 _skeleton class 綁定 — T4 skeleton grid 視覺"
        assert '_failed' in content, \
            "search.html 缺少 _failed 相關綁定 — T4 failed slot 視覺"

    def test_failed_slot_uses_display_none(self):
        """failed slot 使用 display: none 隱藏（C29 約束：_failed slot 完全移除佈局空間）"""
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        assert 'display: none' in content or 'display:none' in content, \
            ("search.html 缺少 display: none — "
             "C29 約束：_failed slot 必須用 display: none 完全隱藏")
        assert 'visibility: hidden' not in content and 'visibility:hidden' not in content, \
            ("search.html 仍包含 visibility: hidden — "
             "C29 約束：已改用 display: none，不應殘留 visibility: hidden")

    def test_search_css_has_skeleton_styles(self):
        """search.css 包含 .skeleton-cover class、.shimmer class、@keyframes shimmer"""
        content = self.SEARCH_CSS.read_text(encoding='utf-8')
        assert '.skeleton-cover' in content, \
            "search.css 缺少 .skeleton-cover class — T4 skeleton overlay 樣式"
        assert '.shimmer' in content, \
            "search.css 缺少 .shimmer class — T4 shimmer 動畫樣式"
        assert '@keyframes shimmer' in content, \
            "search.css 缺少 @keyframes shimmer — T4 shimmer 動畫定義"

    def test_search_flow_has_stream_guard(self):
        """search-flow.js 的 result handler 包含 streamComplete guard（C12 約束）"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        assert 'this.streamComplete' in content, \
            "search-flow.js 缺少 streamComplete guard — T4 防止漸進路徑 result 覆蓋 searchResults"


class TestAnimationHookup:
    """T5 Frontend Animation Hookup 靜態守衛

    確認 animations.js 載入順序、SearchAnimations window 物件、
    動畫觸發 wiring 合約存在。
    """

    SEARCH_HTML = PROJECT_ROOT / "web/templates/search.html"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"
    ANIMATIONS_JS = PROJECT_ROOT / "web/static/js/pages/search/animations.js"
    SEARCH_CSS = PROJECT_ROOT / "web/static/css/pages/search.css"

    def test_animations_js_exists(self):
        """search/animations.js 必須存在"""
        assert self.ANIMATIONS_JS.exists(), \
            "web/static/js/pages/search/animations.js 不存在 — T5 必須新建此檔案"

    def test_animations_js_exposes_window_object(self):
        """animations.js 暴露 window.SearchAnimations 物件"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'window.SearchAnimations' in content, \
            "animations.js 缺少 window.SearchAnimations — 必須掛 window 物件供 search-flow.js 呼叫"

    def test_animations_js_loaded_before_state_modules(self):
        """animations.js script tag 在 core.js 之前（search.html 載入順序）"""
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        anim_pos = content.find('animations.js')
        core_pos = content.find('search/core.js')
        assert anim_pos != -1, \
            "search.html 缺少 animations.js script tag"
        assert core_pos != -1, \
            "search.html 缺少 search/core.js script tag（預期已存在）"
        assert anim_pos < core_pos, \
            ("animations.js 必須在 core.js 之前載入 — "
             "確保 window.SearchAnimations 在 SearchCore 執行前已掛上")

    def test_search_flow_has_animation_trigger_in_result_item(self):
        """search-flow.js 包含 SearchAnimations 引用；U3 後 playMiniBurst 在 _flushStreamBuffer 呼叫"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        assert 'SearchAnimations' in content, \
            "search-flow.js 缺少 SearchAnimations 引用 — playGridFadeIn 仍在 seed handler 使用"
        # U3: playMiniBurst 已接入 _flushStreamBuffer，hook point 註解已移除
        assert 'playMiniBurst' in content, \
            "search-flow.js 缺少 playMiniBurst 引用 — U3 _flushStreamBuffer 應呼叫 playMiniBurst"

    def test_staging_card_html_exists(self):
        """search.html 包含 staging-anchor overlay（.staging-card、stagingVisible + displayMode guard、stagingCover、stagingNumber、stagingReceivedCount）"""
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        assert 'staging-anchor' in content, \
            "search.html 缺少 staging-anchor class — U3 staging overlay HTML"
        assert 'staging-card' in content, \
            "search.html 缺少 staging-card class — U3 staging card HTML"
        assert 'stagingVisible' in content, \
            "search.html 缺少 stagingVisible 綁定 — U3 staging card 可見性控制"
        assert "displayMode === 'grid'" in content, \
            "search.html staging x-show 缺少 displayMode === 'grid' guard — 切 detail view 時不該顯示 staging"
        assert 'stagingCover' in content, \
            "search.html 缺少 stagingCover 綁定 — U3 staging card 封面圖"
        assert 'stagingNumber' in content, \
            "search.html 缺少 stagingNumber 綁定 — U3 staging card 番號"
        assert 'stagingReceivedCount' in content, \
            "search.html 缺少 stagingReceivedCount 綁定 — U3 staging card 計數 badge"

    def test_staging_card_css_exists(self):
        """search.css 包含 staging card CSS（.staging-anchor、.staging-counter-badge）"""
        content = self.SEARCH_CSS.read_text(encoding='utf-8')
        assert '.staging-anchor' in content, \
            "search.css 缺少 .staging-anchor class — U3 staging overlay 容器樣式"
        assert '.staging-counter-badge' in content, \
            "search.css 缺少 .staging-counter-badge class — U3 計數 badge 樣式"

    def test_animations_js_has_play_mini_burst(self):
        """animations.js 包含 playMiniBurst 方法（U3 mini-burst 動畫）"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'playMiniBurst' in content, \
            "animations.js 缺少 playMiniBurst — U3 必須新增此方法（gsap.fromTo 偏移飛行）"

    def test_animations_js_has_staging_animations(self):
        """animations.js 包含 playStagingEntry、playStagingExit、playCoverSwap 方法"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'playStagingEntry' in content, \
            "animations.js 缺少 playStagingEntry — U3 staging card 進場 morph"
        assert 'playStagingExit' in content, \
            "animations.js 缺少 playStagingExit — U3 staging card 退場 morph + onComplete"
        assert 'playCoverSwap' in content, \
            "animations.js 缺少 playCoverSwap — U3 staging card 封面替換動畫"

    def test_flush_triggers_animation(self):
        """search-flow.js 的 _flushStreamBuffer 包含 playMiniBurst 引用（U3 接 mini-burst 動畫）"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        assert '_flushStreamBuffer' in content, \
            "search-flow.js 缺少 _flushStreamBuffer 方法 — U2/U3 batching 核心函數"
        assert 'playMiniBurst' in content, \
            "search-flow.js 缺少 playMiniBurst 呼叫 — U3 _flushStreamBuffer 必須觸發 mini-burst 動畫"

    def test_animations_js_has_reduced_motion_guard(self):
        """animations.js 檢查 prefersReducedMotion（Reduced Motion 降級）"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'prefersReducedMotion' in content, \
            "animations.js 缺少 prefersReducedMotion 守衛 — Reduced Motion 時必須跳過動畫"

    # ===== U4: Detail Entry + Grid-Detail Ghost Transition Guards =====

    GRID_MODE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/grid-mode.js"

    def test_animations_js_has_detail_entry(self):
        """animations.js 包含 playDetailEntry 方法"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'playDetailEntry' in content, \
            "animations.js 缺少 playDetailEntry — U4 detail entry 動畫（cover slide-in + info fade-in）"

    def test_animations_js_has_grid_to_detail(self):
        """animations.js 包含 playGridToDetail 方法"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'playGridToDetail' in content, \
            "animations.js 缺少 playGridToDetail — U4 Grid->Detail ghost 轉場動畫"

    def test_animations_js_has_detail_to_grid(self):
        """animations.js 包含 playDetailToGrid 方法"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'playDetailToGrid' in content, \
            "animations.js 缺少 playDetailToGrid — U4 Detail->Grid ghost 飛回動畫"

    def test_grid_mode_switch_to_detail_has_animation(self):
        """grid-mode.js switchToDetail 接入 ghost transition"""
        content = self.GRID_MODE_JS.read_text(encoding='utf-8')
        assert 'SearchAnimations' in content, \
            "grid-mode.js 缺少 SearchAnimations 引用 — switchToDetail 應接入 ghost 轉場"
        assert 'getBoundingClientRect' in content, \
            "grid-mode.js 缺少 getBoundingClientRect — C17 step 1 capture rect"
        assert '$nextTick' in content, \
            "grid-mode.js 缺少 $nextTick — C17 step 3 animate after render"

    def test_grid_mode_toggle_has_animation(self):
        """grid-mode.js toggleDisplayMode 接入 ghost fly-back"""
        content = self.GRID_MODE_JS.read_text(encoding='utf-8')
        assert 'playDetailToGrid' in content, \
            "grid-mode.js 缺少 playDetailToGrid — toggleDisplayMode Detail->Grid 應觸發 ghost 飛回"

    def test_search_flow_exact_result_has_detail_entry(self):
        """search-flow.js exact result 觸發 detail entry 動畫"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        assert 'playDetailEntry' in content, \
            "search-flow.js 缺少 playDetailEntry — exact result 應觸發 detail entry 動畫"

    def test_animations_js_has_ghost_cleanup(self):
        """animations.js 包含 ghost 清除邏輯"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'data-search-ghost' in content, \
            "animations.js 缺少 data-search-ghost attribute — ghost 元素需可識別以便清除"
        assert 'remove()' in content or 'removeChild' in content, \
            "animations.js 缺少 ghost 清除呼叫 — ghost 元素必須在動畫完成後移除"

    # ===== U5: Detail Navigation Slide + Interrupt Guards =====

    NAVIGATION_JS = PROJECT_ROOT / "web/static/js/pages/search/state/navigation.js"

    def test_animations_js_has_slide_in(self):
        """animations.js 包含 playSlideIn 方法（U5 導航滑動動畫）"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'playSlideIn' in content, \
            "animations.js 缺少 playSlideIn — U5 detail 導航滑動動畫"

    def test_navigation_has_kill_tweens(self):
        """navigation.js 包含 killTweensOf（C18 interrupt 策略）"""
        content = self.NAVIGATION_JS.read_text(encoding='utf-8')
        assert 'killTweensOf' in content, \
            "navigation.js 缺少 killTweensOf — C18 interrupt 策略需在導航時打斷舊動畫"

    def test_navigation_has_slide_animation(self):
        """navigation.js 接入 SearchAnimations slide 動畫"""
        content = self.NAVIGATION_JS.read_text(encoding='utf-8')
        assert 'SearchAnimations' in content, \
            "navigation.js 缺少 SearchAnimations 引用 — navigate() 應接入 slide 動畫"
        assert 'playSlideIn' in content, \
            "navigation.js 缺少 playSlideIn 引用 — navigate() 應觸發 slide-in 動畫"

    # ===== U6: Integration + Cleanup Guards =====

    def test_no_css_fadein_keyframes(self):
        """search.css 不應包含 @keyframes fadeIn（已由 GSAP playDetailEntry 取代）"""
        content = self.SEARCH_CSS.read_text(encoding='utf-8')
        assert '@keyframes fadeIn' not in content, \
            "search.css 仍包含 @keyframes fadeIn — U6 應移除（GSAP playDetailEntry 已取代此 CSS 動畫）"

    def test_no_play_card_stream_in_in_search_animations(self):
        """animations.js 不應包含 playCardStreamIn（已由 playMiniBurst 取代）"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert 'playCardStreamIn' not in content, \
            "animations.js 仍包含 playCardStreamIn — U3 已由 playMiniBurst 取代，不應存在"

    def test_all_animation_methods_consolidated(self):
        """animations.js 包含所有 9 個預期動畫方法（U3/U4/U5 合併驗證）"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        expected_methods = [
            'playMiniBurst',
            'playCoverSwap',
            'playStagingEntry',
            'playStagingExit',
            'playGridFadeIn',
            'playDetailEntry',
            'playGridToDetail',
            'playDetailToGrid',
            'playSlideIn',
        ]
        for method in expected_methods:
            assert method in content, \
                f"animations.js 缺少 {method} — 預期 9 個動畫方法全部存在"

    # ===== U7a: File Search Detail Entry Guard =====

    FILE_LIST_JS = PROJECT_ROOT / "web/static/js/pages/search/state/file-list.js"

    def test_file_search_result_has_detail_entry(self):
        """U7a: file-list.js searchForFile() result triggers playDetailEntry"""
        content = self.FILE_LIST_JS.read_text(encoding="utf-8")
        assert "playDetailEntry" in content, (
            "file-list.js must call playDetailEntry for file search results (U7a)"
        )

    # ===== U7b: File Switch Cached Slide Guards =====

    def test_file_switch_cached_has_slide(self):
        """U7b: file-list.js switchToFile() cached path triggers playSlideIn"""
        content = self.FILE_LIST_JS.read_text(encoding="utf-8")
        assert "playSlideIn" in content, (
            "file-list.js must call playSlideIn for cached file switch (U7b)"
        )

    def test_file_switch_has_kill_tweens(self):
        """U7b: file-list.js switchToFile() cached path interrupts old animation"""
        content = self.FILE_LIST_JS.read_text(encoding="utf-8")
        assert "killTweensOf" in content, (
            "file-list.js must call killTweensOf for C18 interrupt in file switch (U7b)"
        )

    def test_play_slide_in_kills_child_tweens(self):
        """Codex review: playSlideIn must kill child element tweens (cover/info) not just container"""
        content = self.ANIMATIONS_JS.read_text(encoding="utf-8")
        # Find the playSlideIn function definition (not the comment reference)
        slide_in_start = content.find('playSlideIn: function')
        assert slide_in_start != -1, "playSlideIn function definition not found in animations.js"
        # Check that it references child selectors for kill
        slide_in_body = content[slide_in_start:slide_in_start + 800]
        assert 'av-card-full-cover' in slide_in_body, (
            "playSlideIn must kill .av-card-full-cover child tweens (Codex review fix)"
        )
        assert 'av-card-full-info' in slide_in_body, (
            "playSlideIn must kill .av-card-full-info child tweens (Codex review fix)"
        )


class TestCoverStateGuard:
    """U8a Cover State 集中管理守衛

    確認 base.js 有 _resetCoverState helper + state fields，
    search-flow.js 有 _clearTimer method。
    """

    BASE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/base.js"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"

    def test_base_has_reset_cover_state(self):
        """base.js 包含 _resetCoverState 定義"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        assert '_resetCoverState' in content, \
            "base.js 缺少 _resetCoverState — U8a 必須新增集中式 cover state reset helper"

    def test_reset_cover_state_increments_request_id(self):
        """base.js 的 _resetCoverState 包含 _coverRequestId++"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        # 確認 _resetCoverState 方法體內有 _coverRequestId++
        match = re.search(r'_resetCoverState\s*\(', content)
        assert match, "base.js 缺少 _resetCoverState 方法定義"
        method_body = content[match.start():match.start() + 500]
        assert '_coverRequestId++' in method_body, \
            "base.js _resetCoverState 缺少 _coverRequestId++ — 必須遞增 request ID"

    def test_reset_cover_state_calls_clear_timer(self):
        """base.js 的 _resetCoverState 包含 _clearTimer + coverRetry"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        match = re.search(r'_resetCoverState\s*\(', content)
        assert match, "base.js 缺少 _resetCoverState 方法定義"
        method_body = content[match.start():match.start() + 500]
        assert '_clearTimer' in method_body, \
            "base.js _resetCoverState 缺少 _clearTimer 呼叫 — 必須清除 coverRetry timer"
        assert 'coverRetry' in method_body, \
            "base.js _resetCoverState 缺少 coverRetry 參數 — _clearTimer 需指定 key"

    def test_search_flow_has_clear_timer_method(self):
        """search-flow.js 包含 _clearTimer method 定義"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        assert re.search(r'_clearTimer\s*\(\s*\w+\s*\)', content), \
            "search-flow.js 缺少 _clearTimer(key) 方法定義 — U8a 必須新增單一 timer 清除方法"

    def test_base_has_cover_request_id_field(self):
        """base.js 包含 _coverRequestId 初始值"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        assert re.search(r'_coverRequestId\s*:\s*0', content), \
            "base.js 缺少 _coverRequestId: 0 初始值 — U8a 必須新增 cover request ID 欄位"

    def test_base_has_cover_loaded_field(self):
        """base.js 包含 _coverLoaded 初始值"""
        content = self.BASE_JS.read_text(encoding='utf-8')
        assert re.search(r'_coverLoaded\s*:\s*false', content), \
            "base.js 缺少 _coverLoaded: false 初始值 — U8a 必須新增 cover loaded 欄位"

    # === U8b guard tests ===

    FILE_LIST_JS = PROJECT_ROOT / "web/static/js/pages/search/state/file-list.js"
    NAVIGATION_JS = PROJECT_ROOT / "web/static/js/pages/search/state/navigation.js"
    GRID_MODE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/grid-mode.js"
    BATCH_JS = PROJECT_ROOT / "web/static/js/pages/search/state/batch.js"
    PERSISTENCE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/persistence.js"

    def test_file_list_reset_cover_state_count(self):
        """file-list.js 包含至少 8 次 _resetCoverState 呼叫"""
        content = self.FILE_LIST_JS.read_text(encoding='utf-8')
        count = content.count('_resetCoverState')
        assert count >= 8, (
            f"file-list.js 只有 {count} 次 _resetCoverState（需至少 8 次: "
            f"#4,#5,#6,#7,#8,#9,#10,#11）"
        )

    def test_navigation_reset_cover_state_count(self):
        """navigation.js 包含至少 2 次 _resetCoverState 呼叫"""
        content = self.NAVIGATION_JS.read_text(encoding='utf-8')
        count = content.count('_resetCoverState')
        assert count >= 2, (
            f"navigation.js 只有 {count} 次 _resetCoverState（需至少 2 次: "
            f"#1 navigate, #15 loadMore）"
        )

    def test_search_flow_reset_cover_state_count(self):
        """search-flow.js 包含至少 4 次 _resetCoverState 呼叫"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        count = content.count('_resetCoverState')
        assert count >= 4, (
            f"search-flow.js 只有 {count} 次 _resetCoverState（需至少 4 次: "
            f"#12 doSearch init, #13 traditional result, #14 fallback result, fallbackSearch）"
        )

    def test_no_bare_cover_error_reset(self):
        """file-list/navigation/search-flow 中不應有裸 coverError = '' 純 reset 行"""
        files_to_check = [self.FILE_LIST_JS, self.NAVIGATION_JS, self.SEARCH_FLOW_JS]
        violations = []
        for fpath in files_to_check:
            content = fpath.read_text(encoding='utf-8')
            for i, line in enumerate(content.splitlines(), 1):
                # 匹配 coverError = '' 或 coverError = "" (純 reset，非 set error)
                if re.search(r"""coverError\s*=\s*['"](['"])\s*;""", line):
                    # 排除 _resetCoverState 方法定義本身
                    if '_resetCoverState' in line:
                        continue
                    violations.append(f"{fpath.name}:{i} — {line.strip()}")
        assert len(violations) == 0, (
            f"發現 {len(violations)} 個裸 coverError = '' reset（應改用 _resetCoverState()）:\n" +
            "\n".join(f"  - {v}" for v in violations)
        )

    def test_grid_mode_reset_cover_state(self):
        """grid-mode.js 包含至少 1 次 _resetCoverState 呼叫"""
        content = self.GRID_MODE_JS.read_text(encoding='utf-8')
        count = content.count('_resetCoverState')
        assert count >= 1, (
            f"grid-mode.js 缺少 _resetCoverState（需至少 1 次: #16 switchToDetail）"
        )

    def test_batch_reset_cover_state(self):
        """batch.js 包含至少 1 次 _resetCoverState 呼叫"""
        content = self.BATCH_JS.read_text(encoding='utf-8')
        count = content.count('_resetCoverState')
        assert count >= 1, (
            f"batch.js 缺少 _resetCoverState（需至少 1 次: #17 scrapeAll）"
        )

    def test_persistence_reset_cover_state(self):
        """persistence.js 包含至少 1 次 _resetCoverState 呼叫"""
        content = self.PERSISTENCE_JS.read_text(encoding='utf-8')
        count = content.count('_resetCoverState')
        assert count >= 1, (
            f"persistence.js 缺少 _resetCoverState（需至少 1 次: #19 restoreState）"
        )

    # === U8c guard tests ===

    RESULT_CARD_JS = PROJECT_ROOT / "web/static/js/pages/search/state/result-card.js"

    def test_cover_error_has_get_attribute_guard(self):
        """result-card.js 的 handleCoverError 內含 getAttribute"""
        content = self.RESULT_CARD_JS.read_text(encoding='utf-8')
        match = re.search(r'handleCoverError\s*\(', content)
        assert match, "result-card.js 缺少 handleCoverError 方法定義"
        method_body = content[match.start():match.start() + 800]
        assert 'getAttribute' in method_body, \
            "handleCoverError 缺少 getAttribute — Phase 1 stale guard 必須用 getAttribute('src') 比對"

    def test_cover_error_has_cover_url_comparison(self):
        """result-card.js 的 handleCoverError 內含 coverUrl"""
        content = self.RESULT_CARD_JS.read_text(encoding='utf-8')
        match = re.search(r'handleCoverError\s*\(', content)
        assert match, "result-card.js 缺少 handleCoverError 方法定義"
        method_body = content[match.start():match.start() + 800]
        assert 'coverUrl' in method_body, \
            "handleCoverError 缺少 coverUrl — Phase 1 stale guard 必須與 coverUrl() 比對"

    def test_cover_error_has_request_id_guard(self):
        """result-card.js 的 handleCoverError 內含 _coverRequestId"""
        content = self.RESULT_CARD_JS.read_text(encoding='utf-8')
        match = re.search(r'handleCoverError\s*\(', content)
        assert match, "result-card.js 缺少 handleCoverError 方法定義"
        method_body = content[match.start():match.start() + 800]
        assert '_coverRequestId' in method_body, \
            "handleCoverError 缺少 _coverRequestId — Phase 2 timer 競態守衛必須檢查 request ID"

    def test_cover_retry_uses_set_timer(self):
        """result-card.js 內含 _setTimer + coverRetry"""
        content = self.RESULT_CARD_JS.read_text(encoding='utf-8')
        assert '_setTimer' in content, \
            "result-card.js 缺少 _setTimer — cover retry 必須使用 _setTimer 而非 raw setTimeout"
        assert 'coverRetry' in content, \
            "result-card.js 缺少 coverRetry — _setTimer 必須使用 'coverRetry' key"

    # === U8d guard tests ===

    SEARCH_HTML = PROJECT_ROOT / "web/templates/search.html"
    SEARCH_CSS = PROJECT_ROOT / "web/static/css/pages/search.css"

    def test_load_handler_sets_cover_loaded(self):
        """search.html 的 @load handler 包含 _coverLoaded = true"""
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        assert '_coverLoaded = true' in content, \
            "search.html 缺少 _coverLoaded = true — U8d 必須在 cover img @load handler 設定 _coverLoaded"

    def test_shimmer_placeholder_in_html(self):
        """search.html 包含 cover-loading-placeholder"""
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        assert 'cover-loading-placeholder' in content, \
            "search.html 缺少 cover-loading-placeholder — U8d 必須新增 shimmer loading placeholder"

    def test_shimmer_placeholder_in_css(self):
        """search.css 包含 cover-loading-placeholder 樣式"""
        content = self.SEARCH_CSS.read_text(encoding='utf-8')
        assert 'cover-loading-placeholder' in content, \
            "search.css 缺少 cover-loading-placeholder — U8d 必須新增 shimmer placeholder 樣式"

    # === U8 Codex review fix guard tests ===

    UI_JS = PROJECT_ROOT / "web/static/js/pages/search/ui.js"

    def test_switch_source_reset_cover_state(self):
        """ui.js 的 switchSource 包含 _resetCoverState（#20 cover-changing path）"""
        content = self.UI_JS.read_text(encoding='utf-8')
        assert '_resetCoverState' in content, (
            "ui.js 缺少 _resetCoverState — switchSource 替換結果時必須重置 cover state（#20）"
        )

    def test_cover_error_guards_empty_cover_url(self):
        """result-card.js 的 handleCoverError 在 _coverRetried 之前有 coverUrl 空值 early return"""
        content = self.RESULT_CARD_JS.read_text(encoding='utf-8')
        match = re.search(r'handleCoverError\s*\(', content)
        assert match, "result-card.js 缺少 handleCoverError 方法定義"
        method_body = content[match.start():match.start() + 800]
        # coverUrl() 取值必須在 _coverRetried check 之前
        cover_url_pos = method_body.find('coverUrl')
        retried_pos = method_body.find('_coverRetried')
        assert cover_url_pos != -1, \
            "handleCoverError 缺少 coverUrl — 必須檢查空 coverUrl early return"
        assert retried_pos != -1, \
            "handleCoverError 缺少 _coverRetried"
        assert cover_url_pos < retried_pos, (
            "handleCoverError 的 coverUrl 檢查必須在 _coverRetried 之前 — "
            "空 coverUrl 時應直接 return，避免 stale @error 觸發錯誤的 retry"
        )


class TestSearchAllRaceGuard:
    """U10 guard: _searchFileBackground + searchAll 共享狀態競態保護"""

    FILE_LIST_JS = PROJECT_ROOT / "web/static/js/pages/search/state/file-list.js"
    BATCH_JS = PROJECT_ROOT / "web/static/js/pages/search/state/batch.js"

    def test_search_file_background_exists(self):
        """file-list.js 必須包含 _searchFileBackground 方法"""
        content = self.FILE_LIST_JS.read_text(encoding='utf-8')
        assert '_searchFileBackground' in content, \
            "file-list.js 缺少 _searchFileBackground — U10a 必須新增背景搜尋方法"

    def test_search_file_background_no_shared_state_writes(self):
        """_searchFileBackground 不應讀寫共享 UI 狀態（只能操作 file 物件）"""
        content = self.FILE_LIST_JS.read_text(encoding='utf-8')
        match = re.search(r'_searchFileBackground\s*\(', content)
        assert match, "file-list.js 缺少 _searchFileBackground 方法定義"
        method_body = content[match.start():match.start() + 2000]

        # 負面斷言：不應碰共享 UI 狀態
        assert 'this.currentFileIndex' not in method_body, \
            "_searchFileBackground 不應寫入 this.currentFileIndex — 背景搜尋不碰共享狀態"
        assert 'this.currentIndex' not in method_body, \
            "_searchFileBackground 不應寫入 this.currentIndex — 背景搜尋不碰共享狀態"
        assert 'this.displayMode' not in method_body, \
            "_searchFileBackground 不應寫入 this.displayMode — 背景搜尋不碰共享狀態"
        assert 'window.SearchUI.showState' not in method_body, \
            "_searchFileBackground 不應呼叫 window.SearchUI.showState — 背景搜尋不碰 UI"

        # 特殊處理：排除 file.searchResults 誤判
        assert 'this.searchResults' not in method_body, \
            "_searchFileBackground 不應讀寫 this.searchResults — 背景搜尋只能操作 file.searchResults"

        # 正面斷言：應操作 file 物件
        assert 'file.searchResults' in method_body, \
            "_searchFileBackground 必須寫入 file.searchResults — 結果存在 file 物件上"
        assert 'file.searched' in method_body, \
            "_searchFileBackground 必須寫入 file.searched — 標記搜尋完成"

    def test_search_all_uses_background_search(self):
        """batch.js 的 searchAll 必須使用 _searchFileBackground"""
        content = self.BATCH_JS.read_text(encoding='utf-8')
        assert '_searchFileBackground' in content, \
            "batch.js 缺少 _searchFileBackground 呼叫 — U10b searchAll 必須改用背景搜尋"

    def test_search_all_no_direct_switch_to_file_in_promise_all(self):
        """searchAll 的 Promise.all(chunk.map 區塊內不應直接呼叫 switchToFile"""
        content = self.BATCH_JS.read_text(encoding='utf-8')
        match = re.search(r'Promise\.all\(chunk\.map', content)
        assert match, "batch.js 缺少 Promise.all(chunk.map — searchAll 結構異常"
        # 取到 })); 的區塊（約 500 字元）
        block = content[match.start():match.start() + 500]
        # 找到 })); 結束位置，截斷
        end_marker = block.find('}));')
        if end_marker != -1:
            block = block[:end_marker + 3]
        assert 'switchToFile' not in block, (
            "searchAll 的 Promise.all(chunk.map) 內不應直接呼叫 switchToFile — "
            "背景搜尋期間切換檔案會造成 UI 競態"
        )

    def test_search_file_background_no_ui_side_effects(self):
        """_searchFileBackground 不應有 UI 副作用（switchToFile / showToast / alert）"""
        content = self.FILE_LIST_JS.read_text(encoding='utf-8')
        match = re.search(r'_searchFileBackground\s*\(', content)
        assert match, "file-list.js 缺少 _searchFileBackground 方法定義"
        method_body = content[match.start():match.start() + 2000]

        assert 'switchToFile(' not in method_body, \
            "_searchFileBackground 不應呼叫 switchToFile — 背景搜尋不切換 UI"
        assert 'showToast(' not in method_body, \
            "_searchFileBackground 不應呼叫 showToast — 背景搜尋不顯示 toast"
        assert 'alert(' not in method_body, \
            "_searchFileBackground 不應呼叫 alert — 背景搜尋不彈出對話框"

    def test_search_file_background_has_close_wrapper(self):
        """_searchFileBackground 必須有 close-wrapper（確保 forced-close 時 Promise settle）"""
        content = self.FILE_LIST_JS.read_text(encoding='utf-8')
        match = re.search(r'_searchFileBackground\s*\(', content)
        assert match, "file-list.js 缺少 _searchFileBackground 方法定義"
        method_body = content[match.start():match.start() + 2000]

        assert 'settle' in method_body, \
            "_searchFileBackground 缺少 settle 函數 — 必須包裝 close 確保 Promise 可 resolve"
        assert 'originalClose' in method_body, \
            "_searchFileBackground 缺少 originalClose — 必須保存原始 close 再覆寫"


class TestFailedSlotC30Guard:
    """C30 guard: _failed slot 必須從導航、計數、lightbox 中排除

    確認各 JS 方法在計算 navigation、indicator、file count 時
    正確排除 _failed slot，避免用戶看到空白結果或導航到失敗項目。
    """

    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    NAVIGATION_JS = PROJECT_ROOT / "web/static/js/pages/search/state/navigation.js"
    GRID_MODE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/grid-mode.js"
    BASE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/base.js"
    SEARCH_HTML = PROJECT_ROOT / "web/templates/search.html"

    def test_failed_slot_method_bodies_contain_failed(self):
        """navigate/prevLightboxVideo/nextLightboxVideo/navIndicatorText/canGoPrev/canGoNext/showNavigation/fileCountText 方法體含 _failed (C30)"""
        nav_content = self.NAVIGATION_JS.read_text(encoding='utf-8')
        match = re.search(r'navigate\s*\(', nav_content)
        assert match, "navigation.js 缺少 navigate() 方法"
        assert '_failed' in nav_content[match.start():match.start() + 500], \
            "navigation.js navigate() missing: '_failed' skip 邏輯 (C30)"

        gm_content = self.GRID_MODE_JS.read_text(encoding='utf-8')
        for method_name in ['prevLightboxVideo', 'nextLightboxVideo']:
            m = re.search(rf'{method_name}\s*\(', gm_content)
            assert m, f"grid-mode.js 缺少 {method_name}() 方法"
            assert '_failed' in gm_content[m.start():m.start() + 800], \
                f"grid-mode.js {method_name}() missing: '_failed' skip 邏輯 (C30)"

        base_content = self.BASE_JS.read_text(encoding='utf-8')
        for method_name, window in [
            ('navIndicatorText', 500), ('canGoPrev', 300), ('canGoNext', 300),
            ('showNavigation', 300), ('fileCountText', 500),
        ]:
            m = re.search(rf'{method_name}\s*\(', base_content)
            assert m, f"base.js 缺少 {method_name}() 方法"
            assert '_failed' in base_content[m.start():m.start() + window], \
                f"base.js {method_name}() missing: '_failed' 排除邏輯 (C30)"

        search_html = self.SEARCH_HTML.read_text(encoding='utf-8')
        for expected in ['hasVisiblePrev()', 'hasVisibleNext()']:
            assert expected in search_html, f"search.html missing: {expected!r}"

    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"

    def test_repoint_is_conditional(self):
        """result-complete 的 currentIndex repoint 必須是條件式的：只在當前指向 _failed 時才 repoint (Codex review)"""
        content = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        idx = content.find('firstValid')
        assert idx != -1, "search-flow.js 缺少 firstValid repoint 邏輯"
        repoint_context = content[max(0, idx - 200):idx + 200]
        assert 'currentResult' in repoint_context or 'this.searchResults[this.currentIndex]' in repoint_context, \
            "repoint 必須先檢查當前 currentIndex 是否指向 _failed item，不可無條件覆蓋 (Codex review)"


class TestGridSettlePulse:
    """A4 守衛 — Grid Settle Pulse 落地

    確認 animations.js 暴露 playGridSettle 方法、search-flow.js 的
    onExitComplete 呼叫 playGridSettle、CustomEase "settle" 曲線已註冊、
    以及 C4/C6 約束遵守。
    """

    ANIMATIONS_JS = PROJECT_ROOT / "web/static/js/pages/search/animations.js"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"

    def test_grid_settle_pulse_animations_js_contains(self):
        """animations.js 含 playGridSettle + CustomEase.create("settle")"""
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        for expected in ['playGridSettle', 'CustomEase.create("settle"']:
            assert expected in content, f"animations.js missing: {expected!r}"

    def test_grid_settle_pulse_method_bodies(self):
        """search-flow._triggerStagingExit 含 playGridSettle；playGridSettle 方法體含 killTweensOf、不含 rotation"""
        sf = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        match = re.search(r'_triggerStagingExit\s*\(\s*\)\s*\{', sf)
        assert match, "search-flow.js 缺少 _triggerStagingExit 方法定義"
        assert 'playGridSettle' in sf[match.start():match.start() + 1000], \
            "search-flow.js _triggerStagingExit missing: 'playGridSettle'"

        anim = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        m = re.search(r'playGridSettle:\s*function', anim)
        assert m, "animations.js 缺少 playGridSettle 方法定義"
        body = anim[m.start():m.start() + 3000]
        assert 'killTweensOf' in body, "animations.js playGridSettle missing: 'killTweensOf'"
        code_only = '\n'.join(
            l for l in body.split('\n') if l.strip() and not l.strip().startswith('//')
        )
        assert 'rotation' not in code_only, \
            "animations.js playGridSettle should not contain: 'rotation' (C6)"


class TestHeroImageErrorGuard:
    """A6-1 Hero Card / Lightbox 圖片錯誤狀態管理守衛

    確認 Hero Card 和 Lightbox 的 @error handler 不直接修改 DOM，
    改用 Alpine state 管理錯誤狀態。
    """

    SEARCH_HTML = PROJECT_ROOT / "web/templates/search.html"
    BASE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/base.js"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"

    def test_hero_image_error_js_contains(self):
        """base.js 含 _heroCardImageError / _heroLightboxImageError；search-flow.js doSearch 重置兩者"""
        base = self.BASE_JS.read_text(encoding='utf-8')
        for expected in ['_heroCardImageError', '_heroLightboxImageError']:
            assert expected in base, f"base.js missing: {expected!r}"
        sf = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        m = re.search(r'async\s+doSearch', sf)
        assert m, "search-flow.js 缺少 doSearch 方法定義"
        body = sf[m.start():m.start() + 2000]
        for expected in ['_heroCardImageError', '_heroLightboxImageError']:
            assert expected in body and '= false' in body, \
                f"search-flow.js doSearch missing: '{expected} = false' reset"

    def test_hero_card_error_handler_excludes(self):
        """search.html hero-card @error 不含 target.src / .src = / onerror"""
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        match = re.search(r'class="[^"]*hero-card[^"]*"', content)
        assert match, "search.html 缺少 hero-card class 區塊"
        hero_block = content[match.start():match.start() + 1200]
        error_match = re.search(r'@error="([^"]*)"', hero_block)
        assert error_match, "hero-card 區塊缺少 @error handler"
        error_value = error_match.group(1)
        for forbidden in ['target.src', '.src =', 'onerror']:
            assert forbidden not in error_value, \
                f"hero-card @error should not contain: {forbidden!r} (A6-1)"


class TestLightboxModeNormalization:
    """A6-2 Lightbox 模式正規化 + restoreState 防護守衛

    確認 restoreState 後 lightbox 狀態被正規化，
    以及 openActressLightbox 有 actressProfile 存在性 guard。
    """

    PERSISTENCE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/persistence.js"
    GRID_MODE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/grid-mode.js"

    def test_lightbox_mode_normalization_contains(self):
        """persistence.js restoreState 重置 lightboxOpen+lightboxIndex；grid-mode.js openActressLightbox 含 actressProfile guard"""
        ps = self.PERSISTENCE_JS.read_text(encoding='utf-8')
        m = re.search(r'restoreState\s*\(\s*\)', ps)
        assert m, "persistence.js 缺少 restoreState 方法定義"
        body = ps[m.start():m.start() + 3000]
        assert 'lightboxOpen' in body and '= false' in body, \
            "persistence.js restoreState missing: 'lightboxOpen = false' (A6-2)"
        assert 'actressProfile' in body and 'lightboxIndex' in body, \
            "persistence.js restoreState missing: actressProfile + lightboxIndex 處理 (A6-2)"
        gm = self.GRID_MODE_JS.read_text(encoding='utf-8')
        m2 = re.search(r'openActressLightbox\s*\(\s*\)', gm)
        assert m2, "grid-mode.js 缺少 openActressLightbox 方法定義"
        head = gm[m2.start():m2.start() + 300]
        assert re.search(r'if\s*\(\s*!this\.actressProfile\s*\)\s*return', head), \
            "grid-mode.js openActressLightbox missing: actressProfile guard (A6-2)"


class TestHeroSlotReservation:
    """A7-Prod 守衛 — Hero Slot 一律預留落地

    確認 seed handler 設定 _heroSlotReserved、search.html Hero Card
    x-show 包含 _heroSlotReserved、animations.js 暴露 playHeroRemove、
    result-complete 不拆 placeholder、result handler 統一處理 _heroSlotReserved。
    """

    BASE_JS = PROJECT_ROOT / "web/static/js/pages/search/state/base.js"
    SEARCH_FLOW_JS = PROJECT_ROOT / "web/static/js/pages/search/state/search-flow.js"
    SEARCH_HTML = PROJECT_ROOT / "web/templates/search.html"
    ANIMATIONS_JS = PROJECT_ROOT / "web/static/js/pages/search/animations.js"

    def test_hero_slot_reservation_js_contains(self):
        """animations.js playHeroRemove；search.html hero-card 含 _heroSlotReserved；search-flow.js seed/fallback/result-complete 邏輯"""
        anim = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        assert re.search(r'playHeroRemove\s*:', anim), \
            "animations.js missing: 'playHeroRemove' method"
        html = self.SEARCH_HTML.read_text(encoding='utf-8')
        m = re.search(r'class="[^"]*hero-card[^"]*"', html)
        assert m, "search.html 缺少 hero-card class 區塊"
        assert '_heroSlotReserved' in html[max(0, m.start() - 200):m.start() + 200], \
            "search.html hero-card missing: '_heroSlotReserved' (A7-Prod)"
        sf = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        seed_m = re.search(r"data\.type\s*===?\s*['\"]seed['\"]", sf)
        assert seed_m, "search-flow.js 缺少 seed handler"
        assert '_heroSlotReserved' in sf[seed_m.start():seed_m.start() + 1000] and \
               '= true' in sf[seed_m.start():seed_m.start() + 1000], \
            "search-flow.js seed handler missing: '_heroSlotReserved = true'"
        rc_m = re.search(r"data\.type\s*===?\s*['\"]result-complete['\"]", sf)
        assert rc_m, "search-flow.js 缺少 result-complete handler"
        assert '_heroSlotReserved = false' not in sf[rc_m.start():rc_m.start() + 1500], \
            "search-flow.js result-complete should not contain: '_heroSlotReserved = false'"
        fb_m = re.search(r'async\s+fallbackSearch\s*\(', sf)
        assert fb_m, "search-flow.js 缺少 fallbackSearch 方法"
        fb_body = sf[fb_m.start():fb_m.start() + 3000]
        for expected in ['_heroSlotReserved', 'playHeroRemove']:
            assert expected in fb_body, f"search-flow.js fallbackSearch missing: {expected!r}"

    def test_result_event_hero_slot_handling(self):
        """search-flow.js result 事件三路徑（正常stream / allFailed+fallback / 全失敗無fallback）均處理 _heroSlotReserved"""
        sf = self.SEARCH_FLOW_JS.read_text(encoding='utf-8')
        for marker, window, expected in [
            ('正常 stream 完成', 2000, ['_heroSlotReserved', 'playHeroRemove']),
            ('Issue 1: Fallback', 2000, ['_heroSlotReserved']),
            ('全部失敗且無 fallback', 500, ['_heroSlotReserved']),
        ]:
            assert marker in sf, f"search-flow.js missing: comment marker {marker!r}"
            block = sf[sf.index(marker):sf.index(marker) + window]
            for expected_str in expected:
                assert expected_str in block, \
                    f"search-flow.js '{marker}' block missing: {expected_str!r}"


class TestShowcaseAnimationsGuard:
    """B5-B15/T20 守衛 — Showcase GSAP 基礎設施落地（method folded）"""

    ANIMATIONS_JS = PROJECT_ROOT / "web/static/js/pages/showcase/animations.js"
    SHOWCASE_HTML = PROJECT_ROOT / "web/templates/showcase.html"

    def _read_core_js(self):
        """合併讀取動畫相關的 ESM 模組（B6/B7/B8/B9/B13/B14/B15 守衛範圍）。"""
        return (
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-base.js").read_text(encoding='utf-8') + "\n" +
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-videos.js").read_text(encoding='utf-8') + "\n" +
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-lightbox.js").read_text(encoding='utf-8')
        )

    def test_animations_js_contains(self):
        """animations.js 存在且包含所有必要字串；theme.css 含 flip-guard 規則"""
        assert self.ANIMATIONS_JS.exists(), \
            f"animations.js missing: {self.ANIMATIONS_JS!r}"
        content = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        for expected in [
            # B5: IIFE + strict mode + global object
            "window.ShowcaseAnimations",
            "prefersReducedMotion",
            # B5: method stubs
            "playEntry", "playFlipReorder", "playFlipFilter",
            "captureFlipState", "capturePositions",
            "playModeCrossfade",
            # B5: plugin registration
            "registerPlugin(Flip)",
            "showcaseSettle",
            # B6: playEntry implementation
            "gsap.killTweensOf",
            "getBoundingClientRect",
            "gsap.set",
            # B7: captureFlipState + capturePositions
            "Flip.getState",
            ".av-card-preview",
            "data-flip-id",
            # B8: playFlipFilter
            "Flip.from",
            "onEnter",
            "onLeave",
            "clearProps",
            # B8: playFlipFilter returns tweens
            "return gsap.fromTo",
            "return gsap.to",
            # B12: playFlipReorder manual fromTo
            ".fromTo",
            # T20: killLightboxAnimations
            "killLightboxAnimations",
            "getById('showcaseLightboxOpen')",
            "getById('showcaseLightboxSwitch')",
            "typeof gsap",
        ]:
            assert expected in content, \
                f"animations.js missing: {expected!r}"
        # B10: playModeCrossfade not placeholder
        assert ("gsap.fromTo" in content or "tl.fromTo" in content), \
            "animations.js missing: playModeCrossfade fromTo call"
        # B5: strict mode (single or double quote variant)
        assert ("'use strict'" in content or '"\'use strict\""' in content), \
            "animations.js missing: \'use strict\' declaration"
        # B15: theme.css flip-guard rule
        theme_css = (PROJECT_ROOT / "web/static/css/theme.css").read_text(encoding='utf-8')
        for expected in ["flip-guard", "transform: none"]:
            assert expected in theme_css, \
                f"theme.css missing: {expected!r}"

    def test_showcase_html_contains(self):
        """showcase.html 包含 animations.js script tag + data-flip-id；不重複載入 Flip.min.js"""
        content = self.SHOWCASE_HTML.read_text(encoding='utf-8')
        for expected in ["animations.js", "data-flip-id"]:
            assert expected in content, \
                f"showcase.html missing: {expected!r}"
        assert "Flip.min.js" not in content, \
            "showcase.html should not contain: 'Flip.min.js'"

    def test_core_js_contains(self):
        """core.js (state-base/videos/lightbox) 包含所有動畫 method 及 guard 字串"""
        content = self._read_core_js()
        for expected in [
            # B6: playEntry call
            "playEntry",
            "ShowcaseAnimations",
            # B8: _animateFilter
            "_animateFilter",
            # B8: playFlipFilter call
            "playFlipFilter",
            # B9: _animatePageChange
            "_animatePageChange",
            "scrollTo(0, 0)",
            # B10: playModeCrossfade
            "playModeCrossfade",
            "ShowcaseAnimations?.playModeCrossfade?.(",
            # B12: capturePositions + playFlipReorder in sort helper
            "capturePositions",
            "playFlipReorder",
            # B12/B13: flip-guard management
            "flip-guard",
            # B13: generation token guards
            "_animGeneration",
            # B13: _sortWithFlip method
            "_sortWithFlip",
            # B15: captureFlipState in _animateFilter
            "captureFlipState",
            # B13: page change uses playEntry
            "playEntry",
            # B7: savedPage or equivalent in _sortWithFlip
            "updatePagination",
        ]:
            assert expected in content, \
                f"showcase/core.js missing: {expected!r}"
        # B7: page preservation in _sortWithFlip
        assert ("savedPage" in content or "saved_page" in content or "savePage" in content), \
            "showcase/core.js _sortWithFlip missing page preservation (savedPage/saved_page/savePage)"

    def test_core_js_prev_next_page_call_animate_page_change(self):
        """B9: core.js prevPage/nextPage 呼叫 _animatePageChange"""
        content = self._read_core_js()
        lines = content.split('\n')
        for method_name in ['prevPage', 'nextPage']:
            in_method = False
            method_lines = []
            brace_count = 0
            for line in lines:
                stripped = line.strip()
                if not in_method and method_name in stripped and '{' in stripped and stripped.endswith('{'):
                    in_method = True
                    brace_count = 0
                if in_method:
                    method_lines.append(line)
                    brace_count += line.count('{') - line.count('}')
                    if brace_count <= 0 and len(method_lines) > 1:
                        break
            method_body = '\n'.join(method_lines)
            assert '_animatePageChange' in method_body, (
                f"showcase/core.js {method_name} missing: '_animatePageChange'"
            )

    def test_core_js_no_direct_gsap_getById(self):
        """T20: core.js 不得在 _killLightboxTimelines 之外直接呼叫 gsap.getById"""
        import re
        content = self._read_core_js()
        func_start = content.find('function _killLightboxTimelines(')
        if func_start != -1:
            brace_start = content.index('{', func_start)
            depth = 0
            pos = brace_start
            while pos < len(content):
                if content[pos] == '{':
                    depth += 1
                elif content[pos] == '}':
                    depth -= 1
                    if depth == 0:
                        func_end = pos + 1
                        break
                pos += 1
            else:
                func_end = len(content)
            stripped = content[:func_start] + content[func_end:]
        else:
            stripped = content
        assert 'gsap.getById(' not in stripped, (
            "showcase/core.js 在 _killLightboxTimelines 之外仍有直接 gsap.getById( 呼叫 — "
            "T20 規定只有 _killLightboxTimelines fallback 可直接使用 gsap.getById"
        )

class TestMotionLabShowcase:
    """B11 守衛 — Motion Lab Showcase demo 完整性

    確認 Motion Lab 頁面包含 Showcase tab 及所有 demo 方法，
    涵蓋 B1-B4 在 Motion Lab 新增的功能。
    """

    MOTION_LAB_HTML = PROJECT_ROOT / "web/templates/motion_lab.html"
    MOTION_LAB_JS = PROJECT_ROOT / "web/static/js/pages/motion-lab.js"

    def test_motion_lab_html_contains(self):
        """motion_lab.html 含 showcase tab + Alpine 切換邏輯"""
        content = self.MOTION_LAB_HTML.read_text(encoding='utf-8')
        for expected in ["showcase", "tab === 'showcase'"]:
            assert expected in content, f"motion_lab.html missing: {expected!r}"

    def test_motion_lab_js_contains(self):
        """motion-lab.js 含 B1-B4 四個 Showcase demo 方法"""
        content = self.MOTION_LAB_JS.read_text(encoding='utf-8')
        for expected in ['playShowcaseEntry', 'playFlipReorder', 'playFlipFilter', 'playPageTransition']:
            assert expected in content, f"motion-lab.js missing: {expected!r}"


# ====================================================================
# D1 Guards: 錯誤訊息收斂 + console.log 清理
# ====================================================================

class TestSearchErrorMessageGuard:
    """D1 守衛：search 頁面 JS 的 alert / errorText 不可暴露 err.message 技術細節"""

    SEARCH_JS_DIR = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'search'

    def _collect_js_files(self):
        """收集 search 目錄下所有 .js 檔案（含子目錄）"""
        return list(self.SEARCH_JS_DIR.rglob('*.js'))

    @staticmethod
    def _is_console_or_throw(line: str) -> bool:
        """排除 console.error / console.warn / throw 中的合法使用"""
        stripped = line.strip()
        if stripped.startswith('console.error') or stripped.startswith('console.warn'):
            return True
        if stripped.startswith('throw '):
            return True
        # 也排除 JS 註解行
        if stripped.startswith('//'):
            return True
        return False

    def test_no_err_message_exposed_in_search_js(self):
        """D1 守衛：search JS alert() 及 errorText 不可暴露 err.message / error.message / result.error"""
        checks = [
            (r'alert\s*\([^)]*(?:err\.message|error\.message|result\.error)',
             "alert() 內暴露技術錯誤訊息"),
            (r'this\.errorText\s*=\s*.*(?:err\.message|error\.message)',
             "errorText 暴露技術錯誤訊息"),
        ]
        for pattern, label in checks:
            all_violations = []
            for js_file in self._collect_js_files():
                violations = find_pattern_in_file(
                    js_file, pattern,
                    exclude_lines=lambda line, _: self._is_console_or_throw(line)
                )
                for line_num, line_content in violations:
                    all_violations.append(f"  {js_file.relative_to(PROJECT_ROOT)}:{line_num}: {line_content}")
            assert not all_violations, (
                f"D1 守衛違規：{label}\n"
                + "\n".join(all_violations)
                + "\n\n修正：只顯示友善中文提示，技術細節降級到 console.error"
            )


class TestLightboxAnimationGuard:
    """C18 guard: Lightbox interrupt getById kill, ESC/close/open paths (method folded)"""

    SEARCH_GRID_MODE = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'search' / 'state' / 'grid-mode.js'
    SEARCH_NAVIGATION = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'search' / 'state' / 'navigation.js'
    SHOWCASE_CORE = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'state-lightbox.js'

    @staticmethod
    def _extract_function(content, func_name):
        pattern = re.compile(r'^\s*(?:async\s+)?' + re.escape(func_name) + r'\s*\(', re.MULTILINE)
        match = pattern.search(content)
        if not match:
            return ''
        return content[match.start():match.start() + 3000]

    def test_search_js_contains(self):
        """search grid-mode/navigation: getById kill, same-index guard, switch path, ordering"""
        gm = self.SEARCH_GRID_MODE.read_text(encoding='utf-8')
        for expected in ["getById", "playLightboxSwitch"]:
            assert expected in gm, f"search/grid-mode.js missing: {expected!r}"
        # same-index no-op
        body = self._extract_function(gm, 'openLightbox')
        assert re.search(r'lightboxIndex\s*===\s*index', body), \
            "search/grid-mode.js openLightbox missing same-index no-op"
        # navigation: sampleGalleryOpen before lightboxOpen
        nav = self.SEARCH_NAVIGATION.read_text(encoding='utf-8')
        hkd = self._extract_function(nav, 'handleKeydown')
        sg_idx = hkd.find('this.sampleGalleryOpen')
        lb_idx = hkd.find('this.lightboxOpen')
        assert sg_idx >= 0, "navigation.js handleKeydown missing: 'this.sampleGalleryOpen'"
        assert lb_idx >= 0, "navigation.js handleKeydown missing: 'this.lightboxOpen'"
        assert sg_idx < lb_idx, \
            "navigation.js handleKeydown: sampleGalleryOpen block must precede lightboxOpen block"
        assert 'closeSampleGallery' in hkd[sg_idx:lb_idx], \
            "navigation.js sampleGalleryOpen ESC missing: 'closeSampleGallery'"

    def test_showcase_js_contains(self):
        """showcase/state-lightbox.js: _killLightboxTimelines, switch path, searchFromMetadata ordering"""
        content = self.SHOWCASE_CORE.read_text(encoding='utf-8')
        for expected in ["_killLightboxTimelines", "playLightboxSwitch"]:
            assert expected in content, f"showcase/state-lightbox.js missing: {expected!r}"
        body = self._extract_function(content, 'openLightbox')
        assert re.search(r'lightboxIndex\s*===\s*index', body), \
            "showcase/state-lightbox.js openLightbox missing same-index no-op"
        sfm = self._extract_function(content, 'searchFromMetadata')
        assert sfm, "showcase/state-lightbox.js missing: 'searchFromMetadata'"
        assert '_killLightboxTimelines' in sfm, \
            "searchFromMetadata missing: '_killLightboxTimelines'"
        kill_idx = sfm.find('_killLightboxTimelines')
        lb_false_idx = sfm.find('lightboxOpen = false')
        assert lb_false_idx > kill_idx, \
            "searchFromMetadata: 'lightboxOpen = false' must come after '_killLightboxTimelines'"

class TestLightboxStateFirstGuard:
    """B19 守衛：Lightbox 導航必須 state-first（lightboxIndex 在 playLightboxSwitch 之前更新）"""

    SEARCH_GRID_MODE = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'search' / 'state' / 'grid-mode.js'
    SHOWCASE_CORE = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'state-lightbox.js'

    @staticmethod
    def _read_file(path):
        return path.read_text(encoding='utf-8')

    @staticmethod
    def _read_showcase():
        """合併 state-base.js + state-lightbox.js 覆蓋 B19 guard 範圍（cleanup 在 base，lightbox nav 在 lightbox）"""
        return (
            (PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'state-base.js').read_text(encoding='utf-8') + "\n" +
            (PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'state-lightbox.js').read_text(encoding='utf-8')
        )

    @staticmethod
    def _extract_function(content, func_name):
        """粗略擷取函數內容（從函數名到下一個同級函數或檔案結尾）"""
        pattern = re.compile(r'^\s*(?:async\s+)?' + re.escape(func_name) + r'\s*\(', re.MULTILINE)
        match = pattern.search(content)
        if not match:
            return ''
        start = match.start()
        return content[start:start + 3000]

    def test_lightbox_nav_state_first_search(self):
        """B19: search lightbox nav 必須在 playLightboxSwitch 之前更新 lightboxIndex"""
        content = self._read_file(self.SEARCH_GRID_MODE)
        for func in ['prevLightboxVideo', 'nextLightboxVideo']:
            body = self._extract_function(content, func)
            assert body, f"{func} 函數未找到 in grid-mode.js"
            switch_pos = body.find('playLightboxSwitch')
            update_pos = body.find('this.lightboxIndex =')
            assert update_pos != -1 and switch_pos != -1, (
                f"{func} 缺少必要的 lightboxIndex 更新或 playLightboxSwitch 呼叫"
            )
            assert update_pos < switch_pos, (
                f"B19 違規：grid-mode.js {func} 的 lightboxIndex 更新必須在 playLightboxSwitch 之前（state-first）"
            )

    def test_lightbox_nav_state_first_showcase(self):
        """B19: showcase lightbox nav 必須在 playLightboxSwitch 之前更新 lightboxIndex"""
        content = self._read_file(self.SHOWCASE_CORE)
        for func in ['prevLightboxVideo', 'nextLightboxVideo']:
            body = self._extract_function(content, func)
            assert body, f"{func} 函數未找到 in showcase/core.js"
            switch_pos = body.find('playLightboxSwitch')
            # F1: _setLightboxIndex 也是合法的 state-first 更新
            update_pos = body.find('this.lightboxIndex =')
            if update_pos == -1:
                update_pos = body.find('_setLightboxIndex(')
            assert update_pos != -1 and switch_pos != -1, (
                f"{func} 缺少必要的 lightboxIndex 更新或 playLightboxSwitch 呼叫"
            )
            assert update_pos < switch_pos, (
                f"B19 違規：core.js {func} 的 lightboxIndex 更新必須在 playLightboxSwitch 之前（state-first）"
            )

    def test_lightbox_switch_onmidpoint_no_index_update(self):
        """B19: prevLightboxVideo/nextLightboxVideo 不可包含 onMidpoint（state-first 模式下已移除）"""
        for path, filename in [
            (self.SEARCH_GRID_MODE, 'search/state/grid-mode.js'),
            (self.SHOWCASE_CORE, 'showcase/core.js'),
        ]:
            content = self._read_file(path)
            for func in ['prevLightboxVideo', 'nextLightboxVideo']:
                body = self._extract_function(content, func)
                assert body, f"{func} 函數未找到 in {filename}"
                assert 'onMidpoint' not in body, (
                    f"B19 違規：{filename} {func} 仍包含 onMidpoint — "
                    "state-first 模式下 lightboxIndex 應在動畫啟動前就已更新，不需要 onMidpoint callback"
                )

    def test_open_lightbox_switch_state_first(self):
        """B19: openLightbox 的 switch 路徑也必須 state-first"""
        for path, filename in [
            (self.SEARCH_GRID_MODE, 'search/state/grid-mode.js'),
            (self.SHOWCASE_CORE, 'showcase/core.js'),
        ]:
            content = self._read_file(path)
            body = self._extract_function(content, 'openLightbox')
            assert body, f"openLightbox 函數未找到 in {filename}"
            switch_section_start = body.find('lightboxIndex !== index')
            assert switch_section_start != -1, f"{filename} openLightbox 缺少 switch 路徑"
            switch_section = body[switch_section_start:]
            switch_pos = switch_section.find('playLightboxSwitch')
            # F1: _setLightboxIndex(index) 也是合法的 state-first 更新
            update_pos = switch_section.find('lightboxIndex = index')
            if update_pos == -1:
                update_pos = switch_section.find('_setLightboxIndex(index)')
            assert update_pos != -1 and switch_pos != -1, (
                f"{filename} openLightbox switch 路徑缺少 lightboxIndex 更新或 playLightboxSwitch 呼叫"
            )
            assert update_pos < switch_pos, (
                f"B19 違規：{filename} openLightbox switch 路徑的 lightboxIndex 更新必須在 playLightboxSwitch 之前"
            )

    def test_lightbox_nexttick_has_generation_guard(self):
        """B19: 所有 lightbox $nextTick 動畫 callback 必須有 _lightboxGeneration 失效檢查"""
        SEARCH_NAV = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'search' / 'state' / 'navigation.js'
        for path, filename in [
            (self.SEARCH_GRID_MODE, 'search/state/grid-mode.js'),
            (self.SHOWCASE_CORE, 'showcase/core.js'),
        ]:
            content = self._read_file(path)
            for func in ['prevLightboxVideo', 'nextLightboxVideo', 'openLightbox']:
                body = self._extract_function(content, func)
                if 'playLightboxSwitch' not in body and 'playLightboxOpen' not in body:
                    continue
                assert '_lightboxGeneration' in body, (
                    f"B19 違規：{filename} {func} 的 $nextTick callback 缺少 _lightboxGeneration 失效檢查 — "
                    "close/ESC 後 stale callback 會重設 _lightboxAnimating = true 造成 input lock"
                )

    def test_lightbox_close_increments_generation(self):
        """B19: closeLightbox / ESC / searchFromMetadata / page cleanup 必須 increment _lightboxGeneration"""
        # Search closeLightbox
        content = self._read_file(self.SEARCH_GRID_MODE)
        body = self._extract_function(content, 'closeLightbox')
        assert body, "closeLightbox 函數未找到 in grid-mode.js"
        assert '_lightboxGeneration++' in body, (
            "B19 違規：search closeLightbox 缺少 _lightboxGeneration++ — "
            "pending $nextTick callback 不會被 invalidate"
        )

        # Showcase closeLightbox
        content = self._read_file(self.SHOWCASE_CORE)
        body = self._extract_function(content, 'closeLightbox')
        assert body, "closeLightbox 函數未找到 in showcase/core.js"
        assert '_lightboxGeneration++' in body, (
            "B19 違規：showcase closeLightbox 缺少 _lightboxGeneration++ — "
            "pending $nextTick callback 不會被 invalidate"
        )

        # Showcase searchFromMetadata
        body = self._extract_function(content, 'searchFromMetadata')
        assert body, "searchFromMetadata 函數未找到 in showcase/core.js"
        assert '_lightboxGeneration++' in body, (
            "B19 違規：showcase searchFromMetadata 缺少 _lightboxGeneration++ — "
            "pending $nextTick callback 不會被 invalidate"
        )

        # Page lifecycle cleanup — search (index.js 已由 main.js 取代，54e)
        SEARCH_MAIN = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'search' / 'main.js'
        search_main_content = SEARCH_MAIN.read_text(encoding='utf-8')
        assert '_lightboxGeneration++' in search_main_content, (
            "B19 違規：search main.js cleanup 缺少 _lightboxGeneration++ — "
            "離頁時 pending $nextTick lightbox callback 不會被 invalidate"
        )

        # Page lifecycle cleanup — showcase (init is async, extract manually)
        showcase_content = self._read_showcase()
        cleanup_start = showcase_content.find('cleanup: ()')
        assert cleanup_start != -1, "showcase/state-base.js 缺少 cleanup callback"
        cleanup_section = showcase_content[cleanup_start:cleanup_start + 500]
        assert '_lightboxGeneration++' in cleanup_section, (
            "B19 違規：showcase init() cleanup 缺少 _lightboxGeneration++ — "
            "離頁時 pending $nextTick lightbox callback 不會被 invalidate"
        )


class TestShowcaseReactiveScopeGuard:
    """F1: videos/filteredVideos 移出 Alpine reactive scope — 守衛測試"""

    CORE_JS = PROJECT_ROOT / "web/static/js/pages/showcase/state-base.js"
    SHOWCASE_HTML = PROJECT_ROOT / "web/templates/showcase.html"

    def _read_js(self):
        """合併讀取全部 4 個 ESM 模組覆蓋 F1 守衛範圍。"""
        return (
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-base.js").read_text(encoding='utf-8') + "\n" +
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-videos.js").read_text(encoding='utf-8') + "\n" +
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-actress.js").read_text(encoding='utf-8') + "\n" +
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-lightbox.js").read_text(encoding='utf-8')
        )

    def _get_return_block(self):
        """Extract and concatenate all 'return { ... }' blocks from the merged showcase state modules."""
        content = self._read_js()
        blocks = []
        pos = 0
        while True:
            start = content.find('return {', pos)
            if start == -1:
                break
            brace_depth = 0
            end = start
            for i in range(start, len(content)):
                if content[i] == '{':
                    brace_depth += 1
                elif content[i] == '}':
                    brace_depth -= 1
                    if brace_depth == 0:
                        end = i + 1
                        break
            blocks.append(content[start:end])
            pos = end
        assert blocks, "Cannot find any 'return {' block in ESM state modules"
        return '\n'.join(blocks)

    def test_guard1_no_videos_in_return_object(self):
        """Guard 1: showcaseState() return object 不包含 videos: 或 filteredVideos: 屬性"""
        block = self._get_return_block()
        lines = block.split('\n')
        for i, line in enumerate(lines, 1):
            assert not re.search(r'^\s*videos\s*:', line), (
                f"F1 違規：return object 第 {i} 行仍包含 'videos:' 屬性 — "
                "應移至閉包變數 _videos"
            )
            assert not re.search(r'^\s*filteredVideos\s*:', line), (
                f"F1 違規：return object 第 {i} 行仍包含 'filteredVideos:' 屬性 — "
                "應移至閉包變數 _filteredVideos"
            )

    def test_guard2_has_count_scalars(self):
        """Guard 2: return object 包含 videoCount: 和 filteredCount:"""
        block = self._get_return_block()
        assert re.search(r'^\s*videoCount\s*:', block, re.MULTILINE), (
            "F1 違規：return object 缺少 'videoCount:' — "
            "需要 scalar reactive 給 template 綁定"
        )
        assert re.search(r'^\s*filteredCount\s*:', block, re.MULTILINE), (
            "F1 違規：return object 缺少 'filteredCount:' — "
            "需要 scalar reactive 給 template 綁定"
        )

    def test_guard3_no_getter_currentLightboxVideo(self):
        """Guard 3: currentLightboxVideo 不是 getter，應為 reactive property"""
        block = self._get_return_block()
        assert 'get currentLightboxVideo()' not in block, (
            "F1 違規：return object 仍有 'get currentLightboxVideo()' getter — "
            "應改為 'currentLightboxVideo: null' reactive property"
        )
        assert re.search(r'^\s*currentLightboxVideo\s*:', block, re.MULTILINE), (
            "F1 違規：return object 缺少 'currentLightboxVideo:' property — "
            "應為手動更新的 reactive property"
        )

    def test_guard4_no_videos_length_in_template(self):
        """Guard 4: showcase.html 不包含 videos.length 或 filteredVideos.length"""
        content = self.SHOWCASE_HTML.read_text(encoding='utf-8')
        assert 'videos.length' not in content, (
            "F1 違規：showcase.html 仍引用 'videos.length' — "
            "應改用 videoCount"
        )
        assert 'filteredVideos.length' not in content, (
            "F1 違規：showcase.html 仍引用 'filteredVideos.length' — "
            "應改用 filteredCount"
        )

    def test_guard5_no_bare_videos_in_template(self):
        """Guard 5: showcase.html 不引用 bare videos 或 filteredVideos"""
        content = self.SHOWCASE_HTML.read_text(encoding='utf-8')
        # Match 'videos' or 'filteredVideos' but exclude allowed compounds
        for i, line in enumerate(content.split('\n'), 1):
            # Remove allowed patterns first, then check for bare references
            cleaned = line
            for allowed in ['paginatedVideos', 'currentLightboxVideo', 'videoCount', 'filteredCount',
                            'fetchVideos', 'prevLightboxVideo', 'nextLightboxVideo',
                            'openLightbox', 'closeLightbox', 'playVideo',
                            'showcase.unit.videos']:
                cleaned = cleaned.replace(allowed, '')
            # Now check for bare 'videos' (word boundary)
            if re.search(r'\bvideos\b', cleaned):
                pytest.fail(
                    f"F1 違規：showcase.html L{i} 引用 bare 'videos' — "
                    f"應改用 videoCount 或 paginatedVideos: {line.strip()}"
                )

    def test_guard6_closure_variables_exist(self):
        """Guard 6: state-base.js 有 var _videos 和 var _filteredVideos（module-level 大陣列）"""
        content = self._read_js()
        # ESM 結構：_videos/_filteredVideos 為 module-level export var
        assert re.search(r'\bvar\s+_videos\b', content), (
            "F1 違規：state-base.js 缺少 'var _videos' module-level 宣告 — "
            "大陣列應為模組閉包變數（ESM export var）"
        )
        assert re.search(r'\bvar\s+_filteredVideos\b', content), (
            "F1 違規：state-base.js 缺少 'var _filteredVideos' module-level 宣告 — "
            "大陣列應為模組閉包變數（ESM export var）"
        )

    def _find_statement_end(self, lines, start_idx):
        """Find the end line of a statement starting at start_idx.

        For multi-line statements (e.g., _filteredVideos = _videos.filter(video => { ... })),
        track brace/paren nesting to find the actual end of the statement.
        Returns the index of the last line of the statement.
        """
        depth = 0
        for j in range(start_idx, min(start_idx + 50, len(lines))):
            for ch in lines[j]:
                if ch in '({':
                    depth += 1
                elif ch in ')}':
                    depth -= 1
            # Statement ends when we return to depth 0 (or never went deeper)
            if depth <= 0 and j > start_idx:
                return j
            if depth == 0 and ';' in lines[j]:
                return j
        return start_idx

    def test_guard7_count_sync_after_assignment(self):
        """Guard 7: 每個 _videos = 賦值附近有 videoCount 同步；_filteredVideos = 附近有 filteredCount 同步"""
        content = self._read_js()
        lines = content.split('\n')

        # Check _videos = assignments
        for i, line in enumerate(lines):
            # Match _videos = but not _filteredVideos =
            if re.search(r'\b_videos\s*=', line) and not re.search(r'_filteredVideos', line):
                # Skip var declaration (including ESM export var)
                if re.search(r'(?:export\s+)?var\s+_videos', line):
                    continue
                # Find statement end for multi-line expressions
                stmt_end = self._find_statement_end(lines, i)
                # Check within 3 lines after statement end for videoCount
                nearby = '\n'.join(lines[max(0, i-3):stmt_end+4])
                assert 'videoCount' in nearby, (
                    f"F1 違規：core.js L{i+1} 有 '_videos =' 但附近無 videoCount 同步 — "
                    f"每次 _videos 賦值後必須更新 this.videoCount: {line.strip()}"
                )

        # Check _filteredVideos = assignments
        for i, line in enumerate(lines):
            if re.search(r'\b_filteredVideos\s*=', line):
                # Skip var declaration (including ESM export var)
                if re.search(r'(?:export\s+)?var\s+_filteredVideos', line):
                    continue
                # Skip sort (in-place, no length change)
                if '.sort(' in line:
                    continue
                # Find statement end for multi-line expressions
                stmt_end = self._find_statement_end(lines, i)
                # Check within 3 lines after statement end for filteredCount
                nearby = '\n'.join(lines[max(0, i-3):stmt_end+4])
                assert 'filteredCount' in nearby, (
                    f"F1 違規：core.js L{i+1} 有 '_filteredVideos =' 但附近無 filteredCount 同步 — "
                    f"每次 _filteredVideos 賦值後必須更新 this.filteredCount: {line.strip()}"
                )


class TestGridPerPageGuard:
    """F2: Grid mode 禁用「全部」(perPage=0) 守衛測試"""

    CORE_JS = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'state-videos.js'
    SHOWCASE_HTML = PROJECT_ROOT / 'web' / 'templates' / 'showcase.html'

    def _read_js(self):
        """合併讀取 state-base.js + state-videos.js（updatePagination 在 videos，restoreState 在 base）。"""
        return (
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-base.js").read_text(encoding='utf-8') + "\n" +
            (PROJECT_ROOT / "web/static/js/pages/showcase/state-videos.js").read_text(encoding='utf-8')
        )

    def test_grid_per_page_method_bodies_contain_guard(self):
        """Guard 1/3/4: updatePagination / restoreState / switchMode 均含 grid+perPage=120 降級邏輯"""
        content = self._read_js()
        for method_pat, window in [
            (r'updatePagination\s*\(\s*\)\s*\{', 800),
            (r'restoreState\s*\(\s*\)\s*\{', 2500),
            (r'switchMode\s*\(\s*m\s*\)\s*\{', 600),
        ]:
            m = re.search(method_pat, content)
            method_name = method_pat.split(r'\s')[0]
            assert m, f"showcase/core.js 找不到 {method_name} 方法"
            body = content[m.start():m.start() + window]
            has_grid = bool(re.search(r"['\"]grid['\"]", body))
            has_120 = bool(re.search(r'perPage\s*=\s*120', body))
            assert has_grid and has_120, \
                f"F2 違規：{method_name} 缺少 grid+perPage=120 降級邏輯"

    def test_guard5_items_per_page_uses_nullish_coalescing(self):
        """Guard 5 (T3.2 P2 fix): items_per_page 預設值必須用 `??` 而非 `||`

        Settings UI 允許 items_per_page=0（"全部"選項，settings.html L663），
        後端 `core/config.py:GalleryConfig.items_per_page` 沒有 gt=0 validator → 0 會透傳到前端。
        若用 `||` 會把 0 視為 falsy 走 fallback 90，導致：
          1. showcase init 永遠拿不到 0，grid+perPage=0→120 降級邏輯（Guard 1/3/4）永遠不觸發
          2. settings 載入時把存檔的 0 顯示成 90，"全部" 選項失效

        必須用 `??`（nullish coalescing）只對 null/undefined 走 fallback，保留 numeric 0。
        """
        showcase_core = self._read_js()
        settings_js = (PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'settings' / 'state-config.js').read_text(encoding='utf-8')

        # 禁止 `items_per_page || ...` pattern（吞 0 的寫法）
        bad_pattern = re.compile(r'items_per_page\s*\|\|')
        showcase_bad = bad_pattern.findall(showcase_core)
        settings_bad = bad_pattern.findall(settings_js)
        assert not showcase_bad, (
            "T3.2 P2 違規：showcase/core.js 含 `items_per_page ||` — "
            "Settings 的 items_per_page=0 ('全部') 會被吞成 fallback，必須改用 `??`"
        )
        assert not settings_bad, (
            "T3.2 P2 違規：settings.js 含 `items_per_page ||` — "
            "載入存檔的 items_per_page=0 ('全部') 會被吞成 fallback，必須改用 `??`"
        )

        # 正向斷言：showcase / settings 都必須有 `items_per_page ?? <number>` 寫法
        good_pattern = re.compile(r'items_per_page\s*\?\?\s*\d+')
        assert good_pattern.search(showcase_core), (
            "T3.2 P2 違規：showcase/core.js 缺少 `items_per_page ?? <number>` 預設值寫法"
        )
        assert good_pattern.search(settings_js), (
            "T3.2 P2 違規：settings.js 缺少 `items_per_page ?? <number>` 預設值寫法"
        )


class TestSettingsResetConfigNoNativeConfirm:
    """T3.4 (CD-52-11): resetConfig 改 fluent-modal 後 settings.js 不再含原 confirm 文字

    用「資料指紋」式精準字串匹配，避免誤命中 cycleLocale (L262) 既有 confirm —
    該 confirm 屬 backlog，不在 Phase 52 範圍。
    """

    SETTINGS_JS = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'settings' / 'state-config.js'

    def test_settings_resetconfig_no_native_confirm(self):
        """T3.4: resetConfig 改 fluent-modal 後 settings.js 不再含原 confirm 完整文字

        守衛字串對齊舊 native confirm 完整文（含尾句號），與新 i18n key 內容
        ('...無法復原。') 不重疊，避免 fallback 內聯時誤觸發。
        """
        settings_js = self.SETTINGS_JS.read_text(encoding="utf-8")
        assert "確定要重置所有設定嗎？此操作將刪除所有自訂設定。" not in settings_js, (
            "T3.4 違規：resetConfig() native confirm 已於 T3.4 替換為 fluent-modal — "
            "settings.js 不應再含舊 native confirm 完整字串"
        )


class TestScannerDeleteAliasGroupNoNativeConfirm:
    """T3.5 (CD-52-11): deleteAliasGroup 改 fluent-modal 後 scanner.js 不再含原 confirm 完整文字

    用「資料指紋」式精準字串匹配，避免誤命中 L239 page-lifecycle confirm
    （'確定要離開嗎？' — backlog OQ 不在 Phase 52 範圍）+ L734 clearLogs
    confirm（'確定要清除所有日誌嗎？...' — Phase 52 不入）。

    額外 assert 三個新 method 名個別存在（避免假陰性 — 若 deleteAliasGroup
    被混進 confirmRemoveActress 等不相關名稱，弱守衛仍會 pass）。
    """

    SCANNER_JS = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'scanner' / 'state-alias.js'

    def test_scanner_no_delete_alias_group_native_confirm(self):
        """T3.5: deleteAliasGroup native confirm 已替換為 fluent-modal"""
        scanner_js = self.SCANNER_JS.read_text(encoding="utf-8")
        # 守衛舊 native confirm 完整文字（含「確定要刪除「」+ 「整筆別名組嗎？」）
        assert "確定要刪除「" not in scanner_js, (
            "T3.5 違規：deleteAliasGroup() native confirm 已於 T3.5 替換為 fluent-modal"
        )
        assert "整筆別名組嗎？" not in scanner_js, (
            "T3.5 違規：deleteAliasGroup() native confirm 已於 T3.5 替換為 fluent-modal"
        )

    def test_scanner_has_delete_alias_group_modal_methods(self):
        """T3.5: 三個新 method 個別存在（強守衛,避免名字混過去）"""
        scanner_js = self.SCANNER_JS.read_text(encoding="utf-8")
        # 個別 assert，避免「deleteAliasGroup in scanner.js」這種會被舊名混過去的弱 guard
        assert "openDeleteAliasGroupModal" in scanner_js, (
            "T3.5 違規：openDeleteAliasGroupModal method 應存在（modal trigger 入口）"
        )
        assert "confirmDeleteAliasGroup" in scanner_js, (
            "T3.5 違規：confirmDeleteAliasGroup method 應存在（API 執行入口）"
        )
        assert "cancelDeleteAliasGroupModal" in scanner_js, (
            "T3.5 違規：cancelDeleteAliasGroupModal method 應存在（dismiss 入口）"
        )

    def test_scanner_html_escape_ladder_includes_delete_alias_group(self):
        """T3.5: scanner.html root escape.window ladder 含 deleteAliasGroupModalOpen"""
        scanner_html = (PROJECT_ROOT / 'web' / 'templates' / 'scanner.html').read_text(encoding="utf-8")
        assert "deleteAliasGroupModalOpen && cancelDeleteAliasGroupModal" in scanner_html, (
            "T3.5 違規：scanner.html root @keydown.escape.window 應串接 deleteAliasGroupModal 的 cancel"
        )


class TestSampleGalleryTemplateGuard:
    """T8：Search Sample Gallery 模板守衛

    靜態確認舊 sampleLightboxOpen / sampleLightboxIndex 已從所有模板移除，
    新 sampleGalleryOpen / sampleGalleryImages / sampleGalleryIndex 已正確
    出現在 search.html 及 base.html（body x-data fallback）中，且
    .sample-gallery overlay 在 searchPage() x-data scope 範圍內。

    base.html 例外說明：body[x-data] 加入 sampleGalleryOpen 等 fallback
    是必要的。Alpine 嵌套 scope 初始化期間，body scope 偶爾會在
    子 x-data（searchPage()）建立前先評估子元素的 binding，導致
    ReferenceError。Fallback 提供安全預設值。

    此 guard 防止未來模板重構時 .sample-gallery 被移出正確 scope，
    或舊 sampleLightbox* 狀態殘留。
    """

    SEARCH_HTML = PROJECT_ROOT / 'web' / 'templates' / 'search.html'
    BASE_HTML = PROJECT_ROOT / 'web' / 'templates' / 'base.html'
    TEMPLATES_DIR = PROJECT_ROOT / 'web' / 'templates'

    def test_sample_gallery_template_html_contains(self):
        """T8/37b-layout: search.html + base.html 含 sampleGallery* state；search.html 含 lb-header；不含舊殘留字串"""
        search_content = self.SEARCH_HTML.read_text(encoding='utf-8')
        base_content = self.BASE_HTML.read_text(encoding='utf-8')
        for state in ('sampleGalleryOpen', 'sampleGalleryImages', 'sampleGalleryIndex'):
            assert state in search_content, f"search.html missing: {state!r}"
            assert state in base_content, f"base.html missing: {state!r}"
        for expected in ['lb-header']:
            assert expected in search_content, f"search.html missing: {expected!r}"
        for forbidden in ['class="sample-lightbox"', 'lb-meta-extra']:
            assert forbidden not in search_content, \
                f"search.html should not contain: {forbidden!r}"

    def test_sample_gallery_template_structure(self):
        """T8: 舊 sampleLightbox* 不在任何模板；sample-gallery 在 searchPage scope 內；sg-open-btn 在 lb-header 內"""
        # 舊 state 不殘留
        pattern = re.compile(r'sampleLightboxOpen|sampleLightboxIndex')
        violations = [str(t.relative_to(PROJECT_ROOT))
                      for t in self.TEMPLATES_DIR.glob('**/*.html')
                      if pattern.search(t.read_text(encoding='utf-8'))]
        assert not violations, \
            f"T8 違規：舊 sampleLightboxOpen/sampleLightboxIndex 仍殘留：{violations}"
        # sample-gallery 在 searchPage scope 後
        content = self.SEARCH_HTML.read_text(encoding='utf-8')
        lines = content.split('\n')
        sp_line = next((i for i, l in enumerate(lines) if 'x-data="searchPage"' in l), None)
        assert sp_line is not None, "search.html missing: 'x-data=\"searchPage\"'"
        sg_line = next((i for i, l in enumerate(lines) if 'class="sample-gallery"' in l), None)
        assert sg_line is not None, "search.html missing: 'class=\"sample-gallery\"'"
        assert sg_line > sp_line, \
            f"T8 違規：.sample-gallery (L{sg_line+1}) 在 searchPage scope (L{sp_line+1}) 之前"
        # sg-open-btn 在 lb-header 內
        lb_line = next((i for i, l in enumerate(lines) if '"lb-header"' in l), None)
        assert lb_line is not None, "search.html missing: 'lb-header'"
        lb_close = None
        depth = 0
        for i in range(lb_line, len(lines)):
            depth += lines[i].count('<div') - lines[i].count('</div>')
            if i > lb_line and depth <= 0:
                lb_close = i
                break
        assert lb_close is not None, "search.html lb-header 找不到對應的 </div>"
        sg_btn_line = next((i for i, l in enumerate(lines) if 'sg-open-btn' in l), None)
        assert sg_btn_line is not None, "search.html missing: 'sg-open-btn'"
        assert lb_line < sg_btn_line < lb_close, \
            f"T8 違規：sg-open-btn (L{sg_btn_line+1}) 不在 lb-header (L{lb_line+1}~L{lb_close+1}) 內"


class TestProxyDirectGuard:
    """37d T3 守衛 — settings.html proxy placeholder 包含 direct 提示"""

    def test_settings_proxy_placeholder_has_direct(self):
        """i18n 後 placeholder 文字移至 locale JSON，檢查 zh_TW.json 或 HTML"""
        html = (PROJECT_ROOT / 'web/templates/settings.html').read_text(encoding='utf-8')
        locale_file = PROJECT_ROOT / 'locales' / 'zh_TW.json'
        locale_content = locale_file.read_text(encoding='utf-8') if locale_file.exists() else ''
        assert 'direct' in html.lower() or 'direct' in locale_content.lower(), \
            "settings.html 或 locales/zh_TW.json proxy placeholder 應包含 direct 提示"


class TestShowcaseSampleGalleryGuard:
    """T7：Showcase Sample Gallery 靜態守衛

    確保 sample-gallery 元件正確實作於 showcase.html / core.js / animations.js：
    1. Scope 守衛：.sample-gallery 在 x-data="showcaseState()" scope 之後
    2. State 存在守衛：core.js 包含 sampleGalleryOpen / sampleGalleryImages / sampleGalleryIndex
    3. Method 存在守衛：core.js 包含全部 5 個方法
    4. 入口按鈕守衛：showcase.html 包含 sg-open-btn 和 openSampleGallery( 綁定
    5. Overlay 綁定守衛：.sample-gallery 有 sampleGalleryOpen 的 :class / x-show 綁定
    6. 縮圖 active 守衛：sg-thumb-active 和 sampleGalleryIndex 在同一區域
    7. playSampleGallerySwitch 守衛：animations.js 包含完整 C18/C21 實作
    """

    SHOWCASE_HTML = PROJECT_ROOT / 'web' / 'templates' / 'showcase.html'
    CORE_JS = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'state-lightbox.js'
    ANIMATIONS_JS = PROJECT_ROOT / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'animations.js'

    def test_showcase_sample_gallery_js_contains(self):
        """T7 守衛 2/3/7: core.js state props + methods；animations.js playSampleGallerySwitch 完整實作"""
        core = self.CORE_JS.read_text(encoding='utf-8')
        for expected in ('sampleGalleryOpen', 'sampleGalleryImages', 'sampleGalleryIndex',
                         'openSampleGallery', 'closeSampleGallery', 'prevSampleGallery',
                         'nextSampleGallery', 'jumpSampleGallery'):
            assert expected in core, f"showcase/state-lightbox.js missing: {expected!r}"
        anim = self.ANIMATIONS_JS.read_text(encoding='utf-8')
        for expected in ['playSampleGallerySwitch', 'killTweensOf', 'gsap-animating', 'clearProps']:
            assert expected in anim, f"showcase/animations.js missing: {expected!r}"

    def test_showcase_sample_gallery_html_structure(self):
        """T7/37b-layout 守衛 1/4/5/6/8/9/10: showcase.html scope 順序、bindings、lb-header、sg-open-btn 位置"""
        content = self.SHOWCASE_HTML.read_text(encoding='utf-8')
        lines = content.split('\n')
        # 守衛 1: .sample-gallery 在 x-data="showcase" scope 後
        sc_line = next((i for i, l in enumerate(lines) if 'x-data="showcase"' in l), None)
        assert sc_line is not None, "showcase.html missing: 'x-data=\"showcase\"'"
        sg_line = next((i for i, l in enumerate(lines) if 'sample-gallery' in l), None)
        assert sg_line is not None, "showcase.html missing: '.sample-gallery'"
        assert sg_line > sc_line, \
            f"T7 違規：.sample-gallery (L{sg_line+1}) 在 showcase scope (L{sc_line+1}) 之前"
        # 守衛 4: sg-open-btn + openSampleGallery
        for expected in ['sg-open-btn', 'openSampleGallery(']:
            assert expected in content, f"showcase.html missing: {expected!r}"
        # 守衛 5: sampleGalleryOpen 在 .sample-gallery 附近 10 行
        gl_start = next((i for i, l in enumerate(lines)
                         if 'sample-gallery' in l and ('class=' in l or 'class =' in l)), None)
        assert gl_start is not None, "showcase.html missing: class='sample-gallery' element"
        nearby = '\n'.join(lines[gl_start:gl_start + 10])
        assert 'sampleGalleryOpen' in nearby, \
            "showcase.html .sample-gallery missing: 'sampleGalleryOpen' binding nearby"
        # 守衛 6: sg-thumb-active 與 sampleGalleryIndex 在 5 行內
        ta_lines = [i for i, l in enumerate(lines) if 'sg-thumb-active' in l]
        gi_lines = [i for i, l in enumerate(lines) if 'sampleGalleryIndex' in l]
        assert ta_lines, "showcase.html missing: 'sg-thumb-active'"
        assert gi_lines, "showcase.html missing: 'sampleGalleryIndex'"
        assert any(abs(t - g) <= 5 for t in ta_lines for g in gi_lines), \
            "showcase.html: sg-thumb-active 和 sampleGalleryIndex 未在同一區域（5 行內）"
        # 37b-layout: lb-header 存在；無 lb-meta-extra
        assert 'lb-header' in content, "showcase.html missing: 'lb-header'"
        assert 'lb-meta-extra' not in content, \
            "showcase.html should not contain: 'lb-meta-extra'"
        # 守衛 10: sg-open-btn 在 lb-header 範圍內
        lb_line = next((i for i, l in enumerate(lines) if '"lb-header"' in l), None)
        assert lb_line is not None, "showcase.html missing: 'lb-header' container"
        lb_close = None
        depth = 0
        for i in range(lb_line, len(lines)):
            depth += lines[i].count('<div') - lines[i].count('</div>')
            if i > lb_line and depth <= 0:
                lb_close = i
                break
        assert lb_close is not None, "showcase.html lb-header 找不到對應的 </div>"
        sg_btn = next((i for i, l in enumerate(lines) if 'sg-open-btn' in l), None)
        assert sg_btn is not None, "showcase.html missing: 'sg-open-btn'"
        assert lb_line < sg_btn < lb_close, \
            f"showcase.html sg-open-btn (L{sg_btn+1}) 不在 lb-header (L{lb_line+1}~L{lb_close+1}) 內"



class TestHelpPageGuard:
    """37d T4 守衛 — help.html 包含 Phase 36/37 新功能說明
    38a T6 更新：文字已移至 i18n key，改為驗證 HTML 有對應 t() 呼叫 + zh_TW.json 含對應字串"""

    def _zh_tw(self):
        import json
        return json.loads((PROJECT_ROOT / 'locales/zh_TW.json').read_text(encoding='utf-8'))

    def test_help_page_guard_html_contains(self):
        """37d/38a 守衛：help.html 含 i18n keys；zh_TW.json 含對應字串"""
        html = (PROJECT_ROOT / 'web/templates/help.html').read_text(encoding='utf-8')
        zh = self._zh_tw()
        for html_key, json_path, expected_text in [
            ('help.scraper.h6_default_source', ['help', 'scraper', 'h6_default_source'], '預設搜尋來源'),
            ('help.scraper.h6_dmm_fuzzy', ['help', 'scraper', 'h6_dmm_fuzzy'], '模糊搜尋'),
            ('help.showcase.other_lightbox_detail', ['help', 'showcase', 'other_lightbox_detail'], '導演'),
            ('help.showcase.other_gallery', ['help', 'showcase', 'other_gallery'], '劇照'),
            ('help.showcase.other_table_cols', ['help', 'showcase', 'other_table_cols'], '片長'),
            ('help.scanner.subtitle_move', ['help', 'scanner', 'subtitle_move'], '字幕'),
        ]:
            assert html_key in html, f"help.html missing: {html_key!r}"
            cur = zh
            for part in json_path:
                cur = cur[part]
            assert expected_text in cur, \
                f"zh_TW.json {'.'.join(json_path)} missing: {expected_text!r}"

    def test_help_page_guard_direct_mode(self):
        """help.html 含 direct（至少 2 次）"""
        html = (PROJECT_ROOT / 'web/templates/help.html').read_text(encoding='utf-8')
        assert html.lower().count('direct') >= 2, \
            "help.html missing: 'direct' at least 2 occurrences"


class TestScannerMissingPillGuard:
    """T10 guard - missing NFO/cover pill + SSE completion (method folded)"""

    SCANNER_HTML = PROJECT_ROOT / "web" / "templates" / "scanner.html"
    SCANNER_SCAN_JS = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "scanner" / "state-scan.js"
    SCANNER_BATCH_JS = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "scanner" / "state-batch.js"
    ZH_TW = PROJECT_ROOT / "locales" / "zh_TW.json"

    def test_scanner_contains(self):
        """scanner.html/JS/i18n contain all T10 missing pill strings"""
        html = self.SCANNER_HTML.read_text(encoding='utf-8')
        for expected in ["missingPillVisible", "resumePillVisible"]:
            assert expected in html, f"scanner.html missing: {expected!r}"
        batch = self.SCANNER_BATCH_JS.read_text(encoding='utf-8')
        for expected in ["missingPillVisible", "missingItems", "resumePillVisible",
                         "runMissingEnrich", "checkMissing"]:
            assert expected in batch, f"scanner/state-batch.js missing: {expected!r}"
        scan = self.SCANNER_SCAN_JS.read_text(encoding='utf-8')
        for expected in ["enriching", "missingPillVisible"]:
            assert expected in scan, f"scanner/state-scan.js missing: {expected!r}"
        zh = self.ZH_TW.read_text(encoding='utf-8')
        for expected in ["missing_enrich_idle", "missing_resume_btn"]:
            assert expected in zh, f"zh_TW.json missing: {expected!r}"

class TestGhostFlyPlayLightboxOpen:
    """Phase 51 Phase 4 T4.1：GhostFly.playLightboxOpen 共用實作守衛

    確認 ghost-fly.js 內 playLightboxOpen 函式存在 + cleanup 契約
    （clearProps）+ opts.timelineId 介面已植入。
    """

    GHOST_FLY_JS = PROJECT_ROOT / 'web' / 'static' / 'js' / 'shared' / 'ghost-fly.js'

    def test_ghost_fly_play_lightbox_open_contains(self):
        """ghost-fly.js 含 playLightboxOpen + clearProps + timelineId"""
        js = self.GHOST_FLY_JS.read_text(encoding='utf-8')
        for expected in ['playLightboxOpen', 'clearProps', 'timelineId']:
            assert expected in js, f"ghost-fly.js missing: {expected!r}"


class TestT36ToastI18nKeys:
    """T3.6 (CD-52-11): alert→toast 改寫後新 i18n keys 必須存在於 zh_TW.json"""

    LOCALE_FILE = PROJECT_ROOT / "locales" / "zh_TW.json"

    REQUIRED_KEYS = [
        # scanner.toast (6)
        "scanner.toast.desktop_only",
        "scanner.toast.folder_already_added",
        "scanner.toast.copy_path_failed",
        "scanner.toast.generate_error",
        "scanner.toast.nfo_update_error",
        "scanner.toast.jellyfin_update_error",
        # scanner.copy_fail_modal (3)
        "scanner.copy_fail_modal.title",
        "scanner.copy_fail_modal.body",
        "scanner.copy_fail_modal.close",
        # settings.toast (1)
        "settings.toast.desktop_only",
        # search.toast (4)
        "search.toast.no_valid_files",
        "search.toast.desktop_only",
        "search.toast.load_failed",
        "search.toast.translate_failed",
    ]

    def test_all_t36_keys_exist_in_zh_tw(self):
        import json
        data = json.loads(self.LOCALE_FILE.read_text(encoding="utf-8"))

        def get_nested(d, dotted):
            cur = d
            for part in dotted.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return None
                cur = cur[part]
            return cur if isinstance(cur, str) else None

        missing = [k for k in self.REQUIRED_KEYS if get_nested(data, k) is None]
        assert not missing, f"T3.6 違規：zh_TW.json 缺 i18n keys：{missing}"


class TestScannerCopyFailModal:
    """T3.6: scanner.html copyFailModal markup + scanner/state-scan.js 三 method + escape ladder"""

    SCANNER_JS = PROJECT_ROOT / "web" / "static" / "js" / "pages" / "scanner" / "state-scan.js"
    SCANNER_HTML = PROJECT_ROOT / "web" / "templates" / "scanner.html"

    def test_scanner_copy_fail_modal_contains(self):
        """T3.6: scanner.js 三 method + scanner.html markup + escape ladder"""
        js = self.SCANNER_JS.read_text(encoding="utf-8")
        for expected in ['openCopyFailModal', 'closeCopyFailModal', 'copyFailModalOpen']:
            assert expected in js, f"scanner/state-scan.js missing: {expected!r}"
        html = self.SCANNER_HTML.read_text(encoding="utf-8")
        for expected in ['copy_fail_modal.title', 'copy-fail-pre',
                         'copyFailModalOpen && closeCopyFailModal']:
            assert expected in html, f"scanner.html missing: {expected!r}"
