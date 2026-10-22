import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from PIL import Image, ExifTags
import imagehash
from sqlalchemy.orm import Session

from app.models.models import Photo

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def extract_datetime_original(img: Image.Image) -> Optional[datetime]:
    try:
        exif = img._getexif()
        if not exif:
            return None

        for tag_id, value in exif.items():
            tag_name = ExifTags.TAGS.get(tag_id)
            if tag_name == "DateTimeOriginal":
                if isinstance(value, str):
                    clean_str = value.strip().replace("\x00", "")
                    try:
                        return datetime.strptime(clean_str[:19], "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        pass
                break
    except Exception:
        pass
    return None


def calculate_phash(img: Image.Image) -> str:
    return str(imagehash.phash(img))


def scan_directory(folder_path: str, db: Session) -> Dict[str, Any]:
    abs_folder_path = os.path.abspath(folder_path)
    if not os.path.isdir(abs_folder_path):
        raise FileNotFoundError(f"Thư mục không tồn tại: {abs_folder_path}")

    start_time = time.time()

    total_found = 0
    new_added = 0
    exact_duplicates = 0
    already_indexed = 0
    errors_count = 0
    processed_items: List[Photo] = []

    for root, _, files in os.walk(abs_folder_path):
        for file_name in files:
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue

            total_found += 1
            file_path = os.path.join(root, file_name)
            abs_file_path = os.path.abspath(file_path)

            try:
                # 1. Kiểm tra xem file theo đường dẫn này đã từng được lưu vào DB chưa
                existing_file = db.query(Photo).filter(Photo.file_path == abs_file_path).first()
                if existing_file:
                    already_indexed += 1
                    processed_items.append(existing_file)
                    continue

                file_size = os.path.getsize(abs_file_path)

                # 2. Mở ảnh bằng Pillow, đọc EXIF và tính pHash
                with Image.open(abs_file_path) as img:
                    dt_original = extract_datetime_original(img)
                    hash_str = calculate_phash(img)

                # 3. Logic kiểm tra trùng lặp bằng pHash và giữ lại bản có dung lượng lớn nhất
                # Tìm file cũ đang được giữ lại (keep) có cùng mã pHash
                existing_keep = db.query(Photo).filter(Photo.phash == hash_str, Photo.status == "keep").first()
                
                if existing_keep:
                    exact_duplicates += 1
                    if file_size > existing_keep.file_size:
                        # Bản mới dung lượng lớn hơn -> Chuyển bản cũ thành duplicate, giữ bản mới
                        existing_keep.status = "exact_duplicate"
                        db.add(existing_keep)
                        status = "keep"
                    else:
                        # Bản cũ lớn hơn hoặc bằng -> Bản mới là duplicate
                        status = "exact_duplicate"
                else:
                    # Đề phòng trường hợp database có bản ghi pHash nhưng không có bản nào là "keep"
                    existing_any = db.query(Photo).filter(Photo.phash == hash_str).first()
                    if existing_any:
                        exact_duplicates += 1
                        status = "exact_duplicate"
                    else:
                        new_added += 1
                        status = "keep"

                # 4. Lưu bản ghi mới vào MySQL (database)
                new_photo = Photo(
                    file_path=abs_file_path,
                    file_size=file_size,
                    timestamp=dt_original,
                    phash=hash_str,
                    status=status,
                )
                db.add(new_photo)
                db.commit()
                db.refresh(new_photo)

                processed_items.append(new_photo)

            except Exception as e:
                db.rollback()
                errors_count += 1
                print(f"Lỗi khi xử lý file {abs_file_path}: {e}")

    duration = round(time.time() - start_time, 3)

    return {
        "folder_path": abs_folder_path,
        "total_found": total_found,
        "new_added": new_added,
        "exact_duplicates": exact_duplicates,
        "already_indexed": already_indexed,
        "errors_count": errors_count,
        "duration_seconds": duration,
        "items": processed_items,
    }
