"""T6 Hover Reveal — host state machine + railStarMap geometry guards.

純 Python re-implement，不依賴 DOM / GSAP / JS runtime。
- ANCHORS / railEndpoint 沿用 test_constellation_anchors.py pattern（重複聲明，避免兩處不同步要靠引用）。
- HoverStateMachine 用 dataclass 模擬 host 欄位（_activeFocusedRailId / _activeHoverSlot 等），
  只驗 onHoverEnter / onHoverLeave 中「state 必執行」的不變式，不模擬 GSAP / DOM mutation。

對應契約：
- CD-T6-1：HOVER_DISTANCE = 40，pre-compute 12 條 rail × dust corridor map
- CD-T6-4 / spec §2.6 C3：PRM 下 _activeFocusedRailId 仍被設定（state 必執行）
- CD-T6-5：_railStarMap 12 keys（每條 rail 對應 dust 元素清單），不另外維護影子欄位
"""
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

# ===== Geometry constants（與 web/static/js/shared/constellation/anchors.js 同義）=====
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

HOVER_DISTANCE = 40


def rail_endpoint(anchor):
    """railEndpoint — 與 anchors.js 同義（公式：center + (anchor - center) × 1.4）"""
    return {
        'x': round(CX + (anchor['x'] - CX) * 1.4),
        'y': round(CY + (anchor['y'] - CY) * 1.4),
    }


def point_to_segment_dist(px, py, x1, y1, x2, y2):
    """點到線段最短距離（與 constellation-host.js pointToSegmentDist 同義）"""
    dx, dy = x2 - x1, y2 - y1
    len2 = dx * dx + dy * dy
    if len2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / len2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def build_rail_star_map(dust_coords):
    """
    純 Python re-implement constellation-host.js _buildRailStarMap.
    dust_coords: list[(cx, cy)] → { '#01': [(cx, cy), ...], ... } 12 keys
    """
    result = {}
    for a in ANCHORS_PY:
        ep = rail_endpoint(a)
        result[a['id']] = [
            (cx, cy) for (cx, cy) in dust_coords
            if point_to_segment_dist(cx, cy, CX, CY, ep['x'], ep['y']) <= HOVER_DISTANCE
        ]
    return result


# ===== Dust 座標讀取（從 motion_lab.html SVG <circle cx="..." cy="..."> 抽）=====
def _load_dust_coords_from_template():
    """
    從 web/templates/motion_lab.html 的 <svg class="clip-lab-dust"> 區塊讀 100 顆 dust 座標。
    回傳 list[(cx: float, cy: float)]
    """
    repo_root = Path(__file__).resolve().parents[2]
    html_path = repo_root / 'web' / 'templates' / 'motion_lab.html'
    text = html_path.read_text(encoding='utf-8')

    # 抓 <svg class="clip-lab-dust" ...> ... </svg> 區塊
    m = re.search(
        r'<svg class="clip-lab-dust"[^>]*>(.*?)</svg>',
        text,
        flags=re.DOTALL,
    )
    if not m:
        raise RuntimeError('無法在 motion_lab.html 找到 <svg class="clip-lab-dust"> 區塊')

    block = m.group(1)
    # 抓每個 <circle cx="N" cy="N" ...> 的 cx / cy
    pat = re.compile(r'<circle\s+cx="([0-9.]+)"\s+cy="([0-9.]+)"')
    coords = [(float(cx), float(cy)) for cx, cy in pat.findall(block)]
    return coords


# Module-level singleton；test collection 時讀一次（單檔 shared）
DUST_COORDS = _load_dust_coords_from_template()


# ===== Host state machine simulation =====
@dataclass
class HostStateMachine:
    """
    re-implement constellation-host.js onHoverEnter/onHoverLeave 的「state 必執行」段。

    模擬 _activeFocusedRailId / _activeHoverSlot 兩欄位的同步影子（C1 釐清）。
    不模擬 GSAP / DOM mutation，只驗 PRM 路徑下的 state transition（C3 契約）。
    """
    visible_slots: set = field(default_factory=set)
    animating: bool = False
    prm: bool = False
    _activeFocusedRailId: str = None
    _activeHoverSlot: str = None

    def hover_enter(self, slot_id):
        # T6 (CD-T6-4)：移除 PRM 短路 — PRM 下 state 必執行
        if self.animating or slot_id not in self.visible_slots:
            return
        # state 段（不論 PRM）
        self._activeFocusedRailId = slot_id
        self._activeHoverSlot = slot_id

    def hover_leave(self, slot_id):
        # T6 (CD-T6-4 / reviewer P2-1)：移除 PRM 短路 — PRM 下 state 必執行
        if self.animating or slot_id not in self.visible_slots:
            return
        # stale guard（既有保留）
        if self._activeHoverSlot != slot_id:
            return
        self._activeFocusedRailId = None
        self._activeHoverSlot = None


