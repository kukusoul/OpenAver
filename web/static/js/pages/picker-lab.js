/**
 * Picker Lab Phase 1 — Alpine state for /picker-lab dev sandbox
 *
 * 復刻 49b T1 prototype 的 picker burst + float 動畫，但完全本機資源、
 * mock SSE。不改變 production /showcase 行為。詳見 spec-49c.md。
 */
(function () {
    'use strict';

    // T1 fix2 定案動畫參數（與 /showcase _PICKER_PARAMS 相同）
    const _PICKER_PARAMS = {
        arcOvershoot: 1.4,
        arcDuration: 0.6,
        floatAmplY: 8,
        floatAmplRot: 2.5,
        floatDuration: 1.5,
        hoverScale: 1.12,
        exitGravity: 1200,
    };

    function pickerLabState() {
        return {
            // ── Picker 核心 state（命名與 /showcase 對齊） ─────────────
            _pickerOpen: false,
            _pickerLoading: false,
            _pickerSelected: false,
            _candidates: [],
            _pickerCurrentSource: null,
            _pickerFloatTweens: [],
            _pickerRunId: 0,
            coverSrc: '',

            // ── Lab control state ─────────────────────────────────────
            lab: {
                mockCandidates: [],          // injected at init()
                sseMode: 'mixed',            // 'mixed' | 'instant' | 'slow'
                candidateCount: 6,
                cloudDelay: 800,
                localDelay: 50,
                injectPostFail: false,
                reducedMotion: false,
                log: [],
                _t0: Date.now(),
            },

            // ── Init ──────────────────────────────────────────────────
            init() {
                const data = window.__pickerLabData || {};
                const mockCandidates = data.mockCandidates || [];
                this.lab.mockCandidates = mockCandidates;
                this.lab.candidateCount = Math.min(6, mockCandidates.length);
                this._pickerCurrentSource = data.currentSource || null;
                this.coverSrc = mockCandidates[0]?.full_url || '';
                this._log(`init — ${mockCandidates.length} mock candidates loaded`);
            },

            _log(msg) {
                this.lab.log.push({ t: Date.now() - this.lab._t0, msg });
                if (this.lab.log.length > 200) this.lab.log.shift();
            },

            // ── Open / Reset ──────────────────────────────────────────
            async openPicker() {
                if (this._pickerOpen) {
                    this._log('refresh while open — teardown first');
                    this._teardownPicker();
                }
                this._pickerOpen = true;
                this._pickerLoading = true;
                this._pickerSelected = false;
                this._candidates = [];
                this._pickerRunId++;
                const runId = this._pickerRunId;
                this._log(`openPicker run=${runId} mode=${this.lab.sseMode}`);
                await this._simulateSSE(runId);
            },

            cancelPicker() {
                // P5 會擴充為 reverse 動畫；P1 先做 hard close
                this._log('cancelPicker (P1: hard close, no reverse)');
                this._teardownPicker();
            },

            reset() {
                this._teardownPicker();
                this._pickerSelected = false;
                this.coverSrc = this.lab.mockCandidates[0]?.full_url || '';
                this.lab.log = [];
                this.lab._t0 = Date.now();
                this._log('reset');
            },

            _teardownPicker() {
                this._pickerRunId++;   // invalidate any in-flight callbacks
                this._pickerOpen = false;
                this._pickerLoading = false;
                this._candidates = [];
                this._pickerCurrentSource = this._pickerCurrentSource;  // keep label
                this._pickerFloatTweens.forEach(t => t && t.kill && t.kill());
                this._pickerFloatTweens = [];
            },

            // ── Mock SSE simulator ───────────────────────────────────
            async _simulateSSE(runId) {
                const cands = this.lab.mockCandidates.slice(0, this.lab.candidateCount);
                for (let i = 0; i < cands.length; i++) {
                    const c = cands[i];
                    let delay;
                    if (this.lab.sseMode === 'slow') {
                        delay = 800;
                    } else if (this.lab.sseMode === 'instant') {
                        delay = 0;
                    } else {
                        // mixed：cloud 慢、local 快
                        delay = c.source === 'local_crop' ? this.lab.localDelay : this.lab.cloudDelay;
                    }
                    if (delay > 0) await new Promise(r => setTimeout(r, delay));
                    if (this._pickerRunId !== runId) {
                        this._log(`stale runId at i=${i} — abort SSE`);
                        return;
                    }
                    await this._onCandidate(c, runId, i);
                }
                if (this._pickerRunId === runId) {
                    this._pickerLoading = false;
                    this._log(`SSE done — total=${this._candidates.length}`);
                }
            },

            async _onCandidate(candidate, runId, sseIndex) {
                // Race fix（同 /showcase 49c d37c250）：push 後同步 capture myIndex
                this._candidates = [...this._candidates, candidate];
                const myIndex = this._candidates.length - 1;
                await this.$nextTick();
                if (this._pickerRunId !== runId) return;

                const grid = this.$refs.pickerGrid;
                if (grid && typeof window.BurstPicker !== 'undefined') {
                    const cards = grid.querySelectorAll('.picker-candidate-card');
                    const newCard = cards[myIndex];
                    if (newCard) {
                        // 跟 /showcase 一致：用 $refs，避免 @click handler 內 $el 變按鈕
                        const coverEl = this.$refs.coverImg;
                        window.BurstPicker.playPickerBurst([newCard], coverEl, _PICKER_PARAMS, {
                            streamMode: 'instant',
                            floatTimerSink: this._pickerFloatTweens,
                            runId,
                            getRunId: () => this._pickerRunId,
                        });
                        this._log(`burst card[${myIndex}] source=${candidate.source}`);
                    }
                }
            },

            // ── Inspector helper ──────────────────────────────────────
            _inspectorState() {
                return JSON.stringify({
                    _pickerOpen: this._pickerOpen,
                    _pickerLoading: this._pickerLoading,
                    _pickerSelected: this._pickerSelected,
                    candidates: this._candidates.length,
                    _pickerRunId: this._pickerRunId,
                    sources: this._candidates.map(c => c.source),
                }, null, 2);
            },

            // ── Hover (P2 will fully integrate) ──────────────────────
            _onPickerHoverIn(el, i) {
                if (this._pickerSelected) return;
                if (typeof window.BurstPicker !== 'undefined') {
                    window.BurstPicker.playPickerHoverIn(el, _PICKER_PARAMS);
                }
            },
            async _onPickerHoverOut(el, i) {
                if (this._pickerSelected) return;
                if (typeof window.BurstPicker === 'undefined') return;
                await window.BurstPicker.playPickerHoverOut(el, _PICKER_PARAMS);
                if (this._pickerSelected || !this._pickerOpen || !el.isConnected) return;
                const tl = window.BurstPicker.playPickerFloat(el, _PICKER_PARAMS);
                if (tl) this._pickerFloatTweens.push(tl);
            },

            // ── Select (P3 will implement; P1 stub) ──────────────────
            _onPickerSelect(c, i) {
                this._log(`(P3 stub) select card[${i}] source=${c.source}`);
                // P1 不實作替換流程
            },
        };
    }

    document.addEventListener('alpine:init', () => {
        window.Alpine.data('pickerLabState', pickerLabState);
    });
})();
