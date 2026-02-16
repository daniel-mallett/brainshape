# Brain — Current Status & Next Steps

## What's Working

### Core (Python Backend)
- **SurrealDB embedded** (`surrealkv://`) — zero-config graph database, no Docker required. Data stored at `~/.config/brain/surrealdb`
- Structural sync: two-pass (nodes first, then relationships), runs on every startup unconditionally
- Embedding sync: incremental (SHA-256 hash-gated), single event loop for batch processing, direct SurrealQL writes
- Simplified KG pipeline: load → split → embed → write (no LLM entity extraction)
- HNSW vector index on chunk table for cosine similarity search, BM25 fulltext index for keyword search
- 9 agent tools: search, semantic_search, read, create, edit, query_graph, find_related, store_memory, create_connection
- semantic_search tool: embeds query text locally, runs vector similarity against chunk index
- Agent-driven knowledge graph: agent creates Memory records, custom entities, and relationships through structured tools (store_memory, create_connection) or raw SurrealQL (query_graph). Reserved table names are blocked to prevent schema corruption.
- CLI with /sync commands, tool call visibility, batch entry point for cron
- Folder-aware note creation and editing (edit_note looks up path from graph)
- Tool responses use notes-relative paths only (no system path leakage)
- Seed notes for first-run experience (Welcome, About Me, 3 Tutorials)
- **Settings system**: persistent JSON config (~/.config/brain/settings.json), runtime-configurable LLM provider (Anthropic/OpenAI/Ollama), model selection, unified font family, auto-migration of old settings keys
- **Configurable embedding model**: default `sentence-transformers/all-mpnet-base-v2` (ungated), switchable via settings, auto-migrates vector index on dimension change
- **MCP client**: consume external MCP servers via `langchain-mcp-adapters`, stdio + HTTP transports, hot-reload on settings change (no restart required)
- **MCP server**: exposes all 9 tools via MCP protocol for external agents. Two transports: HTTP (mounted at `/mcp` on the FastAPI server, available automatically when the app is running) and stdio (standalone via `uv run python -m brain.mcp_server`)
- **File watching**: watchdog monitors notes directory, auto-triggers structural sync on .md changes (debounced 2s)
- **Voice transcription**: pluggable provider system — local (mlx-whisper on Apple Silicon), OpenAI Whisper API, or Mistral Voxtral API. Provider + model configurable in settings. Auto-migrates old `whisper_model` setting.
- **Meeting transcription**: `POST /transcribe/meeting` records audio and saves timestamped transcription as a new Note with configurable title, folder, and tags

### FastAPI Server
- HTTP server on port 8765 exposing all Brain operations
- Endpoints: health, config, notes CRUD, agent init/message (SSE streaming), sync (structural/semantic/full)
- Graph endpoints: stats, overview, neighborhood (BFS), memories CRUD, notes tags
- Search endpoints: POST /search/keyword (BM25), POST /search/semantic (vector similarity), both with optional tag filter
- Settings endpoints: GET/PUT /settings for runtime configuration
- Transcription endpoints: POST /transcribe (voice-to-text), POST /transcribe/meeting (audio-to-note with timestamps)
- CORS configured for Vite dev and Tauri origins
- Session-based agent conversations via in-memory store
- Structural sync on startup (mirrors CLI behavior)
- MCP tools loaded at startup from settings configuration
- File watcher started at startup, stopped on shutdown
- Seed notes initialized on first run (copies from seed_notes/ if notes directory is empty)
- **Vault import**: `POST /import/vault` copies .md files from any source directory (e.g., Obsidian vault), preserving folder structure. Skips `.obsidian/`, `.git/`, `.trash/`, and other non-note dirs. Auto-triggers structural sync after import
- **Trash system**: `delete_note()` moves to `.trash/` instead of permanent delete. Preserves folder structure, handles name collisions with timestamp suffix. Endpoints: `GET /notes/trash`, `POST /notes/trash/{path}/restore`, `DELETE /notes/trash` (empty trash). `list_notes()` excludes trash files from all downstream operations.
- **Note rename with wikilink rewriting**: `PUT /notes/file/{path}/rename` renames a note on disk, updates the graph node, and rewrites all `[[Old Title]]` / `[[Old Title|alias]]` wikilinks across all notes. Preserves display aliases.
- **Graceful SurrealDB failure**: Server starts in degraded mode when SurrealDB is unreachable. Notes CRUD works (filesystem-only), agent/graph endpoints return 503. Health endpoint reports `surrealdb_connected` and `agent_available` status.

