import io
import json
import ntpath
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import CANONICAL_AESTHETIC_TAGS
from app.models.models import Photo, Cluster
from app.repositories.photo_repository import photo_repo

_HEIF_REGISTERED: bool = False
_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_WIN_DRIVE_ONLY_RE = re.compile(r"^[A-Za-z]:$")


def _ensure_pil_ready():
    """Lazily import Pillow + pillow_heif only when decoding/resizing thumbnails."""
    global _HEIF_REGISTERED
    from PIL import Image, ImageOps

    if not _HEIF_REGISTERED:
        _HEIF_REGISTERED = True
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
        except ImportError:
            pass
    return Image, ImageOps


def _size_only_rank_key(photo: Photo):
    """Khóa xếp hạng ưu tiên dung lượng lớn nhất: file_size lớn -> id nhỏ."""
    return (photo.file_size or 0, -(photo.id or 0))


def _aesthetic_photo_rank_key(photo: Photo):
    """Khóa xếp hạng ưu tiên điểm thẩm mỹ AI cho cụm ảnh tương tự đã chấm điểm."""
    return (
        photo.aesthetic_score if photo.aesthetic_score is not None else -1.0,
        photo.quality_score or 0.0,
        photo.file_size or 0,
        -(photo.id or 0),
    )


def _serialize_photo(
    photo: Photo, is_best: bool = False, include_scores: bool = False
) -> Dict[str, Any]:
    parsed_tags: List[str] = []
    if include_scores and photo.aesthetic_tags:
        try:
            raw_tags = json.loads(photo.aesthetic_tags)
            if isinstance(raw_tags, list):
                parsed_tags = [
                    str(t) for t in raw_tags if str(t) in CANONICAL_AESTHETIC_TAGS
                ]
        except Exception:
            parsed_tags = []

    file_path_str = photo.file_path or ""
    path_mod = ntpath if _WIN_DRIVE_RE.match(file_path_str) else os.path
    parent_dir = path_mod.dirname(file_path_str)
    folder_name = path_mod.basename(parent_dir) or parent_dir

    return {
        "id": photo.id,
        "file_name": path_mod.basename(file_path_str),
        "folder_name": folder_name,
        "file_path": photo.file_path,
        "file_size": photo.file_size,
        "width": photo.width,
        "height": photo.height,
        "timestamp": photo.timestamp,
        "status": photo.status,
        "is_best": is_best,
        "quality_score": round(photo.quality_score, 1)
        if (include_scores and photo.quality_score is not None)
        else None,
        "sharpness_score": round(photo.sharpness_score, 1)
        if (include_scores and photo.sharpness_score is not None)
        else None,
        "exposure_score": round(photo.exposure_score, 1)
        if (include_scores and photo.exposure_score is not None)
        else None,
        "contrast_score": round(photo.contrast_score, 1)
        if (include_scores and photo.contrast_score is not None)
        else None,
        "aesthetic_score": round(photo.aesthetic_score, 1)
        if (include_scores and photo.aesthetic_score is not None)
        else None,
        "composition_score": round(photo.composition_score, 1)
        if (include_scores and photo.composition_score is not None)
        else None,
        "face_score": round(photo.face_score, 1)
        if (include_scores and photo.face_score is not None)
        else None,
        "pose_score": None,
        "tilt_angle": round(photo.tilt_angle, 1)
        if (include_scores and photo.tilt_angle is not None)
        else None,
        "has_closed_eyes": bool(photo.has_closed_eyes)
        if (include_scores and photo.has_closed_eyes is not None)
        else None,
        "aesthetic_tags": parsed_tags,
        "thumbnail_url": (
            f"http://{'127.0.0.1' if settings.HOST in ('0.0.0.0', '::', '') else settings.HOST}"
            f":{settings.PORT}{settings.API_V1_STR}/photos/{photo.id}/thumbnail"
        ),
    }


