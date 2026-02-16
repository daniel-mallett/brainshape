"""Tests for trash system in brain.notes."""

import pytest

from brain.notes import (
    empty_trash,
    list_notes,
    list_trash,
    move_to_trash,
    restore_from_trash,
    write_note,
)


class TestMoveToTrash:
    def test_moves_file_to_trash(self, tmp_notes):
        write_note(tmp_notes, "Doomed", "content")
        assert (tmp_notes / "Doomed.md").exists()

        trash_path = move_to_trash(tmp_notes, "Doomed.md")

        assert not (tmp_notes / "Doomed.md").exists()
        assert trash_path.exists()
        assert ".trash" in trash_path.parts

    def test_preserves_folder_structure(self, tmp_notes):
        (tmp_notes / "sub").mkdir()
        write_note(tmp_notes, "Deep", "content", folder="sub")

        trash_path = move_to_trash(tmp_notes, "sub/Deep.md")

        assert not (tmp_notes / "sub" / "Deep.md").exists()
        assert trash_path.exists()
        assert trash_path.parent.name == "sub"

    def test_name_collision_appends_timestamp(self, tmp_notes):
        write_note(tmp_notes, "Same", "v1")
        first = move_to_trash(tmp_notes, "Same.md")

        write_note(tmp_notes, "Same", "v2")
        second = move_to_trash(tmp_notes, "Same.md")

        assert first.exists()
        assert second.exists()
        assert first != second

    def test_missing_file_raises(self, tmp_notes):
        with pytest.raises(FileNotFoundError):
            move_to_trash(tmp_notes, "nonexistent.md")

    def test_path_traversal_raises(self, tmp_notes):
        with pytest.raises(ValueError, match="escapes"):
            move_to_trash(tmp_notes, "../outside.md")


class TestListTrash:
    def test_empty_trash(self, tmp_notes):
        assert list_trash(tmp_notes) == []

    def test_lists_trashed_files(self, tmp_notes):
        write_note(tmp_notes, "A", "a")
        write_note(tmp_notes, "B", "b")
        move_to_trash(tmp_notes, "A.md")

        trash = list_trash(tmp_notes)
        assert len(trash) == 1
        assert trash[0].stem == "A"


class TestRestoreFromTrash:
    def test_restores_to_original_location(self, tmp_notes):
        write_note(tmp_notes, "Restore Me", "content")
        move_to_trash(tmp_notes, "Restore Me.md")
        assert not (tmp_notes / "Restore Me.md").exists()

        restored = restore_from_trash(tmp_notes, "Restore Me.md")

        assert restored.exists()
        assert restored == tmp_notes / "Restore Me.md"
        assert list_trash(tmp_notes) == []

    def test_restore_conflict_raises(self, tmp_notes):
        write_note(tmp_notes, "Conflict", "v1")
        move_to_trash(tmp_notes, "Conflict.md")
        write_note(tmp_notes, "Conflict", "v2")

        with pytest.raises(FileExistsError, match="already exists"):
            restore_from_trash(tmp_notes, "Conflict.md")

    def test_restore_missing_raises(self, tmp_notes):
        with pytest.raises(FileNotFoundError):
            restore_from_trash(tmp_notes, "ghost.md")

    def test_restore_path_traversal_raises(self, tmp_notes):
        with pytest.raises(ValueError, match="escapes"):
            restore_from_trash(tmp_notes, "../outside.md")


class TestEmptyTrash:
    def test_empty_when_no_trash(self, tmp_notes):
        assert empty_trash(tmp_notes) == 0

    def test_deletes_all_trash_files(self, tmp_notes):
        write_note(tmp_notes, "A", "a")
        write_note(tmp_notes, "B", "b")
        move_to_trash(tmp_notes, "A.md")
        move_to_trash(tmp_notes, "B.md")

        count = empty_trash(tmp_notes)

        assert count == 2
        assert list_trash(tmp_notes) == []


class TestListNotesExcludesTrash:
    def test_trash_files_excluded(self, tmp_notes):
        write_note(tmp_notes, "Active", "content")
        write_note(tmp_notes, "Trashed", "content")
        move_to_trash(tmp_notes, "Trashed.md")

        notes = list_notes(tmp_notes)
        titles = [n.stem for n in notes]
        assert "Active" in titles
        assert "Trashed" not in titles
