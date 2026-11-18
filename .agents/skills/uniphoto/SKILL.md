---
name: uniphoto
description: >-
  Architecture, development, UI styling, i18n, verification, slim standalone macOS .app/.dmg
  packaging, and demo runbook for the UniPhoto macOS duplicate & visually similar photo cleaner
  (FastAPI + SQLite + pure-DCT pHash + OpenCV DNN ONNX MobileNetV2 + on-demand OpenCV/MediaPipe
  quality, composition & face aesthetic scoring backend, and Tauri v2 + React 19 + Tailwind v4
  Apple macOS Native Split-View & Sidebar Vibrancy frontend). Use this skill whenever building
  features, fixing bugs, editing UI/CSS, adding translations, packaging macOS bundles, running
  tests/builds, or preparing and running a UniPhoto demo.
---

# UniPhoto System Skill

UniPhoto is a local-first macOS desktop application that scans photo folders (`.jpg`, `.jpeg`, `.png`, `.heic`, `.heif`) to detect **100% perceptual duplicates** (pure NumPy + Pillow 2D DCT-II `calculate_phash` 16x16 matching `imagehash.phash` bit-for-bit, with `100`-photo batch SQLite commits and largest `file_size` election with zero scoring), cluster **visually similar / burst shots** (`cv2.dnn` ONNX `MobileNetV2` embeddings + memory-bounded `O(B·N)` chunked L2-normalized cosine similarity >= `0.85`, `block_size=512`), optionally run **On-Demand Deep Aesthetic Scoring** (`POST /api/v1/cluster/aesthetic-score`) exclusively on AI similar clusters to evaluate technical quality/sharpness, camera tilt & composition, and face sharpness / closed eyes (with **no** body posture scoring), support **Cooperative Cancellation** (`POST /api/v1/scan/cancel`), stream large libraries via **Server-Side SQL Totals & Infinite Scroll** (`limit=100, offset`), protect unplugged `/Volumes/<Drive>` libraries via **Mount-Aware External Volume Protection**, clean up unwanted photos via **Safe Move to macOS Trash** (`NSFileManager.trashItemAtURL`), and ship as a **slim `~288 MB` standalone offline `UniPhoto.app` / `~100 MB` `.dmg`** (`scripts/build_macos_app.sh`) with an **Apple macOS Native Split-View & Sidebar Vibrancy** desktop UI.

> **Database Note:** UniPhoto uses **SQLite with WAL mode** (`data/uniphoto.db` in local dev, or `~/Library/Application Support/com.hung.uniphoto/uniphoto.db` when packaged via `UNIPHOTO_PACKAGED=1` / `UNIPHOTO_DATA_DIR`) configured in `app/core/config.py` and `app/core/database.py` with automatic non-destructive column migration. Do not introduce external database server dependencies.

## 1. Critical Safety & Runtime Rules

