"""
Smoke test：實際載入 ONNX 模型並推論（需要模型檔存在）。
標記 @pytest.mark.smoke，CI 排除。
若模型未下載，自動 skip（不 FAIL）。
"""
import pytest
import numpy as np
from pathlib import Path

MODEL_PATH = Path("output/models/clip/vision_model_quantized.onnx")


@pytest.mark.smoke
class TestClipSmoke:
    def test_model_file_exists(self):
        """模型檔案存在（若未下載則 skip）"""
        if not MODEL_PATH.exists():
            pytest.skip("CLIP model not downloaded, skip smoke test")

    def test_preprocess_image_output_shape(self):
        """preprocess_image() 回傳 (1,3,224,224) shape"""
        # 用 PIL 建假圖，不需要 ONNX
        import io
        from PIL import Image
        from core.clip.preprocessing import preprocess_image
        img = Image.new("RGB", (100, 150), color=128)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        result = preprocess_image(buf.getvalue())
        assert result.shape == (1, 3, 224, 224)
        assert result.dtype == np.float32

    @pytest.mark.smoke
    def test_onnx_inference(self, tmp_path):
        """實際載入 ONNX 模型並推論（需模型檔）"""
        if not MODEL_PATH.exists():
            pytest.skip("CLIP model not downloaded, skip smoke test")

        import io
        from PIL import Image
        import onnxruntime as ort
        from core.clip.preprocessing import preprocess_image

        # build test input
        img = Image.new("RGB", (200, 300), color=100)
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        tensor = preprocess_image(buf.getvalue())

        session = ort.InferenceSession(
            str(MODEL_PATH),
            providers=["CPUExecutionProvider"],
        )
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: tensor})
        embedding = outputs[0][0]  # shape (512,)

        assert embedding.shape == (512,)
        assert embedding.dtype == np.float32
        # cosine norm 應接近 1（CLIP output 通常已 normalize 或接近 normalize）
        norm = float(np.linalg.norm(embedding))
        assert 0.1 < norm < 100.0  # 合理值域（非 NaN、非 0）
