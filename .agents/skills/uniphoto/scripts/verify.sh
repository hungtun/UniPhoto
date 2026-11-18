#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
CheckTauri=false

if [[ "${1:-}" == "--tauri" ]]; then
  CheckTauri=true
fi

echo "==> [1/4] Checking Python backend syntax & imports..."
"$ROOT_DIR/.venv/bin/python" -m compileall -q "$ROOT_DIR/app" "$ROOT_DIR/run.py" "$ROOT_DIR/tests"
"$ROOT_DIR/.venv/bin/python" -c "import app.main; print('    FastAPI app imported successfully:', app.main.app.title)"

echo "==> [2/4] Running isolated Python unit test suite..."
"$ROOT_DIR/.venv/bin/python" -m unittest discover -s "$ROOT_DIR/tests" -p "test_*.py"

echo "==> [3/4] Checking Frontend TypeScript (tsc) & Vite production bundle..."
npm --prefix "$ROOT_DIR/frontend" run build

if [[ "$CheckTauri" == "true" ]]; then
  echo "==> [4/4] Checking Rust / Tauri crate & capabilities (cargo check)..."
  cargo check --manifest-path "$ROOT_DIR/frontend/src-tauri/Cargo.toml"
else
  echo "==> [4/4] Skipping cargo check (pass --tauri if src-tauri changed)."
fi

echo "✅ UniPhoto verification passed!"
