# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"Brain" is a personal second-brain agent with knowledge graph memory. It connects an Obsidian vault to a Neo4j knowledge graph, allowing an AI agent to read/search/create/edit notes and maintain its own long-term memory.

## Architecture

```
main.py → brain/cli.py → brain/agent.py → tools → graph_db / obsidian / kg_pipeline
```

- `brain/agent.py` — agent factory (`create_brain_agent()`), interface-agnostic
- `brain/tools.py` — 9 LangChain tools (search, read, create, edit notes; query graph; remember/recall; sync; find related)
- `brain/graph_db.py` — Neo4j connection wrapper
- `brain/obsidian.py` — vault reader/writer/parser (wikilinks, tags, frontmatter)
- `brain/kg_pipeline.py` — neo4j-graphrag KG Builder for entity/relationship extraction
- `brain/sync.py` — orchestrates structural + semantic sync from vault to graph
- `brain/cli.py` — interactive CLI chat loop
- `brain/config.py` — pydantic-settings from .env

## Development Environment

- Python 3.14 (managed via `.python-version`)
- Package management: uv (uses `pyproject.toml`, no `requirements.txt`)
- Virtual environment: `.venv/`
- Neo4j 5 via Docker

## Commands

- **Run**: `uv run main.py`
- **Start Neo4j**: `docker compose up -d`
- **Neo4j browser**: http://localhost:7474
- **Add dependency**: `uv add <package>`
- **Sync environment**: `uv sync`
- **Lint**: `uv run ruff check`
- **Lint fix**: `uv run ruff check --fix`
- **Type check**: `uv run ty check`

## Configuration

Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` and `VAULT_PATH`.

## Security Principles

- **The agent must never have access to raw credentials.** API keys and secrets live in `.env` and are loaded by `config.py` into pre-authenticated clients (Neo4j driver, Anthropic SDK). Agent tools use those clients — they never see the keys themselves.
- **Any future tool that accesses the internet or file system must go through a service layer** that prevents the agent from exfiltrating secrets (e.g., no arbitrary HTTP requests, no reading outside the vault directory).
- **The vault path must never overlap with the project directory** to prevent the agent from reading `.env` or source code through note-reading tools.
