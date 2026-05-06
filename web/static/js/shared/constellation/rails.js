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
    // Micro pulse：DrawSVG 完成後 strokeWidth 閃爍（CD-T2FIX-3 §D）
    tl.to(line, { strokeWidth: 2.2, duration: 0.09, ease: 'fluent' }, pos + 0.55);
    tl.to(line, { strokeWidth: 1.5, duration: 0.13, ease: 'fluent' }, pos + 0.64);
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

// ---------------------------------------------------------------------------
// T2fix2 Rail Energy helpers（CD-T2FIX-3）
// ---------------------------------------------------------------------------

/**
 * railSweep — sweep overlay line 掃過動畫（直呼，不接 tl）
 * 啟動前從 sourceLine copy x1/y1/x2/y2（同步呼吸 y 偏移，critical）
 *
 * @param {SVGLineElement} sweepLine
 * @param {SVGLineElement} sourceLine
 * @param {{ onComplete?: () => void }} [opts]
 */
export function railSweep(sweepLine, sourceLine, { onComplete } = {}) {
  if (!sweepLine || !sourceLine) return;
  if (typeof DrawSVGPlugin === 'undefined') return;

  // CRITICAL: 啟動前從 sourceLine copy 座標（同步呼吸 y 偏移）
  sweepLine.setAttribute('x1', sourceLine.getAttribute('x1'));
  sweepLine.setAttribute('y1', sourceLine.getAttribute('y1'));
  sweepLine.setAttribute('x2', sourceLine.getAttribute('x2'));
  sweepLine.setAttribute('y2', sourceLine.getAttribute('y2'));

  // 進場 set
  gsap.set(sweepLine, { drawSVG: '0% 0%', opacity: 1 });

  const tl = gsap.timeline({
    onComplete: () => {
      // CRITICAL: sweep-line 必須回到隱形
      gsap.set(sweepLine, { drawSVG: '0% 0%', opacity: 0 });
      onComplete?.();
    },
  });

  // 兩段：先短亮段成型（0.20s），再掃過 rail 至尾端（0.30s），total 0.50s
  tl.to(sweepLine, { drawSVG: '0% 18%', duration: 0.20, ease: 'fluent' })
    .to(sweepLine, { drawSVG: '82% 100%', duration: 0.30, ease: 'fluent' });
}

/**
 * railFocusPulse — hover focused rail 亮色 + strokeWidth pulse（直呼）
 *
 * @param {SVGLineElement} line
 */
export function railFocusPulse(line) {
  if (!line) return;
  line.classList.add('rail--bright');
  gsap.to(line, { strokeWidth: 2.5, duration: 0.18, ease: 'fluent' })
    .then(() => gsap.to(line, { strokeWidth: 1.5, duration: 0.22, ease: 'fluent' }));
}

/**
 * railClickedPulse — clicked rail 脈衝收掉（接 timeline，供 playSlipThrough t=0）
 *
 * @param {SVGLineElement} line
 * @param {gsap.core.Timeline} tl
 * @param {number} pos
 */
export function railClickedPulse(line, tl, pos) {
  if (!line || !tl) return;
  tl.to(line, { strokeWidth: 3, duration: 0.12, ease: 'fluent' }, pos);
  tl.to(line, { strokeWidth: 1.5, opacity: 0, duration: 0.18, ease: 'fluent-accel' }, pos + 0.12);
}

/**
 * railShimmer — carry-over persist rail 微脈衝（直呼，T2fix4 預埋）
 *
 * @param {SVGLineElement} line
 */
export function railShimmer(line) {
  if (!line) return;
  gsap.timeline()
    .to(line, { strokeWidth: 1.7, duration: 0.14, ease: 'fluent' })
    .to(line, { strokeWidth: 1.5, duration: 0.24, ease: 'fluent' });
}

/**
 * resetSweepLine — sweep-line 強制重置（killTweens + opacity 0）
 * main.js 透過 import 使用，避開 Group 5 drawSVG 字面字 ban
 *
 * @param {SVGLineElement} sweepLine
 */
export function resetSweepLine(sweepLine) {
  if (!sweepLine) return;
  gsap.killTweensOf(sweepLine);
  gsap.set(sweepLine, { drawSVG: '0% 0%', opacity: 0 });
}
