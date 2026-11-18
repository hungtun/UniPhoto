import gc
import os
import ssl
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from app.core.config import is_packaged_runtime, settings
from app.models.models import Cluster, Photo
from app.services.progress_tracker import (
    is_cancel_requested,
    reset_cancel,
    update_progress,
)

# Giới hạn 2 luồng CPU cho OpenCV DNN (ONNX MobileNetV2) để suy luận nhanh mà vẫn giữ máy mát
cv2.setNumThreads(2)

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

_FEATURE_EXTRACTOR: Optional[Any] = None
_EXTRACTOR_LOCK = threading.Lock()
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class OnnxMobileNetV2Extractor:
    """Thread-safe OpenCV DNN ONNX feature extractor producing (B, 1280) float32 embeddings."""

    def __init__(self, onnx_path: Path) -> None:
        self.onnx_path = Path(onnx_path)
        self._net = cv2.dnn.readNetFromONNX(str(self.onnx_path))
        self._forward_lock = threading.Lock()

    def __call__(self, batch: np.ndarray) -> np.ndarray:
        blob = np.ascontiguousarray(batch, dtype=np.float32)
        if blob.ndim == 3:
            blob = blob[np.newaxis, ...]
        with self._forward_lock:
            self._net.setInput(blob)
            # Copy immediately because cv2.dnn.Net reuses internal output buffers across forward() calls
            out = self._net.forward().copy()
        return out.reshape(blob.shape[0], -1).astype(np.float32, copy=False)

    def extract(self, batch: np.ndarray) -> np.ndarray:
        return self(batch)


def _candidate_mobilenet_onnx_paths() -> List[Path]:
    candidates: List[Path] = []
    env_models_dir = os.environ.get("UNIPHOTO_MODELS_DIR", "").strip()
    if env_models_dir:
        candidates.append(Path(env_models_dir).expanduser() / "mobilenet_v2.onnx")
    if settings.BUNDLED_MODELS_DIR.strip():
        bundled_cand = (
            Path(settings.BUNDLED_MODELS_DIR.strip()).expanduser() / "mobilenet_v2.onnx"
        )
        if bundled_cand not in candidates:
            candidates.append(bundled_cand)
    data_cand = Path(settings.DATA_DIR).expanduser() / "models" / "mobilenet_v2.onnx"
    if data_cand not in candidates:
        candidates.append(data_cand)
    repo_cand = PROJECT_ROOT / "data" / "models" / "mobilenet_v2.onnx"
    if repo_cand not in candidates:
        candidates.append(repo_cand)
    return candidates


def _resolve_mobilenet_onnx_path() -> Optional[Path]:
    for cand in _candidate_mobilenet_onnx_paths():
        try:
            if cand.is_file() and cand.stat().st_size > 1_000_000:
                return cand
        except OSError:
            continue
    return None


def _candidate_mobilenet_weight_paths() -> List[Path]:
    """Ordered candidate model paths (ONNX primary; dev-only .pth fallback if .onnx absent)."""
    candidates: List[Path] = []
    allow_pth = not bool(getattr(sys, "frozen", False))

    def _add(p: Path) -> None:
        if p not in candidates:
            candidates.append(p)

    env_models_dir = os.environ.get("UNIPHOTO_MODELS_DIR", "").strip()
    if env_models_dir:
        env_dir = Path(env_models_dir).expanduser()
        _add(env_dir / "mobilenet_v2.onnx")
        if allow_pth:
            _add(env_dir / "mobilenet_v2.pth")

    if settings.BUNDLED_MODELS_DIR.strip():
        bundled_dir = Path(settings.BUNDLED_MODELS_DIR.strip()).expanduser()
        _add(bundled_dir / "mobilenet_v2.onnx")
        if allow_pth:
            _add(bundled_dir / "mobilenet_v2.pth")

    data_models_dir = Path(settings.DATA_DIR).expanduser() / "models"
    repo_models_dir = PROJECT_ROOT / "data" / "models"
    _add(data_models_dir / "mobilenet_v2.onnx")
    _add(repo_models_dir / "mobilenet_v2.onnx")

    if allow_pth:
        _add(data_models_dir / "mobilenet_v2.pth")
        _add(repo_models_dir / "mobilenet_v2.pth")

    return candidates


