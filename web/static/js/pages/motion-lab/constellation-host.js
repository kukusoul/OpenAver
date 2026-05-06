/**
 * pages/motion-lab/constellation-host.js — Thin host：Alpine.data('constellationLab', ...)
 *
 * 56b-T3：從 pages/clip-lab/main.js 等價搬遷至 motion-lab Constellation tab。
 * import 路徑深度多一層（../../shared/constellation/...），其餘行為與舊 host 等價。
 *
 * CD-56B-8 thin host 規範：
 *   - 只做：import shared 模組、Alpine.data 宣告、init + click dispatch
 *   - 禁做：座標計算、rail 邏輯、timeline 建構
 * 雙抽防護：host onCardClick 算 nextVisible，再傳 animations；animations 不 import pickEight
 *
 * D-4：Constellation tab panel 用 x-if，mount/destroy 觸發 Alpine init / destroy lifecycle。
 *      destroy() 內呼叫 breathingManager.stop() + _gsapCtx.revert()，避免 ticker / tween 殘留。
 */

import { ANCHORS, pickEight, nearestNeighbors } from '../../shared/constellation/anchors.js';
import { setRailCoords, railFocusPulse, railSweep, resetSweepLine } from '../../shared/constellation/rails.js';
import { playInitialExpand, playSlipThrough, playExit } from '../../shared/constellation/animations.js';
import { BreathingManager } from '../../shared/constellation/breathing.js';

