#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# UniPhoto — Slim Standalone macOS .app, .dmg & .zip One-Command Builder
# ==============================================================================
# Bundles:
#   1. Validated build toolchain (auto-resolving Node.js ^20.19.0 || >=22.12.0)
#   2. Offline AI model weights (MobileNetV2 .onnx + MediaPipe face_landmarker.task)
#   3. Slim Python FastAPI + OpenCV DNN + MediaPipe sidecar via PyInstaller --onedir
#      (zero torch/scipy/matplotlib; reused when up-to-date or --rebuild-backend)
#   4. Fail-fast React 19 / Vite 8 build + Tauri v2 macOS UniPhoto.app (--bundles app)
#      with symlink-preserving rsync (-a --delete) into Contents/Resources/
#   5. Strip + ad-hoc deep macOS code signing + in-bundle --self-test + .dmg & .zip
# ==============================================================================

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
BUILD_DIR="$ROOT_DIR/build"
MODELS_OUT_DIR="$BUILD_DIR/bundled-models"
PYI_DIST_DIR="$BUILD_DIR/pyinstaller"
PYI_WORK_DIR="$BUILD_DIR/pyinstaller-work"
PYI_CACHE_DIR="$BUILD_DIR/pyinstaller-cache"
BACKEND_BIN="$PYI_DIST_DIR/uniphoto-backend/uniphoto-backend"
SPEC_FILE="$ROOT_DIR/uniphoto_backend.spec"
RTH_STUB_FILE="$ROOT_DIR/scripts/pyi_rth_stub_unused.py"

REBUILD_BACKEND=false
CHECK_ENV_ONLY=false

usage() {
  cat <<'EOF'
Usage: bash scripts/build_macos_app.sh [OPTIONS]

Options:
  --rebuild-backend   Force a clean PyInstaller rebuild of uniphoto-backend
  --check-env         Verify build prerequisites & Node.js compatibility, then exit
  -h, --help          Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rebuild-backend)
      REBUILD_BACKEND=true
      shift
      ;;
    --check-env)
      CHECK_ENV_ONLY=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SMOKE_PID=""
SMOKE_DATA_DIR=""
SMOKE_LOG=""
DMG_STAGE_DIR=""

cleanup() {
  if [[ -n "$SMOKE_PID" ]] && kill -0 "$SMOKE_PID" 2>/dev/null; then
    kill "$SMOKE_PID" 2>/dev/null || true
    wait "$SMOKE_PID" 2>/dev/null || true
  fi
  if [[ -n "$SMOKE_DATA_DIR" && -d "$SMOKE_DATA_DIR" ]]; then
    rm -rf "$SMOKE_DATA_DIR"
  fi
  if [[ -n "$SMOKE_LOG" && -f "$SMOKE_LOG" ]]; then
    rm -f "$SMOKE_LOG"
  fi
  if [[ -n "$DMG_STAGE_DIR" && -d "$DMG_STAGE_DIR" ]]; then
    rm -rf "$DMG_STAGE_DIR"
  fi
}
trap cleanup EXIT

