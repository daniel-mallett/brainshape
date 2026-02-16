"""Tests for note rename and wikilink rewriting in brain.notes."""

import pytest

from brain.notes import rename_note, rewrite_wikilinks, write_note


class TestRenameNote:
    def test_renames_file(self, tmp_notes):
        write_note(tmp_notes, "Old Title", "content")

        old_title, new_path = rename_note(tmp_notes, "Old Title.md", "New Title")

        assert old_title == "Old Title"
        assert new_path == tmp_notes / "New Title.md"
        assert new_path.exists()
        assert not (tmp_notes / "Old Title.md").exists()

    def test_preserves_folder(self, tmp_notes):
        (tmp_notes / "sub").mkdir()
        write_note(tmp_notes, "Note", "content", folder="sub")

        _, new_path = rename_note(tmp_notes, "sub/Note.md", "Renamed")

        assert new_path == tmp_notes / "sub" / "Renamed.md"
        assert new_path.exists()

    def test_collision_raises(self, tmp_notes):
        write_note(tmp_notes, "A", "a")
        write_note(tmp_notes, "B", "b")

        with pytest.raises(FileExistsError, match="already exists"):
            rename_note(tmp_notes, "A.md", "B")

    def test_missing_file_raises(self, tmp_notes):
        with pytest.raises(FileNotFoundError):
            rename_note(tmp_notes, "ghost.md", "New")

    def test_path_traversal_raises(self, tmp_notes):
        with pytest.raises(ValueError, match="escapes"):
            rename_note(tmp_notes, "../outside.md", "New")

    def test_rejects_slash_in_title(self, tmp_notes):
        write_note(tmp_notes, "Note", "content")
        with pytest.raises(ValueError, match="invalid characters"):
            rename_note(tmp_notes, "Note.md", "../../etc/evil")

    def test_rejects_empty_title(self, tmp_notes):
        write_note(tmp_notes, "Note", "content")
        with pytest.raises(ValueError, match="Invalid note title"):
            rename_note(tmp_notes, "Note.md", "  ")

    def test_rejects_dot_dot_title(self, tmp_notes):
        write_note(tmp_notes, "Note", "content")
        with pytest.raises(ValueError, match="Invalid note title"):
            rename_note(tmp_notes, "Note.md", "..")


class TestRewriteWikilinks:
    def test_rewrites_plain_links(self, tmp_notes):
        write_note(tmp_notes, "Page A", "See [[Old Name]] for details")
        write_note(tmp_notes, "Old Name", "original content")

        count = rewrite_wikilinks(tmp_notes, "Old Name", "New Name")

        assert count == 1
        content = (tmp_notes / "Page A.md").read_text()
        assert "[[New Name]]" in content
        assert "[[Old Name]]" not in content

    def test_preserves_display_alias(self, tmp_notes):
        write_note(tmp_notes, "Page B", "See [[Old Name|click here]]")
        write_note(tmp_notes, "Old Name", "content")

        count = rewrite_wikilinks(tmp_notes, "Old Name", "New Name")

        assert count == 1
        content = (tmp_notes / "Page B.md").read_text()
        assert "[[New Name|click here]]" in content

    def test_no_false_matches(self, tmp_notes):
        write_note(tmp_notes, "Page C", "See [[Other Note]] not this one")

        count = rewrite_wikilinks(tmp_notes, "Old Name", "New Name")

        assert count == 0
        content = (tmp_notes / "Page C.md").read_text()
        assert "[[Other Note]]" in content

    def test_multiple_links_in_one_file(self, tmp_notes):
        write_note(tmp_notes, "Page D", "See [[Target]] and also [[Target|alias]]")
        write_note(tmp_notes, "Target", "content")

        count = rewrite_wikilinks(tmp_notes, "Target", "New Target")

        assert count == 1
        content = (tmp_notes / "Page D.md").read_text()
        assert "[[New Target]]" in content
        assert "[[New Target|alias]]" in content
        assert "[[Target]]" not in content

    def test_does_not_modify_renamed_note_itself(self, tmp_notes):
        write_note(tmp_notes, "Self", "I link to [[Self]]")

        # Rename first
        rename_note(tmp_notes, "Self.md", "New Self")

        # Now rewrite — "Self.md" no longer exists, only "New Self.md"
        count = rewrite_wikilinks(tmp_notes, "Self", "New Self")

        # The renamed file itself has [[Self]] in its content,
        # which should be rewritten
        assert count == 1
