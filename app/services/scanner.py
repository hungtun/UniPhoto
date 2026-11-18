import os
import time
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import ExifTags, Image
from sqlalchemy.orm import Session

from app.models.models import Photo
from app.services.progress_tracker import (
    is_cancel_requested,
    reset_cancel,
    update_progress,
)

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


def get_image_timestamp(file_path: str, img: Optional[Image.Image] = None) -> datetime:
    os_time = os.path.getmtime(file_path)
    best_time = datetime.fromtimestamp(os_time)

    try:
        target_img = img if img is not None else Image.open(file_path)
        exif_data = target_img.getexif()

        if exif_data:
            all_tags = dict(exif_data)
            if 0x8769 in exif_data:
                all_tags.update(exif_data.get_ifd(0x8769))

            for tag_id, value in all_tags.items():
                tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                if tag_name in ["DateTimeOriginal", "DateTime", "DateTimeDigitized"] and isinstance(value, str):
                    clean_str = value.strip().replace("\x00", "")[:19]
                    try:
                        parsed_time = datetime.strptime(clean_str, "%Y:%m:%d %H:%M:%S")
                        if tag_name == "DateTimeOriginal":
                            return parsed_time
                        best_time = parsed_time
                    except ValueError:
                        pass
    except Exception:
        pass
    return best_time


def _get_oriented_dimensions(img: Image.Image) -> Tuple[int, int]:
    """Extract EXIF-oriented (width, height) directly from an opened Pillow image."""
    w, h = img.size
    try:
        exif = img.getexif()
        if exif and exif.get(0x0112) in (5, 6, 7, 8):
            return h, w
    except Exception:
        pass
    return w, h


@lru_cache(maxsize=8)
def _get_dct_lowfreq_basis(img_size: int, hash_size: int) -> np.ndarray:
    """Precompute unnormalized 1D DCT-II basis matrix (img_size, hash_size) matching scipy.fftpack.dct."""
    n = np.arange(img_size, dtype=np.float64)[:, None]
    k = np.arange(hash_size, dtype=np.float64)[None, :]
    return 2.0 * np.cos(np.pi * (2.0 * n + 1.0) * k / (2.0 * img_size))


def calculate_phash(
    img: Image.Image, hash_size: int = 16, highfreq_factor: int = 4
) -> str:
    """Pure NumPy + Pillow 2D DCT-II perceptual hash matching imagehash.phash(img, hash_size=16) bit-for-bit."""
    if hash_size < 2:
        raise ValueError("Hash size must be greater than or equal to 2")
    img_size = hash_size * highfreq_factor
    gray = img.convert("L").resize((img_size, img_size), Image.Resampling.LANCZOS)
    pixels = np.asarray(gray, dtype=np.float64)
    basis = _get_dct_lowfreq_basis(img_size, hash_size)
    dctlowfreq = (basis.T @ pixels) @ basis
    med = np.median(dctlowfreq)
    diff = (dctlowfreq > med).reshape(-1)
    if diff.size % 8 == 0:
        return np.packbits(diff).tobytes().hex()
    bit_string = "".join("1" if b else "0" for b in diff)
    width = (len(bit_string) + 3) // 4
    return f"{int(bit_string, 2):0>{width}x}"


