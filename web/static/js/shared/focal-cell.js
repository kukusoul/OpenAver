/**
 * focal-cell.js — applyCellFocal：imperative、load-gated 小格 object-position 套用（99a-T2）。
 *
 * focal.js 是純函式模組（docstring 明文承諾無 DOM/無副作用，比照 dir-path.js）；applyCellFocal
 * 要讀 el.naturalWidth/naturalHeight + getComputedStyle + 掛 load listener + 寫 el.style，是
 * impure DOM 副作用 util，故獨立成檔（比照 dom-timing.js 與 dir-path.js 的分離慣例，見
 * TASK-99a-T2 §0）。import path 走目錄級 `@/shared/`（base.html importmap），新增此檔不需改 importmap。
 *
 * load-gate（Codex P1-3）：naturalWidth 在 `.src=` 賦值後、圖片真正 decode 完成前恆為 0，且
 * load 事件不是 Alpine reactive 依賴、不會讓 `:style` binding 重跑（98b-T6 姊妹案例，見 card §4）。
 * 故一律 `el.complete && el.naturalWidth` 才同步算，否則掛 `load` listener 延後算。
 *
 * expected-src guard（Codex P1-3 延伸）：`.similar-slot-img` 等可重用 DOM 元素會被連續 `.src=`
 * 賦新值多次；若 A 的 load listener 因排程延遲在 B 的 src 已賦值後才 fire，需放棄（不可用 A 的
 * aspect 算出的 object-position 覆寫已顯示 B 封面的 img）。
 */

import { focalCellObjectPosition } from './focal.js';

function computeAndApply(el, video) {
  const a = el.naturalWidth / el.naturalHeight;
  const r = parseFloat(getComputedStyle(el).getPropertyValue('--poster-crop-ratio'));
  if (!Number.isFinite(r) || r <= 0) {
    el.style.objectPosition = '';
    return;
  }
  const result = focalCellObjectPosition(video, a, r);
  el.style.objectPosition = result || ''; // null → 清 inline，退 CSS baseline，不殘留舊值（換片 A→B 契約）
}

/**
 * @param {HTMLImageElement|null} el 小格 <img>（grid / similar slot / mobile drill 三站共用）
 * @param {{crop_mode: string, auto_focal: string}|null|undefined} video
 */
export function applyCellFocal(el, video) {
  if (!el) return;
  if (el.complete && el.naturalWidth) {
    computeAndApply(el, video);
    return;
  }
  // 未載入（或 broken image：complete=true 但 naturalWidth=0）→ 掛 load listener 延後算。
  const expectedSrc = el.src;
  el.addEventListener(
    'load',
    () => {
      // 換過圖了（同一元素被重用、.src= 換成新值）→ 放棄，不覆寫新圖的 objectPosition。
      if (el.currentSrc !== expectedSrc && el.src !== expectedSrc) return;
      computeAndApply(el, video);
    },
    { once: true },
  );
}