def _resolve_mobilenet_weights_path() -> Optional[Path]:
    for cand in _candidate_mobilenet_weight_paths():
        try:
            if cand.is_file() and cand.stat().st_size > 1_000_000:
                return cand
        except OSError:
            continue
    return None


def _load_lazy_pytorch_fallback(pth_path: Optional[Path] = None) -> Any:
    """Optional dev-only PyTorch fallback used strictly when mobilenet_v2.onnx is unavailable."""
    if getattr(sys, "frozen", False):
        raise FileNotFoundError(
            "mobilenet_v2.onnx is required in packaged runtime (PyTorch is excluded)"
        )

    import torch
    import torch.nn as nn
    from torchvision.models import MobileNet_V2_Weights, mobilenet_v2

    ssl._create_default_https_context = ssl._create_unverified_context
    torch.set_num_threads(2)

    if pth_path is not None and pth_path.is_file():
        model = mobilenet_v2(weights=None)
        state_dict = torch.load(str(pth_path), map_location="cpu", weights_only=True)
        if "classifier.1.weight" not in state_dict:
            model.classifier = nn.Identity()
            model.load_state_dict(state_dict)
        else:
            model.load_state_dict(state_dict)
            model.classifier = nn.Identity()
        model.eval()
        return model

    if is_packaged_runtime() and not os.environ.get("TORCH_HOME", "").strip():
        torch_cache = Path(settings.DATA_DIR).expanduser() / "torch_cache"
        try:
            torch_cache.mkdir(parents=True, exist_ok=True)
            os.environ["TORCH_HOME"] = str(torch_cache)
        except OSError:
            pass

    model = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
    model.classifier = nn.Identity()
    model.eval()
    return model


def get_feature_extractor() -> Any:
    global _FEATURE_EXTRACTOR
    if _FEATURE_EXTRACTOR is not None:
        return _FEATURE_EXTRACTOR

    with _EXTRACTOR_LOCK:
        if _FEATURE_EXTRACTOR is not None:
            return _FEATURE_EXTRACTOR

        resolved = _resolve_mobilenet_weights_path()
        if resolved is not None and resolved.suffix.lower() == ".onnx":
            _FEATURE_EXTRACTOR = OnnxMobileNetV2Extractor(resolved)
            return _FEATURE_EXTRACTOR

        if resolved is not None and resolved.suffix.lower() == ".pth":
            _FEATURE_EXTRACTOR = _load_lazy_pytorch_fallback(resolved)
            return _FEATURE_EXTRACTOR

        onnx_only = _resolve_mobilenet_onnx_path()
        if onnx_only is not None:
            _FEATURE_EXTRACTOR = OnnxMobileNetV2Extractor(onnx_only)
            return _FEATURE_EXTRACTOR

        _FEATURE_EXTRACTOR = _load_lazy_pytorch_fallback(None)
        return _FEATURE_EXTRACTOR


IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def preprocess_image_cv2(file_path: str) -> np.ndarray | None:
    img = cv2.imread(file_path)
    if img is not None:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    else:
        # Dự phòng cho file .HEIC / .HEIF mà OpenCV không tự đọc được
        try:
            with Image.open(file_path) as pil_img:
                img = np.array(pil_img.convert("RGB"))
        except Exception:
            return None

    img = cv2.resize(img, (224, 224))
    img = img.astype(np.float32) / 255.0
    img = (img - IMAGENET_MEAN) / IMAGENET_STD
    img = np.transpose(img, (2, 0, 1))
    return img


