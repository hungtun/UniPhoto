# UniPhoto — macOS & Windows Duplicate & Similar Photo Cleaner

UniPhoto is a local-first **macOS & Windows 10/11** desktop application that helps you reclaim disk space by detecting **100% perceptual duplicate photos** and clustering **visually similar / burst shots** completely offline. It combines a slim **FastAPI + SQLite (WAL) + OpenCV DNN (`ONNX MobileNetV2`) + MediaPipe** backend with a **Tauri v2 + React 19 + TypeScript + Tailwind CSS v4** desktop interface styled in an authentic **Apple macOS Native Split-View & Sidebar Vibrancy** design (with native **Windows 11 Mica / dark frame**, File Explorer & Recycle Bin integration on Windows) and instant Vietnamese & English (`VI` ⇄ `EN`) switching.

---

## ✨ Core Features

- **Size-Prioritized Exact Duplicate Detection (Pure-DCT `pHash` 16×16):**
  - Recursively scans `.jpg`, `.jpeg`, `.png`, `.heic`, and `.heif` folders while ignoring system/build directories, committing SQLite writes in fast `100`-photo batches.
  - Reads EXIF capture timestamps (`DateTimeOriginal`) and EXIF-oriented dimensions (handling Orientation tags `5, 6, 7, 8`), computes 256-bit perceptual hashes via pure NumPy + Pillow 2D DCT-II (`scanner.calculate_phash`, bit-for-bit identical to `imagehash.phash(..., hash_size=16)` with zero `scipy`/`PyWavelets` runtime overhead), and elects `"keep"` strictly by **largest `file_size`** (`(file_size, -id)`) with **zero unnecessary quality or aesthetic scoring**.
- **Memory-Bounded AI Visually Similar Photo Clustering (`ONNX MobileNetV2` via `cv2.dnn` + `O(B·N)` Chunked Cosine Similarity):**
  - Extracts 1280-d `MobileNetV2` (`float32` unquantized `mobilenet_v2.onnx`, `8.4 MB`, cosine similarity `>= 0.999999` vs PyTorch `MobileNet_V2_Weights.DEFAULT`) embeddings via thread-safe `cv2.dnn` batches (`batch_size=16`, `cv2.setNumThreads(2)`, zero runtime `torch`/`torchvision` imports) and groups burst/similar photos (`cosine_similarity >= 0.85`) via **chunked L2-normalized float32 block matrix multiplication** (`block_size=512` in `ai_engine.py`, cutting `30k`-photo similarity RAM from `~3.6 GB` to `~60 MB` with **100% identical** clusters).
  - Extracts embeddings **before** touching prior `Cluster` rows so stopping mid-extraction is completely non-destructive, clears stale scores once ready, and initially elects `Cluster.best_photo_id` strictly by largest `file_size`.
- **On-Demand Deep Aesthetic Scoring (`POST /api/v1/cluster/aesthetic-score`):**
  - Triggered **only when requested** (`Score Aesthetics` / `Chấm điểm thẩm mỹ`) and scoped exclusively to multi-photo AI Similar Clusters—never running automatically during scan/cluster and never applied to Exact Duplicates.
  - Evaluates technical quality (`sharpness`, `resolution/compression`, `exposure`, `contrast`), **camera horizon tilt & Rule-of-Thirds composition** (`OpenCV Canny + HoughLinesP`), and **face focus & closed-eye detection** (`MediaPipe FaceLandmarker` with `cv2.setNumThreads(1)`, multi-crop small-face portrait passes + 100% offline OpenCV fallback).
  - Surfaces up to 4 canonical aesthetic tags (`eyes_closed`, `face_blurry`, `tilted_horizon`, `edge_subject`, `eyes_open_sharp`, `level_horizon`, `rule_of_thirds`) and re-elects `Cluster.best_photo_id` to promote sharp, level, open-eye frames.
