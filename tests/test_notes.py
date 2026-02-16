import pytest

from brain.notes import (
    SEED_NOTES_DIR,
    _ensure_within_notes_dir,
    compute_file_hash,
    delete_note,
    import_vault,
    init_notes,
    list_notes,
    parse_note,
    rewrite_note,
    write_note,
)


class TestEnsureWithinNotesDir:
    def test_valid_path(self, tmp_path):
        child = tmp_path / "notes" / "hello.md"
        child.parent.mkdir()
        child.touch()
        result = _ensure_within_notes_dir(tmp_path, child)
        assert result.is_relative_to(tmp_path.resolve())

    def test_rejects_parent_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="escapes notes"):
            _ensure_within_notes_dir(tmp_path, tmp_path / ".." / "etc" / "passwd")

    def test_rejects_absolute_escape(self, tmp_path):
        with pytest.raises(ValueError, match="escapes notes"):
            _ensure_within_notes_dir(tmp_path, tmp_path / ".." / ".." / "tmp" / "evil.md")


class TestComputeFileHash:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "note.md"
        f.write_text("hello world")
        h1 = compute_file_hash(f)
        h2 = compute_file_hash(f)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.md"
        f2 = tmp_path / "b.md"
        f1.write_text("aaa")
        f2.write_text("bbb")
        assert compute_file_hash(f1) != compute_file_hash(f2)


class TestParseNote:
    def test_welcome_note(self, tmp_notes):
        result = parse_note(tmp_notes / "Welcome.md", tmp_notes)
        assert result["title"] == "Welcome"
        assert result["path"] == "Welcome.md"
        assert "second-brain" in result["content"]

    def test_wikilinks(self, tmp_notes):
        result = parse_note(tmp_notes / "Welcome.md", tmp_notes)
        assert "Getting Started" in result["links"]
        assert "Writing Notes" in result["links"]
        assert "About Me" in result["links"]

    def test_frontmatter_tags(self, tmp_notes):
        result = parse_note(tmp_notes / "Welcome.md", tmp_notes)
        assert "brain" in result["tags"]
        assert "getting-started" in result["tags"]

    def test_inline_tags(self, tmp_notes):
        result = parse_note(tmp_notes / "Tutorials" / "Writing Notes.md", tmp_notes)
        assert "markdown" in result["tags"]
        assert "syntax" in result["tags"]

    def test_tag_deduplication(self, tmp_notes):
        # Writing Notes has "markdown" and "syntax" in both frontmatter and body
        result = parse_note(tmp_notes / "Tutorials" / "Writing Notes.md", tmp_notes)
        assert result["tags"].count("markdown") == 1
        assert result["tags"].count("syntax") == 1

    def test_relative_path_subfolder(self, tmp_notes):
        result = parse_note(tmp_notes / "Tutorials" / "Getting Started.md", tmp_notes)
        assert result["path"] == "Tutorials/Getting Started.md"

    def test_frontmatter_extraction(self, tmp_notes):
        result = parse_note(tmp_notes / "Welcome.md", tmp_notes)
        assert "tags" in result["metadata"]

    def test_about_me_tags(self, tmp_notes):
        result = parse_note(tmp_notes / "About Me.md", tmp_notes)
        assert "personal" in result["tags"]
        assert "agent-context" in result["tags"]

    def test_malformed_frontmatter(self, tmp_path):
        bad = tmp_path / "bad.md"
        bad.write_text("---\ntags: [unclosed\n---\nSome content here")
        result = parse_note(bad, tmp_path)
        assert result["title"] == "bad"
        assert result["path"] == "bad.md"
        # Should still have content even though frontmatter parsing failed
        assert "Some content" in result["content"]


