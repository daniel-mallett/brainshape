# Security Principles

## Core Rule

**The agent must never have access to raw credentials.** This is a foundational design constraint that must be maintained as the project grows.

## Current State

API keys and secrets live in `.env` and are loaded by `config.py` into pre-authenticated clients:
- Neo4j driver (`graph_db.py`) — authenticated at construction, agent uses `query()` method
- Anthropic SDK (inside `neo4j-graphrag`'s `AnthropicLLM`) — key passed to constructor
- LangChain agent — model string like `anthropic:claude-haiku-4-5-20251001`, SDK handles auth

The agent's tools (`tools.py`) call these pre-authenticated clients. They never see the keys.

## Current Tool Safety

| Tool | Access Level | Risk |
|------|-------------|------|
| search_notes, read_note | Read notes from graph (not filesystem) | Low — only sees note content |
| create_note, edit_note | Write to vault directory only | Low — scoped to vault_path |
| query_graph | Arbitrary Cypher on Neo4j | Low — Neo4j has no env vars |
| remember, recall_memories | Read/write Memory nodes | Low — agent's own data |
| sync_vault_tool | Read vault files, write to graph | Low — scoped to vault_path |
| find_related | Read graph | Low |

## Future Risks

As the agent gains capabilities (internet access, more integrations), new attack surfaces emerge:

### High Risk Tools (not yet built)
- **Web browsing / HTTP requests** — could exfiltrate keys in URL params or POST bodies
- **File system access** — could read `.env` directly
- **Shell/code execution** — game over for any secret on the machine
- **Email/messaging** — could send secrets to external addresses

### Mitigation Principles

1. **Pre-authenticated clients, never raw credentials** — any future tool that touches an external service should go through a service layer the agent can't use to smuggle data out
2. **Vault path must never overlap with the project directory** — prevents the agent from reading `.env` or source code through note-reading tools
3. **Network access through controlled proxies** — if the agent gets internet access, it should go through a service that sanitizes requests (strips potential secrets from URLs/headers/bodies)
4. **Allowlist, not blocklist** — define what the agent CAN access, not what it can't
5. **Audit logging** — log all tool calls and their parameters for review

## .env File

The `.env` file is:
- Listed in `.gitignore` (never committed)
- Only read by `brain/config.py` at startup
- Not accessible to the agent through any tool
