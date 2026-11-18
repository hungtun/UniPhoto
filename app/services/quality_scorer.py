import math
import os
from dataclasses import dataclass
from typing import Optional
import cv2
import numpy as np
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass


@dataclass
class PhotoQualityMetrics:
    width: int
    height: int
    quality_score: float
    sharpness_score: float
    exposure_score: float
    contrast_score: float


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _compute_sharpness(gray: np.ndarray) -> float:
    """Đánh giá độ sắc nét quang học (Laplacian Variance + 90th-percentile Sobel Edge).

    Kết hợp phương sai Laplacian toàn ảnh và phân vị thứ 90 của biên độ gradient Sobel
    để vừa phạt nặng ảnh rung/mờ nét (motion blur / out-of-focus), vừa không phạt nhầm
    ảnh chân dung/macro có hậu cảnh xóa phông (bokeh) nhưng chủ thể sắc nét.
    """
    denoised = cv2.GaussianBlur(gray, (3, 3), 0.5)

    lap = cv2.Laplacian(denoised, cv2.CV_32F)
    lap_var = float(lap.var())

    gx = cv2.Sobel(denoised, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(denoised, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(gx, gy)
    p90_grad = float(np.percentile(grad_mag, 90))

    lap_norm = _clamp(22.5 * math.log1p(lap_var / 7.5))
    edge_norm = _clamp((p90_grad / 56.0) * 100.0)

    return round(_clamp(0.60 * lap_norm + 0.40 * edge_norm), 1)


def _compute_exposure(lum: np.ndarray) -> float:
    """Đánh giá cân bằng phơi sáng & phạt vùng cháy sáng / bết tối."""
    mean_lum = float(np.mean(lum))

    # Vùng sáng tự nhiên lý tưởng nằm quanh 105 - 145 (trên thang 0 - 255)
    dist = max(0.0, abs(mean_lum - 125.0) - 18.0)
    brightness_balance = _clamp(100.0 - (dist / 110.0) * 85.0)

    over_exposed_ratio = float(np.mean(lum >= 250.0))
    under_exposed_ratio = float(np.mean(lum <= 5.0))

    clip_penalty = (
        max(0.0, over_exposed_ratio - 0.03) * 145.0
        + max(0.0, under_exposed_ratio - 0.05) * 115.0
    )

    return round(_clamp(brightness_balance - clip_penalty), 1)


def _compute_contrast_and_color(rgb: np.ndarray, lum: np.ndarray) -> float:
    """Đánh giá độ tương phản RMS, dải động (P95 - P5) và độ rực màu tự nhiên."""
    std_lum = float(np.std(lum))
    p5, p95 = np.percentile(lum, [5, 95])
    dynamic_spread = float(p95 - p5)

    r = rgb[:, :, 0].astype(np.float32)
    g = rgb[:, :, 1].astype(np.float32)
    b = rgb[:, :, 2].astype(np.float32)
    rg = r - g
    yb = 0.5 * (r + g) - b
    colorfulness = math.sqrt(float(np.var(rg) + np.var(yb))) + 0.3 * math.sqrt(
        float(np.mean(rg) ** 2 + np.mean(yb) ** 2)
    )

    std_norm = _clamp((std_lum / 58.0) * 90.0)
    spread_norm = _clamp((dynamic_spread / 175.0) * 92.0)
    color_norm = _clamp((colorfulness / 48.0) * 90.0)

    return round(_clamp(0.45 * std_norm + 0.35 * spread_norm + 0.20 * color_norm), 1)


def _compute_resolution_and_fidelity(
    width: int, height: int, file_size: int
) -> float:
    """Đánh giá độ phân giải gốc (Megapixels) và mật độ bit nén (chống ảnh nén vỡ hạt)."""
    pixels = max(1, width * height)
    megapixels = pixels / 1_000_000.0

    # Đường cong bão hòa mượt: ~1MP -> ~38đ, 2MP -> ~54đ, 8MP -> ~87đ, 12MP+ -> ~97-100đ
    res_norm = _clamp(26.5 * math.log1p(megapixels * 3.2))

    bits_per_pixel = (max(0, file_size) * 8.0) / pixels
    bpp_norm = _clamp(42.0 * math.log1p(bits_per_pixel * 2.2))

    return _clamp(0.72 * res_norm + 0.28 * bpp_norm)


def evaluate_photo_quality(
    file_path: str,
    img: Optional[Image.Image] = None,
    file_size: Optional[int] = None,
) -> Optional[PhotoQualityMetrics]:
    """Chấm điểm tổng hợp chất lượng ảnh (0 - 100) dựa trên 4 nhóm tiêu chí thị giác:
    - Độ sắc nét (Sharpness: 38%)
    - Độ phân giải & Chất lượng nén gốc (Resolution & Fidelity: 28%)
    - Cân bằng ánh sáng (Exposure: 18%)
    - Độ tương phản & Màu sắc (Contrast & Color: 16%)
    """
    try:
        actual_size = (
            file_size
            if file_size is not None
            else (os.path.getsize(file_path) if os.path.exists(file_path) else 0)
        )

        close_after = False
        if img is None:
            img = Image.open(file_path)
            close_after = True

        try:
            oriented = ImageOps.exif_transpose(img)
            orig_w, orig_h = oriented.size

            # Chuẩn hóa kích thước phân tích thị giác về tối đa 768px để đo độ nét công bằng
            # giữa các độ phân giải khác nhau và tối ưu tốc độ (~3-6ms/ảnh).
            max_analysis_dim = 768
            if max(orig_w, orig_h) > max_analysis_dim:
                scale = max_analysis_dim / float(max(orig_w, orig_h))
                new_size = (
                    max(1, int(round(orig_w * scale))),
                    max(1, int(round(orig_h * scale))),
                )
                sample = oriented.convert("RGB").resize(
                    new_size, Image.Resampling.BILINEAR
                )
            else:
                sample = oriented.convert("RGB")

            rgb = np.asarray(sample, dtype=np.uint8)
        finally:
            if close_after:
                img.close()

        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        lum = (
            0.299 * rgb[:, :, 0].astype(np.float32)
            + 0.587 * rgb[:, :, 1].astype(np.float32)
            + 0.114 * rgb[:, :, 2].astype(np.float32)
        )

        sharpness = _compute_sharpness(gray)
        exposure = _compute_exposure(lum)
        contrast = _compute_contrast_and_color(rgb, lum)
        res_fidelity = _compute_resolution_and_fidelity(orig_w, orig_h, actual_size)

        composite = (
            0.38 * sharpness
            + 0.28 * res_fidelity
            + 0.18 * exposure
            + 0.16 * contrast
        )

        return PhotoQualityMetrics(
            width=orig_w,
            height=orig_h,
            quality_score=round(_clamp(composite), 1),
            sharpness_score=sharpness,
            exposure_score=exposure,
            contrast_score=contrast,
        )
    except Exception as exc:
        print(f"Không thể chấm điểm ảnh {file_path}: {exc}")
        return None

