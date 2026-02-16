from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from brain.kg_pipeline import KGPipeline, NotesLoader, create_kg_pipeline


class TestNotesLoader:
    @pytest.fixture
    def loader(self, tmp_path):
        return NotesLoader(notes_path=tmp_path)

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

    async def test_notes_relative_path(self, tmp_path):
        sub = tmp_path / "folder"
        sub.mkdir()
        note = sub / "Deep.md"
        note.write_text("Deep content")
        loader = NotesLoader(notes_path=tmp_path)
        doc = await loader.run(filepath=note)
        assert doc.document_info.path == "folder/Deep.md"


class TestKGPipelineWriteChunks:
    def test_writes_document_and_chunks(self):
        """Verify _write_chunks MERGEs a Document node and CREATEs Chunk nodes."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        pipeline = KGPipeline.__new__(KGPipeline)
        pipeline.driver = mock_driver

        # Simulate embedded chunks with text and metadata
        chunk1 = MagicMock()
        chunk1.text = "Hello world"
        chunk1.metadata = {"embedding": [0.1, 0.2, 0.3]}

        chunk2 = MagicMock()
        chunk2.text = "Second chunk"
        chunk2.metadata = {"embedding": [0.4, 0.5, 0.6]}

        pipeline._write_chunks("test.md", [chunk1, chunk2])

        # Should have 3 calls: MERGE doc, DELETE old chunks, batched CREATE chunks
        assert mock_session.run.call_count == 3

        # First call: MERGE Document
        merge_call = mock_session.run.call_args_list[0]
        assert "MERGE" in merge_call[0][0]
        assert merge_call[0][1]["path"] == "test.md"

        # Second call: DELETE old chunks
        delete_call = mock_session.run.call_args_list[1]
        assert "DELETE" in delete_call[0][0]

        # Third call: batched CREATE via UNWIND
        create_call = mock_session.run.call_args_list[2]
        assert "UNWIND" in create_call[0][0]
        assert "CREATE" in create_call[0][0]
        chunks_param = create_call[0][1]["chunks"]
        assert len(chunks_param) == 2
        assert chunks_param[0]["text"] == "Hello world"
        assert chunks_param[0]["index"] == 0
        assert chunks_param[1]["text"] == "Second chunk"
        assert chunks_param[1]["index"] == 1

    def test_write_chunks_empty_list(self):
        """_write_chunks with no chunks only MERGEs the Document and DELETEs old chunks."""
        mock_driver = MagicMock()
        mock_session = MagicMock()
        mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)

        pipeline = KGPipeline.__new__(KGPipeline)
        pipeline.driver = mock_driver

        pipeline._write_chunks("test.md", [])

        # Only 2 calls: MERGE doc + DELETE old chunks (no CREATE since empty)
        assert mock_session.run.call_count == 2

    def test_no_llm_dependencies(self):
        """Verify the pipeline doesn't use any LLM for extraction."""
        import inspect

        source = inspect.getsource(KGPipeline)
        assert "AnthropicLLM" not in source
        assert "EntityRelationExtractor" not in source
        assert "Resolver" not in source


class TestKGPipelineRunAsync:
    async def test_run_async_processes_file(self, tmp_path):
        """run_async loads, splits, embeds, and writes chunks for a file."""
        note = tmp_path / "test.md"
        note.write_text("# Test\nSome content for embedding.")

        pipeline = KGPipeline.__new__(KGPipeline)
        pipeline.notes_path = tmp_path

        mock_loader = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.text = "# Test\nSome content for embedding."
        mock_doc.document_info.path = "test.md"
        mock_loader.run.return_value = mock_doc
        pipeline.loader = mock_loader

        mock_splitter = AsyncMock()
        mock_splitter.run.return_value = MagicMock(text="chunk text")
        pipeline.splitter = mock_splitter

        mock_embedder = AsyncMock()
        mock_embedded = MagicMock()
        mock_embedded.chunks = []
        mock_embedder.run.return_value = mock_embedded
        pipeline.embedder = mock_embedder

        pipeline._write_chunks = MagicMock()

        await pipeline.run_async(str(note))

        mock_loader.run.assert_awaited_once()
        mock_splitter.run.assert_awaited_once()
        mock_embedder.run.assert_awaited_once()
        pipeline._write_chunks.assert_called_once()


class TestKGPipelineEmbedQuery:
    def test_embed_query_delegates(self):
        """embed_query delegates to the underlying embedder."""
        pipeline = KGPipeline.__new__(KGPipeline)
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1, 0.2, 0.3]
        pipeline._embedder = mock_embedder

        result = pipeline.embed_query("test query")

        assert result == [0.1, 0.2, 0.3]
        mock_embedder.embed_query.assert_called_once_with("test query")


class TestCreateKgPipeline:
    @patch("brain.kg_pipeline.KGPipeline")
    def test_reads_settings(self, mock_cls, tmp_path, monkeypatch):
        """create_kg_pipeline reads embedding config from settings."""
        monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
        mock_driver = MagicMock()

        create_kg_pipeline(mock_driver, tmp_path)

        mock_cls.assert_called_once()
        # Should use default embedding model from settings
        assert "all-mpnet-base-v2" in str(mock_cls.call_args)
