# Code Walkthrough Status

## Completed

1. **main.py** — Thin entry point, delegates to `brain.cli.run_cli()`. Future interfaces (Slack, web, etc.) will have their own entry points importing from `brain.agent`.

2. **brain/config.py** — `pydantic-settings` loads from `.env`, singleton `settings` object. Discussion: future API keys for internet-connected tools must follow the same pattern (pre-authenticated clients, agent never sees raw keys).

3. **brain/graph_db.py** — SurrealDB embedded wrapper. `query()` is the single primitive everything builds on. `bootstrap_schema()` creates tables, indexes, and analyzers on startup. `get_relation_tables()` and `get_custom_node_tables()` discover edge and entity tables dynamically via `INFO FOR DB`.

4. **Graph design deep dive** — Single-table-per-entity design with SurrealDB's `TYPE RELATION` for edges. Two layers (structural + semantic) in one embedded database. Notes-relative paths as unique keys for cross-device consistency. See `docs/graph-design.md`.

5. **brain/kg_pipeline.py** — Simple pipeline: read file → split text (4000 chars, 200 overlap) → embed via SentenceTransformer → write chunks to SurrealDB with `RELATE chunk->from_document->note`.

6. **brain/notes.py** — Regex-based parsing for wikilinks (with deduplication, anchor/alias stripping, embed skipping), tags (code block exclusion, case normalization); `python-frontmatter` for YAML. Path traversal protection via `_ensure_within_notes_dir()`.

7. **brain/sync.py** — Three functions: `sync_semantic` (KG pipeline, expensive, incremental via content hash), `sync_structural` (SurrealQL, cheap, two-pass UPSERT + relationships, runs unconditionally), `sync_all` (orchestrator).

8. **brain/server.py** — FastAPI server exposing all Brain operations over HTTP + SSE. Dynamic graph endpoints using table discovery. Memory connections with bidirectional edge resolution. CORS locked to localhost + Tauri origins. Session-based agent conversations.

9. **brain/tools.py** — 9 LangChain tools with entity-type-aware connections, reserved table name protection, duplicate edge prevention, and edge cleanup in `_sync_note_structural()`.

10. **desktop/** — Tauri 2 app with React + TypeScript. CodeMirror 6 editor with vim mode, agent chat panel with SSE streaming, file browser sidebar, graph visualization, memory management. ShadCN UI components with Tailwind v4.

## Key Design Decisions Made During Walkthrough

1. **Notes-relative paths** — Changed from absolute paths to `file_path.relative_to(notes_path)` for cross-device consistency
2. **SurrealDB embedded** — Migrated from Neo4j (Docker) to SurrealDB embedded (`surrealkv://`), eliminating Docker dependency
3. **Two-pass structural sync** — UPSERT all note records first, then create relationships (ensures targets exist before linking)
4. **Agent-driven knowledge graph** — No LLM entity extraction; the agent creates memories and connections through dedicated tools (`store_memory`, `create_connection`)
5. **Security principles** — Agent gets pre-authenticated clients, never raw credentials. Notes path must not overlap project directory. Reserved table names blocked. Documented in CLAUDE.md and `docs/security.md`.
6. **Processing model** — Semantic extraction (embedding, multi-chunk per file) is expensive and should be incremental (content-hash-based). Structural sync (cheap) runs on every startup.
7. **Dynamic table discovery** — Graph endpoints discover edge and entity tables at runtime via `INFO FOR DB` instead of hardcoded lists, supporting agent-created custom relationships.

## Status

### Unit Tests — DONE

396 unit tests (89% coverage) covering all modules including tools (edge cleanup, entity-type matrix, reserved names, duplicate prevention), graph_db (table discovery), server (graph endpoints, memory connections, search), notes (wikilink dedup), settings, transcription providers, watcher, MCP client/server, vault import, trash system, note rename. All external deps mocked. Run with `uv run pytest`.

### Other Items — DONE

- Incremental processing (SHA-256 hash-gated semantic sync)
- Real embeddings (`sentence-transformers/all-mpnet-base-v2`, configurable)
- Markdown rendering (Streamdown + Shiki, three-mode editor)
- Settings UI (providers, themes, fonts, MCP servers, notes path)
- SSE token streaming
- Voice transcription (local/OpenAI/Mistral)
- MCP server (HTTP + stdio transports)
- Configurable notes path with native file picker
- Trash system and note rename with wikilink rewriting
- Search UI (keyword/BM25 + semantic/vector, tag filter, Cmd+Shift+F)

### Future Work

- Single-binary install (bundle Python server as Tauri sidecar via PyInstaller)
- Streaming transcription (real-time output)
- Multi-device sync via Git or cloud storage