class TestHoverStateMachine:
    """
    C3 契約：state 必執行（不論 PRM），motion 才條件跳過。
    本測試組只驗 _activeFocusedRailId / _activeHoverSlot 不變式。
    """

    def test_activeFocusedRailId_set_on_enter(self):
        """hover_enter('#01') 後 _activeFocusedRailId == '#01' 且 _activeHoverSlot == '#01'"""
        h = HostStateMachine(visible_slots={'#01', '#02'})
        h.hover_enter('#01')
        assert h._activeFocusedRailId == '#01'
        assert h._activeHoverSlot == '#01'

    def test_activeFocusedRailId_cleared_on_leave(self):
        """hover_leave('#01') 後 _activeFocusedRailId 與 _activeHoverSlot 都歸零"""
        h = HostStateMachine(visible_slots={'#01'})
        h.hover_enter('#01')
        h.hover_leave('#01')
        assert h._activeFocusedRailId is None
        assert h._activeHoverSlot is None

    def test_stale_leave_ignored(self):
        """
        enter('#01') → enter('#02') → leave('#01') 應被 stale guard 擋下，
        _activeHoverSlot 仍為 '#02'（瀏覽器延遲送出舊張 leave 不會清掉新 hover state）。

        注意：本 dataclass 簡化版 hover_enter 不模擬「enter→enter 自清舊張」邏輯
        （host 那層由 _resetHoverRails 處理），所以 enter('#02') 直接覆寫，仍可驗 stale guard。
        """
        h = HostStateMachine(visible_slots={'#01', '#02'})
        h.hover_enter('#01')
        h.hover_enter('#02')   # _activeHoverSlot 覆寫為 '#02'
        h.hover_leave('#01')   # 應被 stale guard 擋下（_activeHoverSlot != '#01'）
        assert h._activeHoverSlot == '#02'
        assert h._activeFocusedRailId == '#02'

    def test_prm_path_does_not_return_early(self):
        """C3 驗證：PRM=true 時 _activeFocusedRailId 仍被設定（state 必執行）"""
        h = HostStateMachine(visible_slots={'#01'}, prm=True)
        h.hover_enter('#01')
        assert h._activeFocusedRailId == '#01', \
            "C3 契約：PRM 下 hover_enter 仍須設定 _activeFocusedRailId（state 必執行）"
        # PRM 下 leave 也不能 early return
        h.hover_leave('#01')
        assert h._activeFocusedRailId is None
        assert h._activeHoverSlot is None


class TestRailStarMapBuild:
    """CD-T6-1 / CD-T6-5 corridor pre-compute 正確性"""

    def test_all_12_anchors_in_map(self):
        """_railStarMap 有 12 個 key，對應 ANCHORS 12 條 rail"""
        m = build_rail_star_map(DUST_COORDS)
        assert len(m) == 12, f"Expected 12 rail keys, got {len(m)}"
        for a in ANCHORS_PY:
            assert a['id'] in m, f"Anchor {a['id']} missing from rail star map"

    def test_corridor_stars_within_40px(self):
        """每個 rail 的 star list 中所有 dust 到 segment 距離 ≤ HOVER_DISTANCE (40 px)"""
        m = build_rail_star_map(DUST_COORDS)
        for a in ANCHORS_PY:
            ep = rail_endpoint(a)
            for (cx, cy) in m[a['id']]:
                d = point_to_segment_dist(cx, cy, CX, CY, ep['x'], ep['y'])
                assert d <= HOVER_DISTANCE, (
                    f"rail {a['id']} dust ({cx},{cy}) dist {d:.2f} > {HOVER_DISTANCE}"
                )

    def test_central_stars_in_multiple_rails(self):
        """
        中心 (480, 310) 附近的 dust 應在多條 rail 的 star list 中（Polaris 感）。
        從 100 顆實際 dust 中找出最靠近中心的一顆，應屬 ≥2 條 rail。
        """
        m = build_rail_star_map(DUST_COORDS)
        # 找最靠近中心的 dust
        center_dust = min(
            DUST_COORDS,
            key=lambda c: math.hypot(c[0] - CX, c[1] - CY),
        )
        rails_with_center = [
            aid for aid, stars in m.items() if center_dust in stars
        ]
        assert len(rails_with_center) >= 2, (
            f"中心 dust {center_dust} 應屬多條 rail（Polaris 感），"
            f"實際: {rails_with_center}"
        )
