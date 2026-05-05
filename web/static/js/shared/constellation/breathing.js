/**
 * breathing.js — BreathingManager
 * CD-56B-T2: 8 顆 visible slot 呼吸漂浮（sine.inOut yoyo）+ rail endpoint ticker 跟隨
 *
 * API:
 *   start(visibleSlots)  — 建立 tweens + 啟動 ticker
 *   stop()               — kill 所有 tweens + 移除 ticker
 *   pauseOne(slotId)     — 暫停單顆（hover enter）
 *   resumeOne(slotId)    — 恢復單顆（hover leave）
 *
 * 設計選型（plan §8 E/F）：
 *   - proxy object _yOffsets[id]（純數字），不直接 tween DOM top
 *   - ticker 每幀批次寫入 card top + line y2 setAttribute（降低 DOM mutation）
 *   - railEndpoint 在 start() 預算快取，ticker 只加 yOff
 */

import { railEndpoint } from './anchors.js';

const BREATH_AMPLITUDE = 6; // px，上下各 6px = 總行程 12px

export class BreathingManager {
  /**
   * @param {Object<string, HTMLElement>} cards       - slotId → DOM element
   * @param {Object<string, SVGLineElement>} railLines - slotId → SVG line element
   * @param {Array<{id: string, x: number, y: number}>} anchors - ANCHORS array
   */
  constructor(cards, railLines, anchors) {
    this._cards = cards;
    this._railLines = railLines;
    this._anchors = anchors;

    /** @type {Object<string, gsap.core.Tween>} */
    this._tweens = {};
    /** @type {Object<string, {value: number}>} */
    this._yOffsets = {};
    /** @type {Object<string, {x: number, y: number}>} */
    this._endpoints = {};
    /** @type {Function|null} */
    this._tickerFn = null;
  }

  /**
   * start — 為每個 visible slot 建立呼吸 tween + 啟動 ticker
   * defensive：先呼叫 stop() 清除舊狀態
   *
   * @param {Set<string>} visibleSlots - 8 個 visible slot id
   */
  start(visibleSlots) {
    this.stop(); // defensive：清除舊 tweens / ticker

    visibleSlots.forEach(id => {
      const anchor = this._anchors.find(a => a.id === id);
      if (!anchor) return;

      // Proxy object（純數字，tween 的目標）
      this._yOffsets[id] = { value: 0 };

      // 預算 rail endpoint（anchor 固定，快取之）
      this._endpoints[id] = railEndpoint(anchor);

      // 每張卡隨機 duration 製造相位差
      const dur = 2.8 + Math.random() * 0.8;

      this._tweens[id] = gsap.to(this._yOffsets[id], {
        value: BREATH_AMPLITUDE,
        duration: dur,
        ease: 'sine.inOut',
        yoyo: true,
        repeat: -1,
      });
    });

    // ticker callback：每幀批次寫入 card top + rail y2
    this._tickerFn = () => this._tickUpdate(visibleSlots);
    gsap.ticker.add(this._tickerFn);
  }

  /**
   * _tickUpdate — 每幀執行，批次更新 card top + line y2
   *
   * @param {Set<string>} visibleSlots
   */
  _tickUpdate(visibleSlots) {
    // double-guard：stop() 後 _tickerFn = null，但 ticker 可能在同幀還呼叫一次
    if (!this._tickerFn) return;

    visibleSlots.forEach(id => {
      if (!this._tweens[id]) return; // stop 後 _tweens 清空，skip

      const anchor = this._anchors.find(a => a.id === id);
      if (!anchor) return;

      const yOff = this._yOffsets[id].value;
      const card = this._cards[id];
      const line = this._railLines[id];
      const ep = this._endpoints[id];

      if (card) {
        gsap.set(card, { top: anchor.y + yOff });
      }
      if (line && ep) {
        line.setAttribute('y2', String(ep.y + yOff));
      }
    });
  }

  /**
   * pauseOne — 暫停單顆呼吸（hover enter）
   * tween.pause() 凍結 _yOffsets[id] 在當前值，card 靜止在漂浮中途位置
   *
   * @param {string} slotId
   */
  pauseOne(slotId) {
    if (this._tweens[slotId]) {
      this._tweens[slotId].pause();
    }
  }

  /**
   * resumeOne — 恢復單顆呼吸（hover leave）
   * tween.resume() 從凍結位置繼續，呼吸無縫銜接
   *
   * @param {string} slotId
   */
  resumeOne(slotId) {
    if (this._tweens[slotId]) {
      this._tweens[slotId].resume();
    }
  }

  /**
   * stop — kill 所有 tweens + 移除 ticker + 清空狀態
   * slip-through 前必須呼叫，確保 card top 不被 ticker 繼續漂移
   */
  stop() {
    // Kill all tweens
    Object.values(this._tweens).forEach(t => t.kill());

    // Remove ticker callback
    if (this._tickerFn) {
      gsap.ticker.remove(this._tickerFn);
      this._tickerFn = null;
    }

    // Clear state
    this._tweens = {};
    this._yOffsets = {};
    this._endpoints = {};
  }
}
