from unittest.mock import AsyncMock, MagicMock

from brain.sync import _get_stored_hashes, sync_all, sync_semantic, sync_structural


class TestGetStoredHashes:
    def test_returns_path_hash_dict(self):
        db = MagicMock()
        db.query.return_value = [
            {"path": "a.md", "content_hash": "abc123"},
            {"path": "b.md", "content_hash": "def456"},
        ]
        result = _get_stored_hashes(db)
        assert result == {"a.md": "abc123", "b.md": "def456"}

    def test_skips_null_hashes(self):
        db = MagicMock()
        db.query.return_value = [
            {"path": "a.md", "content_hash": "abc123"},
            {"path": "b.md", "content_hash": None},
        ]
        result = _get_stored_hashes(db)
        assert "b.md" not in result


class TestSyncStructural:
    def test_two_pass_stats(self, tmp_notes):
        db = MagicMock()
        db.query.return_value = []
        stats = sync_structural(db, tmp_notes)
        assert stats["notes"] == 5  # Welcome, About Me, + 3 Tutorials
        assert stats["tags"] >= 0
        assert stats["links"] >= 0
        assert db.query.call_count > 0

    def test_clears_old_rels(self, tmp_notes):
        db = MagicMock()
        db.query.return_value = []
        sync_structural(db, tmp_notes)
        # Should have DELETE calls for TAGGED_WITH and LINKS_TO
        delete_calls = [c for c in db.query.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) > 0

    def test_link_stats_only_count_matched(self, tmp_path):
        """Links to nonexistent notes should not be counted in stats."""
        # Create a note with a wikilink to a nonexistent note
        (tmp_path / "linker.md").write_text("---\ntags: []\n---\nSee [[Nonexistent]]")
        db = MagicMock()
        # Return empty list for MATCH queries (target note doesn't exist)
        db.query.return_value = []
        stats = sync_structural(db, tmp_path)
        assert stats["notes"] == 1
        assert stats["links"] == 0  # Should not count failed matches


class TestSyncSemantic:
    def test_skips_unchanged_files(self, tmp_notes):
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run_async = AsyncMock(return_value=None)
        # Precompute hashes so everything appears unchanged
        from brain.notes import compute_file_hash, list_notes

        hashes = {}
        for f in list_notes(tmp_notes):
            rel = str(f.relative_to(tmp_notes))
            hashes[rel] = compute_file_hash(f)
        db.query.return_value = [{"path": p, "content_hash": h} for p, h in hashes.items()]
        stats = sync_semantic(db, pipeline, tmp_notes)
        assert stats["processed"] == 0
        assert stats["skipped"] == 5
        pipeline.run_async.assert_not_called()

    def test_processes_changed_files(self, tmp_notes):
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run_async = AsyncMock(return_value=None)
        db.query.return_value = []  # No stored hashes → all files are new
        stats = sync_semantic(db, pipeline, tmp_notes)
        assert stats["processed"] == 5
        assert pipeline.run_async.call_count == 5

    def test_skips_empty_files(self, tmp_path):
        (tmp_path / "empty.md").write_text("")
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run_async = AsyncMock(return_value=None)
        db.query.return_value = []
        stats = sync_semantic(db, pipeline, tmp_path)
        assert stats["skipped"] == 1
        assert stats["processed"] == 0

    def test_handles_pipeline_error(self, tmp_path):
        (tmp_path / "bad.md").write_text("Some content")
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run_async = AsyncMock(side_effect=RuntimeError("LLM error"))
        db.query.return_value = []
        stats = sync_semantic(db, pipeline, tmp_path)
        assert stats["skipped"] == 1
        assert stats["processed"] == 0

    def test_no_chunk_pre_delete(self, tmp_path):
        """Regression: sync_semantic should NOT delete chunks before processing.

        The pipeline's _write_chunks handles its own cleanup. Pre-deleting
        causes data loss if the pipeline fails after the delete.
        """
        (tmp_path / "note.md").write_text("Content for embedding")
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run_async = AsyncMock(return_value=None)
        db.query.return_value = []
        sync_semantic(db, pipeline, tmp_path)
        # The only DELETE should NOT happen before run_async — verify that
        # no standalone "DELETE chunk" call is made outside the pipeline
        delete_calls = [c for c in db.query.call_args_list if "DELETE chunk" in str(c)]
        assert len(delete_calls) == 0


class TestSyncEmptyDir:
    def test_structural_empty_dir(self, tmp_path):
        """Structural sync on an empty directory should not crash."""
        db = MagicMock()
        db.query.return_value = []
        stats = sync_structural(db, tmp_path)
        assert stats["notes"] == 0
        assert stats["tags"] == 0
        assert stats["links"] == 0

    def test_semantic_empty_dir(self, tmp_path):
        """Semantic sync on an empty directory should process nothing."""
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run_async = AsyncMock(return_value=None)
        db.query.return_value = []
        stats = sync_semantic(db, pipeline, tmp_path)
        assert stats["processed"] == 0
        assert stats["skipped"] == 0


class TestSyncAll:
    def test_combines_stats(self, tmp_notes):
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run_async = AsyncMock(return_value=None)
        db.query.return_value = []
        stats = sync_all(db, pipeline, tmp_notes)
        assert "structural" in stats
        assert "semantic" in stats
        assert stats["structural"]["notes"] == 5
