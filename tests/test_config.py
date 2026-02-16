import os
from unittest.mock import patch

from brain.config import Settings, export_api_keys


class TestSettings:
    def test_defaults(self, monkeypatch):
        # Clear any env vars that would override defaults
        for key in ("ANTHROPIC_API_KEY", "SURREALDB_PATH", "NOTES_PATH"):
            monkeypatch.delenv(key, raising=False)
        s = Settings(_env_file=None)
        assert s.anthropic_api_key == ""
        assert s.surrealdb_path == "~/.config/brain/surrealdb"
        assert s.notes_path == "~/brain"
        assert s.model_name == "claude-haiku-4-5-20251001"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setenv("NOTES_PATH", "/custom/notes")
        s = Settings(_env_file=None)
        assert s.anthropic_api_key == "sk-test-123"
        assert s.notes_path == "/custom/notes"


class TestExportApiKeys:
    def test_exports_anthropic_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch("brain.settings.load_settings") as mock_load:
            mock_load.return_value = {"anthropic_api_key": "sk-from-settings", "openai_api_key": ""}
            export_api_keys()
            assert os.environ["ANTHROPIC_API_KEY"] == "sk-from-settings"
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def test_runtime_settings_take_precedence_over_env(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with patch("brain.settings.load_settings") as mock_load:
            mock_load.return_value = {"anthropic_api_key": "sk-from-ui", "openai_api_key": ""}
            export_api_keys()
            assert os.environ["ANTHROPIC_API_KEY"] == "sk-from-ui"
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def test_setdefault_preserves_shell_export(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-shell")
        with patch("brain.settings.load_settings") as mock_load:
            mock_load.return_value = {"anthropic_api_key": "", "openai_api_key": ""}
            export_api_keys()
            # Shell export should be preserved (setdefault doesn't overwrite)
            assert os.environ["ANTHROPIC_API_KEY"] == "sk-from-shell"

    def test_exports_mistral_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        with patch("brain.settings.load_settings") as mock_load:
            mock_load.return_value = {
                "anthropic_api_key": "",
                "openai_api_key": "",
                "mistral_api_key": "mk-test-key",
            }
            export_api_keys()
            assert os.environ["MISTRAL_API_KEY"] == "mk-test-key"
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    def test_exports_openai_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        with patch("brain.settings.load_settings") as mock_load:
            mock_load.return_value = {
                "anthropic_api_key": "",
                "openai_api_key": "sk-openai-test",
                "mistral_api_key": "",
            }
            export_api_keys()
            assert os.environ["OPENAI_API_KEY"] == "sk-openai-test"
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
