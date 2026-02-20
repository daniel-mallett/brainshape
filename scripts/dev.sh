#!/usr/bin/env bash
# Start the full Brainshape dev environment: Python server + Tauri frontend
# Usage: ./scripts/dev.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- Prerequisite checks ---
missing=()
command -v uv    &>/dev/null || missing+=("uv (https://docs.astral.sh/uv/)")
command -v node  &>/dev/null || missing+=("node (https://nodejs.org/)")
command -v cargo &>/dev/null || missing+=("cargo (https://rustup.rs/)")

if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Missing required tools:"
  for m in "${missing[@]}"; do
    echo "  - $m"
  done
  echo ""
  echo "Run ./scripts/setup.sh after installing prerequisites."
  exit 1
fi

if [[ ! -d "$ROOT/desktop/node_modules" ]]; then
  echo "Desktop frontend dependencies not installed."
  echo "Run: ./scripts/setup.sh"
  exit 1
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "Python virtual environment not found."
  echo "Run: ./scripts/setup.sh"
  exit 1
fi

PIDS=()

cleanup() {
  echo ""
  echo "Shutting down..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# 1. Start Python FastAPI server
echo "Starting Python server on :52836..."
cd "$ROOT"
uv run python -m brainshape.server --reload &
PIDS+=($!)

# Wait for server to be healthy
echo "Waiting for server..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:52836/health >/dev/null 2>&1; then
    echo "Server ready."
    break
  fi
  sleep 1
done

# 2. Start Tauri dev (frontend + native window)
echo "Starting Tauri dev..."
cd "$ROOT/desktop"
npm run tauri dev &
PIDS+=($!)

echo ""
echo "=== Brainshape dev environment running ==="
echo "  Python server: http://127.0.0.1:52836"
echo "  Press Ctrl+C to stop all"
echo ""

wait
