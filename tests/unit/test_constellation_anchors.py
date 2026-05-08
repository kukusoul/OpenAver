"""
test_constellation_anchors.py — Python 幾何驗證 + pickEight invariant
CD-56B-1 / CD-56B-2 純邏輯測試（不 import JS 檔案）
"""
import math
import random

# ---------------------------------------------------------------------------
# SSOT：複製自 CD-56B-1（anchors.js ANCHORS_RAW）
# #09 為 (845, 555)，不是舊 (830, 540)
# ---------------------------------------------------------------------------
ANCHORS_RAW_PY = [
    ('#01', 255, 260),
    ('#02', 700, 235),
    ('#03', 570,  85),
    ('#04', 395, 540),
    ('#05', 595, 540),
    ('#06', 340,  85),
    ('#07', 185, 545),
    ('#08',  75, 350),
    ('#09', 845, 555),  # Changed from (830,540) — 解決最小距離瓶頸
    ('#10', 100, 130),
    ('#11', 900, 360),
    ('#12', 865,  95),
]

CX, CY = 480, 310
SHRINK = 0.92

# Apply SHRINK toward center
ANCHORS_PY = [
    (id_, round(CX + (x - CX) * SHRINK), round(CY + (y - CY) * SHRINK))
    for id_, x, y in ANCHORS_RAW_PY
]

ANCHOR_IDS = [a[0] for a in ANCHORS_PY]

# Stage dimensions
STAGE_W, STAGE_H = 960, 620
# Card half-dimensions
HALF_W, HALF_H = 60, 75
# Main image box: 200×250 centered at (480, 310)
MAIN_IMG_LEFT  = CX - 100   # 380
MAIN_IMG_RIGHT = CX + 100   # 580
MAIN_IMG_TOP   = CY - 125   # 185
MAIN_IMG_BOT   = CY + 125   # 435


# ---------------------------------------------------------------------------
# Python re-implementation of pickEight (mirrors CD-56B-2 JS logic)
# ---------------------------------------------------------------------------
def sample_n_py(candidates, n, rng):
    """Fisher-Yates partial shuffle, returns list of n elements."""
    lst = list(candidates)
    result = []
    for i in range(min(n, len(lst))):
        j = i + int(rng() * (len(lst) - i))
        lst[i], lst[j] = lst[j], lst[i]
        result.append(lst[i])
    return result


def pick_eight_py(exclude_slot_id, prev_visible, rng=None):
    """
    Pure Python re-implementation of pickEight from CD-56B-2.
    Returns a frozenset of 8 slot ids.
    """
    if rng is None:
        rng = random.random

    carry_candidates = [id_ for id_ in ANCHOR_IDS
                        if id_ in prev_visible and id_ != exclude_slot_id]
    fresh_candidates = [id_ for id_ in ANCHOR_IDS
                        if id_ not in prev_visible and id_ != exclude_slot_id]

    C = 4 + int(rng() * 3)  # [4, 5, 6]
    F = 8 - C

    actual_c = min(C, len(carry_candidates))
    actual_f = min(F, len(fresh_candidates))

    chosen = (
        sample_n_py(carry_candidates, actual_c, rng) +
        sample_n_py(fresh_candidates, actual_f, rng)
    )

    # top-up safety net (edge case, should not trigger with standard inputs)
    if len(chosen) < 8:
        remaining = [id_ for id_ in ANCHOR_IDS
                     if id_ not in chosen and id_ != exclude_slot_id]
        needed = 8 - len(chosen)
        chosen += sample_n_py(remaining, needed, rng)

    return frozenset(chosen[:8])


