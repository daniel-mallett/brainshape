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

# 1. Build Python sidecar with PyInstaller (onedir mode)
echo "Step 1/3: Building Python sidecar..."
cd "$ROOT"
uv run pyinstaller brainshape.spec --noconfirm --clean 2>&1 | tail -5

SIDECAR_DIR="$ROOT/dist/brainshape-server"
SIDECAR_EXE="$SIDECAR_DIR/brainshape-server"
if [ ! -f "$SIDECAR_EXE" ]; then
  echo "ERROR: PyInstaller did not produce dist/brainshape-server/"
  exit 1
fi
echo "  Sidecar built: $(du -sh "$SIDECAR_DIR" | cut -f1)"

# Smoke-test the sidecar (--help triggers argparse + top-level imports, then exits)
echo "  Smoke-testing sidecar..."
if ! "$SIDECAR_EXE" --help >/dev/null 2>&1; then
  echo "ERROR: Sidecar smoke test failed. Run directly to see the error:"
  echo "  $SIDECAR_EXE --help"
  exit 1
fi
echo "  Smoke test passed."

# 2. Copy sidecar directory to Tauri resources
echo "Step 2/3: Copying sidecar to Tauri resources..."
TAURI_RES="$ROOT/desktop/src-tauri/resources"
mkdir -p "$TAURI_RES"
rm -rf "$TAURI_RES/brainshape-server"
# -RL: dereference symlinks (Tauri resource bundler can't handle symlinks)
cp -RL "$SIDECAR_DIR" "$TAURI_RES/brainshape-server"
chmod +x "$TAURI_RES/brainshape-server/brainshape-server"

# 3. Build Tauri app (.app bundle only — DMG created separately due to large size)
echo "Step 3/3: Building Tauri app..."
cd "$ROOT/desktop"
npm run tauri build -- --bundles app 2>&1 | tail -10

APP_BUNDLE="$ROOT/desktop/src-tauri/target/release/bundle/macos/Brainshape.app"
if [ ! -d "$APP_BUNDLE" ]; then
  echo "ERROR: Tauri did not produce Brainshape.app"
  exit 1
fi

# 4. Create DMG (with Applications shortcut for drag-to-install)
echo "Step 4: Creating DMG..."
DMG_DIR="$ROOT/desktop/src-tauri/target/release/bundle/dmg"
DMG_PATH="$DMG_DIR/Brainshape_${VERSION:-0.1.0}_$TARGET.dmg"
mkdir -p "$DMG_DIR"
rm -f "$DMG_PATH"
DMG_STAGING="$(mktemp -d)"
cp -R "$APP_BUNDLE" "$DMG_STAGING/"
ln -s /Applications "$DMG_STAGING/Applications"
hdiutil create -volname "Brainshape" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_PATH" 2>&1 | tail -3
rm -rf "$DMG_STAGING"

echo ""
echo "=== Build complete ==="
echo "Output:"
ls -lh "$DMG_PATH" 2>/dev/null || echo "(no .dmg found — check build output above)"
