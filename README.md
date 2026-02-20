# Brainshape

[![CI](https://github.com/daniel-mallett/brainshape/actions/workflows/ci.yml/badge.svg)](https://github.com/daniel-mallett/brainshape/actions/workflows/ci.yml)

A personal second-brain agent with knowledge graph memory. Brainshape connects your markdown notes to a SurrealDB embedded knowledge graph, enabling an AI agent to read, search, create, and edit notes while building its own persistent memory over time.

## Features

- **Markdown notes** with wikilinks (`[[Note]]`), tags (`#topic`), and YAML frontmatter
- **Knowledge graph** powered by SurrealDB embedded — structural (tags, wikilinks) and semantic (vector embeddings) connections, zero infrastructure required
- **AI agent** with 9 tools — search, semantic search, read, create, edit notes, query graph, find related, store memory, create connections
- **Vector search** for semantic discovery using local sentence-transformers embeddings
- **Desktop app** (Tauri 2 + React) with three-mode editor (edit/inline/preview), chat, graph visualization, search, and memory panel
- **Voice transcription** via local mlx-whisper, OpenAI Whisper, or Mistral Voxtral
- **Meeting recorder** that transcribes audio and saves timestamped notes
- **MCP server** exposing all tools to external agents (Claude Code, etc.)
- **Claude Code provider** — use your Claude Code subscription as the LLM backend (no separate API key needed)
- **Auto-sync** on file changes with debounced structural + semantic sync
- **Trash system** with restore — deleted notes are recoverable
- **Note rename** with automatic wikilink rewriting across all notes
- **Obsidian vault import** preserving folder structure
- **Theme engine** with 12 built-in themes (6 light/dark pairs) and full color customization
- **Command palette** (Cmd+K) for quick note search and actions
- **Search** with keyword (BM25) and semantic (vector) modes, tag filtering

## Prerequisites

- **Python 3.13+** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** for Python dependency management
- **Node.js 22+** and npm (see `.nvmrc`)
- **Rust** and Cargo (for Tauri shell)

No Docker or external database required — SurrealDB runs embedded in the Python process.

## Quick Start

```bash
# 1. Clone and set up (checks prerequisites, installs all dependencies)
git clone https://github.com/daniel-mallett/brainshape.git
cd brainshape
./scripts/setup.sh

# 2. Edit .env to set ANTHROPIC_API_KEY and NOTES_PATH
$EDITOR .env

# 3. Start everything (server + desktop app)
./scripts/dev.sh
```

Press Ctrl+C to stop all processes.

## Configuration

### Environment Variables (`.env`)

```bash
ANTHROPIC_API_KEY=sk-ant-...          # Required for default LLM
NOTES_PATH=~/Brainshape                # Your notes directory
SURREALDB_PATH=~/.config/brainshape/surrealdb  # Database storage (optional)
```

### LLM Provider

Brainshape supports four LLM providers, configurable via the Settings UI:

| Provider | API Key | Default Model |
|----------|---------|---------------|
| **Anthropic** (default) | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` |
| **OpenAI** | `OPENAI_API_KEY` | `gpt-4o` |
| **Ollama** (local) | None needed | `llama3.1` |
| **Claude Code** | None (uses subscription) | Via `claude` CLI |

For Ollama: install from [ollama.ai](https://ollama.ai), pull a model (`ollama pull llama3.1`), then switch provider in Settings.

For Claude Code: install the [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code), then switch provider in Settings. Brainshape connects via MCP stdio transport — no API key needed.

### Embedding Model

Default: `sentence-transformers/all-mpnet-base-v2` (768 dimensions, ungated — no HuggingFace login required). Change via Settings UI. Changing the model triggers automatic vector index migration on next sync.

### Transcription

| Provider | Requirements | Model |
|----------|-------------|-------|
| **local** | Apple Silicon Mac | `mlx-community/whisper-small` |
| **openai** | `OPENAI_API_KEY` | `gpt-4o-mini-transcribe` |
| **mistral** | `MISTRAL_API_KEY` | `voxtral-mini-latest` |

See [docs/configuration.md](docs/configuration.md) for full configuration reference.

## Usage

### Standalone Modes

```bash
# CLI chat
uv run main.py

# Server only (API on port 52836)
uv run python -m brainshape.server

# Desktop app (requires server running)
cd desktop && npm run tauri dev

# Batch sync (for cron/launchd)
uv run python -m brainshape.batch           # semantic sync
uv run python -m brainshape.batch --structural
uv run python -m brainshape.batch --full
```

### MCP Server

Expose Brainshape tools to external agents:

```bash
# Stdio transport (for Claude Code)
uv run python -m brainshape.mcp_server

# HTTP transport — automatically available at /mcp when running brainshape.server
```

## Development

### First-time setup

```bash
./scripts/setup.sh
```

This checks prerequisites, installs Python and Node dependencies, copies `.env.example`, and installs pre-commit hooks.

### Common commands

```bash
uv run pytest                    # Run tests
uv run pytest -v                 # Verbose
uv run ruff check                # Lint
uv run ruff check --fix          # Auto-fix
uv run ty check                  # Type check (Python)
cd desktop && npx tsc --noEmit   # Type check (TypeScript)
```

## Architecture

```
brainshape/               # Python backend
  server.py               # FastAPI (HTTP + SSE)
  agent.py                # LangChain agent factory
  tools.py                # 9 agent tools
  notes.py                # Notes reader/writer/parser + trash + rename
  graph_db.py             # SurrealDB embedded wrapper
  kg_pipeline.py          # Embedding pipeline (load → split → embed → write)
  sync.py                 # Structural + semantic sync
  settings.py             # Runtime settings (JSON on disk)
  config.py               # Env-based secrets (pydantic-settings)
  claude_code.py          # Claude Code CLI provider
  mcp_client.py           # External MCP server client
  mcp_server.py           # MCP server (stdio + HTTP)
  watcher.py              # File watcher for auto-sync
  transcribe.py           # Voice transcription providers
  cli.py                  # Interactive CLI chat loop
  batch.py                # Batch sync for cron/launchd

desktop/                  # Tauri 2 + React + TypeScript
  src/components/         # Editor, Chat, Sidebar, Settings, Graph, Memory, Search
  src/lib/                # API client, themes, editor extensions
  src-tauri/              # Rust shell
```

See [CLAUDE.md](CLAUDE.md) for the full codebase guide and [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.