### Desktop App (Tauri 2 + React + TypeScript)
- Scaffolded with official `create-tauri-app` (React+TS template)
- CodeMirror 6 editor with configurable keybindings (Vim / Default), markdown syntax highlighting, CSS-variable-driven theme
- **Wikilink autocomplete**: typing `[[` suggests existing note titles
- **Tag autocomplete**: typing `#` suggests existing tags from the graph
- **Clickable wikilinks**: Cmd/Ctrl+click navigates to linked notes in Edit/Inline mode; single-click navigation in Preview mode and Chat. Wikilinks highlighted in blue, tags in purple
- Auto-save on edit (debounced 1s PUT to server)
- File tree sidebar with folder grouping, expand/collapse
- Agent chat panel with SSE streaming, tool call indicators
- **Voice recording**: mic button in chat, records audio, transcribes locally, populates input
- Graph visualization: force-directed graph view (full graph, local per-note neighborhood)
- Memory management panel: browse, edit, delete agent memories
- **Markdown rendering in chat**: Streamdown (streaming-aware markdown renderer) + Shiki code highlighting for agent messages. Wikilinks in agent responses are clickable and navigate to the referenced note
- **Editor three-mode toggle**: Edit (plain CodeMirror), Inline (WYSIWYG decorations that hide syntax on non-cursor lines), Preview (read-only Streamdown rendering)
- **Token-by-token SSE streaming**: server streams via `stream_mode="messages"`, JSON-encoded tokens preserve newlines across SSE transport
- **Settings panel**: Appearance (theme selector + per-property color customizer), Fonts (unified font family + editor font size), Editor (keybindings, line numbers, word wrap), Import Notes (vault/directory import), LLM provider, transcription provider, MCP server editor
- **Theme engine**: 4 built-in themes (Midnight, Dawn, Nord, Solarized Dark), ~40 CSS variables covering all UI elements (base colors, surfaces, editor syntax, graph nodes, sidebar). Full per-property customization with color pickers and live preview. Themes persist to backend settings.
- **Meeting recording**: Header button opens modal recorder — captures audio, shows elapsed time, then transcribes via `/transcribe/meeting` and creates a timestamped note
- **Resizable panels**: Sidebar and Chat panels are resizable and collapsible via drag handles (`react-resizable-panels`), sizes persist to localStorage
- **Command palette**: Cmd+K to search notes and run actions (switch views, create note, sync, etc.). Inline note creation from palette, mouse-hover gating to prevent accidental selection.
- View switching: Editor / Graph / Memory / Search views in header
- **Search view**: Dedicated search panel with keyword (BM25) and smart (semantic/vector) modes, tag filter dropdown, debounced input, result snippets with highlighting, score badges. `Cmd+Shift+F` keyboard shortcut.
- **Sidebar**: forwardRef imperative handle for programmatic control (create note, refresh). Context menu clamped to viewport bounds.
- **Error boundary**: Top-level React error boundary catches render crashes and offers reload instead of white-screening the app
- **SurrealDB warning bar**: Shows a subtle warning below the header when SurrealDB is not connected (degraded mode)
- **Sidebar search/filter**: Inline filter input for quick note search, case-insensitive title match, flat list when filtered
- **Trash UI**: Trash icon in sidebar header opens modal listing trashed notes with per-item restore and "Empty Trash" action
- **Inline rename**: Context menu "Rename" shows inline input in sidebar, submits on Enter/blur, escapes to cancel
- **Editor save status**: Shows "Saving...", "Saved", or "Save failed" indicator in editor header
- **Chat suggested prompts**: 4 clickable prompt pills in empty chat state for discoverability
- ShadCN UI components (button, input, scroll-area) + Tailwind v4
- Health check with auto-reconnect polling

### Testing & CI
- 396 unit tests (89% coverage) covering all modules including tools (edge cleanup, entity-type matrix, reserved names, duplicate prevention), graph_db (table discovery), server (graph endpoints, memory connections, search), notes (wikilink dedup), settings, transcription providers, watcher, MCP client/server, vault import, trash system, note rename, error boundary
- Server tests properly isolated (noop lifespan, no SurrealDB connection required)
- CI: GitHub Actions workflow runs ruff, ty, and pytest (with coverage) on push/PR to main
- Pre-commit hooks: ruff lint, ruff format, gitleaks secret detection, pytest
- Dependabot: weekly PRs for Python deps and GitHub Actions versions
- Type checking: ty for Python (brain/ only), tsc for TypeScript frontend

## Known Issues

- None currently tracked

## Next Steps

### Critical Path (adoption blockers)
1. ~~**Obsidian vault compatibility**~~ — **DONE** (vault import copies .md files from any directory, wikilink parsing handles `[[Note#Heading]]` anchors and `[[Note^block]]` refs, image embeds skipped, tags case-normalized). Remaining: reading Obsidian aliases from frontmatter, `.obsidian/` config awareness.
2. **Killer demo** — build a showcase that demonstrates the agent's long-term memory and cross-note intelligence (e.g., surfacing a forgotten connection, recalling a preference from months ago, answering "what did I write about X last quarter?"). The value of structured memory over flat RAG needs to be felt immediately.

### Product
3. ~~Search UI~~ — **DONE** (dedicated search view with keyword/BM25 and semantic/vector modes, tag filter, debounced input, result snippets with highlighting, `Cmd+Shift+F` shortcut)
4. ~~Rich markdown preview~~ — **DONE** (three-mode editor: edit/inline/preview)
5. Streaming transcription — real-time output as user speaks (progressive UI, leverage Mistral realtime API)

### Platform
6. **Single-binary install** — bundle Python server as Tauri sidecar, produce signed `.app`/`.dmg`/`.exe`. Now feasible with SurrealDB embedded (no Docker dependency). Next step: PyInstaller or Nuitka to package the Python server.
7. Plugin system — user-installable extensions beyond MCP servers
8. Multi-device sync — notes sync via Git or cloud storage
