from unittest.mock import MagicMock

import pytest

from brain.kg_pipeline import MergingNeo4jWriter, VaultLoader


class TestVaultLoader:
    @pytest.fixture
    def loader(self, tmp_path):
        return VaultLoader(vault_path=tmp_path)

    async def test_reads_file_and_returns_document(self, loader, tmp_path):
        note = tmp_path / "Hello.md"
        note.write_text("# Hello\nWorld")
        doc = await loader.run(filepath=note)
        assert doc.text == "# Hello\nWorld"
        assert doc.document_info.path == "Hello.md"

    async def test_sets_title_from_stem(self, loader, tmp_path):
        note = tmp_path / "My Note.md"
        note.write_text("Content")
        doc = await loader.run(filepath=note)
        assert doc.document_info.metadata["title"] == "My Note"

    async def test_vault_relative_path(self, tmp_path):
        sub = tmp_path / "folder"
        sub.mkdir()
        note = sub / "Deep.md"
        note.write_text("Deep content")
        loader = VaultLoader(vault_path=tmp_path)
        doc = await loader.run(filepath=note)
        assert doc.document_info.path == "folder/Deep.md"


class TestMergingNeo4jWriter:
    def test_upsert_splits_doc_from_other_nodes(self):
        mock_driver = MagicMock()
        writer = MergingNeo4jWriter.__new__(MergingNeo4jWriter)
        writer.driver = mock_driver
        writer.neo4j_database = None
        writer.is_version_5_23_or_above = False

        from neo4j_graphrag.experimental.components.types import (
            LexicalGraphConfig,
            Neo4jNode,
        )

        config = LexicalGraphConfig()

        doc_node = Neo4jNode(
            id="doc1",
            label=config.document_node_label,
            properties={"path": "test.md", "title": "Test"},
        )
        chunk_node = Neo4jNode(
            id="chunk1",
            label=config.chunk_node_label,
            properties={"text": "hello", "index": 0},
        )

        writer._upsert_nodes([doc_node, chunk_node], config)

        # Document node should be MERGE'd via execute_query
        merge_calls = [c for c in mock_driver.execute_query.call_args_list if "MERGE" in str(c)]
        assert len(merge_calls) == 1

        # Chunk node should go through standard CREATE path
        create_calls = [
            c for c in mock_driver.execute_query.call_args_list if "MERGE" not in str(c)
        ]
        assert len(create_calls) == 1
