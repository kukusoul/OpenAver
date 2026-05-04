"""
core/clip/indexer.py
ClipIndexer: batch CLIP embedding runner with resume-after-interrupt support.

Pipeline per video:
  cover_path (file:/// URI)
    → uri_to_fs_path()           → fs_path (str)
    → Path.read_bytes()          → image_bytes (bytes)
    → preprocess_image()         → tensor (1, 3, 224, 224) float32 ndarray
    → await provider.embed()     → embedding (512,) float32 ndarray
    → astype('<f4').tobytes()    → blob (bytes)
    → repo.update_clip_embedding()

Resume-after-interrupt:
  get_videos_pending_clip_indexing() only returns videos with NULL embedding,
  so re-running after a crash naturally skips already-indexed videos.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from core.logger import get_logger
from core.path_utils import uri_to_fs_path
from core.clip.preprocessing import preprocess_image
from core.clip.provider import CLIPProvider
from core.database import VideoRepository

logger = get_logger(__name__)


class ClipIndexer:
    """Batch CLIP embedding indexer with resume-after-interrupt support."""

    def __init__(
        self,
        provider: CLIPProvider,
        video_repo: VideoRepository,
        db_path: Optional[Path] = None,
    ) -> None:
        self._provider = provider
        self._repo = video_repo

    async def run_batch(
        self,
        batch_size: int = 32,
        progress_cb: Optional[Callable[[int, int], None]] = None,
    ) -> dict:
        """Find all videos with NULL clip_embedding and index them.

        Supports resume-after-interrupt: only videos still having NULL
        embedding will be processed on subsequent calls.

        Args:
            batch_size: Currently unused (reserved for future chunked DB writes).
            progress_cb: Optional callback called as progress_cb(done, total)
                         after each video is processed.

        Returns:
            dict with keys: indexed, skipped, errors
        """
        model_id = self._provider.model_id
        pending = self._repo.get_videos_pending_clip_indexing(model_id)
        total = len(pending)

        if total == 0:
            logger.info("No videos pending CLIP indexing")
            self._provider.invalidate_matrix()
            return {"indexed": 0, "skipped": 0, "errors": 0}

        indexed = skipped = errors = 0

        for i, video in enumerate(pending):
            # ── cover_path guard ──────────────────────────────────────────
            if not video.cover_path:
                logger.warning("cover_path missing for video_id=%d", video.id)
                skipped += 1
                if progress_cb:
                    progress_cb(i + 1, total)
                continue

            # ── URI → FS path ──────────────────────────────────────────────
            try:
                fs_path = uri_to_fs_path(video.cover_path)
            except Exception as exc:
                logger.warning(
                    "invalid cover_path for video %d: %s (%s)",
                    video.id, video.cover_path, exc,
                )
                skipped += 1
                if progress_cb:
                    progress_cb(i + 1, total)
                continue

            # ── file existence guard ───────────────────────────────────────
            if not Path(fs_path).exists():
                logger.warning("cover file not found for video %d: %s", video.id, fs_path)
                skipped += 1
                if progress_cb:
                    progress_cb(i + 1, total)
                continue

            # ── read → preprocess → embed → serialize ─────────────────────
            try:
                image_bytes = Path(fs_path).read_bytes()

                # preprocess: bytes → (1, 3, 224, 224) float32 tensor
                tensor = preprocess_image(image_bytes)

                # embed: tensor → (512,) float32 embedding
                embedding = await self._provider.embed(tensor)

                # serialize (explicit little-endian, CD-56A-4)
                blob = embedding.astype('<f4').tobytes()
            except Exception as exc:
                logger.error("embed failed for video %d: %s", video.id, exc)
                errors += 1
                if progress_cb:
                    progress_cb(i + 1, total)
                continue

            # ── write to DB (retry once for DB-locked scenario) ───────────
            try:
                success = self._repo.update_clip_embedding(video.id, blob, model_id)
                if not success:
                    # retry once
                    success = self._repo.update_clip_embedding(video.id, blob, model_id)
                if not success:
                    logger.error(
                        "update_clip_embedding returned False for video %d (after retry)",
                        video.id,
                    )
                    errors += 1
                else:
                    indexed += 1
            except Exception as exc:
                logger.error(
                    "update_clip_embedding failed for video %d: %s; retrying", video.id, exc
                )
                try:
                    success = self._repo.update_clip_embedding(video.id, blob, model_id)
                    if success:
                        indexed += 1
                    else:
                        logger.error(
                            "update_clip_embedding retry also failed for video %d", video.id
                        )
                        errors += 1
                except Exception as exc2:
                    logger.error(
                        "update_clip_embedding retry raised for video %d: %s", video.id, exc2
                    )
                    errors += 1

            # ── progress logging ──────────────────────────────────────────
            if (i + 1) % 100 == 0:
                logger.info("CLIP indexing progress: %d/%d", i + 1, total)

            if progress_cb:
                progress_cb(i + 1, total)

        self._provider.invalidate_matrix()
        logger.info(
            "CLIP indexing complete: indexed=%d skipped=%d errors=%d",
            indexed, skipped, errors,
        )
        return {"indexed": indexed, "skipped": skipped, "errors": errors}
