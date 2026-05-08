// web/static/js/pages/settings/state-clip-settings.js
export function stateClipSettings() {
    return {
        // ── toggle state（獨立於 form，不被 isDirty 追蹤）────────
        clipEnabled: false,
        // 由 state-config.js loadConfig() 在 savedState 快照後同步
        // 從 config.clip.enabled；toggle 操作走 dedicated endpoint，
        // 不經 saveConfig 寫回

        // ── status box state ─────────────────────────────────────
        clipPhase: 'idle',
        // 'idle'         = box 隱藏
        // 'downloading'  = 下載中（顯示 X% / XX MB / 80 MB）
        // 'indexing'     = 建索引中（顯示 X / Y 片）
        // 'ready'        = 完成（顯示「已啟用 ✓」+ 測試推論按鈕）
        // 'error'        = 失敗（顯示錯誤訊息 + 重試按鈕）

        clipDownloadProgress: 0,
        clipDownloadBytes: 0,
        clipDownloadTotal: 80 * 1024 * 1024,  // 80 MB fallback
        clipIndexDone: 0,
        clipIndexTotal: 0,
        clipErrorMessage: '',

        // ── popover state ─────────────────────────────────────────
        showClipHelp: false,

        // ── modal state（CD-56D-5）────────────────────────────────
        clipDisableModalOpen: false,
        _clipDisableLoading: false,

        // ── test inference state（CD-56D-7，plan-56f.md 56f-T5）──
        _testInferenceLoading: false,

        // ── computed ──────────────────────────────────────────────
        get clipStatusBoxVisible() {
            return this.clipPhase !== 'idle';
        },
        get clipDownloadPercent() {
            return Math.round(this.clipDownloadProgress * 100);
        },
        get clipDownloadMBStr() {
            const mb = (this.clipDownloadBytes / 1024 / 1024).toFixed(1);
            const total = (this.clipDownloadTotal / 1024 / 1024).toFixed(0);
            return `${mb} / ${total} MB`;
        },
        get clipIndexPercent() {
            return this.clipIndexTotal > 0
                ? Math.round((this.clipIndexDone / this.clipIndexTotal) * 100)
                : 0;
        },

        // ── methods（殼，T3/T4/56f-T5 補實作）───────────────────
        async onClipToggleChange(event) { /* T3 補實作 */ },
        async openClipDisableModal() { /* T4 補實作 */ },
        cancelClipDisableModal() { /* T4 補實作 */ },
        async confirmClipDisable() { /* T4 補實作 */ },
        async testClipInference() { /* plan-56f.md 56f-T5 補實作 */ },
        _connectClipStatusSSE(url, options) { /* T3 補實作 */ },
        _handleClipSseEvent(data) { /* T3 補實作 */ },
        _mergeClipStatusSnapshot(snap) { /* T3 補實作 */ },
        async _restoreClipStatusOnPageLoad() { /* T3 補實作 */ },
        _startClipStatusPolling() { /* T3 補實作 */ },
    };
}
