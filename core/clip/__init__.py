"""
core/clip/__init__.py
Singleton factory for CLIPProvider.

Usage:
    from core.clip import get_provider
    provider = get_provider()
"""
from __future__ import annotations

from pathlib import Path

from core.clip.provider import LocalONNXProvider

# TODO: read default path from core/config.py once a config key is defined (T3+).
_DEFAULT_MODEL_PATH = Path.home() / "OpenAver" / "models" / "vision_model_quantized.onnx"

_provider: LocalONNXProvider | None = None


def get_provider(model_path: Path | None = None) -> LocalONNXProvider:
    """Return the module-level LocalONNXProvider singleton.

    First call creates the instance using *model_path* (falls back to the
    default path when omitted).  Subsequent calls ignore *model_path* and
    return the already-created instance.

    Args:
        model_path: Optional path to the .onnx model file.  Only used on the
            first call; ignored afterwards.

    Returns:
        The shared LocalONNXProvider instance.
    """
    global _provider
    if _provider is None:
        if model_path is None:
            model_path = _DEFAULT_MODEL_PATH
        _provider = LocalONNXProvider(model_path)
    return _provider
