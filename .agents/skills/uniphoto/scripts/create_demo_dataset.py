#!/usr/bin/env python3
"""Generate a safe, realistic demo photo folder for UniPhoto.

Creates:
1. Exact duplicate groups (full-res original vs compressed copy vs downscaled copy
   sharing the same perceptual hash so UniPhoto elects the largest file_size original with zero scoring).
2. Visually similar 'burst' groups (1 tack-sharp level frame, 1 realistic 6.5°-tilted frame
   center-cropped with zero black corners, 1 motion-blurred frame, and 1 over/under-exposed
   frame so MobileNetV2 clusters them >= 0.86 cosine similarity and On-Demand Deep Aesthetic
   Scoring flags "tilted_horizon" & elects the level tack-sharp winner).
3. Unique standalone photo (remains unclustered).
"""

import argparse
import math
import os
import shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


def _add_sensor_grain(
    img: Image.Image, seed: int = 42, strength: float = 14.0
) -> Image.Image:
    """Add deterministic multi-scale natural camera texture so burst embeddings stay cohesive."""
    arr = np.asarray(img, dtype=np.float32)
    h, w, _ = arr.shape
    rng = np.random.RandomState(seed)

    coarse = rng.randn(h // 16 + 2, w // 16 + 2, 3).astype(np.float32)
    coarse_up = np.stack(
        [
            np.asarray(
                Image.fromarray(coarse[:, :, c], mode="F").resize(
                    (w, h), Image.Resampling.BICUBIC
                ),
                dtype=np.float32,
            )
            for c in range(3)
        ],
        axis=-1,
    )

    med = rng.randn(h // 4 + 2, w // 4 + 2).astype(np.float32)
    med_up = np.asarray(
        Image.fromarray(med, mode="F").resize((w, h), Image.Resampling.BICUBIC),
        dtype=np.float32,
    )[..., None]

    out = np.clip(arr + coarse_up * strength + med_up * (strength * 0.48), 0, 255).astype(
        np.uint8
    )
    return Image.fromarray(out)


def _capture_burst_frame(
    world: Image.Image,
    out_size: tuple[int, int] = (1440, 1080),
    shift_x: int = 0,
    shift_y: int = 0,
    tilt_deg: float = 0.0,
) -> Image.Image:
    """Simulate shooting a burst frame (optional 6.5° camera tilt via BICUBIC + clean center-crop)."""
    ww, wh = world.size
    tw, th = out_size
    cx = ww // 2 + shift_x
    cy = wh // 2 + shift_y
    if tilt_deg != 0.0:
        canvas = world.rotate(
            tilt_deg,
            resample=Image.Resampling.BICUBIC,
            center=(cx, cy),
            expand=False,
        )
    else:
        canvas = world
    left = cx - tw // 2
    top = cy - th // 2
    return canvas.crop((left, top, left + tw, top + th))


def _render_landscape_scene(
    size: tuple[int, int] = (1600, 1200),
    shift_x: int = 0,
    shift_y: int = 0,
    sky_tint: tuple[int, int, int] = (185, 72, 92),
    sun_color: tuple[int, int, int] = (255, 218, 120),
    accent_hue: tuple[int, int, int] = (72, 52, 98),
) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / h
        r = int(sky_tint[0] * (1 - t) + 245 * t * 0.6)
        g = int(sky_tint[1] * (1 - t) + 165 * t * 0.6)
        b = int(sky_tint[2] * (1 - t) + 120 * t * 0.6)
        draw.line([(0, y), (w, y)], fill=(min(255, r), min(255, g), min(255, b)))

    sx, sy = int(w * 0.68) + shift_x, int(h * 0.28) + shift_y
    r_sun = int(w * 0.085)
    draw.ellipse([sx - r_sun, sy - r_sun, sx + r_sun, sy + r_sun], fill=sun_color)

    for layer_idx, base_y in enumerate([int(h * 0.52), int(h * 0.64), int(h * 0.76)]):
        pts = [(0, h)]
        freq = (0.008 + layer_idx * 0.004) * (960.0 / w)
        amp = (55 - layer_idx * 10) * (h / 720.0)
        for x in range(0, w + 16, 16):
            xw = x - shift_x * (layer_idx + 1)
            y = base_y + int(
                math.sin(xw * freq + layer_idx * 1.7) * amp
                + math.cos(xw * freq * 2.3) * (amp * 0.4)
            )
            pts.append((x, y))
        pts.append((w, h))
        shade = max(0.35, 1.0 - layer_idx * 0.26)
        color = (
            int(accent_hue[0] * shade),
            int(accent_hue[1] * shade),
            int(accent_hue[2] * shade),
        )
        draw.polygon(pts, fill=color)

    return img


def _build_old_quarter_world(
    world_size: tuple[int, int] = (1800, 1400),
    ref_size: tuple[int, int] = (1440, 1080),
) -> Image.Image:
    """Overscanned lakeside heritage lodges with crisp horizontal quay/eaves & vertical pillars."""
    w, h = world_size
    rw, rh = ref_size
    ox, oy = (w - rw) // 2, (h - rh) // 2
    img = Image.new("RGB", (w, h), (244, 196, 152))
    draw = ImageDraw.Draw(img)

    quay_y = oy + int(rh * 0.60)
    draw.rectangle([0, quay_y, w, h], fill=(68, 42, 58))
    draw.line([(0, quay_y), (w, quay_y)], fill=(252, 232, 198), width=6)

    s = rw / 960.0
    for bx, sc, roof_col, lit_col in [
        (int(310 * s), 1.05 * s, (176, 48, 42), (252, 224, 148)),
        (int(640 * s), 0.82 * s, (142, 44, 52), (246, 208, 132)),
    ]:
        cx = ox + bx
        by = quay_y
        base_w = int(145 * sc)
        wall_h = int(78 * sc)
        gable_h = int(215 * sc)

        draw.rectangle([cx - base_w, by - wall_h, cx + base_w, by], fill=(234, 182, 118))
        draw.line(
            [(cx - base_w - 18, by - wall_h), (cx + base_w + 18, by - wall_h)],
            fill=(72, 42, 34),
            width=6,
        )
        draw.line([(cx - base_w, by - wall_h), (cx - base_w, by)], fill=(72, 42, 34), width=6)
        draw.line([(cx + base_w, by - wall_h), (cx + base_w, by)], fill=(72, 42, 34), width=6)

        eave_y = by - wall_h
        peak_y = eave_y - gable_h
        draw.polygon(
            [(cx - base_w - 22, eave_y), (cx + base_w + 22, eave_y), (cx, peak_y)],
            fill=roof_col,
        )
        draw.polygon(
            [
                (cx - int(58 * sc), eave_y - 16),
                (cx + int(58 * sc), eave_y - 16),
                (cx, peak_y + int(72 * sc)),
            ],
            fill=lit_col,
        )
        draw.line([(cx, peak_y - int(52 * sc)), (cx, by)], fill=(68, 40, 32), width=6)

    return _add_sensor_grain(img, seed=108, strength=14.0)


def _build_sailboat_regatta_world(
    world_size: tuple[int, int] = (1800, 1400),
    ref_size: tuple[int, int] = (1440, 1080),
) -> Image.Image:
    """Overscanned sailboat regatta scene with crisp ocean horizon & vertical masts."""
    w, h = world_size
    rw, rh = ref_size
    ox, oy = (w - rw) // 2, (h - rh) // 2
    img = Image.new("RGB", (w, h), (195, 222, 246))
    draw = ImageDraw.Draw(img)

    horizon = oy + int(rh * 0.56)
    draw.rectangle([0, horizon, w, h], fill=(14, 92, 148))
    draw.line([(0, horizon), (w, horizon)], fill=(232, 245, 255), width=5)

    scale_base = rw / 960.0
    for bx, scale, sail_col in [
        (int(280 * scale_base), 1.0 * scale_base, (250, 250, 252)),
        (int(610 * scale_base), 0.78 * scale_base, (242, 92, 78)),
    ]:
        cx = ox + bx
        cy = horizon + int(24 * scale)
        hull_w, hull_h, mast_h = int(130 * scale), int(34 * scale), int(230 * scale)
        draw.polygon(
            [
                (cx - hull_w, cy),
                (cx + hull_w, cy),
                (cx + int(hull_w * 0.72), cy + hull_h),
                (cx - int(hull_w * 0.72), cy + hull_h),
            ],
            fill=(52, 36, 28),
        )
        draw.line([(cx, cy), (cx, cy - mast_h)], fill=(230, 230, 235), width=7)
        draw.polygon(
            [
                (cx + 5, cy - mast_h + 10),
                (cx + int(115 * scale), cy - 18),
                (cx + 5, cy - 18),
            ],
            fill=sail_col,
        )
        draw.polygon(
            [
                (cx - 5, cy - int(mast_h * 0.85)),
                (cx - int(85 * scale), cy - 22),
                (cx - 5, cy - 22),
            ],
            fill=(245, 246, 250),
        )

    return _add_sensor_grain(img, seed=202, strength=14.0)


def _render_botanical_macro_scene(
    size: tuple[int, int] = (1600, 1200),
    petal_color: tuple[int, int, int] = (236, 88, 134),
) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), (18, 46, 28))
    draw = ImageDraw.Draw(img)

    cx, cy = w // 2, h // 2
    s = w / 960.0
    for angle_deg in range(0, 360, 30):
        rad = math.radians(angle_deg)
        px = cx + int(math.cos(rad) * 145 * s)
        py = cy + int(math.sin(rad) * 145 * s)
        r_p = int(88 * s)
        draw.ellipse(
            [px - r_p, py - r_p, px + r_p, py + r_p],
            fill=petal_color,
            outline=(255, 175, 202),
            width=4,
        )
    r_c = int(72 * s)
    draw.ellipse([cx - r_c, cy - r_c, cx + r_c, cy + r_c], fill=(248, 204, 56))
    return img


