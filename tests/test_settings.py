import json

import pytest

from brain.settings import (
    DEFAULTS,
    VALID_PROVIDERS,
    VALID_TRANSCRIPTION_PROVIDERS,
    _migrate_settings,
    get_llm_model_string,
    load_settings,
    save_settings,
    update_settings,
)


@pytest.fixture(autouse=True)
def tmp_settings_file(tmp_path, monkeypatch):
    """Point settings file at a temp location."""
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("brain.settings.SETTINGS_FILE", settings_file)
    return settings_file


class TestLoadSettings:
    def test_returns_defaults_when_no_file(self, tmp_settings_file):
        assert not tmp_settings_file.exists()
        settings = load_settings()
        assert settings == DEFAULTS

    def test_loads_from_file(self, tmp_settings_file):
        tmp_settings_file.write_text(json.dumps({"llm_provider": "ollama"}))
        settings = load_settings()
        assert settings["llm_provider"] == "ollama"
        # Other defaults still present
        assert settings["llm_model"] == DEFAULTS["llm_model"]

    def test_handles_corrupt_file(self, tmp_settings_file):
        tmp_settings_file.write_text("not json{{{")
        settings = load_settings()
        assert settings == DEFAULTS


class TestSaveSettings:
    def test_saves_known_keys(self, tmp_settings_file):
        save_settings({"llm_provider": "openai", "unknown_key": "ignored"})
        saved = json.loads(tmp_settings_file.read_text())
        assert saved["llm_provider"] == "openai"
        assert "unknown_key" not in saved

    def test_creates_parent_dirs(self, tmp_path, monkeypatch):
        deep_file = tmp_path / "a" / "b" / "settings.json"
        monkeypatch.setattr("brain.settings.SETTINGS_FILE", deep_file)
        save_settings(DEFAULTS)
        assert deep_file.exists()


class TestUpdateSettings:
    def test_merges_and_persists(self, tmp_settings_file):
        result = update_settings({"llm_provider": "ollama", "llm_model": "llama3.3"})
        assert result["llm_provider"] == "ollama"
        assert result["llm_model"] == "llama3.3"
        # Verify persisted
        saved = json.loads(tmp_settings_file.read_text())
        assert saved["llm_provider"] == "ollama"

    def test_ignores_unknown_keys(self):
        result = update_settings({"unknown": "value"})
        assert "unknown" not in result


class TestThemeAndEditorDefaults:
    def test_defaults_include_theme_fields(self, tmp_settings_file):
        settings = load_settings()
        assert settings["theme"] == {}
        assert settings["editor_keymap"] == "vim"
        assert settings["editor_font_size"] == 14
        assert settings["editor_line_numbers"] is False
        assert settings["editor_word_wrap"] is True
        assert settings["font_family"] == ""

    def test_theme_round_trip(self, tmp_settings_file):
        theme = {"name": "Nord", "background": "#2e3440"}
        result = update_settings({"theme": theme, "editor_keymap": "default"})
        assert result["theme"]["name"] == "Nord"
        assert result["editor_keymap"] == "default"
        # Verify persistence
        reloaded = load_settings()
        assert reloaded["theme"]["name"] == "Nord"
        assert reloaded["editor_keymap"] == "default"


class TestGetLlmModelString:
    def test_anthropic(self):
        s = {"llm_provider": "anthropic", "llm_model": "claude-haiku-4-5-20251001"}
        assert get_llm_model_string(s) == "anthropic:claude-haiku-4-5-20251001"

    def test_openai(self):
        s = {"llm_provider": "openai", "llm_model": "gpt-4o"}
        assert get_llm_model_string(s) == "openai:gpt-4o"

    def test_ollama(self):
        s = {
            "llm_provider": "ollama",
            "llm_model": "llama3.3",
            "ollama_base_url": "http://localhost:11434",
        }
        assert get_llm_model_string(s) == "ollama:llama3.3"

    def test_defaults(self):
        result = get_llm_model_string(DEFAULTS)
        assert result == "anthropic:claude-haiku-4-5-20251001"


class TestEmbeddingSettings:
    def test_defaults_include_embedding_model(self):
        assert "embedding_model" in DEFAULTS
        assert DEFAULTS["embedding_model"] == "sentence-transformers/all-mpnet-base-v2"

    def test_defaults_include_embedding_dimensions(self):
        assert "embedding_dimensions" in DEFAULTS
        assert DEFAULTS["embedding_dimensions"] == 768

    def test_update_embedding_model(self):
        result = update_settings({"embedding_model": "sentence-transformers/all-MiniLM-L6-v2"})
        assert result["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"

    def test_update_embedding_dimensions(self):
        result = update_settings({"embedding_dimensions": 384})
        assert result["embedding_dimensions"] == 384


def test_valid_providers():
    assert {"anthropic", "openai", "ollama"} == VALID_PROVIDERS


def test_valid_transcription_providers():
    assert {"local", "openai", "mistral"} == VALID_TRANSCRIPTION_PROVIDERS


class TestMigrateSettings:
    def test_whisper_model_migrated(self):
        old = {"whisper_model": "mlx-community/whisper-large-v3-turbo"}
        result = _migrate_settings(old)
        assert "whisper_model" not in result
        assert result["transcription_model"] == "mlx-community/whisper-large-v3-turbo"

    def test_whisper_model_skipped_if_new_key_set(self):
        old = {
            "whisper_model": "old-model",
            "transcription_model": "already-set",
        }
        result = _migrate_settings(old)
        assert result["transcription_model"] == "already-set"
        assert "whisper_model" not in result

    def test_font_fields_migrated(self):
        old = {"ui_font_family": "Inter", "editor_font_family": "Fira Code"}
        result = _migrate_settings(old)
        assert "ui_font_family" not in result
        assert "editor_font_family" not in result
        assert result["font_family"] == "Inter"

    def test_font_fields_prefer_existing_font_family(self):
        old = {"ui_font_family": "Inter", "font_family": "Monaco"}
        result = _migrate_settings(old)
        assert result["font_family"] == "Monaco"
        assert "ui_font_family" not in result

    def test_no_migration_needed(self):
        settings = {"llm_provider": "anthropic"}
        result = _migrate_settings(settings)
        assert result == {"llm_provider": "anthropic"}

    def test_migration_on_load(self, tmp_settings_file):
        """whisper_model in stored file gets migrated on load."""
        tmp_settings_file.write_text(
            json.dumps({"whisper_model": "mlx-community/whisper-large-v3-turbo"})
        )
        settings = load_settings()
        assert settings["transcription_model"] == "mlx-community/whisper-large-v3-turbo"
        assert "whisper_model" not in settings


class TestTranscriptionSettings:
    def test_defaults(self):
        assert DEFAULTS["transcription_provider"] == "local"
        assert DEFAULTS["transcription_model"] == ""
        assert DEFAULTS["mistral_api_key"] == ""
