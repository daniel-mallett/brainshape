# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

"Brainshape" is a personal second-brain agent with knowledge graph memory. It connects a markdown notes directory to a SurrealDB embedded knowledge graph, allowing an AI agent to read/search/create/edit notes and maintain its own long-term memory. It includes a standalone desktop app (Tauri 2 + React) and a FastAPI backend server.

## Architecture

```
brainshape/               # Python backend
├── server.py             # FastAPI (HTTP + SSE) — desktop app backend
├── agent.py → tools → graph_db / notes / kg_pipeline
├── transcribe.py         # Voice transcription (local / OpenAI / Mistral)
├── settings.py           # Runtime user settings (JSON on disk)
├── config.py             # Env-based secrets/infra (pydantic-settings)
├── sync.py               # Structural + semantic sync from notes → graph
├── watcher.py            # File watcher for auto-sync on .md changes
├── mcp_client.py         # External MCP server integration
├── mcp_server.py         # MCP server exposing tools to external agents
├── batch.py              # Standalone batch sync for cron/launchd
└── cli.py                # Interactive CLI chat loop

desktop/                  # Tauri 2 + React + TypeScript
├── src/components/       # Editor (CodeMirror 6), Chat (SSE), Sidebar, Settings, MeetingRecorder
├── src/lib/              # API client, useAgentStream hook, themes engine, editor theme
└── src-tauri/            # Rust shell
```

### Module Reference

- `brainshape/agent.py` — agent factory (`create_brainshape_agent()`), interface-agnostic
- `brainshape/tools.py` — 9 LangChain tools (search, semantic search, read, create, edit notes; query graph; find related; store memory; create connection)
- `brainshape/graph_db.py` — SurrealDB embedded connection wrapper
- `brainshape/notes.py` — notes reader/writer/parser (wikilinks, tags, frontmatter), vault import, trash system (move/list/restore/empty), rename with wikilink rewriting
- `brainshape/server.py` — FastAPI server (HTTP + SSE) for desktop app
- `brainshape/kg_pipeline.py` — embedding pipeline: load → split → embed → write (no LLM entity extraction)
- `brainshape/sync.py` — orchestrates incremental structural + semantic sync from notes to graph
- `brainshape/claude_code.py` — Claude Code CLI provider: spawns `claude` subprocess, parses stream-json output, yields SSE events matching existing contract
- `brainshape/settings.py` — persistent user settings (JSON on disk), LLM provider config, transcription config, MCP servers, font/editor prefs, auto-migration of old keys
- `brainshape/mcp_client.py` — MCP server client, loads external tools via `langchain-mcp-adapters`
- `brainshape/mcp_server.py` — MCP server exposing all 9 tools; HTTP transport mounted at `/mcp` on the FastAPI server, stdio transport for standalone use
- `brainshape/watcher.py` — watchdog file watcher for auto-sync on notes changes
- `brainshape/transcribe.py` — voice transcription with pluggable providers (local mlx-whisper, OpenAI, Mistral)
- `brainshape/cli.py` — interactive CLI chat loop with `/sync` commands
- `brainshape/batch.py` — standalone batch sync entry point for cron/launchd
- `brainshape/config.py` — pydantic-settings from .env (secrets/infra), exports API keys to `os.environ`
- `tests/` — unit tests (all external deps mocked, no Docker or network access required)

## Development Environment

- Python 3.13 (managed via `.python-version`)
- Package management: uv (uses `pyproject.toml`, no `requirements.txt`)
- Virtual environment: `.venv/`
- SurrealDB embedded (via `surrealdb` Python package, no separate server needed)
- Node.js 22 / npm (for desktop frontend, see `.nvmrc`)
- Rust / Cargo (for Tauri shell)

## Commands

### Full Dev Environment
- **First-time setup**: `./scripts/setup.sh` (checks prerequisites, installs deps, copies .env, installs hooks)
- **Start everything**: `./scripts/dev.sh` (starts Python server + Tauri app, Ctrl+C stops all)

### Python Backend
- **Run CLI**: `uv run main.py`
- **Run server**: `uv run python -m brainshape.server` (starts FastAPI on port 52836)
- **Run MCP server**: `uv run python -m brainshape.mcp_server` (stdio transport for Claude Code)
- **Batch sync**: `uv run python -m brainshape.batch` (semantic), `--structural`, or `--full`
- **Test**: `uv run pytest` (all tests), `uv run pytest -v` (verbose), `uv run pytest tests/test_notes.py` (single file)
- **Lint**: `uv run ruff check`
- **Lint fix**: `uv run ruff check --fix`
- **Type check**: `uv run ty check`
- **Pre-commit (install)**: `uv run pre-commit install`
- **Pre-commit (run manually)**: `uv run pre-commit run --all-files`