class TestListNotes:
    def test_finds_md_files(self, tmp_notes):
        notes = list_notes(tmp_notes)
        names = [n.name for n in notes]
        assert "Welcome.md" in names
        assert "About Me.md" in names
        assert "Getting Started.md" in names

    def test_ignores_non_md(self, tmp_notes):
        notes = list_notes(tmp_notes)
        names = [n.name for n in notes]
        assert "image.png" not in names

    def test_recursive(self, tmp_notes):
        notes = list_notes(tmp_notes)
        paths = [str(n.relative_to(tmp_notes)) for n in notes]
        assert any("Tutorials" in p for p in paths)

    def test_finds_all_seed_notes(self, tmp_notes):
        notes = list_notes(tmp_notes)
        assert len(notes) == 5


class TestWriteNote:
    def test_creates_file(self, tmp_path):
        path = write_note(tmp_path, "New Note", "Hello world")
        assert path.exists()
        assert path.name == "New Note.md"

    def test_content_with_frontmatter(self, tmp_path):
        path = write_note(tmp_path, "Test", "Body", tags=["a", "b"])
        text = path.read_text()
        assert "tags:" in text
        assert "Body" in text

    def test_folder_creation(self, tmp_path):
        path = write_note(tmp_path, "Sub", "Content", folder="A/B")
        assert path.exists()
        assert "A/B" in str(path.relative_to(tmp_path))

    def test_metadata(self, tmp_path):
        path = write_note(tmp_path, "Meta", "Body", metadata={"author": "Dan"})
        text = path.read_text()
        assert "author: Dan" in text

    def test_rejects_folder_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="escapes notes"):
            write_note(tmp_path, "evil", "pwned", folder="../../etc")

    def test_rejects_title_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="escapes notes"):
            write_note(tmp_path, "../../../etc/cron.d/backdoor", "pwned")


class TestRewriteNote:
    def test_preserves_frontmatter(self, tmp_path):
        write_note(tmp_path, "Existing", "Old body", tags=["keep"])
        rewrite_note(tmp_path, "Existing", "New body")
        import frontmatter

        post = frontmatter.load(str(tmp_path / "Existing.md"))
        assert post.content == "New body"
        assert "keep" in post.metadata.get("tags", [])

    def test_updates_content(self, tmp_path):
        write_note(tmp_path, "Edit", "Before")
        rewrite_note(tmp_path, "Edit", "After")
        text = (tmp_path / "Edit.md").read_text()
        assert "After" in text

    def test_re_extracts_tags(self, tmp_path):
        write_note(tmp_path, "Tags", "Old #old")
        rewrite_note(tmp_path, "Tags", "New #new")
        import frontmatter

        post = frontmatter.load(str(tmp_path / "Tags.md"))
        assert "new" in post.metadata["tags"]

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            rewrite_note(tmp_path, "Missing", "content")

    def test_relative_path(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        write_note(tmp_path, "Deep", "Content", folder="sub")
        path = rewrite_note(tmp_path, "Deep", "Updated", relative_path="sub/Deep.md")
        assert path.exists()
        assert "Updated" in path.read_text()

    def test_rejects_relative_path_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="escapes notes"):
            rewrite_note(tmp_path, "evil", "pwned", relative_path="../../.bashrc")

    def test_rejects_title_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="escapes notes"):
            rewrite_note(tmp_path, "../../../evil", "pwned")


class TestDeleteNote:
    def test_deletes_file(self, tmp_path):
        write_note(tmp_path, "Doomed", "goodbye")
        assert (tmp_path / "Doomed.md").exists()
        result = delete_note(tmp_path, "Doomed.md")
        assert not (tmp_path / "Doomed.md").exists()
        # delete_note now moves to trash and returns the trash path
        assert result.exists()
        assert ".trash" in result.parts

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            delete_note(tmp_path, "nonexistent.md")

    def test_rejects_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="escapes notes"):
            delete_note(tmp_path, "../../etc/passwd")


