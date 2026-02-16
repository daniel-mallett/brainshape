import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    anthropic_api_key: str = ""
    model_name: str = "claude-haiku-4-5-20251001"

    # SurrealDB
    surrealdb_path: str = "~/.config/brain/surrealdb"

    # Notes
    notes_path: str = "~/brain"


settings = Settings()


def export_api_keys() -> None:
    """Push API keys into os.environ for downstream libraries.

    Checks both runtime settings (from UI) and .env config,
    with runtime taking precedence. Uses setdefault so explicit
    shell exports aren't overwritten.
    """
    from brain.settings import load_settings

    runtime = load_settings()

    anthropic_key = runtime.get("anthropic_api_key") or settings.anthropic_api_key
    if anthropic_key:
        os.environ.setdefault("ANTHROPIC_API_KEY", anthropic_key)

    openai_key = runtime.get("openai_api_key", "")
    if openai_key:
        os.environ.setdefault("OPENAI_API_KEY", openai_key)

    mistral_key = runtime.get("mistral_api_key", "")
    if mistral_key:
        os.environ.setdefault("MISTRAL_API_KEY", mistral_key)


export_api_keys()
