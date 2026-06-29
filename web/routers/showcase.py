"""
Showcase API 路由 - 影片展示資料端點

端點：
- GET /api/showcase/videos        — 取得所有影片資料（供 Showcase 頁面客戶端渲染）
- GET /api/showcase/video?path=   — 取得單筆影片資料（供 T3 enrich 後刷新卡片）
"""

from urllib.parse import quote
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from core.database import VideoRepository, get_db_path, init_db
from core.path_utils import normalize_path, to_file_uri, is_path_under_dir, uri_to_fs_path
from core.logger import get_logger
from core.config import load_config

logger = get_logger(__name__)

router = APIRouter(prefix="/api/showcase", tags=["showcase"])


def _media_file_json(v) -> dict:
    return {
        "path": v.path,
        "name": Path(uri_to_fs_path(v.path)).name,
        "size": v.size_bytes or 0,
        "mtime": int(v.mtime) if v.mtime else 0,
    }


def _group_videos(videos: list) -> list[list]:
    groups: dict[str, list] = {}
    for v in videos:
        key = v.nfo_path or v.path
        groups.setdefault(key, []).append(v)

    grouped = []
    for items in groups.values():
        items.sort(key=lambda item: item.path)
        grouped.append(items)
    grouped.sort(key=lambda items: items[0].id or 0)
    return grouped


def _serialize_video(v, path_mappings: dict, enabled: bool = False, media_group: list | None = None) -> dict:
    """將 Video ORM 物件序列化為前端 JSON dict（列表端點與單筆端點共用）。

    feature/71 T4：thumbnail_cache_enabled 開關決定 cover_url 走 thumb / image 分支。
    - enabled  → cover_url 指向 T3 /api/gallery/thumb?path=<quote(v.path)>（thumb key = video path）
    - disabled → 維持現狀 /api/gallery/image?path=<quote(uri_to_fs_path(v.cover_path))>（字節不變）
    cover_full_url 恆原圖（不受 flag 影響），供 T6 燈箱 blur-up 上層淡入用。
    """
    cover_url = ""
    cover_full_url = ""
    if v.cover_path:
        original_url = f"/api/gallery/image?path={quote(uri_to_fs_path(v.cover_path), safe='')}"
        cover_full_url = original_url
        if enabled:
            cover_url = f"/api/gallery/thumb?path={quote(v.path, safe='')}"
        else:
            cover_url = original_url

    sample_urls = []
    for img_uri in (v.sample_images or []):
        local_path = uri_to_fs_path(img_uri)
        sample_urls.append(f"/api/gallery/image?path={quote(local_path, safe='')}")

    media_group = media_group or [v]
    media_files = [_media_file_json(item) for item in media_group]
    total_size = sum(item.size_bytes or 0 for item in media_group)
    latest_mtime = max((item.mtime or 0 for item in media_group), default=v.mtime or 0)

    return {
        "path": v.path,                                          # file:/// URI（開啟影片用）
        "nfo_path": v.nfo_path or '',                            # 同一 NFO 分組 key；空值表示一檔一卡
        "title": v.title,
        "original_title": v.original_title,
        "actresses": ','.join(v.actresses) if v.actresses else '',  # 逗號分隔字串
        "number": v.number or '',
        "maker": v.maker,
        "release_date": v.release_date,
        "tags": ','.join(v.tags) if v.tags else '',              # 逗號分隔字串
        "size": total_size,
        "cover_url": cover_url,                                  # enabled→thumb / disabled→image
        "cover_full_url": cover_full_url,                        # 恆原圖 /api/gallery/image?path=...（T6 燈箱）
        "mtime": int(latest_mtime) if latest_mtime else 0,       # Unix timestamp 整數
        "director": v.director or '',
        "duration": v.duration,                                  # Optional[int]，None 時前端 x-show 隱藏
        "series": v.series or '',
        "label": v.label or '',
        "sample_images": sample_urls,
        "user_tags": v.user_tags or [],              # list[str]，空時回空 list
        "has_cover": bool(v.cover_path),             # DB 初判（不做 IO）
        "has_nfo": bool(v.nfo_path) or (v.nfo_mtime or 0) > 0,    # 對齊 41a nfo_mtime 寫入契約，防禦 NULL
        "media_files": media_files,
        "media_count": len(media_files),
    }


