# UniPhoto Backend Architecture, Database, On-Demand Scoring, Safe Trash & API Reference

## Directory Map

```text
app/
├── main.py                        # FastAPI app factory, CORS, lifespan SQLite WAL init_db(), /api/v1/health & aliases
├── core/
│   ├── config.py                  # Pydantic Settings (UNIPHOTO_DATA_DIR / UNIPHOTO_PACKAGED / UNIPHOTO_MODELS_DIR / HOST / PORT)
│   └── database.py                # SQLAlchemy SQLite engine (WAL pragma + auto column migration)
├── models/models.py               # Photo & Cluster ORM models
├── repositories/photo_repository.py # Grouped pHash & cluster SQL queries, server-side total_bytes/total_photos & mount filters
├── schemas/                       # Pydantic v2 request/response schemas (scan, cluster, photo)
├── services/
│   ├── scanner.py                 # Recursive walk, EXIF timestamp & dimensions, pure-DCT 16x16 pHash, 100-photo batch commits & cancel
│   ├── quality_scorer.py          # Technical 0-100 photo quality engine (invoked on-demand in aesthetic_scorer)
│   ├── ai_engine.py               # Offline-first cv2.dnn ONNX MobileNetV2 embeddings, non-destructive cancel & O(B·N) chunked clustering
│   ├── aesthetic_scorer.py        # On-demand cluster scorer: quality + tilt/composition + face/eyes (offline model lookup)
│   ├── photo_service.py           # Dynamic-port thumbnails, mount-aware volume guard, paginated totals, macOS Trash & rebalance
│   └── progress_tracker.py        # Real-time progress (scanning, clustering, aesthetic_scoring, cancelled, done) + _CANCEL_EVENT
└── api/v1/
    ├── api.py                     # Aggregates /scan, /cluster, /photos under /api/v1
    └── endpoints/
        ├── scan.py                # POST /api/v1/scan, GET /api/v1/scan/progress, POST /api/v1/scan/cancel
        ├── cluster.py             # POST /api/v1/cluster, POST /api/v1/cluster/aesthetic-score
        └── photos.py              # Thumbnails, clusters, duplicates, rescore, open, move-to-Trash, reset
run.py                             # Uvicorn entrypoint (freeze_support, HOST/PORT sync, --self-test, --e2e-test, UNIPHOTO_PARENT_PID watchdog)
uniphoto_backend.spec              # Slim PyInstaller --onedir spec (~268 MB; excludes torch/scipy/matplotlib/sklearn/imagehash)
scripts/
├── build_macos_app.sh             # One-command slim macOS .app (~288 MB) & .dmg (~100 MB) builder (rsync -a, strip -x, codesign, hdiutil)
├── build_windows_app.ps1          # One-command slim Windows 10/11 NSIS .exe (~98 MB) & .msi builder (+ .github/workflows/build-windows.yml CI)
├── export_mobilenet_v2_onnx.py    # Offline float32 Conv+BN-folded ONNX exporter & cv2.dnn validator (min_cos >= 0.999999)
└── pyi_rth_stub_unused.py         # PyInstaller runtime hook stubbing unused matplotlib.* imports in MediaPipe drawing_utils
tests/
├── __init__.py
└── test_uniphoto_pipeline.py      # Isolated 11-test stdlib unittest suite (:memory: SQLite + ONNX/DCT + win32 cross-platform)
```

> **Data Directory & Offline Model Assets (`config.py`, `UNIPHOTO_MODELS_DIR`, `data/models/`):**
> - `app/core/config.py` resolves `DATA_DIR` in strict priority order so packaged bundles never attempt to write inside read-only install directories:
>   1. `UNIPHOTO_DATA_DIR` environment variable (expanded via `expanduser()`).
>   2. `~/Library/Application Support/com.hung.uniphoto` on macOS (`darwin`), `%LOCALAPPDATA%\UniPhoto` on Windows (`win32`), or `~/.uniphoto` elsewhere when `getattr(sys, "frozen", False)` is true or `UNIPHOTO_PACKAGED == "1"`.
>   3. `BASE_DIR / "data"` in local dev & unit test mode (preserving `data/uniphoto.db` untouched).
> - Both `mobilenet_v2.onnx` (`8.4 MB`, `ai_engine.py`) and `face_landmarker.task` (`3.6 MB`, `aesthetic_scorer.py`) resolve offline-first in order: `UNIPHOTO_MODELS_DIR` (`UniPhoto.app/Contents/Resources/models` when packaged) -> `settings.BUNDLED_MODELS_DIR` -> `Path(settings.DATA_DIR) / "models"` -> repo `data/models` (with optional dev-only `.pth`/PyTorch fallback in `ai_engine.py` when not frozen, and automatic 100% offline OpenCV Haar cascade / pure-CV face & eye fallback if `face_landmarker.task` is unavailable). UniPhoto **never** downloads or initializes `pose_landmarker_lite.task`.