def generate_demo_dataset(target_dir: Path, overwrite: bool = False) -> None:
    if target_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Target directory already exists: {target_dir} (pass --overwrite to recreate)"
            )
        shutil.rmtree(target_dir)

    album_main = target_dir / "Trip_DaLat"
    album_backup = target_dir / "Backup_iPhone"
    album_bursts = target_dir / "Camera_Bursts"
    for folder in (album_main, album_backup, album_bursts):
        folder.mkdir(parents=True, exist_ok=True)

    # 1. Exact duplicate sets (same pHash, different resolution / JPEG compression)
    sunset_orig = _render_landscape_scene(size=(1600, 1200))
    p1 = album_main / "IMG_1001_Sunset_Original.jpg"
    sunset_orig.save(p1, format="JPEG", quality=96)
    sunset_orig.save(album_backup / "IMG_1001_compressed.jpg", format="JPEG", quality=72)
    sunset_orig.resize((800, 600), Image.Resampling.BILINEAR).save(
        album_backup / "IMG_1001_messenger_downscaled.jpg", format="JPEG", quality=85
    )

    flower_orig = _render_botanical_macro_scene(size=(1600, 1200))
    p2 = album_main / "IMG_1024_LotusMacro.jpg"
    flower_orig.save(p2, format="JPEG", quality=95)
    shutil.copy2(p2, album_backup / "LotusMacro_Duplicate.jpg")

    # 2. Visually similar AI burst groups (cosine similarity >= 0.86 across every burst pair)
    #    including realistic 6.5° tilted camera shots (BICUBIC + center-cropped to 1440x1080):
    # Burst A: OldQuarter (Sharp level winner, Motion-blurred, Washed-out overexposed, 6.5° Tilted)
    oq_world = _build_old_quarter_world()
    b1_sharp = _capture_burst_frame(oq_world, shift_x=0, shift_y=0, tilt_deg=0.0)
    b1_sharp.save(album_bursts / "IMG_2011_OldQuarter_Sharp.jpg", format="JPEG", quality=95)

    b2_blur = _capture_burst_frame(oq_world, shift_x=6, shift_y=0, tilt_deg=0.0).filter(
        ImageFilter.GaussianBlur(radius=1.15)
    )
    b2_blur.save(album_bursts / "IMG_2012_OldQuarter_Blurry.jpg", format="JPEG", quality=95)

    b3_overexp = ImageEnhance.Color(
        ImageEnhance.Brightness(
            _capture_burst_frame(oq_world, shift_x=6, shift_y=-2, tilt_deg=0.0)
        ).enhance(1.26)
    ).enhance(0.62)
    b3_overexp.save(
        album_bursts / "IMG_2013_OldQuarter_Overexposed.jpg", format="JPEG", quality=84
    )

    b4_tilted = _capture_burst_frame(oq_world, shift_x=6, shift_y=-2, tilt_deg=6.5)
    b4_tilted.save(album_bursts / "IMG_2014_OldQuarter_Tilted.jpg", format="JPEG", quality=90)

    # Burst B: Sailboat (Sharp level frame vs crisp -6.5° Tilted frame, Blurry, Underexposed)
    sb_world = _build_sailboat_regatta_world()
    s1_sharp = _capture_burst_frame(sb_world, shift_x=0, shift_y=0, tilt_deg=0.0)
    s1_sharp.save(album_bursts / "IMG_3051_Sailboat_Sharp.jpg", format="JPEG", quality=91)

    s2_blur = _capture_burst_frame(sb_world, shift_x=6, shift_y=-2, tilt_deg=0.0).filter(
        ImageFilter.GaussianBlur(radius=1.12)
    )
    s2_blur.save(album_bursts / "IMG_3052_Sailboat_Blurry.jpg", format="JPEG", quality=95)

    s3_dark = ImageEnhance.Brightness(
        _capture_burst_frame(sb_world, shift_x=6, shift_y=-2, tilt_deg=0.0)
    ).enhance(0.71)
    s3_dark.save(album_bursts / "IMG_3053_Sailboat_Underexposed.jpg", format="JPEG", quality=92)

    s4_tilted = _capture_burst_frame(sb_world, shift_x=6, shift_y=-2, tilt_deg=-6.5)
    s4_tilted.save(album_bursts / "IMG_3054_Sailboat_Tilted.jpg", format="JPEG", quality=96)

    # 3. Standalone unique photo
    unique = Image.new("RGB", (1440, 1080), (12, 14, 24))
    udraw = ImageDraw.Draw(unique)
    for r in range(420, 30, -36):
        udraw.rectangle(
            [720 - r, 540 - r, 720 + r, 540 + r],
            outline=(min(255, 70 + r // 3), 190, max(40, 255 - r // 2)),
            width=7,
        )
    unique.save(album_main / "IMG_4099_NeonFrame_Unique.jpg", format="JPEG", quality=93)

    total_files = sum(1 for _ in target_dir.rglob("*.jpg"))
    print(f"✅ Created UniPhoto demo dataset at: {target_dir}")
    print(
        f"   Total photos: {total_files} (2 exact-duplicate groups, 2 AI burst clusters with sharp/blur/exposure/6.5°-tilted variants, 1 unique photo)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a safe UniPhoto demo photo folder."
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="/tmp/uniphoto-demo",
        help="Destination folder path (default: /tmp/uniphoto-demo)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and recreate output_dir if it already exists",
    )
    args = parser.parse_args()
    generate_demo_dataset(
        Path(os.path.abspath(args.output_dir)), overwrite=args.overwrite
    )


if __name__ == "__main__":
    main()
