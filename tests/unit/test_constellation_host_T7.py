"""T7 Phase Acknowledge — idle timer lifecycle + PRM path + keystone selection guards.

純 Python re-implement，不依賴 DOM / GSAP / JS runtime。
- IdleTimerHost 用 dataclass 模擬 host 欄位（_idleAcknowledgeTimer / prm 等），
  mock setTimeout / clearTimeout 可記錄 cancel count + 模擬 timer state。
- KeystoneSelector pure Python re-implement constellation-host.js _getKeystoneStars。

對應契約：
- CD-T7-2：idle timer 4 處 cancel（destroy / onCardClick / onExit / onHoverEnter）+ 2 處 restart
  （slip-through onComplete / onHoverLeave）
- CD-T7-2 / spec §2.6 C4：PRM 下 _startIdleAcknowledge 首行 return，timer 永不啟動
- CD-T7-1：_getKeystoneStars 取 anchor 端最近 N 顆 dust（非中心端、非隨機）
"""
import math
from dataclasses import dataclass, field
from typing import Callable, Optional


# ===== Geometry constants（與 anchors.js / test_constellation_host_T6.py 同義）=====
ANCHORS_RAW_PY = [
    ('#01', 255, 260),
    ('#02', 700, 235),
    ('#03', 570,  85),
    ('#04', 395, 540),
    ('#05', 595, 540),
    ('#06', 340,  85),
    ('#07', 185, 545),
    ('#08',  75, 350),
    ('#09', 845, 555),
    ('#10', 100, 130),
    ('#11', 900, 360),
    ('#12', 865,  95),
]

CX, CY = 480, 310
SHRINK = 0.92

ANCHORS_PY = [
    {'id': id_,
     'x': round(CX + (x - CX) * SHRINK),
     'y': round(CY + (y - CY) * SHRINK)}
    for id_, x, y in ANCHORS_RAW_PY
]


# ===== IdleTimerHost：mock host 模擬 setTimeout / clearTimeout 行為 =====
@dataclass
class IdleTimerHost:
    """
    re-implement constellation-host.js timer lifecycle 的「行為契約」段。

    _startIdleAcknowledge：
      - PRM 首行 return（C4）
      - 否則 _cancelIdleAcknowledge() + setTimeout 8-15s（mock：賦值 token）
    _cancelIdleAcknowledge：
      - if (timer): clearTimeout + null（mock：increment cancel count）

    模擬 4 個取消點（destroy / onCardClick / onExit / onHoverEnter）
    + 1 個 restart 點（onHoverLeave）。

    不模擬 GSAP / DOM / 真實 setTimeout 觸發；只驗 timer state machine 不變式。
    """
    prm: bool = False
    visible_slots: set = field(default_factory=set)
    animating: bool = False
    _idleAcknowledgeTimer: Optional[int] = None
    _timer_cancelled_count: int = 0
    _activeHoverSlot: Optional[str] = None
    # mock setTimeout token：每次 start 賦一個遞增 ID（!= None），不真實觸發
    _next_token: int = 0

    def start_idle_acknowledge(self):
        """re-implement _startIdleAcknowledge — PRM guard + cancel + setTimeout"""
        if self.prm:
            return
        self.cancel_idle_acknowledge()
        self._next_token += 1
        self._idleAcknowledgeTimer = self._next_token

    def cancel_idle_acknowledge(self):
        """re-implement _cancelIdleAcknowledge — clearTimeout + null"""
        if self._idleAcknowledgeTimer is not None:
            self._timer_cancelled_count += 1
            self._idleAcknowledgeTimer = None

    # ---- 4 cancel wire points（T5 已 wire，T7 stub 替換後生效）----
    def destroy(self):
        """destroy() 開頭 _cancelIdleAcknowledge"""
        self.cancel_idle_acknowledge()

    def on_card_click(self, slot_id: str):
        """onCardClick() 開頭 _cancelIdleAcknowledge（animating guard 後）"""
        if self.animating or slot_id not in self.visible_slots:
            return
        self.cancel_idle_acknowledge()

    def on_exit(self):
        """onExit() 開頭 _cancelIdleAcknowledge"""
        if self.animating:
            return
        self.cancel_idle_acknowledge()

    def on_hover_enter(self, slot_id: str):
        """onHoverEnter() 中段 _cancelIdleAcknowledge"""
        if self.animating or slot_id not in self.visible_slots:
            return
        self.cancel_idle_acknowledge()
        self._activeHoverSlot = slot_id

    def on_hover_leave(self, slot_id: str):
        """onHoverLeave() 末尾 _startIdleAcknowledge（hover 結束 → idle 重新計時）"""
        if self.animating or slot_id not in self.visible_slots:
            return
        if self._activeHoverSlot != slot_id:
            return
        self._activeHoverSlot = None
        self.start_idle_acknowledge()