## Database Schema (`uniphoto.db`)

SQLite runs with `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and `PRAGMA foreign_keys=ON`. `init_db()` runs `_migrate_sqlite_columns()` automatically to add missing columns on older databases without data loss.

### `photos`
- `id` (`INTEGER PK AUTOINCREMENT`)
- `file_path` (`VARCHAR(500) UNIQUE NOT NULL`) — Absolute path on macOS filesystem.
- `file_size` (`INTEGER NOT NULL`) — File size in bytes (sole ranking criterion for Exact Duplicates and unscored AI clusters).
- `width`, `height` (`INTEGER NULL`) — EXIF-oriented original dimensions extracted directly during `scanner.py` (swapping dimensions when EXIF Orientation `0x0112` is in `(5, 6, 7, 8)`).
- `timestamp` (`DATETIME NULL`) — Extracted from EXIF `DateTimeOriginal` (falls back to `DateTime`, `DateTimeDigitized`, then OS `mtime`).
- `phash` (`VARCHAR(64) INDEXED`) — 256-bit hex string from pure NumPy + Pillow 2D DCT-II `calculate_phash(img)` (bit-for-bit identical to `imagehash.phash(img, hash_size=16)`).
- `quality_score` (`FLOAT NULL`) — Technical composite quality score (`0.0 – 100.0`), populated **only** on multi-photo AI clusters during `POST /api/v1/cluster/aesthetic-score` (`NULL` after scan/cluster and always serialized as `None` for duplicates and unscored clusters).
- `sharpness_score` (`FLOAT NULL`) — Optical focus & edge sharpness score (`0.0 – 100.0`), populated on-demand with `quality_score`.
- `exposure_score` (`FLOAT NULL`) — Brightness balance & highlight/shadow clipping score (`0.0 – 100.0`), populated on-demand with `quality_score`.
- `contrast_score` (`FLOAT NULL`) — Tonal dynamic range (`P95 - P5`) & colorfulness score (`0.0 – 100.0`), populated on-demand with `quality_score`.
- `aesthetic_score` (`FLOAT NULL`) — On-demand composite deep aesthetic score (`0.0 – 100.0`), populated **only** for multi-photo AI Similar Clusters after `POST /api/v1/cluster/aesthetic-score`.
- `composition_score` (`FLOAT NULL`) — Camera levelness & Rule-of-Thirds subject placement score (`0.0 – 100.0`).
- `face_score` (`FLOAT NULL`) — Face ROI sharpness & eye-openness score (`0.0 – 100.0`, `NULL` if 0 faces detected).
- `pose_score` (`FLOAT NULL`) — Legacy unused column kept for SQLite schema compatibility; **always `NULL`** (body posture scoring is removed).
- `tilt_angle` (`FLOAT NULL`) — Estimated accidental camera tilt in degrees (`float`, e.g., `6.5`).
- `has_closed_eyes` (`BOOLEAN / INTEGER NULL`) — `True` when closed eyes / blink detected on a prominent face.
- `aesthetic_tags` (`VARCHAR(500) NULL`) — JSON-serialized list of up to 4 canonical aesthetic tags (warnings first) from the 7 active tags.
- `cluster_id` (`INTEGER FK -> clusters.id ON DELETE SET NULL`) — Assigned AI visual cluster.
- `status` (`VARCHAR(50) INDEXED`, default `"keep"`) — `"keep"` (largest `file_size` photo for a given `phash`, tie-broken by `-id`) or `"exact_duplicate"`.

### `clusters`
- `id` (`INTEGER PK AUTOINCREMENT`)
- `best_photo_id` (`INTEGER FK -> photos.id ON DELETE SET NULL`) — Recommended photo to keep in the AI cluster: elected strictly by largest `file_size` (`(file_size, -id)`) initially, and re-elected by `(aesthetic_score, quality_score, file_size, -id)` once on-demand aesthetic scoring is run.

## Core Processing Pipelines

### 1. Exact Duplicate Detection (`scanner.py` — Pure NumPy/Pillow DCT `pHash`, Never Scored, Largest `file_size` Only)
- Supported extensions: `{".jpg", ".jpeg", ".png", ".heic", ".heif"}`.
- **Zero `imagehash` / `scipy` / `pywt` dependencies & zero scoring:** `scanner.py` computes `calculate_phash(img, hash_size=16, highfreq_factor=4)` using `img.convert("L").resize((64, 64), Image.Resampling.LANCZOS)`, a cached `(64, 16)` `float64` unnormalized 1D DCT-II basis matrix `C[n, k] = 2 * cos(pi * (2n + 1) * k / 128)` (`dctlowfreq = (C.T @ pixels) @ C`), median thresholding (`dctlowfreq > np.median(dctlowfreq)`), and MSB `np.packbits(...).tobytes().hex()`—producing the **exact 64-character hex string bit-for-bit** as `str(imagehash.phash(img, hash_size=16))`. `scanner.py` never imports or invokes `evaluate_photo_quality()`; every scanned photo has all `quality_*` and `aesthetic_*` columns left as `None`.
- Decodes each image once to extract EXIF timestamp, EXIF-oriented `(width, height)` (backfilling `existing_file.width`/`height` if `None`), and 16x16 `phash`.
- Among photos sharing the same `phash`, elects `status = "keep"` strictly by larger `file_size` (`file_size > (existing_keep.file_size or 0)` promotes the new photo to `"keep"` and demotes `existing_keep` to `"exact_duplicate"`).
- **Batch SQLite Commits (`100` operations) & Cooperative Cancellation:** Calls `reset_cancel()` on start, checks `is_cancel_requested()` before each photo, and commits SQLite changes every `100` dirty operations (plus once at loop completion, relying on SQLAlchemy `autoflush` for immediate in-loop visibility). When cancelled, commits already-processed items cleanly, emits `update_progress("cancelled", processed_so_far, total_found, "Đã dừng quét thư mục", ...)`, and returns `cancelled: True`.
- **Strict unscored serialization:** `list_duplicate_groups()` in `photo_service.py` ranks & sorts strictly by `_size_only_rank_key` (`(photo.file_size or 0, -(photo.id or 0))`) and serializes every duplicate item with `include_scores=False` so all quality and aesthetic fields serialize as `None` and `aesthetic_tags = []` (even if legacy DB rows hold stale scores).

### 2. AI Visual Similarity Clustering (`ai_engine.py` — `cv2.dnn` ONNX `MobileNetV2`, Non-Destructive Cancel & `O(B·N)` Chunked Cosine Similarity)
- Operates **only** on photos where `status == "keep"`; never imports or runs `evaluate_photo_quality()`, and has **zero top-level `torch` or `torchvision` imports**.
- **Thread-Safe OpenCV DNN ONNX Extractor (`OnnxMobileNetV2Extractor`):** Sets `cv2.setNumThreads(2)`, resolves unquantized `float32` `mobilenet_v2.onnx` (`8.4 MB`, opset 13 with `Conv2d + BatchNorm2d` folded analytically in `float64 -> float32` by `scripts/export_mobilenet_v2_onnx.py`), loads `cv2.dnn.readNetFromONNX(...)` guarded by a `threading.Lock`, and copies `.forward().copy()` into `(B, 1280)` `np.float32` embeddings matching PyTorch `MobileNet_V2_Weights.DEFAULT` at `min_cos >= 0.999999` (`max_abs_diff < 1e-4`). Retains a lazy dev-only PyTorch fallback strictly when `mobilenet_v2.onnx` is absent and `not sys.frozen`.
- **Non-Destructive Cooperative Cancellation Order:** Calls `reset_cancel()` at the start of `cluster_unassigned_photos()`, queries `keep_photos`, and runs `extract_embeddings_in_batches()` (`batch_size=16`, checking `is_cancel_requested()` between batches/photos) **before** deleting existing `Cluster` rows or resetting `Photo` score columns. If cancelled during embedding extraction, prior clusters and aesthetic scores remain **100% untouched** (`update_progress("cancelled", ..., "Đã dừng gom cụm AI")`, `cancelled: True`, `clusters_created: 0`).
- Once embeddings finish without cancellation, resets prior clusters and clears **both** technical quality (`quality_score`, `sharpness_score`, `exposure_score`, `contrast_score`) and aesthetic (`aesthetic_score`, `composition_score`, `face_score`, `pose_score`, `tilt_angle`, `has_closed_eyes`, `aesthetic_tags`) columns to `None`.
- **Memory-Bounded `O(B·N)` Chunked L2-Normalized Cosine Similarity (`cluster_embeddings_chunked`):** Converts 1280-d `MobileNetV2` embeddings to `np.float32`, L2-normalizes rows (`normed = embeddings / np.maximum(norms, 1e-12)`), and iterates in blocks of `block_size=512`, computing `sim_block = normed[block_start:block_end] @ normed[block_start:].T` (`<= 512 × N × 4` bytes). This reduces `30k`-photo similarity RAM from `~3.6 GB` (full `N × N` matrix) to `~60 MB` while producing **100% identical greedy clusters** (`cosine_similarity >= 0.85`) and checking `check_cancel` before each block.
- Elects initial `Cluster.best_photo_id` strictly by largest file size: `key=lambda p: (p.file_size or 0, -(p.id or 0))`.
- In `list_ai_clusters()`, when `has_aesthetic_scores == False` (`not any(p.aesthetic_score is not None for p in photos)`), clusters rank & sort strictly by `_size_only_rank_key` and serialize with `include_scores=False` (all quality & aesthetic score fields `None`) until the user explicitly triggers `POST /api/v1/cluster/aesthetic-score`.

### 3. Technical Multi-Criteria Quality Engine (`quality_scorer.py` — On-Demand Helper)
`evaluate_photo_quality()` computes a `0–100` technical `quality_score` **only** when called by `score_clusters_aesthetics()`:
1. **Sharpness (`38%`):** Grayscale resized to `max_dim=768` + `3x3` Gaussian denoise -> `60%` Laplacian variance + `40%` 90th-percentile Sobel gradient magnitude (avoids penalizing portrait/macro bokeh when the subject is sharp).
2. **Resolution & Compression Fidelity (`28%`):** `72%` log-saturated original Megapixels (`width * height`) + `28%` bits-per-pixel (`file_size * 8 / pixels`) to favor uncompressed/least-compressed originals.
3. **Exposure Balance (`18%`):** Luminance distance from natural `107–143` sweet spot minus highlight (`>=250`) and shadow (`<=5`) clipping penalties.
4. **Contrast & Colorfulness (`16%`):** Luminance RMS std + `P95 - P5` dynamic spread + Hasler-Süsstrunk colorfulness.

### 4. On-Demand Deep Aesthetic & Quality Scoring (`aesthetic_scorer.py` — No Body Posture, Zero `torch`)
- **Manual Trigger & Similar-Photos-Only Scope:** Never runs automatically during `POST /api/v1/scan` or `POST /api/v1/cluster`. Runs **only** when triggered via `POST /api/v1/cluster/aesthetic-score` (or `POST /api/v1/photos/rescore` for clustered photos), evaluating exclusively multi-photo AI Similar Clusters (`photo_repo.get_multi_photo_cluster_ids`) and computing fresh `evaluate_photo_quality()` + `evaluate_photo_aesthetics()` together in one pass.
- **No Body Posture Scoring:** Body posture evaluation (`pose_landmarker_lite.task`, `pose_score`, `"limb_cropped"`, `"awkward_posture"`, `"good_posture"`) is completely removed; `pose_score` is always `None`.
- **MediaPipe `FaceLandmarker` (Multi-Crop Small-Face Passes) + Offline Fallback:** Uses `mediapipe 1.2.2` Tasks API (`mp.tasks.vision.FaceLandmarker` with persistent writable `MPLCONFIGDIR`, `cv2.setNumThreads(1)`, zero `torch` imports, `num_faces=5`, `min_face_detection_confidence=0.30`, `min_face_presence_confidence=0.30`, accepting boxes `>= 0.002 * w * h`). If full-frame detection finds 0 faces, runs a second pass on an upper-center portrait crop (`y: 0..68%`, `x: 14%..86%`, upscaled `1.6x` `cv2.INTER_CUBIC` when max dim `< 960`) and, if still empty, tighter upper-portrait head sub-crops so distant full-body portraits detect small faces accurately. Falls back to OpenCV Haar cascades (`haarcascade_frontalface_default.xml`, `haarcascade_eye.xml`) / pure-CV detection **only** when `FaceLandmarker` is unavailable (`face_lm is None`).
- **Evaluated Dimensions & 7 Active Canonical `aesthetic_tags`:**
  1. **Camera Tilt & Rule-of-Thirds (`composition_score` `0..100`, `tilt_angle` degrees):** OpenCV Canny + `HoughLinesP` on near-horizontal (`-18°..+18°`, excluding `|angle| < 0.3°` frame artifacts) and near-vertical lines estimates accidental tilt `abs_tilt`. Flags `"tilted_horizon"` when `1.8° <= abs_tilt <= 14.0°` and `"level_horizon"` when `abs_tilt <= 1.2°` (with confident lines). Saliency/gradient center-of-mass distance to Rule-of-Thirds power points and border clipping emit `"rule_of_thirds"` vs. `"edge_subject"`.
  2. **Face Focus & Closed Eyes (`face_score` `0..100` or `None`, `has_closed_eyes` bool):** Evaluates face ROI Laplacian sharpness (`"face_blurry"`) and eye openness via MediaPipe `eyeBlinkLeft`/`eyeBlinkRight` blendshapes / EAR or offline eye cascade fallback. Sets `has_closed_eyes = True` and emits `"eyes_closed"` on blink, or `"eyes_open_sharp"` when eyes are open and crisp. (`face_score` is `None` if 0 faces are detected.)
  3. **Composite `aesthetic_score` & 7 Canonical Tags:** Weighted blend of technical `quality_score` (`40%`), `composition_score` (`25%`), and `face_score` (`35%` when faces are detected; redistributed across technical quality and composition when `face_score is None`), minus explicit penalties (`-25` `eyes_closed`, `-10` `tilted_horizon`), clamped to `0..100`. Stores up to 4 canonical `aesthetic_tags` (warnings first) from the **7 active tags**: `{"eyes_closed", "face_blurry", "tilted_horizon", "edge_subject", "eyes_open_sharp", "level_horizon", "rule_of_thirds"}`.
  4. **Cluster Re-Ranking & Cooperative Cancel:** Calls `reset_cancel()` on start, checks `is_cancel_requested()` before each photo, and flushes/commits every `25` photos (plus at loop completion). Re-elects `Cluster.best_photo_id` by `(photo.aesthetic_score, photo.quality_score or 0.0, photo.file_size or 0, -photo.id)` for all clusters with scored photos, tracks `best_changed_count`, exposes `has_aesthetic_scores: true` (`include_scores=True`, `pose_score: null`) in `list_ai_clusters()`, and updates `progress_tracker` with `phase="aesthetic_scoring"` and final message `"Hoàn tất chấm điểm thẩm mỹ AI"` (or `phase="cancelled"`, `"Đã dừng chấm điểm thẩm mỹ AI"`, `cancelled: True` when stopped early).

### 5. Mount-Aware External Volume Protection & Server-Side Pagination Totals (`photo_service.py` & `photo_repository.py`)
- **`_get_unmounted_volume_name(file_path)` (`photo_service.py`):**
  - Inspects paths under `/Volumes/<Drive>/...` (or `UNIPHOTO_VOLUMES_ROOT` in isolated tests, plus optional comma-separated `UNIPHOTO_UNMOUNTED_VOLUMES` override).
  - On macOS `/Volumes`, treats `<Drive>` as mounted iff `/Volumes/<Drive>` exists and `os.path.ismount` or `os.path.islink` is true (or `os.path.isdir` under custom `UNIPHOTO_VOLUMES_ROOT`). Returns `<Drive>` whenever the volume is currently unmounted, else `None`.
- **Non-Destructive Missing-File Cleanup (`cleanup_missing_photos(db)`):**
  - Deletes DB rows for missing local files (e.g., deleted in Finder), **except** when `_get_unmounted_volume_name(photo.file_path) is not None`—preserving 100% of `Photo`, `Cluster`, `status`, and `aesthetic_*` rows while an external drive is unplugged, and restoring them immediately upon reconnect without rescanning.
  - `get_disconnected_volumes(db)` returns the sorted list of unique unmounted volume names referenced by indexed `Photo` rows.
- **Server-Side SQL Totals & Paginated Slices (`list_duplicate_groups` & `list_ai_clusters`):**
  - Accept `limit` (`1..1000`, default `100`) and `offset` (`>= 0`).
  - Temporarily exclude photos on unmounted volumes (`~Photo.file_path.startswith(f"{volumes_root}/{vol}/")`) from active display and aggregates **without** mutating DB `status` or `Cluster.best_photo_id`.
  - Compute full-dataset `total_groups` / `total_clusters`, `total_bytes` (`SUM(file_size)` across all mounted `>= 2`-photo groups/clusters), and `total_photos` (`COUNT(id)` across all mounted `>= 2`-photo groups/clusters) via SQL aggregates in `photo_repository.py`, returning `{ total_groups | total_clusters, total_bytes, total_photos, disconnected_volumes, items }`.

### 6. Safe Move to macOS Trash & Group Rebalancing (`photo_service.py`)
- **Zero Permanent Deletion:** `app/` never calls `os.remove()` or `os.unlink()` on user photos.
- **`_move_files_to_trash(file_paths)`:**
  1. **Isolated Test Override (`UNIPHOTO_TRASH_DIR`):** When `os.environ.get("UNIPHOTO_TRASH_DIR")` is non-empty, moves files into that directory via collision-safe `_move_to_trash_dir_fallback()` so automated tests never touch `~/.Trash`.
  2. **Native macOS Trash (`NSFileManager.trashItemAtURL`):** On `darwin`, runs a single batch `osascript -l JavaScript` invocation calling `$.NSFileManager.defaultManager.trashItemAtURLResultingItemURLError(url, null, null)`—avoiding Finder TCC automation prompts, handling external `/Volumes/.../.Trashes`, renaming collisions automatically, and preserving Finder *"Put Back"* metadata.
  3. **Collision-Safe `~/.Trash` Fallback (`_move_to_trash_dir_fallback`):** If `osascript` is unavailable or restricted (e.g., sandbox), moves remaining files to `~/.Trash` via `shutil.move`, appending a timestamp-counter suffix (`f"{stem} {HH-MM-SS}-{counter}{ext}"`) whenever a file with the same basename already exists in Trash.
- **`remove_photo(db, photo_id)` & `remove_multiple_photos(db, photo_ids)`:** Move existing files to Trash before deleting DB rows (keeping DB consistent if Trash is unwritable), then invoke `_rebalance_after_deletion()` using `_size_only_rank_key` for duplicate groups and unscored clusters, or `_aesthetic_photo_rank_key` when `has_aesthetic == True` (dissolving clusters that drop below 2 photos).

### 7. Slim Standalone macOS `.app` (`~288 MB`) / `.dmg` (`~100 MB`) Packaging & Sidecar Runtime (`run.py`, `uniphoto_backend.spec`, `scripts/build_macos_app.sh`, `src-tauri/src/lib.rs`)
- **Dynamic Port Thumbnail URLs & Health Check:**
  - `photo_service.py` (`_serialize_photo`) generates thumbnail URLs dynamically via `f"http://{settings.HOST}:{settings.PORT}{settings.API_V1_STR}/photos/{photo.id}/thumbnail"` (never hardcoding `:8000`).
  - `app/main.py` exposes `GET /api/v1/health` returning `{"status": "ok", "version": settings.VERSION, "port": settings.PORT}` (polled by Tauri/React during cold sidecar boot and by `scripts/build_macos_app.sh` smoke tests).
- **Packaged Entrypoint, `--self-test` / `--e2e-test` & Parent-PID Orphan Watchdog (`run.py`):**
  - Calls `multiprocessing.freeze_support()` immediately inside `if __name__ == "__main__":` to prevent PyInstaller + OpenCV fork-bombs on macOS.
  - Exposes `--self-test` (`~0.66s` total, `~0.27s` FastAPI boot: asserts lazy ML imports on `app.main`, verifies zero `torch`/`torchvision`/`scipy`/`matplotlib`/`imagehash`/`pywt`/`sklearn` in frozen `_MEIPASS`, checks `/api/v1/health`, pure-DCT `calculate_phash`, `(1, 1280)` `OnnxMobileNetV2Extractor`, and `FaceLandmarker`) and `--e2e-test <folder>` (isolated ASGI `scan -> cluster -> aesthetic-score` pipeline).
  - Synchronizes `HOST` and `PORT` env overrides onto `settings.HOST` and `settings.PORT` before importing/running `app.main`.
  - When `UNIPHOTO_PARENT_PID` is set to a positive integer, starts a `daemon=True` watchdog thread checking every `2.0s` (`os.getppid() == parent_pid` and `os.kill(parent_pid, 0)`) and calling `os._exit(0)` if the parent Tauri GUI exited or was `kill -9`'d.
  - Runs `uvicorn.run(app, host=host, port=port, reload=False, log_level="warning")` when frozen/packaged (`sys.frozen`, `UNIPHOTO_PACKAGED == "1"`, or `not settings.DEBUG`), keeping `reload=True` in local dev.
- **Slim PyInstaller Spec & Matplotlib Runtime Stub (`uniphoto_backend.spec` & `scripts/pyi_rth_stub_unused.py`):**
  - Excludes `torch`, `torchvision`, `scipy`, `pywt`, `imagehash`, `sklearn`, `matplotlib` (+ font/plotting deps), and `sounddevice`, shrinking `build/pyinstaller/uniphoto-backend` from `883 MB` down to `~268 MB`.
  - Registers `scripts/pyi_rth_stub_unused.py` in `runtime_hooks` to install a lightweight `sys.meta_path` stub for `matplotlib.*` so `mediapipe.tasks.python.vision.drawing_utils` imports in `0.0ms` without bundling `~90 MB` of `matplotlib` + fonts.
- **Tauri Sidecar Supervision (`frontend/src-tauri/src/lib.rs`):**
  - Exposes `#[tauri::command] get_backend_url` returning `http://127.0.0.1:{port}/api/v1`.
  - When `Contents/Resources/backend/uniphoto-backend` exists, picks a free TCP port (`8000` or OS ephemeral fallback), ensures `~/Library/Application Support/com.hung.uniphoto` exists, spawns the sidecar with `UNIPHOTO_PACKAGED=1`, `UNIPHOTO_DATA_DIR`, `UNIPHOTO_MODELS_DIR`, `UNIPHOTO_PARENT_PID`, and `Stdio::null()`, and kills/reaps the child on `tauri::RunEvent::Exit`.
  - In dev mode (`npm run tauri dev`), reuses an already-listening server on `UNIPHOTO_BACKEND_PORT` / `8000`, or auto-spawns `.venv/bin/python run.py` on a free port for single-terminal dev.
