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
    # Notes directory path (empty = use .env or default ~/brain)
    "notes_path": "",
    # LLM provider: "anthropic", "openai", "ollama"
    "llm_provider": "anthropic",
    # Model name per provider
    "llm_model": "claude-haiku-4-5-20251001",
    # Ollama base URL (only used when provider is "ollama")
    "ollama_base_url": "http://localhost:11434",
    # Anthropic API key (used when provider is "anthropic")
    "anthropic_api_key": "",
    # OpenAI-compatible API key (only used when provider is "openai")
    "openai_api_key": "",
    # Mistral API key (used for Mistral transcription)
    "mistral_api_key": "",
    # Transcription provider: "local" (mlx-whisper), "openai", "mistral"
    "transcription_provider": "local",
    # Transcription model (empty = provider default)
    "transcription_model": "",
    # Embedding model for semantic search (must be a sentence-transformers model)
    "embedding_model": "sentence-transformers/all-mpnet-base-v2",
    # Embedding dimensions (must match the model's output dimensions)
    "embedding_dimensions": 768,
    # MCP servers: list of server configs
    # Each: {"name", "transport": "stdio"|"http", "command", "args", "url"}
    "mcp_servers": [],
    # Theme: full theme object (JSON) — see desktop/src/lib/themes.ts
    "theme": {},
    # Font settings
    "font_family": "",
    "editor_font_size": 14,
    # Editor settings
    "editor_keymap": "vim",
    "editor_line_numbers": False,
    "editor_word_wrap": True,
}

# Valid LLM providers
VALID_PROVIDERS = {"anthropic", "openai", "ollama"}

# Valid transcription providers
VALID_TRANSCRIPTION_PROVIDERS = {"local", "openai", "mistral"}

# Default transcription models per provider
TRANSCRIPTION_MODEL_DEFAULTS = {
    "local": "mlx-community/whisper-small",
    "openai": "gpt-4o-mini-transcribe",
    "mistral": "voxtral-mini-latest",
}


def _ensure_dir() -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _migrate_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Migrate old settings keys to new ones."""
    # whisper_model → transcription_model (if not already set)
    if "whisper_model" in settings:
        if not settings.get("transcription_model"):
            settings["transcription_model"] = settings["whisper_model"]
        del settings["whisper_model"]
    # ui_font_family + editor_font_family → font_family
    if "ui_font_family" in settings or "editor_font_family" in settings:
        if not settings.get("font_family"):
            settings["font_family"] = (
                settings.get("ui_font_family") or settings.get("editor_font_family") or ""
            )
        settings.pop("ui_font_family", None)
        settings.pop("editor_font_family", None)
    return settings


def load_settings() -> dict[str, Any]:
    """Load settings from disk, falling back to defaults for missing keys."""
    settings = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            stored = _migrate_settings(stored)
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


def get_llm_kwargs(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return extra kwargs needed for LangChain model init (e.g. Ollama base_url)."""
    if settings is None:
        settings = load_settings()

    provider = settings.get("llm_provider", DEFAULTS["llm_provider"])
    kwargs: dict[str, Any] = {}

    if provider == "ollama":
        kwargs["base_url"] = settings.get("ollama_base_url", DEFAULTS["ollama_base_url"])
        # Always use reasoning=True so Ollama separates thinking into its own
        # field rather than leaking it into content (think:false is broken in
        # Ollama streaming as of 0.16.1). The server only streams content, so
        # thinking is automatically excluded from the chat response.
        kwargs["reasoning"] = True

    return kwargs


def get_notes_path() -> str:
    """Resolve the notes path: settings.json > .env > default.

    Returns the raw path string (not expanded).
    """
    from brain.config import settings as config_settings

    runtime = load_settings()
    path = runtime.get("notes_path", "")
    if path:
        return path
    return config_settings.notes_path
