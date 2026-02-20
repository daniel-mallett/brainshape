# Architecture

## Overview

Brainshape is a personal second-brain agent with knowledge graph memory. It connects a markdown notes directory to a SurrealDB embedded knowledge graph, allowing an AI agent to read/search/create/edit notes and maintain its own long-term memory. It includes a standalone desktop app (Tauri 2 + React) backed by a FastAPI server.

## Module Map

```
main.py                      # Thin entry point → brainshape.cli.run_cli()
.env / .env.example          # Configuration (gitignored / template)
scripts/dev.sh               # Start full dev environment (server + Tauri)

brainshape/
├── config.py                # pydantic-settings, loads from .env
├── graph_db.py              # SurrealDB embedded wrapper, schema bootstrap, query() helper
├── notes.py                 # Notes reader/writer/parser, trash system, rename + wikilink rewriting
├── kg_pipeline.py           # Embedding pipeline: load → split → embed → write (no LLM extraction)
├── sync.py                  # Orchestrates incremental semantic + structural sync
├── tools.py                 # 9 LangChain tools for the agent
├── agent.py                 # create_brainshape_agent() — model + tools + system prompt
├── server.py                # FastAPI server (HTTP + SSE) for desktop app
├── settings.py              # Persistent user settings (JSON on disk), LLM provider config
├── claude_code.py           # Claude Code CLI provider (spawns claude subprocess, stream-json)
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
│   │   ├── SearchPanel.tsx  # Keyword (BM25) + semantic search with tag filter
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
│   └── App.tsx              # Multi-view layout (Editor / Graph / Memory / Search / Settings)
├── src-tauri/               # Rust shell (Tauri 2)
├── package.json
└── vite.config.ts

tests/
├── conftest.py              # Shared fixtures (mock db, mock pipeline, tmp notes)
├── test_notes.py            # Parsing, writing, hashing, wikilink dedup
├── test_config.py           # Settings defaults and env loading
├── test_graph_db.py         # GraphDB with mocked driver, table discovery
├── test_tools.py            # Tool functions with mocked db/pipeline, edge cleanup, reserved names
├── test_sync.py             # Sync logic with mocked deps
├── test_server.py           # FastAPI endpoint tests, graph endpoints, memory connections
├── test_kg_pipeline.py      # Chunk writing (mocked driver)
├── test_settings.py         # Settings load/save, defaults, migration
├── test_mcp_client.py       # MCP config building, tool loading
├── test_mcp_server.py       # MCP server lifespan, tool registration
├── test_watcher.py          # File watcher event handling
├── test_transcribe.py       # Transcription provider dispatch, all providers mocked
├── test_trash.py            # Trash system (move, list, restore, empty, list exclusion)
├── test_rename.py           # Note rename, wikilink rewriting
└── test_claude_code.py      # Claude Code provider subprocess handling
```

## Data Flow

```
                              ┌─ brainshape/cli.py (terminal)
main.py ──┤                   │
           └─ brainshape/server.py ─┬─ FastAPI HTTP+SSE ← desktop/ (Tauri app)
                                    │
                                    └─ brainshape/agent.py → tools → graph_db / notes / kg_pipeline
```

## Interface-Agnostic Design

The agent core (`agent.py`) is completely decoupled from any UI. `create_brainshape_agent()` returns a compiled LangGraph agent that any interface can call via `invoke()` or `stream()`. Current consumers:

- **CLI** (`cli.py`) — terminal chat loop
- **Server** (`server.py`) — FastAPI with SSE streaming, consumed by the desktop app

Future interfaces (Slack, Discord, voice) each import `create_brainshape_agent()` and provide their own message loop.

## Server Architecture

`brainshape/server.py` is a FastAPI app on `localhost:52836` that exposes:

- `GET /health` — health check (includes `surrealdb_connected`, `agent_available` status)
- `GET /config` — current configuration
- `POST /agent/init` — create session, returns session_id
- `POST /agent/message` — stream agent response via SSE
- `GET /notes/files` — list all notes
- `GET /notes/file/{path}` — read a note
- `POST /notes/file` — create a note
- `PUT /notes/file/{path}` — update a note
- `DELETE /notes/file/{path}` — move a note to trash
- `PUT /notes/file/{path}/rename` — rename a note and rewrite wikilinks
- `GET /notes/trash` — list trashed notes
- `POST /notes/trash/{path}/restore` — restore a note from trash
- `DELETE /notes/trash` — permanently empty trash
- `GET /notes/tags` — list all tags
- `POST /search/keyword` — BM25 fulltext search with optional tag filter
- `POST /search/semantic` — vector similarity search with optional tag filter
- `GET /graph/stats` — node/relationship counts (dynamic table discovery)
- `GET /graph/overview` — all nodes and edges (optional label filter, includes custom relations)
- `GET /graph/neighborhood/{path}` — local subgraph around a note (BFS over all edge tables)
- `GET /graph/memories` — list agent memories with bidirectional connection discovery
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

- **Structural sync** (cheap, always current): runs on every startup (CLI and server) and via `/sync` or `POST /sync/structural`. Two-pass approach: first UPSERT all note records (so every note exists before linking), then create tag and wikilink relationships. No hash-gating because it's just SurrealQL queries.
- **Semantic sync** (expensive, incremental): runs via `/sync --full`, `/sync --semantic`, or `POST /sync/semantic`. Uses local embedding model to chunk and embed notes. Tracked by SHA-256 content hash — only dirty (changed) files are processed.
- **Batch processing**: `uv run python -m brainshape.batch` for cron/launchd jobs.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `langchain` | Agent framework (`create_agent`, `langchain_core.tools`) |
| `langchain-anthropic` | Claude model provider for LangChain |
| `langgraph` | `MemorySaver` for in-session conversation history |
| `surrealdb` | Embedded graph database (surrealkv:// protocol) |
| `sentence-transformers` | Local embedding model (`all-mpnet-base-v2`, 768-dim), configurable via settings |
| `python-frontmatter` | Parse YAML frontmatter from markdown notes |
| `pydantic-settings` | Type-safe .env config (handles `.env` loading natively) |
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

All config flows through `brainshape/config.py` using `pydantic-settings.BaseSettings`:
- Loads from `.env` file automatically
- Validates types at startup
- Singleton `settings` object imported by all other modules

Key settings: `ANTHROPIC_API_KEY`, `MODEL_NAME`, `SURREALDB_PATH`, `NOTES_PATH`
