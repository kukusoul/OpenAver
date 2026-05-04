"""
tests/unit/test_clip_provider.py
TDD-lite tests for CLIPProvider ABC, LocalONNXProvider skeleton (T2),
and ModelDownloader helper (T3).
"""
import hashlib
import importlib
import sys
from pathlib import Path

import pytest


class TestCLIPProviderInterface:
    def test_abc_cannot_instantiate(self):
        """CLIPProvider ABC 不可直接實例化"""
        from core.clip.provider import CLIPProvider

        with pytest.raises(TypeError):
            CLIPProvider()

    def test_abstract_methods_defined(self):
        """CLIPProvider 有 embed / model_id / is_enabled / model_available / session_loaded 抽象方法"""
        from core.clip.provider import CLIPProvider

        abstract_methods = CLIPProvider.__abstractmethods__
        assert "embed" in abstract_methods
        assert "model_id" in abstract_methods
        assert "is_enabled" in abstract_methods
        assert "model_available" in abstract_methods
        assert "session_loaded" in abstract_methods

    def test_invalidate_matrix_is_not_abstract(self):
        """invalidate_matrix() 為非抽象 default no-op，不在 abstractmethods"""
        from core.clip.provider import CLIPProvider

        assert "invalidate_matrix" not in CLIPProvider.__abstractmethods__


class TestLocalONNXProviderInit:
    def test_model_id_constant(self):
        """LocalONNXProvider.MODEL_ID == 'clip-vit-b32-int8-xenova-v1'"""
        from core.clip.provider import LocalONNXProvider

        assert LocalONNXProvider.MODEL_ID == "clip-vit-b32-int8-xenova-v1"

    def test_model_sha256_updated(self):
        """LocalONNXProvider.MODEL_SHA256 已更新為 T3 驗證值（非 PENDING）"""
        from core.clip.provider import LocalONNXProvider

        assert LocalONNXProvider.MODEL_SHA256 == "583fd1110a514667812fee7d684952aaf82a99b959760c8d7dca7e0ab9839299"

    def test_lazy_load_no_session_on_init(self, tmp_path):
        """__init__ 不立即載入 session（session_loaded == False）"""
        from core.clip.provider import LocalONNXProvider

        model_path = tmp_path / "model.onnx"
        # 故意不建立檔案 — init 不應驗證檔案存在
        provider = LocalONNXProvider(model_path)
        assert provider.session_loaded is False
        assert provider._session is None

    def test_is_enabled_default_true(self, tmp_path):
        """56a 預設 is_enabled == True"""
        from core.clip.provider import LocalONNXProvider

        provider = LocalONNXProvider(tmp_path / "model.onnx")
        assert provider.is_enabled is True

    def test_model_available_false_before_matrix_loaded(self, tmp_path):
        """init 後 _embedding_matrix 為 None，model_available == False"""
        from core.clip.provider import LocalONNXProvider

        provider = LocalONNXProvider(tmp_path / "model.onnx")
        assert provider.model_available is False
        assert provider._embedding_matrix is None

    def test_model_id_property(self, tmp_path):
        """model_id property 回傳 MODEL_ID 常數"""
        from core.clip.provider import LocalONNXProvider

        provider = LocalONNXProvider(tmp_path / "model.onnx")
        assert provider.model_id == "clip-vit-b32-int8-xenova-v1"

    def test_invalidate_matrix_resets_cache(self, tmp_path):
        """invalidate_matrix() 把 _embedding_matrix 設為 None"""
        from core.clip.provider import LocalONNXProvider

        provider = LocalONNXProvider(tmp_path / "model.onnx")
        # 用任意 sentinel 物件模擬已載入狀態（避免 numpy 依賴）
        provider._embedding_matrix = object()
        provider._video_ids = [1, 2, 3, 4, 5]
        assert provider._embedding_matrix is not None

        provider.invalidate_matrix()

        assert provider._embedding_matrix is None
        assert provider._video_ids is None

    def test_ensure_session_raises_file_not_found(self, tmp_path):
        """_ensure_session() 遇不存在的 model_path 拋 FileNotFoundError"""
        from core.clip.provider import LocalONNXProvider

        provider = LocalONNXProvider(tmp_path / "nonexistent.onnx")
        with pytest.raises(FileNotFoundError):
            provider._ensure_session()

    def test_init_does_not_raise_when_file_missing(self, tmp_path):
        """__init__ 呼叫時 .onnx 不存在不拋錯（懶載入）"""
        from core.clip.provider import LocalONNXProvider

        # 應不拋錯
        provider = LocalONNXProvider(tmp_path / "missing.onnx")
        assert provider is not None

    def test_video_ids_none_on_init(self, tmp_path):
        """__init__ 後 _video_ids 為 None"""
        from core.clip.provider import LocalONNXProvider

        provider = LocalONNXProvider(tmp_path / "model.onnx")
        assert provider._video_ids is None