def scan_directory(folder_path: str, db: Session, progress_callback=None) -> Dict[str, Any]:
    abs_folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(abs_folder_path):
        raise FileNotFoundError(f"Thư mục không tồn tại: {abs_folder_path}")

    reset_cancel()
    start_time = time.time()
    IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "Library", ".Trash"}

    # Bước 0: Thu thập danh sách toàn bộ file ảnh trước để biết tổng số lượng ảnh (total_files)
    all_image_paths: List[str] = []
    for root, dirs, files in os.walk(abs_folder_path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in IGNORED_DIRS]
        for file_name in files:
            if file_name.startswith("."):
                continue
            ext = os.path.splitext(file_name)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                all_image_paths.append(os.path.abspath(os.path.join(root, file_name)))

    total_found = len(all_image_paths)
    new_added = 0
    exact_duplicates = 0
    already_indexed = 0
    errors_count = 0
    processed_so_far = 0
    pending_commits = 0
    cancelled = False
    processed_items: List[Photo] = []

    update_progress("scanning", 0, total_found, "Đang bắt đầu quét...", 0, 0, 0)

    for idx, abs_file_path in enumerate(all_image_paths, start=1):
        if is_cancel_requested():
            cancelled = True
            break

        file_name = os.path.basename(abs_file_path)

        update_progress(
            phase="scanning",
            current=idx,
            total=total_found,
            current_file=file_name,
            new_added=new_added,
            exact_duplicates=exact_duplicates,
            already_indexed=already_indexed,
        )

        try:
            # 1. Kiểm tra xem file theo đường dẫn này đã từng được lưu vào DB chưa
            existing_file = db.query(Photo).filter(Photo.file_path == abs_file_path).first()
            if existing_file:
                if existing_file.width is None or existing_file.height is None:
                    with Image.open(abs_file_path) as img:
                        w, h = _get_oriented_dimensions(img)
                    with db.begin_nested():
                        existing_file.width = w
                        existing_file.height = h
                        db.add(existing_file)
                        db.flush()
                    pending_commits += 1
                    if pending_commits >= 100:
                        db.commit()
                        pending_commits = 0
                already_indexed += 1
                processed_items.append(existing_file)
                processed_so_far += 1
                if progress_callback:
                    progress_callback(idx, new_added, exact_duplicates, file_name)
                continue

            file_size = os.path.getsize(abs_file_path)

            # 2. Mở ảnh 1 lần bằng Pillow: đọc EXIF, kích thước hướng đúng và tính pHash (KHÔNG chấm điểm tự động)
            with Image.open(abs_file_path) as img:
                dt_original = get_image_timestamp(abs_file_path, img)
                width, height = _get_oriented_dimensions(img)
                hash_str = calculate_phash(img)

            # 3 & 4. Kiểm tra trùng lặp pHash và lưu vào DB theo lô 100 thao tác
            is_dup = False
            with db.begin_nested():
                existing_keep = (
                    db.query(Photo)
                    .filter(Photo.phash == hash_str, Photo.status == "keep")
                    .first()
                )

                if existing_keep:
                    is_dup = True
                    if file_size > (existing_keep.file_size or 0):
                        existing_keep.status = "exact_duplicate"
                        db.add(existing_keep)
                        status = "keep"
                    else:
                        status = "exact_duplicate"
                else:
                    existing_any = db.query(Photo).filter(Photo.phash == hash_str).first()
                    if existing_any:
                        is_dup = True
                        status = "exact_duplicate"
                    else:
                        status = "keep"

                new_photo = Photo(
                    file_path=abs_file_path,
                    file_size=file_size,
                    width=width,
                    height=height,
                    timestamp=dt_original,
                    phash=hash_str,
                    status=status,
                )
                db.add(new_photo)
                db.flush()

            if is_dup:
                exact_duplicates += 1
            else:
                new_added += 1

            pending_commits += 1
            if pending_commits >= 100:
                db.commit()
                pending_commits = 0

            processed_items.append(new_photo)
            processed_so_far += 1

        except Exception as e:
            errors_count += 1
            processed_so_far += 1
            print(f"Lỗi khi xử lý file {abs_file_path}: {e}")

        if progress_callback:
            progress_callback(idx, new_added, exact_duplicates, file_name)

    if pending_commits > 0:
        db.commit()
        pending_commits = 0

    if not cancelled and total_found == 0 and is_cancel_requested():
        cancelled = True

    if cancelled:
        update_progress(
            phase="cancelled",
            current=processed_so_far,
            total=total_found,
            current_file="Đã dừng quét thư mục",
            new_added=new_added,
            exact_duplicates=exact_duplicates,
            already_indexed=already_indexed,
        )
    else:
        update_progress(
            phase="done",
            current=total_found,
            total=total_found,
            current_file="Hoàn tất quét thư mục",
            new_added=new_added,
            exact_duplicates=exact_duplicates,
            already_indexed=already_indexed,
        )

    duration = round(time.time() - start_time, 3)

    return {
        "folder_path": abs_folder_path,
        "total_found": total_found,
        "new_added": new_added,
        "exact_duplicates": exact_duplicates,
        "already_indexed": already_indexed,
        "errors_count": errors_count,
        "duration_seconds": duration,
        "cancelled": cancelled,
        "items": processed_items,
    }
