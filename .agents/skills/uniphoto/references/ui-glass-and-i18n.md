# UniPhoto Frontend: Apple macOS Native Split-View & Sidebar Vibrancy, UX & i18n Guide

## 1. Apple macOS Native Split-View & Sidebar Vibrancy Design System

UniPhoto uses **Tailwind CSS v4** (`@import "tailwindcss";` in `frontend/src/App.css`) paired with native Tauri v2 macOS Overlay Titlebar & `NSVisualEffectView` Sidebar Vibrancy (`frontend/src-tauri/`) to deliver an authentic **Apple macOS Sequoia / Tahoe native app** experience (modeled after Apple Mail, Calendar, Messages, and Finder split-view).

### Core Visual Principles
- **Native macOS Surfaces Only:** Do **not** re-introduce sci-fi neon radial blobs, floating 4-island card gaps, blurred rainbow ambient photo reflections behind the preview stage, or emoji UI icons.
- **Transparent Root + Opaque Content Panes (`frontend/src/App.css`):**
  - `html, body, #root` keep `background-color: transparent; color: #f2f2f7;` with SF Pro system typography (`-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display"`) and slim `6px` translucent scrollbars.
  - Keeping `#root` transparent lets macOS `NSVisualEffectView` (`Effect::Sidebar`) shine through **Pane 1** (`bg-[#252528]/78 backdrop-blur-2xl`), while **Pane 2** (`bg-[#1E1E20]`), **Pane 3** (`bg-[#161618]` / `bg-[#141416]`), and single-pane screens (`HomePage`, `ScanningPage`, `App.tsx` boot screen: `bg-[#161618]` + `bg-[#1C1C1E]` header) use solid dark macOS surfaces so text and imagery remain crisp and distraction-free.
- **SF-Symbols-Inspired SVG Icon Suite (`frontend/src/components/MacIcons.tsx`):**
  - All UI icons are crisp `15px–18px` (`48px` for empty-state `IconPhotoStack`) `1.7px`-stroke SVG components: `IconSidebarLeft`, `IconDuplicates`, `IconSimilars`, `IconCheckCircle`, `IconFolder`, `IconSparkles`, `IconSearch`, `IconWand`, `IconSort`, `IconRefresh`, `IconEye`, `IconFinder`, `IconGrid`, `IconSingle`, `IconKeyboard`, `IconTrash`, `IconClose`, `IconChevronRight`, `IconChevronDown`, `IconPhotoStack`, and `IconWarning`.

### macOS Overlay Titlebar, Vibrancy & Traffic-Light Safe Zones (`frontend/src-tauri/`)
- **Window Configuration (`frontend/src-tauri/tauri.conf.json`):**
  - `"macOSPrivateApi": true` under `app`.
  - Under `app.windows[0]`: `"width": 1240`, `"height": 820`, `"minWidth": 920`, `"minHeight": 620`, `"titleBarStyle": "Overlay"`, `"hiddenTitle": true`, `"trafficLightPosition": { "x": 18, "y": 22 }`, and `"transparent": true`.
- **Capabilities & Native Vibrancy (`capabilities/default.json`, `Cargo.toml`, `src/lib.rs`):**
  - `capabilities/default.json` grants `"core:window:allow-start-dragging"` (enabling `data-tauri-drag-region`) alongside `"core:window:allow-set-title"`, `"core:default"`, `"opener:default"`, and `"dialog:default"`.
  - `Cargo.toml` enables `tauri = { version = "2", features = ["macos-private-api"] }` (compiles 100% offline against `Cargo.lock`), and `src/lib.rs` applies `window.set_effects(EffectsBuilder::new().effect(Effect::Sidebar).state(EffectState::Active).build())` on `"main"` under `#[cfg(target_os = "macos")]`.