def generate_thumbnail_bytes(db: Session, photo_id: int, max_size: int = 360) -> bytes:
    """Đọc ảnh gốc và nén thành thumbnail JPEG trực tiếp trên RAM (BytesIO)."""
    photo = photo_repo.get_by_id(db, photo_id)
    if not photo or not os.path.exists(photo.file_path):
        raise FileNotFoundError("Image file not found on the hard drive")

    Image, ImageOps = _ensure_pil_ready()
    with Image.open(photo.file_path) as img:
        img.draft("RGB", (max_size * 2, max_size * 2))
        img.thumbnail((max_size, max_size), Image.Resampling.BILINEAR)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        return buf.getvalue()


def _get_volumes_root() -> str:
    return os.environ.get("UNIPHOTO_VOLUMES_ROOT", "/Volumes").rstrip("/") or "/Volumes"


def _get_unmounted_volume_name(file_path: str) -> Optional[str]:
    """Trả về tên ổ đĩa ngoài nếu file_path nằm trên volume đang ngắt kết nối; ngược lại trả về None."""
    if not file_path:
        return None

    raw_forced = [
        v.strip()
        for v in os.environ.get("UNIPHOTO_UNMOUNTED_VOLUMES", "").split(",")
        if v.strip()
    ]

    if _WIN_DRIVE_RE.match(file_path):
        drive = file_path[:2].upper()
        forced_win = {v.upper().rstrip("\\/") for v in raw_forced}
        if drive in forced_win:
            return drive
        system_drive = (os.environ.get("SystemDrive", "C:").strip() or "C:").upper()[:2]
        if (
            sys.platform == "win32"
            and drive != system_drive
            and not os.path.exists(drive + "\\")
        ):
            return drive
        return None

    volumes_root = _get_volumes_root()
    forced_unmounted = {v.rstrip("/") for v in raw_forced}

    matched_root: Optional[str] = None
    real_root = os.path.realpath(volumes_root).rstrip("/")
    for candidate_root in (volumes_root, real_root):
        if candidate_root and file_path.startswith(candidate_root + "/"):
            matched_root = candidate_root
            break

    if matched_root is None:
        return None

    rel = file_path[len(matched_root) + 1 :]
    vol_name = rel.split("/", 1)[0]
    if not vol_name or "/" not in rel:
        return None

    vol_root = f"{volumes_root}/{vol_name}"
    matched_vol_root = f"{matched_root}/{vol_name}"
    if (
        vol_name in forced_unmounted
        or vol_root in forced_unmounted
        or matched_vol_root in forced_unmounted
    ):
        return vol_name

    if volumes_root == "/Volumes":
        is_mounted = os.path.exists(vol_root) and (
            os.path.islink(vol_root) or os.path.ismount(vol_root)
        )
    else:
        is_mounted = os.path.isdir(vol_root) or os.path.isdir(matched_vol_root)

    return None if is_mounted else vol_name


def _volume_root_prefixes() -> List[str]:
    volumes_root = _get_volumes_root()
    prefixes = [volumes_root + "/"]
    real_root = os.path.realpath(volumes_root).rstrip("/")
    if real_root and (real_root + "/") not in prefixes:
        prefixes.append(real_root + "/")
    return prefixes


def _disconnected_volume_prefixes(disconnected_volumes: List[str]) -> List[str]:
    if not disconnected_volumes:
        return []
    root_prefixes = _volume_root_prefixes()
    out: List[str] = []
    for vol in disconnected_volumes:
        if _WIN_DRIVE_ONLY_RE.match(vol):
            drive_upper = vol.upper()
            drive_lower = vol.lower()
            for d in (drive_upper, drive_lower):
                for sep in ("\\", "/"):
                    cand = f"{d}{sep}"
                    if cand not in out:
                        out.append(cand)
        else:
            for rp in root_prefixes:
                out.append(f"{rp}{vol}/")
    return out


