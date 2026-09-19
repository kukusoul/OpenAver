// file 模式卡片「使用番號進階搜尋」採用後：結果寫回當前檔，listMode 不切走。

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { searchStateAdvancedPicker } from '../state/advanced-picker.js';
import { searchStateSearchFlow } from '../state/search-flow.js';

globalThis.window = globalThis;
globalThis.window.t = (k) => k;

const PAYLOAD = { data: [{ number: 'ABC-999', title: 'T' }], mode: 'exact', has_more: false };

function state(over = {}) {
    return {
        ...searchStateAdvancedPicker(),
        listMode: 'file',
        currentFileIndex: 0,
        currentQuery: 'ABC-999',
        fileList: [{ number: 'ABC-999', searched: true, searchResults: [] }],
        checkLocalStatus() {},
        preloadImages() {},
        _resetCoverState() {},
        ...over,
    };
}

test('寫回當前檔 + 留在 file 模式（切成 search 會讓整份檔案清單消失且回不去）', () => {
    const s = state();
    s._commitSearchResults(PAYLOAD);

    assert.equal(s.listMode, 'file');
    assert.deepEqual(s.fileList[0].searchResults, PAYLOAD.data, '檔案列的 ✗ 與「產生 NFO」讀的是這個欄位');
    assert.equal(s.fileList[0].searched, true);
    assert.deepEqual(s.searchResults, PAYLOAD.data, '共享結果列仍要更新，卡片才會換掉');
});

test('race：結果回來時使用者已切到別的檔（番號不符）→ 不寫進錯的檔，落回 search', () => {
    const s = state({ fileList: [{ number: 'OTHER-1', searched: true, searchResults: [] }] });
    s._commitSearchResults(PAYLOAD);

    assert.equal(s.listMode, 'search');
    assert.deepEqual(s.fileList[0].searchResults, []);
});

test('非 file 模式（頂部膠囊／錯誤頁入口）→ 維持原本 listMode=search 行為', () => {
    const s = state({ listMode: 'search', fileList: [] });
    s._commitSearchResults(PAYLOAD);
    assert.equal(s.listMode, 'search');
});

// ===== 查不到時背景不被換掉（彈窗留在 pick 顯示 inline error，背景維持原樣）=====

function failingFetchState(over = {}) {
    return {
        // 真的 cancelSearch，不是 stub：它在沒有 _searchSnapshot 時會把 pageState 設成
        // 'empty'（首頁），而 file 模式永遠沒有 snapshot。stub 掉就等於把唯一會壞的東西
        // 繞過去——這支測試第一版正是這樣漏掉「查不到跳回首頁」的。
        ...searchStateSearchFlow(),
        ...searchStateAdvancedPicker(),
        searchQuery: 'ABC-999',
        listMode: 'file',
        currentFileIndex: 0,
        fileList: [{ number: 'ABC-999', searched: true, searchResults: [] }],
        pageState: 'result',                 // file 模式查無結果的卡片（coverError 撐著）
        coverError: '找不到 ABC-999 的資料',
        currentQuery: 'ABC-999',
        errorText: '',
        errorKind: '',
        requestId: 0,
        _searchSnapshot: null,               // file 模式的實況：沒有快照 → cancelSearch 會設 'empty'
        activeEventSource: null,
        _fallbackAbortController: null,
        streamBurstTimer: null,
        _coverSwapTimer: null,
        showToast() {},
        checkLocalStatus() {},
        preloadImages() {},
        _resetCoverState() {},
        _clearTimer() {},
        ...over,
    };
}

test('查不到 → pageState 原樣還原，不換成錯誤頁（卡片與卡上的換來源入口都留著）', async () => {
    const s = failingFetchState();
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ success: false, data: [] }) });

    const ok = await s.advancedSearch('javdb');

    assert.equal(ok, false, '回傳 false 讓彈窗留在 pick');
    assert.equal(s.pageState, 'result', '背景被換成 error 的話，取消彈窗後那張卡片就不見了');
    assert.equal(s.coverError, '找不到 ABC-999 的資料');
    assert.equal(s.errorText, '');
});

test('fetch 拋例外 → 同樣還原，不留半套 loading', async () => {
    const s = failingFetchState();
    globalThis.fetch = async () => { throw new Error('network down'); };

    const ok = await s.advancedSearch('javdb');

    assert.equal(ok, false);
    assert.equal(s.pageState, 'result');
    assert.equal(s.errorKind, '');
});

test('查到了 → 照常進結果（還原邏輯不擋成功路徑）', async () => {
    const s = failingFetchState();
    globalThis.fetch = async () => ({ ok: true, json: async () => ({ success: true, data: PAYLOAD.data, mode: 'exact' }) });

    const ok = await s.advancedSearch('javdb');

    assert.equal(ok, true);
    assert.equal(s.pageState, 'result');
    assert.deepEqual(s.fileList[0].searchResults, PAYLOAD.data, '成功時仍寫回當前檔');
    assert.equal(s.listMode, 'file');
});
