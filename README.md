# Brain

[![CI](https://github.com/daniel-mallett/brain/actions/workflows/ci.yml/badge.svg)](https://github.com/daniel-mallett/brain/actions/workflows/ci.yml)

A personal second-brain agent with knowledge graph memory. Brain connects your markdown notes to a Neo4j knowledge graph, enabling an AI agent to read, search, create, and edit notes while building its own persistent memory over time.

## Features

- **Markdown notes** with wikilinks (`[[Note]]`), tags (`#topic`), and YAML frontmatter
- **Knowledge graph** powered by Neo4j — structural (tags, wikilinks) and semantic (vector embeddings) connections
- **AI agent** with tool-based note access — search, read, create, edit, query graph, find related
- **Vector search** for semantic discovery using sentence-transformers embeddings
- **Desktop app** (Tauri 2 + React) with three-mode editor, chat, graph visualization, and memory panel
- **Voice transcription** via local mlx-whisper, OpenAI Whisper, or Mistral Voxtral
- **Meeting recorder** that transcribes audio and saves timestamped notes
- **MCP server** exposing all tools to external agents (Claude Code, etc.)
- **Auto-sync** on file changes with debounced structural + semantic sync
- **Trash system** with restore — deleted notes are recoverable
- **Note rename** with automatic wikilink rewriting across all notes
- **Obsidian vault import** preserving folder structure
- **Theme engine** with 4 built-in themes and full color customization
- **Command palette** (Cmd+K) for quick note search and actions

## Prerequisites

- **Python 3.13+** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** for Python dependency management
- **Docker** (for Neo4j)
- **Node.js 22+** and npm (see `.nvmrc`)
- **Rust** and Cargo (for Tauri shell)

## Quick Start

```bash
# 1. Clone and install dependencies
git clone https://github.com/daniel-mallett/brain.git
cd brain
uv sync
cd desktop && npm install && cd ..

# 2. Configure environment
cp .env.example .env
# Edit .env: set ANTHROPIC_API_KEY and NOTES_PATH

# 3. Start everything (Neo4j + server + desktop app)
./scripts/dev.sh
```

Press Ctrl+C to stop all processes.

## Configuration

### Environment Variables (`.env`)

```bash
ANTHROPIC_API_KEY=sk-ant-...   # Required for default LLM
NOTES_PATH=~/Brain             # Your notes directory
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=brain-dev-password
```

### LLM Provider

Brain supports three LLM providers, configurable via the Settings UI:

| Provider | API Key | Default Model |
|----------|---------|---------------|
| **Anthropic** (default) | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` |
| **OpenAI** | `OPENAI_API_KEY` | `gpt-4o` |
| **Ollama** (local) | None needed | `llama3.1` |

For Ollama: install from [ollama.ai](https://ollama.ai), pull a model (`ollama pull llama3.1`), then switch provider in Settings.

### Embedding Model

Default: `sentence-transformers/all-mpnet-base-v2` (768 dimensions, ungated — no HuggingFace login required). Change via Settings UI. Changing the model triggers automatic vector index migration on next sync.

### Transcription

| Provider | Requirements | Model |
|----------|-------------|-------|
| **local** | Apple Silicon Mac | `mlx-community/whisper-large-v3-turbo` |
| **openai** | `OPENAI_API_KEY` | `whisper-1` |
| **mistral** | `MISTRAL_API_KEY` | `codestral-voxtral-2501` |

See [docs/configuration.md](docs/configuration.md) for full configuration reference.

## Usage

### Standalone Modes

```bash
# CLI chat
uv run main.py

# Server only (API on port 8765)
uv run python -m brain.server

# Desktop app (requires server running)
cd desktop && npm run tauri dev

# Batch sync (for cron/launchd)
uv run python -m brain.batch           # semantic sync
uv run python -m brain.batch --structural
uv run python -m brain.batch --full
```

### MCP Server

Expose Brain tools to external agents:

```bash
# Stdio transport (for Claude Code)
uv run python -m brain.mcp_server

# HTTP transport — automatically available at /mcp when running brain.server
```

## Development

```bash
uv run pytest                    # Run tests
uv run pytest -v                 # Verbose
uv run ruff check                # Lint
uv run ruff check --fix          # Auto-fix
uv run ty check                  # Type check (Python)
cd desktop && npx tsc --noEmit   # Type check (TypeScript)
uv run pre-commit install        # Install git hooks
```

## Architecture

```
brain/                    # Python backend
  server.py               # FastAPI (HTTP + SSE)
  agent.py                # LangChain agent factory
  tools.py                # 7 agent tools
  notes.py                # Notes reader/writer/parser + trash + rename
  graph_db.py             # Neo4j connection wrapper
  kg_pipeline.py          # Embedding pipeline
  sync.py                 # Structural + semantic sync
  settings.py             # Runtime settings (JSON)
  config.py               # Env-based secrets (pydantic-settings)
  mcp_server.py           # MCP server (stdio + HTTP)

desktop/                  # Tauri 2 + React + TypeScript
  src/components/         # Editor, Chat, Sidebar, Settings, Graph, Memory
  src/lib/                # API client, themes, editor extensions
  src-tauri/              # Rust shell
```

See [CLAUDE.md](CLAUDE.md) for the full codebase guide.
