# Architecture

## Overview

Brain is a personal second-brain agent with knowledge graph memory. It connects a markdown notes directory to a Neo4j knowledge graph, allowing an AI agent to read/search/create/edit notes and maintain its own long-term memory. It includes a standalone desktop app (Tauri 2 + React) backed by a FastAPI server.

## Module Map

```
main.py                      # Thin entry point → brain.cli.run_cli()
docker-compose.yml           # Neo4j 5 community (ports 7474, 7687)
.env / .env.example          # Configuration (gitignored / template)
scripts/dev.sh               # Start full dev environment (Neo4j + server + Tauri)

brain/
├── config.py                # pydantic-settings, loads from .env
├── graph_db.py              # Neo4j driver wrapper, schema bootstrap, query() helper
├── notes.py                 # Notes reader/writer/parser (wikilinks, tags, frontmatter)
├── kg_pipeline.py           # Component-based KG pipeline (entity/relationship extraction)
├── sync.py                  # Orchestrates incremental semantic + structural sync
├── tools.py                 # 7 LangChain tools for the agent
├── agent.py                 # create_brain_agent() — model + tools + system prompt
├── server.py                # FastAPI server (HTTP + SSE) for desktop app
├── cli.py                   # Interactive CLI chat loop with /sync commands
└── batch.py                 # Standalone batch sync for cron/launchd

desktop/                     # Tauri 2 desktop app (React + TypeScript + Vite)
├── src/
│   ├── components/
│   │   ├── Editor.tsx       # CodeMirror 6 + vim mode
│   │   ├── Chat.tsx         # Agent chat panel with SSE streaming
│   │   └── Sidebar.tsx      # File tree browser
│   ├── lib/
│   │   ├── api.ts           # HTTP client for Python backend
│   │   └── useAgentStream.ts # SSE streaming hook
│   └── App.tsx              # 3-panel layout (sidebar | editor | chat)
├── src-tauri/               # Rust shell (Tauri 2)
├── package.json
└── vite.config.ts

tests/
├── conftest.py              # Shared fixtures (mock db, mock pipeline, tmp notes)
├── test_notes.py            # Parsing, writing, hashing
├── test_config.py           # Settings defaults and env loading
├── test_graph_db.py         # GraphDB with mocked driver
├── test_tools.py            # Tool functions with mocked db/pipeline
├── test_sync.py             # Sync logic with mocked deps
├── test_server.py           # FastAPI endpoint tests
└── test_kg_pipeline.py      # NotesLoader, MergingNeo4jWriter (mocked driver)
```

## Data Flow

```
                              ┌─ brain/cli.py (terminal)
main.py ──┤                   │
           └─ brain/server.py ─┬─ FastAPI HTTP+SSE ← desktop/ (Tauri app)
                               │
                               └─ brain/agent.py → tools → graph_db / notes / kg_pipeline
```

## Interface-Agnostic Design

The agent core (`agent.py`) is completely decoupled from any UI. `create_brain_agent()` returns a compiled LangGraph agent that any interface can call via `invoke()` or `stream()`. Current consumers:

- **CLI** (`cli.py`) — terminal chat loop
- **Server** (`server.py`) — FastAPI with SSE streaming, consumed by the desktop app

Future interfaces (Slack, Discord, voice) each import `create_brain_agent()` and provide their own message loop.

## Server Architecture

`brain/server.py` is a FastAPI app on `localhost:8765` that exposes:

- `GET /health` — health check
- `GET /config` — current settings
- `POST /agent/init` — create session, returns session_id
- `POST /agent/message` — stream agent response via SSE
- `GET /notes/files` — list all notes
- `GET /notes/file/{path}` — read a note
- `POST /notes/file` — create a note
- `PUT /notes/file/{path}` — update a note
- `POST /sync/structural`, `/sync/semantic`, `/sync/full` — trigger sync

In dev mode, the server is started separately. In production, it will be bundled as a Tauri sidecar via PyInstaller.

## Sync Model

Two independent sync layers with different cost profiles:

- **Structural sync** (cheap, always current): runs on every startup (CLI and server) and via `/sync` or `POST /sync/structural`. Processes every note unconditionally — parses tags, wikilinks, frontmatter from markdown files. No hash-gating because it's just Cypher queries.
- **Semantic sync** (expensive, incremental): runs via `/sync --full`, `/sync --semantic`, or `POST /sync/semantic`. Uses local embedding model to chunk and embed notes. Tracked by SHA-256 content hash — only dirty (changed) files are processed.
- **Batch processing**: `uv run python -m brain.batch` for cron/launchd jobs.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `langchain` | Agent framework (`create_agent`, `langchain_core.tools`) |
| `langchain-anthropic` | Claude model provider for LangChain (may be transitive — not directly imported) |
| `langgraph` | `MemorySaver` for in-session conversation history |
| `neo4j` | Python driver for Bolt protocol |
| `neo4j-graphrag` | KG pipeline components (entity extraction, graph writing, entity resolution, `AnthropicLLM`) |
| `sentence-transformers` | Local embedding model (EmbeddingGemma 300m, 768-dim), used via neo4j-graphrag |
| `anthropic` | Transitive dep of neo4j-graphrag's `AnthropicLLM` (not directly imported) |
| `python-frontmatter` | Parse YAML frontmatter from markdown notes |
| `pydantic-settings` | Type-safe .env config (handles `.env` loading natively) |
| `python-dotenv` | Transitive dep (not directly imported — pydantic-settings handles `.env`) |
| `fastapi` | HTTP server framework for desktop app backend |
| `uvicorn` | ASGI server for FastAPI |
| `sse-starlette` | Server-Sent Events for agent response streaming |

### Dev Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support (kg_pipeline has async methods) |
| `pytest-cov` | Coverage reporting |
| `ruff` | Linter |
| `ty` | Type checker |

### Dependency Management

Uses **uv** — all deps managed via `pyproject.toml`. No `requirements.txt`, no `setup.py`, no `[build-system]`.

- `uv add <package>` — add runtime dep
- `uv add --dev <package>` — add dev dep
- `uv remove <package>` — remove dep
- `uv sync` — sync venv to lockfile

## Configuration

All config flows through `brain/config.py` using `pydantic-settings.BaseSettings`:
- Loads from `.env` file automatically
- Validates types at startup
- Singleton `settings` object imported by all other modules

Key settings: `ANTHROPIC_API_KEY`, `MODEL_NAME`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NOTES_PATH`
