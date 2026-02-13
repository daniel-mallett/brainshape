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
├── tools.py                 # 6 LangChain tools for the agent
├── agent.py                 # create_brain_agent() — model + tools + system prompt
├── cli.py                   # Interactive CLI chat loop with /sync commands
└── batch.py                 # Standalone batch sync for cron/launchd
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

Sync is incremental — files are tracked by SHA-256 content hash. Only dirty (changed) files are processed.

- **Structural sync** (cheap): runs on CLI startup and via `/sync`. Parses tags, wikilinks, frontmatter from markdown files.
- **Semantic sync** (expensive): runs via `/sync --full`, `/sync --semantic`, or overnight batch. Uses LLM to extract entities and relationships.
- **Batch processing**: `uv run python -m brain.batch` for cron/launchd jobs.

## Key Dependencies

| Package | Purpose |
|---------|---------|
| `langchain` + `langchain-anthropic` | Agent framework, Claude model provider |
| `langgraph` | `MemorySaver` for in-session conversation history |
| `neo4j` | Python driver for Bolt protocol |
| `neo4j-graphrag` (v1.1.0) | KG pipeline components (entity extraction, graph writing, entity resolution) |
| `anthropic` | Required by neo4j-graphrag's `AnthropicLLM` |
| `python-frontmatter` | Parse YAML frontmatter from Obsidian markdown |
| `pydantic-settings` + `python-dotenv` | Type-safe .env config |

## Configuration

All config flows through `brain/config.py` using `pydantic-settings.BaseSettings`:
- Loads from `.env` file automatically
- Validates types at startup
- Singleton `settings` object imported by all other modules

Key settings: `ANTHROPIC_API_KEY`, `MODEL_NAME`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `VAULT_PATH`