### Desktop App
- **Dev mode**: `cd desktop && npm run tauri dev` (requires Python server running separately)
- **Frontend only**: `cd desktop && npm run dev` (Vite dev server on port 1420)
- **Type check frontend**: `cd desktop && npx tsc --noEmit`
- **Build**: `cd desktop && npm run tauri build`

## CI & Pre-commit

**Pre-commit hooks** (via `pre-commit` framework):
- `ruff` — lint check with `--fix` for safe auto-fixes
- `ruff-format` — format check
- `gitleaks` — secret detection (API keys, passwords, tokens)
- `ty` — type checking
- `pytest` — runs the test suite

Install hooks after cloning: `uv run pre-commit install`

**GitHub Actions CI** (`.github/workflows/ci.yml`):
- Runs on push to `main` and on PRs targeting `main`
- Steps: `ruff check`, `ty check`, `pytest` (with coverage)
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

There is no `[build-system]` table in `pyproject.toml` — the project is not an installable package. Tests use pytest's `pythonpath = ["."]` config to import `brainshape/` modules directly.

## Configuration

Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` and `NOTES_PATH`. SurrealDB data is stored at `~/.config/brainshape/surrealdb` by default (configurable via `SURREALDB_PATH`).

API keys are loaded from both `.env` (via pydantic-settings) and `~/.config/brainshape/settings.json` (via the settings UI). `config.py` exports them to `os.environ` at startup so downstream libraries (LangChain, Anthropic SDK, etc.) find them automatically. Shell-exported keys take precedence.

**Embedding model:** The default embedding model is `sentence-transformers/all-mpnet-base-v2` (ungated, no login required). This can be changed via the settings UI or `~/.config/brainshape/settings.json` (`embedding_model` and `embedding_dimensions` keys). Changing the model triggers automatic vector index migration on next sync.

**Transcription:** Supports three providers — `local` (mlx-whisper, Apple Silicon only), `openai` (Whisper API), `mistral` (Voxtral API). Configured via `transcription_provider` and `transcription_model` in settings. Old `whisper_model` setting auto-migrates.

**Fonts:** A single `font_family` setting applies to the entire app (UI, editor, preview). When empty, falls back to CSS defaults (Inter for UI, JetBrains Mono for editor). Old `ui_font_family`/`editor_font_family` settings auto-migrate to `font_family`.

## Testing

Unit tests live in `tests/`. All external dependencies (SurrealDB, Anthropic, HuggingFace, cloud APIs) are mocked — no network access required to run tests.

- `tests/conftest.py` — shared fixtures (`mock_db`, `mock_pipeline`, `tmp_notes`, `notes_settings`)
- Tests cover: notes parsing/writing, config/env export, graph_db, all 9 tools, sync logic, kg_pipeline components, server endpoints (CRUD, transcription, meeting, settings, sync, trash, rename), transcription providers, settings migration, MCP client/server, watcher, trash system, note rename with wikilink rewriting

When adding new functionality, add corresponding tests. When fixing bugs, add a regression test.

## Documentation

Documentation lives in `docs/`, `CLAUDE.md`, and `PLAN.md`. When making changes to the codebase, always update any docs that are affected — architecture, tool descriptions, dependency tables, status tracking, etc. In particular, keep `PLAN.md` current with what's working, known issues, and next steps. Stale docs are worse than no docs.

## Security Principles

- **The agent must never have access to raw credentials.** API keys and secrets live in `.env` and are loaded by `config.py` into pre-authenticated clients (SurrealDB connection, Anthropic SDK). Agent tools use those clients — they never see the keys themselves.
- **Any future tool that accesses the internet or file system must go through a service layer** that prevents the agent from exfiltrating secrets (e.g., no arbitrary HTTP requests, no reading outside the notes directory).
- **The notes path must never overlap with the project directory** to prevent the agent from reading `.env` or source code through note-reading tools.
- **API keys are never exposed via the settings API.** The `GET /settings` endpoint strips all `*_api_key` fields and returns `*_api_key_set` booleans instead.
