"""
tests/unit/test_clip_provider_is_enabled.py
TDD-lite RED tests for LocalONNXProvider.is_enabled config-driven (56d T1a, CD-56D-11-B).
"""
import pytest


class TestIsEnabledConfigDriven:
    def test_is_enabled_false_when_config_disabled(self, tmp_path, monkeypatch):
        """mock config clip.enabled=False → is_enabled 回 False"""
        import core.config
        from core.clip.provider import LocalONNXProvider

        monkeypatch.setattr(
            core.config,
            "load_config",
            lambda: {"clip": {"enabled": False, "model_path": None}},
        )
        provider = LocalONNXProvider(tmp_path / "model.onnx")
        assert provider.is_enabled is False

    def test_is_enabled_false_when_no_clip_section(self, tmp_path, monkeypatch):
        """mock config 無 clip 區段 → is_enabled 回 False（opt-in 守 race）"""
        import core.config
        from core.clip.provider import LocalONNXProvider

        monkeypatch.setattr(
            core.config,
            "load_config",
            lambda: {"general": {"theme": "dark"}},
        )
        provider = LocalONNXProvider(tmp_path / "model.onnx")
        assert provider.is_enabled is False

    def test_is_enabled_true_when_config_enabled(self, tmp_path, monkeypatch):
        """mock config clip.enabled=True → is_enabled 回 True"""
        import core.config
        from core.clip.provider import LocalONNXProvider

        monkeypatch.setattr(
            core.config,
            "load_config",
            lambda: {"clip": {"enabled": True, "model_path": str(tmp_path / "model.onnx")}},
        )
        provider = LocalONNXProvider(tmp_path / "model.onnx")
        assert provider.is_enabled is True
