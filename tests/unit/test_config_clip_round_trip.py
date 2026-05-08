"""
tests/unit/test_config_clip_round_trip.py
TDD-lite RED tests for AppConfig ClipConfig round-trip (56d T1a).
"""
import pytest


class TestAppConfigClipRoundTrip:
    def test_appconfig_clip_round_trip(self):
        """AppConfig.model_validate({clip: {enabled: True, model_path: '/tmp/m.onnx'}})
        → model_dump() 應完整保留 clip 欄位，不因未知欄位被丟棄。"""
        from core.config import AppConfig

        data = {"clip": {"enabled": True, "model_path": "/tmp/m.onnx"}}
        config = AppConfig.model_validate(data)
        dumped = config.model_dump()

        assert "clip" in dumped
        assert dumped["clip"]["enabled"] is True
        assert dumped["clip"]["model_path"] == "/tmp/m.onnx"

    def test_appconfig_clip_default(self):
        """AppConfig() 不傳 clip → default 為 {enabled: False, model_path: None}"""
        from core.config import AppConfig

        dumped = AppConfig().model_dump()

        assert "clip" in dumped
        assert dumped["clip"] == {"enabled": False, "model_path": None}
