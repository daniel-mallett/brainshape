"""Persistent user settings stored as JSON on disk.

Separate from config.py (which handles env-based secrets/infra).
This module manages user-facing preferences that can be changed at runtime
via the settings UI: LLM provider, model selection, etc.
"""

import json
from pathlib import Path
from typing import Any

# Settings file lives next to the notes directory
SETTINGS_FILE = Path("~/.config/brain/settings.json").expanduser()

# Defaults for all settings
DEFAULTS: dict[str, Any] = {
    # LLM provider: "anthropic", "openai", "ollama"
    "llm_provider": "anthropic",
    # Model name per provider
    "llm_model": "claude-haiku-4-5-20251001",
    # Ollama base URL (only used when provider is "ollama")
    "ollama_base_url": "http://localhost:11434",
    # OpenAI-compatible API key (only used when provider is "openai")
    "openai_api_key": "",
    # Whisper model for transcription
    "whisper_model": "mlx-community/whisper-large-v3-turbo",
    # MCP servers: list of server configs
    # Each: {"name", "transport": "stdio"|"http", "command", "args", "url"}
    "mcp_servers": [],
}

# Valid LLM providers
VALID_PROVIDERS = {"anthropic", "openai", "ollama"}


def _ensure_dir() -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    """Load settings from disk, falling back to defaults for missing keys."""
    settings = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings.update(stored)
        except (json.JSONDecodeError, OSError):
            pass  # Corrupt file — use defaults
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """Write settings to disk. Only persists known keys."""
    _ensure_dir()
    to_save = {k: settings[k] for k in DEFAULTS if k in settings}
    SETTINGS_FILE.write_text(json.dumps(to_save, indent=2) + "\n", encoding="utf-8")


def update_settings(updates: dict[str, Any]) -> dict[str, Any]:
    """Merge updates into current settings and persist."""
    current = load_settings()
    for key, value in updates.items():
        if key in DEFAULTS:
            current[key] = value
    save_settings(current)
    return current


def get_llm_model_string(settings: dict[str, Any] | None = None) -> str:
    """Return a model string suitable for LangChain's create_agent().

    Format: 'provider:model_name' or just 'model_name' for anthropic.
    """
    if settings is None:
        settings = load_settings()

    provider = settings.get("llm_provider", DEFAULTS["llm_provider"])
    model = settings.get("llm_model", DEFAULTS["llm_model"])

    if provider == "anthropic":  # noqa: SIM116
        return f"anthropic:{model}"
    elif provider == "openai":
        return f"openai:{model}"
    elif provider == "ollama":
        return f"ollama:{model}"
    return f"anthropic:{model}"
