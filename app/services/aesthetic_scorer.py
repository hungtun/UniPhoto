import hashlib
import json
import math
import os
import ssl
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure Matplotlib/MediaPipe cache writes to a persistent writable folder before importing mediapipe.
# Note: PyInstaller's built-in pyi_rth_mplconfig hook sets MPLCONFIGDIR to an empty random temp dir
# on every launch; override that with a bundle-keyed persistent directory so font cache builds at most once.
_temp_root = Path(tempfile.gettempdir())
if getattr(sys, "frozen", False):
    _bundle_key = hashlib.sha256(
        str(Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()).encode("utf-8")
    ).hexdigest()[:10]
    _frozen_mpl_dir = _temp_root / f"uniphoto-mpl-{_bundle_key}"
    try:
        _frozen_mpl_dir.mkdir(parents=True, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = str(_frozen_mpl_dir)
    except OSError:
        os.environ.setdefault("MPLCONFIGDIR", str(_temp_root / "uniphoto-mpl"))
else:
    os.environ.setdefault("MPLCONFIGDIR", str(_temp_root / "uniphoto-mpl"))

import cv2
import numpy as np
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CANONICAL_AESTHETIC_TAGS, TAG_PRIORITY_ORDER
from app.models.models import Cluster, Photo
from app.repositories.photo_repository import photo_repo
from app.services.progress_tracker import (
    is_cancel_requested,
    reset_cancel,
    update_progress,
)
from app.services.quality_scorer import evaluate_photo_quality

# Keep CPU thermal footprint cool on macOS laptops
cv2.setNumThreads(1)

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None  # type: ignore[assignment]


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = PROJECT_ROOT / "data" / "models"
FACE_TASK_PATH = MODELS_DIR / "face_landmarker.task"

FACE_TASK_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

_DOWNLOAD_ATTEMPTED: set[str] = set()
_FACE_LANDMARKER: Any = None
_LANDMARKER_INITIALIZED: bool = False
_HAAR_FACE: Optional[cv2.CascadeClassifier] = None
_HAAR_EYE: Optional[cv2.CascadeClassifier] = None
_HAAR_INITIALIZED: bool = False


@dataclass
class PhotoAestheticMetrics:
    aesthetic_score: float
    composition_score: float
    face_score: Optional[float]
    pose_score: Optional[float]
    tilt_angle: float
    has_closed_eyes: bool
    aesthetic_tags: List[str]


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _candidate_face_task_paths() -> List[Path]:
    candidates: List[Path] = []
    env_models_dir = os.environ.get("UNIPHOTO_MODELS_DIR", "").strip()
    if env_models_dir:
        candidates.append(Path(env_models_dir).expanduser() / "face_landmarker.task")
    if settings.BUNDLED_MODELS_DIR.strip():
        bundled_cand = (
            Path(settings.BUNDLED_MODELS_DIR.strip()).expanduser()
            / "face_landmarker.task"
        )
        if bundled_cand not in candidates:
            candidates.append(bundled_cand)
    candidates.append(
        Path(settings.DATA_DIR).expanduser() / "models" / "face_landmarker.task"
    )
    candidates.append(PROJECT_ROOT / "data" / "models" / "face_landmarker.task")
    return candidates


def _resolve_face_task_path() -> Optional[Path]:
    for cand in _candidate_face_task_paths():
        try:
            if cand.is_file() and cand.stat().st_size > 10_000:
                return cand
        except OSError:
            continue
    return None


def _ensure_model_file(dest_path: Path, url: str, timeout: float = 2.5) -> bool:
    """Return True if .task file exists locally or downloads cleanly; False on offline/error."""
    try:
        if dest_path.is_file() and dest_path.stat().st_size > 10_000:
            return True
    except OSError:
        return False

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    key = str(dest_path)
    if key in _DOWNLOAD_ATTEMPTED:
        return False
    _DOWNLOAD_ATTEMPTED.add(key)

    tmp_path = dest_path.with_suffix(".task.tmp")
    try:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={"User-Agent": "UniPhoto/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            data = resp.read()
        if len(data) > 10_000:
            with open(tmp_path, "wb") as f:
                f.write(data)
            os.replace(tmp_path, dest_path)
            return True
    except Exception:
        pass
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    return False


def _get_face_landmarker() -> Any:
    """Lazily initialize MediaPipe Tasks FaceLandmarker using offline-first model lookup."""
    global _FACE_LANDMARKER, _LANDMARKER_INITIALIZED
    if _LANDMARKER_INITIALIZED:
        return _FACE_LANDMARKER

    _LANDMARKER_INITIALIZED = True
    if mp is None or not hasattr(mp, "tasks"):
        return None

    task_path = _resolve_face_task_path()
    if task_path is None:
        writable_dest = (
            Path(settings.DATA_DIR).expanduser() / "models" / "face_landmarker.task"
        )
        if _ensure_model_file(writable_dest, FACE_TASK_URL):
            task_path = writable_dest

    if task_path is not None:
        try:
            options = mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(task_path)),
                running_mode=mp.tasks.vision.RunningMode.IMAGE,
                num_faces=5,
                min_face_detection_confidence=0.30,
                min_face_presence_confidence=0.30,
                output_face_blendshapes=True,
            )
            _FACE_LANDMARKER = mp.tasks.vision.FaceLandmarker.create_from_options(options)
        except Exception:
            try:
                options = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(
                        model_asset_buffer=task_path.read_bytes()
                    ),
                    running_mode=mp.tasks.vision.RunningMode.IMAGE,
                    num_faces=5,
                    min_face_detection_confidence=0.30,
                    min_face_presence_confidence=0.30,
                    output_face_blendshapes=True,
                )
                _FACE_LANDMARKER = mp.tasks.vision.FaceLandmarker.create_from_options(
                    options
                )
            except Exception:
                _FACE_LANDMARKER = None

    return _FACE_LANDMARKER


