// TASK-146a-T4：空狀態四行說明 method 分支 ＋ loadAppConfig() 失敗隔離 oracle（CD-146a-17）
//
// 覆蓋：
//   - favoriteConfigured()：appConfig null／favorite_folder 空字串／只有空白／有值
//   - favoritePathDisplay()：window.pathToDisplay 存在與不存在
//   - namingPreviewExample()：createFolder 開/關、formatVariables 空/非空
//   - CD-146a-17 失敗隔離：format-variables reject／favorite-scanner-link reject／
//     favorite_folder 空時不呼叫 favorite-scanner-link

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';

globalThis.window = globalThis;
globalThis.document = { addEventListener() {} };

if (typeof globalThis.requestAnimationFrame !== 'function') {
    globalThis.requestAnimationFrame = (fn) => setTimeout(fn, 0);
}

// state/__tests__ → 上一層 __tests__/alias-loader.mjs
register(new URL('../../__tests__/alias-loader.mjs', import.meta.url), import.meta.url);

const { searchStateEmptyExplainer } = await import('../empty-explainer.js');
const { searchStateSearchFlow } = await import('../search-flow.js');

function jsonResponse(data, { ok = true, status = 200 } = {}) {
    return {
        ok,
        status,
        json: async () => data,
    };
}

function mockFetch(handler) {
    const calls = [];
    globalThis.fetch = async (url, opts = {}) => {
        const u = String(url);
        calls.push(u);
        return handler(u, opts, calls);
    };
    return calls;
}

function makeExplainerThis(overrides = {}) {
    return {
        appConfig: null,
        formatVariables: [],
        favoriteScannerLinked: null,
        ...searchStateEmptyExplainer(),
        ...overrides,
    };
}

// ─── favoriteConfigured() ─────────────────────────────────────────────────

test('favoriteConfigured: appConfig 為 null → false', () => {
    const state = makeExplainerThis({ appConfig: null });
    assert.equal(state.favoriteConfigured.call(state), false);
});

test('favoriteConfigured: favorite_folder 為空字串 → false', () => {
    const state = makeExplainerThis({
        appConfig: { search: { favorite_folder: '' } },
    });
    assert.equal(state.favoriteConfigured.call(state), false);
});

test('favoriteConfigured: favorite_folder 只有空白 → false', () => {
    const state = makeExplainerThis({
        appConfig: { search: { favorite_folder: '   ' } },
    });
    assert.equal(state.favoriteConfigured.call(state), false);
});

test('favoriteConfigured: favorite_folder 有值 → true', () => {
    const state = makeExplainerThis({
        appConfig: { search: { favorite_folder: '/data/downloads' } },
    });
    assert.equal(state.favoriteConfigured.call(state), true);
});

// ─── favoritePathDisplay() ────────────────────────────────────────────────

test('favoritePathDisplay: window.pathToDisplay 存在時走轉換', () => {
    const prev = window.pathToDisplay;
    window.pathToDisplay = (p) => `DISPLAY(${p})`;
    try {
        const state = makeExplainerThis({
            appConfig: { search: { favorite_folder: '/data/downloads' } },
        });
        assert.equal(state.favoritePathDisplay.call(state), 'DISPLAY(/data/downloads)');
    } finally {
        if (prev === undefined) delete window.pathToDisplay;
        else window.pathToDisplay = prev;
    }
});

test('favoritePathDisplay: window.pathToDisplay 不存在時回原字串', () => {
    const prev = window.pathToDisplay;
    delete window.pathToDisplay;
    try {
        const state = makeExplainerThis({
            appConfig: { search: { favorite_folder: '/data/downloads' } },
        });
        assert.equal(state.favoritePathDisplay.call(state), '/data/downloads');
    } finally {
        if (prev !== undefined) window.pathToDisplay = prev;
    }
});

// ─── namingPreviewExample() ───────────────────────────────────────────────

test('namingPreviewExample: createFolder 關、formatVariables 空 → 檔名＋.mp4（token 殘留）', () => {
    const prev = window.t;
    window.t = (key) => key;
    try {
        const state = makeExplainerThis({
            appConfig: {
                scraper: {
                    filename_format: '{num} {title}',
                    create_folder: false,
                    folder_layers: ['{actor}', '{num}'],
                },
            },
            formatVariables: [],
        });
        assert.equal(state.namingPreviewExample.call(state), '{num} {title}.mp4');
    } finally {
        if (prev === undefined) delete window.t;
        else window.t = prev;
    }
});

