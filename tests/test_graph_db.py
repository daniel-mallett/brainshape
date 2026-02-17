from unittest.mock import MagicMock, patch

from brainshape.graph_db import GraphDB, _convert_record_ids


class TestConvertRecordIds:
    def test_converts_record_id(self):
        mock_rid = MagicMock()
        mock_rid.__str__ = lambda self: "note:abc123"
        # Patch isinstance check
        with patch("brainshape.graph_db.RecordID", type(mock_rid)):
            result = _convert_record_ids(mock_rid)
            assert result == "note:abc123"

    def test_converts_nested_dicts(self):
        result = _convert_record_ids({"name": "Alice", "age": 30})
        assert result == {"name": "Alice", "age": 30}

    def test_converts_nested_lists(self):
        result = _convert_record_ids([{"a": 1}, {"b": 2}])
        assert result == [{"a": 1}, {"b": 2}]

    def test_passes_through_scalars(self):
        assert _convert_record_ids("hello") == "hello"
        assert _convert_record_ids(42) == 42
        assert _convert_record_ids(None) is None


class TestGraphDB:
    @patch("brainshape.graph_db.Surreal")
    def test_query_returns_list_of_dicts(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = [{"name": "Alice", "age": 30}]

        db = GraphDB()
        mock_conn.query.reset_mock()  # clear calls from _migrate_namespace
        mock_conn.query.return_value = [{"name": "Alice", "age": 30}]
        results = db.query("SELECT * FROM note")

        assert results == [{"name": "Alice", "age": 30}]
        mock_conn.query.assert_called_once()

    @patch("brainshape.graph_db.Surreal")
    def test_query_passes_parameters(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = []

        db = GraphDB()
        mock_conn.query.reset_mock()  # clear calls from _migrate_namespace
        mock_conn.query.return_value = []
        db.query("SELECT * FROM note WHERE name = $name", {"name": "Bob"})

        mock_conn.query.assert_called_once_with(
            "SELECT * FROM note WHERE name = $name", {"name": "Bob"}
        )

    @patch("brainshape.graph_db.Surreal")
    def test_bootstrap_schema_runs_all_statements(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = []

        db = GraphDB()
        mock_conn.query.reset_mock()  # clear calls from _migrate_namespace
        mock_conn.query.return_value = []
        db.bootstrap_schema()

        # 4 tables + 3 edge tables + 3 unique indexes + 2 property indexes
        # + 1 analyzer + 2 fulltext indexes = 15 statements
        assert mock_conn.query.call_count == 15

    @patch("brainshape.graph_db.Surreal")
    def test_close(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn

        db = GraphDB()
        db.close()

        mock_conn.close.assert_called_once()

    @patch("brainshape.graph_db.Surreal")
    def test_get_relation_tables(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = {
            "tables": {
                "note": "DEFINE TABLE note TYPE ANY SCHEMALESS",
                "tagged_with": "DEFINE TABLE tagged_with TYPE RELATION IN note OUT tag",
                "links_to": "DEFINE TABLE links_to TYPE RELATION IN note OUT note",
                "from_document": "DEFINE TABLE from_document TYPE RELATION IN chunk OUT note",
                "relates_to": "DEFINE TABLE relates_to TYPE RELATION",
            }
        }
        db = GraphDB()
        tables = db.get_relation_tables()
        assert "tagged_with" in tables
        assert "links_to" in tables
        assert "relates_to" in tables
        assert "from_document" not in tables  # excluded by default

    @patch("brainshape.graph_db.Surreal")
    def test_get_relation_tables_include_internal(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = {
            "tables": {
                "from_document": "DEFINE TABLE from_document TYPE RELATION IN chunk OUT note",
                "tagged_with": "DEFINE TABLE tagged_with TYPE RELATION IN note OUT tag",
            }
        }
        db = GraphDB()
        tables = db.get_relation_tables(exclude_internal=False)
        assert "from_document" in tables
        assert "tagged_with" in tables

    @patch("brainshape.graph_db.Surreal")
    def test_get_custom_node_tables(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = {
            "tables": {
                "note": "DEFINE TABLE note TYPE ANY SCHEMALESS",
                "person": "DEFINE TABLE person TYPE ANY SCHEMALESS",
                "project": "DEFINE TABLE project TYPE ANY SCHEMALESS",
                "tagged_with": "DEFINE TABLE tagged_with TYPE RELATION",
            }
        }
        db = GraphDB()
        custom = db.get_custom_node_tables()
        assert "person" in custom
        assert "project" in custom
        assert "note" not in custom  # core table
        assert "tagged_with" not in custom  # relation table

    @patch("brainshape.graph_db.Surreal")
    def test_get_relation_tables_empty_db(self, mock_surreal_cls):
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = {}
        db = GraphDB()
        assert db.get_relation_tables() == []
        assert db.get_custom_node_tables() == []

    @patch("brainshape.graph_db.Surreal")
    def test_relation_tables_includes_custom_relations(self, mock_surreal_cls):
        """Custom relation tables like works_with appear in get_relation_tables."""
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = {
            "tables": {
                "note": "DEFINE TABLE note TYPE ANY SCHEMALESS",
                "tagged_with": "DEFINE TABLE tagged_with TYPE RELATION IN note OUT tag",
                "works_with": "DEFINE TABLE works_with TYPE RELATION",
                "manages": "DEFINE TABLE manages TYPE RELATION",
            }
        }
        db = GraphDB()
        tables = db.get_relation_tables()
        assert "works_with" in tables
        assert "manages" in tables
        assert "tagged_with" in tables

    @patch("brainshape.graph_db.Surreal")
    def test_custom_node_tables_excludes_relations(self, mock_surreal_cls):
        """Relation tables never appear in get_custom_node_tables."""
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = {
            "tables": {
                "person": "DEFINE TABLE person TYPE ANY SCHEMALESS",
                "works_with": "DEFINE TABLE works_with TYPE RELATION",
                "concept": "DEFINE TABLE concept TYPE ANY SCHEMALESS",
            }
        }
        db = GraphDB()
        custom = db.get_custom_node_tables()
        assert "person" in custom
        assert "concept" in custom
        assert "works_with" not in custom

    @patch("brainshape.graph_db.Surreal")
    def test_custom_node_tables_excludes_core(self, mock_surreal_cls):
        """Core tables (note, tag, memory, chunk) never appear in custom node tables."""
        mock_conn = MagicMock()
        mock_surreal_cls.return_value = mock_conn
        mock_conn.query.return_value = {
            "tables": {
                "note": "DEFINE TABLE note TYPE ANY SCHEMALESS",
                "tag": "DEFINE TABLE tag TYPE ANY SCHEMALESS",
                "memory": "DEFINE TABLE memory TYPE ANY SCHEMALESS",
                "chunk": "DEFINE TABLE chunk TYPE ANY SCHEMALESS",
                "person": "DEFINE TABLE person TYPE ANY SCHEMALESS",
            }
        }
        db = GraphDB()
        custom = db.get_custom_node_tables()
        assert custom == ["person"]
        assert "note" not in custom
        assert "tag" not in custom
        assert "memory" not in custom
        assert "chunk" not in custom
