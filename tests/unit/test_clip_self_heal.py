"""
tests/unit/test_clip_self_heal.py
TDD-lite tests for _clip_self_heal_on_startup (CD-56D-6).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(model_id: str = "clip-vit-b32-int8-xenova-v1", is_enabled: bool = True):
    provider = MagicMock()
    provider.model_id = model_id
    type(provider).is_enabled = property(lambda self: is_enabled)
    return provider


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestClipSelfHeal:

    def test_self_heal_noop_when_disabled(self, mocker):
        """clip.enabled=False → return immediately, do NOT call get_provider, do NOT touch DB."""
        mocker.patch("web.app.load_config", return_value={"clip": {"enabled": False}})
        mock_get_provider = mocker.patch("web.app.get_provider")
        mock_repo_cls = mocker.patch("web.app.VideoRepository")

        from web.app import _clip_self_heal_on_startup
        asyncio.run(_clip_self_heal_on_startup())

        mock_get_provider.assert_not_called()
        mock_repo_cls.assert_not_called()

    def test_self_heal_disables_when_model_missing(self, mocker, tmp_path):
        """clip.enabled=True but model file does not exist → save_config with enabled=False, no crash."""
        missing_model = tmp_path / "no_such_model.onnx"
        mocker.patch("web.app.load_config", return_value={
            "clip": {"enabled": True, "model_path": str(missing_model)}
        })
        mock_save = mocker.patch("web.app.save_config")
        mock_get_provider = mocker.patch("web.app.get_provider")

        from web.app import _clip_self_heal_on_startup
        asyncio.run(_clip_self_heal_on_startup())

        # save_config must be called with enabled=False
        mock_save.assert_called_once()
        saved_cfg = mock_save.call_args[0][0]
        assert saved_cfg["clip"]["enabled"] is False

        # get_provider must NOT be called
        mock_get_provider.assert_not_called()

    def test_self_heal_noop_when_no_stale(self, mocker, tmp_path):
        """clip.enabled=True + model exists + all DB rows have matching model_id → no UPDATE."""
        model_file = tmp_path / "vision_model_quantized.onnx"
        model_file.write_bytes(b"fake")

        current_model_id = "clip-vit-b32-int8-xenova-v1"
        provider = _make_provider(model_id=current_model_id)

        mocker.patch("web.app.load_config", return_value={
            "clip": {"enabled": True, "model_path": str(model_file)}
        })
        mocker.patch("web.app.get_provider", return_value=provider)

        # Mock VideoRepository and its _get_connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # DB returns only current model_id → no stale
        mock_cursor.fetchall.return_value = [(current_model_id,)]
        mock_conn.execute.return_value = mock_cursor

        mock_repo = MagicMock()
        mock_repo._get_connection.return_value = mock_conn
        mocker.patch("web.app.VideoRepository", return_value=mock_repo)

        from web.app import _clip_self_heal_on_startup
        asyncio.run(_clip_self_heal_on_startup())

        # Should call _get_connection once for SELECT, but no UPDATE
        assert mock_repo._get_connection.call_count == 1
        # The single execute call should be the SELECT, no UPDATE
        executed_sqls = [c[0][0] for c in mock_conn.execute.call_args_list]
        assert not any("UPDATE" in sql for sql in executed_sqls)

    def test_self_heal_clears_stale_rows(self, mocker, tmp_path):
        """clip.enabled=True + model exists + DB has stale model_id → UPDATE clears them."""
        model_file = tmp_path / "vision_model_quantized.onnx"
        model_file.write_bytes(b"fake")

        current_model_id = "clip-vit-b32-int8-v2"
        stale_model_id = "clip-vit-b32-int8-xenova-v1"
        provider = _make_provider(model_id=current_model_id)

        mocker.patch("web.app.load_config", return_value={
            "clip": {"enabled": True, "model_path": str(model_file)}
        })
        mocker.patch("web.app.get_provider", return_value=provider)

        # Two separate connections: one for SELECT, one for UPDATE
        mock_conn_select = MagicMock()
        mock_cursor_select = MagicMock()
        mock_cursor_select.fetchall.return_value = [(stale_model_id,)]
        mock_conn_select.execute.return_value = mock_cursor_select

        mock_conn_update = MagicMock()
        mock_cursor_update = MagicMock()
        mock_cursor_update.rowcount = 3  # simulates 3 rows cleared
        mock_conn_update.execute.return_value = mock_cursor_update

        mock_repo = MagicMock()
        mock_repo._get_connection.side_effect = [mock_conn_select, mock_conn_update]
        mocker.patch("web.app.VideoRepository", return_value=mock_repo)

        from web.app import _clip_self_heal_on_startup
        asyncio.run(_clip_self_heal_on_startup())

        # Should open two connections (SELECT + UPDATE)
        assert mock_repo._get_connection.call_count == 2

        # UPDATE should have been called on second connection
        update_calls = mock_conn_update.execute.call_args_list
        assert len(update_calls) == 1
        update_sql = update_calls[0][0][0]
        assert "UPDATE" in update_sql
        assert "clip_embedding" in update_sql

        # commit should be called on update connection
        mock_conn_update.commit.assert_called_once()

        # both connections should be closed
        mock_conn_select.close.assert_called_once()
        mock_conn_update.close.assert_called_once()

        # M1 强断言：logger.info 被呼叫且回報正確清除數量（rowcount=3）
        # Re-run with a fresh side_effect and logger spy to verify cleared count
        mock_repo._get_connection.side_effect = [mock_conn_select, mock_conn_update]
        mock_cursor_select.fetchall.return_value = [(stale_model_id,)]
        mock_cursor_update.rowcount = 3
        mock_conn_select.reset_mock()
        mock_conn_update.reset_mock()

        mock_logger_info = mocker.patch("web.app.logger.info")
        asyncio.run(_clip_self_heal_on_startup())
        mock_logger_info.assert_called_once()
        log_call_args = mock_logger_info.call_args
        # logger.info("CLIP self-heal: cleared %d rows ...", cleared, sorted(stale))
        # args[1] is the cleared count (rowcount = 3)
        assert log_call_args.args[1] == 3, (
            f"logger should report 3 cleared rows, got {log_call_args}"
        )
