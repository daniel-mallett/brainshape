#!/usr/bin/env bash
# Set up the Brainshape development environment.
#
# Checks prerequisites, installs Python + Node dependencies,
# copies .env.example, and installs pre-commit hooks.
#
# Usage: ./scripts/setup.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }

echo "=== Brainshape Development Setup ==="
echo ""

# --- Check prerequisites ---
echo "Checking prerequisites..."
ERRORS=0

# Python 3.13
if command -v python3 &>/dev/null; then
  PY_VERSION=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
  if [[ "$PY_VERSION" == "3.13" ]]; then
    ok "Python $PY_VERSION"
  else
    fail "Python $PY_VERSION found, need 3.13 — https://www.python.org/"
    ERRORS=$((ERRORS + 1))
  fi
else
  fail "Python 3 not found — https://www.python.org/"
  ERRORS=$((ERRORS + 1))
fi

# uv
if command -v uv &>/dev/null; then
  ok "uv $(uv --version 2>&1 | head -1)"
else
  fail "uv not found — https://docs.astral.sh/uv/"
  ERRORS=$((ERRORS + 1))
fi

# Node.js
if command -v node &>/dev/null; then
  NODE_MAJOR=$(node --version | grep -oE '^v([0-9]+)' | tr -d 'v')
  if [[ "$NODE_MAJOR" -ge 20 ]]; then
    ok "Node.js $(node --version)"
  else
    fail "Node.js $(node --version) found, need 20+ — https://nodejs.org/"
    ERRORS=$((ERRORS + 1))
  fi
else
  fail "Node.js not found — https://nodejs.org/"
  ERRORS=$((ERRORS + 1))
fi

# Rust
if command -v cargo &>/dev/null; then
  ok "Rust $(rustc --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
else
  fail "Rust/Cargo not found — https://rustup.rs/"
  ERRORS=$((ERRORS + 1))
fi

if [[ $ERRORS -gt 0 ]]; then
  echo ""
  echo "Install the missing tool(s) above and re-run this script."
  exit 1
fi

echo ""

# --- Install dependencies ---
echo "Installing Python dependencies..."
cd "$ROOT"
uv sync
ok "Python dependencies"

echo ""
echo "Installing desktop frontend dependencies..."
cd "$ROOT/desktop"
npm install
ok "Frontend dependencies"

echo ""

# --- Environment file ---
cd "$ROOT"
if [[ ! -f .env ]]; then
  cp .env.example .env
  warn ".env created from .env.example — edit it to set ANTHROPIC_API_KEY and NOTES_PATH"
else
  ok ".env already exists"
fi

# --- Pre-commit hooks ---
echo ""
echo "Installing pre-commit hooks..."
cd "$ROOT"
uv run pre-commit install
ok "Pre-commit hooks"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env to set ANTHROPIC_API_KEY and NOTES_PATH"
echo "  2. Run: ./scripts/dev.sh"
