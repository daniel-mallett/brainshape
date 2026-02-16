# Security Model

## Overview

Brain is a local-first, single-user application. The trust boundary sits between the agent (LLM + tools) and the host system. The goal is to limit what the agent can access, even if its behavior is unexpected.

## Credential Isolation

**The agent never sees raw credentials.** API keys and secrets live in `.env` (gitignored) and are loaded by `config.py` into pre-authenticated clients at startup:

| Client | Authenticated in | Used by agent via |
|--------|-----------------|-------------------|
| SurrealDB connection | `graph_db.py` constructor | `db.query()` |
| Anthropic SDK | LangChain model string | Agent framework (implicit) |
| OpenAI Whisper API | `transcribe.py` | `httpx.post()` with Bearer token |
| Mistral Voxtral API | `transcribe.py` | `httpx.post()` with Bearer token |
| HuggingFace embeddings | `kg_pipeline.py` | `pipeline.embed_query()` / `pipeline.run_async()` |

The `.env` file is listed in `.gitignore` and is not readable through any agent tool.

## Filesystem Scoping

All file operations are restricted to the configured notes directory:

- `write_note()` and `rewrite_note()` in `notes.py` validate that the resolved file path stays within the notes directory using `_ensure_within_notes_dir()`. Paths containing `../` traversal sequences that would escape the notes directory raise `ValueError`.
- `read_note` reads content from SurrealDB, not the filesystem directly.
- `list_notes` uses `notes_path.rglob()`, which stays within the notes directory.

**Important:** The notes path (configured via `NOTES_PATH` in `.env` or the settings UI) must never overlap with the project directory. This prevents the agent from accessing `.env`, source code, or other sensitive files through note-reading tools. The `PUT /settings` endpoint enforces this by rejecting notes paths that overlap with the project directory.

## Tool Risk Assessment

| Tool | Access | Notes |
|------|--------|-------|
| `search_notes` | Read (graph) | Parameterized BM25 fulltext query |
| `semantic_search` | Read (graph) | Parameterized vector query |
| `read_note` | Read (graph) | Parameterized by title |
| `create_note` | Write (notes + graph) | Path-traversal protected |
| `edit_note` | Write (notes + graph) | Path-traversal protected |
| `query_graph` | Read/write (graph) | Accepts arbitrary SurrealQL — see below |
| `find_related` | Read (graph) | Parameterized by title |
| `store_memory` | Write (graph) | Creates memory records with parameterized values |
| `create_connection` | Write (graph) | Creates entities + edges — see below |

### `query_graph` — arbitrary SurrealQL

The `query_graph` tool executes raw SurrealQL strings against SurrealDB. This is intentional: the agent uses it for complex graph traversals and ad-hoc queries.

The practical risk is limited because:

- SurrealDB contains only note content and extracted entities — no credentials or secrets.
- The database is embedded (no network exposure) — data is stored locally at `~/.config/brain/surrealdb`.
- The worst-case outcome of a destructive query (e.g., `DELETE note`) is data loss in the graph, which can be rebuilt from the notes directory via `/sync`.

### `create_connection` — schema protection

The `create_connection` tool creates entities and relationships in the graph. It includes several safety measures:

- **Identifier sanitization**: All table/relationship names are sanitized to `[a-zA-Z0-9_]` lowercase via `_sanitize_identifier()`.
- **Reserved table blocklist**: Core tables (`tag`, `chunk`, `tagged_with`, `links_to`, `from_document`) are blocked as entity types. All core tables plus `note` and `memory` are blocked as relationship names. This prevents `DEFINE TABLE OVERWRITE` from corrupting the schema.
- **Entity-type-aware lookups**: `note` and `memory` entities are looked up by their natural key (title/content) and never created — only existing records can be referenced.
- **Duplicate edge prevention**: Before creating an edge, the tool checks if the exact (source, target, relationship) triple already exists.

## HTTP Server (`server.py`)

The FastAPI server binds to `127.0.0.1:8765` — localhost only, not exposed to the network. It adds a web-accessible surface to the agent:

- **CORS** is restricted to `http://localhost:1420` and `:5173` (Vite dev), `tauri://localhost`, and `https://tauri.localhost` (Tauri webview). No wildcard origins.
- **No authentication** — the server is single-user and local-only. If the server were ever exposed to the network, session auth would need to be added.
- **Notes CRUD endpoints** reuse `notes.py` functions, inheriting path-traversal protection via `_ensure_within_notes_dir()`.
- **Agent SSE streaming** at `/agent/message` passes user input through the same agent/tool pipeline as the CLI — no additional attack surface vs the CLI.
- **Session state** is in-memory (dict keyed by session_id). No persistence, no cross-session data leakage.
- **Settings API** (`GET /settings`, `PUT /settings`) handles API keys safely: `GET` never returns raw keys, only boolean `_set` flags (e.g., `anthropic_api_key_set: true`, `mistral_api_key_set: true`). `PUT` accepts new key values but they are stored on disk only, never echoed back.
- **API key export** — `config.py:export_api_keys()` pushes keys from both `.env` and runtime settings into `os.environ` using `setdefault` (shell exports take precedence). Cloud transcription providers read keys from `os.environ` at call time, not from settings directly.
- **MCP command validation** — `PUT /settings` validates MCP server commands against an allowlist (`npx`, `uvx`, `node`, `python`, `python3`, `deno`, `bun`) to prevent arbitrary command execution.
- **Notes path validation** — `PUT /settings` rejects notes paths that overlap with the project directory to prevent the agent from reading source code or `.env` files.

## Known Limitations

- **Error messages may leak schema details.** SurrealQL exceptions from `query_graph` are returned to the agent as-is, which could reveal index names or internal structure. This is acceptable for a local tool but would need sanitization in a multi-user context.

## Design Principles

1. **Pre-authenticated clients, never raw credentials** — any tool that touches an external service goes through a service layer the agent can't use to extract keys.
2. **Notes-scoped filesystem access** — all file writes are validated against the notes directory boundary.
3. **Parameterized queries by default** — all built-in graph queries use `$parameters`, not string interpolation.
4. **Allowlist, not blocklist** — the agent has a fixed set of tools. New capabilities require explicit tool definitions.
5. **Reserved name protection** — core schema tables are protected from overwrite by the agent's `create_connection` tool.

## Future Considerations

As the agent gains capabilities, new tools should follow these rules:

- **Network access** must go through a controlled proxy that strips potential secrets from URLs, headers, and bodies.
- **Shell/code execution** should not be added without sandboxing.
- **Multi-user or shared notes support** would require re-evaluating `query_graph` (read-only enforcement), adding input sanitization for prompt injection, and enforcing notes path isolation at startup.
