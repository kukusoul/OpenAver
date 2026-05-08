"""
web/routers/clip_lifecycle.py
CLIP feature lifecycle endpoints: enable (SSE), disable, status, test-inference.

CD-56D-11-C: enable job runs as module-level asyncio.Task（_run_enable_job），
独立 request lifecycle；progress_cb 直接寫 _clip_status singleton。
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.clip import get_provider
from core.clip import _DEFAULT_MODEL_PATH
from core.clip.downloader import ensure_model_downloaded_streaming
from core.clip.indexer import ClipIndexer
from core.config import load_config, save_config
from core.database import VideoRepository, get_db_path
from core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/clip", tags=["clip-lifecycle"])

# ---------------------------------------------------------------------------
# Module-level status singleton（跨 request 共用）
# ---------------------------------------------------------------------------

_clip_status: dict = {
    "phase": "idle",
    "download_bytes": 0,
    "download_total": 0,
    "index_done": 0,
    "index_total": 0,
    "error_message": "",
}
_clip_status_lock = threading.Lock()  # progress_cb 可能在 to_thread 內被呼叫


def _set_status(**kwargs) -> None:
    with _clip_status_lock:
        _clip_status.update(kwargs)


def _get_status_snapshot() -> dict:
    with _clip_status_lock:
        return dict(_clip_status)


# ---------------------------------------------------------------------------
# Enable task management
# ---------------------------------------------------------------------------

_enable_task: asyncio.Task | None = None
_enable_task_lock = asyncio.Lock()  # 搶 task 是 async context

# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

# ---------------------------------------------------------------------------
# Test image path（test-inference endpoint 用）
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_IMAGE_PATH = PROJECT_ROOT / "web" / "static" / "img" / "demo" / "sone-103.jpg"

# ---------------------------------------------------------------------------
# Background enable job（CD-56D-11-C）
# ---------------------------------------------------------------------------

async def _run_enable_job(model_path: Path) -> None:
    """獨立於 request lifecycle 的 background job。直接寫 _clip_status。

    config 寫入時序：enabled=True **延後到索引成功後**才寫，避免「下載成功但索引前段
    拋錯」時 config 卡 enabled=True / status=error 的不一致狀態。
    """
    try:
        # 階段 1: 下載（phase 已在 POST /enable 中 pre-set 為 downloading）
        def download_progress_cb(done: int, total: int) -> None:
            _set_status(download_bytes=done, download_total=total)

        await asyncio.to_thread(
            ensure_model_downloaded_streaming,
            model_path,
            progress_cb=download_progress_cb,
        )

        # 階段 2: provider + index（先 index，後寫 config enabled=True）
        provider = get_provider(model_path)
        _set_status(phase="indexing", index_done=0, index_total=0)

        def index_progress_cb(done: int, total: int) -> None:
            _set_status(index_done=done, index_total=total)

        repo = VideoRepository()
        indexer = ClipIndexer(provider, repo, db_path=Path(get_db_path()))
        await indexer.run_batch(progress_cb=index_progress_cb)

        # 階段 3: 索引成功後才寫 config（commit 啟用結果）
        cfg = load_config()
        cfg.setdefault("clip", {})["enabled"] = True
        cfg.setdefault("clip", {})["model_path"] = str(model_path)
        save_config(cfg)

        # 階段 4: ready
        _set_status(phase="ready")

    except Exception:
        # 失敗路徑：config 從沒寫過 enabled=True，不需要 rollback
        logger.exception("Enable job failed")
        _set_status(phase="error", error_message="啟用失敗，請查閱日誌")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_clip_status():
    """回傳當前 status 快照，給跨頁返回還原 UI 用。"""
    return _get_status_snapshot()


@router.post("/enable")
async def enable_clip():
    """啟動 enable job（若已在跑就 reject）+ return SSE 觀察 _clip_status。

    CD-56D-11-C：
    - 在 create_task 之前先 _set_status(phase="downloading")，避免 observer 讀到 stale idle。
    - SSE 終態：("ready", "error")；idle 不算終態。
    """
    global _enable_task

    async with _enable_task_lock:
        if _enable_task is not None and not _enable_task.done():
            raise HTTPException(status_code=409, detail="啟用流程已在進行中")

        # ⚠️ 必須在 create_task 之前 set phase="downloading"，避免 observer race
        _set_status(
            phase="downloading",
            download_bytes=0,
            download_total=0,
            index_done=0,
            index_total=0,
            error_message="",
        )
        _enable_task = asyncio.create_task(_run_enable_job(_DEFAULT_MODEL_PATH))

    async def event_stream():
        # SSE 純觀察者：每 0.5s 推一次當前 _clip_status；終態（ready/error）後關閉。
        # 注意：'idle' 不算終態（避免新 enable request 第一輪讀到 stale idle 立刻 break）
        last_snapshot = None
        while True:
            snapshot = _get_status_snapshot()
            if snapshot != last_snapshot:
                yield _sse({"type": "status", **snapshot})
                last_snapshot = snapshot
            if snapshot["phase"] in ("ready", "error"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/disable")
async def disable_clip():
    """關閉以圖搜圖：刪 .onnx + 清 embedding + reset provider.

    若 enable job 進行中（download/indexing），回 409 並請使用者等流程結束。

    CD-56D-5 / Codex-56D-P1 修正後六階段：
    0. 搶鎖 + 檢查 enable 是否在跑
    1. 讀取 config（先讀，尚未寫 disabled）
    2. 清空 DB embedding 欄位（不可逆操作先做）
    3. Reset provider singleton（in-memory，不 raise）
    4. 刪 .onnx 檔
    5. 寫 config enabled=False（最後才標 disabled）
    6. Reset status singleton（in-memory，不 raise）

    階段順序設計原則：先做不可逆破壞性操作，最後寫 config，
    避免「config 已標 disabled 但 embedding 仍殘留」的不一致狀態。
    所有 I/O 操作包 try/except，detail 固定中文不洩漏 str(exc)。
    """
    global _enable_task

    # ── 階段 0：搶鎖 + 檢查 enable 是否在跑 ──────────────────────
    # 為何 409 而非 cancel：enable 的 download phase 跑在 asyncio.to_thread 內；
    # asyncio.cancel() 只 cancel awaiter，底層 thread 不會停。
    async with _enable_task_lock:
        if _enable_task is not None and not _enable_task.done():
            raise HTTPException(
                status_code=409,
                detail="啟用流程進行中，請待完成後再關閉",
            )

        # ── 階段 1：讀取 config（此時尚未寫 disabled）────────────
        try:
            cfg = load_config()  # plain dict（core/config.py:138）
        except Exception:
            logger.exception("disable_clip: load_config failed")
            raise HTTPException(status_code=500, detail="讀取設定失敗，請查閱日誌")

        # ── 階段 2：清空 DB embedding 欄位（不可逆，先做）─────────
        try:
            repo = VideoRepository()
            cleared = repo.clear_all_clip_embeddings()
            logger.info("CLIP disable: cleared %d embedding rows", cleared)
        except Exception:
            logger.exception("disable_clip: clear_all_clip_embeddings failed")
            raise HTTPException(status_code=500, detail="清除 CLIP 索引失敗，請查閱日誌")

        # ── 階段 3：Reset provider singleton（in-memory，不 raise）─
        import core.clip
        if core.clip._provider is not None:
            core.clip._provider = None

        # ── 階段 4：刪 .onnx 檔 ────────────────────────────────────
        model_path = Path(_DEFAULT_MODEL_PATH)
        if model_path.exists():
            try:
                model_path.unlink()
                logger.info("Deleted CLIP model file: %s", model_path)
            except Exception:
                logger.exception("Failed to delete CLIP model file")
                raise HTTPException(status_code=500, detail="刪除模型檔失敗，請查閱日誌")

        # ── 階段 5：寫 config enabled=False（最後才標 disabled）────
        try:
            cfg.setdefault("clip", {})["enabled"] = False
            save_config(cfg)
        except Exception:
            logger.exception("disable_clip: save_config failed")
            raise HTTPException(status_code=500, detail="儲存設定失敗，請查閱日誌")

        # ── 階段 6：Reset status singleton（in-memory，不 raise）───
        _set_status(
            phase="idle",
            download_bytes=0,
            download_total=0,
            index_done=0,
            index_total=0,
            error_message="",
        )

    return {"success": True, "cleared_embeddings": cleared}


@router.post("/test-inference")
async def test_clip_inference():
    """測試推論：固定讀馬賽克測試圖 → embed → 回傳耗時 ms.

    CD-56D-7：所有 except → logger.exception + 固定中文 detail，不 leak str(exc)。
    """
    provider = get_provider()
    if not provider.is_enabled:
        raise HTTPException(status_code=503, detail="CLIP 索引尚未準備好")

    if not TEST_IMAGE_PATH.exists():
        raise HTTPException(status_code=500, detail="測試圖不存在")

    image_bytes = TEST_IMAGE_PATH.read_bytes()
    t0 = time.perf_counter()
    try:
        embedding = await provider.embed(image_bytes)
    except Exception:
        # CD-56D-7 / AGENTS.md 安全規則：不洩漏 str(exc) 到前端
        logger.exception("test_inference embed failed")
        raise HTTPException(status_code=500, detail="推論失敗，請查閱日誌")
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "success": True,
        "elapsed_ms": elapsed_ms,
        "embedding_dim": int(embedding.shape[0]),
    }
