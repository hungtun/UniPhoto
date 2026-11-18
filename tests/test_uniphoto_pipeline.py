import asyncio
import importlib.util
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import imagehash
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageDraw
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from torchvision.models import MobileNet_V2_Weights, mobilenet_v2

import app.services.ai_engine as ai_engine_mod
import app.services.scanner as scanner_mod
from app.core.config import Settings, is_packaged_runtime, resolve_data_dir, settings
from app.core.database import Base
from app.main import app as fastapi_app
from app.models.models import Cluster, Photo
from app.services.aesthetic_scorer import (
    CANONICAL_AESTHETIC_TAGS,
    _resolve_face_task_path,
    score_clusters_aesthetics,
)
from app.services.ai_engine import (
    OnnxMobileNetV2Extractor,
    _resolve_mobilenet_onnx_path,
    _resolve_mobilenet_weights_path,
    cluster_embeddings_chunked,
    cluster_unassigned_photos,
    preprocess_image_cv2,
)
from app.services.photo_service import (
    _serialize_photo,
    list_ai_clusters,
    list_duplicate_groups,
    remove_multiple_photos,
    remove_photo,
)
from app.services.progress_tracker import get_progress, request_cancel, reset_cancel
from app.services.scanner import calculate_phash, scan_directory

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_DB_PATH = REPO_ROOT / "data" / "uniphoto.db"

SCORE_KEYS = (
    "quality_score",
    "sharpness_score",
    "exposure_score",
    "contrast_score",
    "aesthetic_score",
    "composition_score",
    "face_score",
    "pose_score",
    "tilt_angle",
    "has_closed_eyes",
)
FORBIDDEN_POSTURE_TAGS = {"limb_cropped", "awkward_posture", "good_posture"}


def _render_sunset_duplicate_scene(size: tuple[int, int] = (960, 720)) -> Image.Image:
    """Smooth high-contrast mountain sunset whose 16x16 pHash stays identical across JPEG qualities."""
    w, h = size
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / float(h)
        r = min(255, int(190 * (1 - t) + 145 * t))
        g = min(255, int(74 * (1 - t) + 100 * t))
        b = min(255, int(96 * (1 - t) + 74 * t))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    sx, sy, sr = int(w * 0.68), int(h * 0.28), int(w * 0.09)
    draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 220, 122))

    for idx, base_y in enumerate([int(h * 0.54), int(h * 0.68)]):
        pts = [(0, h)]
        for x in range(0, w + 16, 16):
            y = base_y + int(math.sin(x * 0.011 + idx * 1.6) * (46 - idx * 12))
            pts.append((x, y))
        pts.append((w, h))
        shade = 1.0 - idx * 0.32
        draw.polygon(
            pts,
            fill=(int(68 * shade), int(48 * shade), int(92 * shade)),
        )
    return img


def _save_exact_phash_variant(
    img: Image.Image, dest: Path, size_tier: str = "small"
) -> None:
    """Save an image as a valid JPEG whose decoded pixels (and 256-bit 16x16 pHash) are
    100% identical across size_tier in {'small', 'mid', 'large'}, with strictly increasing file_size.
    """
    exif = Image.Exif()
    if size_tier == "mid":
        exif[0x010E] = "UniPhoto camera export metadata " * 40  # ImageDescription
    elif size_tier == "large":
        exif[0x010E] = "UniPhoto master original archive metadata " * 120
    exif_bytes = exif.tobytes() if len(exif) > 0 else b""
    if exif_bytes:
        img.save(dest, format="JPEG", quality=94, subsampling=0, exif=exif_bytes)
    else:
        img.save(dest, format="JPEG", quality=94, subsampling=0)


