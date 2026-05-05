/**
 * rails.js — Rail 三態邏輯 + SVG line 操作 helpers
 * CD-56B-3: railRole + setRailCoords + railDrawIn / railDrawOut
 *
 * ESM export — 不走 window 全域
 */

import { ANCHORS, railEndpoint } from './anchors.js';

/**
 * railRole — 判斷 rail 三態（純函數，無副作用）
 * CD-56B-3 契約
 *
 * @param {string} slotId
 * @param {Set<string>} prevVisible
 * @param {Set<string>} nextVisible
 * @returns {'persist' | 'enter' | 'exit' | 'absent'}
 */
export function railRole(slotId, prevVisible, nextVisible) {
  const inPrev = prevVisible.has(slotId);
  const inNext = nextVisible.has(slotId);

  if (inPrev && inNext)  return 'persist'; // rail 完全不動，不加入任何 tween
  if (!inPrev && inNext) return 'enter';   // DrawSVG 0% → 100%
  if (inPrev && !inNext) return 'exit';    // opacity 1 → 0
  return 'absent';                          // 維持 .rail--hidden
}

/**
 * setRailCoords — 設定 SVG line 的 x1/y1（中心）和 x2/y2（endpoint）
 * endpoint 使用 railEndpoint 公式（center + (anchor - center) × 1.4）
 *
 * @param {SVGLineElement} line
 * @param {{ id: string, x: number, y: number }} anchor - ANCHORS 中的元素
 */
export function setRailCoords(line, anchor) {
  if (!line || !anchor) return;
  const ep = railEndpoint(anchor);
  // 中心為起點，anchor endpoint 為終點
  line.setAttribute('x1', 480);
  line.setAttribute('y1', 310);
  line.setAttribute('x2', ep.x);
  line.setAttribute('y2', ep.y);
}

/**
 * railDrawIn — DrawSVG 0% → 100% enter 動畫
 * CD-56B-3 DrawSVG enter 寫法：先 tl.call 初始化，再 tl.to draw-in
 *
 * DrawSVGPlugin fallback：若 typeof DrawSVGPlugin === 'undefined'，退回 opacity 0→1
 *
 * @param {SVGLineElement} line
 * @param {gsap.core.Timeline} tl
 * @param {number} pos - timeline 位置（秒）
 */
export function railDrawIn(line, tl, pos) {
  if (!line || !tl) return;

  if (typeof DrawSVGPlugin !== 'undefined') {
    // DrawSVGPlugin 可用：draw-in 動畫
    tl.call(() => {
      line.classList.remove('rail--hidden');
      gsap.set(line, { drawSVG: '0%', opacity: 1 });
    }, null, Math.max(0, pos - 0.01));
    tl.to(line, { drawSVG: '0% 100%', duration: 0.55, ease: 'fluent-decel' }, pos);
  } else {
    // Fallback：opacity 0 → 1（無「畫出」感，但不炸）
    tl.call(() => {
      line.classList.remove('rail--hidden');
      gsap.set(line, { opacity: 0 });
    }, null, Math.max(0, pos - 0.01));
    tl.to(line, { opacity: 1, duration: 0.55, ease: 'fluent-decel' }, pos);
  }
}

/**
 * railDrawOut — opacity 1 → 0 exit 動畫
 * CD-56B-3 exit 寫法
 *
 * @param {SVGLineElement} line
 * @param {gsap.core.Timeline} tl
 * @param {number} pos - timeline 位置（秒）
 */
export function railDrawOut(line, tl, pos) {
  if (!line || !tl) return;
  tl.to(line, { opacity: 0, duration: 0.35, ease: 'fluent-accel' }, pos);
}
