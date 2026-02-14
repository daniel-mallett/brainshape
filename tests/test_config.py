from brain.config import Settings


class TestSettings:
    def test_defaults(self, monkeypatch):
        # Clear any env vars that would override defaults
        for key in ("ANTHROPIC_API_KEY", "NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD", "VAULT_PATH"):
            monkeypatch.delenv(key, raising=False)
        s = Settings(_env_file=None)
        assert s.anthropic_api_key == ""
        assert s.neo4j_uri == "bolt://localhost:7687"
        assert s.neo4j_user == "neo4j"
        assert s.neo4j_password == "brain-dev-password"
        assert s.vault_path == "~/obsidian-vault"
        assert s.model_name == "claude-haiku-4-5-20251001"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setenv("VAULT_PATH", "/custom/vault")
        s = Settings(_env_file=None)
        assert s.anthropic_api_key == "sk-test-123"
        assert s.vault_path == "/custom/vault"