def _add_fine_grain(img: Image.Image, seed: int = 7, strength: float = 12.0) -> Image.Image:
    arr = np.asarray(img, dtype=np.float32)
    rng = np.random.RandomState(seed)
    noise = rng.randn(*arr.shape).astype(np.float32) * strength
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def _render_sailboat_horizon_frame(
    tilt_deg: float = 0.0,
    shift_x: int = 0,
    out_size: tuple[int, int] = (960, 720),
) -> Image.Image:
    """Overscanned sailboat scene with crisp ocean horizon & vertical masts, optionally tilted."""
    ww, wh = 1280, 960
    tw, th = out_size
    ox, oy = (ww - tw) // 2, (wh - th) // 2
    world = Image.new("RGB", (ww, wh), (196, 224, 248))
    draw = ImageDraw.Draw(world)

    horizon = oy + int(th * 0.56)
    draw.rectangle([0, horizon, ww, wh], fill=(16, 94, 150))
    draw.line([(0, horizon), (ww, horizon)], fill=(236, 248, 255), width=5)

    for bx, sc, sail_col in [(290, 1.0, (250, 250, 252)), (630, 0.80, (242, 92, 78))]:
        cx = ox + bx
        cy = horizon + int(22 * sc)
        hw, hh, mh = int(125 * sc), int(32 * sc), int(225 * sc)
        draw.polygon(
            [
                (cx - hw, cy),
                (cx + hw, cy),
                (cx + int(hw * 0.72), cy + hh),
                (cx - int(hw * 0.72), cy + hh),
            ],
            fill=(52, 36, 28),
        )
        draw.line([(cx, cy), (cx, cy - mh)], fill=(232, 232, 238), width=6)
        draw.polygon(
            [(cx + 5, cy - mh + 10), (cx + int(112 * sc), cy - 16), (cx + 5, cy - 16)],
            fill=sail_col,
        )

    world = _add_fine_grain(world, seed=101, strength=10.0)
    cx_crop = ww // 2 + shift_x
    cy_crop = wh // 2
    if tilt_deg != 0.0:
        world = world.rotate(
            tilt_deg,
            resample=Image.Resampling.BICUBIC,
            center=(cx_crop, cy_crop),
            expand=False,
        )
    return world.crop(
        (cx_crop - tw // 2, cy_crop - th // 2, cx_crop + tw // 2, cy_crop + th // 2)
    )


def _render_portrait_frame(
    size: tuple[int, int] = (720, 960),
    full_body: bool = False,
    eyes_closed: bool = False,
    shift_x: int = 0,
) -> Image.Image:
    """Synthetic close-up or small full-body portrait detected by MediaPipe FaceLandmarker."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    bg = np.zeros((h, w, 3), dtype=np.float32)
    if full_body:
        bg[..., 0] = 95 + 55 * (yy / h)
        bg[..., 1] = 135 + 45 * (1 - yy / h)
        bg[..., 2] = 90 + 30 * (1 - yy / h)
    else:
        bg[..., 0] = 58 + 30 * (1 - yy / h)
        bg[..., 1] = 72 + 34 * (1 - yy / h)
        bg[..., 2] = 108 + 38 * (1 - yy / h)

    img = Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(img)

    if full_body:
        draw.rectangle([0, int(h * 0.72), w, h], fill=(64, 92, 54))
        for tx in (int(w * 0.10) + shift_x // 2, int(w * 0.88) + shift_x // 2):
            draw.rectangle([tx - 14, int(h * 0.28), tx + 14, int(h * 0.74)], fill=(78, 56, 42))
            draw.ellipse([tx - 65, int(h * 0.12), tx + 65, int(h * 0.40)], fill=(46, 88, 48))
        cx, cy = w // 2 + shift_x, int(h * 0.22)
        rx, ry = int(w * 0.068), int(h * 0.068)
    else:
        draw.rectangle(
            [int(w * 0.06) + shift_x, int(h * 0.08), int(w * 0.22) + shift_x, int(h * 0.26)],
            outline=(140, 155, 180),
            width=5,
        )
        cx, cy = w // 2 + shift_x, int(h * 0.42)
        rx, ry = int(w * 0.22), int(h * 0.23)

    draw.ellipse(
        [cx - int(rx * 1.18), cy - int(ry * 1.22), cx + int(rx * 1.18), cy + int(ry * 0.95)],
        fill=(34, 24, 20),
    )
    nw = max(6, int(rx * 0.46))
    draw.rectangle([cx - nw, cy + int(ry * 0.75), cx + nw, cy + int(ry * 1.45)], fill=(214, 168, 140))
    torso_bottom = int(h * 0.88) if full_body else h
    sw = int(rx * (2.2 if full_body else 2.1))
    shirt = (168, 54, 58) if full_body else (38, 56, 88)
    draw.polygon(
        [
            (cx - sw, torso_bottom),
            (cx - int(sw * 0.85), cy + int(ry * 1.30)),
            (cx + int(sw * 0.85), cy + int(ry * 1.30)),
            (cx + sw, torso_bottom),
        ],
        fill=shirt,
    )

    ew, eh = max(3, int(rx * 0.18)), max(5, int(ry * 0.26))
    draw.ellipse([cx - rx - ew // 2, cy - eh // 3, cx - rx + ew, cy + eh], fill=(218, 170, 142))
    draw.ellipse([cx + rx - ew, cy - eh // 3, cx + rx + ew // 2, cy + eh], fill=(218, 170, 142))

    arr = np.asarray(img, dtype=np.float32)
    dx = (xx - cx) / max(1.0, float(rx))
    dy = (yy - cy) / max(1.0, float(ry))
    dist2 = dx * dx + dy * dy
    mask = dist2 <= 1.0
    shade = np.clip(1.06 - 0.24 * dist2 - 0.08 * np.abs(dx), 0.72, 1.08)
    skin = np.stack([232 * shade, 186 * shade, 156 * shade], axis=-1)
    cheek_l = np.exp(
        -(((xx - (cx - 0.48 * rx)) / (0.32 * rx)) ** 2 + ((yy - (cy + 0.14 * ry)) / (0.24 * ry)) ** 2)
    )
    cheek_r = np.exp(
        -(((xx - (cx + 0.48 * rx)) / (0.32 * rx)) ** 2 + ((yy - (cy + 0.14 * ry)) / (0.24 * ry)) ** 2)
    )
    skin[..., 0] += 12 * (cheek_l + cheek_r)
    skin[..., 1] -= 6 * (cheek_l + cheek_r)
    arr[mask] = np.clip(skin[mask], 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    draw.pieslice(
        [cx - int(rx * 1.08), cy - int(ry * 1.16), cx + int(rx * 1.08), cy - int(ry * 0.18)],
        180,
        360,
        fill=(34, 24, 20),
    )

    ey_y = cy - int(ry * 0.12)
    brow_y = cy - int(ry * 0.30)
    eye_dx = int(rx * 0.42)
    eye_rx = max(4, int(rx * 0.20))
    eye_ry = max(3, int(ry * 0.10))
    bw_thick = max(2, int(ry * 0.055))
    for sign in (-1, 1):
        ex = cx + sign * eye_dx
        draw.arc(
            [ex - int(eye_rx * 1.25), brow_y - eye_ry, ex + int(eye_rx * 1.25), brow_y + eye_ry],
            195,
            345,
            fill=(48, 34, 28),
            width=bw_thick,
        )
        if eyes_closed:
            draw.arc(
                [ex - eye_rx, ey_y - eye_ry // 2, ex + eye_rx, ey_y + eye_ry],
                10,
                170,
                fill=(64, 40, 34),
                width=max(2, int(ry * 0.045)),
            )
        else:
            draw.ellipse(
                [ex - eye_rx, ey_y - eye_ry, ex + eye_rx, ey_y + eye_ry],
                fill=(246, 246, 248),
                outline=(72, 48, 42),
                width=max(1, int(ry * 0.025)),
            )
            ir = max(2, int(eye_ry * 0.92))
            draw.ellipse([ex - ir, ey_y - ir, ex + ir, ey_y + ir], fill=(64, 44, 32))
            pr = max(1, int(ir * 0.48))
            draw.ellipse([ex - pr, ey_y - pr, ex + pr, ey_y + pr], fill=(16, 14, 14))
            cr = max(1, int(pr * 0.45))
            draw.ellipse(
                [ex - pr // 2, ey_y - pr // 2, ex - pr // 2 + cr, ey_y - pr // 2 + cr],
                fill=(255, 255, 255),
            )
            draw.arc(
                [ex - eye_rx, ey_y - eye_ry, ex + eye_rx, ey_y + eye_ry],
                190,
                350,
                fill=(32, 22, 18),
                width=max(2, int(ry * 0.04)),
            )

    nose_top = cy - int(ry * 0.08)
    nose_bot = cy + int(ry * 0.26)
    nw_tip = max(3, int(rx * 0.14))
    draw.line(
        [(cx - max(1, nw_tip // 3), nose_top), (cx - nw_tip // 2, nose_bot)],
        fill=(192, 144, 118),
        width=max(1, int(rx * 0.03)),
    )
    draw.ellipse(
        [cx - nw_tip, nose_bot - max(2, nw_tip // 3), cx - nw_tip // 3, nose_bot + max(2, nw_tip // 3)],
        fill=(156, 108, 86),
    )
    draw.ellipse(
        [cx + nw_tip // 3, nose_bot - max(2, nw_tip // 3), cx + nw_tip, nose_bot + max(2, nw_tip // 3)],
        fill=(156, 108, 86),
    )

    my = cy + int(ry * 0.50)
    mw = max(6, int(rx * 0.34))
    mh = max(3, int(ry * 0.10))
    draw.ellipse([cx - mw, my - mh, cx + mw, my + mh], fill=(188, 98, 96))
    draw.line([(cx - mw, my), (cx + mw, my)], fill=(128, 56, 56), width=max(1, int(ry * 0.025)))
    return img


class TestUniPhotoPipeline(unittest.TestCase):
    """End-to-end isolated pipeline tests using sqlite:///:memory: and UNIPHOTO_TRASH_DIR."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._live_db_before = (
            LIVE_DB_PATH.exists(),
            LIVE_DB_PATH.stat().st_mtime_ns if LIVE_DB_PATH.exists() else None,
            LIVE_DB_PATH.stat().st_size if LIVE_DB_PATH.exists() else None,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        live_db_after = (
            LIVE_DB_PATH.exists(),
            LIVE_DB_PATH.stat().st_mtime_ns if LIVE_DB_PATH.exists() else None,
            LIVE_DB_PATH.stat().st_size if LIVE_DB_PATH.exists() else None,
        )
        if cls._live_db_before != live_db_after:
            raise AssertionError("Live data/uniphoto.db was unexpectedly modified by unit tests!")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="uniphoto_test_")
        self.root = Path(self._tmp.name)
        self.photos_dir = self.root / "photos"
        self.trash_dir = self.root / "trash"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir.mkdir(parents=True, exist_ok=True)

        self._prev_trash_env = os.environ.get("UNIPHOTO_TRASH_DIR")
        self._prev_volumes_root_env = os.environ.get("UNIPHOTO_VOLUMES_ROOT")
        self._prev_unmounted_env = os.environ.get("UNIPHOTO_UNMOUNTED_VOLUMES")
        os.environ["UNIPHOTO_TRASH_DIR"] = str(self.trash_dir)
        os.environ.pop("UNIPHOTO_VOLUMES_ROOT", None)
        os.environ.pop("UNIPHOTO_UNMOUNTED_VOLUMES", None)
        reset_cancel()

        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def _enable_fk(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON;")
            cur.close()

        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.Session()

    def tearDown(self) -> None:
        reset_cancel()
        self.db.close()
        self.engine.dispose()
        if self._prev_trash_env is None:
            os.environ.pop("UNIPHOTO_TRASH_DIR", None)
        else:
            os.environ["UNIPHOTO_TRASH_DIR"] = self._prev_trash_env
        if self._prev_volumes_root_env is None:
            os.environ.pop("UNIPHOTO_VOLUMES_ROOT", None)
        else:
            os.environ["UNIPHOTO_VOLUMES_ROOT"] = self._prev_volumes_root_env
        if self._prev_unmounted_env is None:
            os.environ.pop("UNIPHOTO_UNMOUNTED_VOLUMES", None)
        else:
            os.environ["UNIPHOTO_UNMOUNTED_VOLUMES"] = self._prev_unmounted_env
        self._tmp.cleanup()

    def _assert_all_photo_columns_unscored(self, photo: Photo) -> None:
        for attr in (
            "quality_score",
            "sharpness_score",
            "exposure_score",
            "contrast_score",
            "aesthetic_score",
            "composition_score",
            "face_score",
            "pose_score",
            "tilt_angle",
            "has_closed_eyes",
            "aesthetic_tags",
        ):
            self.assertIsNone(
                getattr(photo, attr),
                f"Expected {attr} to be None on unscored photo {photo.file_path}",
            )

    def test_01_scan_directory_exif_orientation_and_size_only_duplicates(self) -> None:
        sub_a = self.photos_dir / "01_compressed_first"
        sub_b = self.photos_dir / "02_master_later"
        sub_a.mkdir()
        sub_b.mkdir()

        # 1) Raw 640x400 image with EXIF Orientation=6 (90° CW -> oriented 400x640)
        raw_landscape = Image.new("RGB", (640, 400), (42, 118, 186))
        ImageDraw.Draw(raw_landscape).rectangle([80, 60, 560, 340], fill=(238, 184, 72))
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation: Rotate 90 CW
        exif[0x0132] = "2025:08:15 16:45:30"  # DateTime
        rotated_path = sub_a / "IMG_oriented.jpg"
        raw_landscape.save(rotated_path, format="JPEG", quality=92, exif=exif.tobytes())

        # 2) Exact perceptual duplicates where smaller compressed copy is scanned BEFORE largest master
        sunset = _render_sunset_duplicate_scene()
        dup_small = sub_a / "IMG_sunset_small.jpg"
        dup_mid = sub_a / "IMG_sunset_mid.jpg"
        dup_large = sub_b / "IMG_sunset_master.jpg"
        _save_exact_phash_variant(sunset, dup_small, size_tier="small")
        _save_exact_phash_variant(sunset, dup_mid, size_tier="mid")
        _save_exact_phash_variant(sunset, dup_large, size_tier="large")

        with Image.open(dup_small) as im_s, Image.open(dup_large) as im_l:
            self.assertEqual(calculate_phash(im_s), calculate_phash(im_l))
        self.assertLess(dup_small.stat().st_size, dup_mid.stat().st_size)
        self.assertLess(dup_mid.stat().st_size, dup_large.stat().st_size)

        res = scan_directory(str(self.photos_dir), self.db)
        self.assertEqual(res["total_found"], 4)
        self.assertEqual(res["new_added"], 2)
        self.assertEqual(res["exact_duplicates"], 2)
        self.assertEqual(res["errors_count"], 0)

        by_path = {p.file_path: p for p in self.db.query(Photo).all()}
        rot_photo = by_path[os.path.abspath(rotated_path)]
        self.assertEqual((rot_photo.width, rot_photo.height), (400, 640))
        self.assertEqual(rot_photo.timestamp, datetime(2025, 8, 15, 16, 45, 30))

        # Largest file_size wins "keep"; smaller duplicates are "exact_duplicate"
        self.assertEqual(by_path[os.path.abspath(dup_large)].status, "keep")
        self.assertEqual(by_path[os.path.abspath(dup_mid)].status, "exact_duplicate")
        self.assertEqual(by_path[os.path.abspath(dup_small)].status, "exact_duplicate")

        for photo in by_path.values():
            self._assert_all_photo_columns_unscored(photo)

    def test_02_cluster_unassigned_photos_and_legacy_stale_score_immunity(self) -> None:
        # Exact duplicate pair
        sunset = _render_sunset_duplicate_scene()
        dup_keep = self.photos_dir / "dup_master.jpg"
        dup_copy = self.photos_dir / "dup_compressed.jpg"
        _save_exact_phash_variant(sunset, dup_keep, size_tier="large")
        _save_exact_phash_variant(sunset, dup_copy, size_tier="small")

        # AI burst pair (smaller level vs larger tilted)
        burst_small = self.photos_dir / "sail_small.jpg"
        burst_large = self.photos_dir / "sail_large.jpg"
        _render_sailboat_horizon_frame(tilt_deg=0.0, shift_x=0).save(
            burst_small, format="JPEG", quality=82
        )
        _render_sailboat_horizon_frame(tilt_deg=-6.5, shift_x=18).save(
            burst_large, format="JPEG", quality=98
        )
        self.assertGreater(burst_large.stat().st_size, burst_small.stat().st_size)

        scan_directory(str(self.photos_dir), self.db)

        # Inject stale legacy scores across all photos prior to clustering
        for p in self.db.query(Photo).all():
            p.quality_score = 93.4
            p.sharpness_score = 91.0
            p.aesthetic_score = 89.5
            p.composition_score = 88.0
            p.pose_score = 77.0
            p.aesthetic_tags = json.dumps(["level_horizon"])
            self.db.add(p)
        self.db.commit()

        cluster_res = cluster_unassigned_photos(self.db)
        self.assertEqual(cluster_res["clusters_created"], 1)
        self.assertEqual(cluster_res["photos_clustered"], 2)

        # Verify cluster_unassigned_photos cleared all stale scores and elected largest file_size
        all_photos = self.db.query(Photo).all()
        for p in all_photos:
            self._assert_all_photo_columns_unscored(p)

        by_path = {p.file_path: p for p in all_photos}
        cluster_obj = self.db.query(Cluster).one()
        self.assertEqual(cluster_obj.best_photo_id, by_path[os.path.abspath(burst_large)].id)

        # Inject legacy stale technical quality_score (without aesthetic_score) on smaller files
        # to verify list_duplicate_groups & unscored list_ai_clusters stay immune to stale scores
        by_path[os.path.abspath(dup_copy)].quality_score = 99.9
        by_path[os.path.abspath(dup_copy)].sharpness_score = 99.9
        by_path[os.path.abspath(burst_small)].quality_score = 99.9
        by_path[os.path.abspath(burst_small)].sharpness_score = 99.9
        self.db.commit()

        dup_payload = list_duplicate_groups(self.db)
        self.assertEqual(dup_payload["total_groups"], 1)
        dup_group = dup_payload["items"][0]
        self.assertEqual(dup_group["best_photo_id"], by_path[os.path.abspath(dup_keep)].id)
        for serialized in dup_group["photos"]:
            for key in SCORE_KEYS:
                self.assertIsNone(serialized[key])
            self.assertEqual(serialized["aesthetic_tags"], [])

        sim_payload = list_ai_clusters(self.db)
        self.assertEqual(sim_payload["total_clusters"], 1)
        sim_group = sim_payload["items"][0]
        self.assertFalse(sim_group["has_aesthetic_scores"])
        self.assertEqual(sim_group["best_photo_id"], by_path[os.path.abspath(burst_large)].id)
        for serialized in sim_group["photos"]:
            for key in SCORE_KEYS:
                self.assertIsNone(serialized[key])
            self.assertEqual(serialized["aesthetic_tags"], [])

    def test_03_score_clusters_aesthetics_tilt_portraits_and_duplicates_unscored(self) -> None:
        # 0) Exact duplicate pair (must stay completely unscored after score_clusters_aesthetics)
        sunset = _render_sunset_duplicate_scene()
        dup_master = self.photos_dir / "dup_master.jpg"
        dup_small = self.photos_dir / "dup_small.jpg"
        _save_exact_phash_variant(sunset, dup_master, size_tier="large")
        _save_exact_phash_variant(sunset, dup_small, size_tier="small")

        # 1) Horizon burst: level sharp (smaller file) vs -6.5° tilted (larger file)
        sail_level = self.photos_dir / "sail_level.jpg"
        sail_tilted = self.photos_dir / "sail_tilted.jpg"
        _render_sailboat_horizon_frame(tilt_deg=0.0, shift_x=0).save(
            sail_level, format="JPEG", quality=84
        )
        _render_sailboat_horizon_frame(tilt_deg=-6.5, shift_x=18).save(
            sail_tilted, format="JPEG", quality=99
        )

        # 2) Close-up portrait burst: open sharp eyes (smaller file) vs closed eyes (larger file)
        cu_open = self.photos_dir / "closeup_open.jpg"
        cu_closed = self.photos_dir / "closeup_closed.jpg"
        _render_portrait_frame(full_body=False, eyes_closed=False, shift_x=0).save(
            cu_open, format="JPEG", quality=85
        )
        _render_portrait_frame(full_body=False, eyes_closed=True, shift_x=28).save(
            cu_closed, format="JPEG", quality=99
        )

        # 3) Small full-body portrait burst (~6.8% face size): open eyes vs closed eyes
        fb_open = self.photos_dir / "fullbody_open.jpg"
        fb_closed = self.photos_dir / "fullbody_closed.jpg"
        _render_portrait_frame(full_body=True, eyes_closed=False, shift_x=0).save(
            fb_open, format="JPEG", quality=85
        )
        _render_portrait_frame(full_body=True, eyes_closed=True, shift_x=28).save(
            fb_closed, format="JPEG", quality=99
        )

        self.assertGreater(sail_tilted.stat().st_size, sail_level.stat().st_size)
        self.assertGreater(cu_closed.stat().st_size, cu_open.stat().st_size)
        self.assertGreater(fb_closed.stat().st_size, fb_open.stat().st_size)

        scan_directory(str(self.photos_dir), self.db)
        c_res = cluster_unassigned_photos(self.db)
        self.assertEqual(c_res["clusters_created"], 3)
        self.assertEqual(c_res["photos_clustered"], 6)

        score_res = score_clusters_aesthetics(self.db)
        self.assertEqual(score_res["clusters_scored"], 3)
        self.assertEqual(score_res["photos_scored"], 6)
        self.assertEqual(score_res["best_changed_count"], 3)

        by_path = {p.file_path: p for p in self.db.query(Photo).all()}

        # Exact duplicates must remain unscored in DB and API serialization
        self._assert_all_photo_columns_unscored(by_path[os.path.abspath(dup_master)])
        self._assert_all_photo_columns_unscored(by_path[os.path.abspath(dup_small)])
        for d_item in list_duplicate_groups(self.db)["items"][0]["photos"]:
            for key in SCORE_KEYS:
                self.assertIsNone(d_item[key])

        # Every clustered photo has aesthetic/composition/quality populated, pose_score None, and zero posture tags
        clustered_paths = [sail_level, sail_tilted, cu_open, cu_closed, fb_open, fb_closed]
        for path in clustered_paths:
            p = by_path[os.path.abspath(path)]
            self.assertIsNotNone(p.aesthetic_score)
            self.assertIsNotNone(p.composition_score)
            self.assertIsNotNone(p.quality_score)
            self.assertIsNone(p.pose_score)
            tags = set(json.loads(p.aesthetic_tags or "[]"))
            self.assertTrue(tags.issubset(CANONICAL_AESTHETIC_TAGS))
            self.assertTrue(tags.isdisjoint(FORBIDDEN_POSTURE_TAGS))

        # Horizon tilt assertions
        p_tilted = by_path[os.path.abspath(sail_tilted)]
        p_level = by_path[os.path.abspath(sail_level)]
        self.assertIn("tilted_horizon", json.loads(p_tilted.aesthetic_tags or "[]"))
        self.assertGreaterEqual(p_tilted.tilt_angle or 0.0, 1.8)
        self.assertGreater(p_level.aesthetic_score or 0.0, p_tilted.aesthetic_score or 0.0)

        # Close-up & small full-body portrait face_score + has_closed_eyes assertions
        for open_path, closed_path in [(cu_open, cu_closed), (fb_open, fb_closed)]:
            p_open = by_path[os.path.abspath(open_path)]
            p_closed = by_path[os.path.abspath(closed_path)]
            self.assertIsNotNone(p_open.face_score, f"Expected face_score on {open_path.name}")
            self.assertIsNotNone(p_closed.face_score, f"Expected face_score on {closed_path.name}")
            self.assertFalse(bool(p_open.has_closed_eyes))
            self.assertTrue(bool(p_closed.has_closed_eyes))
            self.assertIn("eyes_closed", json.loads(p_closed.aesthetic_tags or "[]"))
            self.assertGreater(p_open.aesthetic_score or 0.0, p_closed.aesthetic_score or 0.0)

        # Verify list_ai_clusters exposes has_aesthetic_scores=True, pose_score=None, and updated winners
        sim_payload = list_ai_clusters(self.db)
        self.assertEqual(sim_payload["total_clusters"], 3)
        expected_winners = {
            by_path[os.path.abspath(sail_level)].id,
            by_path[os.path.abspath(cu_open)].id,
            by_path[os.path.abspath(fb_open)].id,
        }
        actual_winners = set()
        for c_item in sim_payload["items"]:
            self.assertTrue(c_item["has_aesthetic_scores"])
            actual_winners.add(c_item["best_photo_id"])
            for sp in c_item["photos"]:
                self.assertIsNotNone(sp["aesthetic_score"])
                self.assertIsNotNone(sp["composition_score"])
                self.assertIsNotNone(sp["quality_score"])
                self.assertIsNone(sp["pose_score"])
                self.assertTrue(set(sp["aesthetic_tags"]).isdisjoint(FORBIDDEN_POSTURE_TAGS))
        self.assertEqual(actual_winners, expected_winners)

    def test_04_remove_photos_safe_trash_collision_and_group_rebalance(self) -> None:
        album_1 = self.photos_dir / "Album_One"
        album_2 = self.photos_dir / "Album_Two"
        album_3 = self.photos_dir / "Album_Three"
        burst_dir = self.photos_dir / "Bursts"
        for d in (album_1, album_2, album_3, burst_dir):
            d.mkdir()

        # 3 exact duplicates across subfolders, two sharing identical basename "IMG_9001.jpg"
        sunset = _render_sunset_duplicate_scene()
        dup_1 = album_1 / "IMG_9001.jpg"  # largest
        dup_2 = album_2 / "IMG_9001.jpg"  # medium (same basename!)
        dup_3 = album_3 / "IMG_9001_backup.jpg"  # smallest
        _save_exact_phash_variant(sunset, dup_1, size_tier="large")
        _save_exact_phash_variant(sunset, dup_2, size_tier="mid")
        _save_exact_phash_variant(sunset, dup_3, size_tier="small")

        size_dup_1 = dup_1.stat().st_size
        size_dup_2 = dup_2.stat().st_size
        self.assertNotEqual(size_dup_1, size_dup_2)

        # 3-photo AI burst cluster: 0° level > -3.2° mild tilt > -6.8° steeper tilt
        b_best = burst_dir / "burst_best.jpg"
        b_second = burst_dir / "burst_second.jpg"
        b_third = burst_dir / "burst_third.jpg"
        _render_sailboat_horizon_frame(tilt_deg=0.0, shift_x=0).save(
            b_best, format="JPEG", quality=95
        )
        _render_sailboat_horizon_frame(tilt_deg=-3.2, shift_x=8).save(
            b_second, format="JPEG", quality=93
        )
        _render_sailboat_horizon_frame(tilt_deg=-6.8, shift_x=16).save(
            b_third, format="JPEG", quality=90
        )

        scan_directory(str(self.photos_dir), self.db)
        cluster_unassigned_photos(self.db)
        score_clusters_aesthetics(self.db)

        by_path = {p.file_path: p for p in self.db.query(Photo).all()}
        id_dup_1 = by_path[os.path.abspath(dup_1)].id
        id_dup_2 = by_path[os.path.abspath(dup_2)].id
        id_dup_3 = by_path[os.path.abspath(dup_3)].id
        id_b_best = by_path[os.path.abspath(b_best)].id
        id_b_second = by_path[os.path.abspath(b_second)].id
        id_b_third = by_path[os.path.abspath(b_third)].id

        self.assertEqual(by_path[os.path.abspath(dup_1)].status, "keep")
        cluster_obj = self.db.query(Cluster).one()
        self.assertEqual(cluster_obj.best_photo_id, id_b_best)

        # Step A: remove_photo on dup_1 (album_1/IMG_9001.jpg) -> rebalances dup_2 to "keep"
        removed_id = remove_photo(self.db, id_dup_1)
        self.assertEqual(removed_id, id_dup_1)
        self.assertFalse(dup_1.exists())
        self.db.expire_all()
        self.assertEqual(self.db.get(Photo, id_dup_2).status, "keep")

        # Step B: remove_multiple_photos on [dup_2 (album_2/IMG_9001.jpg — basename collision!), b_best]
        batch_res = remove_multiple_photos(self.db, [id_dup_2, id_b_best])
        self.assertEqual(batch_res["deleted_count"], 2)
        self.assertGreater(batch_res["freed_bytes"], size_dup_2)
        self.assertFalse(dup_2.exists())
        self.assertFalse(b_best.exists())

        # Verify all 3 trashed files survive inside UNIPHOTO_TRASH_DIR with zero overwrite!
        trashed_files = list(self.trash_dir.iterdir())
        self.assertEqual(len(trashed_files), 3)
        trashed_9001 = [p for p in trashed_files if p.name.startswith("IMG_9001") and p.suffix == ".jpg"]
        self.assertEqual(len(trashed_9001), 2)
        self.assertEqual({p.stat().st_size for p in trashed_9001}, {size_dup_1, size_dup_2})

        # Verify remaining duplicate (dup_3) promoted to "keep" & remaining AI cluster rebalanced to b_second
        self.db.expire_all()
        self.assertEqual(self.db.get(Photo, id_dup_3).status, "keep")
        remaining_cluster = self.db.query(Cluster).one()
        self.assertEqual(remaining_cluster.best_photo_id, id_b_second)

        # Step C: remove_photo on b_second -> 1 photo left -> cluster dissolves cleanly
        remove_photo(self.db, id_b_second)
        self.db.expire_all()
        self.assertEqual(self.db.query(Cluster).count(), 0)
        self.assertIsNone(self.db.get(Photo, id_b_third).cluster_id)
        self.assertEqual(len(list(self.trash_dir.iterdir())), 4)

    def test_05_chunked_cosine_similarity_equivalence_and_scale(self) -> None:
        rng = np.random.RandomState(20261118)
        n_samples = 1200
        dim = 1280
        threshold = 0.85

        # Build 90 distinct 1280-d prototypes + noisy cluster members scattered across all 10 blocks
        n_protos = 90
        prototypes = rng.randn(n_protos, dim).astype(np.float32)
        vectors = np.empty((n_samples, dim), dtype=np.float32)

        for idx in range(n_samples):
            if idx < 720:
                proto = prototypes[idx % n_protos]
                vectors[idx] = proto + 0.22 * rng.randn(dim).astype(np.float32)
            elif idx < 780:
                # Bridge vectors correlated with two prototypes to exercise greedy visited tie-breaking
                p_a = prototypes[idx % n_protos]
                p_b = prototypes[(idx * 7 + 3) % n_protos]
                vectors[idx] = 0.90 * p_a + 0.42 * p_b + 0.05 * rng.randn(dim).astype(np.float32)
            else:
                vectors[idx] = rng.randn(dim).astype(np.float32)

        perm = rng.permutation(n_samples)
        embeddings = vectors[perm].astype(np.float32)

        # Reference full N x N cosine_similarity greedy clustering
        sim_matrix = cosine_similarity(embeddings)
        # Ensure zero test vectors sit right on floating-point precision epsilon of threshold
        near_boundary = np.abs(sim_matrix - threshold) < 1e-4
        np.fill_diagonal(near_boundary, False)
        self.assertFalse(bool(np.any(near_boundary)))

        visited = [False] * n_samples
        expected_groups: list[list[int]] = []
        for i in range(n_samples):
            if visited[i]:
                continue
            visited[i] = True
            group = [i]
            for j in range(i + 1, n_samples):
                if not visited[j] and sim_matrix[i, j] >= threshold:
                    visited[j] = True
                    group.append(j)
            if len(group) >= 2:
                expected_groups.append(group)

        actual_groups, cancelled = cluster_embeddings_chunked(
            embeddings,
            similarity_threshold=threshold,
            block_size=128,
        )
        self.assertFalse(cancelled)
        self.assertEqual(len(expected_groups), n_protos)
        self.assertEqual(actual_groups, expected_groups)

    def test_06_cooperative_cancellation_scan_and_cluster_preservation(self) -> None:
        # Prepare 6 photos: 2 exact duplicates + 2 sailboat burst frames + 2 closeup portrait frames
        sunset = _render_sunset_duplicate_scene()
        _save_exact_phash_variant(sunset, self.photos_dir / "01_dup_large.jpg", size_tier="large")
        _save_exact_phash_variant(sunset, self.photos_dir / "02_dup_small.jpg", size_tier="small")
        _render_sailboat_horizon_frame(tilt_deg=0.0, shift_x=0).save(
            self.photos_dir / "03_sail_level.jpg", format="JPEG", quality=85
        )
        _render_sailboat_horizon_frame(tilt_deg=-6.5, shift_x=18).save(
            self.photos_dir / "04_sail_tilted.jpg", format="JPEG", quality=98
        )
        _render_portrait_frame(full_body=False, eyes_closed=False, shift_x=0).save(
            self.photos_dir / "05_portrait_open.jpg", format="JPEG", quality=85
        )
        _render_portrait_frame(full_body=False, eyes_closed=True, shift_x=28).save(
            self.photos_dir / "06_portrait_closed.jpg", format="JPEG", quality=98
        )

        # Part A: Cancel mid-scan right after processing 2 files
        def _cancel_after_two(idx: int, _new_added: int, _dups: int, _fname: str) -> None:
            if idx >= 2:
                request_cancel()

        partial_scan = scan_directory(
            str(self.photos_dir), self.db, progress_callback=_cancel_after_two
        )
        self.assertTrue(partial_scan["cancelled"])
        self.assertEqual(partial_scan["total_found"], 6)
        self.assertEqual(len(partial_scan["items"]), 2)

        prog_after_scan_cancel = get_progress()
        self.assertEqual(prog_after_scan_cancel["phase"], "cancelled")
        self.assertTrue(prog_after_scan_cancel["cancel_requested"])
        self.assertEqual(prog_after_scan_cancel["current_file"], "Đã dừng quét thư mục")

        # Rollback uncommitted state to prove the 2 processed items were cleanly committed to SQLite
        self.db.rollback()
        self.assertEqual(self.db.query(Photo).count(), 2)

        # Complete scanning remaining photos, build initial AI clusters, and score them
        full_scan = scan_directory(str(self.photos_dir), self.db)
        self.assertFalse(full_scan["cancelled"])
        self.assertEqual(full_scan["already_indexed"], 2)
        self.assertEqual(self.db.query(Photo).count(), 6)

        initial_cluster = cluster_unassigned_photos(self.db)
        self.assertFalse(initial_cluster["cancelled"])
        self.assertEqual(initial_cluster["clusters_created"], 2)
        score_clusters_aesthetics(self.db)

        clusters_before = {
            c.id: c.best_photo_id for c in self.db.query(Cluster).all()
        }
        photo_state_before = {
            p.id: (p.cluster_id, p.aesthetic_score)
            for p in self.db.query(Photo).all()
        }
        self.assertEqual(len(clusters_before), 2)

        # Part B: Trigger request_cancel() mid-embedding extraction during cluster_unassigned_photos
        call_counter = {"count": 0}

        def _preprocess_then_cancel(file_path: str):
            call_counter["count"] += 1
            out = preprocess_image_cv2(file_path)
            if call_counter["count"] >= 2:
                request_cancel()
            return out

        with patch(
            "app.services.ai_engine.preprocess_image_cv2",
            side_effect=_preprocess_then_cancel,
        ):
            cancelled_cluster = cluster_unassigned_photos(self.db, batch_size=1)

        self.assertTrue(cancelled_cluster["cancelled"])
        self.assertEqual(cancelled_cluster["clusters_created"], 0)
        prog_after_cluster_cancel = get_progress()
        self.assertEqual(prog_after_cluster_cancel["phase"], "cancelled")
        self.assertEqual(prog_after_cluster_cancel["current_file"], "Đã dừng gom cụm AI")

        # Existing clusters, best_photo_ids, and aesthetic scores must remain 100% intact!
        self.db.expire_all()
        clusters_after = {
            c.id: c.best_photo_id for c in self.db.query(Cluster).all()
        }
        photo_state_after = {
            p.id: (p.cluster_id, p.aesthetic_score)
            for p in self.db.query(Photo).all()
        }
        self.assertEqual(clusters_after, clusters_before)
        self.assertEqual(photo_state_after, photo_state_before)

    def test_07_server_side_pagination_totals_and_slicing(self) -> None:
        # Group 1 (Sunset): 3 exact duplicates (only "keep" scanned into AI, stays unclustered)
        sunset = _render_sunset_duplicate_scene()
        s_large = self.photos_dir / "sunset_large.jpg"
        s_mid = self.photos_dir / "sunset_mid.jpg"
        s_small = self.photos_dir / "sunset_small.jpg"
        _save_exact_phash_variant(sunset, s_large, size_tier="large")
        _save_exact_phash_variant(sunset, s_mid, size_tier="mid")
        _save_exact_phash_variant(sunset, s_small, size_tier="small")

        # Group 2 (Sailboat level): 2 exact duplicates + 1 tilted burst partner -> Cluster 1
        sail_0 = _render_sailboat_horizon_frame(tilt_deg=0.0, shift_x=0)
        sail_dup_large = self.photos_dir / "sail_level_large.jpg"
        sail_dup_small = self.photos_dir / "sail_level_small.jpg"
        _save_exact_phash_variant(sail_0, sail_dup_large, size_tier="large")
        _save_exact_phash_variant(sail_0, sail_dup_small, size_tier="small")
        sail_tilted = self.photos_dir / "sail_tilted_partner.jpg"
        _render_sailboat_horizon_frame(tilt_deg=-6.5, shift_x=18).save(
            sail_tilted, format="JPEG", quality=98
        )

        # Group 3 (Closeup open): 2 exact duplicates + 1 closed-eye burst partner -> Cluster 2
        cu_0 = _render_portrait_frame(full_body=False, eyes_closed=False, shift_x=0)
        cu_dup_large = self.photos_dir / "cu_open_large.jpg"
        cu_dup_small = self.photos_dir / "cu_open_small.jpg"
        _save_exact_phash_variant(cu_0, cu_dup_large, size_tier="large")
        _save_exact_phash_variant(cu_0, cu_dup_small, size_tier="small")
        cu_closed = self.photos_dir / "cu_closed_partner.jpg"
        _render_portrait_frame(full_body=False, eyes_closed=True, shift_x=28).save(
            cu_closed, format="JPEG", quality=98
        )

        # Cluster 3 (Full-body portraits, no exact duplicates)
        fb_open = self.photos_dir / "fb_open.jpg"
        fb_closed = self.photos_dir / "fb_closed.jpg"
        _render_portrait_frame(full_body=True, eyes_closed=False, shift_x=0).save(
            fb_open, format="JPEG", quality=86
        )
        _render_portrait_frame(full_body=True, eyes_closed=True, shift_x=28).save(
            fb_closed, format="JPEG", quality=98
        )

        scan_directory(str(self.photos_dir), self.db)
        c_res = cluster_unassigned_photos(self.db)
        self.assertEqual(c_res["clusters_created"], 3)

        expected_dup_files = [
            s_large,
            s_mid,
            s_small,
            sail_dup_large,
            sail_dup_small,
            cu_dup_large,
            cu_dup_small,
        ]
        expected_dup_bytes = sum(p.stat().st_size for p in expected_dup_files)
        expected_dup_photos = len(expected_dup_files)  # 7 photos across 3 duplicate groups

        expected_sim_files = [
            sail_dup_large,
            sail_tilted,
            cu_dup_large,
            cu_closed,
            fb_open,
            fb_closed,
        ]
        expected_sim_bytes = sum(p.stat().st_size for p in expected_sim_files)
        expected_sim_photos = len(expected_sim_files)  # 6 photos across 3 AI clusters

        full_dups = list_duplicate_groups(self.db, limit=100, offset=0)
        dup_p0 = list_duplicate_groups(self.db, limit=1, offset=0)
        dup_p1 = list_duplicate_groups(self.db, limit=1, offset=1)
        dup_p2 = list_duplicate_groups(self.db, limit=1, offset=2)

        for page in (full_dups, dup_p0, dup_p1, dup_p2):
            self.assertEqual(page["total_groups"], 3)
            self.assertEqual(page["total_bytes"], expected_dup_bytes)
            self.assertEqual(page["total_photos"], expected_dup_photos)

        self.assertEqual(len(dup_p0["items"]), 1)
        self.assertEqual(len(dup_p1["items"]), 1)
        self.assertEqual(len(dup_p2["items"]), 1)
        self.assertEqual(
            [
                dup_p0["items"][0]["phash"],
                dup_p1["items"][0]["phash"],
                dup_p2["items"][0]["phash"],
            ],
            [g["phash"] for g in full_dups["items"]],
        )

        full_sims = list_ai_clusters(self.db, limit=100, offset=0)
        sim_p0 = list_ai_clusters(self.db, limit=1, offset=0)
        sim_p1 = list_ai_clusters(self.db, limit=1, offset=1)
        sim_p2 = list_ai_clusters(self.db, limit=1, offset=2)

        for page in (full_sims, sim_p0, sim_p1, sim_p2):
            self.assertEqual(page["total_clusters"], 3)
            self.assertEqual(page["total_bytes"], expected_sim_bytes)
            self.assertEqual(page["total_photos"], expected_sim_photos)

        self.assertEqual(len(sim_p0["items"]), 1)
        self.assertEqual(len(sim_p1["items"]), 1)
        self.assertEqual(len(sim_p2["items"]), 1)
        self.assertEqual(
            [
                sim_p0["items"][0]["cluster_id"],
                sim_p1["items"][0]["cluster_id"],
                sim_p2["items"][0]["cluster_id"],
            ],
            [c["cluster_id"] for c in full_sims["items"]],
        )

    def test_08_mount_aware_external_volume_protection_unplug_and_reconnect(self) -> None:
        volumes_root = self.root / "Volumes"
        ext_drive = volumes_root / "ExtDrive"
        ext_album = ext_drive / "CameraRoll"
        ext_album.mkdir(parents=True, exist_ok=True)
        os.environ["UNIPHOTO_VOLUMES_ROOT"] = str(volumes_root)

        # Create exact duplicate pair + sailboat AI burst pair on /Volumes/ExtDrive
        sunset = _render_sunset_duplicate_scene()
        dup_master = ext_album / "ext_dup_master.jpg"
        dup_copy = ext_album / "ext_dup_copy.jpg"
        _save_exact_phash_variant(sunset, dup_master, size_tier="large")
        _save_exact_phash_variant(sunset, dup_copy, size_tier="small")

        sail_level = ext_album / "ext_sail_level.jpg"
        sail_tilted = ext_album / "ext_sail_tilted.jpg"
        _render_sailboat_horizon_frame(tilt_deg=0.0, shift_x=0).save(
            sail_level, format="JPEG", quality=84
        )
        _render_sailboat_horizon_frame(tilt_deg=-6.5, shift_x=18).save(
            sail_tilted, format="JPEG", quality=99
        )

        scan_directory(str(ext_drive), self.db)
        cluster_unassigned_photos(self.db)
        score_clusters_aesthetics(self.db)

        dup_mounted = list_duplicate_groups(self.db)
        sim_mounted = list_ai_clusters(self.db)
        self.assertEqual(dup_mounted["disconnected_volumes"], [])
        self.assertEqual(dup_mounted["total_groups"], 1)
        self.assertEqual(len(dup_mounted["items"]), 1)
        self.assertEqual(sim_mounted["disconnected_volumes"], [])
        self.assertEqual(sim_mounted["total_clusters"], 1)
        self.assertEqual(len(sim_mounted["items"]), 1)
        self.assertTrue(sim_mounted["items"][0]["has_aesthetic_scores"])

        best_cluster_photo_before = sim_mounted["items"][0]["best_photo_id"]
        db_scores_before = {
            p.id: p.aesthetic_score for p in self.db.query(Photo).all()
        }
        self.assertEqual(len(db_scores_before), 4)

        # Simulate unplugging ExtDrive: move directory away AND set UNIPHOTO_UNMOUNTED_VOLUMES
        unplugged_backup = self.root / "ExtDrive_unplugged_backup"
        shutil.move(str(ext_drive), str(unplugged_backup))
        os.environ["UNIPHOTO_UNMOUNTED_VOLUMES"] = "ExtDrive"

        dup_unplugged = list_duplicate_groups(self.db)
        sim_unplugged = list_ai_clusters(self.db)

        self.assertEqual(dup_unplugged["disconnected_volumes"], ["ExtDrive"])
        self.assertEqual(dup_unplugged["items"], [])
        self.assertEqual(dup_unplugged["total_groups"], 0)
        self.assertEqual(dup_unplugged["total_bytes"], 0)
        self.assertEqual(dup_unplugged["total_photos"], 0)

        self.assertEqual(sim_unplugged["disconnected_volumes"], ["ExtDrive"])
        self.assertEqual(sim_unplugged["items"], [])
        self.assertEqual(sim_unplugged["total_clusters"], 0)
        self.assertEqual(sim_unplugged["total_bytes"], 0)
        self.assertEqual(sim_unplugged["total_photos"], 0)

        # Crucial invariant: 100% of Photo, Cluster, and aesthetic_score rows still exist in SQLite!
        self.db.expire_all()
        self.assertEqual(self.db.query(Photo).count(), 4)
        self.assertEqual(self.db.query(Cluster).count(), 1)
        self.assertEqual(
            self.db.query(Cluster).one().best_photo_id, best_cluster_photo_before
        )
        self.assertEqual(
            {p.id: p.aesthetic_score for p in self.db.query(Photo).all()},
            db_scores_before,
        )

        # Simulate reconnecting ExtDrive without rescanning
        shutil.move(str(unplugged_backup), str(ext_drive))
        os.environ.pop("UNIPHOTO_UNMOUNTED_VOLUMES", None)

        dup_reconnected = list_duplicate_groups(self.db)
        sim_reconnected = list_ai_clusters(self.db)

        self.assertEqual(dup_reconnected["disconnected_volumes"], [])
        self.assertEqual(dup_reconnected["total_groups"], 1)
        self.assertEqual(len(dup_reconnected["items"]), 1)
        self.assertEqual(dup_reconnected["total_bytes"], dup_mounted["total_bytes"])
        self.assertEqual(dup_reconnected["total_photos"], 2)

        self.assertEqual(sim_reconnected["disconnected_volumes"], [])
        self.assertEqual(sim_reconnected["total_clusters"], 1)
        self.assertEqual(len(sim_reconnected["items"]), 1)
        self.assertEqual(sim_reconnected["total_bytes"], sim_mounted["total_bytes"])
        self.assertEqual(sim_reconnected["total_photos"], 2)
        self.assertTrue(sim_reconnected["items"][0]["has_aesthetic_scores"])
        self.assertEqual(
            sim_reconnected["items"][0]["best_photo_id"], best_cluster_photo_before
        )
        self.assertEqual(
            [p["aesthetic_score"] for p in sim_reconnected["items"][0]["photos"]],
            [p["aesthetic_score"] for p in sim_mounted["items"][0]["photos"]],
        )

    def test_09_packaged_env_data_dir_dynamic_port_and_health(self) -> None:
        async def _asgi_get_json(path: str) -> tuple[int, dict]:
            messages: list[dict] = []

            async def _receive() -> dict:
                return {"type": "http.request", "body": b"", "more_body": False}

            async def _send(msg: dict) -> None:
                messages.append(msg)

            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": [(b"host", b"127.0.0.1:54321")],
                "client": ("127.0.0.1", 50000),
                "server": ("127.0.0.1", 54321),
            }
            await fastapi_app(scope, _receive, _send)
            start_msg = next(m for m in messages if m["type"] == "http.response.start")
            body_bytes = b"".join(
                m.get("body", b"")
                for m in messages
                if m["type"] == "http.response.body"
            )
            return start_msg["status"], json.loads(body_bytes.decode("utf-8"))

        # 1) Dynamic settings.PORT + /api/v1/health + _serialize_photo thumbnail URL
        sample_path = self.photos_dir / "pkg_thumb_check.jpg"
        _render_sunset_duplicate_scene(size=(320, 240)).save(
            sample_path, format="JPEG", quality=90
        )
        scan_directory(str(self.photos_dir), self.db)
        photo = self.db.query(Photo).one()

        orig_host = settings.HOST
        orig_port = settings.PORT
        try:
            settings.HOST = "127.0.0.1"
            settings.PORT = 54321

            status_code, health_payload = asyncio.run(_asgi_get_json("/api/v1/health"))
            self.assertEqual(status_code, 200)
            self.assertEqual(health_payload.get("status"), "ok")
            self.assertEqual(health_payload.get("port"), 54321)
            self.assertEqual(health_payload.get("version"), settings.VERSION)

            serialized = _serialize_photo(photo, is_best=True, include_scores=False)
            self.assertEqual(
                serialized["thumbnail_url"],
                f"http://127.0.0.1:54321/api/v1/photos/{photo.id}/thumbnail",
            )

            settings.HOST = "0.0.0.0"
            serialized_wildcard = _serialize_photo(photo)
            self.assertEqual(
                serialized_wildcard["thumbnail_url"],
                f"http://127.0.0.1:54321/api/v1/photos/{photo.id}/thumbnail",
            )
        finally:
            settings.HOST = orig_host
            settings.PORT = orig_port

        # 2) Settings & resolve_data_dir resolution for dev, UNIPHOTO_PACKAGED=1, and UNIPHOTO_DATA_DIR
        env_keys = (
            "UNIPHOTO_DATA_DIR",
            "UNIPHOTO_PACKAGED",
            "UNIPHOTO_MODELS_DIR",
            "SQLITE_DB_PATH",
        )
        saved_env = {k: os.environ.get(k) for k in env_keys}
        try:
            for k in env_keys:
                os.environ.pop(k, None)

            # Default dev mode resolves to repo data/
            self.assertFalse(is_packaged_runtime())
            self.assertEqual(resolve_data_dir(), REPO_ROOT / "data")

            # Packaged mode without UNIPHOTO_DATA_DIR resolves to ~/Library/Application Support/com.hung.uniphoto
            os.environ["UNIPHOTO_PACKAGED"] = "1"
            self.assertTrue(is_packaged_runtime())
            expected_pkg_dir = (
                Path.home() / "Library" / "Application Support" / "com.hung.uniphoto"
                if sys.platform == "darwin"
                else Path.home() / ".uniphoto"
            )
            self.assertEqual(resolve_data_dir(), expected_pkg_dir)
            pkg_settings = Settings()
            self.assertEqual(Path(pkg_settings.DATA_DIR), expected_pkg_dir)
            self.assertEqual(
                Path(pkg_settings.SQLITE_DB_PATH), expected_pkg_dir / "uniphoto.db"
            )

            # Explicit UNIPHOTO_DATA_DIR takes top priority even when UNIPHOTO_PACKAGED=1
            custom_data_dir = self.root / "AppSupportOverride"
            os.environ["UNIPHOTO_DATA_DIR"] = str(custom_data_dir)
            self.assertEqual(resolve_data_dir(), custom_data_dir)
            override_settings = Settings()
            self.assertEqual(Path(override_settings.DATA_DIR), custom_data_dir)
            self.assertEqual(
                Path(override_settings.SQLITE_DB_PATH),
                custom_data_dir / "uniphoto.db",
            )
            self.assertEqual(
                override_settings.get_database_url,
                f"sqlite:///{os.path.abspath(custom_data_dir / 'uniphoto.db')}",
            )
            self.assertTrue(custom_data_dir.is_dir())

            # 3) Offline read-only UNIPHOTO_MODELS_DIR lookup for face_landmarker.task & mobilenet_v2.onnx (plus dev .pth fallback)
            bundled_models_dir = self.root / "Contents" / "Resources" / "models"
            bundled_models_dir.mkdir(parents=True, exist_ok=True)

            bundled_face_task = bundled_models_dir / "face_landmarker.task"
            repo_face_task = REPO_ROOT / "data" / "models" / "face_landmarker.task"
            if repo_face_task.is_file() and repo_face_task.stat().st_size > 10_000:
                shutil.copy2(repo_face_task, bundled_face_task)
            else:
                bundled_face_task.write_bytes(b"MP_FACE_TASK_OFFLINE" * 1024)

            repo_onnx = REPO_ROOT / "data" / "models" / "mobilenet_v2.onnx"
            self.assertTrue(repo_onnx.is_file(), f"Expected {repo_onnx} to exist")
            bundled_onnx = bundled_models_dir / "mobilenet_v2.onnx"
            shutil.copy2(repo_onnx, bundled_onnx)
            self.assertGreater(bundled_onnx.stat().st_size, 1_000_000)

            os.chmod(bundled_models_dir, 0o555)
            prev_extractor = ai_engine_mod._FEATURE_EXTRACTOR
            try:
                os.environ["UNIPHOTO_MODELS_DIR"] = str(bundled_models_dir)
                model_settings = Settings()
                self.assertEqual(
                    Path(model_settings.BUNDLED_MODELS_DIR), bundled_models_dir
                )
                self.assertEqual(_resolve_face_task_path(), bundled_face_task)
                self.assertEqual(_resolve_mobilenet_onnx_path(), bundled_onnx)
                self.assertEqual(_resolve_mobilenet_weights_path(), bundled_onnx)

                ai_engine_mod._FEATURE_EXTRACTOR = None
                offline_extractor = ai_engine_mod.get_feature_extractor()
                self.assertIsInstance(offline_extractor, OnnxMobileNetV2Extractor)
                probe_emb = offline_extractor(
                    np.zeros((1, 3, 224, 224), dtype=np.float32)
                )
                self.assertEqual(probe_emb.shape, (1, 1280))
                self.assertEqual(probe_emb.dtype, np.float32)
            finally:
                ai_engine_mod._FEATURE_EXTRACTOR = prev_extractor
                os.chmod(bundled_models_dir, 0o755)

            # Verify optional dev-only .pth fallback when mobilenet_v2.onnx is absent in UNIPHOTO_MODELS_DIR
            fallback_models_dir = self.root / "DevPthFallbackModels"
            fallback_models_dir.mkdir(parents=True, exist_ok=True)
            fallback_pth = fallback_models_dir / "mobilenet_v2.pth"
            torch.save(mobilenet_v2(weights=None).state_dict(), fallback_pth)
            prev_extractor = ai_engine_mod._FEATURE_EXTRACTOR
            try:
                os.environ["UNIPHOTO_MODELS_DIR"] = str(fallback_models_dir)
                self.assertEqual(_resolve_mobilenet_weights_path(), fallback_pth)
                ai_engine_mod._FEATURE_EXTRACTOR = None
                pth_extractor = ai_engine_mod.get_feature_extractor()
                self.assertIsInstance(pth_extractor, nn.Module)
                self.assertIsInstance(pth_extractor.classifier, nn.Identity)
            finally:
                ai_engine_mod._FEATURE_EXTRACTOR = prev_extractor
        finally:
            for k, val in saved_env.items():
                if val is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = val

    def test_10_slim_onnx_and_dct_phash_exact_equivalence(self) -> None:
        # Load demo dataset generator from skill script to test realistic duplicate + burst images
        demo_script_path = (
            REPO_ROOT
            / ".agents"
            / "skills"
            / "uniphoto"
            / "scripts"
            / "create_demo_dataset.py"
        )
        spec = importlib.util.spec_from_file_location(
            "uniphoto_create_demo_dataset", demo_script_path
        )
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        demo_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo_mod)

        demo_dir = self.root / "demo_equiv"
        demo_mod.generate_demo_dataset(demo_dir, overwrite=True)
        demo_files = sorted(demo_dir.rglob("*.jpg"))
        self.assertEqual(len(demo_files), 14)

        # ----------------------------------------------------------------------
        # 1) Pure NumPy + Pillow 16x16 2D DCT-II pHash vs imagehash.phash bit-for-bit equality
        # ----------------------------------------------------------------------
        self.assertNotIn("imagehash", scanner_mod.__dict__)
        self.assertNotIn("scipy", scanner_mod.__dict__)

        rng = np.random.RandomState(20261118)
        yy_l, xx_l = np.mgrid[0:384, 0:512].astype(np.float32)
        gray_landscape = Image.fromarray(
            np.clip(
                128.0
                + 80.0 * np.sin(xx_l * 0.025)
                + 45.0 * np.cos(yy_l * 0.031),
                0,
                255,
            ).astype(np.uint8),
            mode="L",
        )
        gray_portrait = gray_landscape.transpose(Image.Transpose.ROTATE_90)

        rgba_arr = np.zeros((300, 400, 4), dtype=np.uint8)
        rgba_arr[..., 0] = np.linspace(15, 240, 400, dtype=np.uint8)[None, :]
        rgba_arr[..., 1] = np.linspace(230, 20, 300, dtype=np.uint8)[:, None]
        rgba_arr[..., 2] = 140
        rgba_arr[..., 3] = np.linspace(64, 255, 400, dtype=np.uint8)[None, :]
        rgba_sample = Image.fromarray(rgba_arr, mode="RGBA")

        odd_rgb = Image.fromarray(
            rng.randint(0, 256, size=(179, 113, 3), dtype=np.uint8), mode="RGB"
        )
        odd_gray = Image.fromarray(
            rng.randint(0, 256, size=(97, 191), dtype=np.uint8), mode="L"
        )
        tiny_noise = Image.fromarray(
            rng.randint(0, 256, size=(64, 64, 3), dtype=np.uint8), mode="RGB"
        )

        diverse_images: list[tuple[str, Image.Image]] = [
            ("sunset_landscape_rgb", _render_sunset_duplicate_scene((960, 720))),
            (
                "sailboat_tilted_landscape_rgb",
                _render_sailboat_horizon_frame(
                    tilt_deg=-6.5, shift_x=18, out_size=(960, 720)
                ),
            ),
            (
                "portrait_closeup_open_rgb",
                _render_portrait_frame(
                    size=(720, 960), full_body=False, eyes_closed=False
                ),
            ),
            (
                "portrait_fullbody_closed_rgb",
                _render_portrait_frame(
                    size=(720, 960), full_body=True, eyes_closed=True
                ),
            ),
            ("grayscale_landscape_L", gray_landscape),
            ("grayscale_portrait_L", gray_portrait),
            ("translucent_rgba", rgba_sample),
            ("odd_aspect_rgb", odd_rgb),
            ("odd_aspect_L", odd_gray),
            ("random_64x64_rgb", tiny_noise),
        ]

        for label, img in diverse_images:
            actual_hex = calculate_phash(img)
            expected_hex = str(imagehash.phash(img, hash_size=16))
            self.assertIsInstance(actual_hex, str)
            self.assertEqual(len(actual_hex), 64)
            self.assertEqual(
                actual_hex,
                expected_hex,
                f"Pure DCT pHash mismatch vs imagehash.phash on synthetic image '{label}'",
            )

        for demo_file in demo_files:
            with Image.open(demo_file) as demo_img:
                actual_hex = calculate_phash(demo_img)
                expected_hex = str(imagehash.phash(demo_img, hash_size=16))
            self.assertEqual(len(actual_hex), 64)
            self.assertEqual(
                actual_hex,
                expected_hex,
                f"Pure DCT pHash mismatch vs imagehash.phash on demo image '{demo_file.name}'",
            )

        # ----------------------------------------------------------------------
        # 2) ONNX cv2.dnn MobileNetV2 vs PyTorch MobileNet_V2_Weights.DEFAULT
        #    (cosine similarity >= 0.99999 + 100% identical clusters across demo images)
        # ----------------------------------------------------------------------
        onnx_path = _resolve_mobilenet_onnx_path()
        self.assertIsNotNone(onnx_path, "Expected data/models/mobilenet_v2.onnx to exist")
        assert onnx_path is not None

        pt_model = mobilenet_v2(weights=MobileNet_V2_Weights.DEFAULT)
        pt_model.classifier = nn.Identity()
        pt_model.eval()

        preprocessed_list: list[np.ndarray] = []
        for demo_file in demo_files:
            tensor_np = preprocess_image_cv2(str(demo_file))
            self.assertIsNotNone(tensor_np)
            assert tensor_np is not None
            preprocessed_list.append(tensor_np)
        demo_blob = np.ascontiguousarray(
            np.stack(preprocessed_list, axis=0), dtype=np.float32
        )
        self.assertEqual(demo_blob.shape, (14, 3, 224, 224))

        prev_extractor = ai_engine_mod._FEATURE_EXTRACTOR
        try:
            ai_engine_mod._FEATURE_EXTRACTOR = None
            onnx_extractor = ai_engine_mod.get_feature_extractor()
            self.assertIsInstance(onnx_extractor, OnnxMobileNetV2Extractor)

            onnx_batch_emb = onnx_extractor(demo_blob)
            onnx_single_emb = np.vstack(
                [onnx_extractor(demo_blob[i : i + 1]) for i in range(len(demo_files))]
            )
            self.assertEqual(onnx_batch_emb.shape, (14, 1280))
            self.assertEqual(onnx_single_emb.shape, (14, 1280))

            with torch.no_grad():
                pt_emb = (
                    pt_model(torch.from_numpy(demo_blob))
                    .cpu()
                    .numpy()
                    .astype(np.float32)
                )
            self.assertEqual(pt_emb.shape, (14, 1280))

            for mode_label, cand_emb in (
                ("batch=14", onnx_batch_emb),
                ("batch=1", onnx_single_emb),
            ):
                dots = np.sum(cand_emb * pt_emb, axis=1)
                denom = np.maximum(
                    np.linalg.norm(cand_emb, axis=1) * np.linalg.norm(pt_emb, axis=1),
                    1e-12,
                )
                cos_sims = dots / denom
                min_cos = float(np.min(cos_sims))
                self.assertGreaterEqual(
                    min_cos,
                    0.99999,
                    f"Expected ONNX vs PyTorch cosine similarity >= 0.99999 ({mode_label}), got {min_cos:.8f}",
                )

            # Verify 100% identical clustering on both raw embeddings and full DB pipeline
            onnx_raw_groups, _ = cluster_embeddings_chunked(
                onnx_batch_emb, similarity_threshold=0.85
            )
            pt_raw_groups, _ = cluster_embeddings_chunked(
                pt_emb, similarity_threshold=0.85
            )
            self.assertEqual(onnx_raw_groups, pt_raw_groups)

            scan_res = scan_directory(str(demo_dir), self.db)
            self.assertEqual(scan_res["total_found"], 14)
            self.assertEqual(scan_res["exact_duplicates"], 3)
            self.assertEqual(scan_res["new_added"], 11)

            # Cluster using slim ONNX cv2.dnn extractor
            ai_engine_mod._FEATURE_EXTRACTOR = onnx_extractor
            onnx_cluster_res = cluster_unassigned_photos(self.db)
            self.assertEqual(onnx_cluster_res["clusters_created"], 2)
            self.assertEqual(onnx_cluster_res["photos_clustered"], 8)
            onnx_clusters_snapshot = sorted(
                (
                    frozenset(
                        os.path.basename(p["file_path"]) for p in item["photos"]
                    ),
                    os.path.basename(
                        next(
                            p["file_path"]
                            for p in item["photos"]
                            if p["id"] == item["best_photo_id"]
                        )
                    ),
                )
                for item in list_ai_clusters(self.db)["items"]
            )

            # Re-cluster identical DB using PyTorch MobileNet_V2_Weights.DEFAULT reference model
            ai_engine_mod._FEATURE_EXTRACTOR = pt_model
            pt_cluster_res = cluster_unassigned_photos(self.db)
            self.assertEqual(pt_cluster_res["clusters_created"], 2)
            self.assertEqual(pt_cluster_res["photos_clustered"], 8)
            pt_clusters_snapshot = sorted(
                (
                    frozenset(
                        os.path.basename(p["file_path"]) for p in item["photos"]
                    ),
                    os.path.basename(
                        next(
                            p["file_path"]
                            for p in item["photos"]
                            if p["id"] == item["best_photo_id"]
                        )
                    ),
                )
                for item in list_ai_clusters(self.db)["items"]
            )

            self.assertEqual(onnx_clusters_snapshot, pt_clusters_snapshot)
        finally:
            ai_engine_mod._FEATURE_EXTRACTOR = prev_extractor


if __name__ == "__main__":
    unittest.main()
