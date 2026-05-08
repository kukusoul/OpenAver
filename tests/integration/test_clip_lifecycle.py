"""
tests/integration/test_clip_lifecycle.py
TDD-lite integration tests for /api/clip/* lifecycle endpoints.
Uses FastAPI TestClient + mocks (no real downloads, no real DB).
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# SSE helper
# ---------------------------------------------------------------------------

def parse_sse(text: str) -> list:
    """Parse SSE text body into list of dicts."""
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


# ---------------------------------------------------------------------------
# Provider mock factory
# ---------------------------------------------------------------------------

def _make_provider(
    is_enabled: bool = True,
    model_id: str = "clip-vit-b32-int8-xenova-v1",
):
    provider = MagicMock()
    type(provider).is_enabled = property(lambda self: is_enabled)
    provider.model_id = model_id
    provider.embed = AsyncMock(return_value=MagicMock(shape=(512,)))
    return provider


# ---------------------------------------------------------------------------
# Module-state reset fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_lifecycle_module():
    """Reset module-level state in clip_lifecycle between tests."""
    import importlib
    # Import (or reimport) to get fresh module state
    import web.routers.clip_lifecycle as lcm

    # Reset status singleton
    with lcm._clip_status_lock:
        lcm._clip_status.clear()
        lcm._clip_status.update({
            "phase": "idle",
            "download_bytes": 0,
            "download_total": 0,
            "index_done": 0,
            "index_total": 0,
            "error_message": "",
        })

    # Cancel and clear _enable_task
    old_task = lcm._enable_task
    if old_task is not None and not old_task.done():
        old_task.cancel()
    lcm._enable_task = None

    yield

    # Teardown: cancel task if it's still alive
    task = lcm._enable_task
    if task is not None and not task.done():
        task.cancel()
    lcm._enable_task = None


# ---------------------------------------------------------------------------
# App client fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from web.app import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers: standard mock patches used across tests
# ---------------------------------------------------------------------------

def _std_patches(mocker, *, enabled_config=False, indexer_result=None):
    """Return a dict of standard mocker.patch calls for lifecycle tests."""
    if indexer_result is None:
        indexer_result = {"indexed": 1, "skipped": 0, "errors": 0}

    # Patch downloader
    mocker.patch(
        "web.routers.clip_lifecycle.ensure_model_downloaded_streaming",
        return_value=Path("/fake/model.onnx"),
    )

    # Patch ClipIndexer
    mock_indexer_cls = mocker.patch("web.routers.clip_lifecycle.ClipIndexer")
    mock_indexer_instance = MagicMock()
    mock_indexer_instance.run_batch = AsyncMock(return_value=indexer_result)
    mock_indexer_cls.return_value = mock_indexer_instance

    # Patch get_provider
    provider = _make_provider(is_enabled=True)
    mocker.patch("web.routers.clip_lifecycle.get_provider", return_value=provider)

    # Patch load_config and save_config
    cfg = {"clip": {"enabled": enabled_config, "model_path": None}}
    mocker.patch("web.routers.clip_lifecycle.load_config", return_value=cfg)
    mock_save = mocker.patch("web.routers.clip_lifecycle.save_config")

    # Patch VideoRepository
    mock_repo = MagicMock()
    mock_repo.clear_all_clip_embeddings = MagicMock(return_value=5)
    mocker.patch("web.routers.clip_lifecycle.VideoRepository", return_value=mock_repo)

    return {
        "provider": provider,
        "indexer_instance": mock_indexer_instance,
        "save_config": mock_save,
        "repo": mock_repo,
        "cfg": cfg,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_status_returns_phase_idle_by_default(self, client):
        resp = client.get("/api/clip/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "idle"

    def test_status_mirrors_downloading_phase_snapshot(self, client):
        """GET /status correctly mirrors downloading phase with byte counters (plan DoD §三階段快照)."""
        import web.routers.clip_lifecycle as lcm

        lcm._set_status(phase="downloading", download_bytes=1234, download_total=80_000_000)

        resp = client.get("/api/clip/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "downloading"
        assert data["download_bytes"] == 1234
        assert data["download_total"] == 80_000_000

    def test_status_mirrors_indexing_phase_snapshot(self, client):
        """GET /status correctly mirrors indexing phase with index counters (plan DoD §三階段快照)."""
        import web.routers.clip_lifecycle as lcm

        lcm._set_status(phase="indexing", index_done=42, index_total=200)

        resp = client.get("/api/clip/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["phase"] == "indexing"
        assert data["index_done"] == 42
        assert data["index_total"] == 200


class TestEnableSSE:

    def test_enable_returns_sse_event_stream(self, client, mocker):
        """POST /enable → returns SSE with at least one status event."""
        patches = _std_patches(mocker)

        # Use stream=True to consume SSE
        with client.stream("POST", "/api/clip/enable") as resp:
            assert resp.status_code == 200
            content_type = resp.headers.get("content-type", "")
            assert "text/event-stream" in content_type
            # Read all events
            text = resp.read().decode()

        events = parse_sse(text)
        assert len(events) >= 1
        # Should have at least one status event
        assert any(e.get("type") == "status" for e in events)

    def test_enable_sse_contains_downloading_then_ready(self, client, mocker):
        """SSE observer must receive 'downloading' before 'ready' (CD-56D-11-C race fix)."""
        _std_patches(mocker)

        with client.stream("POST", "/api/clip/enable") as resp:
            text = resp.read().decode()

        events = parse_sse(text)
        phases = [e.get("phase") for e in events]

        # CD-56D-11-C: downloading phase must appear in stream before ready
        assert "downloading" in phases, f"downloading phase missing from SSE stream: {phases}"
        assert phases.index("downloading") < phases.index("ready"), \
            f"downloading must come before ready: {phases}"
        # Terminal state must be ready
        assert phases[-1] == "ready"

    def test_enable_post_concurrent_returns_409(self, client, mocker):
        """NAMED: Second POST /enable while first is in-flight → 409."""
        import web.routers.clip_lifecycle as lcm

        # Inject a dummy in-flight task
        try:
            # Use a MagicMock that simulates a running task
            fake_task = MagicMock()
            fake_task.done = MagicMock(return_value=False)
            lcm._enable_task = fake_task

            resp = client.post("/api/clip/enable")
            assert resp.status_code == 409
            assert "啟用流程已在進行中" in resp.json()["detail"]
        finally:
            lcm._enable_task = None

    def test_enable_job_isolated_from_request(self, client, mocker):
        """NAMED: SSE generator cancel does not kill _enable_task; status reaches ready (CD-56D-11-C)."""
        import time
        import web.routers.clip_lifecycle as lcm

        # Add a small async delay in indexer.run_batch to ensure disconnect happens mid-job
        # (ensures _enable_task is still running when we close the SSE connection)
        patches = _std_patches(mocker)
        orig_run_batch = patches["indexer_instance"].run_batch

        async def slow_run_batch(progress_cb=None):
            await asyncio.sleep(0.15)  # simulate non-trivial indexing work
            return {"indexed": 1, "skipped": 0, "errors": 0}

        patches["indexer_instance"].run_batch = slow_run_batch

        # 1. Open SSE connection, read exactly one event then close (simulate client disconnect)
        with client.stream("POST", "/api/clip/enable") as resp:
            assert resp.status_code == 200
            for line in resp.iter_lines():
                if line.startswith("data: "):
                    break
            # Context manager exit → HTTP response closed → SSE generator abandoned

        # 2. Poll /api/clip/status: _enable_task is module-level, independent of the SSE
        # generator, so it continues running even after the client disconnects.
        deadline = time.time() + 5
        snapshot = {"phase": "unknown"}
        while time.time() < deadline:
            snapshot = client.get("/api/clip/status").json()
            if snapshot["phase"] in ("ready", "error"):
                break
            time.sleep(0.05)
        else:
            pytest.fail(f"_enable_task did not reach ready after SSE disconnect, last={snapshot}")

        # 3. Background task must have completed to ready despite SSE disconnect (CD-56D-11-C)
        assert snapshot["phase"] == "ready", \
            f"Expected phase=ready after SSE disconnect, got: {snapshot}"

    def test_enable_observer_idle_not_terminal(self, client, mocker):
        """SSE observer: 'idle' is NOT terminal; stream continues until 'ready'."""
        _std_patches(mocker)

        with client.stream("POST", "/api/clip/enable") as resp:
            text = resp.read().decode()

        events = parse_sse(text)
        phases = [e.get("phase") for e in events]

        # idle must NOT be the last phase (stream must not break on idle)
        if "idle" in phases:
            assert phases[-1] != "idle"
        # Stream must end on ready or error
        assert phases[-1] in ("ready", "error")

    def test_enable_index_fail_does_not_write_config_enabled(self, client, mocker):
        """NAMED (edge-case §7): index failure → phase=error + config enabled stays False."""
        import web.routers.clip_lifecycle as lcm

        mocker.patch(
            "web.routers.clip_lifecycle.ensure_model_downloaded_streaming",
            return_value=Path("/fake/model.onnx"),
        )
        mock_indexer_cls = mocker.patch("web.routers.clip_lifecycle.ClipIndexer")
        mock_indexer_instance = MagicMock()
        mock_indexer_instance.run_batch = AsyncMock(
            side_effect=RuntimeError("index failed")
        )
        mock_indexer_cls.return_value = mock_indexer_instance

        provider = _make_provider(is_enabled=True)
        mocker.patch("web.routers.clip_lifecycle.get_provider", return_value=provider)

        cfg = {"clip": {"enabled": False, "model_path": None}}
        mocker.patch("web.routers.clip_lifecycle.load_config", return_value=cfg)
        mock_save = mocker.patch("web.routers.clip_lifecycle.save_config")
        mocker.patch("web.routers.clip_lifecycle.VideoRepository")

        with client.stream("POST", "/api/clip/enable") as resp:
            text = resp.read().decode()

        events = parse_sse(text)
        phases = [e.get("phase") for e in events]

        # Must end in error
        assert "error" in phases

        # save_config must NOT have been called with enabled=True
        for call_args in mock_save.call_args_list:
            saved_cfg = call_args.args[0]
            assert not saved_cfg.get("clip", {}).get("enabled", False), \
                "config must not have enabled=True after index failure"


class TestDisable:

    def test_disable_returns_409_during_enable_in_flight(self, client, mocker):
        """NAMED: disable while enable in-flight → 409 + config/file/DB unchanged."""
        import web.routers.clip_lifecycle as lcm
        from pathlib import Path
        import tempfile

        # Create a real model file to ensure it's not deleted
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            onnx_path = Path(f.name)
            f.write(b"fake model")

        try:
            # Mock _DEFAULT_MODEL_PATH to our temp file
            mocker.patch("web.routers.clip_lifecycle._DEFAULT_MODEL_PATH", onnx_path)

            # Inject in-flight task
            fake_task = MagicMock()
            fake_task.done = MagicMock(return_value=False)
            lcm._enable_task = fake_task

            # Mock load_config so we can verify it wasn't called to mutate
            cfg = {"clip": {"enabled": True, "model_path": str(onnx_path)}}
            mock_load = mocker.patch(
                "web.routers.clip_lifecycle.load_config", return_value=cfg
            )
            mock_save = mocker.patch("web.routers.clip_lifecycle.save_config")
            mock_repo = MagicMock()
            mocker.patch(
                "web.routers.clip_lifecycle.VideoRepository", return_value=mock_repo
            )

            resp = client.post("/api/clip/disable")

            assert resp.status_code == 409
            assert "啟用流程進行中" in resp.json()["detail"]

            # Config must not have been loaded or saved (409 short-circuits completely)
            mock_load.assert_not_called()
            mock_save.assert_not_called()

            # DB must not have been touched
            mock_repo.clear_all_clip_embeddings.assert_not_called()

            # .onnx file must still exist
            assert onnx_path.exists(), ".onnx file must not be deleted during 409"

        finally:
            lcm._enable_task = None
            onnx_path.unlink(missing_ok=True)

    def test_disable_five_phases_all_executed(self, client, mocker):
        """NAMED (§8): disable after ready → 200 + cleared_embeddings + config=False + provider=None."""
        import web.routers.clip_lifecycle as lcm
        import core.clip
        import tempfile
        from pathlib import Path

        # Create a fake onnx file
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as f:
            onnx_path = Path(f.name)
            f.write(b"fake model")

        # Pre-set _provider to a sentinel to verify it is cleared (not just already None)
        sentinel_provider = MagicMock()
        core.clip._provider = sentinel_provider

        try:
            mocker.patch("web.routers.clip_lifecycle._DEFAULT_MODEL_PATH", onnx_path)

            cfg = {"clip": {"enabled": True, "model_path": str(onnx_path)}}
            mocker.patch("web.routers.clip_lifecycle.load_config", return_value=cfg)
            mock_save = mocker.patch("web.routers.clip_lifecycle.save_config")

            mock_repo = MagicMock()
            mock_repo.clear_all_clip_embeddings = MagicMock(return_value=7)
            mocker.patch(
                "web.routers.clip_lifecycle.VideoRepository", return_value=mock_repo
            )

            # Ensure no in-flight task
            lcm._enable_task = None

            resp = client.post("/api/clip/disable")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["cleared_embeddings"] == 7

            # Config must have been saved with enabled=False
            mock_save.assert_called_once()
            saved_cfg = mock_save.call_args.args[0]
            assert saved_cfg.get("clip", {}).get("enabled") is False

            # DB clearing must have been called
            mock_repo.clear_all_clip_embeddings.assert_called_once()

            # .onnx file must be deleted
            assert not onnx_path.exists(), ".onnx file should have been deleted"

            # Status phase must be idle
            status_resp = client.get("/api/clip/status")
            assert status_resp.json()["phase"] == "idle"

            # Provider singleton must be reset to None (階段 3 驗證)
            assert core.clip._provider is None, "disable 必須 reset _provider singleton"

        finally:
            core.clip._provider = None  # ensure cleanup regardless of test outcome
            onnx_path.unlink(missing_ok=True)


class TestTestInference:

    def test_test_inference_503_when_disabled(self, client, mocker):
        """POST /test-inference when provider.is_enabled=False → 503."""
        provider = _make_provider(is_enabled=False)
        mocker.patch("web.routers.clip_lifecycle.get_provider", return_value=provider)

        resp = client.post("/api/clip/test-inference")
        assert resp.status_code == 503
        assert "CLIP 索引尚未準備好" in resp.json()["detail"]

    def test_test_inference_500_no_exc_leak(self, client, mocker):
        """POST /test-inference + embed raises RuntimeError → 500 + detail does NOT leak exception string."""
        provider = _make_provider(is_enabled=True)
        provider.embed = AsyncMock(
            side_effect=RuntimeError("onnxruntime internal crash details")
        )
        mocker.patch("web.routers.clip_lifecycle.get_provider", return_value=provider)

        mock_path = MagicMock(spec=Path)
        mock_path.exists = MagicMock(return_value=True)
        mock_path.read_bytes = MagicMock(return_value=b"fake_image_bytes")
        mocker.patch("web.routers.clip_lifecycle.TEST_IMAGE_PATH", mock_path)

        resp = client.post("/api/clip/test-inference")

        assert resp.status_code == 500
        detail = resp.json()["detail"]
        assert "onnxruntime internal crash" not in detail
        assert "推論失敗" in detail

    def test_test_inference_success(self, client, mocker):
        """POST /test-inference success path → 200 + elapsed_ms + embedding_dim."""
        import numpy as np

        provider = _make_provider(is_enabled=True)
        fake_embedding = MagicMock()
        fake_embedding.shape = (512,)
        provider.embed = AsyncMock(return_value=fake_embedding)
        mocker.patch("web.routers.clip_lifecycle.get_provider", return_value=provider)

        mock_path = MagicMock(spec=Path)
        mock_path.exists = MagicMock(return_value=True)
        mock_path.read_bytes = MagicMock(return_value=b"fake_image_bytes")
        mocker.patch("web.routers.clip_lifecycle.TEST_IMAGE_PATH", mock_path)

        resp = client.post("/api/clip/test-inference")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "elapsed_ms" in data
        assert data["embedding_dim"] == 512