- **Mandatory Traffic-Light Safe Zone Rule (`pl-[76px]`+ & `data-tauri-drag-region`):**
  - Native macOS `● ● ●` window controls occupy `x: 14..72px, y: 0..42px` at the top-left of the window.
  - Every top-level screen **must** provide `data-tauri-drag-region` on non-interactive header containers (never on `<button>` or `<input>`) and maintain `>= 76px` left clearance so traffic lights never overlap UI controls:
    - `App.tsx` (boot screen), `HomePage.tsx`, and `ScanningPage.tsx`: top `<header data-tauri-drag-region className="h-[46px] pl-[80px] pr-4 bg-[#1C1C1E] border-b border-white/[0.07] ...">`.
    - `ResultsPage.tsx`: when the sidebar is open, Pane 1's top strip uses `h-[46px] pl-[78px] pr-3` (`data-tauri-drag-region`) with the `<IconSidebarLeft />` collapse toggle on the right; when `isSidebarCollapsed` is `true`, Pane 2's top header dynamically adds `pl-[76px]` and renders the `<IconSidebarLeft />` expand button immediately to the right of the traffic lights.

### 3-Pane Split-View Architecture (`frontend/src/pages/ResultsPage.tsx`)
1. **Pane 1 — Vibrancy Source-List Sidebar (`w-[232px] shrink-0 bg-[#252528]/78 backdrop-blur-2xl border-r border-white/[0.09]`):**
   - Top `h-[46px] pl-[78px] pr-3` `data-tauri-drag-region` strip with `<IconSidebarLeft />` collapse toggle.
   - Source-list items (`Duplicates`, `Similar Photos`, `Selected`): active item renders solid Apple Blue `bg-[#007AFF] text-white font-medium rounded-[8px] px-2.5 py-[7px]` with white icon; inactive items use `text-[#E5E5EA] hover:bg-white/[0.06]` with `#0A84FF` icon and right-aligned `tabular-nums` total bytes or selected count.
   - `Storage` / `Lưu trữ` section: `Change Folder` (`<IconFolder />`), `Find Similar` (`<IconSparkles />`), `{selected} / {total}` byte readout, and thin `3px` `#FFD60A` storage bar.
   - Pinned bottom status row (`px-3 py-2.5 border-t border-white/[0.07]`): UniPhoto badge, `#30D158` live dot + `serverTotalFilesCount`, `<LanguageSwitcher compact />`, and `<IconRefresh />`.
2. **Pane 2 — Master Group List (`w-[295px] lg:w-[320px] shrink-0 bg-[#1E1E20] border-r border-white/[0.08]`):**
   - `data-tauri-drag-region` header (`pl-[76px]` + `<IconSidebarLeft />` when sidebar is collapsed) displaying the active filter title and `{groups} • {size}` subtitle.
   - Search & action bar: capsule search input (`bg-[#2C2C2E] focus-within:border-[#0A84FF] rounded-full h-[30px]`) with `<IconSearch />`, `⌘F` hint (`Cmd+F` / `Ctrl+F` focus shortcut) or `<IconClose />` clear button, plus `30px` circular buttons (`bg-[#2C2C2E] hover:bg-[#3A3A3C] rounded-full`) for `<IconWand />` auto-select, `<IconSort />` size/count sort toggle, and conditional `<IconClose />` deselect-all.
   - High-count scrollable group list (`divide-y divide-white/[0.05]`, zero `backdrop-filter` on rows for smooth 60fps scrolling): `w-11 h-11 rounded-[10px]` thumbnails, `bg-[#2C2C2E]` active group highlight, and `#171719` expanded file rows (`bg-[#007AFF]/20` when focused).