class TestGetProvider:
    def test_get_provider_returns_local_onnx_provider(self, tmp_path, monkeypatch):
        """get_provider() 回傳 LocalONNXProvider 實例"""
        import core.clip as clip_module
        from core.clip.provider import LocalONNXProvider

        # 重置 singleton
        monkeypatch.setattr(clip_module, "_provider", None)
        model_path = tmp_path / "model.onnx"
        provider = clip_module.get_provider(model_path=model_path)
        assert isinstance(provider, LocalONNXProvider)

    def test_get_provider_returns_singleton(self, tmp_path, monkeypatch):
        """get_provider() 兩次呼叫回傳同一個 LocalONNXProvider 實例"""
        import core.clip as clip_module

        # 重置 singleton
        monkeypatch.setattr(clip_module, "_provider", None)
        model_path = tmp_path / "model.onnx"
        p1 = clip_module.get_provider(model_path=model_path)
        p2 = clip_module.get_provider(model_path=model_path)
        assert p1 is p2

    def test_get_provider_second_call_ignores_model_path(self, tmp_path, monkeypatch):
        """get_provider() 已有 singleton 時，第二次呼叫忽略 model_path"""
        import core.clip as clip_module

        monkeypatch.setattr(clip_module, "_provider", None)
        model_path_a = tmp_path / "a.onnx"
        model_path_b = tmp_path / "b.onnx"
        p1 = clip_module.get_provider(model_path=model_path_a)
        p2 = clip_module.get_provider(model_path=model_path_b)
        assert p1 is p2


# ---------------------------------------------------------------------------
# T3: ModelDownloader helper
# ---------------------------------------------------------------------------

_FAKE_CONTENT = b"fake model content"
_FAKE_SHA256 = hashlib.sha256(_FAKE_CONTENT).hexdigest()