document.addEventListener('alpine:init', () => {
  Alpine.data('constellationLab', () => ({
    animating: false,
    visibleSlots: new Set(),
    mainSlot: null,
    cards: {},       // slotId -> HTMLElement
    railLines: {},   // slotId -> SVGLineElement
    sweepLines: {},  // slotId -> SVGLineElement（sweep overlay）
    breathingManager: null,
    _mainBreathTween: null,
    _activeTimeline: null,         // 當前 play* 回傳的 timeline，destroy 時 kill（Codex T3 P1）
    _activeFocusedRailId: null,    // hover focus 的 slotId（用於 _resetHoverRails cleanup）
    _activeNeighborRailIds: [],    // hover 觸發的 neighbor slotIds
    _activeHoverSlot: null,        // 當前 hover 的 slotId（防 enter→enter 殘留，T2fix5 Codex P2）

    init() {
      this._gsapCtx = window.OpenAver.motion.createContext(this.$el);

      // Build DOM refs（card / rail 用 id 對應，id 格式 card-01 / rail-01）
      ANCHORS.forEach(a => {
        const num = a.id.slice(1); // '#01' → '01'
        this.cards[a.id] = document.getElementById(`card-${num}`);
        this.railLines[a.id] = document.getElementById(`rail-${num}`);
        this.sweepLines[a.id] = document.getElementById(`sweep-${num}`);

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

      this._playInitialExpand();
    },

    /**
     * _playInitialExpand — 啟動初始 8 顆展開（init 與 onExit 重置共用）
     * Codex T3 P1：timeline reference 存進 _activeTimeline，destroy 時 kill
     * Codex T3 P1：onComplete 內加 destroyed guard（_gsapCtx 已 null 表示 tab 已切走），
     *              避免在已銷毀 DOM 上呼叫 breathingManager.start。
     */
    _playInitialExpand() {
      const initSlots = new Set(['#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08']);
      this.animating = true;
      this._activeTimeline = playInitialExpand(this.cards, this.railLines, initSlots, () => {
        if (!this._gsapCtx) return; // destroyed during animation — stop here
        this._activeTimeline = null;
        this.visibleSlots = new Set(initSlots);
        this.animating = false;
        this.breathingManager.start(initSlots);
        this._startMainBreath();
      });
    },

    /**
     * destroy — Alpine x-if mount/destroy lifecycle hook（D-4）
     * tab 切走時 x-if=false → DOM 銷毀 → Alpine 觸發 destroy()。
     * 關鍵：停 BreathingManager ticker（gsap.ticker.remove）+ revert GSAP context（清所有 tween / inline style）。
     */
    destroy() {
      // Codex T3 P1：kill 當前 play* timeline（gsap.context 不收 host 模組層建立的 timeline，
      // 不 kill 會讓 onComplete 在 DOM 銷毀後仍重啟 breathing ticker）
      if (this._activeTimeline) {
        this._activeTimeline.kill();
        this._activeTimeline = null;
      }
      this.breathingManager?.stop();
      this._stopMainBreath();
      // Codex T3 P2 follow-up #2：createContext(this.$el) 用空 fn 建立，host 之後直呼 gsap.to() 的 tween
      // （carry-bump halo / survivor shimmer / hover card+rail / neighbor strokeWidth 等）不會被 ctx 自動收。
      // tab 切走時若有 delayed/in-flight tween，會在已銷毀 DOM 上繼續跑。
      // → 在 ctx.revert 前對所有 host 持有的 DOM 與 halo 全 killTweensOf。
      gsap.killTweensOf('#main-halo-outer');
      gsap.killTweensOf('#main-halo-inner');
      gsap.killTweensOf('#main-img');
      ANCHORS.forEach(a => {
        if (this.cards[a.id]) gsap.killTweensOf(this.cards[a.id]);
        if (this.railLines[a.id]) gsap.killTweensOf(this.railLines[a.id]);
        if (this.sweepLines[a.id]) gsap.killTweensOf(this.sweepLines[a.id]);
      });
      if (this._gsapCtx) {
        this._gsapCtx.revert();
        this._gsapCtx = null;
      }
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
      // _resetHoverRails 防禦（切換 reduced-motion 後 hover 再 click 的極端情形）
      if (window.OpenAver.prefersReducedMotion) {
        if (this._activeHoverSlot !== null) {
          this._resetHoverCard(this._activeHoverSlot);
          this._activeHoverSlot = null;
        }
        this._resetHoverRails();
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

      // T2fix3: 停止 main 自呼吸（absorb 期間無 yoyo 殘留，_stopMainBreath 強制 reset scale=1）
      this._stopMainBreath();
      // T2fix3 P2: kill 上一輪 carry-bump delayed tween，避免在新 absorb 的 0.55→0.85 expand 進行中
      // 拉回 opacity=0.55 蓋掉新 flash（race window：animating=false 後 ~1.4s 內再點）
      gsap.killTweensOf('#main-halo-outer');

      // T2fix3: carry-over ≥5 時 outer halo 略亮（CD-T2FIX-4 §E）
      // 不用 Set.intersection（ES2025 ban，ESLint Group 6 守衛）
      const carryCount = [...nextVisible].filter(id => prevVisible.has(id) && id !== slotId).length;
      if (carryCount >= 5 && !window.OpenAver.prefersReducedMotion) {
        gsap.to('#main-halo-outer', { '--main-halo-opacity': 0.65, duration: 0.45, ease: 'fluent-decel', delay: 0.6 });
        gsap.to('#main-halo-outer', { '--main-halo-opacity': 0.55, duration: 0.55, ease: 'fluent', delay: 1.4 });
      }

      // sweep / focused / neighbor rail 殘留清理（避 hover→click race，CD-T2FIX-3 + T2fix5）
      // 清 hover card 殘留（scale / opacity / icon / breathing，Codex T2fix5 P2 Finding 1）
      if (this._activeHoverSlot !== null) {
        this._resetHoverCard(this._activeHoverSlot);
        this._activeHoverSlot = null;
      }
      this._resetHoverRails();
      // 防守性 classList 掃描：清除未追蹤到的殘留（不含 tween kill，無效能疑慮）
      this.visibleSlots.forEach(id => {
        const rl = this.railLines[id];
        if (rl) rl.classList.remove('rail--bright', 'rail--neighbor');
      });

      this.animating = true;

      // 同步清 hover 殘留 tween + 視覺 state（CD-56B-T2 codex P1）
      // 避免 mouseleave 在 slip-through 期間觸發 restore tween 與 exit/fade 打架
      this.visibleSlots.forEach(id => {
        const card = this.cards[id];
        if (!card) return;
        gsap.killTweensOf(card, 'scale,opacity');
        if (id !== slotId) gsap.set(card, { opacity: 1 });
        // clearProps: 'scale,rotation' 確保所有 card（含 clicked）從 scale=1.0/rotation=0 起跳（CD-T2FIX-2 + polish）
        gsap.set(card, { clearProps: 'scale,rotation' });
        const overlay = card.querySelector('.slot-icon-overlay');
        if (overlay) overlay.classList.remove('slot-icon--visible');
      });

      // 停止呼吸（slip-through 期間 ticker 不殘留）
      this.breathingManager.stop();

      this._activeTimeline = playSlipThrough(
        slotId,
        prevVisible,
        nextVisible,
        this.cards,
        this.railLines,
        document.getElementById('main-img'),
        () => {
          if (!this._gsapCtx) return; // destroyed during slip-through (Codex T3 P1)
          this._activeTimeline = null;
          this.mainSlot = slotId;
          this.visibleSlots = nextVisible; // 與 animation 使用的批次完全一致
          this.animating = false;
          // slip-through 完成後重啟呼吸（新批 8 顆各自相位）
          if (!window.OpenAver.prefersReducedMotion) {
            this.breathingManager.start(nextVisible);
            // T2fix3: 重啟 main 自呼吸
            this._startMainBreath();
            // T2fix4 預埋：carry-over survivor shimmer（closure 捕獲 prevVisible，不讀 this.visibleSlots）
            const carryIds = [...prevVisible].filter(id => id !== slotId && nextVisible.has(id));
            this._playSurvivorShimmer(carryIds);
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

      // 防 enter→enter 直跳殘留（Codex T2fix5 P2 Finding 1）：
      // 若上一張 hover 未 leave 就直接 hover 到新張，先清舊張 card 狀態再進入
      if (this._activeHoverSlot && this._activeHoverSlot !== slotId) {
        this._resetHoverCard(this._activeHoverSlot);
      }

      // 清 rail state（focused/sweep/neighbor）
      this._resetHoverRails();

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

      // Rail 能量感（CD-T2FIX-3）
      // kill any pending shimmer strokeWidth tween before hover tweens（Codex T2fix5 P2 Finding 2）
      const focusedLine = this.railLines[slotId];
      const sweepLine = this.sweepLines[slotId];
      if (focusedLine) {
        gsap.killTweensOf(focusedLine, 'strokeWidth');
        railFocusPulse(focusedLine);
      }
      if (focusedLine && sweepLine) railSweep(sweepLine, focusedLine);

      // 追蹤 focused rail（用於 _resetHoverRails cleanup，CD-T2FIX-6）
      this._activeFocusedRailId = slotId;

      // Neighbor highlight（CD-T2FIX-6 / TASK-T2fix5）
      const neighbors = nearestNeighbors(slotId, [...this.visibleSlots], 3);
      neighbors.forEach(nid => {
        const nline = this.railLines[nid];
        if (nline) {
          // kill pending shimmer strokeWidth tween before neighbor hover tween（Codex T2fix5 P2 Finding 2）
          gsap.killTweensOf(nline, 'strokeWidth');
          gsap.to(nline, { strokeWidth: 1.8, duration: 0.20, ease: 'fluent' });
          nline.classList.add('rail--neighbor');
        }
      });
      this._activeNeighborRailIds = neighbors;

      // 追蹤當前 hover slot（防 enter→enter 殘留，Codex T2fix5 P2 Finding 1）
      this._activeHoverSlot = slotId;

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

      // Stale guard（Codex T2fix5 P2 Finding 1）：瀏覽器可能延遲送出舊張的 leave 事件，
      // 此時 _activeHoverSlot 已換成新張，忽略延遲 leave 避免清掉新 hover state
      if (this._activeHoverSlot !== slotId) return;

      // 1-4: Restore card scale / opacity / icon / breathing（共用 helper）
      // _resetHoverCard 內部已處理 resumeOne，此處不再重複
      this._resetHoverCard(slotId);

      // 清 sweep / focused rail + neighbor rails（CD-T2FIX-3 + T2fix5 整合）
      this._resetHoverRails();

      // 歸零 hover slot 追蹤
      this._activeHoverSlot = null;
    },

    /**
     * onExit — 點擊主圖 / 背景觸發退出動畫
     * Codex T3 P2：原 standalone 模式 location.reload() 不適用 motion-lab tab 場景
     * （會把整頁 reload 回 default search tab）。改為退出動畫完成後本地 reset：
     * 清 visibleSlots / mainSlot，重跑 _playInitialExpand 讓 sandbox 可繼續探索。
     * Codex T3 P1：timeline reference 存 _activeTimeline，destroy 時 kill。
     */
    onExit() {
      if (this.animating) return;
      this.animating = true;

      // 清 hover card 殘留（scale / opacity / icon / breathing，Codex T2fix5 P2 Finding 1）
      if (this._activeHoverSlot !== null) {
        this._resetHoverCard(this._activeHoverSlot);
        this._activeHoverSlot = null;
      }
      // 清 hover rails 殘留（退出動畫期間不應殘留 neighbor strokeWidth，CD-T2FIX-6）
      this._resetHoverRails();

      // T2fix3: 停止 main 自呼吸（退出前 scale 強制 reset）
      this._stopMainBreath();

      // 停止呼吸（退出動畫期間 ticker 不殘留）
      this.breathingManager.stop();

      this._activeTimeline = playExit(
        this.cards,
        this.railLines,
        this.visibleSlots,
        document.getElementById('main-img'),
        () => {
          if (!this._gsapCtx) return; // destroyed during exit (Codex T3 P1)
          this._activeTimeline = null;
          // Reset state，重新展開（取代 standalone reload）
          // playExit 把 main-img 設為 opacity:0 / scale:0.95，須還原為初始 visible 1.0
          gsap.set('#main-img', { opacity: 1, scale: 1 });
          this.visibleSlots = new Set();
          this.mainSlot = null;
          this.animating = false;
          // Codex T3 P2 follow-up：上一輪若有 #09-#12 visible，playExit 後仍 opacity:0 但無 slot--hidden，
          // 形成隱形 hover/click 目標。_playInitialExpand 只初始化 #01-#08，需先把 12 個全 reset。
          this._resetAllSlotsToBaseline();
          this._playInitialExpand();
        }
      );
    },

    /**
     * _startMainBreath — main 圖自呼吸（scale 1→1.018，5.6s sine.inOut yoyo）
     * reduced-motion guard：prefersReducedMotion 時直接 return，不建 tween
     */
    _startMainBreath() {
      if (window.OpenAver.prefersReducedMotion) return;
      this._mainBreathTween = gsap.to('#main-img', {
        scale: 1.018,
        duration: 5.6,
        ease: 'sine.inOut',
        yoyo: true,
        repeat: -1,
      });
    },

    /**
     * _stopMainBreath — kill main 呼吸 tween + 強制 reset scale=1
     * gsap.set 強制歸位：kill 不自動 reset，yoyo 中段被 kill 會殘留 scale
     */
    _stopMainBreath() {
      if (this._mainBreathTween) {
        this._mainBreathTween.kill();
        this._mainBreathTween = null;
      }
      gsap.set('#main-img', { scale: 1 });
    },

    /**
     * _playSurvivorShimmer — carry-over 卡片 glow 雙脈衝 + rail strokeWidth 雙脈衝
     *
     * 每張 carry-over card：`--card-glow-opacity` 0→0.85（0.25s）→0（0.40s）。
     * 每條 rail line：strokeWidth 1.5→1.7（0.18s）→1.5（0.20s）。
     * 連點時先 killTweensOf 清掉前一輪 pending tween，避免 `--card-glow-opacity` 殘留。
     * reduced-motion：no-op。
     *
     * @param {string[]} carryIds
     */
    _playSurvivorShimmer(carryIds) {
      if (window.OpenAver.prefersReducedMotion) return;
      carryIds.forEach(id => {
        const card = this.cards[id];
        const line = this.railLines[id];
        if (card) {
          gsap.killTweensOf(card, '--card-glow-opacity');
          gsap.to(card, { '--card-glow-opacity': 0.85, duration: 0.25, ease: 'fluent-decel' });
          gsap.to(card, { '--card-glow-opacity': 0, duration: 0.40, ease: 'fluent', delay: 0.25 });
        }
        if (line) {
          gsap.killTweensOf(line, 'strokeWidth');
          gsap.to(line, { strokeWidth: 1.7, duration: 0.18, ease: 'fluent' });
          gsap.to(line, { strokeWidth: 1.5, duration: 0.20, ease: 'fluent', delay: 0.18 });
        }
      });
    },

    /**
     * _resetHoverCard — hover card 視覺還原 helper（Codex T2fix5 P2 Finding 1）
     * 還原指定 slot 的 card scale / 其餘卡片 opacity / icon overlay / breathing。
     * 供 onHoverLeave、onHoverEnter（enter→enter）、onCardClick、onExit 共用。
     * reduced-motion 下：用 gsap.set 同步歸位（不 tween），接受邊緣不處理。
     *
     * 不負責：rail 清理（由 _resetHoverRails 負責）、_activeHoverSlot 歸零（由呼叫方負責）
     *
     * @param {string} slotId
     */
    _resetHoverCard(slotId) {
      const card = this.cards[slotId];
      const useSet = window.OpenAver.prefersReducedMotion;

      // 1. Restore scale
      if (card) {
        if (useSet) {
          gsap.set(card, { scale: 1.0 });
        } else {
          gsap.to(card, { scale: 1.0, duration: 0.18, ease: 'fluent' });
        }
      }

      // 2. Restore others opacity
      this.visibleSlots.forEach(id => {
        if (id !== slotId && this.cards[id]) {
          if (useSet) {
            gsap.set(this.cards[id], { opacity: 1 });
          } else {
            gsap.to(this.cards[id], { opacity: 1, duration: 0.20, ease: 'fluent' });
          }
        }
      });

      // 3. Icon overlay 消失
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
     * _resetHoverRails — hover 清理 helper（CD-T2FIX-6 / TASK-T2fix5）
     * 整合 T2fix2/3 既有 focused rail / sweep 清理 + 新增 neighbor 清理
     *
     * 不接觸：#main-img、halo DOM、breathingManager、animating flag
     */
    /**
     * _resetAllSlotsToBaseline — 把 12 個 slot / rail / sweep 全部回到「init 前」baseline
     * Codex T3 P2 follow-up：onExit 後若上一輪 visibleSlots 含 #09-#12，這些 slot 在 playExit
     * 結束後會留下 opacity:0 但無 .slot--hidden，pointer-events 仍 active；rail 同理。
     * _playInitialExpand 只初始化 #01-#08，碰不到 #09-#12 殘留 → 產生隱形 hover/click 目標。
     * 本 helper 與 init() 開頭的 DOM 建立段落同義（card 居中 + 全 hidden / rail+sweep hidden）。
     */
    _resetAllSlotsToBaseline() {
      ANCHORS.forEach(a => {
        const card = this.cards[a.id];
        const line = this.railLines[a.id];
        const sweep = this.sweepLines[a.id];
        if (card) {
          gsap.killTweensOf(card);
          card.classList.add('slot--hidden');
          card.classList.remove('rail--bright', 'rail--neighbor'); // 防呆（class 應掛 rail，不會在 card；但保險清）
          gsap.set(card, {
            left: 480,
            top: 310,
            width: 120,
            height: 150,
            opacity: 0,
            zIndex: '',
            clearProps: 'scale,rotation,transform,--card-glow-opacity',
          });
          const overlay = card.querySelector('.slot-icon-overlay');
          if (overlay) overlay.classList.remove('slot-icon--visible');
        }
        if (line) {
          gsap.killTweensOf(line);
          line.classList.add('rail--hidden');
          line.classList.remove('rail--bright', 'rail--neighbor');
          gsap.set(line, { opacity: 0, strokeWidth: 1.5 });
        }
        if (sweep) resetSweepLine(sweep);
      });
      this._activeFocusedRailId = null;
      this._activeNeighborRailIds = [];
    },

    _resetHoverRails() {
      // 清 focused rail（railFocusPulse + railSweep 殘留）
      if (this._activeFocusedRailId) {
        const line = this.railLines[this._activeFocusedRailId];
        if (line) {
          gsap.killTweensOf(line, 'strokeWidth,opacity');
          gsap.set(line, { strokeWidth: 1.5 });
          line.classList.remove('rail--bright');
        }
        const sw = this.sweepLines[this._activeFocusedRailId];
        if (sw) resetSweepLine(sw);
        this._activeFocusedRailId = null;
      }
      // 清 neighbor rails
      this._activeNeighborRailIds.forEach(nid => {
        const nline = this.railLines[nid];
        if (nline) {
          gsap.killTweensOf(nline, 'strokeWidth');
          gsap.set(nline, { strokeWidth: 1.5 });
          nline.classList.remove('rail--neighbor');
        }
      });
      this._activeNeighborRailIds = [];
    },
  }));
});
