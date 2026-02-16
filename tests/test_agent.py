"""Tests for brain.agent — agent factory and recreation."""

from unittest.mock import MagicMock, patch

from brain.agent import SYSTEM_PROMPT, create_brain_agent, recreate_agent


class TestCreateBrainAgent:
    @patch("brain.agent.create_agent")
    @patch("brain.agent.create_kg_pipeline")
    @patch("brain.agent.GraphDB")
    def test_creates_agent_with_defaults(self, mock_db_cls, mock_pipeline_fn, mock_create):
        """create_brain_agent() creates a new DB + pipeline when none are given."""
        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_pipeline = MagicMock()
        mock_pipeline_fn.return_value = mock_pipeline
        mock_create.return_value = MagicMock()

        agent, db, pipeline = create_brain_agent()

        mock_db_cls.assert_called_once()
        mock_db.bootstrap_schema.assert_called_once()
        mock_pipeline_fn.assert_called_once()
        mock_create.assert_called_once()
        assert db is mock_db
        assert pipeline is mock_pipeline

    @patch("brain.agent.create_agent")
    def test_uses_provided_db_and_pipeline(self, mock_create):
        """When db and pipeline are provided, they are used directly."""
        mock_db = MagicMock()
        mock_pipeline = MagicMock()
        mock_create.return_value = MagicMock()

        agent, db, pipeline = create_brain_agent(db=mock_db, pipeline=mock_pipeline)

        assert db is mock_db
        assert pipeline is mock_pipeline
        # bootstrap_schema should NOT be called on the provided db
        mock_db.bootstrap_schema.assert_not_called()

    @patch("brain.agent.create_agent")
    def test_sets_tools_globals(self, mock_create):
        """create_brain_agent sets tools.db and tools.pipeline."""
        from brain import tools

        mock_db = MagicMock()
        mock_pipeline = MagicMock()
        mock_create.return_value = MagicMock()

        create_brain_agent(db=mock_db, pipeline=mock_pipeline)

        assert tools.db is mock_db
        assert tools.pipeline is mock_pipeline

    @patch("brain.agent.create_agent")
    def test_includes_mcp_tools(self, mock_create):
        """MCP tools are appended to the built-in tool list."""
        mock_db = MagicMock()
        mock_pipeline = MagicMock()
        mock_create.return_value = MagicMock()
        extra_tool = MagicMock()

        create_brain_agent(db=mock_db, pipeline=mock_pipeline, mcp_tools=[extra_tool])

        call_kwargs = mock_create.call_args[1]
        assert extra_tool in call_kwargs["tools"]

    @patch("brain.agent.create_agent")
    def test_system_prompt_passed(self, mock_create):
        """The system prompt is passed to create_agent."""
        mock_create.return_value = MagicMock()

        create_brain_agent(db=MagicMock(), pipeline=MagicMock())

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["system_prompt"] == SYSTEM_PROMPT


class TestRecreateAgent:
    @patch("brain.agent.create_agent")
    def test_recreates_with_same_db_pipeline(self, mock_create):
        """recreate_agent reuses the given db and pipeline."""
        from brain import tools

        mock_db = MagicMock()
        mock_pipeline = MagicMock()
        mock_create.return_value = MagicMock()

        agent = recreate_agent(mock_db, mock_pipeline)

        assert tools.db is mock_db
        assert tools.pipeline is mock_pipeline
        assert agent is mock_create.return_value

    @patch("brain.agent.create_agent")
    def test_recreate_with_mcp_tools(self, mock_create):
        """recreate_agent includes MCP tools."""
        mock_create.return_value = MagicMock()
        extra = MagicMock()

        recreate_agent(MagicMock(), MagicMock(), mcp_tools=[extra])

        call_kwargs = mock_create.call_args[1]
        assert extra in call_kwargs["tools"]

    @patch("brain.agent.create_agent")
    def test_recreate_without_mcp_tools(self, mock_create):
        """recreate_agent works without MCP tools."""
        mock_create.return_value = MagicMock()

        recreate_agent(MagicMock(), MagicMock())

        call_kwargs = mock_create.call_args[1]
        # Should only have the 7 built-in tools
        assert len(call_kwargs["tools"]) == 7


class TestSystemPrompt:
    def test_prompt_mentions_memory(self):
        """System prompt instructs agent to use persistent memory."""
        assert "Memory" in SYSTEM_PROMPT
        assert "CREATE" in SYSTEM_PROMPT

    def test_prompt_mentions_wikilinks(self):
        """System prompt instructs agent to use wikilink syntax."""
        assert "[[" in SYSTEM_PROMPT
        assert "]]" in SYSTEM_PROMPT

    def test_prompt_mentions_search_strategies(self):
        """System prompt guides search strategy selection."""
        assert "semantic_search" in SYSTEM_PROMPT
        assert "search_notes" in SYSTEM_PROMPT
        assert "query_graph" in SYSTEM_PROMPT
        assert "find_related" in SYSTEM_PROMPT
