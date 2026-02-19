#!/usr/bin/env bash
# Start the full Brainshape dev environment: Python server + Tauri frontend
# Usage: ./scripts/dev.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
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
echo "Starting Python server on :8765..."
cd "$ROOT"
uv run python -m brainshape.server --reload &
PIDS+=($!)

# Wait for server to be healthy
echo "Waiting for server..."
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8765/health >/dev/null 2>&1; then
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
echo "  Python server: http://127.0.0.1:8765"
echo "  Press Ctrl+C to stop all"
echo ""

wait