# ===== KeystoneSelector：pure Python re-implement _getKeystoneStars =====
def get_keystone_stars(slot_id: str, rail_star_map: dict, count: int = 2):
    """
    re-implement constellation-host.js _getKeystoneStars.

    rail_star_map: { '#01': [(cx, cy), ...], ... }（用 (cx, cy) tuple 代替 SVGElement）
    回傳：corridor stars，按距 anchor 升序排序前 N 顆
    """
    anchor = next((a for a in ANCHORS_PY if a['id'] == slot_id), None)
    if anchor is None:
        return []
    stars = rail_star_map.get(slot_id, [])
    if not stars:
        return []
    return sorted(
        stars,
        key=lambda c: math.hypot(c[0] - anchor['x'], c[1] - anchor['y']),
    )[:count]


# ===== Test fixtures =====
def _make_host(prm: bool = False, visible: set = None, animating: bool = False):
    """factory：建立 mock host 並預設 visible slots（pytest fixture 簡化版）"""
    return IdleTimerHost(
        prm=prm,
        visible_slots=visible if visible is not None else {'#01', '#02', '#03'},
        animating=animating,
    )


# ===== Test classes =====
class TestIdleTimerLifecycle:
    """
    CD-T7-2 / spec §2.6 C4：timer 4 處 cancel + 2 處 restart
    """

    def test_timer_cancelled_on_destroy(self):
        """destroy() → _cancelIdleAcknowledge → timer == None"""
        h = _make_host()
        h.start_idle_acknowledge()
        assert h._idleAcknowledgeTimer is not None, "timer should be set after start"
        h.destroy()
        assert h._idleAcknowledgeTimer is None, \
            "C4 契約：destroy 必清 timer"

    def test_timer_cancelled_on_card_click(self):
        """onCardClick(visible slot) → _cancelIdleAcknowledge → cancel count >= 1"""
        h = _make_host(visible={'#01'})
        h.start_idle_acknowledge()
        before = h._timer_cancelled_count
        h.on_card_click('#01')
        assert h._timer_cancelled_count >= before + 1, \
            "C4 契約：onCardClick 必呼叫 _cancelIdleAcknowledge"
        assert h._idleAcknowledgeTimer is None, \
            "cancel 後 timer 必為 None"

    def test_timer_cancelled_on_exit(self):
        """onExit() → _cancelIdleAcknowledge → timer == None"""
        h = _make_host()
        h.start_idle_acknowledge()
        h.on_exit()
        assert h._idleAcknowledgeTimer is None, \
            "C4 契約：onExit 必清 timer"

    def test_timer_cancelled_on_hover_enter(self):
        """onHoverEnter(visible slot) → _cancelIdleAcknowledge → timer == None"""
        h = _make_host(visible={'#01'})
        h.start_idle_acknowledge()
        h.on_hover_enter('#01')
        assert h._idleAcknowledgeTimer is None, \
            "C4 契約：onHoverEnter 必清 timer（hover 期間暫停 idle pulse）"

    def test_timer_restarted_on_hover_leave(self):
        """onHoverLeave(matching slot) → _startIdleAcknowledge → timer != None"""
        h = _make_host(visible={'#01'})
        h.on_hover_enter('#01')
        assert h._idleAcknowledgeTimer is None, "hover_enter 後 timer 應已被清"
        h.on_hover_leave('#01')
        assert h._idleAcknowledgeTimer is not None, \
            "C4 契約：onHoverLeave 末尾必呼叫 _startIdleAcknowledge（hover 結束 → idle 重新計時）"


