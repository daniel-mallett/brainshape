from brain.tools import (
    create_note,
    edit_note,
    find_related,
    query_graph,
    read_note,
    search_notes,
    semantic_search,
)


class TestSearchNotes:
    def test_formats_results(self, mock_db):
        mock_db.query.return_value = [
            {"title": "Note A", "path": "A.md", "snippet": "some text", "score": 0.95},
        ]
        result = search_notes.invoke({"query": "test"})
        assert "Note A" in result
        assert "0.95" in result

    def test_no_results(self, mock_db):
        result = search_notes.invoke({"query": "nothing"})
        assert "No notes found" in result


class TestSemanticSearch:
    def test_calls_embed_and_formats(self, mock_db, mock_pipeline):
        mock_db.query.return_value = [
            {"title": "Semantic", "path": "S.md", "chunk": "relevant chunk", "score": 0.88},
        ]
        result = semantic_search.invoke({"query": "meaning"})
        assert "Semantic" in result
        assert "0.88" in result
        mock_pipeline.embed_query.assert_called_once_with("meaning")

    def test_no_results(self, mock_db, mock_pipeline):
        result = semantic_search.invoke({"query": "nothing"})
        assert "No semantically similar" in result


class TestReadNote:
    def test_returns_content(self, mock_db):
        mock_db.query.return_value = [
            {"title": "My Note", "path": "My Note.md", "content": "The body"},
        ]
        result = read_note.invoke({"title": "My Note"})
        assert "# My Note" in result
        assert "The body" in result

    def test_not_found(self, mock_db):
        result = read_note.invoke({"title": "Nope"})
        assert "not found" in result


class TestCreateNote:
    def test_creates_and_syncs(self, mock_db, mock_pipeline, vault_settings):
        result = create_note.invoke(
            {
                "title": "Brand New",
                "content": "Hello",
                "tags": "a,b",
                "folder": "",
            }
        )
        assert "Created note 'Brand New'" in result
        assert (vault_settings / "Brand New.md").exists()
        mock_pipeline.run.assert_called_once()
        assert mock_db.query.call_count > 0

    def test_pipeline_failure_graceful(self, mock_db, mock_pipeline, vault_settings):
        mock_pipeline.run.side_effect = RuntimeError("LLM down")
        result = create_note.invoke(
            {
                "title": "Fail Note",
                "content": "Body",
            }
        )
        assert "semantic extraction failed" in result
        assert (vault_settings / "Fail Note.md").exists()


class TestEditNote:
    def test_updates_note(self, mock_db, mock_pipeline, vault_settings):
        # Create the note on disk first
        from brain.obsidian import write_note

        write_note(vault_settings, "Editable", "Old content")
        mock_db.query.return_value = [{"path": "Editable.md"}]
        result = edit_note.invoke({"title": "Editable", "new_content": "New content"})
        assert "Updated note 'Editable'" in result

    def test_not_found(self, mock_db, vault_settings):
        mock_db.query.return_value = []
        result = edit_note.invoke({"title": "Ghost", "new_content": "x"})
        assert "not found" in result


class TestQueryGraph:
    def test_formats_results(self, mock_db):
        mock_db.query.return_value = [{"n": "val1"}, {"n": "val2"}]
        result = query_graph.invoke({"cypher": "MATCH (n) RETURN n"})
        assert "val1" in result

    def test_truncates_at_20(self, mock_db):
        mock_db.query.return_value = [{"i": i} for i in range(25)]
        result = query_graph.invoke({"cypher": "MATCH (n) RETURN n"})
        assert "5 more rows" in result

    def test_no_results(self, mock_db):
        result = query_graph.invoke({"cypher": "MATCH (n:Nothing) RETURN n"})
        assert "no results" in result

    def test_cypher_error(self, mock_db):
        mock_db.query.side_effect = Exception("SyntaxError")
        result = query_graph.invoke({"cypher": "BAD QUERY"})
        assert "Cypher query error" in result


class TestFindRelated:
    def test_exact_match(self, mock_db):
        mock_db.query.return_value = [
            {
                "source_labels": ["Person"],
                "source": "Alice",
                "relationship": "WORKS_ON",
                "target_labels": ["Project"],
                "target": "Brain",
            }
        ]
        result = find_related.invoke({"entity_name": "Alice"})
        assert "Alice" in result
        assert "WORKS_ON" in result
        assert "Brain" in result

    def test_fuzzy_fallback(self, mock_db):
        # First call (exact) returns nothing, second (fuzzy) returns result
        mock_db.query.side_effect = [
            [],
            [
                {
                    "source_labels": ["Concept"],
                    "source": "Machine Learning",
                    "relationship": "RELATED_TO",
                    "target_labels": ["Concept"],
                    "target": "AI",
                }
            ],
        ]
        result = find_related.invoke({"entity_name": "Machine"})
        assert "Machine Learning" in result
        assert mock_db.query.call_count == 2

    def test_no_results(self, mock_db):
        mock_db.query.side_effect = [[], []]
        result = find_related.invoke({"entity_name": "Nothing"})
        assert "No entities found" in result

    def test_long_target_truncated(self, mock_db):
        mock_db.query.return_value = [
            {
                "source_labels": ["Note"],
                "source": "Doc",
                "relationship": "FROM_DOCUMENT",
                "target_labels": ["Chunk"],
                "target": "x" * 200,
            }
        ]
        result = find_related.invoke({"entity_name": "Doc"})
        assert "..." in result
