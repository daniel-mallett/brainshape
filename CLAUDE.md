# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"Brain" is a personal second-brain agent with knowledge graph memory. It connects an Obsidian vault to a Neo4j knowledge graph, allowing an AI agent to read/search/create/edit notes and maintain its own long-term memory.

## Architecture

```
main.py → brain/cli.py → brain/agent.py → tools → graph_db / obsidian / kg_pipeline
```

- `brain/agent.py` — agent factory (`create_brain_agent()`), interface-agnostic
- `brain/tools.py` — 7 LangChain tools (search, semantic search, read, create, edit notes; query graph; find related)
- `brain/graph_db.py` — Neo4j connection wrapper
- `brain/obsidian.py` — vault reader/writer/parser (wikilinks, tags, frontmatter)
- `brain/kg_pipeline.py` — component-based KG pipeline for entity/relationship extraction
- `brain/sync.py` — orchestrates incremental structural + semantic sync from vault to graph
- `brain/cli.py` — interactive CLI chat loop with `/sync` commands
- `brain/batch.py` — standalone batch sync entry point for cron/launchd
- `brain/config.py` — pydantic-settings from .env
- `tests/` — unit tests (all external deps mocked, no Docker/Neo4j required)

## Development Environment

- Python 3.13 (managed via `.python-version`)
- Package management: uv (uses `pyproject.toml`, no `requirements.txt`)
- Virtual environment: `.venv/`
- Neo4j 5 via Docker (with APOC plugin)

## Commands

- **Run**: `uv run main.py`
- **Start Neo4j**: `docker compose up -d`
- **Neo4j browser**: http://localhost:7474
- **Batch sync**: `uv run python -m brain.batch` (semantic), `--structural`, or `--full`
- **Test**: `uv run pytest` (all tests), `uv run pytest -v` (verbose), `uv run pytest tests/test_obsidian.py` (single file)
- **Lint**: `uv run ruff check`
- **Lint fix**: `uv run ruff check --fix`
- **Type check**: `uv run ty check`
- **Pre-commit (install)**: `uv run pre-commit install`
- **Pre-commit (run manually)**: `uv run pre-commit run --all-files`

## CI & Pre-commit

**Pre-commit hooks** (via `pre-commit` framework):
- `ruff` — lint check
- `ruff-format` — format check
- `gitleaks` — secret detection (API keys, passwords, tokens)
- `pytest` — runs the test suite

Install hooks after cloning: `uv run pre-commit install`

**GitHub Actions CI** (`.github/workflows/ci.yml`):
- Runs on push to `main` and on PRs targeting `main`
- Steps: `ruff check`, `ty check`, `pytest` (with coverage)
- `ty` runs in CI only (too slow for pre-commit)
- Coverage report printed in CI output via `pytest-cov`

**Dependabot** (`.github/dependabot.yml`):
- Weekly PRs for Python dependency updates and GitHub Actions version bumps

## Dependency Management

This project uses **uv** for all dependency management. Do not use pip directly.

- **Add a runtime dependency**: `uv add <package>`
- **Add a dev dependency**: `uv add --dev <package>`
- **Remove a dependency**: `uv remove <package>`
- **Sync environment after editing pyproject.toml**: `uv sync`
- **Run anything in the venv**: `uv run <command>`

There is no `[build-system]` table in `pyproject.toml` — the project is not an installable package. Tests use pytest's `pythonpath = ["."]` config to import `brain/` modules directly.

## Configuration

Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` and `VAULT_PATH`.

**Known issue:** `.env` loading doesn't work for all dependencies — the Anthropic API key may need to be exported in your shell profile (e.g. `~/.zshrc`) as well.

**HuggingFace auth:** The embedding model (`google/embeddinggemma-300m`) is gated. Users must accept the license at https://huggingface.co/google/embeddinggemma-300m and run `huggingface-cli login` once. This is a known friction point — switching to an ungated model or Ollama is planned.

## Testing

Unit tests live in `tests/`. All external dependencies (Neo4j, Anthropic, HuggingFace) are mocked — no Docker or network access required to run tests.

- `tests/conftest.py` — shared fixtures (`mock_db`, `mock_pipeline`, `tmp_vault`, `vault_settings`)
- Tests cover: obsidian parsing/writing, config, graph_db, all 7 tools, sync logic, kg_pipeline components

When adding new functionality, add corresponding tests. When fixing bugs, add a regression test.

## Documentation

Documentation lives in `docs/`, `CLAUDE.md`, and `PLAN.md`. When making changes to the codebase, always update any docs that are affected — architecture, tool descriptions, dependency tables, status tracking, etc. In particular, keep `PLAN.md` current with what's working, known issues, and next steps. Stale docs are worse than no docs.

## Security Principles

- **The agent must never have access to raw credentials.** API keys and secrets live in `.env` and are loaded by `config.py` into pre-authenticated clients (Neo4j driver, Anthropic SDK). Agent tools use those clients — they never see the keys themselves.
- **Any future tool that accesses the internet or file system must go through a service layer** that prevents the agent from exfiltrating secrets (e.g., no arbitrary HTTP requests, no reading outside the vault directory).
- **The vault path must never overlap with the project directory** to prevent the agent from reading `.env` or source code through note-reading tools.
