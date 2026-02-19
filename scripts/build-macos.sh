#!/usr/bin/env bash
# Build Brainshape as a standalone macOS app.
#
# Usage:
#   ./scripts/build-macos.sh          # Apple Silicon (arm64)
#   ./scripts/build-macos.sh x86_64   # Intel
#
# Produces a .dmg in desktop/src-tauri/target/release/bundle/dmg/

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARCH="${1:-arm64}"

case "$ARCH" in
  arm64)  TARGET="aarch64-apple-darwin" ;;
  x86_64) TARGET="x86_64-apple-darwin" ;;
  *)
    echo "Unknown architecture: $ARCH (use arm64 or x86_64)"
    exit 1
    ;;
esac

echo "=== Building Brainshape for macOS ($ARCH) ==="
echo ""

# 1. Build Python sidecar with PyInstaller
echo "Step 1/3: Building Python sidecar..."
cd "$ROOT"
uv run pyinstaller brainshape.spec --noconfirm --clean 2>&1 | tail -5

SIDECAR="$ROOT/dist/brainshape-server"
if [ ! -f "$SIDECAR" ]; then
  echo "ERROR: PyInstaller did not produce dist/brainshape-server"
  exit 1
fi
echo "  Sidecar built: $(du -h "$SIDECAR" | cut -f1)"

# 2. Copy sidecar to Tauri binaries directory with platform suffix
echo "Step 2/3: Copying sidecar to Tauri binaries..."
TAURI_BIN="$ROOT/desktop/src-tauri/binaries"
mkdir -p "$TAURI_BIN"
cp "$SIDECAR" "$TAURI_BIN/brainshape-server-$TARGET"
chmod +x "$TAURI_BIN/brainshape-server-$TARGET"

# 3. Build Tauri app
echo "Step 3/3: Building Tauri app..."
cd "$ROOT/desktop"
npm run tauri build 2>&1 | tail -10

echo ""
echo "=== Build complete ==="
echo "Output: desktop/src-tauri/target/release/bundle/"
ls -lh "$ROOT/desktop/src-tauri/target/release/bundle/dmg/"*.dmg 2>/dev/null || echo "(no .dmg found — check build output above)"