3. **Pane 3 — Neutral Darkroom Detail Workspace (`flex-1 min-w-0 bg-[#161618]` / `bg-[#141416]`):**
   - Unified macOS toolbar (`h-[48px] px-4 bg-[#1C1C1E] border-b border-white/[0.07]`, `data-tauri-drag-region`):
     - Authentic Apple `NSSegmentedControl` (`bg-[#2C2C2E] p-[2px] rounded-[7px]`, active segment `bg-[#48484A] text-white shadow-sm rounded-[5px]`) switching between `Large View` (`<IconSingle />`) and `Compare` (`<IconGrid />`).
     - Native `#2C2C2E hover:bg-[#3A3A3C]` action buttons for `Preview` (`<IconEye />`), `Finder` (`<IconFinder />`), and `Open Group` (`<IconFolder />`).
     - On `Similar Photos`: `#5E5CE6` `Score Aesthetics` / `#2C2C2E` `Re-score Aesthetics` (`<IconSparkles />`) button.
     - Right-aligned `<IconKeyboard />` Shortcuts button + `bg-[#262629]/95 backdrop-blur-2xl` popover.
   - Inline `#242426` notice strips (`border-b border-white/[0.07]`) for `disconnectedVolumes` and optional unscored `Similar Photos` discovery.
   - Distraction-free `#141416` darkroom photo stage (no blurred ambient photo glow), `#1A1A1C` metadata/score header, centered `<IconPhotoStack />` empty state when no group is active, crisp `#1E1E20` filmstrip & compare grid cards (`border-[#30D158]/60` keep, `border-[#0A84FF]/70` trash), and `h-11 bg-[#1C1C1E] border-t border-white/[0.07]` bottom action bar with `#007AFF` Trash CTA (`<IconTrash />`).

### Single-Pane Screens & Native macOS Overlays
- **`HomePage.tsx`:** Top `h-[46px] pl-[80px]` Overlay Titlebar (`View Previous Results` + `<LanguageSwitcher compact />`), calm `#161618` workspace, Finder/Photos dashed dropzone (`bg-[#1E1E20] border-dashed border-white/[0.14] hover:border-[#0A84FF] rounded-2xl p-8`, active drag `bg-[#0A84FF]/[0.08] border-[#0A84FF]`, `#0A84FF` `<IconFolder />`), `#1E1E20` grouped preference rows (`CustomCheckbox`), and `#007AFF` primary scan CTA.
- **`ScanningPage.tsx`:** Top `h-[46px] pl-[80px]` Overlay Titlebar, centered `#1E1E20` progress card (`rounded-2xl p-7 max-w-md`), `6px` `#007AFF` progress bar, live kept/duplicate counters, and `#2C2C2E` Stop button (`<IconClose />`).
- **`GlassModal.tsx` (`frontend/src/components/GlassModal.tsx`):** Native macOS `NSAlert`-style confirmation dialog (`bg-[#262629]/95 backdrop-blur-2xl border border-white/[0.12] rounded-2xl shadow-2xl`, `#3A3A3C` Cancel + `#FF453A` / `#007AFF` Confirm; `Escape` or backdrop click cancels, `Enter` confirms).
- **`GlassToast.tsx` (`frontend/src/components/GlassToast.tsx`):** Non-blocking macOS notification pill (`fixed bottom-5 right-5 z-50 bg-[#262629]/95 backdrop-blur-xl border border-white/[0.12] rounded-xl shadow-xl`, auto-dismiss ~4s + manual `<IconClose />`, tones `"success" | "warning" | "error"`). **Zero `window.alert()` or `window.confirm()` calls are permitted anywhere in `frontend/src/`.**
- **`LanguageSwitcher.tsx` & `CustomCheckbox.tsx`:** `NSSegmentedControl`-style `VI | EN` switcher (`bg-[#2C2C2E]`, active `bg-[#48484A]`) and `#007AFF` rounded macOS checkbox.

