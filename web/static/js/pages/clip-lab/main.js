/**
 * pages/clip-lab/main.js — Thin host：Alpine.data('constellationLab', ...)
 * CD-56B-8 thin host 規範：
 *   - 只做：import shared 模組、Alpine.data 宣告、init + click dispatch
 *   - 禁做：座標計算、rail 邏輯、timeline 建構
 * 雙抽防護：host onCardClick 算 nextVisible，再傳 animations；animations 不 import pickEight
 */

import { ANCHORS, pickEight } from '../../shared/constellation/anchors.js';
import { setRailCoords } from '../../shared/constellation/rails.js';
import { playInitialExpand, playSlipThrough, playExit } from '../../shared/constellation/animations.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('constellationLab', () => ({
    animating: false,
    visibleSlots: new Set(),
    mainSlot: null,
    cards: {},      // slotId -> HTMLElement
    railLines: {},  // slotId -> SVGLineElement

    init() {
      this._gsapCtx = window.OpenAver.motion.createContext(this.$el);

      // Build DOM refs（card / rail 用 id 對應，id 格式 card-01 / rail-01）
      ANCHORS.forEach(a => {
        const num = a.id.slice(1); // '#01' → '01'
        this.cards[a.id] = document.getElementById(`card-${num}`);
        this.railLines[a.id] = document.getElementById(`rail-${num}`);

        // 設定 rail 端點座標
        if (this.railLines[a.id]) {
          setRailCoords(this.railLines[a.id], a);
        }

        // 所有卡片初始放在中心（GSAP 計算用）
        if (this.cards[a.id]) {
          gsap.set(this.cards[a.id], { left: 480, top: 310 });
        }
      });

      // prefers-reduced-motion：直接呈現終態，跳過所有 timeline（CD-56B DoD 共通 5）
      if (window.OpenAver.prefersReducedMotion) {
        this._setInitialState();
        return;
      }

      const initSlots = new Set(['#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08']);
      this.animating = true;
      playInitialExpand(this.cards, this.railLines, initSlots, () => {
        this.visibleSlots = new Set(initSlots);
        this.animating = false;
      });
    },

    /**
     * _setInitialState — prefers-reduced-motion 終態：
     * gsap.set 直接到 anchor 位置，不建 timeline
     */
    _setInitialState() {
      const initSlots = new Set(['#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08']);
      initSlots.forEach(id => {
        const anchor = ANCHORS.find(a => a.id === id);
        const card = this.cards[id];
        const line = this.railLines[id];
        if (anchor && card) {
          card.classList.remove('slot--hidden');
          gsap.set(card, { left: anchor.x, top: anchor.y, opacity: 1 });
        }
        if (line) {
          line.classList.remove('rail--hidden');
          gsap.set(line, { opacity: 1 });
        }
      });
      this.visibleSlots = new Set(initSlots);
      this.animating = false;
    },

    /**
     * onCardClick — 點擊 slot 卡片觸發 slip-through
     * animating flag 防護：避免 timeline 未完成時重複觸發
     * 雙抽防護：host 先算 nextVisible，再傳 playSlipThrough（不讓 animations 重算）
     *
     * @param {string} slotId
     */
    onCardClick(slotId) {
      if (this.animating || !this.visibleSlots.has(slotId)) return;

      // host 算 nextVisible（防雙抽：animations.js 不 import pickEight）
      const nextVisible = pickEight(slotId, this.visibleSlots, Math.random);
      this.animating = true;

      playSlipThrough(
        slotId,
        this.visibleSlots,
        nextVisible,
        this.cards,
        this.railLines,
        document.getElementById('main-img'),
        () => {
          this.mainSlot = slotId;
          this.visibleSlots = nextVisible; // 與 animation 使用的批次完全一致
          this.animating = false;
        }
      );
    },

    /**
     * onExit — 點擊主圖 / 背景觸發退出動畫
     * 退出後刷新頁面（56b standalone 模式）
     */
    onExit() {
      if (this.animating) return;
      this.animating = true;
      playExit(
        this.cards,
        this.railLines,
        this.visibleSlots,
        document.getElementById('main-img'),
        () => {
          location.reload();
        }
      );
    },
  }));
});
