"""
test_constellation_neighbors.py — Python 幾何驗證：nearestNeighbors invariants
CD-T2FIX-6 / TASK-T2fix5

Python SSOT 複製 JS ANCHORS（同 test_constellation_anchors.py 風格）
pure function nearestNeighbors_py 與 JS export 同邏輯
"""
import math

# ---------------------------------------------------------------------------
# SSOT：複製自 anchors.js（ANCHORS_RAW + SHRINK 計算）
# 與 test_constellation_anchors.py 同步
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
    ('#09', 845, 555),
    ('#10', 100, 130),
    ('#11', 900, 360),
    ('#12', 865,  95),
]

CX, CY = 480, 310
SHRINK = 0.92

ANCHORS_PY = [
    (id_, round(CX + (x - CX) * SHRINK), round(CY + (y - CY) * SHRINK))
    for id_, x, y in ANCHORS_RAW_PY
]

# Build dict for O(1) lookup: id -> (x, y)
ANCHOR_MAP = {id_: (x, y) for id_, x, y in ANCHORS_PY}
ALL_IDS = [a[0] for a in ANCHORS_PY]


# ---------------------------------------------------------------------------
# Python re-implementation of nearestNeighbors（mirrors anchors.js export）
# ---------------------------------------------------------------------------
def nearest_neighbors_py(slot_id, candidate_ids, k=3):
    """
    Pure Python re-implementation of nearestNeighbors from anchors.js.

    - Looks up slot_id in ANCHOR_MAP; returns [] if not found.
    - Filters out slot_id from candidate_ids.
    - Skips candidates not in ANCHOR_MAP (filter(Boolean) equivalent).
    - Sorts remaining by Euclidean distance ascending.
    - Returns first k ids (or all if fewer than k available).
    """
    if slot_id not in ANCHOR_MAP:
        return []

    sx, sy = ANCHOR_MAP[slot_id]

    # Build (distance, id) list — filter out self + unknown ids
    dist_pairs = []
    for cid in candidate_ids:
        if cid == slot_id:
            continue
        if cid not in ANCHOR_MAP:
            continue
        cx, cy = ANCHOR_MAP[cid]
        dist = math.hypot(cx - sx, cy - sy)
        dist_pairs.append((dist, cid))

    dist_pairs.sort(key=lambda p: p[0])
    return [cid for _, cid in dist_pairs[:k]]


# ---------------------------------------------------------------------------
# TestNearestNeighbors
# ---------------------------------------------------------------------------
class TestNearestNeighbors:
    """nearestNeighbors invariant — Python re-implementation"""

    def test_k3_no_self(self):
        """k=3 結果不含 slotId 本身"""
        slot_id = '#01'
        result = nearest_neighbors_py(slot_id, ALL_IDS, k=3)
        assert slot_id not in result, (
            f"Result should not contain self {slot_id}, got {result}"
        )
        assert len(result) == 3, f"Expected 3 neighbors, got {len(result)}"

    def test_k3_sorted_by_distance(self):
        """結果按距離遞增排序（前 3 名距離關係正確）"""
        slot_id = '#04'
        result = nearest_neighbors_py(slot_id, ALL_IDS, k=3)
        assert len(result) == 3

        sx, sy = ANCHOR_MAP[slot_id]
        dists = [math.hypot(ANCHOR_MAP[r][0] - sx, ANCHOR_MAP[r][1] - sy) for r in result]
        assert dists == sorted(dists), (
            f"Distances not ascending for {slot_id}: {list(zip(result, dists))}"
        )

    def test_k3_for_all_anchors(self):
        """12 顆 anchor 各為 slotId，candidateIds = 全 12，結果各為 3 個有效鄰居"""
        for slot_id in ALL_IDS:
            result = nearest_neighbors_py(slot_id, ALL_IDS, k=3)
            assert len(result) == 3, (
                f"{slot_id} expected 3 neighbors, got {len(result)}: {result}"
            )
            assert slot_id not in result, (
                f"{slot_id} result contains self: {result}"
            )
            # All returned ids must be valid anchors
            for rid in result:
                assert rid in ANCHOR_MAP, f"Unknown id {rid} in result for {slot_id}"

    def test_empty_candidates(self):
        """candidateIds = [] → 回 []"""
        result = nearest_neighbors_py('#01', [], k=3)
        assert result == [], f"Expected [], got {result}"

    def test_candidates_without_self(self):
        """candidateIds 不含 slotId → 仍能正常回傳 k 個（self-protection，不崩）"""
        slot_id = '#02'
        candidates_no_self = [id_ for id_ in ALL_IDS if id_ != slot_id]
        result = nearest_neighbors_py(slot_id, candidates_no_self, k=3)
        assert len(result) == 3, (
            f"Expected 3 neighbors even without self in candidates, got {result}"
        )
        assert slot_id not in result

    def test_k_exceeds_candidates(self):
        """k > 有效 candidates 數量時，回全部有效 candidates（不報錯，不崩）
        candidateIds = 只有 3 個，k=10 → 回全部 3 個"""
        slot_id = '#06'
        # Use a small candidate set where k=10 clearly exceeds count
        small_candidates = ['#01', '#02', '#06']  # self + 2 others
        result = nearest_neighbors_py(slot_id, small_candidates, k=10)
        # After excluding self (#06), 2 valid candidates remain; k=10 > 2, return all 2
        assert len(result) == 2, (
            f"Expected 2 (all valid candidates after excluding self), got {len(result)}: {result}"
        )
        assert slot_id not in result

    def test_unknown_slot_returns_empty(self):
        """slotId 不在 ANCHORS → 回 []"""
        result = nearest_neighbors_py('#99', ALL_IDS, k=3)
        assert result == [], f"Expected [] for unknown slot, got {result}"