### Tauri Sidecar Lifecycle, Dynamic Backend URL & Cold-Start Readiness Screen (`src-tauri/src/lib.rs`, `PhotoApi.ts`, `App.tsx`)
- **Rust Sidecar & Dynamic Port Manager (`frontend/src-tauri/src/lib.rs`):**
  - Uses only `std` + `tauri = { version = "2", features = ["macos-private-api"] }` (zero extra crates in `Cargo.toml` so `cargo check --offline` compiles 100% offline).
  - Registers `BackendState { port: u16, child: Mutex<Option<Child>> }` and `#[tauri::command] get_backend_url` returning `http://127.0.0.1:{port}/api/v1`.
  - **Packaged `.app` Mode:** Detects `Contents/Resources/backend/uniphoto-backend`, picks a free port (`pick_available_port(8000)` -> ephemeral port `0` fallback), creates writable `~/Library/Application Support/com.hung.uniphoto` (`app_data_dir`), spawns the sidecar with `UNIPHOTO_PACKAGED=1`, `UNIPHOTO_DATA_DIR`, `UNIPHOTO_MODELS_DIR` (`Contents/Resources/models`), `UNIPHOTO_PARENT_PID`, and `Stdio::null()`, and kills/reaps the child on `tauri::RunEvent::Exit` (backed up by `run.py`'s `UNIPHOTO_PARENT_PID` watchdog).
  - **Local Dev Mode (`npm run tauri dev`):** Reuses an already-listening backend on `UNIPHOTO_BACKEND_PORT` / `8000`, or automatically picks a free port and spawns repo `.venv/bin/python run.py` when running `tauri dev` in a single terminal.
  - **Clean Bundle Config & Symlink-Preserving Sync (`tauri.conf.json`, `tauri.bundle.json` & `scripts/build_macos_app.sh`):** Both `tauri.conf.json` and `tauri.bundle.json` (`{}`) stay free of `build/` resource mappings so `cargo check`, `tauri dev`, and `tauri build -- --bundles app` never dereference `.dylib` symlinks into duplicate copies; `scripts/build_macos_app.sh` syncs `build/pyinstaller/uniphoto-backend -> Contents/Resources/backend` (`~268 MB`) and `build/bundled-models -> Contents/Resources/models` (`mobilenet_v2.onnx` + `face_landmarker.task`) via `rsync -a --delete`, strips Mach-O symbols, applies ad-hoc `codesign --force --deep --sign -` (`~288 MB` `UniPhoto.app`, unsigned distribution uses `xattr -cr /Applications/UniPhoto.app` on first launch), and creates a compressed `UDZO` `.dmg` (`~100 MB`).
- **Dynamic API Client & Native Readiness Boot Screen (`PhotoApi.ts` & `App.tsx`):**
  - `PhotoApi.ts` resolves and caches the backend URL via `resolveApiBase()` (`invoke<string>("get_backend_url")` with `http://127.0.0.1:8000/api/v1` browser fallback)—never hardcoding `:8000` in API calls—and exposes `checkBackendHealthApi()` (`GET ${base}/health` with `1200ms` timeout).
  - On mount, `App.tsx` checks `checkBackendHealthApi()`: if immediately `true`, loads data with zero delay; if `false` during cold PyInstaller sidecar startup (`~0.3–1s`), renders a native macOS readiness screen (`h-[46px] pl-[80px]` Overlay Titlebar with `LanguageSwitcher`, `#161618` surface, `#1E1E20` centered card, `t.app.bootingTitle` / `t.app.bootingSubtitle`, and `t.app.bootTimeoutDesc` + `#007AFF` `t.app.btnRetryConnect` retry button if the `~25s` poll window expires).

### Folder Drag & Drop (`App.tsx` & `HomePage.tsx`)
- When `screen === "home"`, `App.tsx` subscribes to Tauri v2's `getCurrentWebview().onDragDropEvent(...)` (`@tauri-apps/api/webview`) wrapped in a safe `try / catch` for browser compatibility.
- Tracks `isDraggingFolder: boolean` (`"enter"` / `"over"` -> `true`, `"leave"` / `"drop"` -> `false`). On `"drop"`, if `paths[0]` ends with `.jpg`, `.jpeg`, `.png`, `.heic`, or `.heif` (case-insensitive), extracts its parent folder; otherwise sets `folderPath` directly to the dropped directory.
- `HomePage.tsx` prevents default HTML5 drag navigation (`onDragOver` / `onDrop` `e.preventDefault()`) and highlights the Finder-style dashed dropzone panel (`bg-[#0A84FF]/[0.08] border-[#0A84FF]`) while `isDraggingFolder` is active.

### Cooperative Cancel / Stop Button (`ScanningPage.tsx` & `App.tsx`)
- `ScanningPage.tsx` receives `isCancelling: boolean` and `onCancelScan: () => void`, rendering a `#2C2C2E` Stop button (`<IconClose />` + `isCancelling ? t.scanning.btnCancelling : t.scanning.btnCancelScan`, `disabled={isCancelling}`) inside the progress card.
- `App.tsx` tracks cancellation via `useRef` + `useState` so multi-step `handleStartScan` skips `clusterPhotosApi` immediately if `scanDirectoryApi` was cancelled, calls `cancelScanApi()` (`POST /api/v1/scan/cancel`), loads already-committed partial results via `loadData(...)`, shows a reactive `"warning"` `GlassToast` (`kind: "cancelled"`), and navigates to `ResultsPage` when partial groups exist (or back to `HomePage` otherwise).

### Infinite Scroll Pagination (`PAGE_SIZE = 100`) & Disconnected Volume Strip (`App.tsx` & `ResultsPage.tsx`)
- **No `300`-Group Cap:** `App.tsx` fetches initial pages with `PAGE_SIZE = 100` (`fetchDuplicatesApi(100, 0)`, `fetchClustersApi(100, 0)`) and exposes `loadMoreDuplicates()` / `loadMoreClusters()` (appending deduplicated pages by `phash` / `cluster_id`), along with full-library SQL totals (`totalDupGroups`, `totalDupBytes`, `totalDupPhotos`, `totalSimGroups`, `totalSimBytes`, `totalSimPhotos`) and merged `disconnectedVolumes: string[]`.
- **Server-Side Totals & Pane 2 Infinite Scroll:** `ResultsPage.tsx` uses server-side `totalDupBytes`, `totalSimBytes`, and `(totalDupPhotos + totalSimPhotos)` so Sidebar, Master Header, and Bottom Bar counters reflect the entire library even when only page 1 is loaded. Pane 2's scrollable group container triggers `onLoadMoreDups()` / `onLoadMoreSims()` via `onScroll` (`scrollTop + clientHeight >= scrollHeight - 260` when `!searchQuery.trim()`) and renders a `#2C2C2E` load-more / spinner footer row when `hasMoreDups` or `hasMoreSims` is true.
- **Disconnected External Volume Notice Strip:** Whenever `disconnectedVolumes.length > 0`, `ResultsPage.tsx` renders an inline `#242426` notice strip at the top of Pane 3 (`<IconWarning />` + `t.results.disconnectedVolumesNotice(disconnectedVolumes.join(", "))` + `#323236` Refresh button `onRefresh`) indicating that indexed photos/clusters/scores on unplugged `/Volumes/<Drive>` drives remain safely preserved in SQLite until reconnected.

### Keyboard Shortcuts & Popover (`ResultsPage.tsx`)
- `ResultsPage.tsx` registers a `keydown` listener that handles `Cmd+F` / `Ctrl+F` globally (unless `isModalOpen`) and pauses single-key shortcuts when `e.target` is `INPUT`/`TEXTAREA`/`isContentEditable`, when `isModalOpen` is `true`, or when `metaKey`/`ctrlKey` is held (except `Cmd+A` / `Ctrl+A`):
  - `Cmd+F` / `Ctrl+F`: `e.preventDefault()` + focus & select Pane 2's capsule search input (`searchInputRef`)
  - `ArrowLeft` / `ArrowRight`: previous / next photo in `currentGroup`
  - `ArrowUp` / `ArrowDown`: previous / next group in `displayedGroups` (focusing its first photo)
  - `Space`: `e.preventDefault()` + toggle selection (`toggleSelectPhoto`) on `currentPhoto`
  - `1` / `2`: switch `viewLayout` between `"single"` (`Large View`) and `"grid"` (`Compare`)
  - `p` / `P` / `Enter`: open `currentPhoto` in macOS Preview
  - `f` / `F`: reveal `currentPhoto` in macOS Finder
  - `Cmd+A` / `Ctrl+A`: `e.preventDefault()` + run `handleAutoSelectCurrentTab()`
  - `Escape`: blur/clear the focused search input, close the shortcuts popover if open, or clear `searchQuery`
- Pane 3's top toolbar includes a `#2C2C2E` button (`<IconKeyboard />` + `t.results.btnShortcuts`) toggling a `bg-[#262629]/95 backdrop-blur-2xl` shortcuts reference popover in `VI` / `EN`.

### On-Demand Deep Aesthetic Scoring & Strict Score Gating (`ResultsPage.tsx`)
1. **Strict Score Gating (`kind === "similars" && aesthetic_score !== null`) & No Posture UI:**
   - Deep Aesthetic Scoring **never** runs automatically during folder scan (`handleStartScan`) or AI clustering (`handleRunAiClusterFromResults`), and **never** applies to `Exact Duplicates` (`sidebarFilter === "duplicates"`).
   - **All** score badges (`✦ aesthetic_score`, `★ quality_score`), tag pills, aesthetic bars, and technical bars (`sharpness / exposure / contrast`) are strictly gated behind `isSimPhotoScored(group.kind, photo)` (`group.kind === "similars" && photo !== undefined && photo.aesthetic_score !== null && photo.aesthetic_score !== undefined`).
   - Body posture UI and copy (`pose_score`, `metricPose`, `reasonBetterPosture`, `"limb_cropped"`, `"awkward_posture"`, `"good_posture"`) are completely removed—never render or reference body posture anywhere in Frontend.
2. **Unscored State (`Exact Duplicates` & Unscored `Similar Photos` — Largest File Size Priority):**
   - Pane 2 group rows and expanded file rows omit all score pills, showing file/group size (`formatBytes(photo.file_size)`) + `#30D158` `Giữ` / `Keep` badge on the best photo.
   - Pane 3 metadata header (`#1A1A1C`) displays `<IconCheckCircle /> {t.results.recommendedKeepBadge}` (`"Đề xuất giữ"` / `"Recommended Keep"`), appending `({t.results.reasonLargestFile})` (`"Dung lượng lớn nhất"` / `"Largest file size"`) only when `groupBestReasonKey === "largest_file"` (omitting empty parentheses on `"keep_default"`). Both the header metric bar row and Single View top-right image overlay badge are omitted when unscored.
   - Single View bottom filmstrip and Compare Grid `#1E1E20` cards omit score pills and metric bars, displaying `formatBytes(photo.file_size)` and recommended-keep badges (`{reasonLargestFile}` when `"largest_file"`, or `{recommendedKeepBadge}` on `"keep_default"`).
3. **Toolbar CTA & Discovery Strip (`Similar Photos` Only):**
   - Render the `<IconSparkles />` action button (`#5E5CE6` `Chấm điểm thẩm mỹ` / `Score Aesthetics`, switching to `#2C2C2E` `Chấm lại thẩm mỹ` / `Re-score Aesthetics` once scored) in Pane 3's top toolbar **only** when `sidebarFilter === "similars"` and `unifiedSimGroups.length > 0`.
   - When AI similar clusters have not yet been scored (`!unifiedSimGroups.some(g => g.hasAestheticScores)`), display a `#242426` inline discovery strip inviting the user to score similar photos for **face & closed eyes, camera tilt/composition, and sharpness/quality** (zero mention of posture).
   - Clicking invokes `POST /api/v1/cluster/aesthetic-score` via `handleRunAestheticScore` (`scanStep = "scoring_aesthetics"`, `progress.phase = "aesthetic_scoring"` with `t.scanning.badgeAesthetics` on `ScanningPage`), reloads cluster data, shows a `GlassToast`, and returns directly to `sidebarFilter = "similars"`.
4. **Scored `Similar Photos` State (`kind === "similars" && aesthetic_score !== null`):**
   - Display `✦ aesthetic_score` alongside technical `★ quality_score` across Pane 2's group list, Pane 3's `#1A1A1C` header (`<IconSparkles /> {t.results.bestPhotoBadge} ({groupBestReasonText})`) & Single View top-right overlay, filmstrip, and Compare Grid cards.
   - Render color-coded badge pills (`<IconWarning />` / `<IconCheckCircle />`) for the **7 active canonical `aesthetic_tags`**:
     - **Warning tags (rose/amber):** `"eyes_closed"`, `"face_blurry"`, `"tilted_horizon"` (appending `tiltDeg` degrees when `Math.abs(tilt_angle) >= 1.8`), `"edge_subject"`.
     - **Positive tags (emerald/sky):** `"eyes_open_sharp"`, `"level_horizon"`, `"rule_of_thirds"`.
   - Render mini progress bars for `metricComposition` (`#5E5CE6`) and, when non-null, `metricFace` (`#FF453A` when `has_closed_eyes`, else `#30D158`; never `metricPose`), plus technical bars (`sharpness`, `exposure`, `contrast`) in Compare Grid cards and the Single View header.
   - `getBestPhotoReasonKey(best, runnerUp, kind)` (`frontend/src/utils/photoHelpers.ts`) surfaces scored cluster reasons (`"eyes_open"`, `"level_camera"`, `"face_sharp"` -> `t.results.reasonFaceSharp` `"Khuôn mặt rõ nét hơn"` / `"Sharper face"`, `"better_composition"`, `"sharpest"`, `"best_aesthetics"`), and strictly returns `"largest_file"` (`t.results.reasonLargestFile`) or `"keep_default"` (never checking scores/resolution) for `duplicates` and unscored `similars`.

---

## 2. Internationalization (`VI` ⇄ `EN`) Rules

i18n lives in `frontend/src/i18n/` with zero external runtime dependencies:
- `translations.ts`: Defines `Language = "vi" | "en"`, `CanonicalAestheticTag` (7 active tags: `"eyes_closed" | "face_blurry" | "tilted_horizon" | "edge_subject" | "eyes_open_sharp" | "level_horizon" | "rule_of_thirds"`), `STORAGE_KEY = "uniphoto_lang"`, default dictionary `vi`, and `en: Translations` (TypeScript enforces 100% key and function-signature parity between `vi` and `en`, including sidebar/master-list labels, `shortcutSearchFocus` (`⌘F`), Trash confirmation/toast copy, drag-drop hints, `recommendedKeepBadge`, `reasonLargestFile`, and `reasonFaceSharp`, with no `metricPose` or `reasonBetterPosture`).
- `I18nContext.tsx`: Provides `useI18n()` returning `{ lang, setLang, toggleLang, t, formatBytes }`. Automatically updates:
  - `localStorage.getItem("uniphoto_lang")`
  - `document.documentElement.lang`
  - `document.title` and native macOS window title via `getCurrentWindow().setTitle(...)` (enabled by `"core:window:allow-set-title"` in `src-tauri/capabilities/default.json`).
- `LanguageSwitcher.tsx`: Present on all screens (`App.tsx` boot screen, `HomePage`, `ScanningPage`, and `ResultsPage` sidebar footer).

### Rules When Adding or Editing Text
1. **Never hardcode Vietnamese or English UI strings** inside JSX or state variables.
2. **Store state keys, not translated strings:** Just like `scanStep: ScanStepKey` (`"idle" | "resetting" | "scanning_dups" | "clustering_ai" | "scoring_aesthetics"`) in `App.tsx`, store enum/tag keys (such as canonical `aesthetic_tags` and `BestReasonKey`) in state/data and derive display text via `useMemo` + `t` so switching `VI ⇄ EN` mid-operation updates every visible label immediately.
3. **Format sizes & degrees via `useI18n()` / `translations.ts`:** Use `formatBytes(bytes)` (comma decimals in Vietnamese `119,6 MB`, dot decimals in English `119.6 MB`) and parameterized helpers like `t.results.tiltDeg(deg)` (`Lệch 6.5°` / `Tilt 6.5°`).
4. **Backend Progress Strings:** Whenever `scanner.py`, `ai_engine.py`, or `aesthetic_scorer.py` emits a status message in `current_file` (including `"Hoàn tất chấm điểm thẩm mỹ AI"`, `"Đã dừng quét thư mục"`, `"Đã dừng gom cụm AI"`, and `"Đã dừng chấm điểm thẩm mỹ AI"`), register its English mapping in `BACKEND_STATUS_EN_MAP` in `translations.ts`.
