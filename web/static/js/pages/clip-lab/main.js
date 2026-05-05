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
import { BreathingManager } from '../../shared/constellation/breathing.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('constellationLab', () => ({
    animating: false,
    visibleSlots: new Set(),
    mainSlot: null,
    cards: {},      // slotId -> HTMLElement
    railLines: {},  // slotId -> SVGLineElement
    breathingManager: null,

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

      // 建立 BreathingManager（即使 prefers-reduced-motion 也建立，避免 hover 觸發 null 錯誤）
      this.breathingManager = new BreathingManager(this.cards, this.railLines, ANCHORS);

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
        this.breathingManager.start(initSlots);
      });
    },

    /**
     * _setInitialState — prefers-reduced-motion 終態：
     * gsap.set 直接到 anchor 位置，不建 timeline
     * 注意：不啟動 breathing（保持「無動畫」契約）
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
      // 不呼叫 breathingManager.start()（prefers-reduced-motion：無動畫契約）
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

      // CRITICAL: 在呼叫任何 animation / pickEight 之前，先捕獲 prevVisible（CD-T2FIX-4 §E）
      const prevVisible = new Set(this.visibleSlots);

      // host 算 nextVisible（防雙抽：animations.js 不 import pickEight）
      const nextVisible = pickEight(slotId, prevVisible, Math.random);

      // Reduced-motion 短路（CD-T2FIX-11）：sync state update，不播任何動畫
      if (window.OpenAver.prefersReducedMotion) {
        // 隱藏舊批
        prevVisible.forEach(id => {
          const card = this.cards[id];
          if (card) {
            card.classList.add('slot--hidden');
            gsap.set(card, { opacity: 0 });
          }
        });
        // 顯示新批，定位至 anchor
        nextVisible.forEach(id => {
          const anchor = ANCHORS.find(a => a.id === id);
          const card = this.cards[id];
          if (anchor && card) {
            card.classList.remove('slot--hidden');
            gsap.set(card, { left: anchor.x, top: anchor.y, opacity: 1, width: 120, height: 150 });
          }
        });
        // Rails: nextVisible 顯示，其餘隱藏（DrawSVG 禁用，使用 classList + opacity）
        ANCHORS.forEach(a => {
          const line = this.railLines[a.id];
          if (!line) return;
          if (nextVisible.has(a.id)) {
            line.classList.remove('rail--hidden');
            gsap.set(line, { opacity: 1, strokeWidth: 1.5 });
          } else {
            line.classList.add('rail--hidden');
            gsap.set(line, { opacity: 0 });
          }
        });
        // Main label
        const labelEl = document.getElementById('main-id-label');
        if (labelEl) labelEl.textContent = slotId;
        this.mainSlot = slotId;
        this.visibleSlots = nextVisible;
        // this.animating 維持 false（short-circuit 不設 true）
        return;
      }

      this.animating = true;

      // 同步清 hover 殘留 tween + 視覺 state（CD-56B-T2 codex P1）
      // 避免 mouseleave 在 slip-through 期間觸發 restore tween 與 exit/fade 打架
      this.visibleSlots.forEach(id => {
        const card = this.cards[id];
        if (!card) return;
        gsap.killTweensOf(card, 'scale,opacity');
        if (id !== slotId) gsap.set(card, { opacity: 1 });
        // clearProps: 'scale' 確保所有 card（含 clicked）從 scale=1.0 起跳（CD-T2FIX-2）
        gsap.set(card, { clearProps: 'scale' });
        const overlay = card.querySelector('.slot-icon-overlay');
        if (overlay) overlay.classList.remove('slot-icon--visible');
      });

      // 停止呼吸（slip-through 期間 ticker 不殘留）
      this.breathingManager.stop();

      playSlipThrough(
        slotId,
        prevVisible,
        nextVisible,
        this.cards,
        this.railLines,
        document.getElementById('main-img'),
        () => {
          this.mainSlot = slotId;
          this.visibleSlots = nextVisible; // 與 animation 使用的批次完全一致
          this.animating = false;
          // slip-through 完成後重啟呼吸（新批 8 顆各自相位）
          if (!window.OpenAver.prefersReducedMotion) {
            this.breathingManager.start(nextVisible);
          }
        }
      );
    },

    /**
     * onHoverEnter — 滑入 slot 卡片
     * 1. 暫停此顆呼吸
     * 2. scale 1.06 微放大
     * 3. 其餘 visible slots dim 0.5
     * 4. icon overlay 浮現（classList 操作，CSS transition 處理 opacity）
     *
     * @param {string} slotId
     */
    onHoverEnter(slotId) {
      if (this.animating || !this.visibleSlots.has(slotId) || window.OpenAver.prefersReducedMotion) return;

      // 1. 暫停此顆呼吸
      this.breathingManager.pauseOne(slotId);

      // 2. Scale up（transformOrigin 確保 hit target 不位移，CD-T2FIX-2）
      gsap.to(this.cards[slotId], { scale: 1.06, duration: 0.18, ease: 'fluent', transformOrigin: '50% 50%' });

      // 3. Dim 其餘 visible slots
      this.visibleSlots.forEach(id => {
        if (id !== slotId && this.cards[id]) {
          gsap.to(this.cards[id], { opacity: 0.5, duration: 0.20, ease: 'fluent' });
        }
      });

      // 4. Icon overlay 浮現（CSS transition）
      const card = this.cards[slotId];
      if (card) {
        const overlay = card.querySelector('.slot-icon-overlay');
        if (overlay) overlay.classList.add('slot-icon--visible');
      }
    },

    /**
     * onHoverLeave — 滑出 slot 卡片
     * 1. 還原 scale 1.0
     * 2. 還原其餘 visible slots opacity 1.0
     * 3. icon overlay 消失
     * 4. 若非 animating 且非 prefers-reduced-motion：恢復此顆呼吸
     *    （animating 期間不 resume，由 slip-through onComplete 的 start() 統一負責）
     *
     * @param {string} slotId
     */
    onHoverLeave(slotId) {
      // animating 或 reduced-motion 下完全 no-op（CD-56B-T2 codex P1+P2）
      // animating 期間 onCardClick 已同步清 hover state，restore tween 多餘且會與 timeline 打架
      // reduced-motion 與 onHoverEnter guard 對稱，hover lifecycle 全 no-op
      if (this.animating || !this.visibleSlots.has(slotId) || window.OpenAver.prefersReducedMotion) return;

      // 1. Restore scale
      gsap.to(this.cards[slotId], { scale: 1.0, duration: 0.18, ease: 'fluent' });

      // 2. Restore others opacity
      this.visibleSlots.forEach(id => {
        if (id !== slotId && this.cards[id]) {
          gsap.to(this.cards[id], { opacity: 1, duration: 0.20, ease: 'fluent' });
        }
      });

      // 3. Icon overlay 消失（CSS transition）
      const card = this.cards[slotId];
      if (card) {
        const overlay = card.querySelector('.slot-icon-overlay');
        if (overlay) overlay.classList.remove('slot-icon--visible');
      }

      // 4. 恢復呼吸（animating 期間跳過，由 slip-through onComplete 統一處理）
      if (!this.animating && !window.OpenAver.prefersReducedMotion) {
        this.breathingManager.resumeOne(slotId);
      }
    },

    /**
     * onExit — 點擊主圖 / 背景觸發退出動畫
     * 退出後刷新頁面（56b standalone 模式）
     */
    onExit() {
      if (this.animating) return;
      this.animating = true;

      // 停止呼吸（退出動畫期間 ticker 不殘留）
      this.breathingManager.stop();

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
