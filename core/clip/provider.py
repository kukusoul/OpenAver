"""
core/clip/provider.py
CLIPProvider ABC + LocalONNXProvider skeleton (T2).

NOTE: onnxruntime import is lazy (inside _ensure_session) because onnxruntime
is not yet in requirements.txt (added in T3). Top-level import would cause
ImportError in all existing tests.

NOTE: numpy is also not in requirements.txt yet.  Tests that touch
_embedding_matrix directly import numpy themselves; the provider only uses
numpy inside methods that are stubs (raise NotImplementedError) in this phase,
so no top-level numpy import is needed here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from core.logger import get_logger
from core.path_utils import normalize_path

if TYPE_CHECKING:
    import numpy as np

logger = get_logger(__name__)


class CLIPProvider(ABC):
    """Abstract base class for CLIP embedding providers."""

    @abstractmethod
    async def embed(self, image_bytes: bytes) -> "np.ndarray":
        """回傳 shape (512,) float32 的 embedding vector（需要 session_loaded）"""

    @property
    @abstractmethod
    def model_id(self) -> str:
        """回傳模型版本識別字串，用於 DB clip_model_id 欄位"""

    # 三個狀態 property（修正 P2-1：相似查詢不依賴 ONNX session）
    @property
    @abstractmethod
    def is_enabled(self) -> bool:
        """用戶是否啟用 CLIP 功能（56d Settings 控制；56a 預設 True）"""

    @property
    @abstractmethod
    def model_available(self) -> bool:
        """DB 中是否有可用 embedding（matrix 載入後 ≥1 row 且 model_id 匹配）"""

    @property
    @abstractmethod
    def session_loaded(self) -> bool:
        """ONNX InferenceSession 是否已載入記憶體（只影響 embed() 端，不影響相似查詢）"""

    def invalidate_matrix(self) -> None:
        """通知 provider 清除 in-memory cosine matrix cache（預設 no-op，LocalONNX override）"""


class LocalONNXProvider(CLIPProvider):
    """Local ONNX Runtime CLIP provider using Xenova/clip-vit-base-patch32."""

    MODEL_ID: str = "clip-vit-b32-int8-xenova-v1"   # CD-56A-1 + CD-56A-5
    MODEL_SHA256: str = "PENDING"                    # T3 釘版後填入真實 binary hash

    def __init__(self, model_path: Path) -> None:
        """初始化 LocalONNXProvider，不立即載入 ONNX session（懶載入）。

        Args:
            model_path: Path to the .onnx model file.
        """
        self._model_path: Path = Path(normalize_path(str(model_path)))
        self._session = None                         # ORT InferenceSession，懶載入前為 None
        self._embedding_matrix = None               # cosine 查詢用 matrix（np.ndarray | None）
        self._video_ids = None                       # 與 matrix 同步的影片 id 清單（list[int] | None）

    # ------------------------------------------------------------------
    # CLIPProvider abstract method implementations
    # ------------------------------------------------------------------

    async def embed(self, image_bytes: bytes) -> "np.ndarray":
        """T4 後補全。目前為骨架佔位。"""
        raise NotImplementedError("embed() will be implemented in T4")

    @property
    def model_id(self) -> str:
        return self.MODEL_ID

    @property
    def is_enabled(self) -> bool:
        """56a 預設啟用；56d Settings 控制後可修改。"""
        return True

    @property
    def model_available(self) -> bool:
        """DB 中是否有可用 embedding（matrix 載入後 ≥1 row）。"""
        return self._embedding_matrix is not None

    @property
    def session_loaded(self) -> bool:
        """ONNX InferenceSession 是否已載入記憶體。"""
        return self._session is not None

    def invalidate_matrix(self) -> None:
        """清除 in-memory cosine matrix cache，下次查詢時重新從 DB 載入。"""
        self._embedding_matrix = None
        self._video_ids = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_session(self) -> None:
        """懶載入 ONNX InferenceSession。同步方法，供 asyncio.to_thread 包裝。

        Raises:
            FileNotFoundError: 若 model_path 不存在。
            RuntimeError: 若 ONNX 模型損壞或載入失敗（由 ORT 拋出）。
        """
        if self._session is not None:
            return  # already loaded

        # Check file existence BEFORE lazy-importing onnxruntime so that
        # FileNotFoundError is raised even when onnxruntime is not yet
        # installed (e.g. during T2 tests before T3 adds it to requirements).
        if not self._model_path.exists():
            raise FileNotFoundError(
                f"CLIP model not found: {self._model_path}. "
                "Run model download helper (T3) first."
            )

        # Lazy import: onnxruntime is not in requirements.txt until T3.
        import onnxruntime as ort  # noqa: PLC0415

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._session = ort.InferenceSession(str(self._model_path), providers=providers)
        active_ep = self._session.get_providers()[0]
        logger.info("CLIP session loaded, EP=%s", active_ep)

    def _ensure_matrix_loaded(self, db_path: Path, model_id: str) -> None:
        """懶載入 cosine embedding matrix。T5/T6 後補全。"""
        raise NotImplementedError("_ensure_matrix_loaded() will be implemented in T5")

    async def compute_similar(
        self,
        query_embedding: "np.ndarray",
        limit: int,
    ) -> list[dict]:
        """T6 後補全。"""
        raise NotImplementedError("compute_similar() will be implemented in T6")
