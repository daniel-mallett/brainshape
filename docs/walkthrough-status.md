# Code Walkthrough Status

## Completed

1. **main.py** — Thin entry point, delegates to `brain.cli.run_cli()`. Future interfaces (Slack, web, etc.) will have their own entry points importing from `brain.agent`.

2. **brain/config.py** — `pydantic-settings` loads from `.env`, singleton `settings` object. Discussion: future API keys for internet-connected tools must follow the same pattern (pre-authenticated clients, agent never sees raw keys).

3. **brain/graph_db.py** — Neo4j driver wrapper. `query()` is the single primitive everything builds on. `bootstrap_schema()` creates constraints + indexes on startup. `type: ignore[arg-type]` on `session.run()` because Neo4j types require `LiteralString` but we pass dynamic Cypher by design.

4. **docker-compose.yml** — Neo4j 5 community, ports 7474 (browser UI) + 7687 (Bolt), named volume for data persistence.

5. **Graph design deep dive** — Extensive discussion resulting in the unified `:Document:Note` node design. Two layers (structural + semantic) in one graph. Notes-relative paths as unique keys for cross-device consistency. See `docs/graph-design.md`.

6. **brain/kg_pipeline.py** — Component-based pipeline with `NotesLoader`, `MergingNeo4jWriter`, and sequential component orchestration. The `NotesLoader` provides `document_info` with notes-relative paths which triggers Document node creation.

7. **brain/notes.py** — Regex-based parsing for wikilinks, tags; `python-frontmatter` for YAML. Decided regex is fine for v0.1.

8. **brain/sync.py** — Three functions: `sync_semantic` (KG pipeline, expensive, incremental via content hash), `sync_structural` (Cypher, cheap, runs unconditionally), `sync_all` (orchestrator, semantic-first then structural).

9. **brain/server.py** — FastAPI server exposing all Brain operations over HTTP + SSE. Endpoints for health, config, notes CRUD, agent streaming, and sync. CORS locked to localhost + Tauri origins. Session-based agent conversations.

10. **desktop/** — Tauri 2 app with React + TypeScript. CodeMirror 6 editor with vim mode, agent chat panel with SSE streaming, file browser sidebar, sync controls. ShadCN UI components with Tailwind v4 and dark mode.

## Not Yet Walked Through

- **brain/tools.py** — Written and documented but not discussed line-by-line
- **brain/agent.py** — Written and documented but not discussed line-by-line
- **brain/cli.py** — Written and documented but not discussed line-by-line

## Key Design Decisions Made During Walkthrough

1. **Notes-relative paths** — Changed from absolute paths to `file_path.relative_to(notes_path)` for cross-device consistency
2. **Unified nodes** — `:Document:Note` dual-label design instead of separate disconnected nodes
3. **Semantic-first sync** — KG Builder runs first (creates Document nodes), structural sync runs second (adds :Note label + tags + wikilinks)
4. **NotesLoader** — Custom DataLoader for the KG Builder that provides notes-relative `document_info`, triggering proper Document node creation
5. **Security principles** — Agent gets pre-authenticated clients, never raw credentials. Notes path must not overlap project directory. Documented in CLAUDE.md.
6. **Processing model** — Semantic extraction (LLM, multi-chunk per file) is expensive and should never run automatically on every save or startup. Structural sync (cheap) can run on startup. Semantic sync should be incremental (content-hash-based) and intentional (user-triggered or overnight batch). The agent can always read raw files as a fallback — not every note needs to be "processed" to be useful.

## Open Items / Future Work

### Desktop App — DONE

Tauri 2 + React + TypeScript desktop app with CodeMirror 6 editor (vim mode), agent chat (SSE streaming), file browser, sync controls. FastAPI backend (`brain/server.py`) on localhost:8765. ShadCN UI + Tailwind v4 dark theme. PyInstaller bundling for production is planned.

### Incremental Processing — DONE

Implemented in `sync.py`. SHA-256 content hashes stored on `:Document` nodes. Semantic sync skips unchanged files. Structural sync runs unconditionally (cheap). Batch entry point at `brain/batch.py`.

### Real Embeddings — DONE

Using `SentenceTransformerEmbeddings` with `all-mpnet-base-v2` (768-dim, ungated). Configurable via settings UI with auto vector index migration. Vector index on Chunk nodes for cosine similarity search.

### Component-Based Pipeline — DONE

Replaced `SimpleKGPipeline` with sequential component orchestration in `KGPipeline`.

### Unit Tests — DONE

169 unit tests covering all modules including server, settings, transcription, watcher, MCP client. All external deps mocked. Run with `uv run pytest`.

### Markdown Rendering — DONE

Chat messages rendered with Streamdown (streaming-aware markdown renderer) + Shiki code highlighting. Editor supports three modes: plain text editing, inline WYSIWYG rendering (CodeMirror decorations that hide syntax on non-cursor lines), and full read-only preview (Streamdown).

### Settings UI — DONE

Provider dropdown, model dropdown with suggested models per provider, API key fields (Anthropic/OpenAI), Ollama URL, Whisper model, MCP server editor. Organized into logical sections.

### SSE Token Streaming — DONE

Server streams agent responses token-by-token via `stream_mode="messages"`. JSON-encoded text tokens preserve newlines across SSE transport.

### Other

- Batch API support for cost-efficient bulk processing
- Additional interfaces (Slack, Discord, web, native app, voice)
- Internet access tools (with security service layer)
- GraphPruning for schema enforcement
- Preflight checks (Neo4j connectivity, APOC plugin, LLM health)
- Additional data sources (call transcripts, health data, etc.)