is_compatible_node() {
  local node_bin="$1"
  [[ -x "$node_bin" ]] || return 1

  local ver_raw=""
  ver_raw="$("$node_bin" -v 2>/dev/null || "$node_bin" --version 2>/dev/null || true)"
  local ver="${ver_raw#v}"

  if [[ ! "$ver" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
    return 1
  fi

  local major="${BASH_REMATCH[1]}"
  local minor="${BASH_REMATCH[2]}"

  # Vite 8 requires Node.js ^20.19.0 || >=22.12.0
  if (( 10#$major > 22 )) || (( 10#$major == 22 && 10#$minor >= 12 )) || (( 10#$major == 20 && 10#$minor >= 19 )); then
    return 0
  fi
  return 1
}

ensure_compatible_node() {
  local current_node=""
  current_node="$(command -v node 2>/dev/null || true)"
  if [[ -n "$current_node" ]]; then
    local current_dir
    current_dir="$(dirname "$current_node")"
    if [[ -x "$current_dir/npm" ]] && is_compatible_node "$current_node"; then
      export PATH="$current_dir:$PATH"
      hash -r 2>/dev/null || true
      echo "    Using compatible Node.js $(node -v) from $current_dir"
      return 0
    fi
    local current_ver
    current_ver="$("$current_node" -v 2>/dev/null || echo "unknown")"
    echo "    Current node ($current_node -> $current_ver) does not satisfy Vite 8 (^20.19.0 || >=22.12.0); searching for a compatible Node.js..."
  else
    echo "    node not found in current PATH; searching standard macOS locations..."
  fi

  local candidate_dirs=(
    "/opt/homebrew/bin"
    "/opt/homebrew/opt/node/bin"
    "/opt/homebrew/opt/node@22/bin"
    "/opt/homebrew/opt/node@24/bin"
    "/opt/homebrew/opt/node@20/bin"
    "/usr/local/bin"
  )

  local nvm_root="${NVM_DIR:-$HOME/.nvm}"
  if [[ -d "$nvm_root/versions/node" ]]; then
    local nvm_dir
    while IFS= read -r nvm_dir; do
      [[ -n "$nvm_dir" ]] && candidate_dirs+=("$nvm_dir/bin")
    done < <(find "$nvm_root/versions/node" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) -name "v*" 2>/dev/null | sort -V -r 2>/dev/null || true)
  fi
  if [[ "$nvm_root" != "$HOME/.nvm" && -d "$HOME/.nvm/versions/node" ]]; then
    local home_nvm_dir
    while IFS= read -r home_nvm_dir; do
      [[ -n "$home_nvm_dir" ]] && candidate_dirs+=("$home_nvm_dir/bin")
    done < <(find "$HOME/.nvm/versions/node" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) -name "v*" 2>/dev/null | sort -V -r 2>/dev/null || true)
  fi

  candidate_dirs+=(
    "$HOME/.volta/bin"
    "$HOME/.fnm/current/bin"
    "$HOME/Library/Application Support/fnm/aliases/default/bin"
    "$HOME/.asdf/shims"
  )

  local cand_dir
  for cand_dir in "${candidate_dirs[@]}"; do
    if [[ -x "$cand_dir/node" && -x "$cand_dir/npm" ]] && is_compatible_node "$cand_dir/node"; then
      export PATH="$cand_dir:$PATH"
      hash -r 2>/dev/null || true
      echo "    Using compatible Node.js $(node -v) from $cand_dir"
      return 0
    fi
  done

  echo "ERROR: No compatible Node.js binary (^20.19.0 || >=22.12.0) was found on this Mac." >&2
  echo "       Install and activate Node.js 22 LTS, then re-run:" >&2
  echo "         nvm install 22 && nvm use 22" >&2
  echo "       (or via Homebrew: brew install node@22)" >&2
  exit 1
}

echo "==> [1/5] Checking build prerequisites (.venv Python, PyInstaller, Node/npm, Rust/Cargo)..."
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "ERROR: Python virtualenv not found at $VENV_PYTHON" >&2
  echo "       Create it first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

ensure_compatible_node

if ! command -v cargo >/dev/null 2>&1 && [[ -x "$HOME/.cargo/bin/cargo" ]]; then
  export PATH="$HOME/.cargo/bin:$PATH"
  hash -r 2>/dev/null || true
fi

for tool in node npm cargo codesign curl rsync; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: Required command '$tool' is not installed or not in PATH." >&2
    exit 1
  fi
done

if ! "$VENV_PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "    PyInstaller not found in .venv — installing pyinstaller..."
  "$VENV_PYTHON" -m pip install pyinstaller
fi

if [[ "$CHECK_ENV_ONLY" == "true" ]]; then
  echo "    Environment check passed (node=$(command -v node) $(node -v), npm=$(command -v npm) $(npm -v), cargo=$(command -v cargo))."
  exit 0
fi

if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  echo "    Installing frontend npm dependencies..."
  npm --prefix "$ROOT_DIR/frontend" install
fi

echo "==> [2/5] Preparing offline bundled AI models in $MODELS_OUT_DIR..."
mkdir -p "$MODELS_OUT_DIR"
rm -f "$MODELS_OUT_DIR/mobilenet_v2.pth"

FACE_TASK_SRC="$ROOT_DIR/data/models/face_landmarker.task"
FACE_TASK_DST="$MODELS_OUT_DIR/face_landmarker.task"
FACE_TASK_URL="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

if [[ -f "$FACE_TASK_SRC" ]] && [[ $(wc -c <"$FACE_TASK_SRC") -gt 10000 ]]; then
  cp -f "$FACE_TASK_SRC" "$FACE_TASK_DST"
  echo "    Copied local face_landmarker.task ($(du -h "$FACE_TASK_DST" | cut -f1))"
elif [[ -f "$FACE_TASK_DST" ]] && [[ $(wc -c <"$FACE_TASK_DST") -gt 10000 ]]; then
  echo "    Reusing existing $FACE_TASK_DST"
else
  echo "    Downloading face_landmarker.task from Google MediaPipe storage..."
  curl -fL "$FACE_TASK_URL" -o "$FACE_TASK_DST"
fi

MOBILENET_ONNX_SRC="$ROOT_DIR/data/models/mobilenet_v2.onnx"
MOBILENET_ONNX_DST="$MODELS_OUT_DIR/mobilenet_v2.onnx"

if [[ -f "$MOBILENET_ONNX_SRC" ]] && [[ $(wc -c <"$MOBILENET_ONNX_SRC") -gt 1000000 ]]; then
  cp -f "$MOBILENET_ONNX_SRC" "$MOBILENET_ONNX_DST"
  echo "    Copied local mobilenet_v2.onnx ($(du -h "$MOBILENET_ONNX_DST" | cut -f1))"
elif [[ -f "$MOBILENET_ONNX_DST" ]] && [[ $(wc -c <"$MOBILENET_ONNX_DST") -gt 1000000 ]]; then
  echo "    Reusing existing $MOBILENET_ONNX_DST"
else
  echo "    Exporting & validating mobilenet_v2.onnx via scripts/export_mobilenet_v2_onnx.py..."
  "$VENV_PYTHON" "$ROOT_DIR/scripts/export_mobilenet_v2_onnx.py"
fi

echo "==> [3/5] Preparing slim standalone Python backend via PyInstaller (--onedir)..."
NEED_PYI_BUILD=true
if [[ "$REBUILD_BACKEND" == "true" ]]; then
  echo "    --rebuild-backend specified; forcing clean PyInstaller build..."
elif [[ -x "$BACKEND_BIN" ]] \
  && [[ ! "$ROOT_DIR/run.py" -nt "$BACKEND_BIN" ]] \
  && [[ ! "$SPEC_FILE" -nt "$BACKEND_BIN" ]] \
  && [[ ! "$RTH_STUB_FILE" -nt "$BACKEND_BIN" ]] \
  && [[ ! "$ROOT_DIR/requirements.txt" -nt "$BACKEND_BIN" ]] \
  && [[ -z "$(find "$ROOT_DIR/app" -name "*.py" -newer "$BACKEND_BIN" -print -quit 2>/dev/null)" ]]; then
  NEED_PYI_BUILD=false
fi

if [[ "$NEED_PYI_BUILD" == "true" ]]; then
  rm -rf "$PYI_DIST_DIR/uniphoto-backend" "$PYI_WORK_DIR"
  MPLCONFIGDIR="/tmp/uniphoto-mpl" \
  PYINSTALLER_CONFIG_DIR="$PYI_CACHE_DIR" \
  "$VENV_PYTHON" -m PyInstaller \
    --distpath "$PYI_DIST_DIR" \
    --workpath "$PYI_WORK_DIR" \
    --noconfirm \
    "$SPEC_FILE"

  # Deduplicate any byte-identical regular .dylib copies across _internal subdirectories via relative symlinks
  INTERNAL_DIR="$PYI_DIST_DIR/uniphoto-backend/_internal" \
  "$VENV_PYTHON" - <<'PY'
import hashlib
import os
from pathlib import Path

internal = Path(os.environ["INTERNAL_DIR"])
if internal.is_dir():
    by_hash: dict[tuple[int, str], Path] = {}
    deduped_bytes = 0
    deduped_count = 0
    for path in sorted(internal.rglob("*.dylib")):
        if path.is_symlink() or not path.is_file():
            continue
        size = path.stat().st_size
        if size < 4096:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        key = (size, digest)
        canonical = by_hash.get(key)
        if canonical is None:
            by_hash[key] = path
        else:
            rel_target = os.path.relpath(canonical, start=path.parent)
            path.unlink()
            path.symlink_to(rel_target)
            deduped_bytes += size
            deduped_count += 1
    if deduped_count > 0:
        print(
            f"    Deduplicated {deduped_count} identical .dylib files "
            f"(-{deduped_bytes / (1024 * 1024):.1f} MB)"
        )
PY

  if command -v strip >/dev/null 2>&1; then
    echo "    Stripping local debug symbols from PyInstaller native extensions..."
    while IFS= read -r -d '' mach_file; do
      strip -x "$mach_file" 2>/dev/null || true
      codesign --force --sign - "$mach_file" >/dev/null 2>&1 || true
    done < <(find "$PYI_DIST_DIR/uniphoto-backend" -type f \( -name "*.so" -o -name "*.dylib" -o -name "Python" \) -print0)
    codesign --force --sign - "$BACKEND_BIN" >/dev/null 2>&1 || true
  fi
else
  echo "    Reusing up-to-date PyInstaller bundle at $BACKEND_BIN (pass --rebuild-backend to force)"
fi

if [[ ! -x "$BACKEND_BIN" ]]; then
  echo "ERROR: Expected PyInstaller binary not found at $BACKEND_BIN" >&2
  exit 1
fi

echo "    PyInstaller sidecar size: $(du -sh "$PYI_DIST_DIR/uniphoto-backend" | cut -f1)"

echo "    Verifying packaged backend imports & offline AI models (--self-test)..."
SMOKE_DATA_DIR="$(mktemp -d /tmp/uniphoto-smoke.XXXXXX)"
SMOKE_LOG="$(mktemp /tmp/uniphoto-smoke-log.XXXXXX)"

if ! HOST="127.0.0.1" \
  PORT="8000" \
  DEBUG="False" \
  UNIPHOTO_PACKAGED="1" \
  UNIPHOTO_DATA_DIR="$SMOKE_DATA_DIR" \
  UNIPHOTO_MODELS_DIR="$MODELS_OUT_DIR" \
  MPLCONFIGDIR="/tmp/uniphoto-mpl" \
  PYTHONUNBUFFERED="1" \
  "$BACKEND_BIN" --self-test >"$SMOKE_LOG" 2>&1; then
  echo "ERROR: Packaged uniphoto-backend --self-test failed. Output:" >&2
  cat "$SMOKE_LOG" >&2 || true
  exit 1
fi

if ! grep -q "SELF_TEST_OK" "$SMOKE_LOG"; then
  echo "ERROR: Packaged uniphoto-backend --self-test did not report SELF_TEST_OK. Output:" >&2
  cat "$SMOKE_LOG" >&2 || true
  exit 1
fi
echo "    Self-test passed ($(grep -E 'APP_IMPORT_OK|SELF_TEST_OK' "$SMOKE_LOG" | tr -s '[:space:]' ' '))"

echo "    Smoke-testing packaged backend HTTP server on a temporary port..."
SMOKE_PORT_PROBE="$("$VENV_PYTHON" - <<'PY'
import errno
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        c.connect(("127.0.0.1", port))
        print(port)
    finally:
        c.close()
except OSError as exc:
    if exc.errno in (errno.EPERM, errno.EACCES):
        print("SANDBOX_RESTRICTED")
    else:
        raise
finally:
    s.close()
PY
)"

if [[ "$SMOKE_PORT_PROBE" == "SANDBOX_RESTRICTED" ]]; then
  echo "    WARN: Loopback TCP sockets restricted by sandbox; relying on passed --self-test ASGI health check."
  rm -rf "$SMOKE_DATA_DIR"
  SMOKE_DATA_DIR=""
  rm -f "$SMOKE_LOG"
  SMOKE_LOG=""
else
  SMOKE_PORT="$SMOKE_PORT_PROBE"
  : >"$SMOKE_LOG"

  HOST="127.0.0.1" \
  PORT="$SMOKE_PORT" \
  DEBUG="False" \
  UNIPHOTO_PACKAGED="1" \
  UNIPHOTO_DATA_DIR="$SMOKE_DATA_DIR" \
  UNIPHOTO_MODELS_DIR="$MODELS_OUT_DIR" \
  MPLCONFIGDIR="/tmp/uniphoto-mpl" \
  PYTHONUNBUFFERED="1" \
  "$BACKEND_BIN" >"$SMOKE_LOG" 2>&1 &
  SMOKE_PID=$!

  SMOKE_OK=false
  for _ in $(seq 1 180); do
    if ! kill -0 "$SMOKE_PID" 2>/dev/null; then
      echo "ERROR: Packaged uniphoto-backend exited unexpectedly during smoke test. Output:" >&2
      cat "$SMOKE_LOG" >&2 || true
      exit 1
    fi
    if curl --noproxy '*' -fsS "http://127.0.0.1:${SMOKE_PORT}/api/v1/health" >/dev/null 2>&1; then
      SMOKE_OK=true
      break
    fi
    sleep 0.5
  done

  kill "$SMOKE_PID" 2>/dev/null || true
  wait "$SMOKE_PID" 2>/dev/null || true
  SMOKE_PID=""

  if [[ "$SMOKE_OK" != "true" ]]; then
    echo "ERROR: Packaged uniphoto-backend did not respond on /api/v1/health within 90s. Output:" >&2
    cat "$SMOKE_LOG" >&2 || true
    exit 1
  fi

  rm -rf "$SMOKE_DATA_DIR"
  SMOKE_DATA_DIR=""
  rm -f "$SMOKE_LOG"
  SMOKE_LOG=""
  echo "    Smoke test passed (GET /api/v1/health -> 200 OK on port $SMOKE_PORT)!"
fi

echo "==> [4/5] Building frontend & Tauri macOS .app shell..."
BUNDLE_ROOT="$ROOT_DIR/frontend/src-tauri/target/release/bundle"
APP_PATH="$BUNDLE_ROOT/macos/UniPhoto.app"

echo "    Building frontend assets (tsc && vite build)..."
npm --prefix "$ROOT_DIR/frontend" run build

rm -rf "$APP_PATH"
npm --prefix "$ROOT_DIR/frontend" run tauri build -- --bundles app

if [[ ! -d "$APP_PATH" ]]; then
  echo "ERROR: UniPhoto.app bundle was not found at $APP_PATH" >&2
  exit 1
fi

echo "    Syncing slim backend & models into UniPhoto.app/Contents/Resources (preserving symlinks)..."
mkdir -p "$APP_PATH/Contents/Resources/backend" "$APP_PATH/Contents/Resources/models"
rsync -a --delete "$PYI_DIST_DIR/uniphoto-backend/" "$APP_PATH/Contents/Resources/backend/"
rsync -a --delete "$MODELS_OUT_DIR/" "$APP_PATH/Contents/Resources/models/"

if command -v strip >/dev/null 2>&1; then
  echo "    Stripping local debug symbols from native extensions inside UniPhoto.app..."
  while IFS= read -r -d '' mach_file; do
    strip -x "$mach_file" 2>/dev/null || true
  done < <(find "$APP_PATH/Contents/Resources/backend" -type f \( -name "*.so" -o -name "*.dylib" \) -print0)
fi

echo "==> [5/5] Applying ad-hoc deep code signature, verifying in-app --self-test & creating .dmg / .zip..."
# Explicitly sign Mach-O libraries inside hidden .dylibs directories before deep bundle signing
while IFS= read -r -d '' sign_target; do
  codesign --force --sign - "$sign_target" >/dev/null 2>&1 || true
done < <(find "$APP_PATH/Contents/Resources/backend" -type f \( -name "*.so" -o -name "*.dylib" -o -name "Python" \) -print0)
codesign --force --sign - "$APP_PATH/Contents/Resources/backend/uniphoto-backend" >/dev/null 2>&1 || true

codesign --force --deep --sign - "$APP_PATH"
codesign --verify --deep --strict "$APP_PATH"

echo "    Verifying signed UniPhoto.app/Contents/Resources/backend/uniphoto-backend --self-test..."
SMOKE_DATA_DIR="$(mktemp -d /tmp/uniphoto-app-smoke.XXXXXX)"
SMOKE_LOG="$(mktemp /tmp/uniphoto-app-smoke-log.XXXXXX)"

if ! HOST="127.0.0.1" \
  PORT="8000" \
  DEBUG="False" \
  UNIPHOTO_PACKAGED="1" \
  UNIPHOTO_DATA_DIR="$SMOKE_DATA_DIR" \
  UNIPHOTO_MODELS_DIR="$APP_PATH/Contents/Resources/models" \
  MPLCONFIGDIR="/tmp/uniphoto-mpl" \
  PYTHONUNBUFFERED="1" \
  "$APP_PATH/Contents/Resources/backend/uniphoto-backend" --self-test >"$SMOKE_LOG" 2>&1; then
  echo "ERROR: Signed UniPhoto.app backend --self-test failed. Output:" >&2
  cat "$SMOKE_LOG" >&2 || true
  exit 1
fi
if ! grep -q "SELF_TEST_OK" "$SMOKE_LOG"; then
  echo "ERROR: Signed UniPhoto.app backend --self-test did not report SELF_TEST_OK. Output:" >&2
  cat "$SMOKE_LOG" >&2 || true
  exit 1
fi
echo "    Signed in-app self-test passed ($(grep -E 'APP_IMPORT_OK|SELF_TEST_OK' "$SMOKE_LOG" | tr -s '[:space:]' ' '))"
rm -rf "$SMOKE_DATA_DIR"
SMOKE_DATA_DIR=""
rm -f "$SMOKE_LOG"
SMOKE_LOG=""

echo "    Final UniPhoto.app size: $(du -sh "$APP_PATH" | cut -f1)"

APP_VERSION="$("$VENV_PYTHON" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$ROOT_DIR/frontend/src-tauri/tauri.conf.json" 2>/dev/null || echo "0.1.0")"
APP_VERSION="${APP_VERSION:-0.1.0}"
RAW_ARCH="$(uname -m)"
case "$RAW_ARCH" in
  arm64|aarch64)
    ARCH_LABEL="aarch64"
    ;;
  x86_64|amd64)
    ARCH_LABEL="x64"
    ;;
  *)
    ARCH_LABEL="$RAW_ARCH"
    ;;
