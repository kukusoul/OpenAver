"""
core/clip/downloader.py
Model download + sha256 verification helper (T3).

Usage:
    from core.clip.downloader import ensure_model_downloaded, ModelDownloadError
    path = ensure_model_downloaded(target_path)
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

import requests
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import (
    EntryNotFoundError,
    HfHubHTTPError,
    OfflineModeIsEnabled,
    RepositoryNotFoundError,
)

from core.logger import get_logger

logger = get_logger(__name__)


class ModelDownloadError(Exception):
    """下載或驗證模型檔失敗時拋出。"""


def _sha256_of_file(path: Path) -> str:
    """計算檔案的 sha256 hex digest。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model_downloaded(
    target_path: Path,
    repo_id: str = "Xenova/clip-vit-base-patch32",
    filename: str = "onnx/vision_model_quantized.onnx",
    expected_sha256: str | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> Path:
    """確保模型檔案已下載並通過 sha256 驗證。

    Args:
        target_path: 目標 .onnx 檔案路徑（完整路徑，含檔名）。
        repo_id: HuggingFace repo id。
        filename: repo 內的檔案路徑。
        expected_sha256: 預期的 sha256 hex digest。
            - None → 從 LocalONNXProvider.MODEL_SHA256 取得
            - 'PENDING' → 跳過驗證
            - 其他字串 → 與檔案實際 sha256 比對
        progress_cb: 可選的進度回呼，下載完成後以 1.0 呼叫。

    Returns:
        已驗證的模型檔路徑（即 target_path）。

    Raises:
        ModelDownloadError: 下載失敗或 sha256 不符。
    """
    # 1. 解析 expected_sha256（避免循環依賴：在函式體內 import）
    if expected_sha256 is None:
        from core.clip.provider import LocalONNXProvider  # noqa: PLC0415
        expected_sha256 = LocalONNXProvider.MODEL_SHA256

    # 2. 確保父目錄存在
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    skip_verify = expected_sha256 == "PENDING"

    # 3. 若檔案已存在，先驗證 sha256
    if target_path.exists():
        if skip_verify:
            logger.warning("MODEL_SHA256 is PENDING, skipping verification. Fill in real hash after OQ-1 validation.")
            return target_path

        actual = _sha256_of_file(target_path)
        if actual == expected_sha256:
            logger.info("CLIP model verified (sha256 OK): %s", target_path)
            return target_path

        # sha256 不符 → 刪除損壞檔案，重新下載
        logger.warning(
            "CLIP model sha256 mismatch (expected=%s actual=%s), 刪除後重新下載",
            expected_sha256,
            actual,
        )
        target_path.unlink()
        raise ModelDownloadError("模型檔 sha256 驗證失敗，檔案已刪除，請重新下載。")

    # 4. 下載
    logger.info("正在下載 CLIP 模型 %s/%s …", repo_id, filename)
    try:
        downloaded = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(target_path.parent),
        )
    except (
        requests.ConnectionError,
        requests.Timeout,
    ):
        raise ModelDownloadError("無法連線至 HuggingFace Hub，請檢查網路連線後再試。")
    except HfHubHTTPError:
        raise ModelDownloadError("HuggingFace Hub 回傳 HTTP 錯誤，請稍後再試。")
    except RepositoryNotFoundError:
        raise ModelDownloadError("找不到指定的 HuggingFace 模型倉庫，請確認 repo_id 是否正確。")
    except EntryNotFoundError:
        raise ModelDownloadError("模型倉庫中找不到指定檔案，請確認 filename 是否正確。")
    except OfflineModeIsEnabled:
        raise ModelDownloadError("目前為離線模式，無法下載模型。請先連線再試。")

    # hf_hub_download returns the actual file path (may differ from target_path
    # if HF cache layout places it elsewhere under local_dir)
    downloaded_path = Path(downloaded)

    # 5. 確保最終檔案位於 target_path（hf_hub_download 有時產生子路徑）
    if downloaded_path.resolve() != target_path.resolve():
        import shutil  # noqa: PLC0415
        shutil.move(str(downloaded_path), str(target_path))

    # 6. 下載後驗證 sha256（非 PENDING）
    if not skip_verify:
        actual = _sha256_of_file(target_path)
        if actual != expected_sha256:
            target_path.unlink(missing_ok=True)
            raise ModelDownloadError("模型檔下載後 sha256 驗證失敗，檔案已刪除，請重新下載。")
        logger.info("CLIP 模型下載並驗證成功 (sha256 OK): %s", target_path)

    # 7. 進度回呼
    if progress_cb is not None:
        progress_cb(1.0)

    return target_path