def extract_embeddings_in_batches(
    photos: List[Photo], batch_size: int = 16
) -> Tuple[List[Photo], np.ndarray]:
    valid_photos: List[Photo] = []
    all_embeddings: List[np.ndarray] = []
    extractor = get_feature_extractor()
    total_photos = len(photos)

    for i in range(0, total_photos, batch_size):
        if is_cancel_requested():
            break

        batch_photos = photos[i : i + batch_size]
        batch_tensors = []
        batch_valid_photos = []
        cancelled_in_batch = False

        for idx_in_batch, photo in enumerate(batch_photos):
            if is_cancel_requested():
                cancelled_in_batch = True
                break

            current_idx = i + idx_in_batch + 1
            update_progress(
                phase="clustering",
                current=current_idx,
                total=total_photos,
                current_file=os.path.basename(photo.file_path),
            )
            processed = preprocess_image_cv2(photo.file_path)
            if processed is not None:
                batch_tensors.append(processed)
                batch_valid_photos.append(photo)

        if cancelled_in_batch or is_cancel_requested():
            del batch_tensors
            break

        if not batch_tensors:
            continue

        batch_blob = np.ascontiguousarray(
            np.stack(batch_tensors, axis=0), dtype=np.float32
        )

        if isinstance(extractor, OnnxMobileNetV2Extractor):
            features_np = extractor(batch_blob)
        else:
            import torch

            with torch.no_grad():
                features_np = (
                    extractor(torch.from_numpy(batch_blob))
                    .cpu()
                    .numpy()
                    .astype(np.float32)
                )

        all_embeddings.append(features_np)
        valid_photos.extend(batch_valid_photos)

        del batch_tensors, batch_blob, features_np
        gc.collect()

    if not all_embeddings:
        return [], np.array([])

    return valid_photos, np.vstack(all_embeddings)


