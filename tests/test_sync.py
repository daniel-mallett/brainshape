from unittest.mock import MagicMock

from brain.sync import _get_stored_hashes, sync_all, sync_semantic, sync_structural


class TestGetStoredHashes:
    def test_returns_path_hash_dict(self):
        db = MagicMock()
        db.query.return_value = [
            {"path": "a.md", "hash": "abc123"},
            {"path": "b.md", "hash": "def456"},
        ]
        result = _get_stored_hashes(db)
        assert result == {"a.md": "abc123", "b.md": "def456"}

    def test_skips_null_hashes(self):
        db = MagicMock()
        db.query.return_value = [
            {"path": "a.md", "hash": "abc123"},
            {"path": "b.md", "hash": None},
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


class TestSyncSemantic:
    def test_skips_unchanged_files(self, tmp_notes):
        db = MagicMock()
        pipeline = MagicMock()
        # Precompute hashes so everything appears unchanged
        from brain.notes import compute_file_hash, list_notes

        hashes = {}
        for f in list_notes(tmp_notes):
            rel = str(f.relative_to(tmp_notes))
            hashes[rel] = compute_file_hash(f)
        db.query.return_value = [{"path": p, "hash": h} for p, h in hashes.items()]
        stats = sync_semantic(db, pipeline, tmp_notes)
        assert stats["processed"] == 0
        assert stats["skipped"] == 5
        pipeline.run.assert_not_called()

    def test_processes_changed_files(self, tmp_notes):
        db = MagicMock()
        pipeline = MagicMock()
        db.query.return_value = []  # No stored hashes → all files are new
        stats = sync_semantic(db, pipeline, tmp_notes)
        assert stats["processed"] == 5
        assert pipeline.run.call_count == 5

    def test_skips_empty_files(self, tmp_path):
        (tmp_path / "empty.md").write_text("")
        db = MagicMock()
        pipeline = MagicMock()
        db.query.return_value = []
        stats = sync_semantic(db, pipeline, tmp_path)
        assert stats["skipped"] == 1
        assert stats["processed"] == 0

    def test_handles_pipeline_error(self, tmp_path):
        (tmp_path / "bad.md").write_text("Some content")
        db = MagicMock()
        pipeline = MagicMock()
        pipeline.run.side_effect = RuntimeError("LLM error")
        db.query.return_value = []
        stats = sync_semantic(db, pipeline, tmp_path)
        assert stats["skipped"] == 1
        assert stats["processed"] == 0


class TestSyncAll:
    def test_combines_stats(self, tmp_notes):
        db = MagicMock()
        pipeline = MagicMock()
        db.query.return_value = []
        stats = sync_all(db, pipeline, tmp_notes)
        assert "structural" in stats
        assert "semantic" in stats
        assert stats["structural"]["notes"] == 5
