# Architecture

## Overview

Brain is a personal second-brain agent with knowledge graph memory. It connects an Obsidian vault to a Neo4j knowledge graph, allowing an AI agent to read/search/create/edit notes and maintain its own long-term memory.

## Module Map

```
main.py                      # Thin entry point → brain.cli.run_cli()
docker-compose.yml           # Neo4j 5 community (ports 7474, 7687)
.env / .env.example          # Configuration (gitignored / template)

brain/
├── config.py                # pydantic-settings, loads from .env
├── graph_db.py              # Neo4j driver wrapper, schema bootstrap, query() helper
├── obsidian.py              # Vault reader/writer/parser (wikilinks, tags, frontmatter)
├── kg_pipeline.py           # Component-based KG pipeline (entity/relationship extraction)
├── sync.py                  # Orchestrates incremental semantic + structural sync
├── tools.py                 # 7 LangChain tools for the agent
├── agent.py                 # create_brain_agent() — model + tools + system prompt
├── cli.py                   # Interactive CLI chat loop with /sync commands
└── batch.py                 # Standalone batch sync for cron/launchd

tests/
├── conftest.py              # Shared fixtures (mock db, mock pipeline, tmp vault)
├── test_obsidian.py         # Parsing, writing, hashing
├── test_config.py           # Settings defaults and env loading
├── test_graph_db.py         # GraphDB with mocked driver
├── test_tools.py            # Tool functions with mocked db/pipeline
├── test_sync.py             # Sync logic with mocked deps
└── test_kg_pipeline.py      # ObsidianLoader, MergingNeo4jWriter (mocked driver)
```

## Data Flow

```
main.py → brain/cli.py → brain/agent.py → tools → graph_db / obsidian / kg_pipeline
                              ↑
                    (future: slack.py, web.py, discord.py, voice, native app)
```

## Interface-Agnostic Design

The agent core (`agent.py`) is completely decoupled from any UI. `create_brain_agent()` returns a compiled LangGraph agent that any interface can call via `invoke()` or `stream()`. The CLI (`cli.py`) is just the first consumer. Future interfaces (Slack, Discord, web, native app, voice) each import `create_brain_agent()` and provide their own message loop.

## Sync Model

Two independent sync layers with different cost profiles:

- **Structural sync** (cheap, always current): runs on every CLI startup and via `/sync`. Processes every note unconditionally — parses tags, wikilinks, frontmatter from markdown files. No hash-gating because it's just Cypher queries.
- **Semantic sync** (expensive, incremental): runs via `/sync --full`, `/sync --semantic`, or overnight batch. Uses LLM to extract entities and relationships. Tracked by SHA-256 content hash — only dirty (changed) files are processed.
- **Batch processing**: `uv run python -m brain.batch` for cron/launchd jobs.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `langchain` | Agent framework (`create_agent`, `langchain_core.tools`) |
| `langchain-anthropic` | Claude model provider for LangChain (may be transitive — not directly imported) |
| `langgraph` | `MemorySaver` for in-session conversation history |
| `neo4j` | Python driver for Bolt protocol |
| `neo4j-graphrag` | KG pipeline components (entity extraction, graph writing, entity resolution, `AnthropicLLM`) |
| `sentence-transformers` | Local embedding model (EmbeddingGemma 300m, 768-dim), used via neo4j-graphrag |
| `anthropic` | Transitive dep of neo4j-graphrag's `AnthropicLLM` (not directly imported) |
| `python-frontmatter` | Parse YAML frontmatter from Obsidian markdown |
| `pydantic-settings` | Type-safe .env config (handles `.env` loading natively) |
| `python-dotenv` | Transitive dep (not directly imported — pydantic-settings handles `.env`) |

### Dev Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support (kg_pipeline has async methods) |
| `ruff` | Linter |
| `ty` | Type checker |

### Dependency Management

Uses **uv** — all deps managed via `pyproject.toml`. No `requirements.txt`, no `setup.py`, no `[build-system]`.

- `uv add <package>` — add runtime dep
- `uv add --dev <package>` — add dev dep
- `uv remove <package>` — remove dep
- `uv sync` — sync venv to lockfile

## Configuration

All config flows through `brain/config.py` using `pydantic-settings.BaseSettings`:
- Loads from `.env` file automatically
- Validates types at startup
- Singleton `settings` object imported by all other modules

Key settings: `ANTHROPIC_API_KEY`, `MODEL_NAME`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `VAULT_PATH`
