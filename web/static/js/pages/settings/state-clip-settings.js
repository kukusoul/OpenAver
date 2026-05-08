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
        async onClipToggleChange(event) {
            const enabled = event !== undefined ? event.target.checked : true;
            if (enabled) {
                this.clipPhase = 'downloading';
                this._connectClipStatusSSE('/api/clip/enable', { method: 'POST' });
            } else {
                await this.openClipDisableModal();
            }
        },
        async openClipDisableModal() {
            // rollback 視覺（避免 modal 取消後開關仍 OFF）
            // clipEnabled 是獨立 state（audit BLOCKER G1），不是 this.form.clipEnabled
            this.clipEnabled = true;
            this.clipDisableModalOpen = true;
        },
        cancelClipDisableModal() {
            this.clipDisableModalOpen = false;
            // this.clipEnabled 已是 true（rollback 值），開關視覺保持 ON
        },
        async confirmClipDisable() {
            this._clipDisableLoading = true;
            try {
                const resp = await fetch('/api/clip/disable', { method: 'POST' });
                if (resp.status === 409) {
                    // enable job 進行中，請等流程結束（plan-56d §1 CD-56D-5 後端設計）
                    // 409 是「請等候」語義，不走 catch
                    this.clipDisableModalOpen = false;
                    this.showToast(window.t('clip.disable_modal.toast_busy'), 'warning');
                    return;
                }
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                // 後端 2xx：真正把 clipEnabled 改 false（此前保持 ON rollback 值）
                this.clipEnabled = false;
                this.clipPhase = 'idle';
                this.clipDisableModalOpen = false;
                this.showToast(window.t('clip.disable_modal.toast_done'), 'success');
            } catch (_e) {
                // _e.message 是 fetch HTTP 狀態字串（如 "HTTP 500"）或 "Failed to fetch"
                // 後端已 sanitize（固定中文 detail），前端不解析 detail，不展示 _e.message
                // 4 種 500 子 case 一律統一 toast_failed（audit MAJOR §G4.3）
                this.showToast(window.t('clip.disable_modal.toast_failed'), 'error');
                // clipEnabled 保持 true（rollback 值），開關維持 ON
            } finally {
                this._clipDisableLoading = false;  // 只管 loading flag，不動 clipEnabled
            }
        },
        async testClipInference() { /* plan-56f.md 56f-T5 補實作 */ },
        _connectClipStatusSSE(url, options = {}) {
            fetch(url, { method: options.method || 'POST' }).then(async resp => {
                // non-2xx 先處理，避免把 JSON error body 當 SSE stream 讀
                if (!resp.ok) {
                    if (resp.status === 409) {
                        this.showToast(window.t('clip.enable.toast_busy'), 'warning');
                        this.clipPhase = 'idle';
                    } else {
                        this.clipPhase = 'error';
                        this.clipErrorMessage = window.t('clip.enable.toast_failed');
                    }
                    return;
                }
                const reader = resp.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    // SSE block 以 \n\n 分隔
                    const blocks = buffer.split('\n\n');
                    buffer = blocks.pop();  // 最後一個可能不完整，留給下次拼接
                    for (const block of blocks) {
                        if (!block.startsWith('data: ')) continue;
                        try {
                            const data = JSON.parse(block.slice(6));
                            this._handleClipSseEvent(data);
                        } catch (_) { /* malformed JSON block, skip */ }
                    }
                }
            }).catch(() => {
                // 網路斷線或 fetch 級錯誤；err.message 是瀏覽器訊息，不直接顯示給用戶
                this.clipPhase = 'error';
                this.clipErrorMessage = window.t('clip.enable.toast_failed');
            });
        },
        _handleClipSseEvent(data) {
            if (data.type !== 'status') return;  // future-proof：忽略其他 type
            this._mergeClipStatusSnapshot(data);
        },
        _mergeClipStatusSnapshot(snap) {
            const prevPhase = this.clipPhase;
            if (snap.phase) this.clipPhase = snap.phase;
            if (typeof snap.download_bytes === 'number') {
                this.clipDownloadBytes = snap.download_bytes;
            }
            if (typeof snap.download_total === 'number') {
                // download_total=0 (HF 無 content-length) 保留 80MB fallback
                this.clipDownloadTotal = snap.download_total || this.clipDownloadTotal;
            }
            // cap Math.min(1, ...) 避免超過 100%
            this.clipDownloadProgress = this.clipDownloadTotal > 0
                ? Math.min(1, this.clipDownloadBytes / this.clipDownloadTotal)
                : 0;
            if (typeof snap.index_done === 'number') this.clipIndexDone = snap.index_done;
            if (typeof snap.index_total === 'number') this.clipIndexTotal = snap.index_total;
            if (snap.phase === 'error' && snap.error_message) {
                // 後端已 sanitize 為固定中文，直接顯示
                this.clipErrorMessage = snap.error_message;
            }
            // Fix 2 (codex P3a): ready 5s auto-fade（只在初次進入 ready 時啟動，防 polling/SSE 重複觸發）
            // frontend phase → 'idle' 後 status box 靠 x-transition 自然 fade；
            // backend phase 仍是 'ready'，下次 page load 走 ready-early-return，行為一致
            if (this.clipPhase === 'ready' && prevPhase !== 'ready') {
                setTimeout(() => {
                    if (this.clipPhase === 'ready') this.clipPhase = 'idle';
                }, 5000);
            }
        },
        async _restoreClipStatusOnPageLoad() {
            try {
                const resp = await fetch('/api/clip/status');
                const snap = await resp.json();
                // idle：尚未啟用，正常；不顯示 status box
                // ready：已啟用，開關 ON（由 loadConfig mapping 負責），status box 刻意不還原
                //   （避免每次進 Settings 都顯示多餘的「已啟用 ✓」訊息）
                if (snap.phase === 'idle' || snap.phase === 'ready') return;
                // downloading / indexing / error：後端 enable job 跑過或正在跑，
                // 此時 /api/config 的 clip.enabled 可能還是 false（後端只在 indexing 完才寫），
                // 但前端 toggle 必須顯示 ON 對齊用戶意圖（Fix 1: codex P1）
                this.clipEnabled = true;
                // 還原中間態 + 啟動 polling 持續觀察
                this._mergeClipStatusSnapshot(snap);
                this._startClipStatusPolling();
            } catch (_) { /* ignore，page load 時網路 blip 不影響主流程 */ }
        },
        _startClipStatusPolling() {
            const tick = async () => {
                try {
                    const resp = await fetch('/api/clip/status');
                    const snap = await resp.json();
                    this._mergeClipStatusSnapshot(snap);
                    // 終態（ready / error）停止 polling
                    if (snap.phase === 'downloading' || snap.phase === 'indexing') {
                        setTimeout(tick, 1000);
                    }
                    // ready / error / idle → 不繼續排下一 tick
                } catch (_) {
                    // 網路 blip → 2s 退避後重試
                    setTimeout(tick, 2000);
                }
            };
            tick();  // 立即執行第一次
        },
    };
}