1. **Safe Move to macOS Trash (Never `os.remove`):** `POST /api/v1/photos/delete-multiple` and `DELETE /api/v1/photos/{id}` (`app/services/photo_service.py`) move files safely to macOS Trash via Cocoa `NSFileManager.trashItemAtURLResultingItemURLError` (`osascript -l JavaScript`) with a collision-safe `~/.Trash` fallback (`_move_to_trash_dir_fallback`)—never permanently deleting files with `os.remove()` or `os.unlink()`. For manual demos, always generate an isolated dataset with [create_demo_dataset.py](./scripts/create_demo_dataset.py); for automated unit tests (`tests/test_uniphoto_pipeline.py`), always set `UNIPHOTO_TRASH_DIR` (and `UNIPHOTO_VOLUMES_ROOT` / `UNIPHOTO_UNMOUNTED_VOLUMES` when testing external drives) to temporary directories and use `sqlite:///:memory:` so `data/uniphoto.db` and `~/.Trash` are never touched.
2. **Mount-Aware External Volume Protection (Never Prune Unplugged Drives):** `cleanup_missing_photos()` (`app/services/photo_service.py`) prunes DB rows when local files were deleted or moved to Trash in Finder, **except** when `_get_unmounted_volume_name(file_path)` detects that the file resides on a currently unmounted `/Volumes/<Drive>` external drive. Unplugging an external drive preserves **100%** of `Photo`, `Cluster`, `status`, and `aesthetic_score` rows in SQLite, hides offline groups from active slices/totals without mutating `best_photo_id`, surfaces `disconnected_volumes` in the `ResultsPage` inline `#242426` notice strip, and restores all groups and scores immediately upon reconnecting the drive.
3. **Tauri Runtime Required for Overlay Titlebar, Vibrancy, Folder Picker & Drag-Drop:** `frontend/src-tauri/` configures `"titleBarStyle": "Overlay"`, `"hiddenTitle": true`, `"trafficLightPosition": { "x": 18, "y": 22 }`, `"transparent": true`, `"core:window:allow-start-dragging"` (`data-tauri-drag-region`), and macOS `NSVisualEffectView` `Effect::Sidebar` vibrancy, while `frontend/src/App.tsx` uses `@tauri-apps/plugin-dialog` (`open({ directory: true })`) and `@tauri-apps/api/webview` (`getCurrentWebview().onDragDropEvent(...)`). Always run `npm --prefix frontend run tauri dev` (not plain `npm run dev` in a browser) when testing window chrome, traffic-light clearance (`pl-[76px]`+), folder selection, folder drag-and-drop onto `HomePage`, or native window title updates.
4. **Zero `window.alert` / `window.confirm` & Zero Emoji UI Icons:** All confirmations and notifications in `frontend/src/` use native macOS `NSAlert`-style dialog and notification components (`GlassModal.tsx` and `GlassToast.tsx`), and all UI iconography uses crisp `1.7px`-stroke SF-Symbols-inspired SVG components from `frontend/src/components/MacIcons.tsx`. Never introduce native browser `alert()` / `window.confirm()` dialogs or emoji icons.
5. **Slim Runtime (Zero Top-Level `torch`/`scipy`/`imagehash`), CPU Thermal Throttling & Offline Model Lookup:** Keep `app/services/scanner.py` pure NumPy + Pillow (`calculate_phash` 2D DCT-II, zero `imagehash`/`scipy`), keep `cv2.setNumThreads(2)` and thread-safe `OnnxMobileNetV2Extractor` (`cv2.dnn.readNetFromONNX`) in `app/services/ai_engine.py` with zero top-level `torch`/`torchvision` imports (retaining only a lazy dev fallback when `.onnx` is absent), and keep `cv2.setNumThreads(1)` plus writable `MPLCONFIGDIR` before importing `mediapipe` in `app/services/aesthetic_scorer.py` (with zero `torch` imports). Both `mobilenet_v2.onnx` (`ai_engine.py`) and `face_landmarker.task` (`aesthetic_scorer.py`) resolve offline-first in order: `UNIPHOTO_MODELS_DIR` (read-only `Contents/Resources/models` in `.app`) -> `settings.BUNDLED_MODELS_DIR` -> `Path(settings.DATA_DIR) / "models"` -> repo `data/models` (with automatic offline OpenCV Haar cascade / pure-CV fallback when `face_landmarker.task` is unavailable; **never** download or use `pose_landmarker_lite.task`).
6. **No Automatic Scoring & Never Score Exact Duplicates:**
   - `POST /api/v1/scan` (`scanner.py`) **never** runs `evaluate_photo_quality()`. Exact Duplicates (`GET /api/v1/photos/duplicates`) are **never** scored (all `quality_*` and `aesthetic_*` fields serialize as `None`) and elect `"keep"` strictly by largest `file_size` (`(file_size, -id)`).
   - `POST /api/v1/cluster` (`ai_engine.py`) resets **both** `quality_*` and `aesthetic_*` columns to `None` and elects initial `Cluster.best_photo_id` strictly by largest `file_size`. Unscored Similar Photos also serialize with all score fields `None` until the user manually clicks `Chấm điểm thẩm mỹ` / `Score Aesthetics` (`POST /api/v1/cluster/aesthetic-score`).
