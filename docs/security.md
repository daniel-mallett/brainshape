# Security Model

## Overview

Brain is a local-first, single-user application. The trust boundary sits between the agent (LLM + tools) and the host system. The goal is to limit what the agent can access, even if its behavior is unexpected.

## Credential Isolation

**The agent never sees raw credentials.** API keys and secrets live in `.env` (gitignored) and are loaded by `config.py` into pre-authenticated clients at startup:

| Client | Authenticated in | Used by agent via |
|--------|-----------------|-------------------|
| Neo4j driver | `graph_db.py` constructor | `db.query()` |
| Anthropic SDK | LangChain model string | Agent framework (implicit) |
| HuggingFace embeddings | `kg_pipeline.py` | `pipeline.embed_query()` / `pipeline.run()` |

The `.env` file is listed in `.gitignore` and is not readable through any agent tool.

## Filesystem Scoping

All file operations are restricted to the configured vault directory:

- `write_note()` and `rewrite_note()` in `vault.py` validate that the resolved file path stays within the vault using `_ensure_within_vault()`. Paths containing `../` traversal sequences that would escape the vault raise `ValueError`.
- `read_note` reads content from Neo4j, not the filesystem directly.
- `list_notes` and `read_vault` use `vault_path.rglob()`, which stays within the vault.

**Important:** The vault path (configured via `VAULT_PATH` in `.env`) must never overlap with the project directory. This prevents the agent from accessing `.env`, source code, or other sensitive files through note-reading tools. This constraint is documented but not enforced at startup.

## Tool Risk Assessment

| Tool | Access | Notes |
|------|--------|-------|
| `search_notes` | Read (graph) | Parameterized full-text query |
| `semantic_search` | Read (graph) | Parameterized vector query |
| `read_note` | Read (graph) | Parameterized by title |
| `create_note` | Write (vault + graph) | Path-traversal protected |
| `edit_note` | Write (vault + graph) | Path-traversal protected |
| `query_graph` | Read/write (graph) | Accepts arbitrary Cypher — see below |
| `find_related` | Read (graph) | Parameterized by entity name |

### `query_graph` — arbitrary Cypher

The `query_graph` tool executes raw Cypher strings against Neo4j using a read-write session. This is intentional: the agent uses `CREATE` statements to persist memories (`:Memory` nodes).

The practical risk is limited because:

- Neo4j contains only note content and extracted entities — no credentials or secrets.
- The database runs locally and is not exposed to the network (default `bolt://localhost:7687`).
- The worst-case outcome of a destructive query (e.g., `MATCH (n) DETACH DELETE n`) is data loss in the graph, which can be rebuilt from the vault via `/sync`.

If the project grows to support untrusted input sources (shared vaults, web clipping, plugins), this tool should be revisited — either by restricting it to read-only and using a dedicated `store_memory` tool for writes, or by adding a Cypher keyword allowlist.

## HTTP Server (`server.py`)

The FastAPI server binds to `127.0.0.1:8765` — localhost only, not exposed to the network. It adds a web-accessible surface to the agent:

- **CORS** is restricted to `http://localhost:5173` (Vite dev), `tauri://localhost`, and `https://tauri.localhost` (Tauri webview). No wildcard origins.
- **No authentication** — the server is single-user and local-only. If the server were ever exposed to the network, session auth would need to be added.
- **Vault CRUD endpoints** reuse `vault.py` functions, inheriting path-traversal protection via `_ensure_within_vault()`.
- **Agent SSE streaming** at `/agent/message` passes user input through the same agent/tool pipeline as the CLI — no additional attack surface vs the CLI.
- **Session state** is in-memory (dict keyed by session_id). No persistence, no cross-session data leakage.

## Known Limitations

- **No vault path overlap enforcement.** The separation between vault and project directories is a documented convention, not a runtime check. A misconfigured `VAULT_PATH` could expose project files.
- **Error messages may leak schema details.** Neo4j exceptions from `query_graph` are returned to the agent as-is, which could reveal index names or internal structure. This is acceptable for a local tool but would need sanitization in a multi-user context.

## Design Principles

1. **Pre-authenticated clients, never raw credentials** — any tool that touches an external service goes through a service layer the agent can't use to extract keys.
2. **Vault-scoped filesystem access** — all file writes are validated against the vault boundary.
3. **Parameterized queries by default** — all built-in graph queries use `$parameters`, not string interpolation.
4. **Allowlist, not blocklist** — the agent has a fixed set of tools. New capabilities require explicit tool definitions.

## Future Considerations

As the agent gains capabilities, new tools should follow these rules:

- **Network access** must go through a controlled proxy that strips potential secrets from URLs, headers, and bodies.
- **Shell/code execution** should not be added without sandboxing.
- **Multi-user or shared vault support** would require re-evaluating `query_graph` (read-only enforcement), adding input sanitization for prompt injection, and enforcing vault path isolation at startup.