def _get_haar_cascades() -> Tuple[Optional[cv2.CascadeClassifier], Optional[cv2.CascadeClassifier]]:
    """Load OpenCV Haar cascades if available on disk without raising on OpenCV 5 wheels."""
    global _HAAR_FACE, _HAAR_EYE, _HAAR_INITIALIZED
    if _HAAR_INITIALIZED:
        return _HAAR_FACE, _HAAR_EYE

    _HAAR_INITIALIZED = True
    base_dirs: List[Path] = []
    env_models_dir = os.environ.get("UNIPHOTO_MODELS_DIR", "").strip()
    if env_models_dir:
        base_dirs.append(Path(env_models_dir).expanduser())
    cv_haar = getattr(getattr(cv2, "data", None), "haarcascades", None)
    if cv_haar:
        base_dirs.append(Path(cv_haar))
    base_dirs.extend(
        [
            Path(settings.DATA_DIR).expanduser() / "models",
            MODELS_DIR,
            Path("/opt/homebrew/share/opencv4/haarcascades"),
            Path("/usr/local/share/opencv4/haarcascades"),
        ]
    )

    for d in base_dirs:
        face_xml = d / "haarcascade_frontalface_default.xml"
        eye_xml = d / "haarcascade_eye.xml"
        if face_xml.is_file() and eye_xml.is_file():
            fc = cv2.CascadeClassifier(str(face_xml))
            ec = cv2.CascadeClassifier(str(eye_xml))
            if not fc.empty() and not ec.empty():
                _HAAR_FACE = fc
                _HAAR_EYE = ec
                break

    return _HAAR_FACE, _HAAR_EYE


