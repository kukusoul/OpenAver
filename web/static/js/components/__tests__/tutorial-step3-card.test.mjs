// TASK-146a-T1: buildStep3MockCard — i18n keys / 13·11 / disabled / ds-gallery-composition

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildStep3MockCard } from '../tutorial-step3-card.js';

const EXPECTED_KEYS = new Set([
    'scanner.stats.missing_nfo_prefix',
    'scanner.stats.missing_cover_prefix',
    'scanner.stats.missing_suffix',
    'scanner.stats.missing_enrich_idle',
]);

function makeSpy() {
    const keys = [];
    const t = (key) => {
        keys.push(key);
        return `[${key}]`;
    };
    return { t, keys };
}

test('按鈕文字呼叫 scanner.stats.missing_enrich_idle（與真卡同一份 i18n key）', () => {
    const { t, keys } = makeSpy();
    buildStep3MockCard(t);
    assert.deepEqual(new Set(keys), EXPECTED_KEYS);
    assert.ok(keys.includes('scanner.stats.missing_enrich_idle'));
});

test('輸出 HTML 含固定數字 13 與 11', () => {
    const { t } = makeSpy();
    const html = buildStep3MockCard(t);
    assert.match(html, /13/);
    assert.match(html, /11/);
});

test('輸出含 disabled 與 tabindex="-1"', () => {
    const { t } = makeSpy();
    const html = buildStep3MockCard(t);
    assert.match(html, /\bdisabled\b/);
    assert.match(html, /tabindex="-1"/);
});

test('外層 div 帶 ds-gallery-composition class（CD-146a-3 事實訂正的作用域修法）', () => {
    const { t } = makeSpy();
    const html = buildStep3MockCard(t);
    assert.match(html, /class="[^"]*\bds-gallery-composition\b[^"]*"/);
});
