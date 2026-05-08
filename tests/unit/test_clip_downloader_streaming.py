"""
tests/unit/test_clip_downloader_streaming.py
TDD-lite unit tests for ensure_model_downloaded_streaming().
All network calls are mocked.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from core.clip.downloader import (
    ensure_model_downloaded_streaming,
    ModelDownloadError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_model_path(tmp_path: Path) -> Path:
    return tmp_path / "model.onnx"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEnsureModelDownloadedStreaming:

    def test_skip_if_exists_and_sha256_ok(self, tmp_model_path: Path, mocker):
        """已存在且 sha256 符合 → 不發 HTTP 請求，直接回傳路徑。"""
        tmp_model_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_model_path.write_bytes(b"content")

        expected_sha = "abc123"
        mock_sha256 = mocker.patch(
            "core.clip.downloader._sha256_of_file",
            return_value=expected_sha,
        )
        mock_get = mocker.patch("core.clip.downloader.requests.get")
        mock_cb = MagicMock()

        result = ensure_model_downloaded_streaming(
            tmp_model_path,
            expected_sha256=expected_sha,
            progress_cb=mock_cb,
        )

        assert result == tmp_model_path
        mock_get.assert_not_called()
        # progress_cb called with (size, size) for instant 100%
        size = tmp_model_path.stat().st_size
        mock_cb.assert_called_once_with(size, size)

    def test_streaming_download_calls_progress_cb(self, tmp_model_path: Path, mocker):
        """串流下載 3 chunks → progress_cb 被呼叫 ≥ 3 次，最後一次 done == total。"""
        chunks = [b"A" * 100, b"B" * 100, b"C" * 100]
        total_bytes = 300

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {"content-length": str(total_bytes)}
        mock_resp.iter_content = MagicMock(return_value=iter(chunks))
        mock_resp.raise_for_status = MagicMock()

        mocker.patch("core.clip.downloader.requests.get", return_value=mock_resp)

        # Mock sha256 to pass verification
        expected_sha = "deadbeef"
        mocker.patch("core.clip.downloader._sha256_of_file", return_value=expected_sha)

        mock_cb = MagicMock()

        result = ensure_model_downloaded_streaming(
            tmp_model_path,
            expected_sha256=expected_sha,
            progress_cb=mock_cb,
        )

        assert result == tmp_model_path
        assert mock_cb.call_count >= 3

        # Last call: done == total
        last_call = mock_cb.call_args_list[-1]
        done, total = last_call.args
        assert done == total_bytes
        assert total == total_bytes

    def test_sha256_fail_deletes_file(self, tmp_model_path: Path, mocker):
        """下載後 sha256 不符 → file 被刪除 + raise ModelDownloadError。"""
        chunks = [b"X" * 50]

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.headers = {"content-length": "50"}
        mock_resp.iter_content = MagicMock(return_value=iter(chunks))
        mock_resp.raise_for_status = MagicMock()

        mocker.patch("core.clip.downloader.requests.get", return_value=mock_resp)
        # Return bad sha256 so verification fails
        mocker.patch("core.clip.downloader._sha256_of_file", return_value="badhash")

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded_streaming(
                tmp_model_path,
                expected_sha256="expectedhash",
            )

        assert not tmp_model_path.exists()

    def test_connection_error_raises_model_download_error(self, tmp_model_path: Path, mocker):
        """requests.ConnectionError → ModelDownloadError（不洩漏底層訊息型態）。"""
        import requests as req_lib

        mocker.patch(
            "core.clip.downloader.requests.get",
            side_effect=req_lib.ConnectionError("network unreachable"),
        )

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded_streaming(
                tmp_model_path,
                expected_sha256="anything",
            )

    def test_timeout_raises_model_download_error(self, tmp_model_path: Path, mocker):
        """requests.Timeout → ModelDownloadError（CD-56D-3 except (ConnectionError, Timeout)）。"""
        import requests as req_lib

        mocker.patch(
            "core.clip.downloader.requests.get",
            side_effect=req_lib.Timeout("connection timed out"),
        )

        with pytest.raises(ModelDownloadError):
            ensure_model_downloaded_streaming(
                tmp_model_path,
                expected_sha256="anything",
            )
