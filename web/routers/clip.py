"""
web/routers/clip.py
GET /api/similar-covers 端點（T6）。

兩個端點：
- GET /api/similar-covers/by-number/{number}  ← 必須在前（防路由衝突）
- GET /api/similar-covers/{video_id}

狀態拆分（三個 property，修正 P2-1）：
  is_enabled == False → 503「CLIP 索引尚未準備好」
  query video 無 embedding / 不存在 → 404「找不到影片或尚未建立索引」
  model_id 不一致 → 422「CLIP 索引模型不一致，請至設定重建索引」
  model_available == False（matrix 空）→ 200 + results: []
  session_loaded == False + model_available == True → 200（防回歸 P2-1）
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query

from core.clip import get_provider
from core.clip.ranking import apply_diversity_penalty
from core.database import VideoRepository, get_db_path
from core.logger import get_logger
from core.path_utils import uri_to_fs_path

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["clip"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_cover_url(cover_path: str) -> str:
    """file:/// URI → /api/gallery/image?path=<URL-encoded local FS path>。

    沿用 web/routers/showcase.py:26-29 既有 pattern。uri_to_fs_path 已封裝
    file:/// URI 偵測（path_utils.py:376-392），呼叫端零 startswith / 零手動 strip /
    零手動 file:/// 構造，符合 CLAUDE.md P0 路徑規則。

    邊界：cover_path 為空字串 / None → 回傳空字串（對齊 showcase.py:26-29）。
    """
    if not cover_path:
        return ""
    local_path = uri_to_fs_path(cover_path)
    return f"/api/gallery/image?path={quote(local_path, safe='')}"


# ---------------------------------------------------------------------------
# Shared logic
# ---------------------------------------------------------------------------

async def _compute_similar_covers(
    video_id: int,
    limit: int,
) -> dict:
    """主查詢邏輯，by integer video_id。

    Returns a dict matching the API response schema.
    Raises HTTPException on error states.
    """
    provider = get_provider()

    # State 1：is_enabled == False → 503
    if not provider.is_enabled:
        raise HTTPException(status_code=503, detail="CLIP 索引尚未準備好")

    # 取得 query video
    repo = VideoRepository()
    video = repo.get_by_id(video_id)

    if video is None or video.clip_embedding is None:
        raise HTTPException(status_code=404, detail="找不到影片或尚未建立索引")

    # State 3：model_id 不一致 → 422
    if video.clip_model_id != provider.model_id:
        raise HTTPException(status_code=422, detail="CLIP 索引模型不一致，請至設定重建索引")

    # 主動觸發 matrix 懶載入，確保 model_available 反映最新狀態
    provider.ensure_matrix_loaded(Path(get_db_path()))

    # State 4：model_available == False → 200 + empty results
    # （相似查詢不需要 session_loaded，防回歸 P2-1）
    if not provider.model_available:
        return {
            "video_id": video_id,
            "model_id": provider.model_id,
            "query_video": {
                "video_id": video.id,
                "number": video.number,
                "title": video.title,
                "cover_url": _build_cover_url(video.cover_path),
            },
            "results": [],
        }

    # Compute cosine similarity
    import numpy as np  # noqa: PLC0415 — lazy import（onnxruntime optional）

    try:
        query_embedding = np.frombuffer(video.clip_embedding, dtype="<f4")
    except Exception:
        logger.exception("Failed to deserialize clip_embedding for video_id=%d", video_id)
        raise HTTPException(status_code=404, detail="找不到影片或尚未建立索引")

    db_path = get_db_path()

    try:
        raw_results = await provider.compute_similar(
            query_embedding=query_embedding,
            limit=limit,
            query_video_id=video_id,
            db_path=db_path,
        )
    except Exception:
        logger.exception("compute_similar failed for video_id=%d", video_id)
        raise HTTPException(status_code=503, detail="CLIP 索引尚未準備好")

    if not raw_results:
        return {
            "video_id": video_id,
            "model_id": provider.model_id,
            "query_video": {
                "video_id": video.id,
                "number": video.number,
                "title": video.title,
                "cover_url": _build_cover_url(video.cover_path),
            },
            "results": [],
        }

    # 取得候選 video 詳情（for diversity penalty + response enrichment）
    candidate_ids = [r["video_id"] for r in raw_results]
    raw_scores = [r["cosine_score"] for r in raw_results]

    # 批次取候選影片資訊（codex P2 fix：bulk WHERE id IN，取代 N+1 per-id 查詢；
    # compute_similar 不截取，candidate_ids 為全 DB 候選，~2000+ 部時影響顯著）
    candidate_videos = repo.get_by_ids(candidate_ids)

    # 建立 video_actresses_map 供 diversity penalty 使用
    video_actresses_map: dict[int, list[str]] = {}
    for cid, v in candidate_videos.items():
        # v.actresses 已由 from_row 解析為 list[str]
        if isinstance(v.actresses, list):
            video_actresses_map[cid] = v.actresses
        else:
            # fallback：嘗試 JSON 解析（防守）
            try:
                video_actresses_map[cid] = json.loads(v.actresses) if v.actresses else []
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse actresses for video_id=%d", cid)
                video_actresses_map[cid] = []

    # target actresses
    target_actresses: list[str] = video.actresses if isinstance(video.actresses, list) else []

    # 套用 diversity penalty
    penalized = apply_diversity_penalty(
        scores=raw_scores,
        candidate_ids=candidate_ids,
        target_actresses=target_actresses,
        video_actresses_map=video_actresses_map,
    )

    # 截取 limit 筆（diversity penalty 後再截，確保 pool 夠大）
    penalized = penalized[:limit]

    # 組裝回傳結果
    results = []
    for item in penalized:
        cid = item["video_id"]
        v = candidate_videos.get(cid)
        if v is None:
            continue  # 候選影片已從 DB 刪除，略過
        actresses_list: list[str] = v.actresses if isinstance(v.actresses, list) else []
        results.append({
            "video_id": cid,
            "number": v.number,
            "title": v.title,
            "cover_path": v.cover_path,  # file:/// URI 格式，直接從 DB 取出不轉換（向後相容）
            "cover_url": _build_cover_url(v.cover_path),  # /api/gallery/image?path=...
            "cosine_score": item["cosine_score"],
            "penalty_applied": item["penalty_applied"],
            "actresses": actresses_list,
        })

    return {
        "video_id": video_id,
        "model_id": provider.model_id,
        "query_video": {
            "video_id": video.id,
            "number": video.number,
            "title": video.title,
            "cover_url": _build_cover_url(video.cover_path),
        },
        "results": results,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

# ⚠️ by-number 端點必須定義在 {video_id} 之前，防止 FastAPI 將 "by-number" 當成 video_id 路徑參數
@router.get("/similar-covers/by-number/{number}")
async def get_similar_covers_by_number(
    number: str,
    limit: int = Query(default=12, ge=1, le=50),
):
    """GET /api/similar-covers/by-number/{number}

    輔助端點，by 番號（大小寫不敏感）。
    內部取得 video_id 後委派給主端點邏輯，不重複實作 cosine。
    """
    provider = get_provider()

    # State 1：is_enabled 先檢查（與主端點一致）
    if not provider.is_enabled:
        raise HTTPException(status_code=503, detail="CLIP 索引尚未準備好")

    repo = VideoRepository()
    video = repo.get_by_number(number)

    if video is None:
        raise HTTPException(status_code=404, detail="找不到影片或尚未建立索引")

    # 委派給主端點邏輯（共用 is_enabled check 後的邏輯）
    return await _compute_similar_covers(video.id, limit)


@router.get("/similar-covers/{video_id}")
async def get_similar_covers(
    video_id: int,
    limit: int = Query(default=12, ge=1, le=50),
):
    """GET /api/similar-covers/{video_id}

    主端點，by integer DB id。
    回傳格式含 model_id、cosine_score、penalty_applied、actresses。
    """
    return await _compute_similar_covers(video_id, limit)
