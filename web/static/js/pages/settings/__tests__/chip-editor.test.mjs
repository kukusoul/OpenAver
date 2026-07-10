// tokenizer round-trip 守衛（CD-95a-10〔1〕，plan-95a T3）。
// 零新依賴：Node 內建 node:test。跑：npm run test:tokenizer
//
// 守 serializeTokens(tokenize(s)) 的 round-trip 性質、未知 token 留字面、
// 字面大括號不誤判、idempotence——tokenizer 演算法正確性（ESLint 表達不了）。

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tokenize, serializeTokens } from '../chip-editor.js';

// 與端點 SSOT 對齊的白名單（測試自帶，驗 tokenize 對注入 whitelist 的行為）
const WL = new Set([
  '{num}', '{title}', '{actor}', '{actors}', '{maker}',
  '{date}', '{year}', '{month}', '{day}', '{suffix}',
]);

const roundtrip = (s) => serializeTokens(tokenize(s, WL));

test('〔a〕白名單串 round-trip：serializeTokens(tokenize(s))===s', () => {
  const cases = [
    '[{num}][{maker}] {title}{suffix}',   // 預設檔名格式
    '{actor}/{num}',                       // 資料夾兩層
    '{num} - {title} ({year})',            // 含空格/-/()
    '~{maker}~ "{title}" \'{actor}\'',     // 含 ~ 與引號字面
    '{num}{title}{actor}{actors}{maker}{date}{year}{month}{day}{suffix}',  // 全變數相連
  ];
  for (const s of cases) assert.equal(roundtrip(s), s, `round-trip 破壞：${s}`);
});

test('〔b〕未知 token 留字面（不轉膠囊、round-trip 不變）', () => {
  const cases = ['{studio}', '{tit-le}', '{titel}', '{title', '{}', '{123}', '{NUM}'];
  for (const s of cases) {
    assert.equal(roundtrip(s), s, `未知 token 應留字面：${s}`);
    // 且不得產生 chip
    assert.ok(
      tokenize(s, WL).every((tk) => tk.t === 'text'),
      `未知 token 不應成 chip：${s}`,
    );
  }
});

test('〔b2〕已知 token 確實成 chip', () => {
  const toks = tokenize('{num}', WL);
  assert.deepEqual(toks, [{ t: 'chip', v: '{num}' }]);
});

test('〔c〕字面大括號不誤判', () => {
  const cases = ['{', '}', 'a{b}c', '{ num }', 'plain text', '前綴{num後綴'];
  for (const s of cases) assert.equal(roundtrip(s), s, `字面大括號誤判：${s}`);
  // {b} 非白名單 → 全字面
  assert.ok(tokenize('a{b}c', WL).every((tk) => tk.t === 'text'));
});

test('〔d〕idempotence：serialize→tokenize 穩定', () => {
  const cases = ['[{num}] {title}{suffix}', '{studio}{num}', 'a{b}c{actor}'];
  for (const s of cases) {
    const once = tokenize(s, WL);
    const twice = tokenize(serializeTokens(once), WL);
    assert.deepEqual(twice, once, `idempotence 破壞：${s}`);
  }
});

test('〔e〕空字串 → [] → 空字串', () => {
  assert.deepEqual(tokenize('', WL), []);
  assert.equal(serializeTokens([]), '');
  assert.equal(roundtrip(''), '');
});

test('〔f〕{actor} 與 {actors} 各自正確成 chip（無子字串誤併）', () => {
  assert.deepEqual(tokenize('{actor}', WL), [{ t: 'chip', v: '{actor}' }]);
  assert.deepEqual(tokenize('{actors}', WL), [{ t: 'chip', v: '{actors}' }]);
  // 相鄰：{actor} 後接 s} 字面
  assert.equal(roundtrip('{actor}s and {actors}'), '{actor}s and {actors}');
});
