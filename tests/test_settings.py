import json

import pytest

from brain.settings import (
    DEFAULTS,
    VALID_PROVIDERS,
    VALID_TRANSCRIPTION_PROVIDERS,
    _migrate_settings,
    get_llm_model_string,
    get_notes_path,
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
        assert settings["editor_inline_formatting"] is False
        assert settings["font_family"] == ""

    def test_theme_round_trip(self, tmp_settings_file):
        theme = {"name": "Nord Dark", "background": "#2e3440"}
        result = update_settings({"theme": theme, "editor_keymap": "default"})
        assert result["theme"]["name"] == "Nord Dark"
        assert result["editor_keymap"] == "default"
        # Verify persistence
        reloaded = load_settings()
        assert reloaded["theme"]["name"] == "Nord Dark"
        assert reloaded["editor_keymap"] == "default"

    def test_inline_formatting_round_trip(self, tmp_settings_file):
        result = update_settings({"editor_inline_formatting": True})
        assert result["editor_inline_formatting"] is True
        reloaded = load_settings()
        assert reloaded["editor_inline_formatting"] is True


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


class TestGetNotesPath:
    def test_returns_settings_value_when_set(self):
        update_settings({"notes_path": "~/my-notes"})
        assert get_notes_path() == "~/my-notes"

    def test_falls_back_to_config_when_empty(self, monkeypatch):
        monkeypatch.setattr("brain.config.settings.notes_path", "~/env-notes")
        assert get_notes_path() == "~/env-notes"

    def test_defaults_include_notes_path(self):
        assert "notes_path" in DEFAULTS
        assert DEFAULTS["notes_path"] == ""


def test_valid_providers():
    assert {"anthropic", "openai", "ollama", "claude-code"} == VALID_PROVIDERS


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


class TestCustomThemes:
    def test_defaults_include_custom_themes(self):
        assert "custom_themes" in DEFAULTS
        assert DEFAULTS["custom_themes"] == []

    def test_custom_themes_round_trip(self, tmp_settings_file):
        themes = [{"name": "My Theme", "background": "#123456", "mode": "dark"}]
        result = update_settings({"custom_themes": themes})
        assert result["custom_themes"] == themes
        reloaded = load_settings()
        assert reloaded["custom_themes"] == themes

    def test_custom_themes_persisted(self, tmp_settings_file):
        themes = [{"name": "Custom 1"}, {"name": "Custom 2"}]
        save_settings({"custom_themes": themes})
        saved = json.loads(tmp_settings_file.read_text())
        assert saved["custom_themes"] == themes


class TestThemeNameMigration:
    def test_midnight_migrates_to_monochrome_dark(self):
        old = {"theme": {"name": "Midnight", "background": "#111"}}
        result = _migrate_settings(old)
        assert result["theme"]["name"] == "Monochrome Dark"
        assert result["theme"]["background"] == "#111"

    def test_dawn_migrates_to_gruvbox_light(self):
        old = {"theme": {"name": "Dawn"}}
        result = _migrate_settings(old)
        assert result["theme"]["name"] == "Gruvbox Light"

    def test_nord_migrates_to_nord_dark(self):
        old = {"theme": {"name": "Nord"}}
        result = _migrate_settings(old)
        assert result["theme"]["name"] == "Nord Dark"

    def test_solarized_dark_migrates_to_monochrome_dark(self):
        old = {"theme": {"name": "Solarized Dark"}}
        result = _migrate_settings(old)
        assert result["theme"]["name"] == "Monochrome Dark"

    def test_new_theme_name_unchanged(self):
        old = {"theme": {"name": "Catppuccin Dark"}}
        result = _migrate_settings(old)
        assert result["theme"]["name"] == "Catppuccin Dark"

    def test_no_theme_key_unchanged(self):
        old = {"llm_provider": "anthropic"}
        result = _migrate_settings(old)
        assert "theme" not in result

    def test_migration_on_load(self, tmp_settings_file):
        tmp_settings_file.write_text(
            json.dumps({"theme": {"name": "Midnight", "background": "#000"}})
        )
        settings = load_settings()
        assert settings["theme"]["name"] == "Monochrome Dark"


class TestTranscriptionSettings:
    def test_defaults(self):
        assert DEFAULTS["transcription_provider"] == "local"
        assert DEFAULTS["transcription_model"] == ""
        assert DEFAULTS["mistral_api_key"] == ""