- **One-Command Symlink-Preserving Build (`bash scripts/build_macos_app.sh`):**
  - Checks `.venv`, Node.js (`^20.19.0 || >=22.12.0`), `npm`, `cargo`, `rsync`, and `codesign`, stages offline `face_landmarker.task` (`3.6 MB`) + `mobilenet_v2.onnx` (`8.4 MB`), builds `--onedir` `build/pyinstaller/uniphoto-backend` (`~268 MB`) with `.dylib` relative-symlink deduplication and `strip -x`, runs `npm --prefix frontend run tauri build -- --bundles app` (`tauri.bundle.json` kept `{}` to prevent Tauri resource copying from dereferencing `.dylib` symlinks into `+600 MB` duplicate copies), syncs `backend/` and `models/` into `UniPhoto.app/Contents/Resources/` via `rsync -a --delete`, applies ad-hoc `codesign --force --deep --sign -` + `codesign --verify --deep --strict` + signed in-app `--self-test` (`~288 MB` `UniPhoto.app`, down `~80%` from `~1.48 GB`), and creates `UniPhoto_0.1.0_<arch>.dmg` via `hdiutil create -format UDZO -imagekey zlib-level=9` (`~100 MB`).

### 8. Automated Pipeline Test Suite (`tests/test_uniphoto_pipeline.py` — `11/11` Tests)
- Uses stdlib `unittest` with an isolated in-memory SQLite engine (`sqlite:///:memory:`), `tempfile.TemporaryDirectory()`, and `os.environ["UNIPHOTO_TRASH_DIR"]` (plus `UNIPHOTO_VOLUMES_ROOT` / `UNIPHOTO_UNMOUNTED_VOLUMES` for external-volume tests, never touching `data/uniphoto.db` or `~/.Trash`).
- Verifies:
  1. `scan_directory`: EXIF Orientation swap (`5..8`), pure-DCT `pHash` exact duplicate detection electing largest `file_size`, and all quality/aesthetic columns `None`.
  2. `cluster_unassigned_photos`: resets stale legacy scores, elects largest `file_size`, and ensures `list_duplicate_groups` & unscored `list_ai_clusters` serialize all scores as `None`.
  3. `score_clusters_aesthetics`: populates quality/composition/aesthetic scores on AI clusters only while duplicates remain unscored, enforces `pose_score is None` & zero posture tags, detects `"tilted_horizon"` on tilted frames, and detects `face_score` + `has_closed_eyes` on both close-up and small full-body portraits.
  4. `remove_photo` & `remove_multiple_photos`: confirms trashed files survive inside `UNIPHOTO_TRASH_DIR` (including identical basenames from separate subfolders without overwriting) and verifies remaining duplicate/cluster groups rebalance `best_photo`.
  5. `cluster_embeddings_chunked`: proves 100% cluster equivalence against full `sklearn.metrics.pairwise.cosine_similarity` across `1,200` synthetic `1280-d` vectors (`block_size=128`).
  6. `request_cancel`: verifies cooperative early stop during `scan_directory` (`cancelled=True`, `phase=="cancelled"`, partial items committed) and non-destructive cancel during `cluster_unassigned_photos` (existing clusters preserved).
  7. Server-side pagination totals (`limit` / `offset`): confirms `total_groups` / `total_clusters`, `total_bytes`, and `total_photos` reflect the full dataset across pages while `items` slices accurately.
  8. Mount-aware external volume protection (`UNIPHOTO_VOLUMES_ROOT` + `UNIPHOTO_UNMOUNTED_VOLUMES`): simulates unplugging `/Volumes/ExtDrive`, verifies `disconnected_volumes == ["ExtDrive"]`, `items == []`, and 100% survival of SQLite `Photo` / `Cluster` / `aesthetic_score` rows, then reconnects `ExtDrive` and confirms all groups and scores reappear immediately without rescanning.
  9. Packaged runtime configuration (`test_09_packaged_env_data_dir_dynamic_port_and_health`): verifies `/api/v1/health` returns `200` with `{"status": "ok", ...}`, dynamic `settings.PORT` updates `_serialize_photo` `thumbnail_url` cleanly, `config.Settings` resolves `UNIPHOTO_DATA_DIR` and `UNIPHOTO_PACKAGED=1` (`~/Library/Application Support/com.hung.uniphoto`) without touching `data/uniphoto.db`, and offline `UNIPHOTO_MODELS_DIR` lookup resolves `face_landmarker.task` and `mobilenet_v2.onnx` (`OnnxMobileNetV2Extractor`, plus dev `.pth` fallback).
  10. Slim ONNX & pure-DCT mathematical equivalence (`test_10_slim_onnx_and_dct_phash_exact_equivalence`): verifies `scanner.calculate_phash(img)` matches `str(imagehash.phash(img, hash_size=16))` bit-for-bit across `24` diverse synthetic & demo images (`RGB`, `RGBA`, `L`, landscape, portrait, odd aspect ratios) with zero `imagehash`/`scipy` in `scanner.py`, and verifies `OnnxMobileNetV2Extractor` (`cv2.dnn`) matches PyTorch `MobileNet_V2_Weights.DEFAULT` embeddings with cosine similarity `>= 0.99999` (both `batch=1` and `batch=14`) and produces 100% identical AI clusters and `best_photo_id` winners across the full demo dataset.
  11. Windows cross-platform support (`test_11_windows_cross_platform_support`): verifies `resolve_data_dir()` on `win32` (`LOCALAPPDATA`) when `UNIPHOTO_PACKAGED=1`, Windows removable drive-letter protection (`E:\Photos\IMG_001.jpg` with `UNIPHOTO_UNMOUNTED_VOLUMES="E:"`), Unicode/Vietnamese folder & filename decoding across `ai_engine`, `quality_scorer`, and `aesthetic_scorer`, and non-empty `folder_name` serialization on Windows root paths (`D:\IMG_001.jpg`).