test('namingPreviewExample: createFolder 開、formatVariables 非空 → 含資料夾層＋token 替換', () => {
    const prev = window.t;
    window.t = (key) => {
        const map = {
            'settings.var.num': '番號',
            'settings.var.title': '標題',
            'settings.var.actor': '女優',
        };
        return map[key] || key;
    };
    try {
        const state = makeExplainerThis({
            appConfig: {
                scraper: {
                    filename_format: '{num} {title}',
                    create_folder: true,
                    folder_layers: ['{actor}', '{num}'],
                },
            },
            formatVariables: [
                { name: '{num}', folder_ok: true },
                { name: '{title}', folder_ok: true },
                { name: '{actor}', folder_ok: true },
            ],
        });
        assert.equal(state.namingPreviewExample.call(state), '女優/番號/番號 標題.mp4');
    } finally {
        if (prev === undefined) delete window.t;
        else window.t = prev;
    }
});

// ─── CD-146a-17 失敗隔離 oracle ───────────────────────────────────────────

test('loadAppConfig: format-variables reject → appConfig 仍設定、formatVariables 維持 []、不 reject', async () => {
    const calls = mockFetch((url) => {
        if (url === '/api/config') {
            return jsonResponse({
                success: true,
                data: { search: { favorite_folder: '/fav' }, scraper: {} },
            });
        }
        if (url === '/api/config/format-variables') {
            return Promise.reject(new Error('format-variables down'));
        }
        if (url.startsWith('/api/settings/favorite-scanner-link')) {
            return jsonResponse({ linked: true, matched_directory: '/fav' });
        }
        throw new Error('unexpected url: ' + url);
    });

    const state = {
        appConfig: null,
        formatVariables: [],
        favoriteScannerLinked: null,
        ...searchStateSearchFlow(),
    };

    await assert.doesNotReject(() => state.loadAppConfig.call(state));
    assert.ok(
        state.appConfig,
        'loadAppConfig() 在 format-variables 失敗時仍須設定 appConfig',
    );
    assert.equal(state.appConfig.search.favorite_folder, '/fav');
    assert.deepEqual(state.formatVariables, []);
    assert.ok(calls.some((u) => u === '/api/config'));
    assert.ok(calls.some((u) => u === '/api/config/format-variables'));
});

test('loadAppConfig: favorite-scanner-link reject → appConfig 與 formatVariables 正常、favoriteScannerLinked 維持 null', async () => {
    mockFetch((url) => {
        if (url === '/api/config') {
            return jsonResponse({
                success: true,
                data: { search: { favorite_folder: '/fav' }, scraper: {} },
            });
        }
        if (url === '/api/config/format-variables') {
            return jsonResponse({
                variables: [{ name: '{num}', folder_ok: true }],
            });
        }
        if (url.startsWith('/api/settings/favorite-scanner-link')) {
            return Promise.reject(new Error('favorite-scanner-link down'));
        }
        throw new Error('unexpected url: ' + url);
    });

    const state = {
        appConfig: null,
        formatVariables: [],
        favoriteScannerLinked: null,
        ...searchStateSearchFlow(),
    };

    await assert.doesNotReject(() => state.loadAppConfig.call(state));
    assert.ok(state.appConfig, 'appConfig 必須仍被設定');
    assert.equal(state.formatVariables.length, 1);
    assert.equal(state.formatVariables[0].name, '{num}');
    assert.equal(state.favoriteScannerLinked, null);
});

test('loadAppConfig: favorite_folder 為空 → favorite-scanner-link 完全不被呼叫', async () => {
    const calls = mockFetch((url) => {
        if (url === '/api/config') {
            return jsonResponse({
                success: true,
                data: { search: { favorite_folder: '' }, scraper: {} },
            });
        }
        if (url === '/api/config/format-variables') {
            return jsonResponse({ variables: [] });
        }
        throw new Error('unexpected url: ' + url);
    });

    const state = {
        appConfig: null,
        formatVariables: [],
        favoriteScannerLinked: null,
        ...searchStateSearchFlow(),
    };

    await assert.doesNotReject(() => state.loadAppConfig.call(state));
    assert.ok(state.appConfig);
    assert.equal(
        calls.some((u) => u.includes('/api/settings/favorite-scanner-link')),
        false,
        'favorite_folder 空時不得呼叫 favorite-scanner-link；實際呼叫：' + JSON.stringify(calls),
    );
});
