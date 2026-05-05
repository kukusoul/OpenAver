"""
test_constellation_state.py — host state machine invariant
模擬 Alpine constellationLab host 連續 onCardClick 10 次，驗 visibleSlots 一致性
CD-56B-2 / DoD 12
"""
import random

# ---------------------------------------------------------------------------
# Copy of pickEight logic (same as test_constellation_anchors.py — must stay in sync)
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

ANCHOR_IDS = [a[0] for a in ANCHORS_PY]


def sample_n_py(candidates, n, rng):
    lst = list(candidates)
    result = []
    for i in range(min(n, len(lst))):
        j = i + int(rng() * (len(lst) - i))
        lst[i], lst[j] = lst[j], lst[i]
        result.append(lst[i])
    return result


def pick_eight_py(exclude_slot_id, prev_visible, rng):
    carry_candidates = [id_ for id_ in ANCHOR_IDS
                        if id_ in prev_visible and id_ != exclude_slot_id]
    fresh_candidates = [id_ for id_ in ANCHOR_IDS
                        if id_ not in prev_visible and id_ != exclude_slot_id]

    C = 4 + int(rng() * 3)
    F = 8 - C

    actual_c = min(C, len(carry_candidates))
    actual_f = min(F, len(fresh_candidates))

    chosen = (
        sample_n_py(carry_candidates, actual_c, rng) +
        sample_n_py(fresh_candidates, actual_f, rng)
    )

    if len(chosen) < 8:
        remaining = [id_ for id_ in ANCHOR_IDS
                     if id_ not in chosen and id_ != exclude_slot_id]
        needed = 8 - len(chosen)
        chosen += sample_n_py(remaining, needed, rng)

    return frozenset(chosen[:8])


# ---------------------------------------------------------------------------
# Minimal host state machine simulation (mirrors Alpine constellationLab)
# ---------------------------------------------------------------------------
class ConstellationLabHost:
    """
    Pure Python simulation of the Alpine constellationLab component state.
    Does NOT build timelines — only models state transitions.
    """

    def __init__(self, rng=None):
        self.animating = False
        self.visible_slots = frozenset()
        self.main_slot = None
        self._rng = rng or random.random
        self._last_next_visible = None  # store what was passed to animation

    def init(self):
        """Simulate init() — set initial 8 slots and mark not animating."""
        init_slots = frozenset(['#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08'])
        self.visible_slots = init_slots
        self.animating = False

    def on_card_click(self, slot_id):
        """
        Simulate onCardClick:
        1. Guard check (animating or slot not visible → return early)
        2. host picks nextVisible via pickEight
        3. Sets animating = True
        4. Immediately calls onComplete (simulating timeline finishing)
        5. onComplete: updates visibleSlots = nextVisible, animating = False
        Returns nextVisible so test can verify.
        """
        if self.animating or slot_id not in self.visible_slots:
            return None

        # host calculates nextVisible BEFORE passing to animation
        next_visible = pick_eight_py(slot_id, self.visible_slots, self._rng)
        self._last_next_visible = next_visible

        self.animating = True

        # Simulate onComplete callback (timeline finished)
        self._on_complete(slot_id, next_visible)

        return next_visible

    def _on_complete(self, clicked_id, next_visible):
        """onComplete callback from playSlipThrough."""
        self.main_slot = clicked_id
        self.visible_slots = next_visible  # must equal animation's nextVisible
        self.animating = False


# ---------------------------------------------------------------------------
# TestConstellationStateMachine
# ---------------------------------------------------------------------------
class TestConstellationStateMachine:

    def test_continuous_10_clicks_state_invariant(self):
        """
        連續模擬 10 次 onCardClick，每次 onComplete 後驗：
        1. visibleSlots == nextVisible（animation 使用的批次）
        2. clicked slot ∉ nextVisible
        3. len(visibleSlots) == 8
        """
        rng = random.Random(42).random
        host = ConstellationLabHost(rng=rng)
        host.init()

        for click_num in range(10):
            # Pick a visible slot to click
            visible_list = sorted(host.visible_slots)  # deterministic
            # Click the first visible slot for determinism
            clicked_id = visible_list[0]

            next_visible = host.on_card_click(clicked_id)

            assert next_visible is not None, (
                f"Click {click_num + 1}: on_card_click returned None (animating guard triggered unexpectedly)"
            )

            # 1. visibleSlots == nextVisible after onComplete
            assert host.visible_slots == next_visible, (
                f"Click {click_num + 1}: visibleSlots {host.visible_slots} != "
                f"nextVisible {next_visible}"
            )

            # 2. clicked slot not in nextVisible
            assert clicked_id not in next_visible, (
                f"Click {click_num + 1}: clicked slot {clicked_id} is in nextVisible {next_visible}"
            )

            # 3. len == 8
            assert len(host.visible_slots) == 8, (
                f"Click {click_num + 1}: visibleSlots size {len(host.visible_slots)} != 8"
            )