## REST API Endpoints Summary

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Sidecar readiness & dynamic port health check (`{ status: "ok", version, port }`) |
| `GET` | `/api/v1/scan/progress` | Poll `{ phase, current, total, percent, current_file, new_added, exact_duplicates, already_indexed, cancel_requested }` (`phase`: `"idle" \| "scanning" \| "clustering" \| "aesthetic_scoring" \| "cancelled" \| "done"`) |
| `POST` | `/api/v1/scan/cancel` (alias `/api/scan/cancel`) | Request cooperative cancellation of active folder scan, AI clustering, or aesthetic scoring (`{ message, cancel_requested: true }`) |
| `POST` | `/api/v1/scan` (alias `/api/scan`) | Scan folder (`100`-photo batch commits), extract EXIF & pure-DCT 16x16 `phash`, elect `"keep"` by largest `file_size`; includes `cancelled: bool` |
| `POST` | `/api/v1/cluster` (alias `/api/cluster`) | Extract `cv2.dnn` ONNX `MobileNetV2` embeddings (non-destructive if cancelled), reset scores, run `O(B·N)` chunked cosine clustering (`block_size=512`), elect initial `best_photo_id` by largest `file_size`; includes `cancelled: bool` |
| `POST` | `/api/v1/cluster/aesthetic-score` (alias `/api/cluster/aesthetic-score`) | On-demand quality + composition/tilt + face/eyes scoring for multi-photo AI clusters (`25`-photo batch commits); returns `{ message, clusters_scored, photos_scored, best_changed_count, duration_seconds, cancelled }` |
| `GET` | `/api/v1/photos/duplicates` | Paginated exact-duplicate groups (`limit=100, offset`, `1..1000`) ranked by `(file_size, -id)` (scores serialized as `None`); returns `{ total_groups, total_bytes, total_photos, disconnected_volumes, items }` |
| `GET` | `/api/v1/photos/clusters` | Paginated AI similarity clusters (`limit=100, offset`, `1..1000`); returns `{ total_clusters, total_bytes, total_photos, disconnected_volumes, items }` |
| `POST` | `/api/v1/photos/rescore` | Rebalance duplicate groups by `(file_size, -id)` (clearing stale non-cluster scores to `None`) and re-run `score_clusters_aesthetics()` on AI clusters |
| `GET` | `/api/v1/photos/{id}/thumbnail?size=360` | Stream resized EXIF-transposed JPEG from RAM (`100..1600` px) |
| `POST` | `/api/v1/photos/{id}/open?mode=preview\|finder` | Run macOS `open` or `open -R` |
| `POST` | `/api/v1/photos/open-multiple` | Open multiple photo IDs together in macOS Preview |
| `POST` | `/api/v1/photos/delete-multiple` | Safely move `{ "photo_ids": [...] }` to macOS Trash & rebalance remaining groups |
| `DELETE` | `/api/v1/photos/{id}` | Safely move a single photo to macOS Trash & rebalance its group |
| `POST` | `/api/v1/photos/reset` | Wipe all rows in `photos` and `clusters` |
