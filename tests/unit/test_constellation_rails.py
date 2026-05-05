"""
test_constellation_rails.py — railRole 四態邏輯（pure Python re-implementation）
CD-56B-3：railRole(slotId, prevVisible, nextVisible) → 'persist'|'enter'|'exit'|'absent'
"""


# ---------------------------------------------------------------------------
# Python re-implementation of railRole (mirrors CD-56B-3 JS logic)
# ---------------------------------------------------------------------------
def rail_role_py(slot_id, prev_visible, next_visible):
    """
    Pure function, no side effects.
    prev_visible / next_visible: frozenset or set of slot ids
    """
    in_prev = slot_id in prev_visible
    in_next = slot_id in next_visible
    if in_prev and in_next:
        return 'persist'
    if not in_prev and in_next:
        return 'enter'
    if in_prev and not in_next:
        return 'exit'
    return 'absent'


# ---------------------------------------------------------------------------
# TestRailRole
# ---------------------------------------------------------------------------
class TestRailRole:
    PREV = frozenset(['#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08'])
    NEXT = frozenset(['#02', '#03', '#05', '#07', '#09', '#10', '#11', '#12'])

    def test_persist(self):
        """inPrev=True, inNext=True → 'persist'"""
        # #02 is in both PREV and NEXT
        result = rail_role_py('#02', self.PREV, self.NEXT)
        assert result == 'persist', f"Expected 'persist', got '{result}'"

    def test_enter(self):
        """inPrev=False, inNext=True → 'enter'"""
        # #09 is in NEXT but not PREV
        result = rail_role_py('#09', self.PREV, self.NEXT)
        assert result == 'enter', f"Expected 'enter', got '{result}'"

    def test_exit(self):
        """inPrev=True, inNext=False → 'exit'"""
        # #01 is in PREV but not NEXT
        result = rail_role_py('#01', self.PREV, self.NEXT)
        assert result == 'exit', f"Expected 'exit', got '{result}'"

    def test_absent(self):
        """inPrev=False, inNext=False → 'absent'"""
        # #08 is ONLY in PREV and not NEXT; we need a slot in neither
        # Let's use a slot not in either set
        # PREV = #01-#08, NEXT = #02,#03,#05,#07,#09-#12
        # #08 in PREV, not NEXT → 'exit' (not absent)
        # Let's create explicit sets for this test
        prev = frozenset(['#01', '#02'])
        next_ = frozenset(['#03', '#04'])
        result = rail_role_py('#05', prev, next_)
        assert result == 'absent', f"Expected 'absent', got '{result}'"

    def test_clicked_slot_treated_as_exit(self):
        """Clicked slot（被點 → 不在 nextVisible）→ railRole = 'exit'（rail fade）"""
        # clicked slot: was in prevVisible, NOT in nextVisible (because excluded by pickEight)
        clicked = '#03'
        prev = frozenset(['#01', '#02', '#03', '#04', '#05', '#06', '#07', '#08'])
        next_ = frozenset(['#02', '#04', '#05', '#06', '#09', '#10', '#11', '#12'])  # no #03
        result = rail_role_py(clicked, prev, next_)
        assert result == 'exit', (
            f"Clicked slot {clicked} should have role 'exit' (not persist/enter/absent), "
            f"got '{result}'"
        )
