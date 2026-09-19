// 進階搜尋（search 入口）查不到時：留在 pick + inline error，不關窗。
//
// 以前是 await 之前就 closeRescrape()，查不到會直接掉到錯誤頁，要換下一個來源得重開彈窗。
// _rescrape_modal.html 其實早就備好 search 入口的 inline error（:108）與 footer
// 「搜尋中」spinner（:115-118），只是關窗太早從來沒走到。

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

globalThis.window = globalThis;
globalThis.window.t = (k) => k;

register(
  new URL('../../pages/search/__tests__/alias-loader.mjs', import.meta.url),
  import.meta.url,
);
const { rescrapeState } = await import('../state-rescrape.js');

function makeThis(advancedSearchResult, over = {}) {
  const calls = { closed: 0, searched: [], loadingSeen: [] };
  const self = {
    ...rescrapeState(),
    rescrapeEntryPoint: 'search',
    rescrapeNumber: 'ABC-001',
    rescrapeSources: [{ id: 'javdb', manual_only: false }],
    rescrapeLoadingSource: null,
    rescrapeCfWaiting: false,
    rescrapeNotFound: false,
    searchQuery: '',
    closeRescrape() { calls.closed++; },
    async advancedSearch(sourceId) {
      calls.searched.push(sourceId);
      calls.loadingSeen.push(self.rescrapeLoadingSource);   // 搜尋當下 spinner 是否已亮
      return advancedSearchResult;
    },
    ...over,
  };
  return { self, calls };
}

test('查不到 → 不關窗、rescrapeNotFound 轉真、spinner 收乾淨', async () => {
  const { self, calls } = makeThis(false);

  await rescrapeState().rescrapeWithSource.call(self, 'javdb');

  assert.equal(calls.closed, 0, '查不到不該關窗——關了就等於掉回錯誤頁');
  assert.equal(self.rescrapeNotFound, true);
  assert.equal(self.rescrapeLoadingSource, null, 'spinner 要收，否則其他來源 pill 全被 :disabled 鎖住');
  assert.deepEqual(calls.searched, ['javdb']);
});

test('搜尋進行中 rescrapeLoadingSource 已設（footer「搜尋中」與 pill spinner 靠它）', async () => {
  const { self, calls } = makeThis(true);
  await rescrapeState().rescrapeWithSource.call(self, 'javdb');
  assert.deepEqual(calls.loadingSeen, ['javdb']);
});

test('查到了 → 照舊關窗', async () => {
  const { self, calls } = makeThis(true);

  await rescrapeState().rescrapeWithSource.call(self, 'javdb');

  assert.equal(calls.closed, 1);
  assert.equal(self.rescrapeNotFound, false);
  assert.equal(self.rescrapeLoadingSource, null);
});

test('advancedSearch 拋例外也要收 spinner（否則彈窗卡死不能換來源）', async () => {
  const { self } = makeThis(false, {
    async advancedSearch() { throw new Error('boom'); },
  });

  await assert.rejects(() => rescrapeState().rescrapeWithSource.call(self, 'javdb'));
  assert.equal(self.rescrapeLoadingSource, null);
});

test('番號空白 → 直接 inline error，不發搜尋（既有行為不回歸）', async () => {
  const { self, calls } = makeThis(true, { rescrapeNumber: '   ' });

  await rescrapeState().rescrapeWithSource.call(self, 'javdb');

  assert.equal(self.rescrapeNotFound, true);
  assert.deepEqual(calls.searched, []);
  assert.equal(calls.closed, 0);
});
