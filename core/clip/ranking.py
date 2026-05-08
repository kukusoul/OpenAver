"""
core/clip/ranking.py
Diversity penalty logic for CLIP similar-covers results.

CD-56A-7 NOTE: DIVERSITY_PENALTY 必須是正數（0.15），
配合 score -= DIVERSITY_PENALTY 才會真的扣分。
若寫成負數，score -= -0.15 等於加分，與 spec 意圖完全相反。
"""
from __future__ import annotations

from core.logger import get_logger

logger = get_logger(__name__)

DIVERSITY_PENALTY: float = 0.15  # ⚠️ 正數常數，配合 score -= DIVERSITY_PENALTY 扣分；見 CD-56A-7
                                  # TODO: tune after 56a indexing（CD-56A-7 OQ-2）


def apply_diversity_penalty(
    scores: list[float],
    candidate_ids: list[int],
    target_actresses: list[str],
    video_actresses_map: dict[int, list[str]],  # {video_id: [actress, ...]}
) -> list[dict]:
    """套用同女優降權，回傳含 penalty_applied 欄位的 result list（已按 final_score 排序）。

    有交集者：score -= DIVERSITY_PENALTY（正數常數，代表真正的扣分）。
    回傳結果已按 cosine_score 降序排列。

    Args:
        scores: 每個候選的 raw cosine similarity 分數
        candidate_ids: 與 scores 對應的 video_id 清單
        target_actresses: 查詢影片的 actresses（set 交集基準）
        video_actresses_map: {video_id: [actress_name, ...]}

    Returns:
        按 cosine_score 降序排序的 result list，每個 dict 包含：
        - video_id: int
        - cosine_score: float（四捨五入到 6 位小數）
        - penalty_applied: bool
    """
    target_set = set(target_actresses)
    results = []

    for score, vid in zip(scores, candidate_ids):
        candidate_actresses = video_actresses_map.get(vid, [])
        has_overlap = bool(target_set & set(candidate_actresses))
        final_score = score - DIVERSITY_PENALTY if has_overlap else score
        results.append({
            "video_id": vid,
            "cosine_score": round(float(final_score), 6),
            "penalty_applied": has_overlap,
        })

    results.sort(key=lambda x: x["cosine_score"], reverse=True)
    return results
