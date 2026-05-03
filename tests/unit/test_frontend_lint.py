"""前端靜態守衛 — 確保 template 包含必要的 Alpine 綁定"""
import json
import re
from pathlib import Path

import pytest

SHOWCASE_HTML = Path(__file__).parent.parent.parent / "web" / "templates" / "showcase.html"


class TestShowcaseMetadataGuard:
    """T3: 確保 showcase.html 包含必要 Alpine 綁定（method folded）"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def test_showcase_html_contains(self):
        """showcase.html 含 metadata 綁定、lightbox 欄位、searchFromMetadata"""
        html = self._html()
        for expected in [
            "video.series",
            "video.duration",
            "video.director",
            "table-cell-duration",
            "currentLightboxVideo?.director",
            "currentLightboxVideo?.duration",
            "currentLightboxVideo?.series",
            "currentLightboxVideo?.label",
            "lb-details",
            "searchFromMetadata(currentLightboxVideo?.director)",
        ]:
            assert expected in html, f"showcase.html missing: {expected!r}"
        # series searchFromMetadata (grid panel or lightbox)
        assert ("searchFromMetadata(video.series)" in html or
                "searchFromMetadata(currentLightboxVideo?.series)" in html), \
            "showcase.html missing: series searchFromMetadata call"


SEARCH_HTML = Path(__file__).parent.parent.parent / "web" / "templates" / "search.html"


class TestSearchLightboxMetadataGuard:
    """T4: search.html lightbox metadata bindings (method folded)"""

    def _html(self):
        return SEARCH_HTML.read_text(encoding="utf-8")

    def test_search_html_contains(self):
        """search.html lightbox 含 metadata 綁定"""
        html = self._html()
        for expected in [
            "currentLightboxVideo()?.director",
            "currentLightboxVideo()?.duration",
            "currentLightboxVideo()?.series",
            "currentLightboxVideo()?.label",
            "lb-details",
        ]:
            assert expected in html, f"search.html missing: {expected!r}"


SHOWCASE_BASE_JS     = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "showcase" / "state-base.js"
SHOWCASE_VIDEOS_JS   = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "showcase" / "state-videos.js"
SHOWCASE_ACTRESS_JS  = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "showcase" / "state-actress.js"
SHOWCASE_LIGHTBOX_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "showcase" / "state-lightbox.js"
SHOWCASE_MAIN_JS     = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "showcase" / "main.js"


class TestShowcaseCoreJsSearchableFields:
    """T5: showcase/state-videos.js searchable fields guard (method folded)"""

    def _js(self):
        return SHOWCASE_VIDEOS_JS.read_text(encoding="utf-8")

    def _extract_searchable_fields(self, js):
        match = re.search(
            r'const\s+searchable\s*=\s*\[(.*?)\]\.filter\(Boolean\)',
            js, re.DOTALL,
        )
        if not match:
            return set()
        return set(re.findall(r'video\.(\w+)', match.group(1)))

    def test_showcase_js_contains(self):
        """searchable array 含所有必要欄位"""
        js = self._js()
        fields = self._extract_searchable_fields(js)
        assert fields, "showcase/state-videos.js: cannot find 'const searchable = [...].filter(Boolean)'"
        required = {"title", "original_title", "actresses", "number", "maker", "tags",
                    "release_date", "path", "director", "series", "label", "user_tags"}
        missing = required - fields
        assert not missing, f"showcase/state-videos.js searchable missing: {sorted(missing)}"


SETTINGS_HTML = Path(__file__).parent.parent.parent / "web" / "templates" / "settings.html"
SCANNER_HTML = Path(__file__).parent.parent.parent / "web" / "templates" / "scanner.html"
SCANNER_SCAN_JS  = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "scanner" / "state-scan.js"
SCANNER_BATCH_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "scanner" / "state-batch.js"
SCANNER_ALIAS_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "scanner" / "state-alias.js"
SCANNER_MAIN_JS  = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "scanner" / "main.js"
MOTION_LAB_HTML = Path(__file__).parent.parent.parent / "web" / "templates" / "motion_lab.html"
DESIGN_SYSTEM_HTML = Path(__file__).parent.parent.parent / "web" / "templates" / "design-system.html"
THEME_CSS = Path(__file__).parent.parent.parent / "web" / "static" / "css" / "theme.css"
TAILWIND_CSS = Path(__file__).parent.parent.parent / "web" / "static" / "css" / "tailwind.css"


class TestHelpPopoverGuard:
    """38e: help-popover CSS class usage guard (method folded)"""

    def _settings(self):
        return SETTINGS_HTML.read_text(encoding="utf-8")

    def _scanner(self):
        return SCANNER_HTML.read_text(encoding="utf-8")

    def test_settings_html_contains(self):
        """settings.html 含 help-popover classes >=2; 無 broken shadow token"""
        html = self._settings()
        assert html.count('class="help-popover"') >= 2, \
            "settings.html missing: 'class=\"help-popover\"' (x2)"
        assert html.count('class="help-popover-btn"') >= 2, \
            "settings.html missing: 'class=\"help-popover-btn\"' (x2)"
        assert "box-shadow: var(--shadow-4)" not in html, \
            "settings.html should not contain: 'box-shadow: var(--shadow-4)'"

    def test_scanner_html_contains(self):
        """scanner.html 含 help-popover classes; 無 broken shadow token"""
        html = self._scanner()
        assert html.count('class="help-popover"') >= 1, \
            "scanner.html missing: 'class=\"help-popover\"'"
        assert html.count('class="help-popover-btn"') >= 1, \
            "scanner.html missing: 'class=\"help-popover-btn\"'"
        assert "box-shadow: var(--shadow-4)" not in html, \
            "scanner.html should not contain: 'box-shadow: var(--shadow-4)'"


class TestInlineStyleCleanup:
    """T4 守衛：確認 inline style 已清理為 CSS class"""

    def _settings(self):
        return SETTINGS_HTML.read_text(encoding="utf-8")

    def _motion_lab(self):
        return MOTION_LAB_HTML.read_text(encoding="utf-8")

    def _design_system(self):
        return DESIGN_SYSTEM_HTML.read_text(encoding="utf-8")

    def test_settings_no_inline_position_relative_for_popover(self):
        """settings.html 不應有 style="position: relative;" 用於 popover 錨點"""
        html = self._settings()
        assert 'style="position: relative;"' not in html, \
            'settings.html 仍含 style="position: relative;"，應改用 class="... popover-anchor"'

    # test_theme_css_no_scoped_manual_input removed in T55b — superseded by
    # stylelint `selector-disallowed-list` rule (/:is\([^)]*manual-input/).

    def test_motion_lab_no_inline_object_fit(self):
        """motion_lab.html 不應有 inline object-fit:cover"""
        html = self._motion_lab()
        # 在 style= 屬性中尋找 object-fit:cover 或 object-fit: cover
        import re
        pattern = re.compile(r'style=["\'][^"\']*object-fit\s*:\s*cover[^"\']*["\']')
        matches = pattern.findall(html)
        assert len(matches) == 0, \
            f"motion_lab.html 仍有 {len(matches)} 處 inline object-fit:cover，應改用 class=\"img-cover-fill\""

    def test_design_system_no_inline_bg_card_pattern(self):
        """design-system.html 不應有 inline padding + background: var(--bg-card) + border-radius 三合一 pattern"""
        html = self._design_system()
        import re
        # 找 style= 屬性中同時含 padding（1rem 或 1.5rem 2rem）+ background: var(--bg-card) + border-radius: var(--radius-md) 的
        # 這 7 處的 padding 值為 "1rem 1.5rem" 或 "1.5rem 2rem"，且只有這 3 個屬性（無 max-width、box-shadow 等額外屬性）
        pattern = re.compile(
            r'style=["\']padding:\s*(?:1(?:\.5)?rem\s+(?:1\.5rem|2rem)|1rem\s+1\.5rem);\s*background:\s*var\(--bg-card\);\s*border-radius:\s*var\(--radius-md\);["\']'
        )
        matches = pattern.findall(html)
        assert len(matches) == 0, \
            f"design-system.html 仍有 {len(matches)} 處 padding+bg-card+border-radius inline pattern，應改用 class=\"... ds-demo-panel\""


BATCH_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "batch.js"
SEARCH_FLOW_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "search-flow.js"
BASE_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "base.js"
SETTINGS_CONFIG_JS    = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "settings" / "state-config.js"
SETTINGS_PROVIDERS_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "settings" / "state-providers.js"
SETTINGS_UI_JS        = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "settings" / "state-ui.js"
SEARCH_FILE_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "file.js"


class TestBatchIntervalGuard:
    """T1(40b): 守衛 batch/translate checkInterval 具名 ref + cleanupForNavigation 明確清理"""

    def _batch(self):
        return BATCH_JS.read_text(encoding="utf-8")

    def _search_flow(self):
        return SEARCH_FLOW_JS.read_text(encoding="utf-8")

    def _base(self):
        return BASE_JS.read_text(encoding="utf-8")

    def test_batch_check_interval_assigned(self):
        """batch.js searchAll() 使用 this._batchCheckInterval = setInterval"""
        js = self._batch()
        assert "this._batchCheckInterval = setInterval" in js, \
            "batch.js searchAll() 應將 setInterval 賦值給 this._batchCheckInterval（具名 ref）"

    def test_translate_check_interval_assigned(self):
        """batch.js translateAll() 使用 this._translateCheckInterval = setInterval"""
        js = self._batch()
        assert "this._translateCheckInterval = setInterval" in js, \
            "batch.js translateAll() 應將 setInterval 賦值給 this._translateCheckInterval（具名 ref）"

    def test_batch_interval_self_clear(self):
        """batch.js searchAll() 內 clearInterval(this._batchCheckInterval) 自清"""
        js = self._batch()
        assert "clearInterval(this._batchCheckInterval)" in js, \
            "batch.js searchAll() 應在條件成立時 clearInterval(this._batchCheckInterval)"

    def test_translate_interval_self_clear(self):
        """batch.js translateAll() 內 clearInterval(this._translateCheckInterval) 自清"""
        js = self._batch()
        assert "clearInterval(this._translateCheckInterval)" in js, \
            "batch.js translateAll() 應在條件成立時 clearInterval(this._translateCheckInterval)"

    def test_cleanup_clears_batch_interval(self):
        """search-flow.js cleanupForNavigation() 明確清除 this._batchCheckInterval"""
        js = self._search_flow()
        assert "clearInterval(this._batchCheckInterval)" in js, \
            "search-flow.js cleanupForNavigation() 應明確 clearInterval(this._batchCheckInterval)"

    def test_cleanup_clears_translate_interval(self):
        """search-flow.js cleanupForNavigation() 明確清除 this._translateCheckInterval"""
        js = self._search_flow()
        assert "clearInterval(this._translateCheckInterval)" in js, \
            "search-flow.js cleanupForNavigation() 應明確 clearInterval(this._translateCheckInterval)"

    def test_base_declares_batch_check_interval(self):
        """base.js state 初始化包含 _batchCheckInterval 欄位"""
        js = self._base()
        assert "_batchCheckInterval" in js, \
            "base.js 應在初始 state 宣告 _batchCheckInterval: null"

    def test_base_declares_translate_check_interval(self):
        """base.js state 初始化包含 _translateCheckInterval 欄位"""
        js = self._base()
        assert "_translateCheckInterval" in js, \
            "base.js 應在初始 state 宣告 _translateCheckInterval: null"


MAIN_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "main.js"


class TestTimerListenerGuard:
    """T2(40b): 守衛 main.js window listener 具名 ref + cleanup removeEventListener"""

    def _index(self):
        return MAIN_JS.read_text(encoding="utf-8")

    def _base(self):
        return BASE_JS.read_text(encoding="utf-8")

    def test_index_uses_set_timer_for_cover_height(self):
        """main.js $watch('searchResults') 使用 _setTimer('updateCoverHeight'"""
        js = self._index()
        assert "_setTimer('updateCoverHeight'" in js, \
            "main.js $watch('searchResults') 應改用 _setTimer('updateCoverHeight', ...) 取代裸 setTimeout"

    def test_index_no_bare_settimeout_for_cover_height(self):
        """main.js 不含裸 setTimeout(() => this._updateCoverHeight()"""
        js = self._index()
        assert "setTimeout(() => this._updateCoverHeight()" not in js, \
            "main.js 仍含裸 setTimeout(() => this._updateCoverHeight()，應改為 _setTimer"

    def test_index_pywebview_handler_assigned(self):
        """main.js pywebview-files listener 賦值給 this._pywebviewFilesHandler"""
        js = self._index()
        assert "this._pywebviewFilesHandler =" in js, \
            "main.js 應將 pywebview-files handler 賦值給 this._pywebviewFilesHandler（具名 ref）"

    def test_index_resize_handler_assigned(self):
        """main.js resize listener 賦值給 this._resizeHandler"""
        js = self._index()
        assert "this._resizeHandler =" in js, \
            "main.js 應將 resize handler 賦值給 this._resizeHandler（具名 ref）"

    def test_index_cleanup_removes_pywebview_listener(self):
        """main.js cleanup() 含 removeEventListener('pywebview-files', this._pywebviewFilesHandler)"""
        js = self._index()
        assert "removeEventListener('pywebview-files', this._pywebviewFilesHandler)" in js, \
            "main.js cleanup() 應 removeEventListener('pywebview-files', this._pywebviewFilesHandler)"

    def test_index_cleanup_removes_resize_listener(self):
        """main.js cleanup() 含 removeEventListener('resize', this._resizeHandler)"""
        js = self._index()
        assert "removeEventListener('resize', this._resizeHandler)" in js, \
            "main.js cleanup() 應 removeEventListener('resize', this._resizeHandler)"

    def test_base_declares_pywebview_handler(self):
        """base.js state 初始化包含 _pywebviewFilesHandler 欄位"""
        js = self._base()
        assert "_pywebviewFilesHandler" in js, \
            "base.js 應在初始 state 宣告 _pywebviewFilesHandler: null"

    def test_base_declares_resize_handler(self):
        """base.js state 初始化包含 _resizeHandler 欄位"""
        js = self._base()
        assert "_resizeHandler" in js, \
            "base.js 應在初始 state 宣告 _resizeHandler: null"


class TestSettingsCleanupBypassGuard:
    """T3(40b): 確保 dirtyCheckDiscard() 使用 __leavePage 而非直接跳轉"""

    def _js(self):
        return SETTINGS_UI_JS.read_text(encoding="utf-8")

    def test_dirty_check_discard_uses_leave_page(self):
        """dirtyCheckDiscard() 呼叫 window.__leavePage"""
        js = self._js()
        assert "window.__leavePage" in js, \
            "settings.js dirtyCheckDiscard() 應使用 window.__leavePage 而非直接設定 window.location.href"

    def test_dirty_check_discard_has_location_fallback(self):
        """dirtyCheckDiscard() 保留 window.location.href fallback"""
        js = self._js()
        assert "window.location.href" in js, \
            "settings.js dirtyCheckDiscard() 應保留 window.location.href 作為 fallback"

    def test_dirty_check_discard_calls_leave_page_with_url(self):
        """dirtyCheckDiscard() 以 pendingNavigationUrl 呼叫 __leavePage"""
        js = self._js()
        assert "window.__leavePage(this.pendingNavigationUrl)" in js, \
            "settings.js dirtyCheckDiscard() 應以 this.pendingNavigationUrl 呼叫 window.__leavePage"

    def test_dirty_check_discard_gates_on_leave_page_return(self):
        """dirtyCheckDiscard() 使用 !window.__leavePage(...) gate（回傳 false 時阻止導航）"""
        js = self._js()
        assert "if (!window.__leavePage(this.pendingNavigationUrl)) return;" in js, \
            "settings.js dirtyCheckDiscard() 應在 __leavePage 回傳 false 時 return（阻止導航）"

    def test_dirty_check_save_calls_leave_page_with_url(self):
        """dirtyCheckSave() 儲存成功後也透過 __leavePage gate 再跳轉"""
        js = self._js()
        # dirtyCheckSave 在 isDirty 為 false 後跳轉，需同樣呼叫 __leavePage
        # 至少出現兩次（dirtyCheckDiscard 一次 + dirtyCheckSave 一次）
        count = js.count("window.__leavePage(this.pendingNavigationUrl)")
        assert count >= 2, \
            (f"settings.js dirtyCheckSave() 也應使用 window.__leavePage(this.pendingNavigationUrl) gate，"
             f"目前只有 {count} 處")

    def test_dirty_check_save_gates_on_leave_page_return(self):
        """dirtyCheckSave() 使用 !window.__leavePage(...) gate（回傳 false 時阻止導航）"""
        js = self._js()
        # 同一個 gate pattern 在檔案中出現至少兩次
        count = js.count("if (!window.__leavePage(this.pendingNavigationUrl)) return;")
        assert count >= 2, \
            (f"settings.js dirtyCheckSave() 也應在 __leavePage 回傳 false 時 return，"
             f"目前只有 {count} 處")


LOCALES_ROOT = Path(__file__).parent.parent.parent / "locales"


class TestJellyfinCheckManualGuard:
    """40c-T2: 守衛 Jellyfin check 改為手動觸發的所有前端不變式"""

    def _html(self):
        return SCANNER_HTML.read_text(encoding="utf-8")

    def _js(self):
        return SCANNER_SCAN_JS.read_text(encoding="utf-8")

    def test_no_auto_trigger_in_init(self):
        """init() 後的 loadStats 呼叫後，不應緊接 checkJellyfinImages()"""
        # 確認 checkJellyfinImages() 只透過 @click 觸發，不在 init() 或 loadStats 後出現
        js = self._js()
        assert "this.loadStats();\n        this.checkJellyfinImages();" not in js, \
            "scanner.js init() 仍含自動觸發 checkJellyfinImages()"

    def test_jellyfin_check_state_declared(self):
        """Alpine data 宣告 jellyfinCheckState 欄位"""
        js = self._js()
        assert "jellyfinCheckState: 'idle'" in js, \
            "scanner.js 缺少 jellyfinCheckState: 'idle' 初始化宣告"

    def test_jellyfin_check_controller_declared(self):
        """Alpine data 宣告 _jellyfinCheckController 欄位"""
        js = self._js()
        assert "_jellyfinCheckController: null" in js, \
            "scanner.js 缺少 _jellyfinCheckController: null 初始化宣告"

    def test_abort_controller_used_in_check(self):
        """checkJellyfinImages() 建立 AbortController"""
        js = self._js()
        assert "new AbortController()" in js, \
            "scanner.js checkJellyfinImages() 缺少 new AbortController()"

    def test_abort_called_in_cleanup(self):
        """cleanup 回呼內含 _jellyfinCheckController.abort()"""
        js = self._js()
        assert "_jellyfinCheckController.abort()" in js, \
            "scanner.js cleanup 缺少 _jellyfinCheckController.abort()"

    def test_jellyfin_check_state_reset_in_cleanup(self):
        """cleanup 回呼補上 jellyfinCheckState = 'idle' 重設"""
        js = self._js()
        assert "jellyfinCheckState = 'idle'" in js, \
            "scanner.js cleanup 缺少 jellyfinCheckState = 'idle' 重設"

    def test_should_warn_checks_jellyfin_checking(self):
        """shouldWarnBeforeLeave() 含 jellyfinCheckState === 'checking' 判斷"""
        js = self._js()
        assert "jellyfinCheckState === 'checking'" in js, \
            "scanner.js shouldWarnBeforeLeave() 缺少 jellyfinCheckState === 'checking' 判斷"

    def test_trigger_button_click_handler(self):
        """觸發按鈕 @click 呼叫 checkJellyfinImages()"""
        html = self._html()
        assert '@click="checkJellyfinImages()"' in html, \
            "scanner.html 缺少 @click=\"checkJellyfinImages()\" 觸發按鈕"

    def test_no_auto_trigger_after_generate(self):
        """generate SSE done 事件後無自動呼叫 checkJellyfinImages()"""
        js = self._js()
        # loadStats 後面不應接 checkJellyfinImages（generate 路徑）
        assert "this.loadStats();\n                    this.checkJellyfinImages();" not in js, \
            "scanner.js generate done 路徑仍自動呼叫 checkJellyfinImages()"

    def test_clear_cache_resets_jellyfin_state(self):
        """clearCache 成功後含 jellyfinCheckState = 'idle' 重設"""
        js = self._js()
        # jellyfinImageVisible = false 後緊接 jellyfinCheckState = 'idle'
        assert "jellyfinImageVisible = false" in js, \
            "scanner.js clearCache 缺少 jellyfinImageVisible = false"
        # jellyfinCheckState = 'idle' 在 clearCache 函數中也必須出現
        # （在 shouldWarnBeforeLeave 和 beforeLeave 都有，此守衛確認 clearCache 路徑有）
        # 用計數確認至少 2 處（cleanup + clearCache，shouldWarnBeforeLeave 判斷不算 assignment）
        count = js.count("jellyfinCheckState = 'idle'")
        assert count >= 2, \
            f"scanner.js jellyfinCheckState = 'idle' 出現 {count} 次，期望 >= 2（cleanup + clearCache）"

    def test_trigger_row_xshow_uses_jellyfin_image_visible(self):
        """T3(40c) Codex fix: 觸發列 x-show 改為 !jellyfinImageVisible 而非 jellyfinCheckState !== 'done'"""
        html = self._html()
        assert "config?.scraper?.jellyfin_mode && !jellyfinImageVisible" in html, \
            "scanner.html 觸發列 x-show 應使用 !jellyfinImageVisible（而非 jellyfinCheckState !== 'done'）"
        assert "config?.scraper?.jellyfin_mode && jellyfinCheckState !== 'done'" not in html, \
            "scanner.html 觸發列 x-show 仍使用舊的 jellyfinCheckState !== 'done' 條件"

    def test_trigger_row_done_state_text_present(self):
        """T3(40c) Codex fix: 觸發列包含 done 狀態顯示文字"""
        html = self._html()
        assert "jellyfinCheckState === 'done'" in html, \
            "scanner.html 觸發列缺少 done 狀態文字顯示"
        assert "jellyfin_check_done_ok" in html, \
            "scanner.html 觸發列缺少 jellyfin_check_done_ok i18n key 引用"

    def test_jellyfin_update_done_resets_check_state(self):
        """T3(40c) Codex fix: jellyfin-update done handler 重設 jellyfinCheckState = 'idle'"""
        js = self._js()
        # 確認 runJellyfinImageUpdate 的 done 分支有三個重設欄位
        assert "this.jellyfinImageVisible = false" in js, \
            "scanner.js runJellyfinImageUpdate done 缺少 jellyfinImageVisible = false 重設"
        assert "this.jellyfinImageCount = 0" in js, \
            "scanner.js runJellyfinImageUpdate done 缺少 jellyfinImageCount = 0 重設"
        # jellyfinCheckState = 'idle' 重設（update done 分支使用 this. 前綴）
        assert "this.jellyfinCheckState = 'idle'" in js, \
            "scanner.js runJellyfinImageUpdate done 缺少 this.jellyfinCheckState = 'idle' 重設"


class TestJellyfinCheckI18nKeys:
    """40c-T2: 確認新增 i18n key 存在於 zh_TW.json"""

    REQUIRED_KEYS = [
        "scanner.stats.jellyfin_check_btn",
        "scanner.stats.jellyfin_check_idle_label",
        "scanner.stats.jellyfin_checking",
    ]

    def _zh_tw(self):
        return json.loads((LOCALES_ROOT / "zh_TW.json").read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_jellyfin_i18n_keys_exist(self):
        """zh_TW.json 包含 40c 所有 jellyfin check i18n key"""
        zh_tw = self._zh_tw()
        for key in self.REQUIRED_KEYS + ["scanner.stats.jellyfin_check_done_ok"]:
            val = self._get_nested(zh_tw, key)
            assert val, f"zh_TW.json missing: {key!r}"


class TestShowcaseKeyboardGuard:
    """Phase 40d-T2: Showcase 鍵盤 preventDefault 守衛"""

    CORE_JS = SHOWCASE_LIGHTBOX_JS

    def _extract_block(self, content, anchor, end_marker='return;'):
        """提取從 anchor 到 end_marker 的區塊"""
        start = content.find(anchor)
        if start == -1:
            return ''
        end = content.find(end_marker, start)
        if end == -1:
            return content[start:]
        return content[start:end + len(end_marker)]

    def test_sample_gallery_keyboard_has_prevent_default(self):
        """sample gallery keyboard 分支應有 e.preventDefault()"""
        content = self.CORE_JS.read_text(encoding='utf-8')
        block = self._extract_block(content, 'if (this.sampleGalleryOpen)')
        assert 'e.preventDefault()' in block, \
            "sample gallery keyboard 分支缺少 e.preventDefault()"

    def test_lightbox_keyboard_has_prevent_default(self):
        """lightbox keyboard 分支應有 e.preventDefault()"""
        content = self.CORE_JS.read_text(encoding='utf-8')
        # 使用鍵盤 handler 特有的注釋行作為錨，避免誤中 cleanup 裡的 if (this.lightboxOpen)
        block = self._extract_block(content, '// 5. Lightbox 開啟時的快捷鍵')
        assert 'e.preventDefault()' in block, \
            "lightbox keyboard 分支缺少 e.preventDefault()"


class TestShowcaseActressState:
    """Phase 44a-T2: Showcase 女優模式 Alpine state 守衛"""

    def _js(self):
        # 女優 state 分散於 state-base/actress/lightbox，合併讀取確保覆蓋
        return (
            SHOWCASE_BASE_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_LIGHTBOX_JS.read_text(encoding="utf-8")
        )

    def test_actress_js_contains(self):
        """state 屬性、module-level 陣列、method 名、互斥 reset、saveState/restoreState、keydown 全部存在"""
        js = self._js()
        for expected in [
            # module-level arrays
            "var _actresses = []",
            "var _filteredActresses = []",
            # Alpine state properties
            "showFavoriteActresses",
            "actressCount",
            "filteredActressCount",
            "paginatedActresses",
            "actressSearch",
            "actressSort",
            "actressOrder",
            "actressLoading",
            "actressLightboxIndex",
            "currentLightboxActress",
            "_actressChipsExpanded",
            "_addActressName",
            "_addingActress",
            "_addDropdownOpen",
            "_videoChipsExpanded",
            # core methods
            "toggleActressMode",
            "loadActresses",
            "applyActressFilterAndSort",
            "onActressSearchChange",
            "onActressSortChange",
            "toggleActressOrder",
            # lightbox methods
            "openActressLightbox",
            "closeActressLightbox",
            "prevActressLightbox",
            "nextActressLightbox",
            "_setActressLightboxIndex",
            # sort logic
            "cupRank",
            # mutual exclusion
            "currentLightboxActress = null",
            "_videoChipsExpanded = false",
            # saveState / restoreState
            "_persistedShowcase.showFavoriteActresses = this.showFavoriteActresses",
            "_persistedShowcase.actressSort = this.actressSort",
            "_persistedShowcase.actressOrder = this.actressOrder",
            "showFavoriteActresses === true",
            "state.actressSort",
            "state.actressOrder",
            # handleKeydown
            "this.currentLightboxActress",
            "this.prevActressLightbox()",
            "this.nextActressLightbox()",
        ]:
            assert expected in js, \
                f"showcase/core.js (state-base/actress/lightbox) missing: {expected!r}"

    def test_actress_js_excludes(self):
        """_rescraping 不應存在（49b-T5 已刪除 rescrape dead code）"""
        js = self._js()
        for forbidden in ["_rescraping"]:
            assert forbidden not in js, \
                f"showcase/core.js should not contain: {forbidden!r}"


class TestActressLightboxSourceGuard:
    """49a-T5: Actress Lightbox source state guard（CD-9 顯式 state 取代物件 identity 判斷）

    驗證：
    - init state 含 actressLightboxSource: null
    - openHeroCardLightbox 函數體設 'hero'
    - openActressLightbox 函數體至少 2 處設 'grid'（首次進入 + 切換女優分支）
    - closeLightbox 函數體 reset null
    - showcase.html camera button 含 x-show="actressLightboxSource === 'grid'"
    """

    def _js(self):
        # actressLightboxSource / openActressLightbox / closeLightbox / handleKeydown → state-lightbox.js
        # openHeroCardLightbox → state-lightbox.js
        return (
            SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_LIGHTBOX_JS.read_text(encoding="utf-8")
        )

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def _extract_method_body(self, js, method_name):
        """抓取 Alpine state method（methodName(...) { ... }）函式主體，大括號平衡。"""
        pattern = re.compile(
            r'(?:^|\n)\s*' + re.escape(method_name) + r'\s*\([^)]*\)\s*\{',
            re.DOTALL,
        )
        m = pattern.search(js)
        assert m is not None, f"showcase/core.js 找不到 {method_name} 方法"
        start = m.end()  # 位於 { 之後
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            c = js[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            i += 1
        return js[start:i - 1]

    def test_source_state_init_and_html(self):
        """core.js Alpine state 含 actressLightboxSource: null；showcase.html camera button 含 grid 綁定"""
        js = self._js()
        assert re.search(r'actressLightboxSource\s*:\s*null', js), \
            "showcase/core.js missing: actressLightboxSource: null (Alpine state init)"
        html = self._html()
        assert "actressLightboxSource === 'grid'" in html, \
            "showcase.html missing: actressLightboxSource === 'grid' (camera button x-show binding)"

    def test_source_set_in_open_methods(self):
        """openHeroCardLightbox 設 'hero'；closeLightbox reset null"""
        js = self._js()
        for method_name, pattern, msg in [
            (
                'openHeroCardLightbox',
                r"this\.actressLightboxSource\s*=\s*['\"]hero['\"]",
                "openHeroCardLightbox 函數體缺少 this.actressLightboxSource = 'hero'",
            ),
            (
                'closeLightbox',
                r"this\.actressLightboxSource\s*=\s*null",
                "closeLightbox 函數體缺少 this.actressLightboxSource = null（reset）",
            ),
        ]:
            body = self._extract_method_body(js, method_name)
            assert re.search(pattern, body), \
                f"showcase/core.js {method_name} missing: {msg}"

    def test_open_actress_lightbox_sets_grid(self):
        """openActressLightbox 函數體至少 2 處設 'grid'（首次進入 + 切換女優分支）"""
        js = self._js()
        body = self._extract_method_body(js, 'openActressLightbox')
        matches = re.findall(r"this\.actressLightboxSource\s*=\s*['\"]grid['\"]", body)
        assert len(matches) >= 2, \
            f"showcase/core.js openActressLightbox 應至少 2 處設 'grid'（首次進入 + 切換女優），目前 {len(matches)} 處"


class TestShowcasePreciseMatchState:
    """Phase 44b-T1: Showcase 精準匹配 Alpine state 守衛（method folded）"""

    def _js(self):
        return (
            SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_VIDEOS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_BASE_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_LIGHTBOX_JS.read_text(encoding="utf-8")
        )

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def test_actress_js_contains(self):
        """state 屬性、methods、trigger points、stale guard 全部存在"""
        js = self._js()
        for expected in [
            # module-level flag
            "var _actressesLoaded",
            # Alpine state properties
            "_isPreciseActressMatch",
            "_matchedActress",
            "_preciseMatchSource",
            "_favoriteHeartLoading",
            # methods
            "_checkPreciseActressMatch",
            "_clearPreciseMatch",
            # trigger points (checked globally)
            "_checkPreciseActressMatch",
            "_clearPreciseMatch",
            # stale guard
            "capturedTerm",
            # heart method
            "addFavoriteFromSearch",
        ]:
            assert expected in js, f"showcase/core.js missing: {expected!r}"
        # lazy load flag
        assert ("_actressesLoaded = true" in js or "_setActressesLoaded(true)" in js), \
            "showcase state missing: _actressesLoaded set to true"
        # _favoriteHeartLoading used in addFavoriteFromSearch
        idx = js.find("addFavoriteFromSearch")
        assert idx != -1, "showcase/core.js missing: 'addFavoriteFromSearch'"
        block = js[idx:idx+2000]
        assert "_favoriteHeartLoading" in block, \
            "addFavoriteFromSearch missing: '_favoriteHeartLoading'"

    def test_actress_html_contains(self):
        """showcase.html 含 addFavoriteFromSearch 和 _isPreciseActressMatch"""
        html = self._html()
        for expected in ["addFavoriteFromSearch", "_isPreciseActressMatch"]:
            assert expected in html, f"showcase.html missing: {expected!r}"

class TestGeminiLocaleKeyGuard:
    """39a-T3: 守衛 settings.js 不再使用 gemini_n_flash_models locale key"""

    def _js(self):
        return SETTINGS_PROVIDERS_JS.read_text(encoding="utf-8")

    def test_settings_js_no_gemini_n_flash_models(self):
        """settings.js 不應出現 gemini_n_flash_models（已替換為 connected_n_models）"""
        js = self._js()
        assert "gemini_n_flash_models" not in js, \
            "settings.js 仍含 gemini_n_flash_models，應改為 connected_n_models"


GRID_MODE_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "grid-mode.js"


class TestLoadMoreButton:
    """39a-T4: Load More button + hasMoreResults + loadMore trigger (method folded)"""

    def _locale(self, name):
        return json.loads((LOCALES_ROOT / name).read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_html_and_js_contains(self):
        """search.html + base/grid-mode/navigation/animations JS 含 load more 所有必要字串"""
        html = SEARCH_HTML.read_text(encoding="utf-8")
        for expected in [
            '@click="gridLoadMore()"',
            "t('search.button.load_more')",
            "hasMoreResults && displayMode === 'grid'",
        ]:
            assert expected in html, f"search.html missing: {expected!r}"
        base = BASE_JS.read_text(encoding="utf-8")
        assert "hasMoreResults" in base, "base.js missing: 'hasMoreResults'"
        gm = GRID_MODE_JS.read_text(encoding="utf-8")
        assert "await this.loadMore('lightbox')" in gm, \
            "grid-mode.js missing: \"await this.loadMore('lightbox')\""
        nav = NAVIGATION_JS.read_text(encoding="utf-8")
        for expected in ["async loadMore(trigger", "return { loadedCount", "async gridLoadMore()"]:
            assert expected in nav, f"navigation.js missing: {expected!r}"
        anim = ANIMATIONS_JS.read_text(encoding="utf-8")
        assert "playAppendCascade" in anim, "animations.js missing: 'playAppendCascade'"

    def test_locales_have_load_more_key(self):
        """4 locales 含 search.button.load_more key"""
        for locale_file in ["zh_TW.json", "zh_CN.json", "en.json", "ja.json"]:
            data = self._locale(locale_file)
            val = self._get_nested(data, "search.button.load_more")
            assert val, f"{locale_file} missing: search.button.load_more"


NAVIGATION_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "navigation.js"
ANIMATIONS_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "animations.js"


class TestCodexFixes:
    """39a Codex review 修正守衛"""

    def _navigation_js(self):
        return NAVIGATION_JS.read_text(encoding="utf-8")

    def _settings_js(self):
        return SETTINGS_PROVIDERS_JS.read_text(encoding="utf-8")

    def test_loadmore_no_currentindex_assignment(self):
        """F1：loadMore() 成功分支不含 this.currentIndex = 賦值"""
        js = self._navigation_js()
        # 找到 loadMore 函數體，截取到 finally 區塊結束
        start = js.find("async loadMore(trigger")
        assert start != -1, "navigation.js 找不到 async loadMore(trigger ...) 函數"
        # 截取 loadMore 函數體（到函數結尾）
        func_body = js[start:]
        # 找到 finally { ... } 後的第一個右大括號（函數結束）
        finally_pos = func_body.find("finally {")
        if finally_pos != -1:
            # 截取 loadMore 函數範圍：從函數開始到 finally 區塊後的 } 結尾
            end_pos = func_body.find("}", finally_pos + len("finally {"))
            # 再找外層函數的 }
            end_pos = func_body.find("},", end_pos + 1)
            func_body = func_body[:end_pos] if end_pos != -1 else func_body
        # 確認函數體內不含 this.currentIndex = 賦值（有空格的賦值語句）
        assert "this.currentIndex =" not in func_body, \
            "navigation.js loadMore() 成功分支不應含 this.currentIndex = 賦值（破壞 shared state contract）"

    def test_gemini_model_fallback_includes_check(self):
        """F2：testGeminiConnection() 成功後包含 includes() 檢查舊 model 是否在 allowlist"""
        js = self._settings_js()
        assert "modelNames.includes(this.form.geminiModel)" in js or \
               "includes(this.form.geminiModel)" in js, \
            "settings.js testGeminiConnection() 成功後應含 includes(this.form.geminiModel) allowlist 檢查"


class TestOpenAIErrorI18nGuard:
    """39a-PR-fix P1: 守衛 fetchOpenAIModels/testOpenAITranslation error 使用 window.t(errorKey) 翻譯"""

    def _js(self):
        return SETTINGS_PROVIDERS_JS.read_text(encoding="utf-8")

    def test_fetch_models_error_uses_i18n(self):
        """fetchOpenAIModels() error 分支使用 settings.status.openai_ 動態 errorKey 拼接"""
        js = self._js()
        # 截取 fetchOpenAIModels 函數體
        start = js.find("async fetchOpenAIModels(")
        assert start != -1, "settings.js 找不到 async fetchOpenAIModels( 函數"
        # 截取到下一個 async 函數起點（保守估計）
        next_async = js.find("async ", start + 1)
        func_body = js[start:next_async] if next_async != -1 else js[start:]
        assert "settings.status.openai_" in func_body, \
            "settings.js fetchOpenAIModels() error 分支應包含 settings.status.openai_ 動態 key 拼接"

    def test_translate_error_uses_i18n(self):
        """testOpenAITranslation() error 分支使用 settings.status.openai_ 動態 errorKey 拼接"""
        js = self._js()
        start = js.find("async testOpenAITranslation()")
        assert start != -1, "settings.js 找不到 async testOpenAITranslation() 函數"
        next_async = js.find("async ", start + 1)
        func_body = js[start:next_async] if next_async != -1 else js[start:]
        assert "settings.status.openai_" in func_body, \
            "settings.js testOpenAITranslation() error 分支應包含 settings.status.openai_ 動態 key 拼接"

    def test_fetch_catch_uses_i18n(self):
        """fetchOpenAIModels() catch 分支使用 window.t('settings.status.openai_connection_failed')"""
        js = self._js()
        assert "window.t('settings.status.openai_connection_failed')" in js, \
            "settings.js fetchOpenAIModels() catch 分支應使用 window.t('settings.status.openai_connection_failed')，不顯示裸 error.message"


class TestAutoFetchDirtyStateGuard:
    """39a-PR-fix P2: 守衛 auto-fallback 後同步 savedState，防止誤觸 dirty state"""

    def _js(self):
        return SETTINGS_PROVIDERS_JS.read_text(encoding="utf-8")

    def _config_js(self):
        return SETTINGS_CONFIG_JS.read_text(encoding="utf-8")

    def test_gemini_fallback_syncs_saved_state(self):
        """testGeminiConnection() auto-fallback 後同步 savedState.geminiModel"""
        js = self._js()
        assert "this.savedState.geminiModel" in js, \
            "settings.js testGeminiConnection() auto-fallback 後應同步 this.savedState.geminiModel，否則 isDirty 誤判"

    def test_openai_fallback_syncs_saved_state(self):
        """fetchOpenAIModels() auto-assign 後同步 savedState.openaiModel"""
        js = self._js()
        assert "this.savedState.openaiModel" in js, \
            "settings.js fetchOpenAIModels() auto-assign 後應同步 this.savedState.openaiModel，否則 isDirty 誤判"

    def test_openai_config_saves_use_custom_model(self):
        """saveConfig() openai 區段應含 use_custom_model，以便重載後還原 custom/select 模式"""
        js = self._config_js()
        assert "use_custom_model: this.openaiUseCustomModel" in js, \
            "settings/state-config.js saveConfig() 的 openai 物件應含 use_custom_model: this.openaiUseCustomModel，否則重載後 custom 模式丟失"

    def test_openai_config_loads_use_custom_model(self):
        """loadConfig() 應從 config 還原 openaiUseCustomModel，而非固定從 false 重設"""
        js = self._config_js()
        assert "config.translate.openai?.use_custom_model" in js, \
            "settings/state-config.js loadConfig() 應含 config.translate.openai?.use_custom_model 讀取，否則重載後 custom 模式無法還原"

    def test_fetch_openai_models_has_source_param(self):
        """fetchOpenAIModels() 應接受 source 參數，區分 auto-fetch 與手動 Fetch"""
        js = self._js()
        assert "source = 'manual'" in js, \
            "settings.js fetchOpenAIModels() 應含 source = 'manual' 預設參數，避免共享 boolean 競態"


MOTION_LAB_STATE_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "motion-lab-state.js"


class TestMotionLabStateGuard:
    """39b-T1: motion_lab.html inline x-data 已抽離至 motion-lab-state.js (method folded)"""

    def _html(self):
        return MOTION_LAB_HTML.read_text(encoding="utf-8")

    def _js(self):
        return MOTION_LAB_STATE_JS.read_text(encoding="utf-8")

    def test_motion_lab_html_contains(self):
        """motion_lab.html 含 motionLabPage factory ref + state JS + no inline x-data block"""
        html = self._html()
        for expected in [
            'x-data="motionLabPage"',
            "motion-lab-state.js",
        ]:
            assert expected in html, f"motion_lab.html missing: {expected!r}"
        pattern = re.compile(r'x-data="([^"]{100,})"')
        matches = pattern.findall(html)
        assert len(matches) == 0, \
            f"motion_lab.html has {len(matches)} x-data attributes >100 chars (inline object not removed)"
        # no defer on state script
        tag_pattern = re.compile(r'<script[^>]*motion-lab-state\.js[^>]*>')
        tags = tag_pattern.findall(html)
        assert len(tags) > 0, "motion_lab.html missing: motion-lab-state.js script tag"
        for tag in tags:
            assert "defer" not in tag, \
                f"motion_lab.html motion-lab-state.js script tag should not have defer: {tag}"

    def test_motion_lab_state_js_contains(self):
        """motion-lab-state.js 存在且含必要方法"""
        assert MOTION_LAB_STATE_JS.exists(), \
            f"motion-lab-state.js not found: {MOTION_LAB_STATE_JS}"
        js = self._js()
        for expected in [
            "function motionLabPage()",
            "init()",
            "destroy()",
        ]:
            assert expected in js, f"motion-lab-state.js missing: {expected!r}"


class TestScannerStateGuard:
    """39b-T2: 守衛 scanner.html inline script 已抽離至 scanner.js"""

    def _html(self):
        return SCANNER_HTML.read_text(encoding="utf-8")

    def test_scanner_html_has_pre_alpine_module_block(self):
        """scanner.html 含 pre_alpine_module block override，且含 scanner/main.js module script（54c-T2）"""
        html = self._html()
        assert "pre_alpine_module" in html, \
            "scanner.html 缺少 {% block pre_alpine_module %}（54c-T2 未加入 main.js 載入）"
        assert "scanner/main.js" in html, \
            "scanner.html pre_alpine_module block 缺少 main.js module script"

    def test_scanner_no_inline_script(self):
        """scanner.html 的 extra_js 區段（若存在）不含超過 10 行的 inline script"""
        import re
        html = self._html()
        pattern = re.compile(r'\{%-?\s*block extra_js\s*-?%\}(.*?)\{%-?\s*endblock\s*-?%\}', re.DOTALL)
        match = pattern.search(html)
        if match is None:
            return  # extra_js block 已移除，守衛通過
        block_content = match.group(1)
        # 確認區段內沒有 inline script（只有含 src 的外部 script 標籤）
        inline_scripts = re.findall(r'<script(?:\s[^>]*)?>.*?</script>', block_content, re.DOTALL)
        for script_tag in inline_scripts:
            if 'src=' in script_tag:
                continue
            line_count = script_tag.count('\n') + 1
            assert line_count <= 10, \
                f"scanner.html extra_js 含超過 10 行 inline script（{line_count} 行）"


class TestCtaI18nGuard:
    """39c-T1: 守衛 CTA 文案重構 — 四語系 5 個核心 key 的新值"""

    # 5 個核心 CTA key 的預期新值（各語系）
    EXPECTED = {
        "zh_TW.json": {
            "search.button.search_all": "批次搜尋",
            "search.filelist.scrape_all": "批次整理",
            "search.filelist.scrape_nfo": "整理此片",
            "help.batch.h6_generate_all": "批次整理",
            "search.filelist.scrape_all_title": "整理所有已搜尋的檔案（重命名 + 建資料夾 + NFO）",
        },
        "zh_CN.json": {
            "search.button.search_all": "批量搜索",
            "search.filelist.scrape_all": "批量整理",
            "search.filelist.scrape_nfo": "整理此片",
            "help.batch.h6_generate_all": "批量整理",
            "search.filelist.scrape_all_title": "整理所有已搜索的文件（重命名 + 建文件夹 + NFO）",
        },
        "en.json": {
            "search.button.search_all": "Batch Search",
            "search.filelist.scrape_all": "Batch Organize",
            "search.filelist.scrape_nfo": "Organize",
            "help.batch.h6_generate_all": "Batch Organize",
            "search.filelist.scrape_all_title": "Organize all searched files (rename + folder + NFO)",
        },
        "ja.json": {
            "search.button.search_all": "一括検索",
            "search.filelist.scrape_all": "一括整理",
            "search.filelist.scrape_nfo": "この作品を整理",
            "help.batch.h6_generate_all": "一括整理",
            "search.filelist.scrape_all_title": "検索済みのファイルをすべて整理（リネーム + フォルダ作成 + NFO）",
        },
    }

    def _locale(self, name):
        return json.loads((LOCALES_ROOT / name).read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_all_locales_cta_keys(self):
        """四語系 5 個 CTA key 新值正確"""
        for locale_file, keys in self.EXPECTED.items():
            data = self._locale(locale_file)
            for key, expected in keys.items():
                actual = self._get_nested(data, key)
                assert actual == expected, \
                    f"{locale_file} missing: {key!r} expected {expected!r}, got {actual!r}"


class TestScrapeProgressI18nGuard:
    """39c-T2b: 守衛 scrape progress 進度文字 — 四語系 organizing_prefix key"""

    EXPECTED = {
        "zh_TW.json": {
            "search.filelist.organizing_prefix": "整理中",
        },
        "zh_CN.json": {
            "search.filelist.organizing_prefix": "整理中",
        },
        "en.json": {
            "search.filelist.organizing_prefix": "Organizing",
        },
        "ja.json": {
            "search.filelist.organizing_prefix": "整理中",
        },
    }

    def _locale(self, name):
        return json.loads((LOCALES_ROOT / name).read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_all_locales_have_organizing_prefix(self):
        """四語系 JSON 都有 search.filelist.organizing_prefix key 且值正確"""
        for locale_file, keys in self.EXPECTED.items():
            data = self._locale(locale_file)
            for key, expected in keys.items():
                actual = self._get_nested(data, key)
                assert actual is not None, \
                    f"{locale_file} 缺少 key: {key}"
                assert actual != "", \
                    f"{locale_file} {key} 值不可為空字串"
                assert actual == expected, \
                    f"{locale_file} {key} 期望 {expected!r}，實際 {actual!r}"

    def test_search_html_uses_organizing_prefix(self):
        """search.html 包含 organizing_prefix 字串（確認 HTML 已引用此 key）"""
        search_html = (LOCALES_ROOT.parent / "web" / "templates" / "search.html").read_text(encoding="utf-8")
        assert "organizing_prefix" in search_html, \
            "search.html 未引用 search.filelist.organizing_prefix（請確認 scrape progress section 已插入）"




class TestScrapeToastI18nGuard:
    """39c-T2c: 守衛批次完成 toast — 四語系 7 個 search.toast.* keys 存在且非空"""

    EXPECTED_KEYS = [
        'no_searchable_files',
        'search_complete',
        'no_scrapable_files',
        'scrape_complete',
        'scrape_complete_dup',
        'no_search_results',
        'scrape_failed',
    ]

    def _locale(self, name):
        return json.loads((LOCALES_ROOT / name).read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_all_locales_have_toast_keys(self):
        """四語系 search.toast.* 必須全部存在且非空"""
        for locale in ['zh_TW', 'zh_CN', 'en', 'ja']:
            data = self._locale(f"{locale}.json")
            for key in self.EXPECTED_KEYS:
                dotted = f"search.toast.{key}"
                val = self._get_nested(data, dotted)
                assert val is not None, \
                    f"{locale}.json missing: {dotted!r}"
                assert isinstance(val, str) and len(val) > 0, \
                    f"{locale}.json {dotted!r} must not be empty string"


SEARCH_STATE_DIR = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state"


class TestNoAlertInSearchJs:
    """39c-T2c + T3.6: search/scanner/settings JS 不應使用原生 alert()，改用 showToast / fluent-modal
    (A-class alert tests removed in T55c; clipboard E-class tests retained below)
    """

    def test_scanner_clipboard_has_availability_guard(self):
        """T3.6 P2 fix: scanner/state-scan.js 兩處 clipboard call 必須有 availability guard

        navigator.clipboard 在 HTTP / 舊 WebView 為 undefined，
        若直接呼叫 navigator.clipboard.writeText(...) 會在 property access 階段
        sync throw TypeError，.then().catch() chain 的 .catch 完全不會跑，
        導致 copyLogs 的 fail modal / copyOutputPath 的 error toast 被跳過。
        守衛 if (!navigator.clipboard?.writeText) 必須在兩處 clipboard call 之前。
        """
        content = SCANNER_SCAN_JS.read_text(encoding="utf-8")
        # 兩處 copy 點都應該有 ?. optional chaining guard
        guard_count = content.count("navigator.clipboard?.writeText")
        assert guard_count >= 2, (
            f"scanner/state-scan.js 應該有至少 2 處 navigator.clipboard?.writeText 守衛 "
            f"（copyLogs + copyOutputPath），目前只有 {guard_count} 處。"
            "若沒守衛，clipboard API 不存在時 .catch() 完全不會觸發。"
        )

    def test_all_clipboard_writetext_files_have_availability_guard(self):
        """T3.7: 全 web/static/js 任何使用 navigator.clipboard.writeText 的檔案
        必須同時含 ?. optional chaining 守衛形式（navigator.clipboard?.writeText）。

        此守衛防止未來新檔案再犯同類 pre-existing bug（HTTP / 舊 WebView
        clipboard undefined 時 sync TypeError 跳過 .catch chain）。
        既知合法檔（截至 T3.7）：scanner.js（×2 + ×2 guards）、help.js、
        result-card.js、showcase/core.js — 全部含 ?. 守衛形式。
        """
        js_root = Path(__file__).parent.parent.parent / "web" / "static" / "js"
        offenders = []
        for js_file in js_root.rglob("*.js"):
            text = js_file.read_text(encoding="utf-8")
            if "navigator.clipboard.writeText" not in text:
                continue
            if "navigator.clipboard?.writeText" not in text:
                offenders.append(str(js_file.relative_to(js_root)))
        assert not offenders, (
            f"以下檔案使用 navigator.clipboard.writeText 但缺 ?. 守衛形式："
            f"{offenders}。"
            "請改寫成 if (!navigator.clipboard?.writeText) { ...fallback...; return; } "
            "或 navigator.clipboard?.writeText ? ... : fallback 三元，"
            "避免 clipboard undefined 時 sync TypeError 跳過 .catch。"
        )


class TestNavigateLoadMore:
    """T3b: navigate() loadMore + state-first slide (method folded)"""

    NAVIGATION_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "navigation.js"

    def _js(self):
        return self.NAVIGATION_JS.read_text(encoding="utf-8")

    def _navigate_body(self):
        js = self._js()
        start = js.find("navigate(delta)")
        assert start != -1, "navigation.js missing: 'navigate(delta)'"
        return js[start:start + 3000]

    def test_navigate_js_contains(self):
        """navigation.js navigate() 含 async + loadMore"""
        js = self._js()
        assert "async navigate(delta)" in js, "navigation.js missing: 'async navigate(delta)'"
        body = self._navigate_body()
        for expected in ["await this.loadMore('detail')", "this.currentIndex = result.oldLength"]:
            assert expected in body, f"navigation.js navigate() missing: {expected!r}"

    def test_navigate_state_before_slide_in(self):
        """navigate(): currentIndex update before playSlideIn (state-first)"""
        body = self._navigate_body()
        state_pos = body.find("this.currentIndex = result.oldLength")
        slide_in_pos = body.find("playSlideIn", state_pos if state_pos != -1 else 0)
        assert state_pos != -1 and slide_in_pos != -1, \
            "navigation.js navigate() missing state update or playSlideIn"
        assert state_pos < slide_in_pos, \
            "navigation.js navigate(): currentIndex must update before playSlideIn"


class TestNextLightboxLoadMore:
    """T3c: nextLightboxVideo() loadMore + state-first crossfade (method folded)"""

    def _js(self):
        return GRID_MODE_JS.read_text(encoding="utf-8")

    def _next_lightbox_body(self):
        js = self._js()
        start = js.find("nextLightboxVideo()")
        assert start != -1, "grid-mode.js missing: 'nextLightboxVideo()'"
        return js[start:start + 3000]

    def test_next_lightbox_js_contains(self):
        """grid-mode.js nextLightboxVideo() 含 async + loadMore + state updates"""
        js = self._js()
        assert "async nextLightboxVideo()" in js, \
            "grid-mode.js missing: 'async nextLightboxVideo()'"
        body = self._next_lightbox_body()
        for expected in [
            "await this.loadMore('lightbox')",
            "this.currentIndex = result.oldLength",
            "this.lightboxIndex = result.oldLength",
        ]:
            assert expected in body, f"grid-mode.js nextLightboxVideo() missing: {expected!r}"

    def test_next_lightbox_state_before_switch(self):
        """T3c: currentIndex update before playLightboxSwitch (state-first)"""
        body = self._next_lightbox_body()
        state_pos = body.find("this.currentIndex = result.oldLength")
        switch_pos = body.find("playLightboxSwitch", state_pos if state_pos != -1 else 0)
        assert state_pos != -1, "grid-mode.js nextLightboxVideo() missing: 'this.currentIndex = result.oldLength'"
        assert switch_pos != -1, \
            "grid-mode.js nextLightboxVideo() missing: 'playLightboxSwitch'"
        assert state_pos < switch_pos, \
            "grid-mode.js nextLightboxVideo(): currentIndex must update before playLightboxSwitch"


RESULT_CARD_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "result-card.js"
PATH_UTILS_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "components" / "path-utils.js"
FILE_LIST_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "search" / "state" / "file-list.js"


class TestUserTagsApiGuard:
    """41b-T3: 確保 confirmAddTag 和 removeUserTag 改接 /api/user-tags API（method folded）"""

    def _result_card(self):
        return RESULT_CARD_JS.read_text(encoding="utf-8")

    def _path_utils(self):
        return PATH_UTILS_JS.read_text(encoding="utf-8")

    def _html(self):
        return SEARCH_HTML.read_text(encoding="utf-8")

    def _locale(self, name):
        return json.loads((LOCALES_ROOT / name).read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_result_card_js_contains(self):
        """result-card.js 含 API 呼叫、async functions、file-level user_tags、fetch helper"""
        content = self._result_card()
        for expected in [
            "user-tags",
            "async confirmAddTag()",
            "async removeUserTag(",
            "fileList[this.currentFileIndex].user_tags",
            "currentUserTags()",
            "fetchUserTagsForCurrent",
        ]:
            assert expected in content, f"result-card.js missing: {expected!r}"
        # not-in guards
        for forbidden in ["pathToFileUri", "c.user_tags.push(tag)"]:
            assert forbidden not in content, f"result-card.js should not contain: {forbidden!r}"
        # fetchUserTagsForCurrent writes to file-level
        idx = content.find("async fetchUserTagsForCurrent()")
        assert idx != -1, "result-card.js missing: 'async fetchUserTagsForCurrent()'"
        func_body = content[idx:idx+800]
        has_direct = "fileList[this.currentFileIndex].user_tags" in func_body
        has_captured_ref = ("file.user_tags" in func_body and
                            "this.fileList?.[this.currentFileIndex]" in func_body)
        assert has_direct or has_captured_ref, \
            "fetchUserTagsForCurrent missing file-level user_tags write"

    def test_search_html_contains(self):
        """search.html 含 user-tags 守衛 + currentUserTags()"""
        html = self._html()
        for expected in [
            "listMode === \'file\'",
            "fileList[currentFileIndex]?.path",
            "currentUserTags()",
        ]:
            assert expected in html, f"search.html missing: {expected!r}"

    def test_path_utils_and_locales(self):
        """path-utils.js 無 pathToFileUri + 有 pathToDisplay；locales 含 tag_api_failed"""
        pu = self._path_utils()
        assert "pathToFileUri" not in pu, "path-utils.js should not contain: 'pathToFileUri'"
        assert "pathToDisplay" in pu, "path-utils.js missing: 'pathToDisplay'"
        # file-list.js user_tags init
        file_list_content = FILE_LIST_JS.read_text(encoding="utf-8")
        assert "user_tags: []" in file_list_content, "file-list.js missing: 'user_tags: []'"
        # locales
        for locale_file in ["zh_TW.json", "zh_CN.json", "en.json", "ja.json"]:
            data = self._locale(locale_file)
            val = self._get_nested(data, "search.error.tag_api_failed")
            assert val, f"{locale_file} missing: search.error.tag_api_failed key"

class TestShowcaseActressTemplate:
    """Phase 44a-T3: 守衛 showcase.html 含有女優模式 UI 結構（method folded）"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def test_showcase_html_contains(self):
        """showcase.html 含女優模式所有必要 UI 結構字串"""
        html = self._html()
        for expected in [
            "toggleActressMode()",
            "showFavoriteActresses",
            "actressSearch",
            "paginatedActresses",
            "actress-card",
            "\'actress:\'",
            "openActressLightbox(index)",
            "actressLoading",
            "actressCount === 0",
            "actress.photo_url",
            "actress-no-photo",
            "actress-card-footer",
            "actressSort",
            "!showFavoriteActresses",
        ]:
            assert expected in html, f"showcase.html missing: {expected!r}"

class TestShowcaseActressLightbox:
    """Phase 44a-T4: Actress Lightbox layout + chips + nav（method folded）"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def _js(self):
        return SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8")

    def test_showcase_html_contains(self):
        """showcase.html 含女優 lightbox 所有必要 UI 結構"""
        html = self._html()
        for expected in [
            "currentLightboxActress",
            "currentLightboxVideo && !currentLightboxActress",
            "actress-lightbox-meta",
            "lb-chips-more",
            "prevActressLightbox()",
        ]:
            assert expected in html, f"showcase.html missing: {expected!r}"

    def test_actress_js_contains(self):
        """state-actress.js 含 lightbox 必要 methods"""
        js = self._js()
        for expected in [
            "_actressCoreMetadata",
            "_allInfoChips",
            "_chipsLimit",
            "_visibleAliases",
            "_visibleInfoChips",
            "_visibleVideoTags",
        ]:
            assert expected in js, f"state-actress.js missing: {expected!r}"

class TestShowcaseActressCRUD:
    """Phase 44a-T5: Actress CRUD guards (method folded)"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def _js(self):
        return SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8")

    def test_actress_js_contains(self):
        """state-actress.js 含 CRUD methods"""
        js = self._js()
        for expected in [
            "addFavoriteActress",
            "openRemoveActressModal",
            "confirmRemoveActress",
            "cancelRemoveActressModal",
            "searchActressFilms",
        ]:
            assert expected in js, f"state-actress.js missing: {expected!r}"
        assert "rescrapeActress" not in js, \
            "state-actress.js should not contain: 'rescrapeActress'"

    def test_showcase_html_contains(self):
        """showcase.html 含 CRUD handlers; searchActressFilms >=2; 無 rescrapeActress"""
        html = self._html()
        for expected in ["_addActressName", "addFavoriteActress()", "openRemoveActressModal()"]:
            assert expected in html, f"showcase.html missing: {expected!r}"
        assert html.count("searchActressFilms(") >= 2, \
            "showcase.html missing: 'searchActressFilms(' (x2)"
        assert "rescrapeActress()" not in html, \
            "showcase.html should not contain: 'rescrapeActress()'"


class TestShowcaseActressCardFooter:
    """Phase 44c-T2: Actress Card Footer guards (method folded)"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def _js(self):
        return SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8")

    def test_actress_html_contains(self):
        """showcase.html actress card footer 含 footer-default + footer-hover 結構"""
        html = self._html()
        for expected in ["footer-default", "_actressCardMiddle", "footer-hover", "_actressHoverInfo"]:
            assert expected in html, f"showcase.html missing: {expected!r}"

    def test_actress_js_contains(self):
        """state-actress.js 含 footer 必要方法"""
        js = self._js()
        for expected in ["_actressCardMiddle", "_actressHoverInfo", "actressSort"]:
            assert expected in js, f"state-actress.js missing: {expected!r}"
        # _actressHoverInfo should not include age
        m = re.search(r'_actressHoverInfo\(actress\)\s*\{(.+?)^\s{8}\},', js, re.DOTALL | re.MULTILINE)
        if m:
            assert "actress.age" not in m.group(1), \
                "state-actress.js _actressHoverInfo should not contain: 'actress.age'"


class TestShowcaseActressI18n:
    """Phase 44a-T7: showcase actress i18n keys (method folded)"""

    LOCALES_ROOT = Path(__file__).parent.parent.parent / "locales"

    def _locale(self, name):
        return json.loads((self.LOCALES_ROOT / name).read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_all_locales_actress_keys(self):
        """4 locales 含 23 個 showcase actress keys"""
        keys = [
            "showcase.mode.actress", "showcase.mode.video",
            "showcase.search.actress", "showcase.search.video",
            "showcase.actress.add", "showcase.actress.addPlaceholder",
            "showcase.actress.addSuccess", "showcase.actress.addDuplicate",
            "showcase.actress.addNotFound", "showcase.actress.addTimeout",
            "showcase.actress.remove", "showcase.actress.removeSuccess",
            "showcase.actress.empty", "showcase.actress.emptyHint",
            "showcase.actress.search_films",
            "showcase.sort.actress.video_count", "showcase.sort.actress.name",
            "showcase.sort.actress.added_at", "showcase.sort.actress.age",
            "showcase.sort.actress.height", "showcase.sort.actress.cup",
            "showcase.unit.videos_count", "showcase.unit.films",
        ]
        for locale_file in ["zh_TW.json", "zh_CN.json", "en.json", "ja.json"]:
            data = self._locale(locale_file)
            for key in keys:
                val = self._get_nested(data, key)
                assert val is not None, f"{locale_file} missing: {key!r}"
        # remove_modal keys (zh_TW only)
        zh_tw = self._locale("zh_TW.json")
        for key in ["showcase.actress.remove_modal.title", "showcase.actress.remove_modal.body",
                    "showcase.actress.remove_modal.cancel", "showcase.actress.remove_modal.confirm"]:
            val = self._get_nested(zh_tw, key)
            assert val is not None, f"zh_TW.json missing: {key!r}"
        # orphan key removed
        assert self._get_nested(zh_tw, "showcase.actress.removeConfirm") is None, \
            "zh_TW.json should not contain: 'showcase.actress.removeConfirm'"


class TestSettingsResetModalI18n:
    """T3.4 (CD-52-11): resetConfig fluent-modal i18n key guard (method folded)"""

    LOCALES_ROOT = Path(__file__).parent.parent.parent / "locales"

    def _locale(self, name):
        return json.loads((self.LOCALES_ROOT / name).read_text(encoding="utf-8"))

    def _get_nested(self, d, dotted_key):
        keys = dotted_key.split(".")
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    def test_reset_modal_keys_in_zh_tw(self):
        """T3.4: reset_modal.* 3 keys 在 zh_TW.json 存在"""
        data = self._locale("zh_TW.json")
        for key in ["settings.reset_modal.title", "settings.reset_modal.body", "settings.reset_modal.confirm"]:
            val = self._get_nested(data, key)
            assert val is not None, f"zh_TW.json missing: {key!r}"


class TestShowcaseLightboxSentinel:
    """Phase 44b-T4: Lightbox -1 sentinel nav guards (method folded)"""

    CORE_JS = SHOWCASE_LIGHTBOX_JS
    SHOWCASE_HTML = Path(__file__).parents[2] / 'web' / 'templates' / 'showcase.html'

    def _js(self):
        return self.CORE_JS.read_text(encoding='utf-8')

    def _html(self):
        return self.SHOWCASE_HTML.read_text(encoding='utf-8')

    def test_showcase_lightbox_js_contains(self):
        """state-lightbox.js 含 sentinel nav 所有必要方法與邏輯"""
        js = self._js()
        for expected in ["hasVisiblePrev", "hasVisibleNext", "openHeroCardLightbox"]:
            assert expected in js, f"state-lightbox.js missing: {expected!r}"
        # openHeroCardLightbox block checks
        idx = js.find("openHeroCardLightbox")
        block = js[idx:idx + 2000]
        assert "lightboxIndex = -1" in block, \
            "state-lightbox.js openHeroCardLightbox missing: 'lightboxIndex = -1'"
        assert "this.currentLightboxActress" in block, \
            "state-lightbox.js openHeroCardLightbox missing: 'this.currentLightboxActress'"
        # prevLightboxVideo sentinel guard
        prev_idx = js.find("prevLightboxVideo()")
        assert prev_idx != -1, "state-lightbox.js missing: 'prevLightboxVideo()'"
        prev_block = js[prev_idx:prev_idx + 1500]
        assert "lightboxIndex === -1" in prev_block, \
            "state-lightbox.js prevLightboxVideo missing: 'lightboxIndex === -1'"
        assert "is_favorite" in prev_block, \
            "state-lightbox.js prevLightboxVideo missing: 'is_favorite'"
        # nextLightboxVideo -1 transition
        next_idx = js.find("nextLightboxVideo()")
        assert next_idx != -1, "state-lightbox.js missing: 'nextLightboxVideo()'"
        next_block = js[next_idx:next_idx + 1500]
        assert "lightboxIndex === -1" in next_block, \
            "state-lightbox.js nextLightboxVideo missing: 'lightboxIndex === -1'"
        assert "_setLightboxIndex" in next_block, \
            "state-lightbox.js nextLightboxVideo missing: '_setLightboxIndex'"
        # handleKeydown uses showFavoriteActresses
        hkd_idx = js.find("// 5. Lightbox")
        assert hkd_idx != -1, "state-lightbox.js handleKeydown section anchor not found"
        assert "showFavoriteActresses" in js[hkd_idx:hkd_idx + 1000], \
            "state-lightbox.js handleKeydown missing: 'showFavoriteActresses'"

    def test_showcase_html_contains(self):
        """showcase.html removeActress button gated by showFavoriteActresses"""
        html = self._html()
        idx = html.find("openRemoveActressModal()")
        assert idx != -1, "showcase.html missing: 'openRemoveActressModal()'"
        surrounding = html[max(0, idx - 300):idx + 100]
        assert "showFavoriteActresses" in surrounding, \
            "showcase.html removeActress button missing: 'showFavoriteActresses' guard"


class TestShowcaseHeroCard:
    """Phase 44b-T6: Showcase Hero Card guards (method folded)"""

    SHOWCASE_HTML = Path(__file__).parents[2] / 'web' / 'templates' / 'showcase.html'

    def _html(self):
        return self.SHOWCASE_HTML.read_text(encoding='utf-8')

    def test_showcase_html_contains(self):
        """showcase.html Hero Card 含必要結構"""
        html = self._html()
        for expected in [
            "hero-card",
            "t('common.no_image')",
            "searchFromMetadata(actress.trim(), 'actress')",
        ]:
            assert expected in html, f"showcase.html missing: {expected!r}"
        assert "<span>No Image</span>" not in html, \
            "showcase.html should not contain: '<span>No Image</span>'"

    def test_animations_js_contains(self):
        """showcase animations.js 含 playHeroCardAppear"""
        anim_js = (Path(__file__).parents[2] / 'web' / 'static' / 'js' / 'pages' / 'showcase' / 'animations.js').read_text(encoding='utf-8')
        assert "playHeroCardAppear" in anim_js, \
            "showcase/animations.js missing: 'playHeroCardAppear'"


class TestShowcaseAliasGuard:
    """T5 (45-actress-alias): Frontend Guard — alias injection guard (method folded)"""

    def _js(self):
        return (
            SHOWCASE_BASE_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_VIDEOS_JS.read_text(encoding="utf-8")
        )

    def test_alias_js_contains(self):
        """showcase JS 含 _nameToGroup 宣告 + API + 使用"""
        js = self._js()
        for expected in [
            "var _nameToGroup = {}",
            "/api/actress-aliases",
            "_nameToGroup[a.name]",
            "_nameToGroup[term]",
        ]:
            assert expected in js, f"showcase JS missing: {expected!r}"
        # _checkPreciseActressMatch function body must use _nameToGroup
        func_start = js.find("async _checkPreciseActressMatch")
        func_end = js.find("},", func_start)
        func_body = js[func_start:func_end]
        assert "_nameToGroup" in func_body, \
            "showcase JS _checkPreciseActressMatch missing: '_nameToGroup'"


# ---------------------------------------------------------------------------
# T6: Scanner Alias UI v2 — 舊 token 移除 + 新 token 存在守衛
# ---------------------------------------------------------------------------
SCANNER_HTML = Path(__file__).parent.parent.parent / "web" / "templates" / "scanner.html"
ZH_TW_JSON = Path(__file__).parent.parent.parent / "locales" / "zh_TW.json"


class TestScannerAliasV2Guard:
    """T6/T8: scanner alias V2 guard（method folded）"""

    def _js(self):
        return SCANNER_ALIAS_JS.read_text(encoding="utf-8")

    def _html(self):
        return SCANNER_HTML.read_text(encoding="utf-8")

    def _zh_tw(self):
        return json.loads(ZH_TW_JSON.read_text(encoding="utf-8"))

    def test_scanner_alias_js_contains(self):
        """scanner alias JS 含新 state；不含舊欄位名"""
        js = self._js()
        for expected in ["aliasRecords", "aliasInput", "cancelAddAlias"]:
            assert expected in js, f"scanner alias JS missing: {expected!r}"
        for forbidden in ["alias.old_name", "alias.new_name", "api/gallery/actress-aliases"]:
            assert forbidden not in js, f"scanner alias JS should not contain: {forbidden!r}"

    def test_scanner_html_contains(self):
        """scanner.html 含 x-model 綁定；不含舊 binding"""
        html = self._html()
        x_model = 'x-model="addingAlias[group.primary_name]"'
        assert x_model in html, f"scanner.html missing: {x_model!r}"
        btn_type = 'type="button" class="btn-cancel"'
        assert btn_type in html, f"scanner.html missing: {btn_type!r}"
        for forbidden in [
            "aliasForm.oldName",
            ':value="addingAlias[group.primary_name]"',
            "btn-confirm",
        ]:
            assert forbidden not in html, f"scanner.html should not contain: {forbidden!r}"

    def test_zh_tw_contains(self):
        """zh_TW.json 含 scanner.alias i18n keys"""
        data = self._zh_tw()
        alias = data.get("scanner", {}).get("alias", {})
        for expected in ["search_placeholder", "filter_hint"]:
            assert expected in alias, f"zh_TW.json scanner.alias missing: {expected!r}"

class TestUserTagCSSGuard:
    """T3: 確保 user-tag 選擇器不使用 --text-inverse（dark mode 對比度修正）"""

    def test_search_user_tag_no_text_inverse(self):
        """search.css 的 .tag-badge.user-tag 不使用 --text-inverse"""
        css = Path("web/static/css/pages/search.css").read_text(encoding="utf-8")
        # 截取 .tag-badge.user-tag 選擇器區塊
        match = re.search(r'\.tag-badge\.user-tag\s*\{([^}]+)\}', css)
        assert match, ".tag-badge.user-tag selector not found in search.css"
        block = match.group(1)
        assert "--text-inverse" not in block, \
            ".tag-badge.user-tag should use --color-primary-content, not --text-inverse"

    def test_showcase_lb_user_tag_no_text_inverse(self):
        """showcase.css 的 .lb-user-tag 不使用 --text-inverse"""
        css = Path("web/static/css/pages/showcase.css").read_text(encoding="utf-8")
        match = re.search(r'\.lb-user-tag\s*\{([^}]+)\}', css)
        assert match, ".lb-user-tag selector not found in showcase.css"
        block = match.group(1)
        assert "--text-inverse" not in block, \
            ".lb-user-tag should use --color-primary-content, not --text-inverse"


class TestShowcaseToolbarStructureGuard:
    """T5: 確保影片模式 .toolbar-controls 直接子 .control-group 數量為 2"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def test_video_mode_toolbar_has_two_control_groups(self):
        """影片模式 .toolbar-controls 直接子 .control-group 應有 2 個

        group 1: funnel + sort-dir
        group 2: mode dropdown + eye button + perPage dropdown
        """
        html = self._html()

        # 找到影片模式的 toolbar-controls（x-show="!showFavoriteActresses"）
        # 用正則截取從開啟標籤到對應結尾 </div> 的區塊
        # 先找到開啟的 div
        start_pattern = re.compile(
            r'<div[^>]+class="[^"]*toolbar-section toolbar-controls[^"]*"[^>]+x-show="!showFavoriteActresses"[^>]*>'
        )
        start_match = start_pattern.search(html)
        assert start_match, (
            "showcase.html 找不到影片模式 .toolbar-controls（x-show=\"!showFavoriteActresses\"）"
        )

        # 從開啟標籤後，追蹤 div 巢狀深度找到對應的結尾 </div>
        pos = start_match.end()
        depth = 1
        tag_pattern = re.compile(r'<(/?)div[\s>]')
        while depth > 0 and pos < len(html):
            m = tag_pattern.search(html, pos)
            if not m:
                break
            if m.group(1) == '/':
                depth -= 1
            else:
                depth += 1
            pos = m.end()

        block = html[start_match.end():pos]

        # 計算直接子 .control-group 數量：找開啟的 <div class="control-group">
        # 只計算深度 1 的（直接子）
        direct_groups = 0
        depth = 0
        tag_re = re.compile(r'<(/?)(div)(?:\s+([^>]*))?>')
        for m in tag_re.finditer(block):
            closing, tag, attrs = m.group(1), m.group(2), m.group(3) or ''
            if closing:
                depth -= 1
            else:
                if depth == 0 and 'control-group' in attrs:
                    direct_groups += 1
                depth += 1

        assert direct_groups == 1, (
            f"影片模式 .toolbar-controls 直接子 .control-group 應為 1 個（全部 5 icon 合併），實際為 {direct_groups} 個。"
        )


class TestActressIconGuard:
    """T6E: 確保女優 icon 統一為 bi-person-circle"""

    def test_showcase_no_bare_bi_person(self):
        """showcase.html 不應有 bi-person（非 circle/heart）"""
        html = Path("web/templates/showcase.html").read_text(encoding="utf-8")
        # 匹配 bi-person 但排除 bi-person-circle 和 bi-person-heart
        matches = re.findall(r'class="bi bi-person(?!-circle|-heart)"', html)
        # 排除 icon catalog 展示（如有）
        assert len(matches) == 0, f"showcase.html 仍有 {len(matches)} 處 bi-person（非 circle/heart）"

    def test_scanner_no_bi_person_badge(self):
        """scanner.html 不應有 bi-person-badge"""
        html = Path("web/templates/scanner.html").read_text(encoding="utf-8")
        assert "bi-person-badge" not in html, "scanner.html 仍有 bi-person-badge"


class TestFluentCustomEaseRegistered:
    """Phase 50.2.0: motion-adapter.js 同步註冊 fluent CustomEase 三角色"""

    def _js(self):
        return Path("web/static/js/components/motion-adapter.js").read_text(encoding="utf-8")

    def test_fluent_standard_registered(self):
        js = self._js()
        assert "CustomEase.create('fluent'" in js, \
            "motion-adapter.js 缺 CustomEase.create('fluent', ...) — charter §5 standard"

    def test_fluent_decel_registered(self):
        js = self._js()
        assert "CustomEase.create('fluent-decel'" in js, \
            "motion-adapter.js 缺 CustomEase.create('fluent-decel', ...) — charter §5 decel"

    def test_fluent_accel_registered(self):
        js = self._js()
        assert "CustomEase.create('fluent-accel'" in js, \
            "motion-adapter.js 缺 CustomEase.create('fluent-accel', ...) — charter §5 accel"

    def test_register_is_guarded(self):
        """guard 寫法避免 CustomEase plugin 載入失敗時 IIFE 炸掉"""
        js = self._js()
        assert "typeof CustomEase !== 'undefined'" in js, \
            "fluent ease 註冊應用 typeof guard 包住"

    def test_register_is_synchronous(self):
        """同步註冊（不放 DOMContentLoaded handler，CD-2）"""
        js = self._js()
        # 註冊區段位於 IIFE 內、var motion 之前；不應出現 DOMContentLoaded wrapper 包裹 CustomEase.create
        register_idx = js.find("CustomEase.create('fluent'")
        dom_ready_idx = js.find("DOMContentLoaded")
        # 若有 DOMContentLoaded（reduced-motion handler 等），其位置必須在 register 之後
        if dom_ready_idx != -1:
            assert register_idx < dom_ready_idx, \
                "fluent CustomEase 註冊不應被 DOMContentLoaded handler 包住"


class TestShowcaseCssTransitionTokens:
    """Phase 50.2.10 + 51.T1.2: showcase.css transition 硬編碼 → fluent token（影片 + 女優模式全段）"""

    def _css(self):
        return Path("web/static/css/pages/showcase.css").read_text(encoding="utf-8")

    def test_actress_picker_transition_tokenized(self):
        """Phase 51 T1.2: 女優 picker 三處 transition 已 token 化（fluent-duration-fast + fluent-ease-standard）"""
        css = self._css()
        # picker-check-icon (opacity), picker-refresh-btn (all), picker-open cover-actions (opacity)
        assert "transition: opacity var(--fluent-duration-fast) var(--fluent-ease-standard)" in css, \
            "picker-check-icon / cover-actions opacity transition 應使用 fluent token"
        assert "transition: all var(--fluent-duration-fast) var(--fluent-ease-standard)" in css, \
            "picker-refresh-btn all transition 應使用 fluent token"


class TestMotionDurationConstants:
    """Phase 50.2.9: motion.DURATION 三角色常數 + 業務 caller 套用 (CD-1)"""

    def _adapter(self):
        return Path("web/static/js/components/motion-adapter.js").read_text(encoding="utf-8")

    def _animations(self):
        return Path("web/static/js/pages/showcase/animations.js").read_text(encoding="utf-8")

    def test_duration_constants_exposed(self):
        """motion.DURATION 三角色常數透過 IIFE 暴露於 window.OpenAver.motion"""
        js = self._adapter()
        assert "DURATION:" in js, "motion-adapter.js 缺 DURATION: 物件定義"
        # 三角色值對齊 charter §5 (167ms / 333ms / 500ms)
        assert "fast:" in js and "0.167" in js, "DURATION.fast 應為 0.167 (charter §5 167ms)"
        assert "medium:" in js and "0.333" in js, "DURATION.medium 應為 0.333 (charter §5 333ms)"
        assert "emphasis:" in js and "0.5" in js, "DURATION.emphasis 應為 0.5 (charter §5 500ms)"

    def test_adapter_callers_use_duration_constants(self):
        """motion-adapter.js 內部 caller 使用 motion.DURATION.* 取代 hardcoded fallback"""
        js = self._adapter()
        assert js.count("motion.DURATION.") >= 4, \
            "motion-adapter.js 至少 4 個 caller (playEnter/Leave/FadeTo/Modal/Stagger) 應走 motion.DURATION.*"

    def test_animations_callers_use_duration_constants(self):
        """showcase/animations.js 業務 caller 使用 OpenAver.motion.DURATION.*"""
        js = self._animations()
        assert js.count("OpenAver.motion.DURATION.") >= 8, \
            "animations.js 至少 8 處 hardcoded duration 應改走 OpenAver.motion.DURATION.*"

    def test_white_list_durations_preserved(self):
        """白名單 hardcoded duration 不被誤改：
        - showcaseSettle 招牌曲線 (charter §5 white-list)
        - HeroCardAppear (女優專屬，plan D10)
        - SourcePulse 0.1 (低於 DURATION.fast 不適合 bucket)"""
        js = self._animations()
        # showcaseSettle: var dur = params.duration || 0.8;
        assert "params.duration || 0.8" in js, "playSettle (showcaseSettle) duration 0.8 不應被改"
        # HeroCardAppear: duration: 0.3
        hero_idx = js.find("playHeroCardAppear")
        hero_scope = js[hero_idx : hero_idx + 800]
        assert "duration: 0.3" in hero_scope, "playHeroCardAppear duration 0.3 (女優白名單) 不應被改"
        # SourcePulse default 0.1 stays
        pulse_idx = js.find("playSourcePulse")
        pulse_scope = js[pulse_idx : pulse_idx + 800]
        assert "options.duration : 0.1" in pulse_scope, \
            "playSourcePulse default 0.1 (低於 fast bucket) 不應被改"


class TestMotionAdapterFluentDefaults:
    """Phase 50.2.1: motion-adapter.js 5 default ease → fluent 角色"""

    def _js(self):
        return Path("web/static/js/components/motion-adapter.js").read_text(encoding="utf-8")

    def _scoped(self, fn_name):
        """擷取從 fn_name 開頭到下一個 /** 區段間的 JS（function body 範圍）"""
        js = self._js()
        idx = js.find(fn_name + ":")
        assert idx > 0, f"找不到 {fn_name}"
        next_doc = js.find("/**", idx + 1)
        return js[idx : next_doc if next_doc > 0 else idx + 800]

    def test_play_enter_default_fluent_decel(self):
        scope = self._scoped("playEnter")
        assert "opts.ease || 'fluent-decel'" in scope, \
            "playEnter default ease 應為 'fluent-decel'（charter §5 進場）"

    def test_play_leave_default_fluent_accel(self):
        scope = self._scoped("playLeave")
        assert "opts.ease || 'fluent-accel'" in scope, \
            "playLeave default ease 應為 'fluent-accel'（charter §5 離場）"

    def test_play_stagger_default_fluent_decel(self):
        scope = self._scoped("playStagger")
        assert "opts.ease || 'fluent-decel'" in scope, \
            "playStagger default ease 應為 'fluent-decel'（charter §5 進場 stagger）"

    def test_play_fade_to_default_fluent(self):
        scope = self._scoped("playFadeTo")
        assert "opts.ease || 'fluent'" in scope and "opts.ease || 'fluent-decel'" not in scope, \
            "playFadeTo default ease 應為 'fluent'（charter §5 standard）"

    def test_play_modal_default_fluent_decel(self):
        scope = self._scoped("playModal")
        assert "opts.ease || 'fluent-decel'" in scope, \
            "playModal default ease 應為 'fluent-decel'（charter §5 modal 彈出）"

    def test_no_legacy_power_ease_defaults(self):
        """confirm 沒有殘留的 power* default ease（在 motion-adapter.js 中）"""
        js = self._js()
        # 註解 / 文件字串若引用 power* 不算違規；但 default fallback 不應有
        assert "opts.ease || 'power" not in js, \
            "motion-adapter.js 殘留 power* default ease — 未完成 fluent 角色化"


class TestShowcaseAnimationsFluent:
    """Phase 50.2.2-2.8: showcase/animations.js 各動畫 ease → charter §5 fluent 角色（method folded）"""

    def _js(self):
        return Path("web/static/js/pages/showcase/animations.js").read_text(encoding="utf-8")

    GHOST_FLY_JS = Path("web/static/js/shared/ghost-fly.js")

    def test_animations_js_contains(self):
        """animations.js ease 角色符合 charter §5 + 招牌曲線保留"""
        js = self._js()
        for expected in [
            # T2.2: playEntry
            "params.easing || 'fluent-decel'",
            # T2.3: playFlipReorder
            "params.ease || 'fluent'",
            # T2.5: playModeCrossfade
            "ease: 'fluent-accel'",
            "ease: 'fluent-decel'",
            # T2.7: playLightboxSwitch + playSampleGallerySwitch
            "ease: 'fluent'",
            # T2.8: playContainerFadeIn + playSourcePulse
            "options.ease || 'fluent-decel'",
            # white-list
            'CustomEase.create("showcaseSettle"',
            # T4.2 delegate
            "GhostFly.playLightboxOpen",
            "showcaseLightboxOpen",
            "typeof window.GhostFly?.playLightboxOpen === 'function'",
        ]:
            assert expected in js, f"showcase/animations.js missing: {expected!r}"
        # T2.4: playFlipFilter onEnter × 2
        assert js.count("ease: 'fluent-decel'") >= 2, \
            "showcase/animations.js missing: 'ease: 'fluent-decel'' (×2 for playFlipFilter onEnter)"
        # not-in: no power2.out in playLightboxSwitch/playSampleGallerySwitch
        # (checking globally is OK since power2.out should only be in ghost-fly for white-list)

    def test_ghost_fly_js_contains(self):
        """ghost-fly.js playLightboxOpen 三段 power2.out + clearProps (×4) + white-list 標注"""
        js = self.GHOST_FLY_JS.read_text(encoding="utf-8")
        idx = js.find("playLightboxOpen:")
        assert idx > 0, "ghost-fly.js missing: 'playLightboxOpen:'"
        scope = js[idx:idx+4500]
        assert scope.count("ease: 'power2.out'") >= 3, \
            "ghost-fly.js playLightboxOpen missing: 'ease: 'power2.out'' (×3 for backdrop/content/cover)"
        assert scope.count("clearProps: 'transform,opacity'") >= 4, \
            "ghost-fly.js playLightboxOpen missing: clearProps ×4 (onComplete + onInterrupt)"
        assert "ease: 'fluent-decel'" not in scope, \
            "ghost-fly.js playLightboxOpen should not contain: 'ease: 'fluent-decel''"
        assert ("white-list" in scope or "ghost-fly" in scope), \
            "ghost-fly.js playLightboxOpen missing: white-list or ghost-fly comment"

    def test_search_animations_js_contains(self):
        """search/animations.js playLightboxOpen delegate GhostFly（Phase 51 T4.3）"""
        search_js = Path("web/static/js/pages/search/animations.js").read_text(encoding="utf-8")
        idx = search_js.find("playLightboxOpen: function")
        assert idx > 0, "search/animations.js missing: 'playLightboxOpen: function'"
        scope = search_js[idx:idx+800]
        assert "GhostFly.playLightboxOpen" in scope, \
            "search/animations.js missing: 'GhostFly.playLightboxOpen'"
        assert "showcaseLightboxOpen" not in scope, \
            "search/animations.js should not contain: 'showcaseLightboxOpen'"
        assert "typeof window.GhostFly?.playLightboxOpen === 'function'" in scope, \
            "search/animations.js missing: typeof guard for playLightboxOpen"

class TestGhostFlyGuards:
    """T8: Ghost Fly architecture guards (method folded)"""

    def test_ghost_fly_js_and_html_contains(self):
        """ghost-fly.js exists + loaded in base.html + skipCover support + delegates"""
        assert Path("web/static/js/shared/ghost-fly.js").exists(), \
            "web/static/js/shared/ghost-fly.js missing"
        html = Path("web/templates/base.html").read_text(encoding="utf-8")
        assert "ghost-fly.js" in html, "base.html missing: 'ghost-fly.js'"
        ghost_fly_js = Path("web/static/js/shared/ghost-fly.js").read_text(encoding="utf-8")
        assert "skipCover" in ghost_fly_js, "ghost-fly.js missing: 'skipCover'"
        for path in [
            "web/static/js/pages/showcase/animations.js",
            "web/static/js/pages/search/animations.js",
        ]:
            js = Path(path).read_text(encoding="utf-8")
            assert "GhostFly.playLightboxOpen" in js, f"{path} missing: 'GhostFly.playLightboxOpen'"
        # search/animations.js fallback
        search_js = Path("web/static/js/pages/search/animations.js").read_text(encoding="utf-8")
        lines = search_js.split('\n')
        ghost_fly_refs = [i for i, line in enumerate(lines) if 'window.GhostFly' in line]
        assert len(ghost_fly_refs) >= 3, \
            "search/animations.js missing: at least 3 window.GhostFly references"

    def test_gsap_animating_before_lightbox_open(self):
        """state-lightbox.js gsap-animating before lightboxOpen = true (ordering)"""
        content = SHOWCASE_LIGHTBOX_JS.read_text(encoding="utf-8")
        for fn_name in ("openLightbox(", "openHeroCardLightbox("):
            idx_fn = content.find(fn_name)
            assert idx_fn > 0, f"state-lightbox.js missing: {fn_name!r}"
            fn_scope = content[idx_fn:idx_fn + 4000]
            idx_animating = fn_scope.find("gsap-animating")
            idx_open = fn_scope.find("this.lightboxOpen = true")
            assert idx_animating > 0, f"state-lightbox.js {fn_name} missing: 'gsap-animating'"
            assert idx_open > 0, f"state-lightbox.js {fn_name} missing: 'lightboxOpen = true'"
            assert idx_animating < idx_open, \
                f"state-lightbox.js {fn_name}: gsap-animating must precede lightboxOpen = true"


class TestTutorialExpandGuard:
    """T10: 新手教學 7 步守衛 (method folded)"""

    def test_tutorial_js_and_i18n(self):
        """tutorial.js 7 步 + samples large: true + 四語系 i18n keys"""
        js = Path("web/static/js/components/tutorial.js").read_text(encoding="utf-8")
        for step_id in ['search', 'files', 'scanner', 'showcase', 'settings', 'help', 'samples']:
            assert f"id: '{step_id}'" in js, f"tutorial.js missing: \"id: '{step_id}'\""
        samples_idx = js.find("id: 'samples'")
        assert samples_idx > 0, "tutorial.js missing: \"id: 'samples'\""
        block = js[samples_idx:js.find('}', samples_idx)]
        assert 'large: true' in block, "tutorial.js samples step missing: 'large: true'"
        for locale in ["zh_TW", "en", "ja", "zh_CN"]:
            data = json.loads(Path(f"locales/{locale}.json").read_text(encoding="utf-8"))
            tutorial = data.get("tutorial", {})
            for i in range(1, 8):
                for key in [f"step{i}_title", f"step{i}_content"]:
                    assert key in tutorial and tutorial[key], \
                        f"{locale}.json missing or empty: tutorial.{key!r}"


class TestMissingEnrichConfirmGuard:
    """TASK-13 (0.7.6 hotfix): 守衛 Scanner 一鍵補完 > 500 confirm dialog 的實作"""

    def _js(self):
        return SCANNER_BATCH_JS.read_text(encoding="utf-8")

    def _html(self):
        return SCANNER_HTML.read_text(encoding="utf-8")

    def _extract_function_body(self, js, fn_name):
        """抓取具名 function（async fn_name(...) { ... }）函式主體（大括號平衡匹配）。
        也涵蓋 `async runMissingEnrich({ skipConfirm = false } = {})` 這類 options pattern。"""
        pattern = re.compile(
            r'async\s+' + re.escape(fn_name) + r'\s*\([^)]*\)\s*\{',
            re.DOTALL,
        )
        m = pattern.search(js)
        if not m:
            # 非 async 版本（例如 resumeMissingEnrich）
            pattern_sync = re.compile(
                re.escape(fn_name) + r'\s*\([^)]*\)\s*\{',
                re.DOTALL,
            )
            m = pattern_sync.search(js)
        assert m is not None, f"scanner.js 找不到 {fn_name} 函式"
        start = m.end()  # 位於 { 之後
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            c = js[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            i += 1
        return js[start:i - 1]

    def test_js_has_missing_confirm_modal_open_state(self):
        """scanner.js 含 missingConfirmModalOpen state 欄位宣告"""
        js = self._js()
        assert "missingConfirmModalOpen" in js, \
            "scanner.js 缺少 missingConfirmModalOpen state（confirm modal 綁定用）"

    def test_js_run_missing_enrich_has_threshold_check(self):
        """runMissingEnrich 函式體含 skipConfirm 參數 + > 500 threshold 檢查 + missingConfirmModalOpen"""
        js = self._js()
        body = self._extract_function_body(js, "runMissingEnrich")
        assert "skipConfirm" in body, \
            "runMissingEnrich 函式體缺少 skipConfirm 參數處理"
        assert "> 500" in body, \
            "runMissingEnrich 函式體缺少 > 500 threshold 檢查"
        assert "missingConfirmModalOpen" in body, \
            "runMissingEnrich 函式體缺少 missingConfirmModalOpen 觸發"

    def test_js_resume_missing_enrich_uses_skip_confirm(self):
        """resumeMissingEnrich 不清 localStorage.avlist_enrich_pending 且用 skipConfirm: true 呼叫 runMissingEnrich"""
        js = self._js()
        body = self._extract_function_body(js, "resumeMissingEnrich")
        assert "localStorage.removeItem('avlist_enrich_pending')" not in body and \
               'localStorage.removeItem("avlist_enrich_pending")' not in body, \
            "resumeMissingEnrich 不應 localStorage.removeItem('avlist_enrich_pending')（會丟恢復點）"
        assert "skipConfirm: true" in body, \
            "resumeMissingEnrich 應呼叫 runMissingEnrich({ skipConfirm: true })"

    def test_html_has_missing_confirm_modal(self):
        """scanner.html 含 missingConfirmModalOpen 綁定 + cancel/confirm 方法"""
        html = self._html()
        assert "missingConfirmModalOpen" in html, \
            "scanner.html 缺少 missingConfirmModalOpen 綁定（confirm modal）"
        assert "cancelLargeMissingEnrich" in html, \
            "scanner.html 缺少 cancelLargeMissingEnrich 綁定"
        assert "confirmLargeMissingEnrich" in html, \
            "scanner.html 缺少 confirmLargeMissingEnrich 綁定"

    def test_all_locales_have_missing_enrich_confirm_keys(self):
        """四語系都有 6 個 missing_enrich_confirm_* keys（純文字）"""
        required = [
            "missing_enrich_confirm_title",
            "missing_enrich_confirm_body_prefix",
            "missing_enrich_confirm_body_middle",
            "missing_enrich_confirm_body_suffix",
            "missing_enrich_confirm_cancel",
            "missing_enrich_confirm_confirm",
        ]
        for locale in ["zh_TW", "zh_CN", "ja", "en"]:
            data = json.loads((LOCALES_ROOT / f"{locale}.json").read_text(encoding="utf-8"))
            stats = data.get("scanner", {}).get("stats", {})
            for key in required:
                assert key in stats and stats[key], \
                    f"{locale}.json missing or empty: scanner.stats.{key!r}"
                value = stats[key]
                assert "<" not in value and ">" not in value, \
                    f"{locale}.json scanner.stats.{key!r} should not contain HTML tags: {value!r}"


class TestIMEGuard:
    """spec-48a §a4: IME composition guard (method folded)"""

    def test_search_html_ime_guard(self):
        """search.html searchQuery input 含 @keydown.enter + isComposing + preventDefault"""
        content = (Path(__file__).parent.parent.parent / "web" / "templates" / "search.html").read_text(encoding="utf-8")
        m = re.search(r'<input\b[^>]*\bid="searchQuery"[^>]*>', content, re.DOTALL)
        assert m, "search.html missing: id=\"searchQuery\" input tag"
        tag = m.group(0)
        handler_m = re.search(r'@keydown\.enter(?:\.prevent)?="([^"]*)"', tag)
        assert handler_m, "search.html searchQuery input missing: @keydown.enter handler"
        expr = handler_m.group(1)
        assert "isComposing" in expr, \
            f"search.html searchQuery @keydown.enter missing: 'isComposing' (handler: {expr!r})"
        assert "preventDefault()" in expr, \
            f"search.html searchQuery @keydown.enter missing: 'preventDefault()' (handler: {expr!r})"


class TestLongPathWarning:
    """spec-48a §a5: scanner/state-scan.js long_paths warning (method folded)"""

    def test_scanner_js_long_path_warning(self):
        """scanner/state-scan.js long_paths 警告 toast 含 warn + 6000 + 260 + debug.log"""
        js = SCANNER_SCAN_JS.read_text(encoding="utf-8")
        assert "long_paths" in js, "scanner/state-scan.js missing: 'long_paths'"
        assert "showToast" in js, "scanner/state-scan.js missing: 'showToast'"
        idx = js.find("long_paths")
        window = js[idx:idx + 500]
        assert "'warn'" in window or '"warn"' in window, \
            "scanner/state-scan.js long_paths toast missing: 'warn' type"
        assert "6000" in window, "scanner/state-scan.js long_paths toast missing: '6000'"
        assert "260" in window, "scanner/state-scan.js long_paths toast missing: '260'"
        assert "debug.log" in window, "scanner/state-scan.js long_paths toast missing: 'debug.log'"


class TestSearchFileJsSubtitleHelper:
    """48a T2 a2 — 前端 extractChineseTitle 同步套用 stripSubtitleMarkers helper（對齊 Python 端）"""

    def _js(self):
        return SEARCH_FILE_JS.read_text(encoding="utf-8")

    def test_file_js_contains(self):
        """file.js 包含 stripSubtitleMarkers helper、常數定義，且舊 regex 已移除"""
        js = self._js()
        for expected in [
            "function stripSubtitleMarkers(",
            "_SUBTITLE_BRACKETS",
            "_SUBTITLE_TEXT_MARKERS",
        ]:
            assert expected in js, f"file.js missing: {expected!r}"
        assert "/^中文字幕\\s*/" not in js, \
            "file.js should not contain: '/^中文字幕\\s*/' (殘缺舊 regex，應改用 stripSubtitleMarkers())"

    def test_extract_chinese_title_uses_strip_helper(self):
        """extractChineseTitle() 應呼叫 stripSubtitleMarkers(name)，不再內嵌殘缺 regex"""
        js = self._js()
        start = js.find("function extractChineseTitle(")
        assert start >= 0, "file.js 找不到 extractChineseTitle 函式定義"
        # 找到函式開頭後的第一個 { ，往後掃直到配對的 }
        brace_start = js.find("{", start)
        assert brace_start >= 0
        depth = 0
        end = brace_start
        for i in range(brace_start, len(js)):
            ch = js[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        body = js[start:end]
        assert "stripSubtitleMarkers(name)" in body, \
            "extractChineseTitle() 應呼叫 stripSubtitleMarkers(name) 剝除所有字幕標記變體"
        assert "name.replace(/^中文字幕" not in body, \
            "extractChineseTitle() 不應再內嵌殘缺 `/^中文字幕...` regex"


class TestFetchSamplesButton:
    """spec-48b §b3 b6 — 守衛 showcase.html fetch-samples-btn（method folded）"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def _js(self):
        return (
            SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_LIGHTBOX_JS.read_text(encoding="utf-8")
        )

    def _fetch_samples_btn_tag(self, html: str):
        m = re.search(
            r'<button\b[^>]*class="[^"]*fetch-samples-btn[^"]*"[^>]*>',
            html, re.DOTALL,
        )
        return m.group(0) if m else None

    def test_html_contains(self):
        """showcase.html fetch-samples-btn 含必要 Alpine 綁定 + loading state + icon"""
        html = self._html()
        tag = self._fetch_samples_btn_tag(html)
        assert tag is not None, "showcase.html missing: class='fetch-samples-btn' button"
        for attr in [
            "x-show=", "sample_images", "@click=", "fetchSamples",
            ":disabled=", "_fetchSamplesFailed",
        ]:
            assert attr in tag, f"fetch-samples-btn tag missing: {attr!r}"
        # boolean coercion in :disabled
        m = re.search(r':disabled=["\'"]([^"\']+)["\'""]', tag)
        assert m, "fetch-samples-btn missing :disabled binding"
        disabled_expr = m.group(1)
        has_coercion = (
            disabled_expr.startswith("!!")
            or "=== true" in disabled_expr
        )
        assert has_coercion, \
            f"fetch-samples-btn :disabled missing boolean coercion: {disabled_expr!r}"
        # x-text and icon in button region
        close_tag_pos = html.find('</button>', tag.__class__ is str and html.find(tag))
        m2 = re.search(
            r'<button\b[^>]*class="[^"]*fetch-samples-btn[^"]*"[^>]*>',
            html, re.DOTALL,
        )
        close_tag_pos = html.find('</button>', m2.end())
        btn_region = html[m2.start():close_tag_pos + len('</button>')]
        for expected in [
            "x-text=", "showcase.samples.fetch_btn",
            "bi bi-cloud-download",
            "_fetchSamplesLoading", "showcase.samples.fetching",
        ]:
            assert expected in btn_region or expected in html, \
                f"showcase.html missing: {expected!r}"
        for forbidden in ["☁"]:
            assert forbidden not in btn_region, f"fetch-samples-btn should not contain: {forbidden!r}"

    def test_core_js_contains(self):
        """core.js 含 fetchSamples method + state init + closeLightbox reset"""
        js = self._js()
        for expected in ["_fetchSamplesLoading:", "_fetchSamplesFailed:"]:
            assert expected in js or expected.replace(":", " :") in js, \
                f"core.js missing: {expected!r}"
        assert "fetchSamples" in js, "core.js missing: 'fetchSamples'"
        close_lb_idx = js.find('closeLightbox() {')
        assert close_lb_idx >= 0, "core.js missing: closeLightbox() method"
        close_lb_body = js[close_lb_idx:close_lb_idx + 2000]
        assert '_fetchSamplesFailed = {}' in close_lb_body, \
            "closeLightbox() missing: '_fetchSamplesFailed = {}'"

    def test_locale_files_have_samples_keys(self):
        """4 語系 showcase.samples 含 5 必要 key + fetch_btn 無 ☁ emoji"""
        required_keys = {"fetch_btn", "fetching", "success", "fetch_failed", "multi_video_error"}
        for locale in ["zh_TW", "zh_CN", "en", "ja"]:
            locale_path = LOCALES_ROOT / f"{locale}.json"
            assert locale_path.exists(), f"locale file missing: {locale_path}"
            data = json.loads(locale_path.read_text(encoding="utf-8"))
            samples = data.get("showcase", {}).get("samples", {})
            missing = required_keys - set(samples.keys())
            assert not missing, f"locales/{locale}.json showcase.samples missing: {sorted(missing)}"
            fetch_btn_val = samples.get("fetch_btn", "")
            assert "☁" not in fetch_btn_val, \
                f"locales/{locale}.json showcase.samples.fetch_btn should not contain ☁: {fetch_btn_val!r}"

class TestActressCoreMetadataVideoCount:
    """T2: _actressCoreMetadata() 加 video_count 前置 + i18n showcase.unit.films 改值"""

    def _js(self):
        # _actressCoreMetadata → state-actress.js
        return SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8")

    def _extract_method_body(self, js, method_name):
        """抓取 Alpine state method 函式主體（大括號平衡）。"""
        pattern = re.compile(
            r'(?:^|\n)\s*' + re.escape(method_name) + r'\s*\([^)]*\)\s*\{',
            re.DOTALL,
        )
        m = pattern.search(js)
        assert m is not None, f"showcase/core.js 找不到 {method_name} 方法"
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            c = js[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            i += 1
        return js[start:i - 1]

    def test_video_count_pushed_first(self):
        """_actressCoreMetadata 函數體前置 push video_count（在 age 之前）"""
        js = self._js()
        body = self._extract_method_body(js, '_actressCoreMetadata')
        assert 'video_count' in body, \
            "showcase/core.js _actressCoreMetadata 函數體缺少 video_count"
        assert 'showcase.unit.films' in body, \
            "showcase/core.js _actressCoreMetadata 函數體缺少 showcase.unit.films i18n key"

        vc_push = re.search(r'parts\.push\([^)]*video_count[^)]*\)', body)
        age_push = re.search(r'parts\.push\([^)]*\.age[^)]*\)', body)
        assert vc_push is not None, \
            "showcase/core.js _actressCoreMetadata 缺少 parts.push(...video_count...) 行"
        assert age_push is not None, \
            "showcase/core.js _actressCoreMetadata 缺少 parts.push(...age...) 行"
        assert vc_push.start() < age_push.start(), \
            "showcase/core.js _actressCoreMetadata video_count push 必須在 age push 之前（前置）"

    def test_video_count_typeof_number_guard(self):
        """_actressCoreMetadata 函數體含 typeof a.video_count === 'number' guard"""
        js = self._js()
        body = self._extract_method_body(js, '_actressCoreMetadata')
        assert re.search(r"typeof\s+\w+\.video_count\s*===\s*['\"]number['\"]", body), \
            "showcase/core.js _actressCoreMetadata 缺少 typeof a.video_count === 'number' guard"

    def test_films_unit_zh_tw_value(self):
        """locales/zh_TW.json showcase.unit.films == '部作品'"""
        data = json.loads((LOCALES_ROOT / "zh_TW.json").read_text(encoding="utf-8"))
        assert data["showcase"]["unit"]["films"] == "部作品", \
            f"zh_TW.json showcase.unit.films 應為 '部作品'，目前 {data['showcase']['unit']['films']!r}"

    def test_films_unit_zh_cn_value(self):
        """locales/zh_CN.json showcase.unit.films == '部作品'"""
        data = json.loads((LOCALES_ROOT / "zh_CN.json").read_text(encoding="utf-8"))
        assert data["showcase"]["unit"]["films"] == "部作品", \
            f"zh_CN.json showcase.unit.films 應為 '部作品'，目前 {data['showcase']['unit']['films']!r}"

    def test_films_unit_ja_value(self):
        """locales/ja.json showcase.unit.films == '作品'"""
        data = json.loads((LOCALES_ROOT / "ja.json").read_text(encoding="utf-8"))
        assert data["showcase"]["unit"]["films"] == "作品", \
            f"ja.json showcase.unit.films 應為 '作品'，目前 {data['showcase']['unit']['films']!r}"

    def test_films_unit_en_unchanged(self):
        """locales/en.json showcase.unit.films == ' films'（保留前空格，不變）"""
        data = json.loads((LOCALES_ROOT / "en.json").read_text(encoding="utf-8"))
        assert data["showcase"]["unit"]["films"] == " films", \
            f"en.json showcase.unit.films 應保留為 ' films'，目前 {data['showcase']['unit']['films']!r}"


SHOWCASE_ANIMATIONS_JS = (
    Path(__file__).parent.parent.parent
    / "web" / "static" / "js" / "pages" / "showcase" / "animations.js"
)


class TestModeToggleFadeOutGuard:
    """T1: 模式切換動畫補 fade-out（playModeCrossfade 4-arg + toggleActressMode callback 延遲翻轉）"""

    def _core_js(self):
        # toggleActressMode / searchActressFilms → state-actress.js
        # switchMode → state-videos.js
        return (
            SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_VIDEOS_JS.read_text(encoding="utf-8")
        )

    def _anim_js(self):
        return SHOWCASE_ANIMATIONS_JS.read_text(encoding="utf-8")

    def _extract_method_body(self, js, method_name):
        """抓取 Alpine state method（methodName(...) { ... }）函式主體，大括號平衡（容忍 async 前綴）。"""
        pattern = re.compile(
            r'(?:^|\n)\s*(?:async\s+)?' + re.escape(method_name) + r'\s*\([^)]*\)\s*\{',
            re.DOTALL,
        )
        m = pattern.search(js)
        assert m is not None, f"找不到 {method_name} 方法"
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            c = js[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            i += 1
        return js[start:i - 1]

    def _extract_property_function_body(self, js, prop_name):
        """抓取 propName: function (...) { ... } 形式的函式主體，大括號平衡。"""
        pattern = re.compile(
            r'\b' + re.escape(prop_name) + r'\s*:\s*function\s*\([^)]*\)\s*\{',
            re.DOTALL,
        )
        m = pattern.search(js)
        assert m is not None, f"找不到 {prop_name} property function"
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            c = js[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            i += 1
        return js[start:i - 1]

    def test_play_mode_crossfade_has_callbacks_param(self):
        """animations.js playModeCrossfade 簽名包含 4 個參數 (oldMode, newMode, params, callbacks)"""
        js = self._anim_js()
        assert re.search(
            r'playModeCrossfade\s*:\s*function\s*\(\s*oldMode\s*,\s*newMode\s*,\s*params\s*,\s*callbacks\s*\)',
            js,
        ), "showcase/animations.js playModeCrossfade 缺少 callbacks 第 4 參數"

    def test_play_mode_crossfade_old_fade_out(self):
        """playModeCrossfade 函數體含 oldEl fade-out (tl.to(oldEl,...) + clearProps:'opacity')"""
        js = self._anim_js()
        body = self._extract_property_function_body(js, 'playModeCrossfade')
        assert re.search(r'tl\s*\.\s*to\s*\(\s*oldEl', body), \
            "playModeCrossfade 函數體缺少 oldEl fade-out (tl.to(oldEl,...))"
        assert re.search(r"clearProps\s*:\s*['\"]opacity['\"]", body), \
            "playModeCrossfade 函數體缺少 clearProps: 'opacity'（避免 CSS transition 殘留）"

    def test_play_mode_crossfade_new_fade_in_preserved(self):
        """playModeCrossfade 函數體保留 newEl fade-in（tl.fromTo(newEl,...) + clearProps:'opacity'）"""
        js = self._anim_js()
        body = self._extract_property_function_body(js, 'playModeCrossfade')
        assert re.search(r'(?:tl\s*\.\s*)?fromTo\s*\(\s*newEl', body), \
            "playModeCrossfade 函數體缺少 newEl fade-in (fromTo(newEl,...))"
        # newEl 段落（從第一次 newEl 出現到結尾）必須有 clearProps
        new_idx = body.find('newEl')
        assert new_idx >= 0, "playModeCrossfade 函數體找不到 newEl 區段"
        new_section = body[new_idx:]
        assert re.search(r"clearProps\s*:\s*['\"]opacity['\"]", new_section), \
            "playModeCrossfade newEl fade-in 段落缺少 clearProps: 'opacity'"

    def test_toggle_actress_mode_uses_callback(self):
        """toggleActressMode 函數體使用 onOldFadeComplete callback，不直接翻轉 showFavoriteActresses"""
        js = self._core_js()
        body = self._extract_method_body(js, 'toggleActressMode')
        assert 'onOldFadeComplete' in body, \
            "toggleActressMode 函數體缺少 onOldFadeComplete callback"
        assert 'playModeCrossfade' in body, \
            "toggleActressMode 函數體缺少 playModeCrossfade 呼叫"
        assert not re.search(
            r'this\.showFavoriteActresses\s*=\s*!\s*this\.showFavoriteActresses',
            body,
        ), "toggleActressMode 不應直接翻轉 this.showFavoriteActresses，應延遲到 callback 內"

    def test_toggle_actress_mode_animgen_guard(self):
        """toggleActressMode 函數體內 _animGeneration 出現 ≥ 2 次（外層 gen + 內層 gen2 race guard）"""
        js = self._core_js()
        body = self._extract_method_body(js, 'toggleActressMode')
        count = len(re.findall(r'_animGeneration', body))
        assert count >= 2, \
            f"toggleActressMode 函數體 _animGeneration 出現次數應 ≥ 2 (外 gen + 內 gen2)，實際 {count}"

    def test_old_caller_backward_compat(self):
        """switchMode 內 playModeCrossfade 呼叫不含 onOldFadeComplete（保持影片模式內切換行為不變）。
        searchActressFilms 自 T7 起為 async 並使用 onOldFadeComplete 觸發 ghost fly fade-out，
        故僅驗證 switchMode 路徑不退化。"""
        js = self._core_js()
        search_body = self._extract_method_body(js, 'searchActressFilms')
        switch_body = self._extract_method_body(js, 'switchMode')
        # 兩處都應呼叫 playModeCrossfade
        assert 'playModeCrossfade' in search_body, \
            "searchActressFilms 應仍呼叫 playModeCrossfade"
        assert 'playModeCrossfade' in switch_body, \
            "switchMode 應仍呼叫 playModeCrossfade"
        # switchMode 不該帶 onOldFadeComplete（保持原 2/3-arg 行為）
        assert 'onOldFadeComplete' not in switch_body, \
            "switchMode 內 playModeCrossfade 呼叫不應帶 onOldFadeComplete（保持影片模式內切換行為不變）"

    def test_toggle_actress_mode_handles_animations_unavailable(self):
        """Codex P1: animations.js 不可用時 toggleActressMode 必須有 fallback path（不能讓 callback 永不觸發）"""
        js = self._core_js()
        body = self._extract_method_body(js, 'toggleActressMode')
        # callback body 應抽成 named function（給 onOldFadeComplete 用、也給 fallback path 用）
        assert re.search(
            r'(?:function\s+\w*FadeIn\w*|var\s+\w*FadeIn\w*\s*=\s*function|\w*FadeIn\w*\s*=\s*function)',
            body,
        ), "toggleActressMode 應將 callback body 抽成 named function（如 flipAndFadeIn）以便 fallback 重用"
        # 必須顯式檢查 playModeCrossfade 是否存在（不能單靠 optional chaining 短路）
        assert re.search(
            r'(?:typeof\s+\w+\s*===\s*[\'"]function[\'"]|window\.ShowcaseAnimations\s*&&\s*window\.ShowcaseAnimations\.playModeCrossfade)',
            body,
        ), "toggleActressMode 應顯式檢查 playModeCrossfade 是否可用（不能單靠 optional chaining）"
        # 抽出來的 named function 應在函數體內被引用 ≥ 2 次（一次給 onOldFadeComplete、一次 fallback 直接呼叫）
        # 找出第一個 *FadeIn* 識別字
        m = re.search(r'\b(\w*[Ff]adeIn\w*)\b', body)
        assert m is not None, "toggleActressMode 找不到 FadeIn 命名函數"
        fname = m.group(1)
        count = len(re.findall(r'\b' + re.escape(fname) + r'\b', body))
        assert count >= 3, (
            f"toggleActressMode 內 {fname} 應出現 ≥ 3 次"
            f"（宣告 1 + onOldFadeComplete 引用 1 + fallback 同步呼叫 1），實際 {count}"
        )

    def test_toggle_actress_mode_reduced_motion_guard_on_fade_in(self):
        """Codex P2: toggleActressMode 內 newEl fade-in 必須有 reduced-motion 防護。

        49a-T4 起：原本的 inline `gsap.fromTo` 已重構為呼叫
        `window.ShowcaseAnimations.playContainerFadeIn`，該 helper 內部的
        `shouldSkip()` 已涵蓋 reduced-motion。本 test 接受兩種寫法擇一：
        (a) inline guard（舊架構）— 函數體內含 `prefersReducedMotion` 檢查
        (b) helper 委派（新架構）— 函數體內呼叫 `playContainerFadeIn`
        """
        js = self._core_js()
        body = self._extract_method_body(js, 'toggleActressMode')
        has_inline_guard = 'prefersReducedMotion' in body
        has_helper_delegation = 'playContainerFadeIn' in body
        assert has_inline_guard or has_helper_delegation, (
            "toggleActressMode newEl fade-in 應走 inline prefersReducedMotion guard，"
            "或委派 ShowcaseAnimations.playContainerFadeIn helper（後者 shouldSkip 已涵蓋）"
        )


class TestAliasLiveQueryGuard:
    """49a-T3: Actress Lightbox 別名即時查 guard

    驗證：
    - _fetchLiveAliases 方法存在
    - 200 分支以 Object.assign 覆蓋 aliases（CD-4 + §8.4 reactivity）
    - 404 / error / timeout 保留 snapshot（catch + 不覆蓋 fallback）
    """

    def _js(self):
        # _fetchLiveAliases / openActressLightbox / prevActressLightbox / nextActressLightbox → state-actress.js
        # openHeroCardLightbox → state-lightbox.js
        return (
            SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8") + "\n" +
            SHOWCASE_LIGHTBOX_JS.read_text(encoding="utf-8")
        )

    def _extract_method_body(self, js, method_name):
        """抓取 Alpine state method 函式主體，大括號平衡（容忍 async 前綴）。"""
        pattern = re.compile(
            r'(?:^|\n)\s*(?:async\s+)?' + re.escape(method_name) + r'\s*\([^)]*\)\s*\{',
            re.DOTALL,
        )
        m = pattern.search(js)
        assert m is not None, f"showcase/core.js 找不到 {method_name} 方法"
        start = m.end()
        depth = 1
        i = start
        while i < len(js) and depth > 0:
            c = js[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            i += 1
        return js[start:i - 1]

    def test_fetch_live_aliases_method_exists(self):
        """core.js 含 async _fetchLiveAliases 方法定義"""
        js = self._js()
        assert re.search(r'async\s+_fetchLiveAliases\s*\([^)]*\)\s*\{', js), \
            "showcase/core.js 缺少 async _fetchLiveAliases(...) 方法定義"
        # 必須呼叫 /api/actress-aliases/ 端點
        body = self._extract_method_body(js, '_fetchLiveAliases')
        assert "/api/actress-aliases/" in body, \
            "_fetchLiveAliases 函數體缺少 /api/actress-aliases/ 端點呼叫"

    def test_200_branch_uses_object_assign(self):
        """200 分支用 Object.assign 覆蓋 currentLightboxActress.aliases（§8.4 Alpine reactivity）"""
        js = self._js()
        body = self._extract_method_body(js, '_fetchLiveAliases')
        # 必須有 200 status 分支
        assert re.search(r'(?:resp|response)\.status\s*===\s*200', body), \
            "_fetchLiveAliases 缺少 resp.status === 200 分支"
        # 必須用 Object.assign 建立新物件以觸發 Alpine deep watch（§8.4）
        assert re.search(r'Object\.assign\s*\(', body), \
            "_fetchLiveAliases 200 分支應用 Object.assign 建立新物件以觸發 Alpine reactivity（§8.4）"
        # 覆蓋的目標必須是 aliases
        assert re.search(r'aliases\s*:', body), \
            "_fetchLiveAliases Object.assign 應指定 aliases 屬性"

    def test_fallback_preserves_snapshot_on_error(self):
        """error / timeout / 404 分支保留 snapshot（catch 區塊不覆蓋 aliases）"""
        js = self._js()
        body = self._extract_method_body(js, '_fetchLiveAliases')
        # 必須有 try / catch 區塊（fallback contract）
        assert re.search(r'\btry\s*\{', body), \
            "_fetchLiveAliases 缺少 try 區塊（error fallback contract）"
        assert re.search(r'\bcatch\s*\(', body), \
            "_fetchLiveAliases 缺少 catch 區塊（error fallback contract）"
        # 200 分支應用 if 包裹（亦即 404/其他狀態落入 implicit fallback：不執行覆蓋）
        # 實作必須讓「非 200」 + 「catch」 不執行 Object.assign
        # 用結構驗證：Object.assign 必須出現在 if (resp.status === 200) { ... } 區塊內
        pattern = re.compile(
            r'if\s*\(\s*(?:resp|response)\.status\s*===\s*200\s*\)\s*\{[^}]*?Object\.assign',
            re.DOTALL,
        )
        assert pattern.search(body), \
            "_fetchLiveAliases Object.assign 應位於 if (resp.status === 200) {...} 區塊內，避免非 200 分支誤覆蓋 snapshot"

    def test_callsites_in_open_actress_and_hero(self):
        """openActressLightbox（兩分支）+ openHeroCardLightbox 皆 fire-and-forget 呼叫 _fetchLiveAliases"""
        js = self._js()
        actress_body = self._extract_method_body(js, 'openActressLightbox')
        # 至少 2 處（首次進入 + 切換女優）
        actress_calls = re.findall(r'_fetchLiveAliases\s*\(', actress_body)
        assert len(actress_calls) >= 2, \
            f"openActressLightbox 應至少 2 處呼叫 _fetchLiveAliases（首次進入 + 切換女優），目前 {len(actress_calls)} 處"

        hero_body = self._extract_method_body(js, 'openHeroCardLightbox')
        assert re.search(r'_fetchLiveAliases\s*\(', hero_body), \
            "openHeroCardLightbox 缺少 _fetchLiveAliases 呼叫"

    def test_prev_next_actress_lightbox_refetch_aliases(self):
        """Codex P2: prev/nextActressLightbox 在切換 index 後也須呼叫 _fetchLiveAliases，
        否則方向鍵切換時 SSOT 心智模型破功（看到 stale snapshot）。"""
        js = self._js()
        for method in ('prevActressLightbox', 'nextActressLightbox'):
            body = self._extract_method_body(js, method)
            assert re.search(r'_fetchLiveAliases\s*\(', body), (
                f"{method} 缺少 _fetchLiveAliases 呼叫（Codex P2 fix）— "
                "方向鍵切換時不重抓 alias，違反 T3 SSOT 設計"
            )


GHOST_FLY_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "shared" / "ghost-fly.js"


class TestGhostFlyInFlightGuard:
    """49a-T7: 女優 → 影片跨模式 Ghost Fly 動畫並發保護 guard

    驗證：
    - state 初始化物件含 _ghostFlyInFlight: false（CD-13 並發 flag）
    - ghost-fly.js 新增 playActressToHeroCard 方法（CD-11）
    - searchActressFilms 為 async 並接受第二參數 fromEl
    - showcase.html 兩個 camera button（grid + lightbox）皆綁 :disabled="_ghostFlyInFlight"
    """

    def _js(self):
        # _ghostFlyInFlight / searchActressFilms → state-actress.js
        return SHOWCASE_ACTRESS_JS.read_text(encoding="utf-8")

    def _ghost_js(self):
        return GHOST_FLY_JS.read_text(encoding="utf-8")

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def test_ghost_fly_in_flight_state_present(self):
        """core.js Alpine state 含 _ghostFlyInFlight: false（CD-13 並發 flag）"""
        js = self._js()
        assert re.search(r'_ghostFlyInFlight\s*:\s*false', js), \
            "showcase/core.js 缺少 Alpine state 屬性 _ghostFlyInFlight: false"

    def test_play_actress_to_hero_card_method_exists(self):
        """ghost-fly.js 含 playActressToHeroCard 方法定義（CD-11）"""
        js = self._ghost_js()
        assert re.search(r'playActressToHeroCard\s*:\s*function', js), \
            "ghost-fly.js 缺少 playActressToHeroCard: function 方法定義"

    def test_search_actress_films_is_async_with_from_el(self):
        """searchActressFilms 為 async 且簽名含第二個參數 fromEl"""
        js = self._js()
        assert re.search(
            r'async\s+searchActressFilms\s*\(\s*actressName\s*,\s*fromEl\s*\)',
            js,
        ), "showcase/core.js searchActressFilms 應為 async 且簽名為 (actressName, fromEl)"

    def test_camera_buttons_disabled_binding(self):
        """showcase.html 兩個 camera button (grid L529 + lightbox L579) 皆綁 :disabled=\"_ghostFlyInFlight\""""
        html = self._html()
        # 計算 :disabled="_ghostFlyInFlight" 出現次數，應 ≥ 2
        matches = re.findall(r':disabled\s*=\s*"_ghostFlyInFlight"', html)
        assert len(matches) >= 2, \
            f"showcase.html 至少 2 個 camera button 應綁 :disabled=\"_ghostFlyInFlight\"（grid + lightbox），目前 {len(matches)} 處"

    def test_camera_buttons_pass_el_to_search(self):
        """showcase.html 兩個 camera button 呼叫 searchActressFilms 時皆傳入 $el 參數"""
        html = self._html()
        # grid camera: searchActressFilms(actress.name, $el)
        # lightbox camera: searchActressFilms(currentLightboxActress?.name, $el)
        assert "searchActressFilms(actress.name, $el)" in html, \
            "showcase.html grid camera button 缺少 searchActressFilms(actress.name, $el) 呼叫"
        assert "searchActressFilms(currentLightboxActress?.name, $el)" in html, \
            "showcase.html lightbox camera button 缺少 searchActressFilms(currentLightboxActress?.name, $el) 呼叫"

    def test_search_actress_films_explicit_ghost_fly_availability_check(self):
        """Codex P1: searchActressFilms 主流程前需 explicit check window.GhostFly?.playActressToHeroCard
        是 function。optional chaining 缺失時 silent no-op，flag 永久 true → camera button 永久 disabled。
        """
        js = self._js()
        body = self._extract_method_body(js, 'searchActressFilms')
        assert re.search(
            r"typeof\s+window\.GhostFly\??\.?playActressToHeroCard\s*!==\s*['\"]function['\"]",
            body,
        ), (
            "searchActressFilms 缺少 explicit GhostFly availability check（Codex P1 fix）— "
            "optional chaining 在缺失時 silent no-op，flag 卡死所有 camera button"
        )

    def _extract_method_body(self, js, name):
        """共用 brace-counting 提取方法體（避免依賴外部 helper class）"""
        m = re.search(r'(?:async\s+)?' + re.escape(name) + r'\s*\([^)]*\)\s*\{', js)
        if not m:
            return ''
        start = m.end() - 1
        depth = 0
        for i, ch in enumerate(js[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return js[start:i + 1]
        return ''


# ============================================================================
# 49a-T4: 底部 footer 整合（status bar 移除 + 三段式 footer + i18n 同步）
# ============================================================================

LOCALES_DIR = Path(__file__).parent.parent.parent / "locales"
LOCALE_FILES = ["zh_TW.json", "zh_CN.json", "en.json", "ja.json"]
SHOWCASE_CSS = Path(__file__).parent.parent.parent / "web" / "static" / "css" / "pages" / "showcase.css"


class TestT4FooterStructure:
    """49a-T4: showcase.html 三段式底部 footer 守衛（method folded）"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def _css(self):
        return SHOWCASE_CSS.read_text(encoding="utf-8")

    def test_showcase_html_contains(self):
        """showcase.html footer 結構、快捷鍵、pager、openPagePicker 全部存在"""
        html = self._html()
        # removed
        assert 'class="showcase-status-bar"' not in html, \
            "showcase.html should not contain: 'class=\"showcase-status-bar\"'"
        # structure
        for expected in [
            'class="showcase-footer"',
            'class="footer-left"',
            'class="footer-center"',
            'class="footer-right"',
            "bi-film",
            "bi-person-circle",
            "<kbd>A</kbd>",
            "<kbd>S</kbd>",
            "<kbd>ESC</kbd>",
            "<kbd>←</kbd>",
            "<kbd>→</kbd>",
            'class="footer-pager"',
            'x-show="!showFavoriteActresses && totalPages > 1"',
            "prevPage()",
            "nextPage()",
            'x-ref="pageSelectFooter"',
            'class="pager-current"',
            "openPagePicker",
        ]:
            assert expected in html, f"showcase.html missing: {expected!r}"
        # footer must not have x-data
        idx = html.find('class="showcase-footer"')
        assert idx >= 0
        div_start = html.rfind('<div', 0, idx)
        end = html.find('>', idx)
        opening_tag = html[div_start:end + 1]
        assert 'x-data' not in opening_tag, \
            "showcase-footer opening tag should not have x-data"
        # openPagePicker must use showPicker
        js = SHOWCASE_VIDEOS_JS.read_text(encoding="utf-8")
        assert "openPagePicker" in js, "core.js missing: 'openPagePicker'"
        assert "showPicker" in js, "core.js missing: 'showPicker'"

    def test_showcase_css_contains(self):
        """showcase.css 含 footer rules + responsive 隱藏 footer-left/center"""
        css = self._css()
        for expected in [
            ".showcase-footer",
            ".footer-left",
            ".footer-center",
            ".footer-right",
            ".footer-pager",
        ]:
            assert expected in css, f"showcase.css missing: {expected!r}"
        # responsive media query
        media_match = re.search(
            r"@media\'s*\(max-width:\'s*640px\'s*\)\'s*\{(.*?)\n\}",
            css, re.DOTALL,
        )
        if media_match is None:
            media_match = re.search(
                r"@media[^{]*640px[^{]*\{([^@]*?)\n\}",
                css, re.DOTALL,
            )
        assert media_match is not None, "showcase.css missing: @media (max-width: 640px)"
        body = media_match.group(1)
        assert ".footer-left" in body and ".footer-center" in body, \
            "@media (max-width: 640px) missing: .footer-left and .footer-center"
        assert ("display: none" in body or "display:none" in body), \
            "@media (max-width: 640px) missing: display: none"

class TestT4I18n:
    """49a-T4: showcase i18n keys guard (method folded)"""

    EXPECTED_SWITCH_MODE = {
        "zh_TW.json": "切換顯示",
        "zh_CN.json": "切换显示",
        "en.json": "Switch view",
        "ja.json": "表示切替",
    }

    @staticmethod
    def _load(locale):
        return json.loads((LOCALES_DIR / locale).read_text(encoding="utf-8"))

    def test_all_locales_i18n(self):
        """四語系 switch_mode / status / unit.actresses 全部正確"""
        for locale in LOCALE_FILES:
            data = self._load(locale)
            showcase = data.get("showcase", {})
            # switch_mode value check
            val = showcase.get("shortcut", {}).get("switch_mode")
            assert val, f"{locale}: missing showcase.shortcut.switch_mode"
            expected_val = self.EXPECTED_SWITCH_MODE[locale]
            assert val == expected_val, \
                f"{locale}: switch_mode expected {expected_val!r}, got {val!r}"
            # status.search_empty
            assert showcase.get("status", {}).get("search_empty"), \
                f"{locale}: missing showcase.status.search_empty"
            # status search_actresses parts
            status = showcase.get("status", {})
            for key in ("search_actresses_prefix", "search_actresses_middle", "search_actresses_suffix"):
                assert key in status, f"{locale}: missing showcase.status.{key!r}"
            # unit.actresses
            unit = showcase.get("unit", {})
            assert "actresses" in unit and unit["actresses"], \
                f"{locale}: missing or empty showcase.unit.actresses"


# ─── 49b-T4a: BurstPicker 模組抽出守衛 ────────────────────────────────────────
BURST_PICKER_JS = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "shared" / "burst-picker.js"
BASE_HTML_T4A = Path(__file__).parent.parent.parent / "web" / "templates" / "base.html"
MOTION_LAB_JS_T4A = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "motion-lab.js"
MOTION_LAB_STATE_JS_T4A = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "motion-lab-state.js"


class TestBurstPickerGuard:
    """49b-T4a: 守衛 BurstPicker 模組抽出（從 motion-lab.js → shared/burst-picker.js）"""

    PICKER_METHODS = (
        "playPickerBurst",
        "playPickerFloat",
        "playPickerHoverIn",
        "playPickerHoverOut",
        "playPickerFlipReplace",
        "playPickerExitAll",
        "playPickerReverseAll",
    )

    def test_burst_picker_js_contains(self):
        """burst-picker.js 存在暴露 module；motion-lab.js 已無 picker 定義；motion-lab-state.js 用新模組路徑"""
        # burst-picker.js: exists + window.BurstPicker + 7 method defs
        assert BURST_PICKER_JS.exists(), f"burst-picker.js 不存在：{BURST_PICKER_JS}"
        picker_js = BURST_PICKER_JS.read_text(encoding="utf-8")
        assert "window.BurstPicker" in picker_js, \
            "burst-picker.js missing: 'window.BurstPicker'"
        for method in self.PICKER_METHODS:
            assert method + ":" in picker_js, f"burst-picker.js missing: {method + ':'!r}"

        # motion-lab.js: picker methods should be removed
        lab_js = MOTION_LAB_JS_T4A.read_text(encoding="utf-8")
        for method in self.PICKER_METHODS:
            pattern = re.compile(re.escape(method) + r"\s*:\s*function")
            matches = pattern.findall(lab_js)
            assert not matches, \
                f"motion-lab.js 仍內嵌 {method} 方法定義（應只在 burst-picker.js）"

        # motion-lab-state.js: calls new module, not old
        state_js = MOTION_LAB_STATE_JS_T4A.read_text(encoding="utf-8")
        assert "window.BurstPicker.playPicker" in state_js, \
            "motion-lab-state.js missing: 'window.BurstPicker.playPicker'"
        legacy = re.findall(r"window\.MotionLab\.playPicker\w+", state_js)
        assert not legacy, \
            f"motion-lab-state.js 仍有舊呼叫 window.MotionLab.playPicker*：{legacy}"

    def test_base_html_loads_burst_picker(self):
        """base.html 含 burst-picker.js script tag 且使用 defer 或 type="module"（54a-T2 後允許 module）"""
        html = BASE_HTML_T4A.read_text(encoding="utf-8")
        assert "/static/js/shared/burst-picker.js" in html, \
            "base.html 缺少 /static/js/shared/burst-picker.js script 引用"
        # 驗證 defer 或 type="module"（type="module" 天生 deferred，等同 defer）
        pattern = re.compile(r'<script[^>]*burst-picker\.js[^>]*>')
        matches = pattern.findall(html)
        assert matches, "base.html 找不到 burst-picker.js script tag"
        for tag in matches:
            assert "defer" in tag or 'type="module"' in tag, \
                f"burst-picker.js script tag 應含 defer 或 type=\"module\" 屬性：{tag}"


# ─── 49b-T4cd: Actress Photo Picker UI/Alpine/SSE 整合守衛 ──────────────────
SHOWCASE_CSS_T4CD = Path(__file__).parent.parent.parent / "web" / "static" / "css" / "pages" / "showcase.css"


class TestPickerIntegrationGuard:
    """49b-T4cd: 守衛 Actress Photo Picker 在 Showcase Lightbox 的 UI + Alpine + SSE 整合（method folded）"""

    def _html(self):
        return SHOWCASE_HTML.read_text(encoding="utf-8")

    def _core_js(self):
        return SHOWCASE_LIGHTBOX_JS.read_text(encoding="utf-8")

    def _css(self):
        return SHOWCASE_CSS_T4CD.read_text(encoding="utf-8")

    def test_picker_html_contains(self):
        """showcase.html 含 picker button、overlay 結構"""
        html = self._html()
        for expected in [
            "bi-arrow-clockwise",
            "showcase.actress.change_photo",
            "currentLightboxActress?.is_favorite",
            "actress-picker-overlay",
            "picker-candidates-grid",
            "picker-source-badge",
            "picker-loading",
            "picker-empty",
        ]:
            assert expected in html, f"showcase.html missing: {expected!r}"
        # T1: actress-picker-area must be renamed
        assert "actress-picker-area" not in html, \
            "showcase.html should not contain: 'actress-picker-area'"

    def test_picker_js_contains(self):
        """core.js 含 picker state、methods、params、SSE handler 等必要字串"""
        js = self._core_js()
        for expected in [
            # state
            "_pickerOpen: false",
            "_pickerRunId: 0",
            "_candidates: []",
            "_pickerSelected: false",
            # methods
            "openActressPicker(",
            "_startPickerSSE(",
            "_closePicker(",
            "_resetPicker(",
            "_fadeMetadataPanel(",
            "_cancelPicker",
            # params
            "_PICKER_PARAMS",
            "arcOvershoot: 1.3",
            # burst picker animations
            "playPickerFlipReplace",
            "playPickerExitAll",
            "typeof window.BurstPicker",
            "playPickerReverseAll",
            # SSE defer-burst
            "_burstAllPickerCandidates",
            # i18n
            "showcase.actress.picker.replaced",
            "showcase.actress.picker.error",
            "showToast(",
            # reduced motion
            "prefers-reduced-motion",
            "matchMedia",
            # lightbox teardown
            "_pickerOpen",
            "_closePicker",
            # stale name capture
            "capturedName",
            "currentLightboxActress",
        ]:
            assert expected in js, f"core.js missing: {expected!r}"
        # arcDuration
        assert ("arcDuration:  0.75" in js or "arcDuration: 0.75" in js), \
            "core.js missing: 'arcDuration: 0.75' in _PICKER_PARAMS"
        # _burstAllPickerCandidates ≥ 4 occurrences
        assert js.count("_burstAllPickerCandidates") >= 4, \
            "_burstAllPickerCandidates must appear ≥4 times (def + done/timeout/error)"

    def test_picker_css_rules_present(self):
        """showcase.css 含 .picker-candidate-card opacity:0 + overlay fixed + spin keyframes"""
        css = self._css()
        assert ".picker-candidate-card" in css, \
            "showcase.css missing: '.picker-candidate-card'"
        card_block = re.search(
            r"(?:^|\n)\.picker-candidate-card\s*\{[^}]*\}", css, re.DOTALL
        )
        assert card_block, "showcase.css: cannot find .picker-candidate-card style block"
        assert "opacity: 0" in card_block.group(0), \
            ".picker-candidate-card missing: 'opacity: 0'"
        area_block = re.search(
            r"\.actress-picker-overlay\s*\{[^}]*\}", css, re.DOTALL
        )
        assert area_block, "showcase.css: cannot find .actress-picker-overlay style block"
        overlay_css = area_block.group(0)
        for expected in ["position: fixed", "bottom:", "width:"]:
            assert expected in overlay_css, \
                f".actress-picker-overlay missing: {expected!r}"
        assert "@keyframes spin" in css, \
            "showcase.css missing: '@keyframes spin'"

    def test_picker_overlay_is_showcase_lightbox_direct_child(self):
        """49c-T1: actress-picker-overlay 必須為 .showcase-lightbox 的直接 child"""
        import html.parser as _html_parser

        html_text = self._html()
        assert "actress-picker-overlay" in html_text, \
            "showcase.html missing: 'actress-picker-overlay'"

        class _DivStackParser(_html_parser.HTMLParser):
            def __init__(self):
                super().__init__()
                self.div_stack = []
                self.overlay_ancestors = None
                self.found_overlay_in_lightbox_content = False

            def handle_starttag(self, tag, attrs):
                if tag != "div":
                    return
                attr_dict = dict(attrs)
                classes = set(attr_dict.get("class", "").split())
                if "actress-picker-overlay" in classes:
                    if self.overlay_ancestors is None:
                        self.overlay_ancestors = [s.copy() for s in self.div_stack]
                    if any("lightbox-content" in s for s in self.div_stack):
                        self.found_overlay_in_lightbox_content = True
                self.div_stack.append(classes)

            def handle_endtag(self, tag):
                if tag != "div":
                    return
                if self.div_stack:
                    self.div_stack.pop()

        parser = _DivStackParser()
        parser.feed(html_text)
        assert parser.overlay_ancestors is not None, \
            "actress-picker-overlay not found in markup"
        assert not parser.found_overlay_in_lightbox_content, \
            "actress-picker-overlay should not be inside lightbox-content"
        assert "showcase-lightbox" in parser.overlay_ancestors[-1], \
            "actress-picker-overlay direct parent should have showcase-lightbox class"

# Removed in T55b — superseded by stylelint:
#   TestSettingsCssHardcoded, TestHelpCssHardcoded, TestDesignSystemCssHardcoded
#     -> declaration-property-value-disallowed-list (transition / filter / box-shadow)
#        + color-no-hex (with design-system.css whole-file ignore).
# TestMotionLabHtmlHardcoded kept below as C-class deferral (HTML <style> scan
# needs postcss-html parser; T55b is minimal toolchain — handled in T55d).


class TestMotionLabHtmlHardcoded:
    """T1.5.6: 確認 motion_lab.html <style> 區塊內無 hardcoded 視覺值（blur / hex / radius / transition）

    掃描策略：僅掃 <style>...</style> block 內容，不掃 HTML style="..." 屬性
    （demo 區大量合法 inline style 用於展示，不納入守衛範疇）
    """

    def _style_blocks(self) -> str:
        """提取 motion_lab.html 所有 <style> block 內容合併"""
        html = MOTION_LAB_HTML.read_text(encoding="utf-8")
        blocks = re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)
        return "\n".join(blocks)

    def test_no_hardcoded_blur_px_in_motion_lab_html(self):
        """motion_lab.html <style> 區塊不含 hardcoded blur(Npx)（須用 var(--fluent-blur-*)）"""
        css = self._style_blocks()
        matches = re.findall(r"blur\(\d+px\)", css)
        assert not matches, (
            f"motion_lab.html <style> 仍有 hardcoded blur(Npx)，請改用 var(--fluent-blur-light/overlay/heavy)：{matches}"
        )

    def test_no_hardcoded_hex_color_in_motion_lab_html(self):
        """motion_lab.html <style> 區塊不含裸 hardcoded hex color（#xxx / #xxxxxx）

        允許例外：
        - var(..., #fff) 形式的 CSS fallback 值（在 var() 內部，pattern 不命中）
        """
        css = self._style_blocks()
        lines = css.split("\n")
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # 跳過純註釋行
            if stripped.startswith("/*") or stripped.startswith("//") or stripped.startswith("*"):
                continue
            # 找裸 hex（不在 var() 內部）：pattern 尋找 # 後接 3/4/6/8 hex digits，
            # 但排除 var(..., #xxx) 形式（前方有逗號 + 空格）
            # 實作：先移除 var( ... ) 內容再搜尋
            line_no_var_fallback = re.sub(r"var\([^)]*\)", "", line)
            if re.search(r"#[0-9a-fA-F]{3,8}\b", line_no_var_fallback):
                violations.append(f"L{i}: {stripped}")
        assert not violations, (
            "motion_lab.html <style> 殘留裸 hex 硬編碼（應改用 token；var() 內 fallback 除外）：\n"
            + "\n".join(violations)
        )

    def test_no_hardcoded_border_radius_px_in_motion_lab_html(self):
        """motion_lab.html <style> 區塊 border-radius 不應含裸 px 數字硬編碼

        允許例外：
        - border-radius: 50%（圓形語義，比例值不是像素）
        - var(--fluent-radius-*, Npx) 的 fallback px 值（在 var() 內部）
        """
        css = self._style_blocks()
        lines = css.split("\n")
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("/*") or stripped.startswith("//") or stripped.startswith("*"):
                continue
            if "border-radius" not in line:
                continue
            # 允許 50%
            if re.search(r"border-radius\s*:\s*50%", line):
                continue
            # 移除 var() 內容再搜尋
            line_no_var = re.sub(r"var\([^)]*\)", "", line)
            if re.search(r"border-radius\s*:[^;]*\d+px", line_no_var):
                violations.append(f"L{i}: {stripped}")
        assert not violations, (
            "motion_lab.html <style> border-radius 殘留裸 px 硬編碼（應改用 var(--fluent-radius-*)；"
            "50% 及 var() 內 fallback 除外）：\n"
            + "\n".join(violations)
        )

    def test_no_hardcoded_transition_duration_in_motion_lab_html(self):
        """motion_lab.html <style> 區塊 transition 不應含裸數字秒數或非 fluent 前綴 alias 硬編碼

        允許例外（留 Phase 2 處理，已標記白名單）：
        - .picker-source-badge transition: background 0.15s
        - .picker-check-icon transition: opacity 0.15s
        這兩處屬 Picker demo 的細節 transition，Phase 1 不改動，Phase 2 統一處理。

        非 fluent 前綴 alias 規則：
        - 禁止 var(--duration-*) — 應改用 var(--fluent-duration-*)
        - 禁止 var(--ease-*) — 應改用 var(--fluent-ease-*)
        這些 alias 已在 theme.css 定義，但 motion_lab 的 <style> 應直接用 canonical token。
        """
        css = self._style_blocks()
        lines = css.split("\n")
        violations = []
        # Phase 2 whitelist：picker demo 兩處細節 transition（已知，留 Phase 2 處理）
        phase2_whitelist = {
            "transition: background 0.15s;",
            "transition: opacity 0.15s;",
        }
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("/*") or stripped.startswith("//") or stripped.startswith("*"):
                continue
            # Phase 2 whitelist
            if stripped in phase2_whitelist:
                continue
            if "transition:" in line:
                # 1. 裸數字秒數（不含任何 var(-- 前綴）
                if re.search(r"transition:[^;]*\b0?\.\d+s\b", line) and "var(--" not in line:
                    violations.append(f"L{i}: {stripped}")
                    continue
                # 2. 非 fluent 前綴 alias：var(--duration-*) 或 var(--ease-*)
                #    （直接命中即是 alias，fluent 前綴版本為 var(--fluent-duration-*) 不命中此 pattern）
                if re.search(r"var\(--(?:duration|ease)-", line):
                    violations.append(f"L{i}: {stripped}")
        assert not violations, (
            "motion_lab.html <style> transition 殘留裸數字秒數或非 fluent 前綴 alias\n"
            "（應改用 var(--fluent-duration-*) / var(--fluent-ease-*)；"
            "picker 兩處 0.15s 已列 Phase 2 whitelist）：\n"
            + "\n".join(violations)
        )



# ─── 52-T2.1: §5 Ease Roles Demo 守衛 ────────────────────────────────────────
MOTION_LAB_HTML_T2 = Path(__file__).parent.parent.parent / "web" / "templates" / "motion_lab.html"
MOTION_LAB_JS_T2 = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "motion-lab.js"


class TestMotionLabT2EaseRoles:
    """52-T2.1: 守衛 §5 Ease Roles 並排 demo 必要元素"""

    def _html(self) -> str:
        return MOTION_LAB_HTML_T2.read_text(encoding="utf-8")

    def _js(self) -> str:
        return MOTION_LAB_JS_T2.read_text(encoding="utf-8")

    def test_html_contains_fluent_decel(self):
        """motion_lab.html 含 fluent-decel 字樣（Ease Roles select 選項或 demo panel）"""
        assert "fluent-decel" in self._html(), \
            "motion_lab.html 缺少 fluent-decel（§5 Ease Roles select / demo panel 未加入）"

    def test_html_contains_fluent_accel(self):
        """motion_lab.html 含 fluent-accel 字樣（Ease Roles select 選項或 demo panel）"""
        assert "fluent-accel" in self._html(), \
            "motion_lab.html 缺少 fluent-accel（§5 Ease Roles select / demo panel 未加入）"

    def test_html_has_ease_roles_tab(self):
        """motion_lab.html tab bar 含 ease-roles tab button"""
        assert "ease-roles" in self._html(), \
            "motion_lab.html tab bar 缺少 ease-roles tab（§5 Ease Roles tab 未加入）"

    def test_js_has_play_ease_roles_demo(self):
        """motion-lab.js 含 playEaseRolesDemo 函式"""
        assert "playEaseRolesDemo" in self._js(), \
            "motion-lab.js 缺少 playEaseRolesDemo（§5 Ease Roles demo 函式未加入）"

    def test_js_no_bare_back_out_in_stream(self):
        """motion-lab.js playCardStreamIn 不含裸 power2.out / power3.out（已改 fluent-decel）"""
        js = self._js()
        # 找到 playCardStreamIn 區塊（到下一個函式前）
        start = js.find("playCardStreamIn:")
        assert start != -1, \
            "playCardStreamIn 函式不見了；如果是重命名請更新此守衛"
        end = js.find("\n        /**", start + 1)
        block = js[start:end] if end != -1 else js[start:]
        assert "power3.out" not in block, \
            "playCardStreamIn 仍含 power3.out（應改為 fluent-decel）"
        assert "power2.out" not in block, \
            "playCardStreamIn 仍含 power2.out（應改為 fluent-decel）"


MOTION_LAB_HTML_T2_2 = Path(__file__).parent.parent.parent / "web" / "templates" / "motion_lab.html"
MOTION_LAB_JS_T2_2 = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "motion-lab.js"


class TestMotionLabT2DurationBuckets:
    """52-T2.2: 守衛 §5 Duration Buckets 並排 demo 必要元素"""

    def _html(self) -> str:
        return MOTION_LAB_HTML_T2_2.read_text(encoding="utf-8")

    def _js(self) -> str:
        return MOTION_LAB_JS_T2_2.read_text(encoding="utf-8")

    def test_html_has_duration_buckets_tab(self):
        """motion_lab.html tab bar 含 duration-buckets tab button"""
        assert "duration-buckets" in self._html(), \
            "motion_lab.html tab bar 缺少 duration-buckets tab（§5 Duration Buckets tab 未加入）"

    def test_js_has_play_duration_buckets_demo(self):
        """motion-lab.js 含 playDurationBucketsDemo 函式"""
        assert "playDurationBucketsDemo" in self._js(), \
            "motion-lab.js 缺少 playDurationBucketsDemo（§5 Duration Buckets demo 函式未加入）"

    def test_html_shows_duration_fast_label(self):
        """motion_lab.html 含 DURATION.fast 標籤（duration-buckets panel box label）"""
        assert "DURATION.fast" in self._html(), \
            "motion_lab.html 缺少 DURATION.fast 標籤（§5 Duration Buckets panel box label 未加入）"


# ─── 52-T2.3: §5 Special Motion White-list Demo 守衛 ──────────────────────────
MOTION_LAB_HTML_T2_3 = Path(__file__).parent.parent.parent / "web" / "templates" / "motion_lab.html"
MOTION_LAB_JS_T2_3 = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "pages" / "motion-lab.js"


class TestMotionLabT2SpecialMotion:
    """52-T2.3: 守衛 §5 Special Motion 白名單 demo 必要元素"""

    def _html(self) -> str:
        return MOTION_LAB_HTML_T2_3.read_text(encoding="utf-8")

    def _js(self) -> str:
        return MOTION_LAB_JS_T2_3.read_text(encoding="utf-8")

    def test_html_has_special_motion_tab(self):
        """motion_lab.html tab bar 含 special-motion tab button"""
        assert "special-motion" in self._html(), \
            "motion_lab.html tab bar 缺少 special-motion tab（§5 Special Motion 白名單 tab 未加入）"

    def test_js_has_play_special_motion_checkmark_demo(self):
        """motion-lab.js 含 playSpecialMotionCheckmarkDemo 函式"""
        assert "playSpecialMotionCheckmarkDemo" in self._js(), \
            "motion-lab.js 缺少 playSpecialMotionCheckmarkDemo（§5 Special Motion checkmark demo 函式未加入）"

    def test_js_has_play_special_motion_shake_demo(self):
        """motion-lab.js 含 playSpecialMotionShakeDemo 函式"""
        assert "playSpecialMotionShakeDemo" in self._js(), \
            "motion-lab.js 缺少 playSpecialMotionShakeDemo（§5 Special Motion shake demo 函式未加入）"

    def test_js_has_play_special_motion_pulse_demo(self):
        """motion-lab.js 含 playSpecialMotionPulseDemo 函式"""
        assert "playSpecialMotionPulseDemo" in self._js(), \
            "motion-lab.js 缺少 playSpecialMotionPulseDemo（§5 Special Motion pulse demo 函式未加入）"

    def test_html_has_whitelist_skip_note(self):
        """motion_lab.html special-motion panel 含 whitelist-skip-note 跳過說明"""
        assert "whitelist-skip-note" in self._html(), \
            "motion_lab.html 缺少 whitelist-skip-note（§5 Special Motion 跳過條目說明未加入）"


# ─── 54a-T1: importmap + pre_alpine_module slot + ghost-fly ESM export 守衛 ───
_BASE_HTML_54A = Path(__file__).parent.parent.parent / "web" / "templates" / "base.html"
_GHOST_FLY_JS_54A = Path(__file__).parent.parent.parent / "web" / "static" / "js" / "shared" / "ghost-fly.js"


class TestImportMapGuard:
    """54a-T1: importmap + pre_alpine_module slot + ghost-fly ESM export guards"""

    def _base(self) -> str:
        return _BASE_HTML_54A.read_text(encoding="utf-8")

    def _ghost_fly(self) -> str:
        return _GHOST_FLY_JS_54A.read_text(encoding="utf-8")

    def test_importmap_exists(self):
        """base.html 含 type="importmap" 字串"""
        assert 'type="importmap"' in self._base(), \
            'base.html 缺少 <script type="importmap">（54a-T1 importmap 未插入）'

    def test_importmap_aliases(self):
        """base.html importmap 含六個 @/ alias"""
        content = self._base()
        for alias in ('"@/shared/"', '"@/components/"', '"@/showcase/"',
                      '"@/scanner/"', '"@/settings/"', '"@/search/"'):
            assert alias in content, \
                f'base.html importmap 缺少 {alias} alias（54a-T1 importmap alias 未設定）'

    def test_pre_alpine_module_slot(self):
        """base.html 含 {% block pre_alpine_module %} slot"""
        assert "{% block pre_alpine_module %}" in self._base(), \
            "base.html 缺少 {% block pre_alpine_module %}（54a-T1 slot 未插入）"

    def test_ghost_fly_has_export(self):
        """ghost-fly.js 含 export 關鍵字"""
        assert "export" in self._ghost_fly(), \
            "ghost-fly.js 缺少 export（54a-T1 ESM export 未加入）"

    def test_ghost_fly_window_bridge(self):
        """ghost-fly.js 含 window.GhostFly 賦值（橋接保留）"""
        assert "window.GhostFly = GhostFly" in self._ghost_fly(), \
            "ghost-fly.js 缺少 window.GhostFly = GhostFly（54a-T1 window 橋接被移除）"

    def test_ghost_fly_script_tag_is_module(self):
        """base.html 中 ghost-fly.js 的 script tag 是 type="module"，無殘留 defer 標籤"""
        content = self._base()
        assert 'type="module" src="/static/js/shared/ghost-fly.js"' in content, \
            'base.html ghost-fly.js script tag 非 type="module"（54a-T1 script tag 未更新）'
        assert '<script defer src="/static/js/shared/ghost-fly.js">' not in content, \
            'base.html 仍有殘留的 <script defer src=".../ghost-fly.js">（54a-T1 舊標籤未移除）'


class TestESMExportGuard:
    """
    54a-T2：守衛五個 shared/components 工具的 ESM export + window 橋接 + base.html script tag
    前置：TestImportMapGuard 通過（T1 spike gate）
    """

    def _read(self, rel_path):
        return Path(__file__).parent.parent.parent / rel_path

    def _burst_picker(self):
        return (self._read("web/static/js/shared/burst-picker.js")).read_text(encoding="utf-8")

    def _motion_adapter(self):
        return (self._read("web/static/js/components/motion-adapter.js")).read_text(encoding="utf-8")

    def _path_utils(self):
        return (self._read("web/static/js/components/path-utils.js")).read_text(encoding="utf-8")

    def _page_lifecycle(self):
        return (self._read("web/static/js/components/page-lifecycle.js")).read_text(encoding="utf-8")

    def _motion_prefs(self):
        return (self._read("web/static/js/components/motion-prefs.js")).read_text(encoding="utf-8")

    def _base(self):
        return (self._read("web/templates/base.html")).read_text(encoding="utf-8")

    def test_burst_picker_export_and_bridge(self):
        """burst-picker.js 含 export + window.BurstPicker 橋接"""
        content = self._burst_picker()
        assert "export" in content, \
            "burst-picker.js 缺少 export（54a-T2 ESM export 未加入）"
        assert "window.BurstPicker" in content, \
            "burst-picker.js 缺少 window.BurstPicker（54a-T2 window 橋接被移除）"

    def test_motion_adapter_export_and_bridge(self):
        """motion-adapter.js 含 export + window.OpenAver.motion 橋接"""
        content = self._motion_adapter()
        assert "export" in content, \
            "motion-adapter.js 缺少 export（54a-T2 ESM export 未加入）"
        assert "window.OpenAver.motion" in content, \
            "motion-adapter.js 缺少 window.OpenAver.motion（54a-T2 window 橋接被移除）"

    def test_path_utils_export_and_bridge(self):
        """path-utils.js 含 export pathToDisplay + window.pathToDisplay 橋接"""
        content = self._path_utils()
        assert "export" in content and "pathToDisplay" in content, \
            "path-utils.js 缺少 export pathToDisplay（54a-T2 ESM export 未加入）"
        assert "window.pathToDisplay" in content, \
            "path-utils.js 缺少 window.pathToDisplay（54a-T2 window 橋接被移除）"

    def test_page_lifecycle_export_and_bridge(self):
        """page-lifecycle.js 含 export + window.__registerPage 橋接"""
        content = self._page_lifecycle()
        assert "export" in content, \
            "page-lifecycle.js 缺少 export（54a-T2 ESM export 未加入）"
        assert "window.__registerPage" in content, \
            "page-lifecycle.js 缺少 window.__registerPage（54a-T2 window 橋接被移除）"

    def test_motion_prefs_export_and_bridge(self):
        """motion-prefs.js 含 export + window.OpenAver 初始化保留"""
        content = self._motion_prefs()
        assert "export" in content, \
            "motion-prefs.js 缺少 export（54a-T2 ESM export 未加入）"
        assert "window.OpenAver" in content, \
            "motion-prefs.js 缺少 window.OpenAver（54a-T2 window 橋接被移除）"

    @pytest.mark.parametrize("path", [
        "/static/js/shared/burst-picker.js",
        "/static/js/components/motion-adapter.js",
        "/static/js/components/path-utils.js",
        "/static/js/components/page-lifecycle.js",
        "/static/js/components/motion-prefs.js",
    ])
    def test_five_files_script_tags_are_module(self, path):
        """base.html 中五個工具的 script tag 均為 type="module"，無殘留 <script defer src>"""
        content = self._base()
        assert f'type="module" src="{path}"' in content, \
            f'base.html {path} script tag 非 type="module"（54a-T2 script tag 未更新）'
        assert f'<script defer src="{path}">' not in content, \
            f'base.html 仍有殘留的 <script defer src="{path}">（54a-T2 舊標籤未移除）'


class TestSettingsESMGuard:
    """54d-T1：守衛 settings state 模組 + main.js 結構"""

    def _read(self, rel_path):
        return (Path(__file__).parent.parent.parent / rel_path).read_text(encoding="utf-8")

    def test_state_config_exists_and_exports(self):
        content = self._read("web/static/js/pages/settings/state-config.js")
        assert "export function stateConfig" in content

    def test_state_providers_exists_and_exports(self):
        content = self._read("web/static/js/pages/settings/state-providers.js")
        assert "export function stateProviders" in content

    def test_state_ui_exists_and_exports(self):
        content = self._read("web/static/js/pages/settings/state-ui.js")
        assert "export function stateUI" in content

    def test_main_js_exists_and_has_alpine_init(self):
        content = self._read("web/static/js/pages/settings/main.js")
        assert "alpine:init" in content

    def test_main_js_registers_settings_name(self):
        content = self._read("web/static/js/pages/settings/main.js")
        assert "Alpine.data('settings'," in content
        assert "Alpine.data('settingsPage'" not in content

    def test_main_js_uses_importmap_alias(self):
        content = self._read("web/static/js/pages/settings/main.js")
        assert "@/settings/" in content

    def test_no_circular_state_imports(self):
        """三個 state 模組頂層 import 不可引用彼此"""
        import re
        forbidden = ["state-config", "state-providers", "state-ui"]
        for fname in ["state-config.js", "state-providers.js", "state-ui.js"]:
            content = self._read(f"web/static/js/pages/settings/{fname}")
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped.startswith("import"):
                    continue
                for f in forbidden:
                    assert f not in stripped, \
                        f"{fname} 有循環 import：{stripped}"

    # ── T2 guards ──────────────────────────────────────────────────────────

    def test_settings_html_has_pre_alpine_module(self):
        """settings.html 含 pre_alpine_module block override，含 main.js module script"""
        content = self._read("web/templates/settings.html")
        assert "pre_alpine_module" in content, \
            "settings.html 缺少 {% block pre_alpine_module %}（54d-T2 未加入 main.js 載入）"
        assert "settings/main.js" in content, \
            "settings.html pre_alpine_module block 缺少 main.js module script"

    def test_settings_html_xdata_is_settings(self):
        """settings.html x-data 值為 'settings'（非 'settingsPage'）"""
        content = self._read("web/templates/settings.html")
        assert 'x-data="settings"' in content, \
            "settings.html x-data 非 settings（54d-T2 切換未完成）"
        assert 'x-data="settingsPage"' not in content, \
            "settings.html 仍有舊 x-data=settingsPage（54d-T2 切換未完成）"

    def test_settings_html_no_settings_js_script(self):
        """settings.html extra_js block 不含 /pages/settings.js script 載入"""
        content = self._read("web/templates/settings.html")
        assert "/pages/settings.js" not in content, \
            "settings.html 仍載入舊 settings.js（54d-T2 未移除）"

    def test_settings_js_deleted(self):
        """web/static/js/pages/settings.js 不存在"""
        from pathlib import Path
        p = Path(__file__).parent.parent.parent / "web/static/js/pages/settings.js"
        assert not p.exists(), \
            "settings.js 仍存在（54d-T2 刪除步驟未執行）"

    def test_no_settings_page_xdata_in_templates(self):
        """所有 production templates 不含 x-data=\"settingsPage\"（防殘留）"""
        from pathlib import Path
        templates_dir = Path(__file__).parent.parent.parent / "web/templates"
        for tmpl in templates_dir.rglob("*.html"):
            content = tmpl.read_text(encoding="utf-8")
            assert 'x-data="settingsPage"' not in content, \
                f"{tmpl.name} 仍含 x-data=settingsPage（54d-T2 殘留）"

    def test_no_settings_page_alpine_data_in_js(self):
        """web/static/js/pages/ 下所有 JS 不含 Alpine.data('settingsPage'（防殘留）"""
        from pathlib import Path
        pages_dir = Path(__file__).parent.parent.parent / "web/static/js/pages"
        for js_file in pages_dir.rglob("*.js"):
            content = js_file.read_text(encoding="utf-8")
            assert "Alpine.data('settingsPage'" not in content, \
                f"{js_file.name} 仍含 Alpine.data('settingsPage'（54d-T2 殘留）"

    def test_main_js_no_settingspage_reference(self):
        """settings/main.js 不含 settingsPage 字串"""
        content = self._read("web/static/js/pages/settings/main.js")
        assert "settingsPage" not in content, \
            "settings/main.js 含 settingsPage（54d-T2 設計錯誤）"

    def test_main_js_uses_descriptor_merge(self):
        """main.js 使用 descriptor-preserving merge 而非 object spread，
        防止 getter（isDirty、folderPreviewText 等）在合併時被立即求值成靜態值"""
        content = self._read("web/static/js/pages/settings/main.js")
        assert "getOwnPropertyDescriptors" in content, \
            "settings/main.js 缺少 getOwnPropertyDescriptors（54d Codex P1 修正未套用）"
        assert "...stateConfig()" not in content, \
            "settings/main.js 仍使用 spread 合併 stateConfig()（54d Codex P1 修正未套用）"

    def test_state_config_has_getter_isDirty(self):
        """state-config.js 的 isDirty 必須是 getter（get isDirty()），
        確保 mergeState 有 getter 可以保留"""
        content = self._read("web/static/js/pages/settings/state-config.js")
        assert "get isDirty()" in content, \
            "state-config.js 的 isDirty 不是 getter — spread bug 修正依賴此 getter"


class TestScannerESMGuard:
    """54c-T1：守衛 scanner state 模組 + main.js 結構"""

    def _read(self, rel_path):
        return (Path(__file__).parent.parent.parent / rel_path).read_text(encoding="utf-8")

    def test_state_scan_exists_and_exports(self):
        """驗 state-scan.js 存在且含 export function stateScan"""
        content = self._read("web/static/js/pages/scanner/state-scan.js")
        assert "export function stateScan" in content

    def test_state_batch_exists_and_exports(self):
        """驗 state-batch.js 存在且含 export function stateBatch"""
        content = self._read("web/static/js/pages/scanner/state-batch.js")
        assert "export function stateBatch" in content

    def test_state_alias_exists_and_exports(self):
        """驗 state-alias.js 存在且含 export function stateAlias"""
        content = self._read("web/static/js/pages/scanner/state-alias.js")
        assert "export function stateAlias" in content

    def test_main_js_exists_and_has_alpine_init(self):
        """驗 main.js 存在且含 alpine:init"""
        content = self._read("web/static/js/pages/scanner/main.js")
        assert "alpine:init" in content

    def test_main_js_registers_scanner_name(self):
        """驗 main.js 含 Alpine.data('scanner', 且不含 scannerPage"""
        content = self._read("web/static/js/pages/scanner/main.js")
        assert "Alpine.data('scanner'," in content
        assert "Alpine.data('scannerPage'" not in content

    def test_main_js_uses_importmap_alias(self):
        """驗 main.js import 語句使用 @/scanner/ alias"""
        content = self._read("web/static/js/pages/scanner/main.js")
        assert "@/scanner/" in content

    def test_main_js_has_descriptor_merge(self):
        """驗 main.js 含 getOwnPropertyDescriptors 或 defineProperties（確保 getter 不被 spread 破壞）"""
        content = self._read("web/static/js/pages/scanner/main.js")
        assert "getOwnPropertyDescriptors" in content or "defineProperties" in content

    def test_main_js_no_plain_spread_merge(self):
        """驗 main.js 不含三個 state 的 plain spread（...stateScan() 等）"""
        content = self._read("web/static/js/pages/scanner/main.js")
        assert "...stateScan()" not in content
        assert "...stateBatch()" not in content
        assert "...stateAlias()" not in content

    def test_state_scan_no_batch_functions(self):
        """驗 state-scan.js 不含 batch 函式定義（防誤放；跨模組 this.xxx 呼叫允許）"""
        content = self._read("web/static/js/pages/scanner/state-scan.js")
        # 只防函式定義被放錯模組，不攔 this.checkMissing() 等跨模組呼叫
        assert "checkMissing() {" not in content
        assert "runMissingEnrich" not in content
        assert "resumeMissingEnrich" not in content

    def test_state_batch_no_scan_functions(self):
        """驗 state-batch.js 不含 scan 主流程函式（防誤放）"""
        content = self._read("web/static/js/pages/scanner/state-batch.js")
        assert "generate(" not in content
        assert "runNfoUpdate" not in content
        assert "runJellyfinImageUpdate" not in content
        assert "copyOutputPath" not in content

    def test_no_circular_state_imports(self):
        """驗三個 state 模組頂層 import 不引用彼此"""
        forbidden = ["state-scan", "state-batch", "state-alias"]
        for fname in ["state-scan.js", "state-batch.js", "state-alias.js"]:
            content = self._read(f"web/static/js/pages/scanner/{fname}")
            for line in content.splitlines():
                stripped = line.strip()
                if not stripped.startswith("import"):
                    continue
                for f in forbidden:
                    assert f not in stripped, \
                        f"{fname} 有循環 import：{stripped}"

    def test_scanner_html_has_pre_alpine_module(self):
        """scanner.html 含 pre_alpine_module block override，含 main.js module script"""
        content = self._read("web/templates/scanner.html")
        assert "pre_alpine_module" in content, \
            "scanner.html 缺少 {% block pre_alpine_module %}（54c-T2 未加入 main.js 載入）"
        assert "scanner/main.js" in content, \
            "scanner.html pre_alpine_module block 缺少 main.js module script"

    def test_scanner_html_xdata_is_scanner(self):
        """scanner.html x-data 值為 'scanner'（非 'scannerPage'）"""
        content = self._read("web/templates/scanner.html")
        assert 'x-data="scanner"' in content, \
            "scanner.html x-data 非 scanner（54c-T2 切換未完成）"
        assert 'x-data="scannerPage"' not in content, \
            "scanner.html 仍有舊 x-data=scannerPage（54c-T2 切換未完成）"

    def test_scanner_html_no_scanner_js_script(self):
        """scanner.html extra_js block 不含 /pages/scanner.js script 載入"""
        content = self._read("web/templates/scanner.html")
        assert "/pages/scanner.js" not in content, \
            "scanner.html 仍載入舊 scanner.js（54c-T2 未移除）"

    def test_scanner_js_deleted(self):
        """web/static/js/pages/scanner.js 不存在"""
        from pathlib import Path
        p = Path(__file__).parent.parent.parent / "web/static/js/pages/scanner.js"
        assert not p.exists(), \
            "scanner.js 仍存在（54c-T2 刪除步驟未執行）"

    def test_no_scanner_page_xdata_in_templates(self):
        """所有 production templates 不含 x-data=\"scannerPage\"（防殘留）"""
        from pathlib import Path
        templates_dir = Path(__file__).parent.parent.parent / "web/templates"
        for tmpl in templates_dir.rglob("*.html"):
            content = tmpl.read_text(encoding="utf-8")
            assert 'x-data="scannerPage"' not in content, \
                f"{tmpl.name} 仍含 x-data=scannerPage（54c-T2 殘留）"

    def test_no_scanner_page_alpine_data_in_js(self):
        """web/static/js/pages/ 下所有 JS 不含 Alpine.data('scannerPage'（防殘留）"""
        from pathlib import Path
        pages_dir = Path(__file__).parent.parent.parent / "web/static/js/pages"
        for js_file in pages_dir.rglob("*.js"):
            content = js_file.read_text(encoding="utf-8")
            assert "Alpine.data('scannerPage'" not in content, \
                f"{js_file.name} 仍含 Alpine.data('scannerPage'（54c-T2 殘留）"

    def test_main_js_no_scannerpage_reference(self):
        """scanner/main.js 不含 scannerPage 字串"""
        content = self._read("web/static/js/pages/scanner/main.js")
        assert "scannerPage" not in content, \
            "scanner/main.js 含 scannerPage（54c-T2 設計錯誤）"


class TestShowcaseESMGuard:
    """54b 守衛 — Showcase ESM 模組化

    T1a：state-base.js（foundation）
    T1b：state-videos / state-actress / state-lightbox / main.js
    T2b：showcase.html 切換 + core.js 刪除
    """

    BASE = Path(__file__).parents[2] / "web" / "static" / "js" / "pages" / "showcase"

    def _read(self, filename):
        return (self.BASE / filename).read_text(encoding="utf-8")

    # ── T1a guards（state-base.js foundation）────────────────────────

    def test_state_base_exists_and_exports(self):
        """state-base.js 存在且含 export function stateBase 和 export var _videos"""
        assert (self.BASE / "state-base.js").exists(), (
            "showcase/state-base.js 不存在"
        )
        content = self._read("state-base.js")
        assert "export function stateBase" in content, (
            "state-base.js 缺少 export function stateBase"
        )
        assert "export var _videos" in content or "export let _videos" in content, (
            "state-base.js 缺少 export var _videos（共用陣列必須 export 供其他模組 import）"
        )

    def test_state_base_has_shared_array_exports(self):
        """state-base.js export _videos、_filteredVideos、_actresses、_filteredActresses"""
        content = self._read("state-base.js")
        for var_name in ("_videos", "_filteredVideos", "_actresses", "_filteredActresses"):
            assert var_name in content, (
                f"state-base.js 缺少 {var_name} — "
                "module-level 共用陣列必須在 state-base.js 宣告（F1 性能優化：大陣列移出 Alpine reactive scope）"
            )

    def test_state_base_no_lightbox_functions(self):
        """state-base.js 不含 openLightbox / closeLightbox（防止 lightbox 邏輯誤放入 base）"""
        content = self._read("state-base.js")
        assert "openLightbox(" not in content, (
            "state-base.js 含 openLightbox — lightbox 邏輯應在 state-lightbox.js"
        )
        assert "closeLightbox(" not in content, (
            "state-base.js 含 closeLightbox — lightbox 邏輯應在 state-lightbox.js"
        )

    def test_state_base_no_picker_params(self):
        """state-base.js 不含 _PICKER_PARAMS（應在 stateLightbox 閉包，非 base state）"""
        content = self._read("state-base.js")
        assert "_PICKER_PARAMS" not in content, (
            "state-base.js 含 _PICKER_PARAMS — "
            "此常數應在 stateLightbox() 函式頂部作閉包常數（OQ-54B-2 Option B），不應放 stateBase"
        )

    # ── T1b guards（state-videos / state-actress / state-lightbox / main.js）──

    def test_state_videos_exists_and_exports(self):
        """state-videos.js 存在且含 export function stateVideos"""
        assert (self.BASE / "state-videos.js").exists(), (
            "showcase/state-videos.js 不存在"
        )
        content = self._read("state-videos.js")
        assert "export function stateVideos" in content, (
            "state-videos.js 缺少 export function stateVideos"
        )

    def test_state_actress_exists_and_exports(self):
        """state-actress.js 存在且含 export function stateActress"""
        assert (self.BASE / "state-actress.js").exists(), (
            "showcase/state-actress.js 不存在"
        )
        content = self._read("state-actress.js")
        assert "export function stateActress" in content, (
            "state-actress.js 缺少 export function stateActress"
        )

    def test_state_lightbox_exists_and_exports(self):
        """state-lightbox.js 存在且含 export function stateLightbox"""
        assert (self.BASE / "state-lightbox.js").exists(), (
            "showcase/state-lightbox.js 不存在"
        )
        content = self._read("state-lightbox.js")
        assert "export function stateLightbox" in content, (
            "state-lightbox.js 缺少 export function stateLightbox"
        )

    def test_main_js_exists_and_has_alpine_init(self):
        """main.js 存在且含 alpine:init 事件監聽"""
        assert (self.BASE / "main.js").exists(), (
            "showcase/main.js 不存在"
        )
        content = self._read("main.js")
        assert "alpine:init" in content, (
            "showcase/main.js 缺少 alpine:init 事件監聽"
        )

    def test_main_js_registers_showcase_name(self):
        """main.js 含 Alpine.data('showcase', — 名稱必須是 showcase，非 showcaseState"""
        content = self._read("main.js")
        assert "Alpine.data('showcase'," in content or 'Alpine.data("showcase",' in content, (
            "showcase/main.js 缺少 Alpine.data('showcase', — "
            "54b 要求 Alpine component 名稱從 showcaseState 改為 showcase"
        )
        assert "Alpine.data('showcaseState'" not in content and 'Alpine.data("showcaseState"' not in content, (
            "showcase/main.js 不應含 Alpine.data('showcaseState' — "
            "舊名稱 showcaseState 應已移除，防殘留"
        )

    def test_main_js_uses_importmap_alias(self):
        """main.js import 語句使用 @/showcase/ alias"""
        content = self._read("main.js")
        assert "@/showcase/" in content, (
            "showcase/main.js import 語句缺少 @/showcase/ alias — "
            "必須使用 importmap alias，不可用相對路徑"
        )

    def test_main_js_has_descriptor_merge(self):
        """main.js 含 getOwnPropertyDescriptors 或 defineProperties"""
        content = self._read("main.js")
        has_merge = (
            "getOwnPropertyDescriptors" in content
            or "defineProperties" in content
        )
        assert has_merge, (
            "showcase/main.js 缺少 descriptor-preserving 合併（getOwnPropertyDescriptors 或 defineProperties）"
        )

    def test_main_js_no_plain_spread_merge(self):
        """main.js 不含 plain spread（...stateBase() 等）"""
        content = self._read("main.js")
        for factory in ("stateBase()", "stateVideos()", "stateActress()", "stateLightbox()"):
            assert f"...{factory}" not in content, (
                f"showcase/main.js 含 ...{factory} plain spread — "
                "必須改用 mergeState（descriptor-preserving）"
            )

    def test_main_js_factory_calls_use_call_this(self):
        """main.js 所有 factory 呼叫使用 .call(this)"""
        content = self._read("main.js")
        for factory in ("stateBase", "stateVideos", "stateActress", "stateLightbox"):
            assert f"{factory}.call(this)" in content, (
                f"showcase/main.js 缺少 {factory}.call(this) — "
                "stateBase() 含 this.$persist(...)，bare call 時 this=undefined 會崩潰"
            )

    def test_main_js_has_window_showcase_state_bridge(self):
        """main.js 含 window.showcaseState 橋接"""
        content = self._read("main.js")
        assert "window.showcaseState" in content, (
            "showcase/main.js 缺少 window.showcaseState 橋接 — "
            "spec-54 §5 明確要求保留向後相容橋接"
        )

    def test_no_circular_state_factory_imports(self):
        """state 模組頂層 import 不含其他 state-*.js 的 factory 函式名稱"""
        import re
        factory_names = ["stateBase", "stateVideos", "stateActress", "stateLightbox"]
        for filename in ("state-videos.js", "state-actress.js", "state-lightbox.js"):
            content = self._read(filename)
            import_lines = [
                line for line in content.split("\n")
                if line.strip().startswith("import ")
            ]
            import_text = "\n".join(import_lines)
            for name in factory_names:
                assert name not in import_text, (
                    f"showcase/{filename} 的 import 語句含 {name} — "
                    "state 模組不可 import 其他 state factory，違反 spec-54 §9 D2"
                )

    def test_state_lightbox_imports_kill_timelines(self):
        """state-lightbox.js 從 state-base.js import _killLightboxTimelines"""
        content = self._read("state-lightbox.js")
        assert "_killLightboxTimelines" in content, (
            "state-lightbox.js 缺少 _killLightboxTimelines — "
            "此函式從 state-base.js import，閉包/全域存取均不符 ESM 規範"
        )

    def test_state_videos_no_actress_functions(self):
        """state-videos.js 不含 loadActresses / addFavoriteActress"""
        content = self._read("state-videos.js")
        assert "loadActresses" not in content, (
            "state-videos.js 含 loadActresses — 女優邏輯應在 state-actress.js"
        )
        assert "addFavoriteActress" not in content, (
            "state-videos.js 含 addFavoriteActress — 女優 CRUD 應在 state-actress.js"
        )

    def test_state_actress_no_lightbox_functions(self):
        """state-actress.js 不含 openLightbox / closeLightbox 定義"""
        import re
        content = self._read("state-actress.js")
        assert not re.search(r"^\s+openLightbox\s*\(", content, re.MULTILINE), (
            "state-actress.js 含 openLightbox 方法定義 — 應在 state-lightbox.js"
        )
        assert not re.search(r"^\s+closeLightbox\s*\(", content, re.MULTILINE), (
            "state-actress.js 含 closeLightbox 方法定義 — 應在 state-lightbox.js"
        )

    def test_no_gsap_at_module_top_level(self):
        """state 模組頂層不含 window.gsap 或 gsap 直接存取"""
        import re
        for filename in ("state-base.js", "state-videos.js", "state-actress.js", "state-lightbox.js", "main.js"):
            content = self._read(filename)
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("//") or stripped.startswith("*"):
                    continue
                if line and not line.startswith(" ") and not line.startswith("\t"):
                    if "window.gsap" in line or (re.match(r"^gsap\b", line)):
                        assert False, (
                            f"showcase/{filename} L{i}: 模組頂層含 gsap 存取 — "
                            "spec-54 §9 D3：window.gsap 只在函式體內存取"
                        )

    def test_no_this_picker_params_in_state_modules(self):
        """state 模組不含 this._PICKER_PARAMS（應改為閉包直接存取）"""
        for filename in ("state-base.js", "state-videos.js", "state-actress.js", "state-lightbox.js"):
            content = self._read(filename)
            assert "this._PICKER_PARAMS" not in content, (
                f"showcase/{filename} 含 this._PICKER_PARAMS — "
                "應改為閉包直接存取 _PICKER_PARAMS（無需 this.）"
            )

    # ── T2b guards ────────────────────────────────────────────────────

    def test_showcase_html_has_pre_alpine_module(self):
        """showcase.html 含 {% block pre_alpine_module %} override（含 main.js module script）"""
        html_path = Path(__file__).parents[2] / "web" / "templates" / "showcase.html"
        content = html_path.read_text(encoding="utf-8")
        assert "pre_alpine_module" in content, (
            "showcase.html 缺少 {% block pre_alpine_module %} — "
            "main.js 必須放在此 slot 確保 alpine:init listener 在 Alpine CDN 之前掛上"
        )
        assert "showcase/main.js" in content, (
            "showcase.html 的 pre_alpine_module block 缺少 showcase/main.js module script"
        )

    def test_showcase_html_xdata_is_showcase(self):
        """showcase.html 的 x-data 值為 showcase（非 showcaseState）"""
        html_path = Path(__file__).parents[2] / "web" / "templates" / "showcase.html"
        content = html_path.read_text(encoding="utf-8")
        assert 'x-data="showcase"' in content, (
            'showcase.html 缺少 x-data="showcase" — '
            "54b 要求 x-data 從 showcaseState 改為 showcase"
        )
        assert 'x-data="showcaseState"' not in content, (
            'showcase.html 仍含 x-data="showcaseState" — 舊名稱應已移除'
        )

    def test_showcase_html_no_core_js_script(self):
        """showcase.html 不含 core.js script tag"""
        html_path = Path(__file__).parents[2] / "web" / "templates" / "showcase.html"
        content = html_path.read_text(encoding="utf-8")
        assert "core.js" not in content, (
            "showcase.html 仍含 core.js script tag — 54b 完成後 core.js 應已刪除且 HTML 不再引用"
        )

    def test_showcase_html_still_has_animations_js(self):
        """showcase.html 仍含 animations.js script tag（B5：不動 animations.js）"""
        html_path = Path(__file__).parents[2] / "web" / "templates" / "showcase.html"
        content = html_path.read_text(encoding="utf-8")
        assert "animations.js" in content, (
            "showcase.html 缺少 animations.js script tag — "
            "54b 不動 animations.js，它應仍在 extra_js block 中"
        )

    def test_core_js_deleted(self):
        """web/static/js/pages/showcase/core.js 不存在"""
        core_js = self.BASE / "core.js"
        assert not core_js.exists(), (
            "showcase/core.js 仍然存在 — 54b 完成後應已刪除"
        )

    def test_no_showcase_state_xdata_in_templates(self):
        """所有 production templates 不含 x-data="showcaseState"（防殘留）"""
        templates_dir = Path(__file__).parents[2] / "web" / "templates"
        for tmpl in templates_dir.glob("**/*.html"):
            content = tmpl.read_text(encoding="utf-8")
            assert 'x-data="showcaseState"' not in content, (
                f"{tmpl.name} 仍含 x-data=\"showcaseState\" — 舊名稱應已全部移除"
            )

    def test_no_showcase_state_alpine_data_in_js(self):
        """web/static/js/pages/ 下所有 JS 不含 Alpine.data('showcaseState'（防殘留）"""
        pages_dir = Path(__file__).parents[2] / "web" / "static" / "js" / "pages"
        for js_file in pages_dir.glob("**/*.js"):
            content = js_file.read_text(encoding="utf-8")
            assert "Alpine.data('showcaseState'" not in content and \
                   'Alpine.data("showcaseState"' not in content, (
                f"{js_file.name} 含 Alpine.data('showcaseState' — 舊名稱應已全部移除"
            )


class TestSearchESMGuard:
    """54e 守衛 — Search ESM 遷移（window.SearchStateMixin_* → ESM export）"""

    BASE = Path(__file__).parents[2] / "web" / "static" / "js" / "pages" / "search"
    STATE = BASE / "state"

    def _read_state(self, filename):
        return (self.STATE / filename).read_text(encoding="utf-8")

    def _read_main(self):
        return (self.BASE / "main.js").read_text(encoding="utf-8")

    # ── state 模組 export 驗證（8 條）────────────────────────────────

    def test_state_base_exists_and_exports(self):
        """state/base.js 含 export function searchStateBase"""
        content = self._read_state("base.js")
        assert "export function searchStateBase" in content, (
            "state/base.js 缺少 export function searchStateBase — "
            "需將 window.SearchStateMixin_Base = function() 改為 export function searchStateBase()"
        )

    def test_state_persistence_exists_and_exports(self):
        """state/persistence.js 含 export function searchStatePersistence"""
        content = self._read_state("persistence.js")
        assert "export function searchStatePersistence" in content

    def test_state_search_flow_exists_and_exports(self):
        """state/search-flow.js 含 export function searchStateSearchFlow"""
        content = self._read_state("search-flow.js")
        assert "export function searchStateSearchFlow" in content

    def test_state_navigation_exists_and_exports(self):
        """state/navigation.js 含 export function searchStateNavigation"""
        content = self._read_state("navigation.js")
        assert "export function searchStateNavigation" in content

    def test_state_batch_exists_and_exports(self):
        """state/batch.js 含 export function searchStateBatch"""
        content = self._read_state("batch.js")
        assert "export function searchStateBatch" in content

    def test_state_result_card_exists_and_exports(self):
        """state/result-card.js 含 export function searchStateResultCard"""
        content = self._read_state("result-card.js")
        assert "export function searchStateResultCard" in content

    def test_state_file_list_exists_and_exports(self):
        """state/file-list.js 含 export function searchStateFileList"""
        content = self._read_state("file-list.js")
        assert "export function searchStateFileList" in content

    def test_state_grid_mode_exists_and_exports(self):
        """state/grid-mode.js 含 export function searchStateGridMode"""
        content = self._read_state("grid-mode.js")
        assert "export function searchStateGridMode" in content

    # ── main.js 驗證（4 條）─────────────────────────────────────────

    def test_main_js_exists_and_has_alpine_init(self):
        """search/main.js 存在且含 alpine:init"""
        assert (self.BASE / "main.js").exists(), "search/main.js 不存在"
        content = self._read_main()
        assert "alpine:init" in content

    def test_main_js_registers_search_page_name(self):
        """main.js 含 Alpine.data('searchPage',"""
        content = self._read_main()
        assert "Alpine.data('searchPage'" in content or 'Alpine.data("searchPage"' in content, (
            "main.js 缺少 Alpine.data('searchPage', — component 名稱必須保持 searchPage"
        )

    def test_main_js_uses_importmap_alias(self):
        """main.js import 使用 @/search/state/ alias"""
        content = self._read_main()
        assert "@/search/state/" in content, (
            "main.js 缺少 @/search/state/ import alias — 需使用 importmap 別名"
        )

    def test_main_js_uses_merge_state_not_spread(self):
        """main.js 使用 descriptor-preserving mergeState（含 Object.getOwnPropertyDescriptors 和 Object.defineProperties），且不含 plain spread"""
        content = self._read_main()
        assert "Object.getOwnPropertyDescriptors" in content, (
            "main.js 缺少 Object.getOwnPropertyDescriptors — "
            "必須使用 descriptor-preserving mergeState 保留 base.js L300 的 get isCloudSearchMode() getter"
        )
        assert "Object.defineProperties" in content, (
            "main.js 缺少 Object.defineProperties — mergeState 必須用此 API"
        )
        assert "...searchStateBase()" not in content, (
            "main.js 含 ...searchStateBase() plain spread — 會凍結 getter，用 mergeState() 取代"
        )

    # ── 防殘留驗證（4 條）────────────────────────────────────────────

    def test_no_window_mixin_in_state_modules(self):
        """8 個 state 模組均不含 window.SearchStateMixin_ 字串"""
        state_files = [
            "base.js", "persistence.js", "search-flow.js", "navigation.js",
            "batch.js", "result-card.js", "file-list.js", "grid-mode.js",
        ]
        for fname in state_files:
            content = self._read_state(fname)
            assert "window.SearchStateMixin_" not in content, (
                f"state/{fname} 仍含 window.SearchStateMixin_ — 舊全域名稱應已移除"
            )

    def test_no_circular_state_imports(self):
        """8 個 state 模組頂層 import 語句不互相引用"""
        state_files = [
            "base.js", "persistence.js", "search-flow.js", "navigation.js",
            "batch.js", "result-card.js", "file-list.js", "grid-mode.js",
        ]
        state_names = [f.replace(".js", "") for f in state_files]
        for fname in state_files:
            content = self._read_state(fname)
            import_lines = [
                line for line in content.splitlines()
                if line.strip().startswith("import ")
            ]
            for imp_line in import_lines:
                for other in state_names:
                    if other != fname.replace(".js", "") and f"state/{other}" in imp_line:
                        raise AssertionError(
                            f"state/{fname} 頂層 import 引用了 state/{other} — "
                            "state 模組不可互相 import（D2 規則），跨模組連接只在 main.js 做"
                        )

    def test_no_window_search_state_mixin_in_templates(self):
        """所有 templates 不含 window.SearchStateMixin_"""
        templates_dir = Path(__file__).parents[2] / "web" / "templates"
        for tmpl in templates_dir.glob("**/*.html"):
            content = tmpl.read_text(encoding="utf-8")
            assert "window.SearchStateMixin_" not in content, (
                f"{tmpl.name} 含 window.SearchStateMixin_ — 舊全域名稱應已全部移除"
            )

    def test_no_window_search_state_mixin_in_pages_js(self):
        """pages/search/ 下所有 JS 不含 window.SearchStateMixin_ 賦值"""
        search_dir = self.BASE
        for js_file in search_dir.glob("**/*.js"):
            content = js_file.read_text(encoding="utf-8")
            assert "window.SearchStateMixin_" not in content, (
                f"{js_file.name} 含 window.SearchStateMixin_ — 舊全域名稱應已全部移除"
            )

    # ── HTML 切換驗證（4 條）─────────────────────────────────────────

    def test_search_html_has_pre_alpine_module(self):
        """search.html 含 {% block pre_alpine_module %} 且含 search/main.js module script"""
        html_path = Path(__file__).parents[2] / "web" / "templates" / "search.html"
        content = html_path.read_text(encoding="utf-8")
        assert "pre_alpine_module" in content, (
            "search.html 缺少 {% block pre_alpine_module %} — "
            "main.js 必須放在此 slot 確保 alpine:init listener 在 Alpine CDN 之前掛上"
        )
        assert "search/main.js" in content, (
            "search.html 缺少 search/main.js module script"
        )

    def test_search_html_xdata_is_search_page(self):
        """search.html 仍含 x-data=\"searchPage\"（防誤改）"""
        html_path = Path(__file__).parents[2] / "web" / "templates" / "search.html"
        content = html_path.read_text(encoding="utf-8")
        assert 'x-data="searchPage"' in content, (
            'search.html 缺少 x-data="searchPage" — component 名稱必須保持 searchPage'
        )

    def test_search_html_no_old_state_script_tags(self):
        """search.html 不含 9 個舊 state script tag（逐一 assert）"""
        html_path = Path(__file__).parents[2] / "web" / "templates" / "search.html"
        content = html_path.read_text(encoding="utf-8")
        old_scripts = [
            "state/base.js",
            "state/persistence.js",
            "state/search-flow.js",
            "state/navigation.js",
            "state/batch.js",
            "state/result-card.js",
            "state/file-list.js",
            "state/grid-mode.js",
            "state/index.js",
        ]
        for script in old_scripts:
            assert script not in content, (
                f"search.html 仍含 {script} script tag — "
                "54e 完成後應改由 ESM main.js 載入，所有 state 模組 classic script tag 應已移除"
            )

    def test_search_state_index_js_deleted(self):
        """search/state/index.js 不存在"""
        index_js = self.STATE / "index.js"
        assert not index_js.exists(), (
            "search/state/index.js 仍然存在 — 54e 完成後 index.js 職責已由 main.js 接替，應已刪除"
        )