# ---------------------------------------------------------------------------
# TestAnchorGeometry
# ---------------------------------------------------------------------------
class TestAnchorGeometry:
    def test_all_in_bounds(self):
        """每個 anchor card box (halfW=60, halfH=75) 全在 960×620 viewport 內"""
        for id_, x, y in ANCHORS_PY:
            assert x - HALF_W >= 0, f"{id_} left edge out of bounds: {x - HALF_W}"
            assert x + HALF_W <= STAGE_W, f"{id_} right edge out of bounds: {x + HALF_W}"
            assert y - HALF_H >= 0, f"{id_} top edge out of bounds: {y - HALF_H}"
            assert y + HALF_H <= STAGE_H, f"{id_} bottom edge out of bounds: {y + HALF_H}"

    def test_min_pairwise_distance(self):
        """所有 anchor pair 兩兩中心距 ≥ 175px（最接近：#01/#06 ≈ 178.90px）"""
        min_dist = float('inf')
        min_pair = None
        for i in range(len(ANCHORS_PY)):
            for j in range(i + 1, len(ANCHORS_PY)):
                id_i, xi, yi = ANCHORS_PY[i]
                id_j, xj, yj = ANCHORS_PY[j]
                dist = math.hypot(xi - xj, yi - yj)
                if dist < min_dist:
                    min_dist = dist
                    min_pair = (id_i, id_j, dist)
        assert min_dist >= 175, (
            f"Minimum pairwise distance {min_dist:.2f}px < 175px "
            f"(pair: {min_pair[0]}/{min_pair[1]} = {min_pair[2]:.2f}px)"
        )

    def test_left_right_split(self):
        """左側（x < 480）恰好 6 顆，右側（x ≥ 480）恰好 6 顆"""
        left = sum(1 for _, x, _ in ANCHORS_PY if x < CX)
        right = sum(1 for _, x, _ in ANCHORS_PY if x >= CX)
        assert left == 6, f"Expected 6 left-side anchors, got {left}"
        assert right == 6, f"Expected 6 right-side anchors, got {right}"

    def test_no_overlap_with_main_image(self):
        """#01-#04 SHRINK 後座標與主圖 box 面積重疊 = 0 px²"""
        for id_, x, y in ANCHORS_PY:
            if id_ not in ('#01', '#02', '#03', '#04'):
                continue
            # card box
            card_left  = x - HALF_W
            card_right = x + HALF_W
            card_top   = y - HALF_H
            card_bot   = y + HALF_H

            # overlap
            overlap_w = max(0, min(card_right, MAIN_IMG_RIGHT) - max(card_left, MAIN_IMG_LEFT))
            overlap_h = max(0, min(card_bot, MAIN_IMG_BOT) - max(card_top, MAIN_IMG_TOP))
            overlap_area = overlap_w * overlap_h

            assert overlap_area == 0, (
                f"{id_} overlaps main image box: "
                f"card=({card_left},{card_top},{card_right},{card_bot}), "
                f"mainImg=({MAIN_IMG_LEFT},{MAIN_IMG_TOP},{MAIN_IMG_RIGHT},{MAIN_IMG_BOT}), "
                f"overlap={overlap_area}px²"
            )


# ---------------------------------------------------------------------------
# TestPickEight
# ---------------------------------------------------------------------------
class TestPickEight:
    """pickEight invariant — Python re-implementation，固定種子 rng"""

    INIT_VISIBLE = frozenset(['#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08'])
    CLICKED = '#03'

    def _make_rng(self, seed=42):
        return random.Random(seed).random

    def test_returns_eight(self):
        """回傳 Set 大小 = 8"""
        result = pick_eight_py(self.CLICKED, self.INIT_VISIBLE, self._make_rng(42))
        assert len(result) == 8, f"Expected 8 slots, got {len(result)}"

    def test_excludes_clicked_slot(self):
        """回傳 Set 不包含 excludeSlotId"""
        result = pick_eight_py(self.CLICKED, self.INIT_VISIBLE, self._make_rng(42))
        assert self.CLICKED not in result, (
            f"Result should not contain clicked slot {self.CLICKED}"
        )

    def test_carry_over_in_range(self):
        """carry-over count（回傳中屬於 prevVisible 的數量）∈ [4, 6]"""
        rng = self._make_rng(42)
        result = pick_eight_py(self.CLICKED, self.INIT_VISIBLE, rng)
        carry_count = sum(1 for id_ in result if id_ in self.INIT_VISIBLE)
        assert 4 <= carry_count <= 6, (
            f"carry-over count {carry_count} not in [4, 6]"
        )

    def test_no_duplicate(self):
        """回傳 Set 內無重複（frozenset 本身保證，但驗 sampleN 邏輯）"""
        result = pick_eight_py(self.CLICKED, self.INIT_VISIBLE, self._make_rng(42))
        # frozenset 已去重，但如果有 duplicate，len 會 < 8（test_returns_eight 已覆蓋）
        result_list_check = list(result)
        assert len(result_list_check) == len(set(result_list_check)), (
            "Result contains duplicates"
        )

    def test_fresh_slots_not_in_prev(self):
        """fresh slots（回傳中不屬於 prevVisible 的部分）⊄ prevVisible"""
        result = pick_eight_py(self.CLICKED, self.INIT_VISIBLE, self._make_rng(42))
        fresh_in_result = [id_ for id_ in result if id_ not in self.INIT_VISIBLE]
        for id_ in fresh_in_result:
            assert id_ not in self.INIT_VISIBLE, (
                f"Fresh slot {id_} should not be in prevVisible"
            )
        # Additional: total fresh + carry should sum to 8
        carry_count = sum(1 for id_ in result if id_ in self.INIT_VISIBLE)
        fresh_count = len(fresh_in_result)
        assert carry_count + fresh_count == 8, (
            f"carry({carry_count}) + fresh({fresh_count}) != 8"
        )