class TestModelDownloader:
    """Tests for core.clip.downloader.ensure_model_downloaded."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _write_fake_file(path: Path, content: bytes = _FAKE_CONTENT) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_returns_path_if_exists_and_sha256_matches(self, tmp_path, mocker):
        """檔案已存在且 sha256 正確 → 跳過下載，回傳 path（idempotent）"""
        from core.clip.downloader import ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"
        self._write_fake_file(target)

        mock_dl = mocker.patch("core.clip.downloader.hf_hub_download")

        result = ensure_model_downloaded(
            target_path=target,
            expected_sha256=_FAKE_SHA256,
        )

        assert result == target
        mock_dl.assert_not_called()

    def test_downloads_if_not_exists(self, tmp_path, mocker):
        """檔案不存在 → 呼叫 hf_hub_download，回傳 path"""
        from core.clip.downloader import ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"

        def fake_download(repo_id, filename, local_dir=None, **kwargs):
            # simulate hf_hub_download writing the file
            dest = Path(local_dir) / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_FAKE_CONTENT)
            return str(dest)

        mocker.patch("core.clip.downloader.hf_hub_download", side_effect=fake_download)

        result = ensure_model_downloaded(
            target_path=target,
            filename="onnx/model.onnx",
            expected_sha256=_FAKE_SHA256,
        )

        assert result == target

    def test_sha256_mismatch_raises_error(self, tmp_path, mocker):
        """sha256 不符 → 刪除檔案 + 拋 ModelDownloadError"""
        from core.clip.downloader import ModelDownloadError, ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"
        self._write_fake_file(target, b"corrupt content")

        mocker.patch("core.clip.downloader.hf_hub_download")

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded(
                target_path=target,
                expected_sha256=_FAKE_SHA256,
            )

        # corrupted file should be deleted
        assert not target.exists()

    def test_pending_sha256_skips_verification(self, tmp_path, mocker):
        """expected_sha256 == 'PENDING' → 跳過驗證，成功回傳"""
        from core.clip.downloader import ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"
        self._write_fake_file(target, b"any content, no verification")

        mock_dl = mocker.patch("core.clip.downloader.hf_hub_download")

        result = ensure_model_downloaded(
            target_path=target,
            expected_sha256="PENDING",
        )

        assert result == target
        mock_dl.assert_not_called()

    def test_connection_error_raises_model_download_error(self, tmp_path, mocker):
        """requests.ConnectionError → 包裝為 ModelDownloadError"""
        import requests
        from core.clip.downloader import ModelDownloadError, ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"

        mocker.patch(
            "core.clip.downloader.hf_hub_download",
            side_effect=requests.ConnectionError("no network"),
        )

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded(
                target_path=target,
                expected_sha256=_FAKE_SHA256,
            )

    def test_hf_http_error_raises_model_download_error(self, tmp_path, mocker):
        """HfHubHTTPError → 包裝為 ModelDownloadError"""
        from unittest.mock import MagicMock
        import httpx
        from huggingface_hub.errors import HfHubHTTPError
        from core.clip.downloader import ModelDownloadError, ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 503
        mock_response.headers = {}
        hf_error = HfHubHTTPError("503 Server Error", response=mock_response)

        mocker.patch(
            "core.clip.downloader.hf_hub_download",
            side_effect=hf_error,
        )

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded(
                target_path=target,
                expected_sha256=_FAKE_SHA256,
            )

    def test_repository_not_found_raises_model_download_error(self, tmp_path, mocker):
        """RepositoryNotFoundError → 包裝為 ModelDownloadError"""
        from unittest.mock import MagicMock
        import httpx
        from huggingface_hub.errors import RepositoryNotFoundError
        from core.clip.downloader import ModelDownloadError, ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.headers = {}
        repo_error = RepositoryNotFoundError("not found", response=mock_response)

        mocker.patch(
            "core.clip.downloader.hf_hub_download",
            side_effect=repo_error,
        )

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded(
                target_path=target,
                expected_sha256=_FAKE_SHA256,
            )

    def test_entry_not_found_raises_model_download_error(self, tmp_path, mocker):
        """EntryNotFoundError → 包裝為 ModelDownloadError"""
        from huggingface_hub.errors import EntryNotFoundError
        from core.clip.downloader import ModelDownloadError, ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"

        mocker.patch(
            "core.clip.downloader.hf_hub_download",
            side_effect=EntryNotFoundError("no such file"),
        )

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded(
                target_path=target,
                expected_sha256=_FAKE_SHA256,
            )

    def test_creates_parent_directory(self, tmp_path, mocker):
        """目標目錄不存在 → 自動建立，不拋錯"""
        from core.clip.downloader import ensure_model_downloaded

        # deeply nested path that does not yet exist
        target = tmp_path / "a" / "b" / "c" / "model.onnx"

        def fake_download(repo_id, filename, local_dir=None, **kwargs):
            dest = Path(local_dir) / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_FAKE_CONTENT)
            return str(dest)

        mocker.patch("core.clip.downloader.hf_hub_download", side_effect=fake_download)

        result = ensure_model_downloaded(
            target_path=target,
            filename="onnx/model.onnx",
            expected_sha256=_FAKE_SHA256,
        )

        assert result == target
        assert target.exists()

    def test_model_download_error_message_is_fixed_chinese(self, tmp_path, mocker):
        """錯誤 message 為固定中文字串，不含 exception args/traceback"""
        import requests
        from core.clip.downloader import ModelDownloadError, ensure_model_downloaded

        target = tmp_path / "onnx" / "model.onnx"

        mocker.patch(
            "core.clip.downloader.hf_hub_download",
            side_effect=requests.ConnectionError("raw network error details"),
        )

        with pytest.raises(ModelDownloadError) as exc_info:
            ensure_model_downloaded(
                target_path=target,
                expected_sha256=_FAKE_SHA256,
            )

        msg = str(exc_info.value)
        # should be fixed Chinese, not leaking raw exception internals
        assert "raw network error details" not in msg
        # must contain Chinese characters (at least one CJK char)
        assert any("一" <= ch <= "鿿" for ch in msg)


# ---------------------------------------------------------------------------
# T5: ClipIndexer (batch indexing runner)
# ---------------------------------------------------------------------------

import asyncio
from unittest.mock import AsyncMock, MagicMock, call, patch

import numpy as np


class TestClipIndexer:
    """Tests for core.clip.indexer.ClipIndexer.run_batch()."""

    def _make_mock_provider(self, embedding=None):
        provider = MagicMock()
        provider.model_id = "clip-vit-b32-int8-xenova-v1"
        if embedding is None:
            embedding = np.zeros(512, dtype=np.float32)
        provider.embed = AsyncMock(return_value=embedding)
        provider.invalidate_matrix = MagicMock()
        return provider

    def _make_video(self, video_id, cover_path, tmp_path=None):
        """Build a minimal Video-like object (MagicMock with required attrs)."""
        v = MagicMock()
        v.id = video_id
        v.cover_path = cover_path
        return v

    def _write_cover(self, tmp_path, filename="cover.jpg"):
        """Write a tiny fake JPEG to tmp_path and return its file:/// URI."""
        from PIL import Image
        img_path = tmp_path / filename
        Image.new("RGB", (10, 10)).save(img_path)
        from core.path_utils import to_file_uri
        return str(to_file_uri(str(img_path))), img_path

    # ------------------------------------------------------------------
    # happy path
    # ------------------------------------------------------------------

    async def test_run_batch_indexes_pending_videos(self, tmp_path):
        """有 pending video → embed 被呼叫，update_clip_embedding 被呼叫"""
        from core.clip.indexer import ClipIndexer

        cover_uri, _ = self._write_cover(tmp_path)
        video = self._make_video(1, cover_uri)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video]
        mock_repo.update_clip_embedding.return_value = True

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert result == {"indexed": 1, "skipped": 0, "errors": 0}
        provider.embed.assert_awaited_once()
        mock_repo.update_clip_embedding.assert_called_once_with(
            1, provider.embed.return_value.astype('<f4').tobytes(), provider.model_id
        )

    async def test_run_batch_no_pending_videos(self, tmp_path):
        """0 筆待索引 → indexed=0, embed 不被呼叫"""
        from core.clip.indexer import ClipIndexer

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = []

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert result == {"indexed": 0, "skipped": 0, "errors": 0}
        provider.embed.assert_not_awaited()

    async def test_run_batch_returns_stats(self, tmp_path):
        """回傳 dict 含 indexed / skipped / errors key"""
        from core.clip.indexer import ClipIndexer

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = []

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert "indexed" in result
        assert "skipped" in result
        assert "errors" in result

    # ------------------------------------------------------------------
    # skipping
    # ------------------------------------------------------------------

    async def test_run_batch_skips_no_cover(self, tmp_path):
        """cover_path 為 None → skip，embed 不被呼叫"""
        from core.clip.indexer import ClipIndexer

        video = self._make_video(1, None)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video]

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert result["skipped"] == 1
        assert result["indexed"] == 0
        provider.embed.assert_not_awaited()

    async def test_run_batch_skips_missing_cover_file(self, tmp_path):
        """cover_path 有值但檔案不存在 → skipped++"""
        from core.clip.indexer import ClipIndexer
        from core.path_utils import to_file_uri

        nonexistent = tmp_path / "no_such_file.jpg"
        cover_uri = str(to_file_uri(str(nonexistent)))

        video = self._make_video(1, cover_uri)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video]

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert result["skipped"] == 1
        assert result["indexed"] == 0
        provider.embed.assert_not_awaited()

    # ------------------------------------------------------------------
    # errors
    # ------------------------------------------------------------------

    async def test_run_batch_embed_failure_increments_errors(self, tmp_path):
        """embed 拋 exception → errors 計數增加，不中止 batch"""
        from core.clip.indexer import ClipIndexer

        cover_uri_1, _ = self._write_cover(tmp_path, "cover1.jpg")
        cover_uri_2, _ = self._write_cover(tmp_path, "cover2.jpg")

        video1 = self._make_video(1, cover_uri_1)
        video2 = self._make_video(2, cover_uri_2)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video1, video2]
        mock_repo.update_clip_embedding.return_value = True

        provider = self._make_mock_provider()
        provider.embed = AsyncMock(side_effect=[RuntimeError("embed failed"), np.zeros(512, dtype=np.float32)])
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert result["errors"] == 1
        assert result["indexed"] == 1

    # ------------------------------------------------------------------
    # resume / checkpoint
    # ------------------------------------------------------------------

    async def test_run_batch_resume_after_interrupt(self, tmp_path):
        """斷點續傳：第二次跑時已索引的 video 不重複 embed"""
        from core.clip.indexer import ClipIndexer

        cover_uri_a, _ = self._write_cover(tmp_path, "a.jpg")
        cover_uri_b, _ = self._write_cover(tmp_path, "b.jpg")
        cover_uri_c, _ = self._write_cover(tmp_path, "c.jpg")

        video_a = self._make_video(1, cover_uri_a)
        video_b = self._make_video(2, cover_uri_b)
        video_c = self._make_video(3, cover_uri_c)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.side_effect = [
            [video_a, video_b],   # 第一次 run_batch
            [video_c],             # 第二次 run_batch（模擬 a, b 已完成）
        ]
        mock_repo.update_clip_embedding.return_value = True

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        await indexer.run_batch()   # 第一次：embed a, b
        await indexer.run_batch()   # 第二次：embed c only

        # embed 總共應被呼叫 3 次（2 + 1），不是 5 次
        assert provider.embed.await_count == 3

    # ------------------------------------------------------------------
    # invalidate_matrix
    # ------------------------------------------------------------------

    async def test_run_batch_calls_invalidate_matrix(self, tmp_path):
        """完成後呼叫 provider.invalidate_matrix()"""
        from core.clip.indexer import ClipIndexer

        cover_uri, _ = self._write_cover(tmp_path)
        video = self._make_video(1, cover_uri)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video]
        mock_repo.update_clip_embedding.return_value = True

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        await indexer.run_batch()

        provider.invalidate_matrix.assert_called_once()

    async def test_run_batch_invalidate_matrix_called_with_zero_pending(self, tmp_path):
        """0 筆待索引時 invalidate_matrix 仍被呼叫"""
        from core.clip.indexer import ClipIndexer

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = []

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        await indexer.run_batch()

        provider.invalidate_matrix.assert_called_once()

    # ------------------------------------------------------------------
    # progress_cb
    # ------------------------------------------------------------------

    async def test_run_batch_progress_cb_called_for_each_video(self, tmp_path):
        """progress_cb(done, total) 每筆完成後被呼叫，total 固定，done 遞增"""
        from core.clip.indexer import ClipIndexer

        cover_uri_1, _ = self._write_cover(tmp_path, "p1.jpg")
        cover_uri_2, _ = self._write_cover(tmp_path, "p2.jpg")
        video1 = self._make_video(1, cover_uri_1)
        video2 = self._make_video(2, cover_uri_2)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video1, video2]
        mock_repo.update_clip_embedding.return_value = True

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        calls = []
        await indexer.run_batch(progress_cb=lambda done, total: calls.append((done, total)))

        assert calls == [(1, 2), (2, 2)]

    # ------------------------------------------------------------------
    # uri_to_fs_path usage
    # ------------------------------------------------------------------

    async def test_run_batch_uses_uri_to_fs_path(self, tmp_path):
        """cover_path 轉換使用 uri_to_fs_path()（不手動 strip file:///）"""
        from core.clip.indexer import ClipIndexer
        from core.path_utils import to_file_uri

        cover_uri, _ = self._write_cover(tmp_path)
        video = self._make_video(1, cover_uri)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video]
        mock_repo.update_clip_embedding.return_value = True

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        with patch("core.clip.indexer.uri_to_fs_path", wraps=__import__("core.path_utils", fromlist=["uri_to_fs_path"]).uri_to_fs_path) as mock_uri:
            await indexer.run_batch()
            mock_uri.assert_called_once_with(cover_uri)

    # ------------------------------------------------------------------
    # DB retry
    # ------------------------------------------------------------------

    async def test_db_write_retry_once_succeeds(self, tmp_path):
        """update_clip_embedding 第一次回 False，retry 成功 → indexed=1"""
        from core.clip.indexer import ClipIndexer

        cover_uri, _ = self._write_cover(tmp_path)
        video = self._make_video(1, cover_uri)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video]
        # 第一次回 False，第二次回 True
        mock_repo.update_clip_embedding.side_effect = [False, True]

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert result == {"indexed": 1, "skipped": 0, "errors": 0}
        assert mock_repo.update_clip_embedding.call_count == 2

    async def test_db_write_retry_both_fail(self, tmp_path):
        """update_clip_embedding 兩次都回 False → errors=1"""
        from core.clip.indexer import ClipIndexer

        cover_uri, _ = self._write_cover(tmp_path)
        video = self._make_video(1, cover_uri)

        mock_repo = MagicMock()
        mock_repo.get_videos_pending_clip_indexing.return_value = [video]
        mock_repo.update_clip_embedding.return_value = False

        provider = self._make_mock_provider()
        indexer = ClipIndexer(provider=provider, video_repo=mock_repo)

        result = await indexer.run_batch()

        assert result == {"indexed": 0, "skipped": 0, "errors": 1}
        assert mock_repo.update_clip_embedding.call_count == 2