7. **Large-Library Scale, Memory Bounds & Cooperative Cancellation:**
   - **Cooperative Cancel (`POST /api/v1/scan/cancel`):** `progress_tracker.py` exposes thread-safe `request_cancel()`, `reset_cancel()`, and `is_cancel_requested()` (`phase="cancelled"`). `scanner.py` commits every `100` dirty operations and preserves partial results on cancel; `ai_engine.py` extracts embeddings **before** wiping prior `Cluster` rows / scores so cancelling during embedding extraction is 100% non-destructive; `aesthetic_scorer.py` commits every `25` photos and re-elects `best_photo_id` on partially scored clusters. `ScanningPage.tsx` provides a native `#2C2C2E` Stop button that loads partial results cleanly.
   - **Chunked `O(B·N)` Cosine Similarity (`cluster_embeddings_chunked`):** Never allocate a full `N × N` `cosine_similarity(embeddings)` matrix in production. `ai_engine.py` L2-normalizes `float32` embeddings and computes `block_size=512` similarity blocks (`<= 512 × N × 4` bytes, cutting `30k`-photo similarity RAM from `~3.6 GB` to `~60 MB` with **100% identical** greedy clusters).
   - **Server-Side Totals & Infinite Scroll (`PAGE_SIZE = 100`):** `GET /api/v1/photos/duplicates` and `GET /api/v1/photos/clusters` compute full-library `total_bytes` and `total_photos` in SQL alongside paginated `items` (`limit=100, offset`), while `ResultsPage.tsx` Pane 2 (`#1E1E20` master list) loads additional `100`-group pages via `onScroll` + load-more footer (no hardcoded `300`-group cap).