esac

mkdir -p "$BUNDLE_ROOT/macos"
TARGET_ZIP_PATH="$BUNDLE_ROOT/macos/UniPhoto_${APP_VERSION}_${ARCH_LABEL}.zip"
ZIP_PATH=""

if command -v ditto >/dev/null 2>&1; then
  echo "    Creating $(basename "$TARGET_ZIP_PATH") from signed UniPhoto.app..."
  rm -f "$TARGET_ZIP_PATH"
  ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$TARGET_ZIP_PATH"
  ZIP_PATH="$TARGET_ZIP_PATH"
  echo "    Final ZIP size: $(du -sh "$ZIP_PATH" | cut -f1)"
else
  echo "WARN: ditto not found in PATH; skipping .zip creation." >&2
fi

mkdir -p "$BUNDLE_ROOT/dmg"
TARGET_DMG_PATH="$BUNDLE_ROOT/dmg/UniPhoto_${APP_VERSION}_${ARCH_LABEL}.dmg"
DMG_PATH=""

if command -v hdiutil >/dev/null 2>&1; then
  echo "    Creating $(basename "$TARGET_DMG_PATH") from signed UniPhoto.app..."
  DMG_STAGE_DIR="$(mktemp -d /tmp/uniphoto-dmg-stage.XXXXXX)"
  rsync -a "$APP_PATH" "$DMG_STAGE_DIR/"
  ln -s /Applications "$DMG_STAGE_DIR/Applications"
  rm -f "$TARGET_DMG_PATH"

  HDIUTIL_OUT=""
  if HDIUTIL_OUT="$(hdiutil create \
    -volname "UniPhoto" \
    -srcfolder "$DMG_STAGE_DIR" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$TARGET_DMG_PATH" 2>&1)"; then
    DMG_PATH="$TARGET_DMG_PATH"
    codesign --force --sign - "$DMG_PATH" 2>/dev/null || true
    echo "    Final DMG size: $(du -sh "$DMG_PATH" | cut -f1)"
  else
    rm -f "$TARGET_DMG_PATH"
    if echo "$HDIUTIL_OUT" | grep -Eqi "Device not configured|Operation not permitted|Permission denied|/dev/disk|attach failed"; then
      echo "WARN: hdiutil could not attach virtual /dev/disk device (restricted sandbox environment); skipping .dmg creation. Run in a standard macOS Terminal to produce $TARGET_DMG_PATH." >&2
      DMG_PATH=""
    else
      echo "ERROR: hdiutil create failed while building $TARGET_DMG_PATH:" >&2
      echo "$HDIUTIL_OUT" >&2
      exit 1
    fi
  fi

  rm -rf "$DMG_STAGE_DIR"
  DMG_STAGE_DIR=""
else
  echo "WARN: hdiutil not found in PATH; skipping .dmg creation." >&2
fi

echo ""
echo "=============================================================================="
echo "UniPhoto macOS Standalone Build Complete! (v${APP_VERSION})"
echo "  App Bundle : $APP_PATH ($(du -sh "$APP_PATH" | cut -f1))"
if [[ -n "$DMG_PATH" ]]; then
  echo "  DMG Image  : $DMG_PATH ($(du -sh "$DMG_PATH" | cut -f1))"
fi
if [[ -n "$ZIP_PATH" ]]; then
  echo "  ZIP Archive: $ZIP_PATH ($(du -sh "$ZIP_PATH" | cut -f1))"
fi
echo ""
echo "First-launch tip on another Mac (unsigned / ad-hoc signed Gatekeeper bypass):"
echo "  xattr -cr /Applications/UniPhoto.app"
echo "=============================================================================="
