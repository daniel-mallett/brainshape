# Brain — Current Status & Next Steps

## What's Working

### Core (Python Backend)
- Structural sync: two-pass (nodes first, then relationships), runs on every startup unconditionally
- Embedding sync: incremental (SHA-256 hash-gated), EmbeddingGemma 300m for chunk embeddings, direct Cypher writes
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

### FastAPI Server
- HTTP server on port 8765 exposing all Brain operations
- Endpoints: health, config, notes CRUD, agent init/message (SSE streaming), sync (structural/semantic/full)
- Graph endpoints: stats, overview, neighborhood, memories CRUD, notes tags
- CORS configured for Vite dev and Tauri origins
- Session-based agent conversations via in-memory store
- Structural sync on startup (mirrors CLI behavior)
- Seed notes initialized on first run (copies from seed_notes/ if notes directory is empty)

### Desktop App (Tauri 2 + React + TypeScript)
- Scaffolded with official `create-tauri-app` (React+TS template)
- CodeMirror 6 editor with vim motions (`@replit/codemirror-vim`), markdown syntax highlighting, one-dark theme
- Auto-save on edit (debounced 1s PUT to server)
- File tree sidebar with folder grouping, expand/collapse
- Agent chat panel with SSE streaming, tool call indicators
- Graph visualization: force-directed graph view (full graph, local per-note neighborhood)
- Memory management panel: browse, edit, delete agent memories
- View switching: Editor / Graph / Memory views in header
- ShadCN UI components (button, input, scroll-area) + Tailwind v4
- Dark mode by default via ShadCN design tokens
- Health check with auto-reconnect polling

### Testing & CI
- 98 unit tests covering all modules including server + graph endpoints
- Server tests properly isolated (noop lifespan, no Neo4j connection required)
- CI: GitHub Actions workflow runs ruff, ty, and pytest (with coverage) on push/PR to main
- Pre-commit hooks: ruff lint, ruff format, gitleaks secret detection, pytest
- Dependabot: weekly PRs for Python deps and GitHub Actions versions
- Type checking: ty for Python (brain/ only), tsc for TypeScript frontend

## Known Issues

- **`.env` config**: API key loading doesn't work for all deps — key needs to be in shell environment too
- **HuggingFace gating**: EmbeddingGemma requires HF account + login. Need to switch to ungated model or Ollama
- **`asyncio.run()` per file**: creates new event loop for each note in semantic sync — should be one loop
- **`notes.py` regex parsing**: could be enhanced with richer metadata extraction in the future
- **Potentially unused deps**: `anthropic`, `langchain-anthropic`, `python-dotenv` are not directly imported — may be transitive deps that could be removed
- **Desktop: no PyInstaller bundling yet**: Python server must be run separately in dev mode

## Next Steps

1. Settings infrastructure + LLM provider configuration (Anthropic, OpenAI, Ollama)
2. MCP server integration — consume external MCP servers for agent actions
3. Better editor features — wikilink autocomplete, tag autocomplete, clickable links
4. Call transcription — built-in audio recording + Whisper transcription
5. PyInstaller bundling — bundle Python server as Tauri sidecar for standalone `.app`
6. File watching — `watchdog` to auto-sync on notes changes
7. Command palette — keyboard-driven actions (create note, search, sync, etc.)
8. Dependency cleanup (audit and remove transitive-only deps)
