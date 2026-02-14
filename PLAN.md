# Brain — Current Status & Next Steps

## What's Working

### Core (Python Backend)
- Structural sync: two-pass (nodes first, then relationships), runs on every startup unconditionally
- Semantic sync: incremental (SHA-256 hash-gated), EmbeddingGemma 300m for chunk embeddings, LLM entity extraction
- MergingNeo4jWriter: custom writer that MERGEs Document nodes on path (prevents duplicates between structural/semantic layers)
- Component-based KG pipeline: sequential component orchestration (loader → splitter → embedder → extractor → writer → resolver)
- Vector index on Chunk nodes for cosine similarity search
- 7 agent tools: search, semantic_search, read, create, edit, query_graph, find_related
- semantic_search tool: embeds query text locally, runs vector similarity against chunk index
- CLI with /sync commands, tool call visibility, batch entry point for cron
- APOC plugin enabled in Docker
- Memory persistence: agent stores user preferences/info as :Memory nodes via query_graph
- System prompt: auto-discovered entity types, memory instructions, folder-aware note creation
- Folder-aware note creation and editing (edit_note looks up path from graph)
- Tool responses use vault-relative paths only (no system path leakage)

### FastAPI Server
- HTTP server on port 8765 exposing all Brain operations
- Endpoints: health, config, vault CRUD, agent init/message (SSE streaming), sync (structural/semantic/full)
- CORS configured for Vite dev and Tauri origins
- Session-based agent conversations via in-memory store
- Structural sync on startup (mirrors CLI behavior)

### Desktop App (Tauri 2 + React + TypeScript)
- Scaffolded with official `create-tauri-app` (React+TS template)
- CodeMirror 6 editor with vim motions (`@replit/codemirror-vim`), markdown syntax highlighting, one-dark theme
- Auto-save on edit (debounced 1s PUT to server)
- File tree sidebar with folder grouping, expand/collapse
- Agent chat panel with SSE streaming, tool call indicators
- Sync controls (structural/semantic/full) in sidebar
- ShadCN UI components (button, input, scroll-area, separator) + Tailwind v4
- Dark mode by default via ShadCN design tokens
- Health check with auto-reconnect polling

### Testing & CI
- 85 unit tests covering all modules including server endpoints (71% line coverage)
- CI: GitHub Actions workflow runs ruff, ty, and pytest (with coverage) on push/PR to main
- Pre-commit hooks: ruff lint, ruff format, gitleaks secret detection, pytest
- Dependabot: weekly PRs for Python deps and GitHub Actions versions
- Type checking: ty for Python (brain/ only), tsc for TypeScript frontend

## Known Issues

- **`.env` config**: API key loading doesn't work for all deps — key needs to be in shell environment too
- **HuggingFace gating**: EmbeddingGemma requires HF account + login. Need to switch to ungated model or Ollama
- **Entity/Tag constraint collision**: LLM-extracted entities can conflict with Tag node uniqueness constraints (e.g., "CS580" as both entity and tag)
- **Resolver runs per-file**: `SinglePropertyExactMatchResolver` scans entire graph after every note — should run once at end of batch
- **`asyncio.run()` per file**: creates new event loop for each note in semantic sync — should be one loop
- **Anthropic Batch API**: not yet integrated — would halve LLM costs for semantic sync
- **`tools.py` runs pipeline on create/edit**: agent-triggered semantic extraction is expensive and may not be desired
- **`vault.py` regex parsing**: could be enhanced with richer metadata extraction in the future
- **Potentially unused deps**: `anthropic`, `langchain-anthropic`, `python-dotenv` are not directly imported — may be transitive deps that could be removed
- **Desktop: no PyInstaller bundling yet**: Python server must be run separately in dev mode

## Next Steps

1. PyInstaller bundling — bundle Python server as Tauri sidecar for standalone `.app`
2. Graph visualization — Cytoscape.js or D3 for exploring entity/note relationships
3. MCP server — expose Brain tools via Model Context Protocol for external agents
4. Wikilink autocomplete — CodeMirror extension suggesting `[[note titles]]` as you type
5. File watching — `watchdog` to auto-sync on vault changes
6. Command palette — keyboard-driven actions (create note, search, sync, etc.)
7. Entity/Tag constraint collision fix
8. Batch API integration for semantic sync
9. Dependency cleanup (audit and remove transitive-only deps)
