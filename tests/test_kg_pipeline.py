from unittest.mock import MagicMock, patch

import numpy as np

from brain.kg_pipeline import KGPipeline, _split_text, create_kg_pipeline


class TestSplitText:
    def test_empty_text(self):
        assert _split_text("") == []

    def test_single_chunk(self):
        result = _split_text("hello", chunk_size=100, chunk_overlap=0)
        assert result == ["hello"]

    def test_multiple_chunks_with_overlap(self):
        text = "a" * 10
        result = _split_text(text, chunk_size=6, chunk_overlap=2)
        assert len(result) == 3
        assert result[0] == "aaaaaa"
        assert result[1] == "aaaaaa"
        assert result[2] == "aa"


class TestKGPipelineWriteChunks:
    def test_writes_note_and_chunks(self):
        """Verify _write_chunks UPSERTs a note and creates chunk records."""
        mock_db = MagicMock()
        mock_db.query.return_value = []

        pipeline = KGPipeline.__new__(KGPipeline)
        pipeline.db = mock_db

        texts = ["Hello world", "Second chunk"]
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        pipeline._write_chunks("test.md", texts, embeddings)

        # Should have: UPSERT note + DELETE old chunks + 2x (CREATE chunk with RELATE)
        assert mock_db.query.call_count == 4

        # First call: UPSERT note
        upsert_call = mock_db.query.call_args_list[0]
        assert "UPSERT" in upsert_call[0][0]

        # Second call: DELETE old chunks
        delete_call = mock_db.query.call_args_list[1]
        assert "DELETE" in delete_call[0][0]

    def test_write_chunks_empty_list(self):
        """_write_chunks with no chunks only UPSERTs note and DELETEs old chunks."""
        mock_db = MagicMock()
        mock_db.query.return_value = []

        pipeline = KGPipeline.__new__(KGPipeline)
        pipeline.db = mock_db

        pipeline._write_chunks("test.md", [], [])

        # Only 2 calls: UPSERT note + DELETE old chunks
        assert mock_db.query.call_count == 2

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
        pipeline.db = MagicMock()
        pipeline.db.query.return_value = []

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        pipeline._model = mock_model

        await pipeline.run_async(str(note))

        # Model should have been called to encode chunks
        mock_model.encode.assert_called_once()
        # DB should have been called (UPSERT + DELETE + CREATE chunks)
        assert pipeline.db.query.call_count >= 2


class TestKGPipelineEmbedQuery:
    def test_embed_query_delegates(self):
        """embed_query delegates to the underlying model."""
        pipeline = KGPipeline.__new__(KGPipeline)
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2, 0.3])
        pipeline._model = mock_model

        result = pipeline.embed_query("test query")

        assert result == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once_with("test query")


class TestCreateKgPipeline:
    @patch("brain.kg_pipeline.KGPipeline")
    def test_reads_settings(self, mock_cls, tmp_path, monkeypatch):
        """create_kg_pipeline reads embedding config from settings."""
        monkeypatch.setattr("brain.settings.SETTINGS_FILE", tmp_path / "settings.json")
        mock_db = MagicMock()

        create_kg_pipeline(mock_db, tmp_path)

        mock_cls.assert_called_once()
        # Should use default embedding model from settings
        assert "all-mpnet-base-v2" in str(mock_cls.call_args)
