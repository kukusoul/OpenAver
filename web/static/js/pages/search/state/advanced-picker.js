/**
 * SearchState - Advanced Search Mixin（TASK-61c-7 / 62c-1 / 62c-2）
 *
 * 進階搜尋：長壓搜尋按鈕 → 開 62a 共用重刮彈窗上半部 → 點來源 pill 整包覆寫搜尋。
 * （62c-1：B1 radio picker 已移除，改 include _rescrape_modal.html，番號 input + 來源 pill 點擊即搜。）
 *
 * 機制重點：
 * - enabled gate / sources 清單來自 SSR 注入的 window.__ADVANCED_SEARCH__。
 * - #btnSubmit 長壓入口已退役（74a-T2）；search 進階搜尋入口保留 openRescrape(null,'search') 呼叫。
 *   submit 按鈕的隱式 form 送出保護；form @submit 直接走 doSearch()（不再有 form-level submit guard）。
 * - advancedSearch(source) 走非 stream GET /api/search?q=...&mode=exact&source=<id>（stream 端點無 source param），
 *   自帶 result→Alpine state binding（整包贏由後端 search_jav_single_source 承擔；不呼叫 fallbackSearch）。
 * - OQ-3 軟提示 scaffold：metatube source + 非番號 query + 空結果 → showToast hint（B1 無 metatube source 故不觸發）。
 */

export function searchStateAdvancedPicker() {
    return {
        // ===== Helpers =====
        _advancedConfig() {
            return window.__ADVANCED_SEARCH__ || { sources: [] };
        },

        // ===== 進階搜尋（非 stream，整包贏）=====
        /**
         * 以指定來源覆寫搜尋（單一來源整包贏）。
         * 走非 stream GET /api/search?q=...&mode=exact&source=<id>（stream 端點無 source param）。
         * @param {string} source - 來源 id（builtin id 或 metatube:<id>）
         * @returns {boolean} true = 呼叫端可關窗（成功，或已被新搜尋取代、無事可報）；
         *   false = 查不到／出錯，呼叫端留在 pick 顯示 inline error 讓使用者換下一個來源。
         */
        async advancedSearch(source) {
            const query = this.searchQuery?.trim();
            if (!query || !source) return true;

            // 查不到時背景一格都不該動，所以快照必須在 cancelSearch() **之前** 取。
            // cancelSearch() 沒有 _searchSnapshot 時會把 pageState 設成 'empty'（首頁，
            // search-flow.js 的 else 分支），而 file 模式永遠沒有 snapshot——在它之後才
            // 快照，存下的就是已經被打壞的 'empty'，還原等於跳回首頁。
            // errorKind 全專案無讀取點，一併還原不影響任何人。
            const restore = {
                pageState: this.pageState,
                currentQuery: this.currentQuery,
                errorText: this.errorText,
                errorKind: this.errorKind,
            };

            // 取消現有搜尋（同 doSearch 前置）
            this.cancelSearch();
            this.requestId++;
            const currentRequestId = this.requestId;

            this.currentQuery = query;
            this.pageState = 'loading';
            this.errorText = '';

            this._fallbackAbortController = new AbortController();
            try {
                const url = `/api/search?q=${encodeURIComponent(query)}`
                    + `&mode=exact&source=${encodeURIComponent(source)}`;
                const response = await fetch(url, { signal: this._fallbackAbortController.signal });
                const data = await response.json();

                // 防競態：被新搜尋取代則丟棄
                if (currentRequestId !== this.requestId) return true;

                if (response.ok && data.success && data.data && data.data.length > 0) {
                    this._commitSearchResults(data);
                    return true;
                } else {
                    this._searchSnapshot = null;
                    Object.assign(this, restore);
                    // OQ-3 軟提示 scaffold：metatube source + 非番號 query + 空結果（B1 無 metatube source 故不觸發）
                    this._advancedMaybeMetatubeHint(source, query);
                    return false;
                }
            } catch (err) {
                if (err.name === 'AbortError') return true;
                if (currentRequestId !== this.requestId) return true;
                this._searchSnapshot = null;
                console.error('[AdvancedSearch]', err);
                Object.assign(this, restore);
                return false;
            }
        },

        /**
         * CD-86-14: 共用搜尋結果提交 helper。
         * state-rescrape.js search 入口採用路徑可跨 mixin 呼叫此 helper（mergeState 共享 this）。
         * @param {Object} payload - { data: [...], mode, has_more, actress_profile }
         */
        _commitSearchResults(payload) {
            this.currentMode = payload.mode || this.currentMode;
            this.searchResults = payload.data;
            this.currentIndex = 0;
            this.hasMoreResults = payload.has_more || false;
            this.actressProfile = payload.actress_profile || null;
            if (this.actressProfile) this._heroCardImageError = false;
            // file 模式（卡片上的「使用番號進階搜尋」）：結果寫回當前檔，不切走 listMode。
            // 切成 'search' 的話檔案清單（search.html x-show="listMode === 'file'"）整份消失，
            // 而沒有任何 UI 能切回去——加了一整夾只想修一檔，其餘檔案就這樣不見了。
            // 寫回 file.searchResults 另一個作用：那一列的 ✗ 轉 ✓、「產生 NFO」才會亮
            // （canScrapeFile / scrapeSingle 讀的都是 file.searchResults，不是共享的那份）。
            // 番號比對是 race 防線：關窗到結果回來這段期間使用者可以點別的檔，
            // 不比對就會把這一筆寫進錯的檔。不符就落回原本的 'search' 行為（fail-safe）。
            const _file = this.listMode === 'file' ? this.fileList?.[this.currentFileIndex] : null;
            if (_file && _file.number === this.currentQuery) {
                _file.searchResults = payload.data;
                _file.hasMoreResults = payload.has_more || false;
                _file.searched = true;
                _file.selectedCandidateIndex = 0;
            } else {
                this.listMode = 'search';
            }
            this.checkLocalStatus(this.searchResults);
            this.pageState = 'result';
            this.preloadImages(1, 5);
            this._searchSnapshot = null;
            // TASK-106 Option C: editingTitle/editingChineseTitle 不再在這裡手動歸零——
            // 上面 currentIndex/searchResults 已改寫，persistence.js 的 $watch 會偵測到
            // 候選改變並呼叫 _resetPendingEdits()（連 editingActors 一起清，舊版這裡漏了）。
            this._resetCoverState();
            this.addingTag = false;
        },

        // OQ-3：metatube 來源 + 非番號 + 空結果 → 軟提示（scaffold）
        _advancedMaybeMetatubeHint(source, query) {
            const isMetatube = typeof source === 'string'
                && (source.startsWith('metatube:') || this._advancedSourceIsMetatube(source));
            if (!isMetatube) return;
            // 番號格式（如 SSIS-001）→ 不提示；非番號（女優/關鍵字）→ 提示
            const looksLikeNumber = /[A-Za-z]+-?\d+/.test(query);
            if (looksLikeNumber) return;
            this.showToast(window.t('settings.advanced_search.metatube_keyword_hint'), 'info');
        },

        _advancedSourceIsMetatube(id) {
            const src = (this._advancedConfig().sources || []).find(s => s && s.id === id);
            return !!src && src.type === 'metatube';
        },
    };
}
