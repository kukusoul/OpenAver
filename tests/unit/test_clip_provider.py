"""
tests/unit/test_clip_provider.py
TDD-lite tests for CLIPProvider ABC and LocalONNXProvider skeleton (T2).
"""
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

    def test_model_sha256_pending(self):
        """LocalONNXProvider.MODEL_SHA256 == 'PENDING'（T3 填入前）"""
        from core.clip.provider import LocalONNXProvider

        assert LocalONNXProvider.MODEL_SHA256 == "PENDING"

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
