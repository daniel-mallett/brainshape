# Brain — Current Status & Next Steps

## What's Working

### Core (Python Backend)
- Structural sync: two-pass (nodes first, then relationships), runs on every startup unconditionally
- Embedding sync: incremental (SHA-256 hash-gated), single event loop for batch processing, direct Cypher writes
- Simplified KG pipeline: load → split → embed → write (no LLM entity extraction)
- Vector index on Chunk nodes for cosine similarity search
- 7 agent tools: search, semantic_search, read, create, edit, query_graph, find_related
- semantic_search tool: embeds query text locally, runs vector similarity against chunk index
- Agent-driven knowledge graph: agent creates Memory nodes, custom entities, and relationships through conversation
- CLI with /sync commands, tool call visibility, batch entry point for cron
- APOC plugin enabled in Docker
- Folder-aware note creation and editing (edit_note looks up path from graph)
- Tool responses use notes-relative paths only (no system path leakage)
- Seed notes for first-run experience (Welcome, About Me, 3 Tutorials)
- **Settings system**: persistent JSON config (~/.config/brain/settings.json), runtime-configurable LLM provider (Anthropic/OpenAI/Ollama), model selection, Whisper model
- **Configurable embedding model**: default `sentence-transformers/all-mpnet-base-v2` (ungated), switchable via settings, auto-migrates vector index on dimension change
- **MCP server integration**: consume external MCP servers via `langchain-mcp-adapters`, stdio + HTTP transports, hot-reload on settings change (no restart required)
- **File watching**: watchdog monitors notes directory, auto-triggers structural sync on .md changes (debounced 2s)
- **Voice transcription**: pluggable provider system — local (mlx-whisper on Apple Silicon), OpenAI Whisper API, or Mistral Voxtral API. Provider + model configurable in settings. Auto-migrates old `whisper_model` setting.
- **Meeting transcription**: `POST /transcribe/meeting` records audio and saves timestamped transcription as a new Note with configurable title, folder, and tags

### FastAPI Server
- HTTP server on port 8765 exposing all Brain operations
- Endpoints: health, config, notes CRUD, agent init/message (SSE streaming), sync (structural/semantic/full)
- Graph endpoints: stats, overview, neighborhood, memories CRUD, notes tags
- Settings endpoints: GET/PUT /settings for runtime configuration
- Transcription endpoints: POST /transcribe (voice-to-text), POST /transcribe/meeting (audio-to-note with timestamps)
- CORS configured for Vite dev and Tauri origins
- Session-based agent conversations via in-memory store
- Structural sync on startup (mirrors CLI behavior)
- MCP tools loaded at startup from settings configuration
- File watcher started at startup, stopped on shutdown
- Seed notes initialized on first run (copies from seed_notes/ if notes directory is empty)

### Desktop App (Tauri 2 + React + TypeScript)
- Scaffolded with official `create-tauri-app` (React+TS template)
- CodeMirror 6 editor with vim motions (`@replit/codemirror-vim`), markdown syntax highlighting, one-dark theme
- **Wikilink autocomplete**: typing `[[` suggests existing note titles
- **Tag autocomplete**: typing `#` suggests existing tags from the graph
- **Clickable wikilinks**: Cmd/Ctrl+click navigates to linked notes; wikilinks highlighted in blue, tags in purple
- Auto-save on edit (debounced 1s PUT to server)
- File tree sidebar with folder grouping, expand/collapse
- Agent chat panel with SSE streaming, tool call indicators
- **Voice recording**: mic button in chat, records audio, transcribes locally, populates input
- Graph visualization: force-directed graph view (full graph, local per-note neighborhood)
- Memory management panel: browse, edit, delete agent memories
- **Markdown rendering in chat**: Streamdown (streaming-aware markdown renderer) + Shiki code highlighting for agent messages
- **Editor three-mode toggle**: Edit (plain CodeMirror), Inline (WYSIWYG decorations that hide syntax on non-cursor lines), Preview (read-only Streamdown rendering)
- **Token-by-token SSE streaming**: server streams via `stream_mode="messages"`, JSON-encoded tokens preserve newlines across SSE transport
- **Settings panel**: LLM provider dropdown, model dropdown with suggestions per provider, API key fields (Anthropic/OpenAI), Ollama URL, Whisper model, MCP server editor — organized into logical sections
- **Command palette**: Cmd+K to search notes and run actions (switch views, create note, sync, etc.)
- View switching: Editor / Graph / Memory / Settings views in header
- ShadCN UI components (button, input, scroll-area) + Tailwind v4
- Dark mode by default via ShadCN design tokens
- Health check with auto-reconnect polling

### Testing & CI
- 193+ unit tests covering all modules including server, settings, transcription providers, watcher, MCP client
- Server tests properly isolated (noop lifespan, no Neo4j connection required)
- CI: GitHub Actions workflow runs ruff, ty, and pytest (with coverage) on push/PR to main
- Pre-commit hooks: ruff lint, ruff format, gitleaks secret detection, pytest
- Dependabot: weekly PRs for Python deps and GitHub Actions versions
- Type checking: ty for Python (brain/ only), tsc for TypeScript frontend

## Known Issues

- **`notes.py` regex parsing**: could be enhanced with richer metadata extraction in the future

## Next Steps

### Critical Path (adoption blockers)
1. **Obsidian vault compatibility** — first-class support for coexisting with Obsidian. Read Obsidian vaults directly, respect `.obsidian/` config, handle Obsidian-style links and frontmatter conventions. Position as a companion to Obsidian, not a replacement.
2. **Killer demo** — build a showcase that demonstrates the agent's long-term memory and cross-note intelligence (e.g., surfacing a forgotten connection, recalling a preference from months ago, answering "what did I write about X last quarter?"). The value of structured memory over flat RAG needs to be felt immediately.

### Product
3. Search UI — dedicated search view with filters (by tag, date, keyword, semantic)
4. ~~Rich markdown preview~~ — **DONE** (three-mode editor: edit/inline/preview)
5. Streaming transcription — real-time output as user speaks (progressive UI, leverage Mistral realtime API)

### Platform
6. Plugin system — user-installable extensions beyond MCP servers
7. Multi-device sync — notes sync via Git or cloud storage

### Later (post-stabilization)
8. **Single-binary install** — bundle Python server as Tauri sidecar, replace Neo4j with embedded DB, produce signed `.app`/`.dmg`/`.exe`. Deferred until the architecture stabilizes — packaging now would mean maintaining build infrastructure alongside active feature development, and every pipeline or DB change would break the bundling.