def cluster_embeddings_chunked(
    embeddings: np.ndarray,
    similarity_threshold: float = 0.85,
    block_size: int = 512,
    check_cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[List[List[int]], bool]:
    """Gom cụm tham lam trên vector chuẩn hóa L2 theo từng khối (block_size x N) tiết kiệm >98% RAM."""
    groups: List[List[int]] = []
    if embeddings is None or embeddings.size == 0:
        return groups, False

    normed = np.array(embeddings, dtype=np.float32, copy=True)
    n = normed.shape[0]
    if n < 2:
        return groups, False

    sq_norms = np.einsum("ij,ij->i", normed, normed)
    norms = np.maximum(
        np.sqrt(sq_norms, dtype=np.float32)[:, np.newaxis], np.float32(1e-12)
    )
    del sq_norms
    normed /= norms
    del norms

    visited = np.zeros(n, dtype=bool)

    for block_start in range(0, n, block_size):
        if check_cancel and check_cancel():
            return groups, True

        block_end = min(block_start + block_size, n)
        if np.all(visited[block_start:block_end]):
            continue

        sim_block = normed[block_start:block_end] @ normed[block_start:].T

        for r in range(block_end - block_start):
            i = block_start + r
            if visited[i]:
                continue
            visited[i] = True

            rel_js = np.where(
                (sim_block[r, (r + 1) :] >= similarity_threshold)
                & (~visited[(i + 1) :])
            )[0]
            if rel_js.size > 0:
                abs_js = (i + 1) + rel_js
                visited[abs_js] = True
                groups.append([i, *abs_js.tolist()])

        del sim_block

    return groups, False


def _wipe_existing_clusters_and_scores(db: Session) -> None:
    """Làm sạch các cụm cũ và đặt lại toàn bộ điểm chất lượng & điểm thẩm mỹ về None."""
    db.query(Photo).update(
        {
            Photo.cluster_id: None,
            Photo.quality_score: None,
            Photo.sharpness_score: None,
            Photo.exposure_score: None,
            Photo.contrast_score: None,
            Photo.aesthetic_score: None,
            Photo.composition_score: None,
            Photo.face_score: None,
            Photo.pose_score: None,
            Photo.tilt_angle: None,
            Photo.has_closed_eyes: None,
            Photo.aesthetic_tags: None,
        }
    )
    db.query(Cluster).update({Cluster.best_photo_id: None})
    db.flush()
    db.query(Cluster).delete()
    db.flush()


def cluster_unassigned_photos(
    db: Session,
    batch_size: int = 16,
    similarity_threshold: float = 0.85,
) -> Dict[str, Any]:
    reset_cancel()
    start_time = time.time()

    keep_photos = (
        db.query(Photo)
        .filter(Photo.status == "keep")
        .order_by(Photo.timestamp.asc())
        .all()
    )

    if not keep_photos:
        if is_cancel_requested():
            update_progress("cancelled", 0, 0, "Đã dừng gom cụm AI")
            return {
                "total_processed": 0,
                "clusters_created": 0,
                "photos_clustered": 0,
                "duration_seconds": round(time.time() - start_time, 3),
                "cancelled": True,
            }
        _wipe_existing_clusters_and_scores(db)
        db.commit()
        update_progress("done", 0, 0, "Không có ảnh cần gom cụm")
        return {
            "total_processed": 0,
            "clusters_created": 0,
            "photos_clustered": 0,
            "duration_seconds": round(time.time() - start_time, 3),
            "cancelled": False,
        }

    update_progress("clustering", 0, len(keep_photos), "Đang khởi tạo AI MobileNetV2...")

    valid_photos, embeddings = extract_embeddings_in_batches(
        keep_photos, batch_size=batch_size
    )

    # Nếu người dùng bấm dừng trong lúc trích xuất đặc trưng, giữ nguyên các cụm cũ trong DB!
    if is_cancel_requested():
        update_progress(
            "cancelled", len(valid_photos), len(keep_photos), "Đã dừng gom cụm AI"
        )
        return {
            "total_processed": len(valid_photos),
            "clusters_created": 0,
            "photos_clustered": 0,
            "duration_seconds": round(time.time() - start_time, 3),
            "cancelled": True,
        }

    n = len(valid_photos)
    if n == 0:
        _wipe_existing_clusters_and_scores(db)
        db.commit()
        update_progress("done", 0, 0, "Hoàn tất")
        return {
            "total_processed": 0,
            "clusters_created": 0,
            "photos_clustered": 0,
            "duration_seconds": round(time.time() - start_time, 3),
            "cancelled": False,
        }

    groups, cancelled = cluster_embeddings_chunked(
        embeddings,
        similarity_threshold=similarity_threshold,
        block_size=512,
        check_cancel=is_cancel_requested,
    )
    del embeddings

    if cancelled or is_cancel_requested():
        update_progress("cancelled", n, len(keep_photos), "Đã dừng gom cụm AI")
        return {
            "total_processed": n,
            "clusters_created": 0,
            "photos_clustered": 0,
            "duration_seconds": round(time.time() - start_time, 3),
            "cancelled": True,
        }

    # Chỉ xóa cụm cũ & điểm cũ sau khi trích xuất vector và gom cụm hoàn tất không bị hủy
    _wipe_existing_clusters_and_scores(db)

    clusters_created = 0
    photos_clustered = 0
    cluster_records: List[Tuple[Cluster, List[Photo]]] = []

    for group_indices in groups:
        if len(group_indices) < 2:
            continue

        current_group = [valid_photos[idx] for idx in group_indices]
        best_photo = max(
            current_group,
            key=lambda p: (p.file_size or 0, -(p.id or 0)),
        )
        new_cluster = Cluster(best_photo_id=best_photo.id)
        db.add(new_cluster)
        cluster_records.append((new_cluster, current_group))

    if cluster_records:
        db.flush()
        for new_cluster, current_group in cluster_records:
            for photo in current_group:
                photo.cluster_id = new_cluster.id
                db.add(photo)
            clusters_created += 1
            photos_clustered += len(current_group)

    db.commit()
    update_progress("done", n, n, "Hoàn tất gom cụm AI")
    duration = round(time.time() - start_time, 3)

    return {
        "total_processed": n,
        "clusters_created": clusters_created,
        "photos_clustered": photos_clustered,
        "duration_seconds": duration,
        "cancelled": False,
    }