def _get_configured_dirs(config: dict) -> tuple[set, dict]:
    """從 config 取出 configured_dir_uris 與 path_mappings（列表與單筆端點共用）"""
    gallery_config = config.get('gallery', {})
    directories = gallery_config.get('directories', [])
    path_mappings = gallery_config.get('path_mappings', {})

    configured_dir_uris: set = set()
    for d in directories:
        try:
            configured_dir_uris.add(to_file_uri(normalize_path(d), path_mappings))
        except ValueError:
            continue

    return configured_dir_uris, path_mappings


@router.get("/videos")
def get_videos():
    """取得所有影片資料（用於 Showcase 頁面客戶端渲染）"""
    try:
        db_path = get_db_path()

        # 空庫情境：資料庫檔案不存在
        if not db_path.exists():
            return JSONResponse({
                "success": True,
                "videos": [],
                "total": 0
            })

        init_db(db_path)  # 確保 schema 存在（防止半毀損 DB）
        repo = VideoRepository(db_path)

        # 只取「當前設定資料夾」底下的記錄（DB 保留全部當 cache）
        config = load_config()
        configured_dir_uris, path_mappings = _get_configured_dirs(config)

        all_videos = [v for v in repo.get_all()
                      if any(is_path_under_dir(v.path, uri) for uri in configured_dir_uris)]

        thumb_enabled = config.get('thumbnail_cache_enabled', False)
        videos_json = [
            _serialize_video(group[0], path_mappings, thumb_enabled, group)
            for group in _group_videos(all_videos)
        ]

        return JSONResponse({
            "success": True,
            "videos": videos_json,
            "total": len(videos_json)
        })

    except Exception as e:
        logger.error("取得影片資料失敗: %s", e)
        return JSONResponse({
            "success": False,
            "error": "取得影片資料失敗",
            "videos": [],
            "total": 0
        }, status_code=500)


@router.get("/video")
def get_video(path: str = Query(..., description="file:/// URI")):
    """取得單筆影片資料（用於 T3 refreshVideoData enrich 後刷新卡片）"""
    try:
        db_path = get_db_path()
        if not db_path.exists():
            return JSONResponse({"success": False, "error": "video not found"}, status_code=404)

        init_db(db_path)
        repo = VideoRepository(db_path)

        config = load_config()
        configured_dir_uris, path_mappings = _get_configured_dirs(config)

        if not any(is_path_under_dir(path, uri) for uri in configured_dir_uris):
            return JSONResponse({"success": False, "error": "video not found"}, status_code=404)

        v = repo.get_by_path(path)
        if v is None:
            return JSONResponse({"success": False, "error": "video not found"}, status_code=404)

        thumb_enabled = config.get('thumbnail_cache_enabled', False)
        all_videos = [item for item in repo.get_all()
                      if any(is_path_under_dir(item.path, uri) for uri in configured_dir_uris)]
        group_key = v.nfo_path or v.path
        media_group = [item for item in all_videos if (item.nfo_path or item.path) == group_key]
        media_group.sort(key=lambda item: item.path)
        representative = media_group[0] if media_group else v
        return JSONResponse({"success": True, "video": _serialize_video(representative, path_mappings, thumb_enabled, media_group or [v])})

    except Exception as e:
        logger.error("取得單筆影片失敗: %s", e)
        return JSONResponse({"success": False, "error": "取得影片資料失敗"}, status_code=500)


@router.delete("/video")
def delete_video(path: str = Query(..., description="file:/// URI")):
    """從收藏移除單筆影片（71-T7，CD-10 / §1.6）。

    只刪 DB row（repo.delete_by_paths，DB-only）+ 砍衍生縮圖 WebP
    （thumbnail_cache.invalidate）。**絕不 unlink 影片檔或原始封面檔。**

    刻意「無 scope guard」：issue #57 要刪的正是已移出 gallery 設定資料夾的
    stale DB row，那些 path 依定義不在任何 configured dir 下，scope guard 會
    擋掉正當用例。未知 path → delete_by_paths rowcount=0，安全 no-op。

    `def`（非 async）→ Starlette threadpool，body 內 DB / unlink 在 worker thread。
    不進 capabilities（D9）。
    """
    db_path = get_db_path()
    if not db_path.exists():
        return JSONResponse({"deleted": 0})

    init_db(db_path)
    repo = VideoRepository(db_path)

    n = repo.delete_by_paths([path])
    from core import thumbnail_cache
    thumbnail_cache.invalidate(path)

    return JSONResponse({"deleted": n})