- **Large-Library Scale, Cooperative Cancellation & External Drive Protection:**
  - **Cooperative Cancellation (`POST /api/v1/scan/cancel`):** Stop folder scanning, AI clustering, or aesthetic scoring at any moment via the `ScanningPage` Stop button while cleanly preserving already-processed photos and existing clusters.
  - **Server-Side SQL Totals & Infinite Scroll (`PAGE_SIZE = 100`):** Full-library `total_bytes` and `total_photos` SQL aggregates keep Sidebar, Master Header, and Bottom Bar counters exact from page 1 while `ResultsPage` Pane 2 (`#1E1E20` master list) streams unlimited `100`-group pages on scroll (lifting the legacy `300`-group cap).
  - **Mount-Aware External Volume Protection (`/Volumes/<Drive>` & Windows `D:\` / `E:\`):** Unplugging an external drive on macOS or a removable drive letter on Windows never prunes your indexed `Photo`, `Cluster`, or `aesthetic_score` rows in SQLite—UniPhoto displays an inline disconnected-volume notice strip (`disconnected_volumes`) and restores all groups and scores immediately when the drive is reconnected.
- **Safe OS Trash & Recycle Bin Cleanup (Zero Permanent Deletion):**
  - Smart Cleanup moves selected photos safely to **macOS Trash** (`NSFileManager.trashItemAtURLResultingItemURLError` with collision-safe `~/.Trash` fallback) or **Windows Recycle Bin** (Win32 `SHFileOperationW` `FOF_ALLOWUNDO` with PowerShell `SendToRecycleBin` fallback)—never calling `os.remove()`, preserving *"Put Back"* / Recycle Bin restore metadata, and automatically rebalancing remaining groups.
- **Native macOS & Windows 10/11 Split-View UX, Unicode Path Safety & Keyboard Workflow:**
  - **macOS:** Native Overlay Titlebar (`titleBarStyle: "Overlay"`, `trafficLightPosition: { x: 18, y: 22 }`, `pl-[76px]`+ traffic-light safe zones) paired with `NSVisualEffectView` Sidebar Vibrancy (`Effect::Sidebar`), `Preview` & `Finder` integration, and `⌘` shortcuts.
  - **Windows 10/11:** Native standard dark window frame (`tauri.windows.bundle.json` `transparent: false` + `Effect::Mica`), hidden sidecar console (`CREATE_NO_WINDOW`), Unicode/Vietnamese path-safe OpenCV decoding (`np.fromfile` + `cv2.imdecode`), Windows default Photo Viewer & `explorer /select` integration, and `Ctrl` shortcuts.
  - Authentic **3-pane split layout** on `ResultsPage`: collapsible sidebar (`#007AFF` active source-list items, `#FFD60A` storage bar), `#1E1E20` master group list (`⌘F` / `Ctrl+F` capsule search, circular action buttons), and `#161618` / `#141416` darkroom detail stage (`Large View` / `Compare Grid`), plus Tauri v2 **Folder Drag & Drop** on `HomePage` and instant `VI` ⇄ `EN` internationalization.
  - **Interactive 4-Step User Guide (`TutorialModal.tsx`):** Auto-shown on first launch (`uniphoto_tutorial_seen_v1`) with **Previous**, **Next / Get Started**, and **Skip** controls (`←/→`, `Enter`, `Esc`), bespoke native UI mini-previews, inline `VI` ⇄ `EN` switching, and 1-click replay anytime via the **Hướng dẫn / Guide** (`?`) button on both the Home screen and Results toolbar.
- **Slim Standalone Offline Packaging, In-App Updater & Dual-OS Auto-Release (`macOS` & `Windows`):**
  - **macOS (`bash scripts/build_macos_app.sh`):** Reads the release version dynamically from `tauri.conf.json`, builds a slim PyInstaller `--onedir` sidecar (`~268 MB`, excluding `torch`/`scipy`/`matplotlib`/`sklearn`/`imagehash`), syncs `backend/` and offline `mobilenet_v2.onnx` (`8.4 MB`) + `face_landmarker.task` (`3.6 MB`) into `UniPhoto.app` (`~288 MB`) with symlink-preserving `rsync -a --delete` and `strip -x`, verifies ad-hoc deep `codesign` + `--self-test`, and packages both a compressed `UDZO` `.dmg` (`~100 MB`) and a symlink/signature-preserving `ditto` `.zip` archive (`UniPhoto_<version>_aarch64.zip`).
  - **Windows 10/11 (`scripts/build_windows_app.ps1`):** Builds `uniphoto-backend.exe` + offline ONNX/MediaPipe models into standalone NSIS `UniPhoto_<version>_x64-setup.exe` (`~98 MB`) and `.msi` installers, storing runtime data in `%LOCALAPPDATA%\UniPhoto\uniphoto.db` with Win32 `SYNCHRONIZE` parent-process watchdog cleanup.
  - **Level 1 In-App Updater & 1-Command Release Automation:** `frontend/src/utils/updater.ts` and `UpdateModal.tsx` check GitHub Releases (`releases/latest`, 15-min cache, offline/404-safe, plus manual check on `HomePage` & `ResultsPage`) and open the matching `.dmg`/`.zip` or `.exe`/`.msi` installer while preserving 100% of user scan history. `scripts/bump_version.py` atomically syncs all 6 version-bearing files, and pushing a `v*` tag triggers parallel `macos-latest` + `windows-latest` builds in `.github/workflows/build-windows.yml`.

---

## 🛠️ Architecture & Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Desktop Shell** | Tauri v2 (`@tauri-apps/api`, `@tauri-apps/plugin-dialog`, `@tauri-apps/plugin-opener`), macOS Overlay Titlebar & `Effect::Sidebar` vibrancy, Windows 11 `Effect::Mica` & `CREATE_NO_WINDOW` sidecar spawn, dynamic port manager (`src-tauri/src/lib.rs`) |
| **Frontend UI** | React 19, TypeScript, Vite 8, Tailwind CSS v4, Native Split-View UI (`App.css`), SF-style SVG icons (`MacIcons.tsx`), `GlassModal` / `UpdateModal` / `TutorialModal`, OS-aware `VI`/`EN` i18n |
| **Backend API** | Python 3, FastAPI, Uvicorn, Pydantic v2 (`pydantic-settings`), dynamic `HOST`/`PORT` & `/api/v1/health` |
| **Database** | SQLite 3 (`data/uniphoto.db` in dev; `~/Library/Application Support/com.hung.uniphoto/uniphoto.db` on macOS; `%LOCALAPPDATA%\UniPhoto\uniphoto.db` on Windows) via SQLAlchemy 2.0 (`PRAGMA journal_mode=WAL`, automatic schema migration) |
| **Image & Hashing** | Pillow (`PIL`), `pillow-heif` (`.heic`/`.heif`), pure NumPy + Pillow 2D DCT-II `pHash` 16×16 (bit-for-bit `ImageHash` equivalent), Unicode-safe `np.fromfile` + `cv2.imdecode` |
| **AI & Computer Vision** | OpenCV DNN (`cv2.dnn` running `float32` `mobilenet_v2.onnx` with optional dev-only PyTorch fallback), NumPy `O(B·N)` chunked L2 cosine similarity, `MediaPipe` Tasks (`FaceLandmarker`), OpenCV (`HoughLinesP` camera tilt, Laplacian/Sobel sharpness, offline face/eye fallback) |
| **Packaging, Updater & CI** | Slim PyInstaller `--onedir` (`uniphoto_backend.spec`), macOS `.app` / `.dmg` / `.zip` (`scripts/build_macos_app.sh`), Windows NSIS `.exe` / `.msi` (`scripts/build_windows_app.ps1`), In-App GitHub Release Updater (`updater.ts`), 1-command version sync (`scripts/bump_version.py`), dual-OS GitHub Actions (`.github/workflows/build-windows.yml`) |

---

## ⌨️ Keyboard Shortcuts (`ResultsPage`)

Click the Keyboard Shortcuts icon button in the top toolbar of the Results screen to view all shortcuts at any time (`⌘F` / `Ctrl+F` works anywhere unless a confirmation, update, or tutorial modal is open; single-key shortcuts pause automatically while typing in search inputs):

| Shortcut | Action |
| :--- | :--- |
| `⌘F` / `Ctrl+F` | Focus and select the capsule group/photo search bar |
| `←` / `→` | Select previous / next photo in the active group |
| `↑` / `↓` | Select previous / next group in the master list |
| `Space` | Toggle cleanup selection on the focused photo |
| `1` / `2` | Switch between **Large View** (`1`) and **Compare Grid** (`2`) |
| `P` / `Enter` | Open the focused photo in macOS **Preview** / Windows default photo viewer |
| `F` | Reveal the focused photo in macOS **Finder** / Windows **File Explorer** |
| `⌘A` / `Ctrl+A` | Smart-select all non-best duplicates/alternates in the active tab |
| `Esc` | Close the shortcuts popover or clear/blur the active search filter |

---

## 📁 Project Structure

```text
UniPhoto/
├── .github/workflows/
│   └── build-windows.yml               # Dual-OS GitHub Actions CI: builds macOS (.dmg/.zip) & Windows (.exe/.msi) on v* tags
├── app/                                # FastAPI Python backend
│   ├── main.py                         # FastAPI app, CORS, lifespan SQLite WAL init, /api/v1/health & aliases
│   ├── core/
│   │   ├── config.py                   # Pydantic Settings (dev data/ vs macOS App Support / Windows %LOCALAPPDATA%\UniPhoto)
│   │   └── database.py                 # SQLite engine (WAL pragma + automatic column migration)
│   ├── models/models.py                # SQLAlchemy ORM models (Photo, Cluster)
│   ├── repositories/photo_repository.py# SQL pHash/cluster queries, server-side total_bytes/total_photos & mount filters
│   ├── schemas/                        # Pydantic v2 request/response models (scan, cluster, photo)
│   ├── services/
│   │   ├── scanner.py                  # Recursive scan, EXIF orientation/time, pure-DCT 16x16 pHash, 100-photo batch commits & cancel
│   │   ├── ai_engine.py                # Offline-first cv2.dnn ONNX MobileNetV2 embeddings (Unicode-safe decode) & O(B·N) clustering
│   │   ├── quality_scorer.py           # On-demand technical sharpness/exposure/contrast/fidelity scorer
│   │   ├── aesthetic_scorer.py         # On-demand cluster scorer: quality + tilt/composition + face/eyes (offline model lookup)
│   │   ├── photo_service.py            # Dynamic-port thumbnails, /Volumes & D:\ guard, macOS Trash & Windows Recycle Bin
│   │   └── progress_tracker.py         # Real-time in-memory progress state & cooperative _CANCEL_EVENT
│   └── api/v1/                         # /api/v1 router & endpoints (scan, cluster, photos)
├── frontend/                           # Tauri v2 + React 19 + Tailwind CSS v4 desktop client
│   ├── src/
│   │   ├── App.tsx                     # Root state, readiness boot, first-launch tutorial, scan/score, drag-drop & update check
│   │   ├── App.css                     # Native SF Pro / Segoe UI typography, macOS vibrancy & Windows dark surfaces
│   │   ├── api/PhotoApi.ts             # Dynamic-port REST client (invoke("get_backend_url") + /health check)
│   │   ├── components/                 # MacIcons, CustomCheckbox, LanguageSwitcher, GlassModal, UpdateModal, TutorialModal, GlassToast
│   │   ├── i18n/                       # Bilingual VI/EN dictionary & I18nContext
│   │   ├── pages/                      # HomePage, ScanningPage, ResultsPage (3-pane split-view)
│   │   └── utils/                      # photoHelpers.ts & updater.ts (GitHub Releases semver check & OS asset selector)
│   └── src-tauri/                      # macOS Overlay + Windows bundle config (src/lib.rs, tauri.conf.json, tauri.windows.bundle.json)
├── scripts/
│   ├── bump_version.py                 # 1-command atomic version sync & --check across all 6 version-bearing files
│   ├── build_macos_app.sh              # 1-command slim offline macOS .app (~288 MB), .dmg (~100 MB) & .zip builder
│   ├── build_windows_app.ps1           # 1-command slim offline Windows 10/11 NSIS .exe (~98 MB) & .msi builder
│   ├── export_mobilenet_v2_onnx.py     # Offline float32 Conv+BN-folded ONNX exporter & cv2.dnn validator
│   └── pyi_rth_stub_unused.py          # PyInstaller runtime hook stubbing unused matplotlib imports in MediaPipe
├── website/                            # Minimalist dual-OS (macOS & Windows) download landing page (zero-build HTML/CSS/JS)
├── data/                               # Local dev runtime storage (auto-created; untouched by packaged builds)
│   ├── uniphoto.db                     # Dev SQLite WAL database
│   └── models/                         # mobilenet_v2.onnx (8.4 MB) & face_landmarker.task (3.6 MB)
├── tests/
│   └── test_uniphoto_pipeline.py       # Isolated 12-test stdlib unittest suite (:memory: SQLite + ONNX/DCT + win32 + release sync)
├── .agents/skills/uniphoto/
│   └── scripts/                        # create_demo_dataset.py & verify.sh
├── uniphoto_backend.spec               # Slim cross-platform PyInstaller --onedir spec (excludes torch/scipy/matplotlib)
├── requirements.txt                    # Core slim runtime + optional .venv model-export/verification dependencies
└── run.py                              # Uvicorn entrypoint (freeze_support, dynamic HOST/PORT, --self-test, cross-OS watchdog)
```

---

## 🗄️ SQLite Database Schema (`uniphoto.db`)

UniPhoto initializes SQLite automatically on startup (`data/uniphoto.db` during local development, `~/Library/Application Support/com.hung.uniphoto/uniphoto.db` inside packaged macOS `.app`, or `%LOCALAPPDATA%\UniPhoto\uniphoto.db` on packaged Windows, overridable via `UNIPHOTO_DATA_DIR`) with `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and `PRAGMA foreign_keys=ON`, running non-destructive `ALTER TABLE` column migrations when needed.

### `photos`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER PK` | Auto-increment photo ID |
| `file_path` | `VARCHAR(500) UNIQUE` | Absolute filesystem path |
| `file_size` | `INTEGER NOT NULL` | File size in bytes (primary ranking key for Duplicates & unscored Similar clusters) |
| `width`, `height` | `INTEGER NULL` | EXIF-oriented pixel dimensions |
| `timestamp` | `DATETIME NULL` | Capture timestamp (`DateTimeOriginal` / `DateTime` / OS `mtime`) |
| `phash` | `VARCHAR(64) INDEXED` | 256-bit hex string from pure NumPy/Pillow 2D DCT-II `calculate_phash` (bit-for-bit `imagehash.phash(..., hash_size=16)`) |
| `quality_score` | `FLOAT NULL` | On-demand composite technical quality (`0–100`) for scored AI clusters |
| `sharpness_score`, `exposure_score`, `contrast_score` | `FLOAT NULL` | On-demand technical sub-scores (`0–100`) |
| `aesthetic_score` | `FLOAT NULL` | On-demand composite AI aesthetic score (`0–100`) for scored AI clusters |
| `composition_score` | `FLOAT NULL` | Camera horizon levelness & Rule-of-Thirds subject placement (`0–100`) |
| `face_score` | `FLOAT NULL` | Face ROI focus & eye openness (`0–100`, `NULL` when no face is present) |
| `pose_score` | `FLOAT NULL` | Reserved compatibility column (`NULL`; body posture scoring is disabled) |
| `tilt_angle` | `FLOAT NULL` | Estimated camera roll tilt in degrees (e.g., `6.5`) |
| `has_closed_eyes` | `BOOLEAN NULL` | `True` when a prominent face has closed eyes / blink |
| `aesthetic_tags` | `VARCHAR(500) NULL` | JSON array of up to 4 canonical tags (`eyes_closed`, `tilted_horizon`, etc.) |
| `cluster_id` | `INTEGER FK` | Foreign key to `clusters.id` (`ON DELETE SET NULL`) |
| `status` | `VARCHAR(50) INDEXED` | `"keep"` or `"exact_duplicate"` |

### `clusters`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER PK` | Auto-increment AI similarity cluster ID |
| `best_photo_id` | `INTEGER FK` | Recommended photo ID (`(file_size, -id)` initially; `(aesthetic_score, quality_score, file_size, -id)` once scored) |

---

## 📡 REST API Endpoints

Interactive OpenAPI docs are served at `http://127.0.0.1:8000/api/v1/docs` when the backend is running.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Sidecar readiness & dynamic port health check (`{ "status": "ok", "version", "port" }`) |
| `GET` | `/api/v1/scan/progress` | Real-time progress polling (`idle`, `scanning`, `clustering`, `aesthetic_scoring`, `cancelled`, `done`, `cancel_requested`) |
| `POST` | `/api/v1/scan/cancel` (alias `/api/scan/cancel`) | Cooperatively cancel active folder scan, AI clustering, or aesthetic scoring |
| `POST` | `/api/v1/scan` (alias `/api/scan`) | Scan folder (`100`-photo batch commits), extract EXIF & pure-DCT 16×16 `pHash`, elect `"keep"` by largest `file_size` (`cancelled` flag) |
| `POST` | `/api/v1/cluster` (alias `/api/cluster`) | Extract `ONNX MobileNetV2` embeddings via `cv2.dnn` (non-destructive on cancel), run `O(B·N)` chunked cosine clustering (`block_size=512`, `>= 0.85`), elect largest `file_size` |
| `POST` | `/api/v1/cluster/aesthetic-score` | On-demand quality + horizon tilt/composition + face/closed-eye scoring for AI clusters (`25`-photo commits, `cancelled` flag) |
| `GET` | `/api/v1/photos/duplicates` | Paginated exact-duplicate groups (`limit=100, offset`) with full-dataset `total_bytes`, `total_photos`, and `disconnected_volumes` |
| `GET` | `/api/v1/photos/clusters` | Paginated AI clusters (`limit=100, offset`) with full-dataset `total_bytes`, `total_photos`, and `disconnected_volumes` |
| `POST` | `/api/v1/photos/rescore` | Rebalance duplicates by file size & re-run aesthetic scoring on AI clusters |
| `GET` | `/api/v1/photos/{id}/thumbnail?size=360` | Stream EXIF-transposed JPEG thumbnail (`100..1600` px) directly from RAM |
| `POST` | `/api/v1/photos/{id}/open?mode=preview\|finder` | Open photo in default viewer (`Preview` / `os.startfile`) or reveal in `Finder` / `File Explorer` |
| `POST` | `/api/v1/photos/open-multiple` | Open multiple photo IDs together in `Preview` / Windows photo viewer |
| `POST` | `/api/v1/photos/delete-multiple` | Safely move `{ "photo_ids": [...] }` to macOS Trash / Windows Recycle Bin & rebalance groups |
| `DELETE` | `/api/v1/photos/{id}` | Safely move a single photo to macOS Trash / Windows Recycle Bin & rebalance its group |
| `POST` | `/api/v1/photos/reset` | Clear all indexed rows in `photos` and `clusters` |

---

## 🚀 Local Setup & Running

### Prerequisites
- **macOS 12+** (Apple Silicon or Intel) or **Windows 10/11 (x64)**
- **Python 3.11+**
- **Node.js `^20.19.0 || >=22.12.0` & npm** (for Vite 8)
- **Rust toolchain (`cargo`)** for Tauri v2

### 1. Python Virtual Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
> **Note on `requirements.txt`:** Core runtime packages (`fastapi`, `uvicorn`, `SQLAlchemy`, `pillow`, `pillow_heif`, `numpy`, `opencv-python`, `mediapipe`) power the slim production app, while optional model-export & equivalence-verification packages (`torch`, `torchvision`, `ImageHash`, `scikit-learn`) remain in `.venv` for `scripts/export_mobilenet_v2_onnx.py` and `tests/test_uniphoto_pipeline.py` (excluded from `UniPhoto.app`).

### 2. Launch Desktop App (`npm run tauri dev` — Single or Dual Terminal)
```bash
npm --prefix frontend install
npm --prefix frontend run tauri dev
```
- **Single-Terminal Auto-Spawn:** If port `8000` (or `UNIPHOTO_BACKEND_PORT`) is not already listening, `frontend/src-tauri/src/lib.rs` automatically picks a free port and spawns `.venv/bin/python run.py` as a managed child process (terminating it cleanly on exit).
- **Two-Terminal Hot-Reload Mode (Optional):** If you want `uvicorn --reload` logs or Swagger docs fixed at `http://127.0.0.1:8000/api/v1/docs`, run `.venv/bin/python run.py` in Terminal 1 first; `tauri dev` in Terminal 2 will detect port `8000` and connect to it without spawning a second server.
- > **Note:** Always launch via `npm --prefix frontend run tauri dev` (rather than a plain browser tab) so Tauri v2 Overlay Titlebar & `Effect::Sidebar` vibrancy, native folder dialog, folder drag-and-drop events, `get_backend_url` port discovery, and macOS window title synchronization are active.

---

## 📦 Building Slim Standalone macOS `.app` (`~288 MB`), `.dmg` (`~100 MB`) & `.zip`

Package UniPhoto into a self-contained, 100% offline-capable `UniPhoto.app` (`~288 MB`, down `~80%` from `~1.48 GB`), compressed `UniPhoto_<version>_<arch>.dmg` (`~100 MB`), and `UniPhoto_<version>_<arch>.zip` archive—no Python, PyTorch, or Homebrew required on the recipient's Mac:

```bash
bash scripts/build_macos_app.sh
```

### What `scripts/build_macos_app.sh` Does
1. **Toolchain & Node.js Check:** Verifies `.venv/bin/python`, compatible Node.js (`^20.19.0 || >=22.12.0`), `npm`, `cargo`, `rsync`, and `codesign` (installing `pyinstaller` into `.venv` automatically if not yet present; pass `--check-env` to check only or `--rebuild-backend` to force a clean PyInstaller rebuild).
2. **Pre-Bundles Offline AI Weights (`build/bundled-models/`):** Stages `face_landmarker.task` (`3.6 MB`) and unquantized `float32` `mobilenet_v2.onnx` (`8.4 MB`, exported and validated against PyTorch via `scripts/export_mobilenet_v2_onnx.py` if absent) so AI clustering and portrait/eye scoring run 100% offline.
3. **Compiles Slim Backend Sidecar (`build/pyinstaller/uniphoto-backend/`, `~268 MB`):** Packages `run.py` + FastAPI + SQLAlchemy + Pillow/HEIF + OpenCV DNN + MediaPipe via PyInstaller `--onedir` (`uniphoto_backend.spec`), excluding `torch`/`torchvision`/`scipy`/`imagehash`/`pywt`/`sklearn`/`matplotlib`, stubbing unused `matplotlib` imports via `scripts/pyi_rth_stub_unused.py`, deduplicating identical `.dylib` files via relative symlinks, stripping Mach-O debug symbols (`strip -x`), and verifying `--self-test` + `GET /api/v1/health`.
4. **Builds Tauri `.app` Shell & Syncs Resources Preserving Symlinks:** Runs `npm --prefix frontend run tauri build -- --bundles app` (keeping `tauri.conf.json` and `tauri.bundle.json` clean so Tauri never dereferences `.dylib` symlinks into duplicate copies) and syncs `backend/` and `models/` into `UniPhoto.app/Contents/Resources/` via `rsync -a --delete`.
5. **Ad-Hoc Deep Signing, In-Bundle `--self-test`, `.dmg` & `.zip`:** Reads `APP_VERSION` dynamically from `frontend/src-tauri/tauri.conf.json`, applies ad-hoc `codesign --force --deep --sign -` + `codesign --verify --deep --strict` on `UniPhoto.app` (`~288 MB`), runs `Contents/Resources/backend/uniphoto-backend --self-test` (`~0.66s`), creates `UniPhoto_<version>_<arch>.zip` via `ditto -c -k --sequesterRsrc --keepParent` (preserving symlinks & Mach-O signatures), and creates `UniPhoto_<version>_<arch>.dmg` via `hdiutil create -format UDZO -imagekey zlib-level=9` (`~100 MB`).

### Packaged Runtime Lifecycle (`frontend/src-tauri/src/lib.rs`)
- **Automatic Free Port Selection (`get_backend_url`):** Prefers `127.0.0.1:8000` and seamlessly falls back to an OS-assigned free ephemeral port if `8000` is busy; React resolves the dynamic base URL via `invoke("get_backend_url")` (`PhotoApi.ts`) and displays a native macOS readiness screen while the sidecar initializes.
- **Writable App Support Database:** Sets `UNIPHOTO_PACKAGED=1` and `UNIPHOTO_DATA_DIR=~/Library/Application Support/com.hung.uniphoto` (`uniphoto.db`), never writing inside read-only `/Applications/UniPhoto.app` and keeping `data/uniphoto.db` strictly for local repo development.
- **Zero Orphan Processes:** Terminates and reaps the sidecar on Tauri `RunEvent::Exit`, backed up by `run.py`'s `UNIPHOTO_PARENT_PID` daemon watchdog (`2.0s` check calling `os._exit(0)` if the parent app is ever force-quit).

### First-Launch Gatekeeper Tip (Unsigned macOS Distribution)
Because `scripts/build_macos_app.sh` uses local ad-hoc signing (`codesign --sign -`) rather than a paid Apple Developer ID notarization certificate, macOS Gatekeeper may quarantine the app when copied to another Mac. Clear the quarantine extended attribute once after dragging `UniPhoto.app` to `/Applications`:
```bash
xattr -cr /Applications/UniPhoto.app
```

---

## 🪟 Windows 10/11 Build & 1-Command Dual-OS Auto-Release (`macOS` + `Windows`)

### Option A — Local Build on Windows 10/11 (PowerShell)
```powershell
pwsh -File scripts/build_windows_app.ps1
```
`scripts/build_windows_app.ps1` verifies `.venv\Scripts\python.exe`, installs only slim runtime dependencies (`fastapi`, `uvicorn`, `SQLAlchemy`, `pillow`, `pillow_heif`, `numpy`, `opencv-python`, `mediapipe`, `pyinstaller`—no `torch` needed), stages offline `mobilenet_v2.onnx` (`8.4 MB`) + `face_landmarker.task` (`3.6 MB`), compiles `build\pyinstaller\uniphoto-backend\uniphoto-backend.exe` via `uniphoto_backend.spec`, verifies `--self-test` + `/api/v1/health`, and builds standalone NSIS `UniPhoto_0.1.0_x64-setup.exe` (`~98 MB`) and WiX `.msi` installers via `npm --prefix frontend run tauri build -- --bundles nsis,msi --config src-tauri/tauri.windows.bundle.json` (spawning the sidecar with `CREATE_NO_WINDOW`, storing SQLite data in `%LOCALAPPDATA%\UniPhoto\uniphoto.db`, and monitoring parent GUI liveness via Win32 `OpenProcess(SYNCHRONIZE)` + `WaitForSingleObject`).

### Option B — 1-Command Version Bump & Dual-OS GitHub Actions Release (`scripts/bump_version.py` + `.github/workflows/build-windows.yml`)
1. **Check or bump all 6 version-bearing files atomically** (`app/core/config.py`, `frontend/package.json`, `frontend/src-tauri/Cargo.toml`, `frontend/src-tauri/tauri.conf.json`, `frontend/src/utils/updater.ts`, and `website/script.js`):
   ```bash
   .venv/bin/python scripts/bump_version.py --check
   .venv/bin/python scripts/bump_version.py 0.2.0
   ```
2. **Commit & push a `v*` tag** (or trigger `workflow_dispatch` in GitHub Actions):
   ```bash
   git add -A && git commit -m "chore: release v0.2.0"
   git tag v0.2.0 && git push origin main v0.2.0
   ```
   `.github/workflows/build-windows.yml` runs **`build-macos` (`macos-latest` Apple Silicon `.dmg` & `.zip`)** and **`build-windows` (`windows-latest` x64 `.exe` & `.msi`)** in parallel and attaches all 4 installers directly to the GitHub Release via `softprops/action-gh-release@v2`—where both the **Level 1 In-App Updater** (`frontend/src/utils/updater.ts` + `UpdateModal.tsx`) and `website/script.js` automatically discover the new version and select the right OS installer.

---

## 🧪 Demo Dataset, Automated Tests & Verification

### Generate a Safe Demo Photo Folder
Create a self-contained test library under `/tmp/uniphoto-demo` containing exact duplicates across subfolders, two realistic AI burst clusters (`OldQuarter` & `Sailboat` with sharp, blurry, exposure-shifted, and `6.5°` tilted camera frames), and a standalone unique photo:
```bash
.venv/bin/python .agents/skills/uniphoto/scripts/create_demo_dataset.py /tmp/uniphoto-demo --overwrite
```
You can then **drag & drop** `/tmp/uniphoto-demo` directly onto the UniPhoto home dropzone panel or select it via the folder picker.

### Run the Isolated Unit Test Suite (`12/12` Tests)
`tests/test_uniphoto_pipeline.py` uses Python's `unittest` with an isolated in-memory SQLite database (`sqlite:///:memory:`), temporary image directories, and `UNIPHOTO_TRASH_DIR` / `UNIPHOTO_VOLUMES_ROOT` / `UNIPHOTO_UNMOUNTED_VOLUMES` (never touching `data/uniphoto.db` or system Trash) to test EXIF orientation & pure-DCT `pHash` scanning, `O(B·N)` chunked cosine similarity equivalence (`1,200 × 1280-d`), on-demand aesthetic/tilt/portrait scoring, collision-safe Trash moves, cooperative cancellation (`request_cancel`), server-side pagination totals (`limit`/`offset`), mount-aware external volume protection, packaged runtime configuration (`/api/v1/health`, dynamic `settings.PORT` thumbnail URLs, `UNIPHOTO_DATA_DIR` / `UNIPHOTO_PACKAGED=1`, and offline `UNIPHOTO_MODELS_DIR` lookup), mathematical slim-runtime equivalence (`calculate_phash` bit-for-bit equality against `imagehash.phash` + ONNX `cv2.dnn` vs PyTorch `MobileNetV2` cosine similarity `>= 0.99999`), Windows (`win32`) cross-platform support (`%LOCALAPPDATA%\UniPhoto`, removable drive-letter protection `E:\`, Unicode/Vietnamese path decoding across `ai_engine` / `quality_scorer` / `aesthetic_scorer`, and root drive `folder_name` serialization), and multi-file release version sync & `scripts/bump_version.py` automation:
```bash
.venv/bin/python -m unittest discover -s tests -p "test_*.py" -v
```

### Run Full-Stack Verification
Verify Python syntax/imports, the `12/12` `unittest` pipeline suite, Frontend TypeScript (`tsc`) + Vite production build, and (optionally) Rust/Tauri `cargo check`:
```bash
bash .agents/skills/uniphoto/scripts/verify.sh
bash .agents/skills/uniphoto/scripts/verify.sh --tauri
```
