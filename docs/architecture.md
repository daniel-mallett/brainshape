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
├── kg_pipeline.py           # Embedding pipeline: load → split → embed → write (no LLM extraction)
├── sync.py                  # Orchestrates incremental semantic + structural sync
├── tools.py                 # 7 LangChain tools for the agent
├── agent.py                 # create_brain_agent() — model + tools + system prompt
├── server.py                # FastAPI server (HTTP + SSE) for desktop app
├── settings.py              # Persistent user settings (JSON on disk), LLM provider config
├── mcp_client.py            # MCP server client, loads external tools via langchain-mcp-adapters
├── mcp_server.py            # MCP server exposing tools to external agents (HTTP + stdio)
├── watcher.py               # Watchdog file watcher for auto-sync on notes changes
├── transcribe.py            # Voice transcription with pluggable providers (local/OpenAI/Mistral)
├── cli.py                   # Interactive CLI chat loop with /sync commands
└── batch.py                 # Standalone batch sync for cron/launchd

desktop/                     # Tauri 2 desktop app (React + TypeScript + Vite)
├── src/
│   ├── components/
│   │   ├── Editor.tsx       # CodeMirror 6 + vim mode, three-mode toggle (edit/inline/preview)
│   │   ├── Chat.tsx         # Agent chat panel with SSE streaming + Streamdown markdown
│   │   ├── Sidebar.tsx      # File tree browser
│   │   ├── GraphPanel.tsx   # Graph stats + overview controls
│   │   ├── GraphView.tsx    # Force-directed graph visualization
│   │   ├── MemoryPanel.tsx  # Browse, edit, delete agent memories
│   │   ├── SettingsPanel.tsx # LLM provider/model, API keys, MCP servers, voice config
│   │   ├── CommandPalette.tsx # Cmd+K search and actions
│   │   ├── MeetingRecorder.tsx # Meeting audio recording + transcription modal
│   │   └── VoiceRecorder.tsx # Mic button for audio transcription
│   ├── lib/
│   │   ├── api.ts           # HTTP client for Python backend
│   │   ├── useAgentStream.ts # SSE streaming hook
│   │   ├── useVoiceRecorder.ts # Audio recording hook
│   │   ├── useWikilinkClick.ts # Event delegation hook for wikilink navigation
│   │   ├── themes.ts        # Theme engine (built-in themes, CSS variable application)
│   │   ├── editorTheme.ts   # CodeMirror theme driven by CSS variables
│   │   ├── wikilinks.ts     # Clickable wikilink decorations for CodeMirror
│   │   ├── WikilinkComponents.tsx # Streamdown wikilink component overrides
│   │   ├── remarkWikilinks.ts # Remark plugin for [[wikilink]] syntax
│   │   ├── inlineMarkdown.ts # CodeMirror inline markdown rendering (WYSIWYG decorations)
│   │   ├── completions.ts   # Wikilink + tag autocomplete
│   │   └── utils.ts         # Tailwind merge utilities
│   └── App.tsx              # Multi-view layout (Editor / Graph / Memory / Settings)
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
├── test_kg_pipeline.py      # NotesLoader, chunk writing (mocked driver)
├── test_settings.py         # Settings load/save, defaults, migration
├── test_mcp_client.py       # MCP config building, tool loading
├── test_mcp_server.py       # MCP server lifespan, tool registration
├── test_watcher.py          # File watcher event handling
└── test_transcribe.py       # Transcription provider dispatch, all providers mocked
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
- `GET /config` — current configuration
- `POST /agent/init` — create session, returns session_id
- `POST /agent/message` — stream agent response via SSE
- `GET /notes/files` — list all notes
- `GET /notes/file/{path}` — read a note
- `POST /notes/file` — create a note
- `PUT /notes/file/{path}` — update a note
- `DELETE /notes/file/{path}` — delete a note
- `GET /notes/tags` — list all tags
- `GET /graph/stats` — node/relationship counts
- `GET /graph/overview` — all nodes and edges (optional label filter)
- `GET /graph/neighborhood/{path}` — local subgraph around a note
- `GET /graph/memories` — list agent memories
- `DELETE /graph/memory/{id}` — delete a memory
- `PUT /graph/memory/{id}` — update a memory
- `POST /transcribe` — upload audio, returns transcription (uses configured provider)
- `POST /transcribe/meeting` — record meeting audio → timestamped Note
- `GET /settings` — current user settings
- `PUT /settings` — update user settings
- `POST /sync/structural`, `/sync/semantic`, `/sync/full` — trigger sync
- `POST /import/vault` — import markdown files from external directory

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
| `neo4j-graphrag` | KG pipeline components (text splitting, chunk embedding, vector index management) |
| `sentence-transformers` | Local embedding model (`all-mpnet-base-v2`, 768-dim), configurable via settings |
| `python-frontmatter` | Parse YAML frontmatter from markdown notes |
| `pydantic-settings` | Type-safe .env config (handles `.env` loading natively) |
| `python-dotenv` | Transitive dep (not directly imported — pydantic-settings handles `.env`) |
| `fastapi` | HTTP server framework for desktop app backend |
| `uvicorn` | ASGI server for FastAPI |
| `sse-starlette` | Server-Sent Events for agent response streaming |
| `watchdog` | File system watcher for auto-sync on notes changes |
| `mlx-whisper` | Local voice transcription on Apple Silicon (optional) |
| `httpx` | HTTP client for cloud transcription APIs (OpenAI, Mistral) |
| `langchain-mcp-adapters` | Load external MCP server tools into the agent |

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
