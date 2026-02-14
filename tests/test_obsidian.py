import pytest

from brain.obsidian import (
    compute_file_hash,
    list_notes,
    parse_note,
    rewrite_note,
    write_note,
)


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
    def test_simple_note(self, tmp_vault):
        result = parse_note(tmp_vault / "Simple.md", tmp_vault)
        assert result["title"] == "Simple"
        assert result["path"] == "Simple.md"
        assert "Just some content." in result["content"]
        assert result["links"] == []
        assert result["tags"] == []

    def test_wikilinks(self, tmp_vault):
        result = parse_note(tmp_vault / "Linked.md", tmp_vault)
        assert "Simple" in result["links"]
        assert "Tagged" in result["links"]

    def test_aliased_wikilink(self, tmp_vault):
        result = parse_note(tmp_vault / "Linked.md", tmp_vault)
        # [[Tagged|my tagged note]] should extract "Tagged"
        assert "Tagged" in result["links"]

    def test_folder_wikilink(self, tmp_vault):
        result = parse_note(tmp_vault / "Projects" / "Deep.md", tmp_vault)
        # [[folder/Page]] should extract "Page" (last segment)
        assert "Page" in result["links"]

    def test_frontmatter_tags(self, tmp_vault):
        result = parse_note(tmp_vault / "Tagged.md", tmp_vault)
        assert "python" in result["tags"]
        assert "project" in result["tags"]

    def test_body_tags(self, tmp_vault):
        result = parse_note(tmp_vault / "Tagged.md", tmp_vault)
        assert "inline" in result["tags"]

    def test_tag_deduplication(self, tmp_path):
        f = tmp_path / "Dup.md"
        f.write_text("---\ntags:\n  - dup\n---\nSome #dup tag.\n")
        result = parse_note(f, tmp_path)
        assert result["tags"].count("dup") == 1

    def test_nested_tags(self, tmp_vault):
        result = parse_note(tmp_vault / "Projects" / "Deep.md", tmp_vault)
        assert "nested/tag" in result["tags"]

    def test_vault_relative_path_subfolder(self, tmp_vault):
        result = parse_note(tmp_vault / "Projects" / "Deep.md", tmp_vault)
        assert result["path"] == "Projects/Deep.md"

    def test_frontmatter_extraction(self, tmp_vault):
        result = parse_note(tmp_vault / "Tagged.md", tmp_vault)
        assert "tags" in result["metadata"]

    def test_string_tag_in_frontmatter(self, tmp_vault):
        result = parse_note(tmp_vault / "Projects" / "Deep.md", tmp_vault)
        # tags: research (string, not list)
        assert "research" in result["tags"]


class TestListNotes:
    def test_finds_md_files(self, tmp_vault):
        notes = list_notes(tmp_vault)
        names = [n.name for n in notes]
        assert "Simple.md" in names
        assert "Tagged.md" in names
        assert "Deep.md" in names

    def test_ignores_non_md(self, tmp_vault):
        notes = list_notes(tmp_vault)
        names = [n.name for n in notes]
        assert "image.png" not in names

    def test_recursive(self, tmp_vault):
        notes = list_notes(tmp_vault)
        paths = [str(n.relative_to(tmp_vault)) for n in notes]
        assert any("Projects" in p for p in paths)


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