class TestInitNotes:
    def test_copies_seed_notes_to_empty_dir(self, tmp_path):
        count = init_notes(tmp_path)
        assert count == 5
        assert (tmp_path / "Welcome.md").exists()
        assert (tmp_path / "About Me.md").exists()
        assert (tmp_path / "Tutorials" / "Getting Started.md").exists()
        assert (tmp_path / "Tutorials" / "Writing Notes.md").exists()
        assert (tmp_path / "Tutorials" / "Using the Agent.md").exists()

    def test_creates_directory_if_missing(self, tmp_path):
        notes_dir = tmp_path / "new_notes"
        count = init_notes(notes_dir)
        assert count == 5
        assert notes_dir.exists()
        assert (notes_dir / "Welcome.md").exists()

    def test_skips_if_has_notes(self, tmp_path):
        (tmp_path / "existing.md").write_text("My note")
        count = init_notes(tmp_path)
        assert count == 0
        assert not (tmp_path / "Welcome.md").exists()

    def test_seed_notes_dir_exists(self):
        assert SEED_NOTES_DIR.is_dir()
        seed_notes = list(SEED_NOTES_DIR.rglob("*.md"))
        assert len(seed_notes) == 5


class TestParseNoteRegexFixes:
    def test_wikilink_strips_heading_anchor(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Link to [[MyNote#Section One]] here")
        result = parse_note(f, tmp_path)
        assert "MyNote" in result["links"]
        assert not any("#" in link for link in result["links"])

    def test_wikilink_strips_block_ref(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("See [[Reference^abc123]] for details")
        result = parse_note(f, tmp_path)
        assert "Reference" in result["links"]
        assert not any("^" in link for link in result["links"])

    def test_wikilink_skips_image_embeds(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("An image: ![[photo.png]]\nA note: [[Real Note]]")
        result = parse_note(f, tmp_path)
        assert "Real Note" in result["links"]
        assert "photo" not in result["links"]
        assert "photo.png" not in result["links"]

    def test_wikilink_skips_pdf_embeds(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("See ![[report.pdf]]")
        result = parse_note(f, tmp_path)
        assert result["links"] == []

    def test_tags_not_extracted_from_code_blocks(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("Real #valid tag\n\n```\n#fake-tag\n```\n\nMore #real text")
        result = parse_note(f, tmp_path)
        assert "valid" in result["tags"]
        assert "real" in result["tags"]
        assert "fake-tag" not in result["tags"]

    def test_tag_case_insensitive_dedup(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("#Python and #python are the same")
        result = parse_note(f, tmp_path)
        assert result["tags"].count("python") == 1
        assert "Python" not in result["tags"]

    def test_wikilink_with_heading_and_alias(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("See [[Deep Note#Intro|introduction]]")
        result = parse_note(f, tmp_path)
        assert "Deep Note" in result["links"]

    def test_wikilink_folder_path_with_anchor(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("See [[Projects/MyProject#Overview]]")
        result = parse_note(f, tmp_path)
        assert "MyProject" in result["links"]

    def test_wikilink_deduplication(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("See [[About Me]] and also [[About Me]] again")
        result = parse_note(f, tmp_path)
        assert result["links"].count("About Me") == 1

    def test_wikilinks_dedup_preserves_order(self, tmp_path):
        """Dedup preserves first-seen order: [[A]] [[B]] [[A]] → ["A", "B"]."""
        f = tmp_path / "test.md"
        f.write_text("Link [[A]] then [[B]] then [[A]] again")
        result = parse_note(f, tmp_path)
        assert result["links"] == ["A", "B"]

    def test_wikilinks_dedup_case_preserving(self, tmp_path):
        """Exact-match dedup means [[About Me]] and [[about me]] are both kept."""
        f = tmp_path / "test.md"
        f.write_text("See [[About Me]] and [[about me]]")
        result = parse_note(f, tmp_path)
        assert "About Me" in result["links"]
        assert "about me" in result["links"]
        assert len(result["links"]) == 2

    def test_wikilinks_dedup_with_aliases(self, tmp_path):
        """[[Note|alias]] and [[Note]] resolve to same target, deduped."""
        f = tmp_path / "test.md"
        f.write_text("See [[Note|alias]] and [[Note]]")
        result = parse_note(f, tmp_path)
        assert result["links"].count("Note") == 1


class TestRewriteNoteRegexFixes:
    def test_rewrite_strips_code_block_tags(self, tmp_path):
        write_note(tmp_path, "CodeTest", "old content")
        rewrite_note(tmp_path, "CodeTest", "New #real\n```\n#fake\n```")
        import frontmatter

        post = frontmatter.load(str(tmp_path / "CodeTest.md"))
        assert "real" in post.metadata["tags"]
        assert "fake" not in post.metadata["tags"]

    def test_rewrite_normalizes_tag_case(self, tmp_path):
        write_note(tmp_path, "CaseTest", "old", tags=["KeepTag"])
        rewrite_note(tmp_path, "CaseTest", "New #python content")
        import frontmatter

        post = frontmatter.load(str(tmp_path / "CaseTest.md"))
        assert "python" in post.metadata["tags"]
        assert "keeptag" in post.metadata["tags"]
        assert "KeepTag" not in post.metadata["tags"]


class TestImportVault:
    def test_imports_md_files(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        dest.mkdir()
        (source / "note1.md").write_text("# Note 1")
        (source / "note2.md").write_text("# Note 2")

        stats = import_vault(source, dest)
        assert stats["files_copied"] == 2
        assert (dest / "note1.md").exists()
        assert (dest / "note2.md").exists()

    def test_preserves_folder_structure(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        (source / "Projects").mkdir(parents=True)
        (source / "Projects" / "task.md").write_text("# Task")

        stats = import_vault(source, dest)
        assert stats["files_copied"] == 1
        assert stats["folders_created"] >= 1
        assert (dest / "Projects" / "task.md").exists()

    def test_skips_obsidian_dir(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        (source / ".obsidian").mkdir(parents=True)
        (source / ".obsidian" / "config.md").write_text("config")
        (source / "real.md").write_text("# Real")

        stats = import_vault(source, dest)
        assert stats["files_copied"] == 1
        assert stats["files_skipped"] == 1
        assert not (dest / ".obsidian").exists()

    def test_skips_git_dir(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        (source / ".git").mkdir(parents=True)
        (source / ".git" / "hooks.md").write_text("hook")
        (source / "note.md").write_text("# Note")

        stats = import_vault(source, dest)
        assert stats["files_copied"] == 1
        assert not (dest / ".git").exists()

    def test_skips_trash_dir(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        (source / ".trash").mkdir(parents=True)
        (source / ".trash" / "deleted.md").write_text("deleted")
        (source / "note.md").write_text("# Note")

        stats = import_vault(source, dest)
        assert stats["files_copied"] == 1
        assert stats["files_skipped"] == 1

    def test_rejects_nonexistent_source(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            import_vault(tmp_path / "nonexistent", tmp_path / "dest")

    def test_rejects_file_as_source(self, tmp_path):
        source_file = tmp_path / "file.txt"
        source_file.write_text("not a dir")
        with pytest.raises(ValueError, match="not a directory"):
            import_vault(source_file, tmp_path / "dest")

    def test_rejects_same_directory(self, tmp_path):
        with pytest.raises(ValueError, match="same directory"):
            import_vault(tmp_path, tmp_path)

    def test_rejects_overlapping_directories(self, tmp_path):
        parent = tmp_path / "parent"
        child = parent / "child"
        parent.mkdir()
        child.mkdir()
        with pytest.raises(ValueError, match="inside"):
            import_vault(parent, child)

    def test_creates_dest_if_missing(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "new_dest"
        source.mkdir()
        (source / "note.md").write_text("# Note")

        stats = import_vault(source, dest)
        assert dest.exists()
        assert stats["files_copied"] == 1

    def test_only_copies_md_files(self, tmp_path):
        source = tmp_path / "source"
        dest = tmp_path / "dest"
        source.mkdir()
        (source / "note.md").write_text("# Note")
        (source / "image.png").write_bytes(b"\x89PNG")
        (source / "data.json").write_text("{}")

        stats = import_vault(source, dest)
        assert stats["files_copied"] == 1
        assert not (dest / "image.png").exists()
        assert not (dest / "data.json").exists()
