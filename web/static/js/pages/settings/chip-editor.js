// 命名區膠囊編輯器（feature/95 Part A）。
//
// 本檔分兩層（CLAUDE.md lint 守衛規則：演算法正確性走 node:test、結構防 fork 走 ESLint）：
//   1. 純函式 tokenize / serializeTokens —— 無 DOM，可被 node:test import（本 T3）。
//   2. ChipEditor class —— contentEditable 非受控 widget（T4 append）。
//
// ⚠ module top-level 不得碰 `document`/`window`（否則 node --test import 會炸）；
//   DOM 只在 class 方法內觸碰。tokenize/serializeTokens 皆為純函式。

'use strict';

/**
 * 全函數 tokenizer（D-A3 / CD-95a-4）：任何字串 → token model 陣列，永不拋錯。
 *
 * 候選 regex `\{[a-zA-Z]+\}`；只有**精確匹配** whitelist 的 `{name}` 轉膠囊（chip），
 * 其餘一律字面（text）——未知 token（`{studio}`）、缺括號（`{title`）、字面大括號
 * （`{`、`}`、`{123}`）都保留原樣。whitelist 由呼叫端注入（CD-95a-10〔2〕：不硬編 token）。
 *
 * @param {string} str
 * @param {Set<string>} whitelist  形如 `new Set(['{num}', '{title}', ...])`（含大括號）
 * @returns {Array<{t:'chip'|'text', v:string}>}
 */
export function tokenize(str, whitelist) {
  const out = [];
  // 每次呼叫新建 regex，避免共享 lastIndex 造成有狀態 bug
  const re = /\{[a-zA-Z]+\}/g;
  let last = 0;
  let m;
  while ((m = re.exec(str)) !== null) {
    if (m.index > last) out.push({ t: 'text', v: str.slice(last, m.index) });
    if (whitelist.has(m[0])) out.push({ t: 'chip', v: m[0] });
    else out.push({ t: 'text', v: m[0] });  // 未知 token 保留字面
    last = re.lastIndex;
  }
  if (last < str.length) out.push({ t: 'text', v: str.slice(last) });
  return out;
}

/**
 * 純 serializer（CD-95a-13，**單一序列化真理**）：token model → 字串。
 *
 * chip 的 `v` 即完整 `{token}` 字串、text 的 `v` 即字面，故兩者皆取 `v` 串接即還原原字串。
 * ChipEditor 的 DOM serialize 必須 delegate 到此函式（DOM → token model → serializeTokens），
 * 產出與本純函式逐字元相同，避免兩條 serialize 路徑漂移。
 *
 * @param {Array<{t:'chip'|'text', v:string}>} tokens
 * @returns {string}
 */
export function serializeTokens(tokens) {
  let out = '';
  for (const tk of tokens) out += tk.v;
  return out;
}