def get_disconnected_volumes(db: Session) -> List[str]:
    """Trả về danh sách tên các ổ đĩa ngoài (sorted, unique) có ảnh trong DB nhưng hiện đang ngắt kết nối."""
    root_prefixes = _volume_root_prefixes()
    filters = [
        Photo.file_path.startswith(rp, autoescape=True) for rp in root_prefixes
    ]
    filters.append(Photo.file_path.op("GLOB")("[A-Za-z]:[/\\\\]*"))
    rows = db.query(Photo.file_path).filter(or_(*filters)).all()
    if not rows:
        return []

    unmounted: set[str] = set()
    checked_cache: Dict[Tuple[str, str], Optional[str]] = {}
    for (fp,) in rows:
        if _WIN_DRIVE_RE.match(fp):
            drive = fp[:2].upper()
            key = ("WIN_DRIVE", drive)
            if key not in checked_cache:
                checked_cache[key] = _get_unmounted_volume_name(fp)
            if checked_cache[key] is not None:
                unmounted.add(checked_cache[key])  # type: ignore[arg-type]
            continue

        for rp in root_prefixes:
            if fp.startswith(rp):
                rel = fp[len(rp) :]
                if "/" in rel:
                    vol_name = rel.split("/", 1)[0]
                    if vol_name:
                        key = (rp, vol_name)
                        if key not in checked_cache:
                            checked_cache[key] = _get_unmounted_volume_name(fp)
                        if checked_cache[key] is not None:
                            unmounted.add(checked_cache[key])  # type: ignore[arg-type]
                break

    return sorted(unmounted)