def _load_rgb_image(file_path: str, max_dim: int = 960) -> Optional[np.ndarray]:
    try:
        with Image.open(file_path) as img:
            oriented = ImageOps.exif_transpose(img)
            w, h = oriented.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                new_size = (
                    max(1, int(round(w * scale))),
                    max(1, int(round(h * scale))),
                )
                rgb_img = oriented.convert("RGB").resize(
                    new_size, Image.Resampling.BILINEAR
                )
            else:
                rgb_img = oriented.convert("RGB")
            return np.ascontiguousarray(np.asarray(rgb_img, dtype=np.uint8))
    except Exception:
        bgr = None
        try:
            raw = np.fromfile(file_path, dtype=np.uint8)
            if raw.size > 0:
                bgr = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        except Exception:
            bgr = None
        if bgr is None:
            try:
                bgr = cv2.imread(file_path)
            except Exception:
                bgr = None
        if bgr is None:
            return None
        h, w = bgr.shape[:2]
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            bgr = cv2.resize(
                bgr,
                (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                interpolation=cv2.INTER_LINEAR,
            )
        return np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


# ---------------------------------------------------------------------------
# 1. Composition, Horizon Tilt & Rule of Thirds
# ---------------------------------------------------------------------------


def _estimate_camera_tilt(gray_u8: np.ndarray) -> Tuple[float, bool]:
    """Estimate accidental camera roll angle (abs degrees in [0, 18]) and line confidence.

    Uses Canny + HoughLinesP inside the interior 94% of the frame (avoiding outer frame
    border artifacts) and unifies near-horizontal (-18°..+18°) and near-vertical lines
    into a common signed roll angle so genuine structural tilt forms a coherent peak.
    """
    h, w = gray_u8.shape[:2]
    mx = max(4, int(round(w * 0.03)))
    my = max(4, int(round(h * 0.03)))
    if w <= 2 * mx + 16 or h <= 2 * my + 16:
        return 0.0, False

    interior = gray_u8[my : h - my, mx : w - mx]
    ih, iw = interior.shape[:2]

    blurred = cv2.GaussianBlur(interior, (5, 5), 1.1)
    edges = cv2.Canny(blurred, 55, 150)

    min_line_len = max(24, int(round(min(iw, ih) * 0.10)))
    max_line_gap = max(8, int(round(min(iw, ih) * 0.025)))
    lines = cv2.HoughLinesP(
        edges,
        rho=1.0,
        theta=np.pi / 180.0,
        threshold=36,
        minLineLength=min_line_len,
        maxLineGap=max_line_gap,
    )
    if lines is None or len(lines) == 0:
        return 0.0, False

    samples: List[Tuple[float, float]] = []
    zero_axis_samples: List[Tuple[float, float]] = []

    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        dx = float(x2 - x1)
        dy = float(y2 - y1)
        length = math.hypot(dx, dy)
        if length < min_line_len:
            continue

        if abs(dx) >= abs(dy):
            if dx < 0:
                dx, dy = -dx, -dy
            dev = math.degrees(math.atan2(dy, dx))
        else:
            if dy < 0:
                dx, dy = -dx, -dy
            dev = -math.degrees(math.atan2(dx, dy))

        if abs(dev) > 18.0:
            continue

        if abs(dev) < 0.3:
            if length >= min(iw, ih) * 0.14:
                zero_axis_samples.append((dev, length))
        else:
            samples.append((dev, length))

    tilted_weight = sum(w_len for _, w_len in samples)
    zero_weight = sum(w_len for _, w_len in zero_axis_samples)

    if tilted_weight > 0 and tilted_weight >= zero_weight * 1.35:
        combined = samples
    else:
        combined = samples + zero_axis_samples

    total_weight = sum(w_len for _, w_len in combined)
    if total_weight < min(iw, ih) * 0.35:
        return 0.0, False

    best_center = 0.0
    best_cluster_weight = 0.0
    grid = np.linspace(-18.0, 18.0, 145)
    for center in grid:
        w_sum = 0.0
        for ang, w_len in combined:
            diff = abs(ang - float(center))
            if diff <= 1.35:
                w_sum += w_len * (1.0 - 0.35 * (diff / 1.35))
        if w_sum > best_cluster_weight:
            best_cluster_weight = w_sum
            best_center = float(center)

    concentration = best_cluster_weight / max(1e-6, total_weight)
    if concentration < 0.38:
        return 0.0, False

    cluster_members = [(ang, w_len) for ang, w_len in combined if abs(ang - best_center) <= 1.5]
    if not cluster_members:
        return 0.0, False

    refined_signed = sum(ang * w_len for ang, w_len in cluster_members) / sum(
        w_len for _, w_len in cluster_members
    )
    return round(abs(refined_signed), 1), True


def _evaluate_composition(rgb: np.ndarray, gray_u8: np.ndarray) -> Tuple[float, float, List[str]]:
    """Compute composition_score (0..100), abs tilt_angle, and composition canonical tags."""
    h, w = gray_u8.shape[:2]
    tags: List[str] = []

    abs_tilt, confident_lines = _estimate_camera_tilt(gray_u8)

    # Saliency map: Sobel edge energy + color contrast from outer border background
    gray_f = gray_u8.astype(np.float32)
    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    grad_mag = cv2.magnitude(gx, gy)
    grad_norm = grad_mag / (float(np.percentile(grad_mag, 98)) + 1e-5)
    grad_norm = np.clip(grad_norm, 0.0, 1.5)

    rgb_f = rgb.astype(np.float32)
    border_strip = max(4, int(round(min(h, w) * 0.04)))
    border_pixels = np.concatenate(
        [
            rgb_f[:border_strip, :, :].reshape(-1, 3),
            rgb_f[-border_strip:, :, :].reshape(-1, 3),
            rgb_f[:, :border_strip, :].reshape(-1, 3),
            rgb_f[:, -border_strip:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg_color = np.median(border_pixels, axis=0)
    color_dist = np.linalg.norm(rgb_f - bg_color, axis=2)
    color_norm = np.clip(color_dist / (float(np.percentile(color_dist, 98)) + 1e-5), 0.0, 1.5)

    saliency = 0.58 * grad_norm + 0.42 * color_norm
    saliency = cv2.GaussianBlur(saliency, (9, 9), 2.0)

    # Keep top 25% most salient energy for subject placement analysis
    thresh = float(np.percentile(saliency, 75))
    sal_top = np.maximum(0.0, saliency - thresh)
    total_sal = float(np.sum(sal_top))

    if total_sal > 1e-5:
        ys, xs = np.indices((h, w), dtype=np.float32)
        cx_norm = float(np.sum(xs * sal_top) / total_sal) / max(1.0, float(w - 1))
        cy_norm = float(np.sum(ys * sal_top) / total_sal) / max(1.0, float(h - 1))
    else:
        cx_norm, cy_norm = 0.5, 0.5

    power_points = [
        (1.0 / 3.0, 1.0 / 3.0),
        (2.0 / 3.0, 1.0 / 3.0),
        (1.0 / 3.0, 2.0 / 3.0),
        (2.0 / 3.0, 2.0 / 3.0),
    ]
    d_rot = min(math.hypot(cx_norm - px, cy_norm - py) for px, py in power_points)
    d_line = min(
        abs(cx_norm - 1.0 / 3.0),
        abs(cx_norm - 2.0 / 3.0),
        abs(cy_norm - 1.0 / 3.0),
        abs(cy_norm - 2.0 / 3.0),
    )

    rot_score = _clamp(96.0 - (d_rot / 0.34) * 44.0, 42.0, 98.0)

    # Border clipping check ("edge_subject")
    edge_w = max(3, int(round(w * 0.035)))
    edge_h = max(3, int(round(h * 0.035)))
    interior_mask = np.zeros((h, w), dtype=np.float32)
    interior_mask[edge_h : h - edge_h, edge_w : w - edge_w] = 1.0
    border_sal_ratio = (
        float(np.sum(sal_top * (1.0 - interior_mask))) / total_sal if total_sal > 1e-5 else 0.0
    )
    edge_clipped = (
        cx_norm < 0.11
        or cx_norm > 0.89
        or cy_norm < 0.11
        or cy_norm > 0.89
        or border_sal_ratio > 0.30
    )

    # Horizon / camera stability subscore
    if confident_lines:
        if abs_tilt <= 1.2:
            horizon_score = 95.0 - abs_tilt * 4.0
            tags.append("level_horizon")
        elif 1.8 <= abs_tilt <= 14.0:
            horizon_score = _clamp(68.0 - (abs_tilt - 1.8) * 3.8, 22.0, 68.0)
            tags.append("tilted_horizon")
        elif abs_tilt > 14.0:
            horizon_score = 45.0
        else:
            horizon_score = 84.0
    else:
        horizon_score = 82.0

    comp_score = 0.54 * rot_score + 0.46 * horizon_score

    if edge_clipped:
        comp_score -= 14.0
        tags.append("edge_subject")
    elif d_rot <= 0.145 or (d_rot <= 0.19 and d_line <= 0.06):
        comp_score += 4.0
        tags.append("rule_of_thirds")

    if "tilted_horizon" in tags:
        comp_score -= min(18.0, 6.0 + (abs_tilt - 1.8) * 1.4)

    return round(_clamp(comp_score), 1), abs_tilt, tags


# ---------------------------------------------------------------------------
# 2. Face Focus & Closed-Eye Detection (MediaPipe -> Offline Haar / Pure CV)
# ---------------------------------------------------------------------------


def _compute_roi_sharpness(gray_roi: np.ndarray) -> float:
    """Resolution-normalized sharpness (0..100) for a face ROI."""
    rh, rw = gray_roi.shape[:2]
    if rh < 12 or rw < 12:
        return 50.0
    max_dim = 300
    if max(rh, rw) > max_dim:
        scale = max_dim / float(max(rh, rw))
        gray_roi = cv2.resize(
            gray_roi,
            (max(12, int(round(rw * scale))), max(12, int(round(rh * scale)))),
            interpolation=cv2.INTER_LINEAR,
        )
    gray_f = cv2.GaussianBlur(gray_roi.astype(np.float32), (3, 3), 0.5)
    lap_var = float(cv2.Laplacian(gray_f, cv2.CV_32F).var())
    gx = cv2.Sobel(gray_f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray_f, cv2.CV_32F, 0, 1, ksize=3)
    p90_grad = float(np.percentile(cv2.magnitude(gx, gy), 90))

    lap_norm = _clamp(20.0 * math.log1p(max(0.0, lap_var - 8.0) / 8.5))
    edge_norm = _clamp((p90_grad / 58.0) * 100.0)
    if lap_var < 22.0:
        return _clamp(0.82 * lap_norm + 0.18 * edge_norm)
    return _clamp(0.68 * lap_norm + 0.32 * edge_norm)


def _compute_mp_ear(
    landmarks: Any, indices: List[int], det_w: float = 1.0, det_h: float = 1.0
) -> float:
    pts = [(landmarks[i].x * det_w, landmarks[i].y * det_h) for i in indices]
    v1 = math.hypot(pts[1][0] - pts[5][0], pts[1][1] - pts[5][1])
    v2 = math.hypot(pts[2][0] - pts[4][0], pts[2][1] - pts[4][1])
    horiz = math.hypot(pts[0][0] - pts[3][0], pts[0][1] - pts[3][1])
    if horiz < 1e-6:
        return 0.25
    return (v1 + v2) / (2.0 * horiz)


def _extract_mp_faces_from_region(
    face_landmarker: Any,
    region_rgb: np.ndarray,
    gray_u8: np.ndarray,
    offset_x: int,
    offset_y: int,
    region_w: int,
    region_h: int,
    upscale: bool,
) -> Optional[List[Tuple[int, float, bool]]]:
    """Run FaceLandmarker on a region (optionally upscaled 1.6x) and map boxes to full-frame."""
    if region_w < 24 or region_h < 24:
        return []

    if upscale and max(region_h, region_w) < 960:
        det_w = max(1, int(round(region_w * 1.6)))
        det_h = max(1, int(round(region_h * 1.6)))
        det_rgb = np.ascontiguousarray(
            cv2.resize(region_rgb, (det_w, det_h), interpolation=cv2.INTER_CUBIC)
        )
    else:
        det_h, det_w = region_rgb.shape[:2]
        det_rgb = np.ascontiguousarray(region_rgb)

    try:
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=det_rgb)
        result = face_landmarker.detect(mp_img)
    except Exception:
        return None

    face_landmarks_list = getattr(result, "face_landmarks", None) or []
    if not face_landmarks_list:
        return []

    full_h, full_w = gray_u8.shape[:2]
    min_face_area = 0.002 * (full_w * full_h)
    blendshapes_list = getattr(result, "face_blendshapes", None) or []

    entries: List[Tuple[int, float, bool]] = []
    for idx, lms in enumerate(face_landmarks_list):
        full_xs = [offset_x + lm.x * region_w for lm in lms]
        full_ys = [offset_y + lm.y * region_h for lm in lms]
        x1 = max(0, int(math.floor(min(full_xs))))
        y1 = max(0, int(math.floor(min(full_ys))))
        x2 = min(full_w, int(math.ceil(max(full_xs))))
        y2 = min(full_h, int(math.ceil(max(full_ys))))
        fw, fh = max(1, x2 - x1), max(1, y2 - y1)
        area = fw * fh
        if area < min_face_area:
            continue

        blink_l, blink_r = 0.0, 0.0
        if idx < len(blendshapes_list) and blendshapes_list[idx]:
            for cat in blendshapes_list[idx]:
                name = getattr(cat, "category_name", "")
                if name == "eyeBlinkLeft":
                    blink_l = float(getattr(cat, "score", 0.0))
                elif name == "eyeBlinkRight":
                    blink_r = float(getattr(cat, "score", 0.0))

        ear_l = _compute_mp_ear(lms, [33, 160, 158, 133, 153, 144], det_w, det_h)
        ear_r = _compute_mp_ear(lms, [362, 385, 387, 263, 373, 380], det_w, det_h)
        mean_ear = 0.5 * (ear_l + ear_r)
        max_blink = max(blink_l, blink_r)

        is_closed = (
            blink_l >= 0.50
            or blink_r >= 0.50
            or mean_ear < 0.195
            or (mean_ear < 0.22 and max_blink >= 0.20)
        )
        sharp = _compute_roi_sharpness(gray_u8[y1:y2, x1:x2])
        entries.append((area, sharp, is_closed))

    return entries


def _evaluate_faces_mediapipe(
    face_landmarker: Any, rgb: np.ndarray, gray_u8: np.ndarray
) -> Optional[Tuple[Optional[float], bool, List[str]]]:
    if face_landmarker is None or mp is None:
        return None

    h, w = gray_u8.shape[:2]

    # Pass 1: Full-frame detection
    face_entries = _extract_mp_faces_from_region(
        face_landmarker, rgb, gray_u8, 0, 0, w, h, upscale=False
    )
    if face_entries is None:
        return None

    # Pass 2: Upper-center portrait crop (1.6x INTER_CUBIC when < 960) for medium/full-body portraits
    if not face_entries:
        cy1, cy2 = 0, int(round(0.68 * h))
        cx1, cx2 = int(round(0.14 * w)), int(round(0.86 * w))
        crop_entries = _extract_mp_faces_from_region(
            face_landmarker,
            rgb[cy1:cy2, cx1:cx2],
            gray_u8,
            cx1,
            cy1,
            cx2 - cx1,
            cy2 - cy1,
            upscale=True,
        )
        if crop_entries:
            face_entries = crop_entries

    # Pass 3: Tighter upper-portrait head sub-crops for distant full-body portraits (~6-10% face height)
    if not face_entries:
        sub_crops = [
            (0, int(round(0.42 * h)), int(round(0.20 * w)), int(round(0.80 * w))),
            (int(round(0.12 * h)), int(round(0.54 * h)), int(round(0.20 * w)), int(round(0.80 * w))),
            (0, int(round(0.45 * h)), int(round(0.06 * w)), int(round(0.56 * w))),
            (0, int(round(0.45 * h)), int(round(0.44 * w)), int(round(0.94 * w))),
        ]
        for sy1, sy2, sx1, sx2 in sub_crops:
            sub_entries = _extract_mp_faces_from_region(
                face_landmarker,
                rgb[sy1:sy2, sx1:sx2],
                gray_u8,
                sx1,
                sy1,
                sx2 - sx1,
                sy2 - sy1,
                upscale=True,
            )
            if sub_entries:
                face_entries = sub_entries
                break

    if not face_entries:
        return None, False, []

    max_area = max(e[0] for e in face_entries)
    prominent = [e for e in face_entries if e[0] >= 0.28 * max_area]

    has_closed_eyes = any(e[2] for e in prominent)
    mean_sharp = sum(e[1] for e in prominent) / len(prominent)
    tags: List[str] = []

    eye_quality = 20.0 if has_closed_eyes else 92.0
    score = 0.58 * mean_sharp + 0.42 * eye_quality

    if has_closed_eyes:
        score = min(score - 32.0, 38.0)
        tags.append("eyes_closed")
    elif mean_sharp < 36.0:
        score -= 14.0
        tags.append("face_blurry")
    elif mean_sharp >= 52.0:
        tags.append("eyes_open_sharp")

    if mean_sharp < 36.0 and "face_blurry" not in tags:
        tags.append("face_blurry")

    return round(_clamp(score, 5.0, 100.0), 1), has_closed_eyes, tags


def _check_eye_zone_openness_cv(eye_gray: np.ndarray, skin_lum: float) -> Tuple[bool, bool]:
    """Analyze a single eye ROI in grayscale for offline fallback."""
    eh, ew = eye_gray.shape[:2]
    if eh < 6 or ew < 10:
        return False, True

    eye_f = eye_gray.astype(np.float32)
    dark_thresh = min(skin_lum - 22.0, float(np.percentile(eye_f, 22)))
    if skin_lum - float(np.min(eye_f)) < 22.0:
        return False, True

    dark_mask = (eye_f <= dark_thresh).astype(np.uint8)
    if min(eh, ew) >= 18:
        kernel = np.ones((2, 2), dtype=np.uint8)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, kernel)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(dark_mask, connectivity=8)
    if num_labels <= 1:
        return False, True

    candidates = []
    for lbl in range(1, num_labels):
        cx, cy = centroids[lbl]
        bx, by, bw, bh, area = stats[lbl]
        if area < max(4, int(0.008 * eh * ew)) or bw < max(3, int(0.14 * ew)):
            continue
        candidates.append((lbl, bx, by, bw, bh, area, cx, cy))

    if not candidates:
        return False, True

    lower_candidates = [c for c in candidates if c[7] >= 0.28 * eh]
    chosen_pool = lower_candidates if lower_candidates else candidates
    best = max(chosen_pool, key=lambda c: c[3] * (1.0 - 0.5 * abs((c[7] / eh) - 0.55)))
    lbl, bx, by, bw, bh, area, _, _ = best

    comp_mask = (labels == lbl).astype(np.uint8)
    col_heights = np.sum(comp_mask[:, bx : bx + bw], axis=0)
    p75_col_h = float(np.percentile(col_heights, 75)) if len(col_heights) > 0 else float(bh)

    aspect = float(bh) / max(1.0, float(bw))
    thickness_ratio = p75_col_h / max(1.0, float(bw))

    pad_x = max(2, int(0.15 * bw))
    pad_y = max(2, int(0.35 * bh))
    sx1, sy1 = max(0, bx - pad_x), max(0, by - pad_y)
    sx2, sy2 = min(ew, bx + bw + pad_x), min(eh, by + bh + pad_y)
    local_patch = eye_f[sy1:sy2, sx1:sx2]
    sclera_ratio = float(np.mean(local_patch > skin_lum + 20.0)) if local_patch.size > 0 else 0.0

    gx = cv2.Sobel(local_patch, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(local_patch, cv2.CV_32F, 0, 1, ksize=3)
    mean_gx = float(np.mean(np.abs(gx))) + 1e-4
    mean_gy = float(np.mean(np.abs(gy))) + 1e-4
    gy_over_gx = mean_gy / mean_gx

    if sclera_ratio >= 0.05 and aspect >= 0.30 and thickness_ratio >= 0.22:
        return True, True
    if aspect < 0.29 or thickness_ratio < 0.20:
        return True, False
    if gy_over_gx > 2.15 and sclera_ratio < 0.04:
        return True, False

    return True, True


def _detect_faces_pure_cv(
    rgb: np.ndarray, gray_u8: np.ndarray
) -> Tuple[Optional[float], bool, List[str]]:
    """Pure OpenCV skin-oval + symmetric eye-zone detector for 100% offline fallback (when MediaPipe is unavailable)."""
    h, w = gray_u8.shape[:2]
    ycrcb = cv2.cvtColor(rgb, cv2.COLOR_RGB2YCrCb)
    y_ch, cr_ch, cb_ch = ycrcb[:, :, 0], ycrcb[:, :, 1], ycrcb[:, :, 2]

    r_ch = rgb[:, :, 0].astype(np.int16)
    g_ch = rgb[:, :, 1].astype(np.int16)
    b_ch = rgb[:, :, 2].astype(np.int16)

    skin_ycrcb = (
        (y_ch >= 45)
        & (cr_ch >= 132)
        & (cr_ch <= 180)
        & (cb_ch >= 76)
        & (cb_ch <= 132)
    )
    skin_rgb = (
        (r_ch >= 95)
        & (g_ch >= 52)
        & (b_ch >= 32)
        & (r_ch > g_ch)
        & ((r_ch - g_ch) >= 8)
        & ((r_ch - g_ch) <= 105)
        & ((r_ch - b_ch) >= 20)
        & ~((g_ch > 195) & (b_ch < 135) & ((r_ch - g_ch) < 42))
    )
    skin_mask = ((skin_ycrcb | skin_rgb).astype(np.uint8)) * 255

    k_size = max(3, int(round(min(h, w) * 0.010)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
    skin_closed = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    skin_clean = cv2.morphologyEx(skin_closed, cv2.MORPH_OPEN, kernel, iterations=1)

    contours, _ = cv2.findContours(skin_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    img_area = float(h * w)

    face_entries = []

    for cnt in contours:
        bx, by, bw, bh = cv2.boundingRect(cnt)
        if bh > bw * 1.48 and bw >= 0.04 * w:
            bh = int(round(bw * 1.32))

        box_area = float(bw * bh)
        if box_area < 0.002 * img_area or box_area > 0.52 * img_area:
            continue

        aspect = float(bw) / max(1.0, float(bh))
        if aspect < 0.54 or aspect > 1.15:
            continue

        cw = max(2, int(round(bw * 0.13)))
        ch = max(2, int(round(bh * 0.13)))
        top_corners = np.concatenate(
            [
                skin_mask[by : by + ch, bx : bx + cw].ravel(),
                skin_mask[by : by + ch, bx + bw - cw : bx + bw].ravel(),
            ]
        )
        corner_skin_frac = float(np.mean(top_corners > 0)) if top_corners.size > 0 else 1.0
        center_patch = skin_mask[
            by + int(0.45 * bh) : by + int(0.68 * bh),
            bx + int(0.25 * bw) : bx + int(0.75 * bw),
        ]
        center_skin_frac = float(np.mean(center_patch > 0)) if center_patch.size > 0 else 0.0
        if corner_skin_frac > 0.55 or center_skin_frac < 0.55:
            continue

        face_gray = gray_u8[by : by + bh, bx : bx + bw]
        cheek_patch = face_gray[
            int(0.54 * bh) : int(0.70 * bh),
            int(0.22 * bw) : int(0.78 * bw),
        ]
        if cheek_patch.size == 0:
            continue
        skin_lum = float(np.median(cheek_patch))

        ey1, ey2 = int(round(0.26 * bh)), int(round(0.54 * bh))
        lx1, lx2 = int(round(0.14 * bw)), int(round(0.47 * bw))
        rx1, rx2 = int(round(0.53 * bw)), int(round(0.86 * bw))

        left_zone = face_gray[ey1:ey2, lx1:lx2]
        right_zone = face_gray[ey1:ey2, rx1:rx2]

        has_l, open_l = _check_eye_zone_openness_cv(left_zone, skin_lum)
        has_r, open_r = _check_eye_zone_openness_cv(right_zone, skin_lum)
        if not (has_l and has_r):
            continue

        is_closed = (not open_l) or (not open_r)
        sharp = _compute_roi_sharpness(face_gray)
        face_entries.append((box_area, sharp, is_closed))

    if not face_entries:
        return None, False, []

    max_area = max(e[0] for e in face_entries)
    prominent = [e for e in face_entries if e[0] >= 0.28 * max_area]
    has_closed_eyes = any(e[2] for e in prominent)
    mean_sharp = sum(e[1] for e in prominent) / len(prominent)
    tags: List[str] = []

    eye_quality = 20.0 if has_closed_eyes else 90.0
    score = 0.58 * mean_sharp + 0.42 * eye_quality

    if has_closed_eyes:
        score = min(score - 32.0, 38.0)
        tags.append("eyes_closed")
    elif mean_sharp < 36.0:
        score -= 14.0
        tags.append("face_blurry")
    elif mean_sharp >= 50.0:
        tags.append("eyes_open_sharp")

    if mean_sharp < 36.0 and "face_blurry" not in tags:
        tags.append("face_blurry")

    return round(_clamp(score, 5.0, 100.0), 1), has_closed_eyes, tags


def _evaluate_faces_haar(
    haar_face: cv2.CascadeClassifier,
    haar_eye: cv2.CascadeClassifier,
    rgb: np.ndarray,
    gray_u8: np.ndarray,
) -> Tuple[Optional[float], bool, List[str]]:
    h, w = gray_u8.shape[:2]
    min_dim = max(24, int(round(min(h, w) * 0.06)))
    faces = haar_face.detectMultiScale(
        gray_u8, scaleFactor=1.12, minNeighbors=5, minSize=(min_dim, min_dim)
    )
    if faces is None or len(faces) == 0:
        return _detect_faces_pure_cv(rgb, gray_u8)

    face_entries = []
    for (fx, fy, fw, fh) in faces:
        area = float(fw * fh)
        face_gray = gray_u8[fy : fy + fh, fx : fx + fw]
        upper_face = face_gray[int(0.18 * fh) : int(0.60 * fh), :]
        eyes = haar_eye.detectMultiScale(
            upper_face,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(max(10, fw // 9), max(8, fh // 12)),
        )
        cheek = face_gray[int(0.55 * fh) : int(0.72 * fh), int(0.25 * fw) : int(0.75 * fw)]
        skin_lum = float(np.median(cheek)) if cheek.size > 0 else 140.0
        _, open_l = _check_eye_zone_openness_cv(
            face_gray[int(0.25 * fh) : int(0.55 * fh), int(0.14 * fw) : int(0.47 * fw)],
            skin_lum,
        )
        _, open_r = _check_eye_zone_openness_cv(
            face_gray[int(0.25 * fh) : int(0.55 * fh), int(0.53 * fw) : int(0.86 * fw)],
            skin_lum,
        )
        is_closed = (len(eyes) == 0) and (not open_l or not open_r)
        sharp = _compute_roi_sharpness(face_gray)
        face_entries.append((area, sharp, is_closed))

    max_area = max(e[0] for e in face_entries)
    prominent = [e for e in face_entries if e[0] >= 0.28 * max_area]
    has_closed_eyes = any(e[2] for e in prominent)
    mean_sharp = sum(e[1] for e in prominent) / len(prominent)
    tags: List[str] = []

    eye_quality = 20.0 if has_closed_eyes else 90.0
    score = 0.58 * mean_sharp + 0.42 * eye_quality
    if has_closed_eyes:
        score = min(score - 32.0, 38.0)
        tags.append("eyes_closed")
    elif mean_sharp < 36.0:
        score -= 14.0
        tags.append("face_blurry")
    elif mean_sharp >= 50.0:
        tags.append("eyes_open_sharp")

    if mean_sharp < 36.0 and "face_blurry" not in tags:
        tags.append("face_blurry")

    return round(_clamp(score, 5.0, 100.0), 1), has_closed_eyes, tags


def _evaluate_faces(
    rgb: np.ndarray, gray_u8: np.ndarray
) -> Tuple[Optional[float], bool, List[str]]:
    face_lm = _get_face_landmarker()
    if face_lm is not None:
        mp_res = _evaluate_faces_mediapipe(face_lm, rgb, gray_u8)
        if mp_res is not None:
            return mp_res
        return None, False, []

    haar_face, haar_eye = _get_haar_cascades()
    if haar_face is not None and haar_eye is not None:
        return _evaluate_faces_haar(haar_face, haar_eye, rgb, gray_u8)

    return _detect_faces_pure_cv(rgb, gray_u8)


# ---------------------------------------------------------------------------
# 3. Composite Aesthetic Score & Cluster Orchestration (Quality + Face + Composition)
# ---------------------------------------------------------------------------


def _select_canonical_tags(raw_tags: List[str], max_tags: int = 4) -> List[str]:
    tag_set = {t for t in raw_tags if t in CANONICAL_AESTHETIC_TAGS}
    # Ensure mutually exclusive positive/warning pairs never coexist
    if "eyes_closed" in tag_set or "face_blurry" in tag_set:
        tag_set.discard("eyes_open_sharp")
    if "tilted_horizon" in tag_set:
        tag_set.discard("level_horizon")
    if "edge_subject" in tag_set:
        tag_set.discard("rule_of_thirds")

    ordered = [t for t in TAG_PRIORITY_ORDER if t in tag_set]
    return ordered[:max_tags]


def evaluate_photo_aesthetics(
    file_path: str, quality_score: Optional[float] = None
) -> Optional[PhotoAestheticMetrics]:
    """Compute deep aesthetic metrics (Quality + Face + Composition/Tilt) for a single photo."""
    rgb = _load_rgb_image(file_path, max_dim=960)
    if rgb is None:
        return None

    if quality_score is None:
        q_metrics = evaluate_photo_quality(file_path)
        tech_score = q_metrics.quality_score if q_metrics is not None else 50.0
    else:
        tech_score = float(quality_score)

    gray_u8 = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    comp_score, tilt_angle, comp_tags = _evaluate_composition(rgb, gray_u8)
    face_score, has_closed_eyes, face_tags = _evaluate_faces(rgb, gray_u8)

    tags = _select_canonical_tags(face_tags + comp_tags, max_tags=4)

    # Weighted blend (Quality 40%, Composition 25%, Face 35% when detected else redistributed)
    w_tech = 0.40
    w_comp = 0.25
    w_face = 0.35 if face_score is not None else 0.0
    total_w = w_tech + w_comp + w_face

    composite = (
        w_tech * tech_score
        + w_comp * comp_score
        + w_face * (face_score or 0.0)
    ) / total_w

    # Explicit perceptual defect penalties
    tag_lookup = set(tags)
    if has_closed_eyes or "eyes_closed" in tag_lookup:
        composite -= 25.0
    if "tilted_horizon" in tag_lookup:
        composite -= 10.0

    return PhotoAestheticMetrics(
        aesthetic_score=round(_clamp(composite), 1),
        composition_score=comp_score,
        face_score=face_score,
        pose_score=None,
        tilt_angle=tilt_angle,
        has_closed_eyes=has_closed_eyes,
        aesthetic_tags=tags,
    )


def score_clusters_aesthetics(db: Session) -> Dict[str, Any]:
    """Run on-demand scoring (Quality + Face + Composition) ONLY on multi-photo AI Similar Clusters."""
    reset_cancel()
    start_time = time.time()

    _, cluster_ids = photo_repo.get_multi_photo_cluster_ids(db, limit=1_000_000, offset=0)
    if not cluster_ids:
        update_progress("done", 0, 0, "Hoàn tất chấm điểm thẩm mỹ AI")
        return {
            "clusters_scored": 0,
            "photos_scored": 0,
            "best_changed_count": 0,
            "duration_seconds": round(time.time() - start_time, 3),
            "cancelled": False,
        }

    cluster_photos_map: Dict[int, List[Photo]] = {}
    all_target_photos: List[Photo] = []
    all_c_photos_by_cid: Dict[int, List[Photo]] = {}
    for p in photo_repo.get_photos_by_clusters(db, cluster_ids):
        if p.cluster_id is not None and os.path.exists(p.file_path):
            all_c_photos_by_cid.setdefault(p.cluster_id, []).append(p)

    for cid in cluster_ids:
        c_photos = all_c_photos_by_cid.get(cid, [])
        if len(c_photos) >= 2:
            cluster_photos_map[cid] = c_photos
            all_target_photos.extend(c_photos)

    total_photos = len(all_target_photos)
    if total_photos == 0:
        update_progress("done", 0, 0, "Hoàn tất chấm điểm thẩm mỹ AI")
        return {
            "clusters_scored": 0,
            "photos_scored": 0,
            "best_changed_count": 0,
            "duration_seconds": round(time.time() - start_time, 3),
            "cancelled": False,
        }

    photos_scored = 0
    pending_commits = 0
    cancelled = False

    for idx, photo in enumerate(all_target_photos, start=1):
        if is_cancel_requested():
            cancelled = True
            break

        update_progress(
            phase="aesthetic_scoring",
            current=idx,
            total=total_photos,
            current_file=os.path.basename(photo.file_path),
        )

        q_metrics = evaluate_photo_quality(photo.file_path, file_size=photo.file_size)
        if q_metrics is not None:
            photo.width = q_metrics.width
            photo.height = q_metrics.height
            photo.quality_score = q_metrics.quality_score
            photo.sharpness_score = q_metrics.sharpness_score
            photo.exposure_score = q_metrics.exposure_score
            photo.contrast_score = q_metrics.contrast_score

        a_metrics = evaluate_photo_aesthetics(
            photo.file_path, quality_score=photo.quality_score
        )
        if a_metrics is not None:
            photo.aesthetic_score = a_metrics.aesthetic_score
            photo.composition_score = a_metrics.composition_score
            photo.face_score = a_metrics.face_score
            photo.pose_score = None
            photo.tilt_angle = a_metrics.tilt_angle
            photo.has_closed_eyes = a_metrics.has_closed_eyes
            photo.aesthetic_tags = json.dumps(a_metrics.aesthetic_tags)
            db.add(photo)
            photos_scored += 1
            pending_commits += 1
            if pending_commits >= 25:
                db.flush()
                db.commit()
                pending_commits = 0

    db.flush()

    cluster_objs = {
        c.id: c
        for c in db.query(Cluster).filter(Cluster.id.in_(list(cluster_photos_map.keys()))).all()
    }
    best_changed_count = 0
    clusters_scored = 0

    for cid, c_photos in cluster_photos_map.items():
        if not any(p.aesthetic_score is not None for p in c_photos):
            continue
        cluster_obj = cluster_objs.get(cid)
        if not cluster_obj:
            continue
        clusters_scored += 1
        new_best = max(
            c_photos,
            key=lambda p: (
                p.aesthetic_score if p.aesthetic_score is not None else -1.0,
                p.quality_score or 0.0,
                p.file_size or 0,
                -(p.id or 0),
            ),
        )
        if cluster_obj.best_photo_id != new_best.id:
            cluster_obj.best_photo_id = new_best.id
            db.add(cluster_obj)
            best_changed_count += 1

    db.commit()

    if cancelled:
        update_progress(
            "cancelled", photos_scored, total_photos, "Đã dừng chấm điểm thẩm mỹ AI"
        )
    else:
        update_progress(
            "done", total_photos, total_photos, "Hoàn tất chấm điểm thẩm mỹ AI"
        )

    return {
        "clusters_scored": clusters_scored,
        "photos_scored": photos_scored,
        "best_changed_count": best_changed_count,
        "duration_seconds": round(time.time() - start_time, 3),
        "cancelled": cancelled,
    }
