"""
tests/unit/test_config_clip_migration.py
TDD-lite RED tests for load_config() clip migration block (56d T1a).
"""
import json
import hashlib
from pathlib import Path

import pytest


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


class TestClipMigration:
    def test_migration_no_clip_section(self, tmp_path, monkeypatch):
        """config.json 無 clip 區段 → load_config 補 default 並寫回；
        第二次 load_config 不再 migrate（file hash 不變）。"""
        import core.config as cfg_module

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"general": {"theme": "dark"}}), encoding="utf-8")

        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg_module, "CONFIG_DEFAULT_PATH", tmp_path / "no_default.json")

        hash_before = _file_hash(config_path)
        raw = cfg_module.load_config()

        # clip 欄位補齊
        assert raw.get("clip") == {"enabled": False, "model_path": None}
        # 檔案已寫回（hash 變了）
        assert _file_hash(config_path) != hash_before

        # 第二次載入 hash 不再變化
        hash_after_first = _file_hash(config_path)
        cfg_module.load_config()
        assert _file_hash(config_path) == hash_after_first

    def test_migration_partial_clip(self, tmp_path, monkeypatch):
        """config.json 含 {clip: {enabled: True}}（缺 model_path）
        → migration 後 enabled=True 保留、model_path=None 補上、檔案寫回。"""
        import core.config as cfg_module

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"clip": {"enabled": True}}), encoding="utf-8"
        )

        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg_module, "CONFIG_DEFAULT_PATH", tmp_path / "no_default.json")

        hash_before = _file_hash(config_path)
        raw = cfg_module.load_config()

        assert raw["clip"]["enabled"] is True
        assert raw["clip"]["model_path"] is None
        # 檔案因補缺而寫回
        assert _file_hash(config_path) != hash_before

    def test_migration_complete_clip_no_change(self, tmp_path, monkeypatch):
        """config.json 含完整 clip 區段且其他所有 migration 欄位齊全
        → clip migration 不動 clip 欄位，clip 區段 hash 不變。"""
        import core.config as cfg_module
        from core.config import AppConfig

        # 使用 AppConfig 預設 dump 作為基底（已含所有 migration 所需欄位），覆寫 clip
        # 移除 TranslateConfig 的 legacy 欄位（ollama_url / ollama_model）避免觸發 translate migration
        base = AppConfig().model_dump()
        base["clip"] = {"enabled": True, "model_path": "/x/m.onnx"}
        base["translate"].pop("ollama_url", None)
        base["translate"].pop("ollama_model", None)

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(base, indent=2, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg_module, "CONFIG_DEFAULT_PATH", tmp_path / "no_default.json")

        hash_before = _file_hash(config_path)
        raw = cfg_module.load_config()

        assert raw["clip"]["enabled"] is True
        assert raw["clip"]["model_path"] == "/x/m.onnx"
        # 所有 migration 欄位齊全 → 不觸發任何寫回
        assert _file_hash(config_path) == hash_before

    def test_migration_null_clip_section(self, tmp_path, monkeypatch):
        """config.json 含 {clip: null}（非 dict）→ migration 替換為 default dict 並寫回。"""
        import core.config as cfg_module

        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"clip": None}), encoding="utf-8")

        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg_module, "CONFIG_DEFAULT_PATH", tmp_path / "no_default.json")

        hash_before = _file_hash(config_path)
        raw = cfg_module.load_config()

        assert raw["clip"] == {"enabled": False, "model_path": None}
        assert _file_hash(config_path) != hash_before

    def test_migration_extra_clip_keys_preserved(self, tmp_path, monkeypatch):
        """config.json 含 {clip: {enabled: True, model_path: '/p', extra_key: 'x'}}
        → migration 不應移除 extra_key（只補缺，不刪除）。"""
        import core.config as cfg_module

        config_path = tmp_path / "config.json"
        config_path.write_text(
            json.dumps({"clip": {"enabled": True, "model_path": "/p", "extra_key": "x"}}),
            encoding="utf-8",
        )

        monkeypatch.setattr(cfg_module, "CONFIG_PATH", config_path)
        monkeypatch.setattr(cfg_module, "CONFIG_DEFAULT_PATH", tmp_path / "no_default.json")

        raw = cfg_module.load_config()

        assert raw["clip"]["extra_key"] == "x"
        assert raw["clip"]["enabled"] is True
        assert raw["clip"]["model_path"] == "/p"
