#!/usr/bin/env python3
"""
scripts/clip_index.py
Dev trigger：以 CLI 觸發 CLIP 批次索引（56a 專用）。

用法：
    source venv/bin/activate
    python scripts/clip_index.py           # 完整索引
    python scripts/clip_index.py --dry-run # 只列出待索引數量，不寫 DB
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

# 確保 project root 在 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.clip import get_provider
from core.clip.downloader import ensure_model_downloaded, ModelDownloadError
from core.clip.indexer import ClipIndexer
from core.database import VideoRepository, init_db, get_db_path
from core.logger import get_logger

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="CLIP 批次索引 Dev Trigger")
    parser.add_argument("--dry-run", action="store_true", help="只列出待索引數量，不下載模型、不寫 DB")
    return parser.parse_args()


def print_progress(done: int, total: int) -> None:
    pct = done * 100 // total
    bar = "=" * (pct // 2) + " " * (50 - pct // 2)
    print(f"\r[{bar}] {done}/{total} ({pct}%)", end="", flush=True)


async def main():
    args = parse_args()
    db_path = get_db_path()

    if args.dry_run:
        init_db(db_path)
        repo = VideoRepository(db_path)
        # 用預設 model_id 列出 pending
        from core.clip.provider import LocalONNXProvider
        pending = repo.get_videos_pending_clip_indexing(LocalONNXProvider.MODEL_ID)
        print(f"待索引影片數：{len(pending)}")
        return

    # 1. 確保模型已下載
    model_path = Path("output/models/clip/vision_model_quantized.onnx")
    print("檢查 CLIP 模型…")
    try:
        ensure_model_downloaded(model_path)
        print(f"模型就緒：{model_path}")
    except ModelDownloadError as e:
        print(f"模型下載失敗：{e}")
        sys.exit(1)

    # 2. 初始化 DB + Provider + Indexer
    init_db(db_path)
    repo = VideoRepository(db_path)
    provider = get_provider(model_path)
    indexer = ClipIndexer(provider=provider, video_repo=repo)

    # 3. 執行批次索引
    print("開始建立 CLIP 索引…")
    start = time.perf_counter()
    result = await indexer.run_batch(progress_cb=print_progress)
    elapsed = time.perf_counter() - start

    print()  # 換行（progress bar 結尾）
    print(f"完成：indexed={result['indexed']}  skipped={result['skipped']}  errors={result['errors']}")
    print(f"耗時：{elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
