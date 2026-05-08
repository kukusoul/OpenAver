"""
T4: 影像 Preprocessing Pipeline - Unit Tests
TDD-lite: RED → GREEN
"""
import io
import pytest
import numpy as np
from PIL import Image


def _make_image_bytes(width=100, height=150, color=128, mode="RGB") -> bytes:
    """建立固定顏色的小影像 bytes，供測試使用（不需 mock）。
    JPEG 不支援 RGBA / L mode，對這些 mode 改用 PNG。
    """
    img = Image.new(mode, (width, height), color=color)
    buf = io.BytesIO()
    fmt = "PNG" if mode in ("RGBA", "L", "P", "LA") else "JPEG"
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestPreprocessImage:
    def test_output_shape(self):
        """正常 RGB 圖 → shape (1, 3, 224, 224)"""
        from core.clip.preprocessing import preprocess_image

        result = preprocess_image(_make_image_bytes())
        assert result.shape == (1, 3, 224, 224)

    def test_output_dtype_float32(self):
        """dtype == float32"""
        from core.clip.preprocessing import preprocess_image

        result = preprocess_image(_make_image_bytes())
        assert result.dtype == np.float32

    def test_values_normalized(self):
        """像素值不在 [0, 255] 範圍（已 normalize）"""
        from core.clip.preprocessing import preprocess_image

        result = preprocess_image(_make_image_bytes())
        # 正規化後值域大約在 [-3, 3]，肯定不全在 [0, 255]
        assert result.max() <= 10.0  # 不是原始 [0, 255] 尺度
        assert not np.isnan(result).any()
        assert not np.isinf(result).any()

    def test_rgba_input_no_exception(self):
        """RGBA 輸入不拋 exception，shape 正確"""
        from core.clip.preprocessing import preprocess_image

        result = preprocess_image(_make_image_bytes(mode="RGBA"))
        assert result.shape == (1, 3, 224, 224)

    def test_grayscale_input_no_exception(self):
        """灰階 L 輸入不拋 exception，shape 正確"""
        from core.clip.preprocessing import preprocess_image

        result = preprocess_image(_make_image_bytes(mode="L"))
        assert result.shape == (1, 3, 224, 224)

    def test_invalid_bytes_raises(self):
        """非圖像 bytes → PIL.UnidentifiedImageError 或 Exception"""
        from core.clip.preprocessing import preprocess_image

        with pytest.raises(Exception):
            preprocess_image(b"not an image at all")

    def test_width_one_no_crash(self):
        """width=1 影像不 crash，shape 輸出正確"""
        from core.clip.preprocessing import preprocess_image

        result = preprocess_image(_make_image_bytes(width=1, height=50))
        assert result.shape == (1, 3, 224, 224)

    def test_small_image_no_crash(self):
        """極小影像 (1×1) resize 拉伸至 224×224，正常輸出"""
        from core.clip.preprocessing import preprocess_image

        result = preprocess_image(_make_image_bytes(width=1, height=1))
        assert result.shape == (1, 3, 224, 224)


class TestRightHalfCrop:
    def test_normal_width(self):
        """100px 寬 → 裁切後 50px 寬，高度不變"""
        from core.clip.preprocessing import right_half_crop

        img = Image.new("RGB", (100, 150), color=128)
        result = right_half_crop(img)
        assert result.width == 50
        assert result.height == 150

    def test_width_one_guard(self):
        """width=1 不 crash，回傳原圖"""
        from core.clip.preprocessing import right_half_crop

        img = Image.new("RGB", (1, 50), color=128)
        result = right_half_crop(img)
        assert result.width == 1
        assert result.height == 50

    def test_right_half_content(self):
        """裁切後是右半邊（不是左半邊）"""
        from core.clip.preprocessing import right_half_crop

        # 建立左半紅、右半綠的圖像
        img = Image.new("RGB", (100, 10), color=(255, 0, 0))
        # 右半邊填綠色
        right_pixels = Image.new("RGB", (50, 10), color=(0, 255, 0))
        img.paste(right_pixels, (50, 0))

        result = right_half_crop(img)
        arr = np.array(result)
        # 裁切結果應該是綠色（右半邊）
        assert arr[0, 0, 1] > 200  # G channel 高
        assert arr[0, 0, 0] < 50   # R channel 低

    def test_odd_width_floor_division(self):
        """奇數寬度 (101px) → 裁切後 50px 寬（floor division）"""
        from core.clip.preprocessing import right_half_crop

        img = Image.new("RGB", (101, 100), color=128)
        result = right_half_crop(img)
        assert result.width == 101 - (101 // 2)  # 101 - 50 = 51