8. **Packaged Sidecar Lifecycle, Dynamic Ports, Symlink-Preserving Bundle & Read-Only Safety:**
   - **Never write inside `/Applications/UniPhoto.app`:** `app/core/config.py` resolves `DATA_DIR` via `UNIPHOTO_DATA_DIR` -> `~/Library/Application Support/com.hung.uniphoto` (when `sys.frozen` or `UNIPHOTO_PACKAGED=1`) -> `data/` in local dev (preserving `data/uniphoto.db` untouched during dev and packaging).
   - **Never hardcode `127.0.0.1:8000`:** `photo_service.py` (`_serialize_photo`) constructs thumbnail URLs from `settings.HOST` and `settings.PORT`, while `frontend/src/api/PhotoApi.ts` resolves the API base dynamically via Tauri `invoke<string>("get_backend_url")` (falling back to `http://127.0.0.1:8000/api/v1` outside Tauri) and checks `GET /api/v1/health`.
   - **Sidecar Supervision & Slim Symlink-Preserving Packaging:** `frontend/src-tauri/src/lib.rs` picks an available TCP port (`8000` or ephemeral fallback), spawns `Contents/Resources/backend/uniphoto-backend` when packaged (or auto-spawns `.venv/bin/python run.py` in single-terminal `tauri dev` if port `8000` isn't already listening), kills/reaps the child on `RunEvent::Exit`, and passes `UNIPHOTO_PARENT_PID` so `run.py`'s `2.0s` daemon watchdog calls `os._exit(0)` if the parent GUI ever terminates abruptly. Keep `tauri.conf.json` and `tauri.bundle.json` (`{}`) free of `build/` resource copies so Tauri never dereferences `.dylib` symlinks into duplicate copies; `scripts/build_macos_app.sh` builds `tauri build -- --bundles app` and syncs `build/pyinstaller/uniphoto-backend -> Contents/Resources/backend` (`~268 MB`) and `build/bundled-models -> Contents/Resources/models` (`mobilenet_v2.onnx` + `face_landmarker.task`) via `rsync -a --delete` + `strip -x` + deep `codesign` + `hdiutil` `UDZO` `.dmg` (`~288 MB` `.app` / `~100 MB` `.dmg`).

## 2. Running Locally & Building Slim Standalone macOS `.app` / `.dmg`

### Option A — Single-Terminal Dev (`tauri dev` Auto-Spawn)
```bash
npm --prefix /Users/hung/hacker/UniPhoto/frontend run tauri dev
```
If port `8000` (or `UNIPHOTO_BACKEND_PORT`) is not already listening, `src-tauri/src/lib.rs` automatically picks a free port and spawns `.venv/bin/python run.py`, cleaning it up on exit.

### Option B — Two-Terminal Dev (Hot-Reload Backend + Swagger on `:8000`)
1. **Backend (`http://127.0.0.1:8000`, Swagger: `/api/v1/docs`):**
   ```bash
   /Users/hung/hacker/UniPhoto/.venv/bin/python /Users/hung/hacker/UniPhoto/run.py
   ```
2. **Desktop App (reuses already-listening `:8000` without spawning a second server):**
   ```bash
   npm --prefix /Users/hung/hacker/UniPhoto/frontend run tauri dev
   ```

### Slim Standalone Offline macOS `.app` (`~288 MB`) & `.dmg` (`~100 MB`) Build
```bash
bash /Users/hung/hacker/UniPhoto/scripts/build_macos_app.sh
```
Bundles slim FastAPI + OpenCV DNN + MediaPipe via PyInstaller `--onedir` (`uniphoto_backend.spec` + `scripts/pyi_rth_stub_unused.py`, `~268 MB`, excluding `torch`/`scipy`/`matplotlib`/`sklearn`/`imagehash`), pre-bundles offline `mobilenet_v2.onnx` (`8.4 MB`, exported via `scripts/export_mobilenet_v2_onnx.py`) + `face_landmarker.task` (`3.6 MB`), syncs into `UniPhoto.app/Contents/Resources/` via symlink-preserving `rsync -a --delete`, strips Mach-O symbols (`strip -x`), applies ad-hoc `codesign --force --deep --sign -` + in-bundle `--self-test` (`~0.66s`), and creates a compressed `UDZO` `UniPhoto_*.dmg` (`~100 MB`). For unsigned distribution to another Mac, clear Gatekeeper quarantine once before first launch:
```bash
xattr -cr /Applications/UniPhoto.app
```

## 3. Demo Preparation Workflow

1. Generate (or regenerate with `--overwrite`) a safe, self-contained demo folder containing exact duplicates across subfolders and 2 AI burst clusters (`OldQuarter` and `Sailboat`) with sharp, motion-blurred, over/under-exposed, and realistic `6.5°` tilted camera shots (`>= 0.86` MobileNetV2 cosine similarity):
   ```bash
   /Users/hung/hacker/UniPhoto/.venv/bin/python .agents/skills/uniphoto/scripts/create_demo_dataset.py /tmp/uniphoto-demo --overwrite
   ```
2. Start the backend and Tauri app above, **drag & drop `/tmp/uniphoto-demo` directly onto the macOS Finder/Photos dropzone panel** on `HomePage` (or click to browse), keep both scan options checked, and run the scan.
3. Demonstrate:
   - **Native macOS 3-Pane Split-View & Sidebar Vibrancy:** Show the Overlay Titlebar traffic lights integrated into the translucent vibrancy sidebar (`<IconSidebarLeft />` collapse/expand with automatic `pl-[76px]` traffic-light safe zone on Pane 2), `#007AFF` active source-list items, `#1E1E20` master list with `⌘F` capsule search & circular action buttons, `#161618` / `#141416` distraction-free darkroom preview stage, and `VI | EN` instant language switching (even mid-scan or mid-scoring).
   - `Duplicates` vs. `Similar Photos` source-list items (unscored state): verify `Duplicates` displays **no** quality or aesthetic scores/bars and recommends keeping the largest file (`Đề xuất giữ (Dung lượng lớn nhất)` / `Recommended Keep (Largest file size)`), while `Similar Photos` also starts unscored (ranked by largest `file_size`) and presents the optional `#5E5CE6` `Chấm điểm thẩm mỹ` / `Score Aesthetics` toolbar button and `#242426` discovery strip.
   - **On-Demand Deep Aesthetic Scoring:** Click `Chấm điểm thẩm mỹ` / `Score Aesthetics` in `Similar Photos` to run `POST /api/v1/cluster/aesthetic-score`. Show how it computes technical quality + composition/tilt + face/eyes in one pass, flags `"tilted_horizon"` (`6.5°`) on `IMG_2014_OldQuarter_Tilted.jpg` and `IMG_3054_Sailboat_Tilted.jpg`, updates `Cluster.best_photo_id` to promote the level sharp frame (`IMG_3051_Sailboat_Sharp.jpg`), surfaces `✦ aesthetic_score`, `★ quality_score`, mini composition/face & technical bars (never body posture), and shows a `GlassToast` completion notification.
   - **Keyboard Shortcuts & Popover (`ResultsPage`):** Click the `<IconKeyboard />` button in Pane 3's toolbar to open the Shortcuts popover, then test `⌘F` (capsule search focus), `←/→` (photos), `↑/↓` (groups), `Space` (toggle selection), `1/2` (`Large View` vs. `Compare`), `P`/`Enter` (Preview), `F` (Finder), `⌘A` (auto-select alternates), and `Esc` (close popover / clear search).
   - **Safe Smart Cleanup to macOS Trash:** Click the `#007AFF` cleanup CTA in the bottom bar to open the `NSAlert`-style `GlassModal`, confirm moving selected alternates safely to **macOS Trash** (restorable via Finder *"Put Back"*), and verify the `GlassToast` summary and rebalanced groups.

## 4. Development Guidelines & References

- **Backend, SQLite Schema, Pure-DCT Scan, ONNX `cv2.dnn` Cluster, On-Demand Aesthetic Scoring & Safe Trash Pipeline:** Read [architecture-and-api.md](./references/architecture-and-api.md) before modifying endpoints, database queries, scanning logic, MobileNetV2 ONNX clustering, aesthetic scoring, or photo Trash cleanup.
- **Apple macOS Native Split-View & Sidebar Vibrancy UI, Overlay Titlebar Safe Zones, `MacIcons.tsx`, Modals/Toasts, Drag & Drop, Keyboard Shortcuts & `VI`/`EN` i18n:** Read [ui-glass-and-i18n.md](./references/ui-glass-and-i18n.md) before modifying any React component, Tailwind class, Tauri window setting, or user-facing text. Every new string **must** be added to both `vi` and `en` in `frontend/src/i18n/translations.ts`.

## 5. Automated Tests & Verification Steps

UniPhoto includes an isolated 10-test stdlib `unittest` suite in `tests/test_uniphoto_pipeline.py` (`sqlite:///:memory:` + `tempfile.TemporaryDirectory()` + `UNIPHOTO_TRASH_DIR`) covering EXIF orientation & size-only pure-DCT `pHash` scan, `ONNX MobileNetV2` clustering & stale-score immunity, on-demand `score_clusters_aesthetics` (tilted horizon + close-up & full-body portrait face/closed-eye detection + zero posture), collision-safe Trash moves + group rebalancing, `O(B·N)` chunked cosine similarity equivalence (`1,200 × 1280-d`), cooperative cancellation (`request_cancel` mid-scan & mid-cluster), server-side pagination totals (`limit`/`offset`), mount-aware external volume protection (`UNIPHOTO_VOLUMES_ROOT` + `UNIPHOTO_UNMOUNTED_VOLUMES`), packaged `.app` runtime config (`/api/v1/health`, dynamic `settings.PORT` thumbnails, `UNIPHOTO_DATA_DIR` / `UNIPHOTO_PACKAGED=1`, and offline `UNIPHOTO_MODELS_DIR` lookup), and slim ONNX/DCT mathematical equivalence (`calculate_phash` bit-for-bit equality vs `imagehash.phash` + ONNX `cv2.dnn` vs PyTorch `MobileNetV2` cosine similarity `>= 0.99999` & 100% identical clusters).

After making backend, frontend, test, or Tauri configuration changes, run the unified verification script (which runs Python `compileall`, FastAPI import check, `tests/test_uniphoto_pipeline.py`, and `tsc && vite build`):

```bash
bash .agents/skills/uniphoto/scripts/verify.sh
```

Add `--tauri` (`bash .agents/skills/uniphoto/scripts/verify.sh --tauri`) whenever `frontend/src-tauri/` (Rust code, `Cargo.toml`, `tauri.conf.json`, or `capabilities/default.json`) is modified.
