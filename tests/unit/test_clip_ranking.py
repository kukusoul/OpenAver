"""
tests/unit/test_clip_ranking.py
TDD-lite unit tests for core/clip/ranking.py — apply_diversity_penalty().
"""
import pytest


class TestDiversityPenaltyConstant:
    def test_constant_exists_and_is_float(self):
        from core.clip.ranking import DIVERSITY_PENALTY
        assert isinstance(DIVERSITY_PENALTY, float)

    def test_constant_is_positive(self):
        """CD-56A-7 符號警告：DIVERSITY_PENALTY 必須是正數，score -= DIVERSITY_PENALTY 才能扣分"""
        from core.clip.ranking import DIVERSITY_PENALTY
        assert DIVERSITY_PENALTY > 0, "DIVERSITY_PENALTY 必須是正數（0.15），負數會導致加分（符號 bug）"

    def test_constant_value(self):
        from core.clip.ranking import DIVERSITY_PENALTY
        assert DIVERSITY_PENALTY == pytest.approx(0.15)


class TestApplyDiversityPenalty:
    def test_no_overlap_no_penalty(self):
        """無共同女優的候選不被扣分"""
        from core.clip.ranking import apply_diversity_penalty

        scores = [0.9, 0.8]
        candidate_ids = [1, 2]
        target_actresses = ["Alice"]
        video_actresses_map = {
            1: ["Bob"],
            2: ["Carol"],
        }

        results = apply_diversity_penalty(scores, candidate_ids, target_actresses, video_actresses_map)

        assert len(results) == 2
        for r in results:
            assert r["penalty_applied"] is False

    def test_overlap_applies_penalty(self):
        """有共同女優的候選被扣分，final_score 嚴格小於 raw_score"""
        from core.clip.ranking import apply_diversity_penalty, DIVERSITY_PENALTY

        raw_score = 0.85
        scores = [raw_score]
        candidate_ids = [10]
        target_actresses = ["Alice"]
        video_actresses_map = {10: ["Alice", "Bob"]}

        results = apply_diversity_penalty(scores, candidate_ids, target_actresses, video_actresses_map)

        assert len(results) == 1
        r = results[0]
        assert r["penalty_applied"] is True
        assert r["cosine_score"] < raw_score  # 確保確實被扣分（CD-56A-7 符號防回歸）
        assert r["cosine_score"] == pytest.approx(raw_score - DIVERSITY_PENALTY)

    def test_partial_overlap_mixed(self):
        """混合情況：有交集的被扣分，無交集的不扣"""
        from core.clip.ranking import apply_diversity_penalty, DIVERSITY_PENALTY

        scores = [0.9, 0.85, 0.8]
        candidate_ids = [1, 2, 3]
        target_actresses = ["Alice"]
        video_actresses_map = {
            1: ["Alice"],   # 有交集 → penalty
            2: ["Bob"],     # 無交集 → no penalty
            3: ["Alice", "Carol"],  # 有交集 → penalty
        }

        results = apply_diversity_penalty(scores, candidate_ids, target_actresses, video_actresses_map)

        result_map = {r["video_id"]: r for r in results}
        assert result_map[1]["penalty_applied"] is True
        assert result_map[2]["penalty_applied"] is False
        assert result_map[3]["penalty_applied"] is True

    def test_sorted_by_final_score(self):
        """結果按 final_score 降序排序，同女優降權後可能改變排名"""
        from core.clip.ranking import apply_diversity_penalty, DIVERSITY_PENALTY

        # candidate 1 raw=0.9 但有交集 → 0.9 - 0.15 = 0.75
        # candidate 2 raw=0.8 無交集 → 0.8
        # 排序後：candidate 2 (0.8) > candidate 1 (0.75)
        scores = [0.9, 0.8]
        candidate_ids = [1, 2]
        target_actresses = ["Alice"]
        video_actresses_map = {
            1: ["Alice"],
            2: ["Bob"],
        }

        results = apply_diversity_penalty(scores, candidate_ids, target_actresses, video_actresses_map)

        assert results[0]["video_id"] == 2   # 降權後 2 > 1
        assert results[1]["video_id"] == 1

    def test_empty_target_actresses_no_penalty(self):
        """target 無女優資訊，無候選被扣分"""
        from core.clip.ranking import apply_diversity_penalty

        results = apply_diversity_penalty(
            scores=[0.9],
            candidate_ids=[1],
            target_actresses=[],
            video_actresses_map={1: ["Alice"]},
        )
        assert results[0]["penalty_applied"] is False

    def test_candidate_missing_from_map(self):
        """候選不在 video_actresses_map → 視為空 actresses，不扣分"""
        from core.clip.ranking import apply_diversity_penalty

        results = apply_diversity_penalty(
            scores=[0.9],
            candidate_ids=[999],
            target_actresses=["Alice"],
            video_actresses_map={},  # 999 不在 map
        )
        assert results[0]["penalty_applied"] is False

    def test_cosine_score_rounded(self):
        """cosine_score 四捨五入到 6 位小數"""
        from core.clip.ranking import apply_diversity_penalty

        results = apply_diversity_penalty(
            scores=[1 / 3],
            candidate_ids=[1],
            target_actresses=[],
            video_actresses_map={},
        )
        val = results[0]["cosine_score"]
        assert val == round(1 / 3, 6)

    def test_result_contains_required_fields(self):
        """每個 result 必須有 video_id、cosine_score、penalty_applied 欄位"""
        from core.clip.ranking import apply_diversity_penalty

        results = apply_diversity_penalty(
            scores=[0.7],
            candidate_ids=[42],
            target_actresses=[],
            video_actresses_map={},
        )
        r = results[0]
        assert "video_id" in r
        assert "cosine_score" in r
        assert "penalty_applied" in r
        assert r["video_id"] == 42
