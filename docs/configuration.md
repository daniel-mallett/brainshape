# Configuration Guide

## Environment Variables (`.env`)

Brain uses `.env` for infrastructure secrets and `~/.config/brain/settings.json` for runtime preferences. Keys set in `.env` (or shell exports) take precedence over settings.

### Required

```bash
NOTES_PATH=~/Brain              # Your notes directory (created on first run)
ANTHROPIC_API_KEY=sk-ant-...    # Required if using Anthropic (default provider)
```

### Neo4j (Docker)

Default values work with `docker compose up -d`:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=brain-dev-password
```

If Neo4j is not running, the server starts in degraded mode: notes CRUD works, but agent and graph features are unavailable. The desktop app shows a warning bar.

### Model Override

```bash
MODEL_NAME=claude-haiku-4-5-20251001   # Override default model
```

## LLM Providers

Configure via the Settings UI or `~/.config/brain/settings.json`.

### Anthropic (Default)

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Get your key from [console.anthropic.com](https://console.anthropic.com/settings/keys).

Settings:
- `llm_provider`: `"anthropic"`
- `llm_model`: `"claude-haiku-4-5-20251001"` (default), or any Claude model

### OpenAI

```bash
OPENAI_API_KEY=sk-proj-...
```

Get your key from [platform.openai.com](https://platform.openai.com/api-keys).

Settings:
- `llm_provider`: `"openai"`
- `llm_model`: `"gpt-4o"` (default), `"gpt-4o-mini"`, etc.

### Ollama (Local)

No API key needed. Install from [ollama.ai](https://ollama.ai), then pull a model:

```bash
ollama pull llama3.1
```

Settings:
- `llm_provider`: `"ollama"`
- `llm_model`: `"llama3.1"` (or any model you pulled)
- `ollama_base_url`: `"http://localhost:11434"` (default)

## Embedding Model

Default: `sentence-transformers/all-mpnet-base-v2` (768 dimensions, ungated — no HuggingFace login required).

The first semantic sync downloads the model (~400MB). Subsequent syncs use the cached version.

To change the model:

1. Open Settings
2. Set `embedding_model` (e.g., `BAAI/bge-small-en-v1.5`)
3. Set `embedding_dimensions` to match (e.g., `384`)
4. Trigger a sync — the vector index is automatically migrated

## Transcription

### Local (mlx-whisper)

Requirements: Apple Silicon Mac with sufficient RAM.

Settings:
- `transcription_provider`: `"local"`
- `transcription_model`: `"mlx-community/whisper-large-v3-turbo"` (default)

### OpenAI Whisper API

Requires `OPENAI_API_KEY`.

Settings:
- `transcription_provider`: `"openai"`
- `transcription_model`: `"whisper-1"`

### Mistral Voxtral API

```bash
MISTRAL_API_KEY=...
```

Settings:
- `transcription_provider`: `"mistral"`
- `transcription_model`: `"codestral-voxtral-2501"`

## Runtime Settings

The Settings UI writes to `~/.config/brain/settings.json`. Changes apply immediately (hot-reload, no restart needed).

### Editor

| Setting | Values | Default |
|---------|--------|---------|
| `editor_keymap` | `"default"`, `"vim"` | `"vim"` |
| `editor_line_numbers` | `true`, `false` | `false` |
| `editor_word_wrap` | `true`, `false` | `true` |
| `editor_font_size` | pixels | `14` |

### Appearance

| Setting | Description |
|---------|-------------|
| `theme` | Object with color overrides (set via Theme dropdown) |
| `font_family` | Applies to entire app. Empty = defaults (Inter UI, JetBrains Mono editor) |

### MCP Servers

External MCP servers can be configured in Settings:

```json
{
  "mcp_servers": [
    {
      "name": "filesystem",
      "transport": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    }
  ]
}
```

Allowed commands: `npx`, `uvx`, `node`, `python`, `python3`, `deno`, `bun`.

## Troubleshooting

### "Cannot connect to Brain server"

The desktop app can't reach the backend.

1. Check server is running: `uv run python -m brain.server`
2. Check port 8765 is not blocked by another process

### "Neo4j not connected" warning

The server started in degraded mode because Neo4j is unreachable.

1. Check Docker is running: `docker ps`
2. Start Neo4j: `docker compose up -d`
3. Check logs: `docker compose logs neo4j`
4. Restart the server after Neo4j is up

### "Agent not initialized" (503 error)

Same as above — Neo4j connection failed. Fix Neo4j, restart the server.

### Transcription fails

- **Local**: Requires Apple Silicon. Verify: `uv run python -c "import mlx_whisper"`
- **OpenAI/Mistral**: Check API key is set and valid in Settings

### Embedding model download hangs

The first sync downloads the model from HuggingFace. Check your internet connection. If behind a proxy, set `HF_ENDPOINT` or `TRANSFORMERS_CACHE` environment variables.

### Neo4j Browser

Access the graph directly at [http://localhost:7474](http://localhost:7474).

Credentials: `neo4j` / `brain-dev-password` (or whatever you set in `.env`).
