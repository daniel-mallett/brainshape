from unittest.mock import MagicMock, patch

from brain.graph_db import GraphDB


class TestGraphDB:
    @patch("brain.graph_db.GraphDatabase.driver")
    def test_query_returns_list_of_dicts(self, mock_driver_factory):
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver

        mock_record = MagicMock()
        mock_record.data.return_value = {"name": "Alice", "age": 30}
        mock_session = MagicMock()
        mock_session.run.return_value = [mock_record]
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        db = GraphDB()
        results = db.query("MATCH (n) RETURN n.name AS name, n.age AS age")

        assert results == [{"name": "Alice", "age": 30}]
        mock_session.run.assert_called_once()

    @patch("brain.graph_db.GraphDatabase.driver")
    def test_query_passes_parameters(self, mock_driver_factory):
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver

        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        db = GraphDB()
        db.query("MATCH (n {name: $name}) RETURN n", {"name": "Bob"})

        mock_session.run.assert_called_once_with(
            "MATCH (n {name: $name}) RETURN n", {"name": "Bob"}
        )

    @patch("brain.graph_db.GraphDatabase.driver")
    def test_bootstrap_schema_runs_all_statements(self, mock_driver_factory):
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver

        mock_session = MagicMock()
        mock_session.run.return_value = []
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        db = GraphDB()
        db.bootstrap_schema()

        assert mock_session.run.call_count == 6

    @patch("brain.graph_db.GraphDatabase.driver")
    def test_close(self, mock_driver_factory):
        mock_driver = MagicMock()
        mock_driver_factory.return_value = mock_driver

        db = GraphDB()
        db.close()

        mock_driver.close.assert_called_once()
