"""
tests/integration/test_scanner_clip_hook.py
TDD-lite integration tests for generate_avlist CLIP fire-and-forget hook (CD-56D-4).
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
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


# ---------------------------------------------------------------------------
# Fixtures: patch the heavy scanner machinery so we only test the hook
# ---------------------------------------------------------------------------

_FAKE_DIR = "/tmp/fake_scan_dir"

# Base scanner config (directories must be non-empty to pass the early-return guard)
_BASE_SCANNER_CONFIG = {
    "gallery": {
        "directories": [_FAKE_DIR],
        "output_dir": "/tmp",
        "output_filename": "out.html",
        "path_mappings": {},
        "min_size_mb": 0,
    },
    "general": {"theme": "light"},
}


@pytest.fixture()
def scanner_patches(mocker):
    """Patch out all scanner internals so generate_avlist completes quickly."""
    # Minimal config with clip disabled by default; each test can override load_config
    mocker.patch(
        "web.routers.scanner.load_config",
        return_value={**_BASE_SCANNER_CONFIG, "clip": {"enabled": False}},
    )
    mocker.patch("web.routers.scanner.fast_scan_directory", return_value=[])
    mocker.patch("web.routers.scanner.init_db")
    mocker.patch("web.routers.scanner.get_db_path", return_value="/tmp/test.db")
    mocker.patch("web.routers.scanner.normalize_path", side_effect=lambda p: p)
    mocker.patch("os.path.exists", return_value=True)

    # VideoRepository mock: empty DB
    mock_repo = MagicMock()
    mock_repo.get_all_videos.return_value = []
    mock_repo.count.return_value = 0
    mock_repo.upsert_video.return_value = (False, False)
    mock_repo.remove_deleted_videos.return_value = 0
    mocker.patch("web.routers.scanner.VideoRepository", return_value=mock_repo)

    # HTML generator mock
    mock_gen = MagicMock()
    mock_gen.generate.return_value = Path("/tmp/out.html")
    mocker.patch("web.routers.scanner.HTMLGenerator", return_value=mock_gen)

    # notifications
    mocker.patch("web.routers.scanner._emit_notif")

    return mock_repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestScannerClipHook:

    def test_hook_not_triggered_when_clip_disabled(self, mocker, scanner_patches):
        """clip.enabled=False → threading.Thread is NOT called."""
        # Override load_config with clip disabled (scanner_patches fixture already does this,
        # but we re-patch to make the intent explicit)
        mocker.patch(
            "web.routers.scanner.load_config",
            return_value={**_BASE_SCANNER_CONFIG, "clip": {"enabled": False}},
        )
        mock_thread_cls = mocker.patch("web.routers.scanner.threading.Thread")

        from web.app import app
        client = TestClient(app)
        resp = client.get("/api/gallery/generate")
        assert resp.status_code == 200

        # Thread constructor should NOT have been called (hook not triggered)
        mock_thread_cls.assert_not_called()

    def test_hook_triggered_once_when_clip_enabled(self, mocker, scanner_patches):
        """clip.enabled=True → threading.Thread is constructed and .start() called once."""
        mocker.patch(
            "web.routers.scanner.load_config",
            return_value={**_BASE_SCANNER_CONFIG, "clip": {"enabled": True}},
        )
        mock_thread_instance = MagicMock()
        mock_thread_cls = mocker.patch(
            "web.routers.scanner.threading.Thread",
            return_value=mock_thread_instance,
        )

        from web.app import app
        client = TestClient(app)
        resp = client.get("/api/gallery/generate")
        assert resp.status_code == 200

        # Thread should have been instantiated once
        mock_thread_cls.assert_called_once()
        # .start() should have been called
        mock_thread_instance.start.assert_called_once()

        # M2 强断言：daemon=True 必須傳入（process exit 時自動清理）
        call_kwargs = mock_thread_cls.call_args.kwargs
        assert call_kwargs.get("daemon") is True, (
            f"threading.Thread must be called with daemon=True, got kwargs={call_kwargs}"
        )

        # M3 强断言：target 必須是 callable wrapper，不能是 coroutine 物件
        import asyncio as _asyncio
        target = call_kwargs.get("target")
        assert callable(target), f"target must be callable, got {type(target).__name__}"
        assert not _asyncio.iscoroutine(target), (
            f"target must be a wrapper function, not a coroutine object: {target}"
        )

    def test_hook_skips_when_already_running(self, mocker, scanner_patches):
        """Codex-56D-P2: _clip_bg_index_running=True → threading.Thread 完全不被建。"""
        mocker.patch(
            "web.routers.scanner.load_config",
            return_value={**_BASE_SCANNER_CONFIG, "clip": {"enabled": True}},
        )
        import web.routers.scanner as scanner_mod
        # 模擬 bool flag 已為 True（另一個 thread 正在跑）
        original = scanner_mod._clip_bg_index_running
        scanner_mod._clip_bg_index_running = True
        mock_thread_cls = mocker.patch("web.routers.scanner.threading.Thread")

        try:
            from web.app import app
            client = TestClient(app)
            resp = client.get("/api/gallery/generate")
            assert resp.status_code == 200

            # Thread constructor should NOT have been called（已在跑，跳過）
            mock_thread_cls.assert_not_called()
        finally:
            scanner_mod._clip_bg_index_running = original

    def test_hook_atomic_check_and_set_no_race(self, mocker):
        """Codex-56D-P2: Lock-based atomic check-and-set 必須讓並發 caller 只 spawn 一個 thread。"""
        import threading
        import web.routers.scanner as scanner_mod

        # reset module state
        scanner_mod._clip_bg_index_running = False

        barrier = threading.Barrier(2)
        spawn_count = [0]

        def caller():
            barrier.wait()  # sync 兩 thread 同時抵達
            with scanner_mod._clip_bg_index_lock:
                if not scanner_mod._clip_bg_index_running:
                    scanner_mod._clip_bg_index_running = True
                    spawn_count[0] += 1

        t1 = threading.Thread(target=caller)
        t2 = threading.Thread(target=caller)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert spawn_count[0] == 1, (
            f"atomic check-and-set must allow only 1 spawn, got {spawn_count[0]}"
        )

        # cleanup
        scanner_mod._clip_bg_index_running = False

    def test_hook_exception_does_not_break_scanner(self, mocker, scanner_patches):
        """If load_config raises on the hook call, scanner SSE still completes normally."""
        call_count = [0]

        def load_config_side_effect():
            call_count[0] += 1
            # First call (scanner setup) returns normal config;
            # second call (hook) raises
            if call_count[0] <= 1:
                return {**_BASE_SCANNER_CONFIG, "clip": {"enabled": False}}
            raise RuntimeError("simulated config failure")

        mocker.patch(
            "web.routers.scanner.load_config",
            side_effect=load_config_side_effect,
        )

        from web.app import app
        client = TestClient(app)
        resp = client.get("/api/gallery/generate")
        # Scanner should still return 200 even if hook explodes
        assert resp.status_code == 200
        events = parse_sse(resp.text)
        # done event should still be present
        done_events = [e for e in events if e.get("type") == "done"]
        assert len(done_events) == 1