def list_ai_clusters(db: Session, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    cleanup_missing_photos(db)
    disconnected = get_disconnected_volumes(db)
    excluded_prefixes = _disconnected_volume_prefixes(disconnected)

    total_clusters, total_bytes, total_photos, cluster_ids = (
        photo_repo.get_multi_photo_clusters_page(
            db, limit=limit, offset=offset, excluded_prefixes=excluded_prefixes
        )
    )
    items = []
    dirty = False

    cluster_map = (
        {
            c.id: c
            for c in db.query(Cluster).filter(Cluster.id.in_(cluster_ids)).all()
        }
        if cluster_ids
        else {}
    )

    photos_by_cid: Dict[int, List[Photo]] = {}
    for p in photo_repo.get_photos_by_clusters(db, cluster_ids):
        if p.cluster_id is not None:
            photos_by_cid.setdefault(p.cluster_id, []).append(p)

    for cid in cluster_ids:
        all_c_photos = photos_by_cid.get(cid, [])
        if disconnected:
            photos = [
                p
                for p in all_c_photos
                if _get_unmounted_volume_name(p.file_path) is None
            ]
            has_unmounted_member = len(photos) != len(all_c_photos)
        else:
            photos = all_c_photos
            has_unmounted_member = False

        if len(photos) < 2:
            continue

        has_aesthetic = any(p.aesthetic_score is not None for p in photos)
        rank_fn = _aesthetic_photo_rank_key if has_aesthetic else _size_only_rank_key
        best_photo = max(photos, key=rank_fn)

        cluster_obj: Optional[Cluster] = cluster_map.get(cid)
        if (
            not has_unmounted_member
            and cluster_obj
            and cluster_obj.best_photo_id != best_photo.id
        ):
            cluster_obj.best_photo_id = best_photo.id
            db.add(cluster_obj)
            dirty = True

        if has_aesthetic:
            photos.sort(
                key=lambda x: (
                    0 if x.id == best_photo.id else 1,
                    -(x.aesthetic_score if x.aesthetic_score is not None else -1.0),
                    -(x.quality_score or 0.0),
                    -(x.file_size or 0),
                    x.id or 0,
                )
            )
        else:
            photos.sort(
                key=lambda x: (
                    0 if x.id == best_photo.id else 1,
                    -(x.file_size or 0),
                    x.id or 0,
                )
            )

        items.append(
            {
                "cluster_id": cid,
                "best_photo_id": best_photo.id,
                "photo_count": len(photos),
                "has_aesthetic_scores": has_aesthetic,
                "photos": [
                    _serialize_photo(
                        p,
                        is_best=(p.id == best_photo.id),
                        include_scores=has_aesthetic,
                    )
                    for p in photos
                ],
            }
        )

    if dirty:
        db.commit()

    return {
        "total_clusters": total_clusters,
        "total_bytes": total_bytes,
        "total_photos": total_photos,
        "disconnected_volumes": disconnected,
        "items": items,
    }


def list_duplicate_groups(
    db: Session, limit: int = 100, offset: int = 0
) -> Dict[str, Any]:
    cleanup_missing_photos(db)
    disconnected = get_disconnected_volumes(db)
    excluded_prefixes = _disconnected_volume_prefixes(disconnected)

    total_groups, total_bytes, total_photos, phashes = (
        photo_repo.get_duplicate_groups_page(
            db, limit=limit, offset=offset, excluded_prefixes=excluded_prefixes
        )
    )
    items = []
    dirty = False

    photos_by_phash: Dict[str, List[Photo]] = {}
    for p in photo_repo.get_photos_by_phashes(db, phashes):
        if p.phash is not None:
            photos_by_phash.setdefault(p.phash, []).append(p)

    for idx, phash_val in enumerate(phashes, start=offset + 1):
        all_g_photos = photos_by_phash.get(phash_val, [])
        if disconnected:
            group_photos = [
                p
                for p in all_g_photos
                if _get_unmounted_volume_name(p.file_path) is None
            ]
            has_unmounted_member = len(group_photos) != len(all_g_photos)
        else:
            group_photos = all_g_photos
            has_unmounted_member = False

        if len(group_photos) < 2:
            continue

        # Nhóm ảnh trùng lặp 100% KHÔNG chấm điểm — chỉ ưu tiên giữ file có dung lượng lớn nhất
        best_photo = max(group_photos, key=_size_only_rank_key)

        if not has_unmounted_member:
            for p in group_photos:
                desired_status = (
                    "keep" if p.id == best_photo.id else "exact_duplicate"
                )
                if p.status != desired_status:
                    p.status = desired_status
                    db.add(p)
                    dirty = True

        group_photos.sort(
            key=lambda x: (
                0 if x.id == best_photo.id else 1,
                -(x.file_size or 0),
                x.id or 0,
            )
        )
        dup_count = sum(1 for p in group_photos if p.id != best_photo.id)

        items.append(
            {
                "group_index": idx,
                "phash": phash_val,
                "best_photo_id": best_photo.id,
                "total_photos": len(group_photos),
                "duplicate_count": dup_count,
                "photos": [
                    _serialize_photo(
                        p,
                        is_best=(p.id == best_photo.id),
                        include_scores=False,
                    )
                    for p in group_photos
                ],
            }
        )

    if dirty:
        db.commit()

    return {
        "total_groups": total_groups,
        "total_bytes": total_bytes,
        "total_photos": total_photos,
        "disconnected_volumes": disconnected,
        "items": items,
    }


def rescore_all_photos(db: Session) -> Dict[str, Any]:
    """Đồng bộ nhóm ảnh trùng lặp theo dung lượng file và chấm điểm lại các cụm ảnh tương tự AI."""
    cleanup_missing_photos(db)
    disconnected = get_disconnected_volumes(db)
    all_photos = db.query(Photo).all()
    _, multi_cluster_ids = photo_repo.get_multi_photo_cluster_ids(
        db, limit=1_000_000, offset=0
    )
    clustered_set = set(multi_cluster_ids)

    # Xóa sạch điểm tồn đọng trên các ảnh không thuộc cụm AI (bao gồm ảnh trùng lặp 100%)
    for photo in all_photos:
        if photo.cluster_id is None or photo.cluster_id not in clustered_set:
            photo.quality_score = None
            photo.sharpness_score = None
            photo.exposure_score = None
            photo.contrast_score = None
            photo.aesthetic_score = None
            photo.composition_score = None
            photo.face_score = None
            photo.pose_score = None
            photo.tilt_angle = None
            photo.has_closed_eyes = None
            photo.aesthetic_tags = None
            db.add(photo)

    db.flush()

    # Cập nhật lại bản keep cho các nhóm trùng lặp pHash theo dung lượng lớn nhất
    _, phashes = photo_repo.get_duplicate_phashes(db, limit=1_000_000, offset=0)
    for ph in phashes:
        g_photos = photo_repo.get_photos_by_phash(db, ph)
        if g_photos:
            if disconnected and any(
                _get_unmounted_volume_name(p.file_path) is not None for p in g_photos
            ):
                continue
            best = max(g_photos, key=_size_only_rank_key)
            for p in g_photos:
                p.status = "keep" if p.id == best.id else "exact_duplicate"
                db.add(p)

    db.commit()

    # Ủy quyền chấm điểm (chất lượng + khuôn mặt + bố cục) cho các cụm ảnh tương tự AI
    from app.services.aesthetic_scorer import score_clusters_aesthetics

    cluster_res = score_clusters_aesthetics(db)
    return {
        "scored_count": cluster_res["photos_scored"],
        "total_photos": len(all_photos),
        **cluster_res,
    }


def open_single_photo(db: Session, photo_id: int, mode: str = "preview") -> str:
    photo = photo_repo.get_by_id(db, photo_id)
    if not photo or not os.path.exists(photo.file_path):
        missing = photo.file_path if photo else f"ID {photo_id}"
        raise FileNotFoundError(f"File không tồn tại trên ổ cứng: {missing}")

    if sys.platform == "win32":
        norm_path = os.path.normpath(photo.file_path)
        if mode == "finder":
            subprocess.Popen(["explorer", f"/select,{norm_path}"])
        else:
            os.startfile(norm_path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        if mode == "finder":
            subprocess.run(["open", "-R", photo.file_path])
        else:
            subprocess.run(["open", photo.file_path])
    else:
        target = (
            os.path.dirname(photo.file_path)
            if mode == "finder"
            else photo.file_path
        )
        subprocess.Popen(["xdg-open", target])
    return photo.file_path


def open_multiple_photos(db: Session, photo_ids: List[int]) -> int:
    photos = photo_repo.get_by_ids(db, photo_ids)
    valid_paths = [p.file_path for p in photos if os.path.exists(p.file_path)]
    if not valid_paths:
        raise FileNotFoundError("Không tìm thấy file hợp lệ trên ổ cứng")

    if sys.platform == "win32":
        target_paths = valid_paths[:15]
        for p in target_paths:
            os.startfile(os.path.normpath(p))  # type: ignore[attr-defined]
        return len(target_paths)
    if sys.platform == "darwin":
        subprocess.run(["open", *valid_paths])
        return len(valid_paths)

    target_paths = valid_paths[:15]
    for p in target_paths:
        subprocess.Popen(["xdg-open", p])
    return len(target_paths)


def _rebalance_after_deletion(
    db: Session, affected_phashes: set[str], affected_clusters: set[int]
) -> None:
    for ph in affected_phashes:
        remaining = db.query(Photo).filter(Photo.phash == ph).all()
        if remaining:
            best = max(remaining, key=_size_only_rank_key)
            for p in remaining:
                desired = "keep" if p.id == best.id else "exact_duplicate"
                if p.status != desired:
                    p.status = desired
                    db.add(p)

    for cid in affected_clusters:
        cluster = db.query(Cluster).filter(Cluster.id == cid).first()
        if not cluster:
            continue
        remaining = photo_repo.get_photos_by_cluster(db, cid)
        if len(remaining) >= 2:
            has_aesthetic = any(p.aesthetic_score is not None for p in remaining)
            rank_fn = _aesthetic_photo_rank_key if has_aesthetic else _size_only_rank_key
            best = max(remaining, key=rank_fn)
            cluster.best_photo_id = best.id
            db.add(cluster)
        else:
            for p in remaining:
                p.cluster_id = None
                db.add(p)
            cluster.best_photo_id = None
            db.add(cluster)
            db.flush()
            db.delete(cluster)


_JXA_TRASH_SCRIPT = """ObjC.import('Foundation');
function run(argv) {
  var fm = $.NSFileManager.defaultManager;
  var failed = [];
  for (var i = 0; i < argv.length; i++) {
    var url = $.NSURL.fileURLWithPath($(argv[i]));
    var ok = fm.trashItemAtURLResultingItemURLError(url, null, null);
    if (!ok) failed.push(argv[i]);
  }
  return JSON.stringify(failed);
}"""


def _move_to_trash_dir_fallback(file_path: str, trash_dir: Path) -> None:
    """Chuyển file vào thư mục Thùng rác chỉ định kèm hậu tố chống ghi đè trùng tên."""
    trash_dir.mkdir(parents=True, exist_ok=True)
    base_name = os.path.basename(file_path)
    dest = trash_dir / base_name
    if os.path.lexists(dest):
        stem, ext = os.path.splitext(base_name)
        counter = 1
        while os.path.lexists(dest):
            dest = trash_dir / f"{stem} {time.strftime('%H-%M-%S')}-{counter}{ext}"
            counter += 1
    shutil.move(file_path, str(dest))


def _move_files_to_windows_recycle_bin(existing_paths: List[str]) -> int:
    """Chuyển an toàn danh sách file ảnh vào Windows Recycle Bin qua Win32 SHFileOperationW (không xóa vĩnh viễn)."""
    import ctypes
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        if ctypes.sizeof(ctypes.c_void_p) == 4:
            _pack_ = 1
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 3
    flags = 0x0040 | 0x0010 | 0x0004 | 0x0400  # FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI

    shell32 = ctypes.windll.shell32
    shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell32.SHFileOperationW.restype = ctypes.c_int

    norm_paths = [os.path.normpath(os.path.abspath(p)) for p in existing_paths]
    chunk_size = 200
    for idx in range(0, len(norm_paths), chunk_size):
        batch = norm_paths[idx : idx + chunk_size]
        joined = "\0".join(batch) + "\0\0"
        buf = ctypes.create_unicode_buffer(joined)
        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = ctypes.cast(buf, wintypes.LPCWSTR)
        op.pTo = None
        op.fFlags = flags
        op.fAnyOperationsAborted = False
        op.hNameMappings = None
        op.lpszProgressTitle = None
        shell32.SHFileOperationW(ctypes.byref(op))

    ps_script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        "[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
        "$env:UNIPHOTO_TRASH_TARGET, "
        "'OnlyErrorDialogs', "
        "'SendToRecycleBin')"
    )
    still_present: List[str] = []
    for orig_p, norm_p in zip(existing_paths, norm_paths):
        if os.path.exists(norm_p):
            env = os.environ.copy()
            env["UNIPHOTO_TRASH_TARGET"] = norm_p
            for ps_exe in ("powershell", "pwsh"):
                if not os.path.exists(norm_p):
                    break
                try:
                    subprocess.run(
                        [ps_exe, "-NoProfile", "-NonInteractive", "-Command", ps_script],
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except (OSError, subprocess.SubprocessError):
                    continue
            if os.path.exists(norm_p):
                still_present.append(orig_p)

    if still_present:
        raise OSError(
            f"Không thể chuyển file vào Windows Recycle Bin: {still_present[0]}"
        )

    return sum(1 for p in existing_paths if not os.path.exists(p))


def _move_files_to_trash(file_paths: List[str]) -> int:
    """Chuyển an toàn danh sách file ảnh vào Thùng rác hệ điều hành (macOS Trash / Windows Recycle Bin — không xóa vĩnh viễn)."""
    existing_paths = [p for p in file_paths if p and os.path.exists(p)]
    if not existing_paths:
        return 0

    custom_trash = os.environ.get("UNIPHOTO_TRASH_DIR", "").strip()
    if custom_trash:
        trash_dir = Path(custom_trash)
        moved = 0
        for p in existing_paths:
            _move_to_trash_dir_fallback(p, trash_dir)
            moved += 1
        return moved

    if sys.platform == "darwin":
        failed_from_jxa: set[str] = set()
        abs_paths = [os.path.abspath(p) for p in existing_paths]
        chunk_size = 500
        for idx in range(0, len(abs_paths), chunk_size):
            batch = abs_paths[idx : idx + chunk_size]
            try:
                proc = subprocess.run(
                    ["osascript", "-l", "JavaScript", "-e", _JXA_TRASH_SCRIPT, *batch],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    parsed = json.loads(proc.stdout.strip())
                    if isinstance(parsed, list):
                        failed_from_jxa.update(str(item) for item in parsed)
            except (OSError, subprocess.SubprocessError, ValueError):
                pass

        fallback_trash = Path.home() / ".Trash"
        moved = 0
        for p in existing_paths:
            if os.path.abspath(p) in failed_from_jxa or os.path.exists(p):
                if os.path.exists(p):
                    _move_to_trash_dir_fallback(p, fallback_trash)
            if not os.path.exists(p):
                moved += 1
        return moved

    elif sys.platform == "win32":
        return _move_files_to_windows_recycle_bin(existing_paths)

    fallback_trash = Path.home() / ".local" / "share" / "Trash" / "files"
    moved = 0
    for p in existing_paths:
        if os.path.exists(p):
            _move_to_trash_dir_fallback(p, fallback_trash)
        if not os.path.exists(p):
            moved += 1
    return moved


def remove_photo(db: Session, photo_id: int) -> int:
    """Chuyển ảnh vào Thùng rác macOS, xóa khỏi Database và cân bằng lại cụm/nhóm."""
    photo = photo_repo.get_by_id(db, photo_id)
    if not photo:
        raise FileNotFoundError("Không tìm thấy ảnh trong Database")

    affected_phashes = {photo.phash} if photo.phash else set()
    affected_clusters = {photo.cluster_id} if photo.cluster_id else set()

    if os.path.exists(photo.file_path):
        _move_files_to_trash([photo.file_path])

    db.delete(photo)
    db.flush()
    _rebalance_after_deletion(db, affected_phashes, affected_clusters)
    db.commit()
    return photo_id


def remove_multiple_photos(db: Session, photo_ids: List[int]) -> Dict[str, Any]:
    """Chuyển hàng loạt ảnh vào Thùng rác macOS, xóa bản ghi DB tương ứng và cân bằng lại cụm/nhóm."""
    photos = photo_repo.get_by_ids(db, photo_ids)
    deleted_count = 0
    freed_bytes = 0
    affected_phashes: set[str] = set()
    affected_clusters: set[int] = set()

    existing_paths = [
        p.file_path for p in photos if p.file_path and os.path.exists(p.file_path)
    ]
    failed_paths: set[str] = set()

    if existing_paths:
        try:
            _move_files_to_trash(existing_paths)
        except OSError:
            for path in existing_paths:
                if os.path.exists(path):
                    try:
                        _move_files_to_trash([path])
                    except OSError:
                        failed_paths.add(path)

    for photo in photos:
        if photo.file_path and (
            photo.file_path in failed_paths or os.path.exists(photo.file_path)
        ):
            continue
        freed_bytes += photo.file_size or 0
        if photo.phash:
            affected_phashes.add(photo.phash)
        if photo.cluster_id:
            affected_clusters.add(photo.cluster_id)
        db.delete(photo)
        deleted_count += 1

    db.flush()
    _rebalance_after_deletion(db, affected_phashes, affected_clusters)
    db.commit()
    return {"deleted_count": deleted_count, "freed_bytes": freed_bytes}


def cleanup_missing_photos(db: Session) -> int:
    """Xóa các bản ghi trong DB mà file thật trên ổ cứng đã bị xóa/di chuyển ngoài Finder
    (bảo toàn dữ liệu cho các ảnh nằm trên ổ đĩa ngoài /Volumes/... đang tạm thời ngắt kết nối)."""
    all_photos = db.query(Photo).all()
    removed_count = 0
    affected_phashes: set[str] = set()
    affected_clusters: set[int] = set()

    for photo in all_photos:
        if not os.path.exists(photo.file_path):
            if _get_unmounted_volume_name(photo.file_path) is not None:
                continue
            if photo.phash:
                affected_phashes.add(photo.phash)
            if photo.cluster_id:
                affected_clusters.add(photo.cluster_id)
            db.delete(photo)
            removed_count += 1

    if removed_count > 0:
        db.flush()
        _rebalance_after_deletion(db, affected_phashes, affected_clusters)
        db.commit()

    return removed_count


def reset_all_data(db: Session) -> None:
    """Xóa sạch toàn bộ dữ liệu trong bảng clusters và photos."""
    db.query(Photo).update({Photo.cluster_id: None})
    db.query(Cluster).update({Cluster.best_photo_id: None})
    db.commit()

    db.query(Photo).delete()
    db.query(Cluster).delete()
    db.commit()
