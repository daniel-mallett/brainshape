#!/usr/bin/env bash
# Start the full Brain dev environment: Neo4j + Python server + Tauri frontend
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

# 1. Start Neo4j (if not already running)
if ! docker compose -f "$ROOT/docker-compose.yml" ps --status running 2>/dev/null | grep -q neo4j; then
  echo "Starting Neo4j..."
  docker compose -f "$ROOT/docker-compose.yml" up -d
  echo "Waiting for Neo4j to be ready..."
  until docker compose -f "$ROOT/docker-compose.yml" exec -T neo4j cypher-shell -u neo4j -p brain-dev-password "RETURN 1" >/dev/null 2>&1; do
    sleep 1
  done
  echo "Neo4j ready."
else
  echo "Neo4j already running."
fi

# 2. Start Python FastAPI server
echo "Starting Python server on :8765..."
cd "$ROOT"
uv run python -m brain.server &
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

# 3. Start Tauri dev (frontend + native window)
echo "Starting Tauri dev..."
cd "$ROOT/desktop"
npm run tauri dev &
PIDS+=($!)

echo ""
echo "=== Brain dev environment running ==="
echo "  Python server: http://127.0.0.1:8765"
echo "  Neo4j browser: http://localhost:7474"
echo "  Press Ctrl+C to stop all"
echo ""

wait