class TestPRMPath:
    """
    spec §2.6 C4：PRM 下 idle timer 不啟動、keystone pulse 不觸發
    """

    def test_prm_timer_never_starts(self):
        """PRM=True → start_idle_acknowledge 首行 return，timer 永遠 None"""
        h = _make_host(prm=True)
        h.start_idle_acknowledge()
        assert h._idleAcknowledgeTimer is None, \
            "C4 契約：PRM 下 _startIdleAcknowledge 首行 return，timer 不啟動"

    def test_prm_hover_leave_does_not_restart_timer(self):
        """
        PRM 下，onHoverLeave 末尾雖呼叫 _startIdleAcknowledge，但 PRM guard 擋下，
        timer 仍為 None（keystone pulse 走 onCardClick PRM 短路 sync 處理，不到 onComplete，
        即使能到也透過此 guard 確保 idle 路徑不啟動）。
        """
        h = _make_host(prm=True, visible={'#01'})
        h.on_hover_enter('#01')
        h.on_hover_leave('#01')
        assert h._idleAcknowledgeTimer is None, \
            "C4 契約：PRM 下 hover_leave 雖呼叫 _startIdleAcknowledge，但 PRM guard 擋下"


class TestGetKeystoneStars:
    """
    CD-T7-1：keystone = corridor stars 中距離 anchor 端最近的 N 顆
    """

    def test_returns_anchor_nearest_stars(self):
        """
        構造 fake corridor：5 顆 dust 沿 (CX, CY) → anchor 端的線段散布，
        驗 _getKeystoneStars 取的前 2 顆是離 anchor 最近的（非中心、非隨機）。
        """
        slot_id = '#01'  # anchor at (CX + (255-CX)*SHRINK, CY + (260-CY)*SHRINK) ≈ (273, 264)
        anchor = next(a for a in ANCHORS_PY if a['id'] == slot_id)
        # 沿 center → anchor 線段散布 5 顆，t=0.0 (中心) → t=1.0 (anchor)
        ts = [0.0, 0.25, 0.5, 0.75, 1.0]
        corridor = [
            (CX + (anchor['x'] - CX) * t,
             CY + (anchor['y'] - CY) * t)
            for t in ts
        ]
        rail_star_map = {slot_id: corridor}
        # 取前 2 顆應是 t=1.0 與 t=0.75（最靠近 anchor 的）
        result = get_keystone_stars(slot_id, rail_star_map, count=2)
        assert len(result) == 2, f"Expected 2 stars, got {len(result)}"
        # 第一顆距 anchor 最近，第二顆次之
        d0 = math.hypot(result[0][0] - anchor['x'], result[0][1] - anchor['y'])
        d1 = math.hypot(result[1][0] - anchor['x'], result[1][1] - anchor['y'])
        assert d0 <= d1, f"Result 必按距 anchor 升序：d0={d0:.2f} > d1={d1:.2f}"
        # 驗第一顆是 t=1.0（anchor 本身），第二顆是 t=0.75
        expected_first = corridor[4]  # t=1.0
        expected_second = corridor[3]  # t=0.75
        assert result[0] == expected_first, \
            f"First star 應是 t=1.0（anchor 端最近），實際 {result[0]}"
        assert result[1] == expected_second, \
            f"Second star 應是 t=0.75，實際 {result[1]}"

    def test_returns_empty_for_unknown_slot(self):
        """slot_id 不在 ANCHORS → return []（graceful fallback）"""
        result = get_keystone_stars('#99', {'#99': [(100, 100)]}, count=2)
        assert result == [], "未知 slot_id 應 return []"

    def test_returns_empty_for_empty_corridor(self):
        """corridor 空 → return []（graceful fallback）"""
        result = get_keystone_stars('#01', {'#01': []}, count=2)
        assert result == [], "空 corridor 應 return []"

    def test_count_parameter_respected(self):
        """count=1 → 只取 1 顆；count > corridor size → 取全部"""
        slot_id = '#01'
        anchor = next(a for a in ANCHORS_PY if a['id'] == slot_id)
        corridor = [
            (anchor['x'] + 10, anchor['y']),
            (anchor['x'] + 20, anchor['y']),
            (anchor['x'] + 5, anchor['y']),
        ]
        rail_star_map = {slot_id: corridor}
        # count=1
        r1 = get_keystone_stars(slot_id, rail_star_map, count=1)
        assert len(r1) == 1
        # 最近 anchor 的是 +5 那顆
        assert r1[0] == (anchor['x'] + 5, anchor['y'])
        # count=10（> corridor size）→ 取全部 3 顆，且按距升序
        r10 = get_keystone_stars(slot_id, rail_star_map, count=10)
        assert len(r10) == 3
        assert r10[0] == (anchor['x'] + 5, anchor['y'])
        assert r10[1] == (anchor['x'] + 10, anchor['y'])
        assert r10[2] == (anchor['x'] + 20, anchor['y'])
