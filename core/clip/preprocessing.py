"""
影像 Preprocessing Pipeline
對應 plan-56a.md §1 CD-56A-3

純函式，無副作用：不寫檔案、不連 DB、不呼叫外部服務。
"""
import io

import numpy as np
from PIL import Image

# CLIP normalize 常數（來源：OpenAI CLIP 官方 repo + HuggingFace CLIPImageProcessor）
# ⚠️ 這不是 ImageNet 標準值（ImageNet mean ≈ [0.485, 0.456, 0.406]）
CLIP_MEAN = [0.48145466, 0.4578275, 0.40821073]
CLIP_STD = [0.26862954, 0.26130258, 0.27577711]


def right_half_crop(img: Image.Image) -> Image.Image:
    """裁取影像右側 50%，保留原始高度。

    Args:
        img: PIL Image 物件

    Returns:
        裁切後的 PIL Image（右側 50%）。
        若 img.width < 2，直接回傳原圖（防 crop 後 width=0）。
    """
    if img.width < 2:
        return img
    return img.crop((img.width // 2, 0, img.width, img.height))


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """完整 preprocessing pipeline（見 CD-56A-3）：

    PIL open → RGB → 右半裁切 → resize 224×224 → [0,1] → CLIP normalize → CHW → batch

    Args:
        image_bytes: 原始影像 bytes（JPEG / PNG / 任何 PIL 支援格式）

    Returns:
        shape (1, 3, 224, 224) float32 numpy array，供 InferenceSession.run() 直接使用。

    Raises:
        PIL.UnidentifiedImageError: 若 image_bytes 非合法影像格式。
        不在此層 catch（由上層 T5 indexer catch + log ERROR + skip）。
    """
    # 1. 載入並轉 RGB（去除 alpha / 灰階，確保三通道）
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # 2. 右半裁切（spec §1 Domain Knowledge 優化 1）
    img = right_half_crop(img)

    # 3. Resize 至 CLIP 標準輸入尺寸（Pillow 10+ API）
    img = img.resize((224, 224), Image.Resampling.LANCZOS)

    # 4. 轉 float32 並正規化至 [0, 1]
    arr = np.array(img, dtype=np.float32) / 255.0

    # 5. CLIP normalize（逐 channel，HWC broadcast）
    mean = np.array(CLIP_MEAN, dtype=np.float32).reshape(1, 1, 3)
    std = np.array(CLIP_STD, dtype=np.float32).reshape(1, 1, 3)
    arr = (arr - mean) / std

    # 6. HWC → CHW
    arr = np.transpose(arr, (2, 0, 1))

    # 7. 加 batch 維度 → (1, 3, 224, 224)
    arr = np.expand_dims(arr, axis=0)

    return arr
