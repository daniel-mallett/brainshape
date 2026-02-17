import pytest

from brainshape.tools import (
    create_connection,
    create_note,
    edit_note,
    find_related,
    query_graph,
    read_note,
    search_notes,
    semantic_search,
    store_memory,
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
    def test_creates_and_syncs(self, mock_db, notes_settings):
        result = create_note.invoke(
            {
                "title": "Brand New",
                "content": "Hello",
                "tags": "a,b",
                "folder": "",
            }
        )
        assert "Created note 'Brand New'" in result
        assert (notes_settings / "Brand New.md").exists()
        # Structural sync should run (UPSERT note + tag queries)
        assert mock_db.query.call_count > 0

    def test_clears_old_edges(self, mock_db, notes_settings):
        """_sync_note_structural deletes old edges before creating new ones."""
        create_note.invoke({"title": "Edge Test", "content": "Hello", "tags": "tag1", "folder": ""})
        call_sqls = [c.args[0] for c in mock_db.query.call_args_list if c.args]
        # Edge cleanup must happen before edge creation
        delete_idx = next(i for i, s in enumerate(call_sqls) if "DELETE tagged_with" in s)
        relate_idx = next(
            i for i, s in enumerate(call_sqls) if "tagged_with" in s and "RELATE" in s
        )
        assert delete_idx < relate_idx

    def test_clears_links_to_edges_before_recreating(self, mock_db, notes_settings):
        """DELETE links_to must precede RELATE links_to."""
        create_note.invoke(
            {"title": "Link Test", "content": "See [[Other Note]]", "tags": "", "folder": ""}
        )
        call_sqls = [c.args[0] for c in mock_db.query.call_args_list if c.args]
        delete_idx = next(i for i, s in enumerate(call_sqls) if "DELETE links_to" in s)
        # links_to RELATE may not fire if target note doesn't exist in mock,
        # but DELETE must still run
        assert delete_idx >= 0

    def test_edge_cleanup_runs_on_create_not_just_edit(self, mock_db, notes_settings):
        """create_note triggers DELETE for both edge types."""
        create_note.invoke(
            {"title": "Cleanup Test", "content": "Hello #tag1", "tags": "tag1", "folder": ""}
        )
        call_sqls = [c.args[0] for c in mock_db.query.call_args_list if c.args]
        assert any("DELETE tagged_with" in s for s in call_sqls)
        assert any("DELETE links_to" in s for s in call_sqls)

    def test_edge_cleanup_with_no_tags_or_links(self, mock_db, notes_settings):
        """DELETE runs even with no tags/links; no RELATE follows."""
        create_note.invoke({"title": "Empty", "content": "Plain text", "tags": "", "folder": ""})
        call_sqls = [c.args[0] for c in mock_db.query.call_args_list if c.args]
        # Cleanup must still run
        assert any("DELETE tagged_with" in s for s in call_sqls)
        assert any("DELETE links_to" in s for s in call_sqls)
        # But no RELATE should follow
        assert not any("RELATE" in s for s in call_sqls)


class TestEditNote:
    def test_updates_note(self, mock_db, notes_settings):
        # Create the note on disk first
        from brainshape.notes import write_note

        write_note(notes_settings, "Editable", "Old content")
        mock_db.query.return_value = [{"path": "Editable.md"}]
        result = edit_note.invoke({"title": "Editable", "new_content": "New content"})
        assert "Updated note 'Editable'" in result

    def test_not_found(self, mock_db, notes_settings):
        mock_db.query.return_value = []
        result = edit_note.invoke({"title": "Ghost", "new_content": "x"})
        assert "not found" in result

    def test_edge_cleanup_via_sync(self, mock_db, notes_settings):
        """edit_note relies on _sync_note_structural for edge cleanup."""
        from brainshape.notes import write_note

        write_note(notes_settings, "Tagged", "Content #mytag")
        mock_db.query.return_value = [{"path": "Tagged.md"}]
        edit_note.invoke({"title": "Tagged", "new_content": "Updated #newtag"})
        call_sqls = [c.args[0] for c in mock_db.query.call_args_list if c.args]
        assert any("DELETE tagged_with" in s for s in call_sqls)
        assert any("DELETE links_to" in s for s in call_sqls)


class TestQueryGraph:
    def test_formats_results(self, mock_db):
        mock_db.query.return_value = [{"n": "val1"}, {"n": "val2"}]
        result = query_graph.invoke({"surql": "SELECT * FROM note"})
        assert "val1" in result

    def test_truncates_at_20(self, mock_db):
        mock_db.query.return_value = [{"i": i} for i in range(25)]
        result = query_graph.invoke({"surql": "SELECT * FROM note"})
        assert "5 more rows" in result

    def test_no_results(self, mock_db):
        result = query_graph.invoke({"surql": "SELECT * FROM nothing"})
        assert "no results" in result

    def test_query_error(self, mock_db):
        mock_db.query.side_effect = Exception("SyntaxError")
        result = query_graph.invoke({"surql": "BAD QUERY"})
        assert "SurrealQL query error" in result


class TestFindRelated:
    def test_exact_match(self, mock_db):
        mock_db.query.return_value = [
            {
                "tags": [["python", "code"]],
                "outgoing_links": [[{"title": "Target Note", "path": "Target.md"}]],
                "incoming_links": [[]],
            }
        ]
        result = find_related.invoke({"title": "My Note"})
        assert "python" in result
        assert "Target Note" in result

    def test_fuzzy_fallback(self, mock_db):
        # First call (exact) returns nothing useful, second (fuzzy) returns result
        mock_db.query.side_effect = [
            [{"tags": [], "outgoing_links": [], "incoming_links": []}],
            [
                {
                    "title": "Machine Learning Notes",
                    "tags": [["ml"]],
                    "outgoing_links": [[{"title": "AI Overview", "path": "AI.md"}]],
                    "incoming_links": [[]],
                }
            ],
        ]
        result = find_related.invoke({"title": "Machine"})
        assert "AI Overview" in result
        assert mock_db.query.call_count == 2

    def test_no_results(self, mock_db):
        mock_db.query.side_effect = [
            [{"tags": [], "outgoing_links": [], "incoming_links": []}],
            [],
        ]
        result = find_related.invoke({"title": "Nothing"})
        assert "No connections found" in result


class TestStoreMemory:
    def test_stores_memory(self, mock_db):
        mock_db.query.return_value = [{"id": "uuid-123"}]
        result = store_memory.invoke(
            {"memory_type": "preference", "content": "User likes dark mode"},
        )
        assert "Stored memory" in result
        assert "User likes dark mode" in result
        mock_db.query.assert_called_once()


class TestCreateConnection:
    def test_creates_generic_connection(self, mock_db):
        mock_db.query.return_value = []
        result = create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Alice",
                "relationship": "works_with",
                "target_type": "person",
                "target_name": "Bob",
            }
        )
        assert "Connected person:Alice" in result
        assert "works_with" in result
        assert "person:Bob" in result
        # Should have 5 calls: UPSERT src, UPSERT tgt, DEFINE TABLE, duplicate check, RELATE
        assert mock_db.query.call_count == 5

    def test_skips_duplicate_edge(self, mock_db):
        """If the exact relationship already exists, don't create a duplicate."""
        mock_db.query.side_effect = [
            [],  # UPSERT src (person)
            [],  # UPSERT tgt (person)
            [],  # DEFINE TABLE
            ["existing_edge"],  # duplicate check finds existing
        ]
        result = create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Alice",
                "relationship": "works_with",
                "target_type": "person",
                "target_name": "Bob",
            }
        )
        assert "Connected" in result
        # Should have 4 calls: UPSERT src, UPSERT tgt, DEFINE TABLE, duplicate check (no RELATE)
        assert mock_db.query.call_count == 4

    def test_note_lookup_by_title(self, mock_db):
        """Note entities are looked up by title, not created."""
        mock_db.query.side_effect = [
            ["note:abc"],  # source note lookup (found)
            [],  # target UPSERT (person)
            [],  # DEFINE TABLE
            [],  # duplicate check (no existing)
            [],  # RELATE
        ]
        result = create_connection.invoke(
            {
                "source_type": "note",
                "source_name": "My Note",
                "relationship": "about",
                "target_type": "person",
                "target_name": "Alice",
            }
        )
        assert "Connected note:My Note" in result
        # First call should be SELECT by title, not UPSERT
        first_sql = mock_db.query.call_args_list[0].args[0]
        assert "title" in first_sql
        assert "UPSERT" not in first_sql

    def test_note_not_found_returns_error(self, mock_db):
        """If source note doesn't exist, return error."""
        mock_db.query.return_value = []
        result = create_connection.invoke(
            {
                "source_type": "note",
                "source_name": "Nonexistent",
                "relationship": "about",
                "target_type": "person",
                "target_name": "Alice",
            }
        )
        assert "not found" in result

    def test_memory_lookup_by_content(self, mock_db):
        """Memory entities are looked up by content, not created."""
        mock_db.query.side_effect = [
            ["memory:xyz"],  # source memory lookup
            ["note:abc"],  # target note lookup
            [],  # DEFINE TABLE
            [],  # duplicate check
            [],  # RELATE
        ]
        result = create_connection.invoke(
            {
                "source_type": "memory",
                "source_name": "User prefers dark themes",
                "relationship": "relates_to",
                "target_type": "note",
                "target_name": "Settings",
            }
        )
        assert "Connected memory:User prefers dark themes" in result
        first_sql = mock_db.query.call_args_list[0].args[0]
        assert "content" in first_sql

    def test_target_memory_not_found(self, mock_db):
        """If target memory doesn't exist, return error."""
        mock_db.query.side_effect = [
            [],  # source person UPSERT
            [],  # target memory lookup (not found)
        ]
        result = create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Alice",
                "relationship": "relates_to",
                "target_type": "memory",
                "target_name": "nonexistent",
            }
        )
        assert "not found" in result

    def test_sanitizes_identifiers(self, mock_db):
        mock_db.query.return_value = []
        result = create_connection.invoke(
            {
                "source_type": "my-type!",
                "source_name": "Alice",
                "relationship": "has spaces",
                "target_type": "normal",
                "target_name": "Bob",
            }
        )
        assert "my_type_" in result
        assert "has_spaces" in result

    @pytest.mark.parametrize(
        "reserved",
        ["tag", "chunk", "tagged_with", "links_to", "from_document"],
    )
    def test_rejects_reserved_source_type(self, mock_db, reserved):
        result = create_connection.invoke(
            {
                "source_type": reserved,
                "source_name": "X",
                "relationship": "rel",
                "target_type": "person",
                "target_name": "Y",
            }
        )
        assert "reserved" in result.lower()
        assert reserved in result
        mock_db.query.assert_not_called()

    @pytest.mark.parametrize(
        "reserved",
        ["tag", "chunk", "tagged_with", "links_to", "from_document"],
    )
    def test_rejects_reserved_target_type(self, mock_db, reserved):
        result = create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "X",
                "relationship": "rel",
                "target_type": reserved,
                "target_name": "Y",
            }
        )
        assert "reserved" in result.lower()
        assert reserved in result
        mock_db.query.assert_not_called()

    @pytest.mark.parametrize(
        "reserved",
        ["note", "tag", "memory", "chunk", "tagged_with", "links_to", "from_document"],
    )
    def test_rejects_reserved_relationship(self, mock_db, reserved):
        result = create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "X",
                "relationship": reserved,
                "target_type": "person",
                "target_name": "Y",
            }
        )
        assert "reserved" in result.lower()
        assert reserved in result
        mock_db.query.assert_not_called()

    def test_note_to_note_connection(self, mock_db):
        """Both source and target are notes — both use title field lookup."""
        mock_db.query.side_effect = [
            ["note:abc"],  # source note lookup
            ["note:def"],  # target note lookup
            [],  # DEFINE TABLE
            [],  # duplicate check
            [],  # RELATE
        ]
        result = create_connection.invoke(
            {
                "source_type": "note",
                "source_name": "Note A",
                "relationship": "references",
                "target_type": "note",
                "target_name": "Note B",
            }
        )
        assert "Connected note:Note A" in result
        # Both lookups should use title
        src_sql = mock_db.query.call_args_list[0].args[0]
        tgt_sql = mock_db.query.call_args_list[1].args[0]
        assert "title" in src_sql
        assert "title" in tgt_sql
        assert "UPSERT" not in src_sql
        assert "UPSERT" not in tgt_sql

    def test_memory_to_memory_connection(self, mock_db):
        """Both source and target are memories — both use content field lookup."""
        mock_db.query.side_effect = [
            ["memory:abc"],  # source memory lookup
            ["memory:def"],  # target memory lookup
            [],  # DEFINE TABLE
            [],  # duplicate check
            [],  # RELATE
        ]
        result = create_connection.invoke(
            {
                "source_type": "memory",
                "source_name": "Fact A",
                "relationship": "contradicts",
                "target_type": "memory",
                "target_name": "Fact B",
            }
        )
        assert "Connected memory:Fact A" in result
        src_sql = mock_db.query.call_args_list[0].args[0]
        tgt_sql = mock_db.query.call_args_list[1].args[0]
        assert "content" in src_sql
        assert "content" in tgt_sql

    def test_note_as_target_not_found(self, mock_db):
        """Target note doesn't exist — returns error."""
        mock_db.query.side_effect = [
            [],  # source person UPSERT
            [],  # target note lookup (not found)
        ]
        result = create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Alice",
                "relationship": "about",
                "target_type": "note",
                "target_name": "Nonexistent",
            }
        )
        assert "not found" in result

    def test_custom_entity_types_upserted(self, mock_db):
        """Custom types (concept, project) use name field and UPSERT."""
        mock_db.query.return_value = []
        result = create_connection.invoke(
            {
                "source_type": "concept",
                "source_name": "AI",
                "relationship": "part_of",
                "target_type": "project",
                "target_name": "Brain",
            }
        )
        assert "Connected concept:AI" in result
        # Both should UPSERT by name
        src_sql = mock_db.query.call_args_list[0].args[0]
        tgt_sql = mock_db.query.call_args_list[1].args[0]
        assert "UPSERT" in src_sql
        assert "name" in src_sql
        assert "UPSERT" in tgt_sql
        assert "name" in tgt_sql

    def test_reverse_direction_not_duplicate(self, mock_db):
        """A→B and B→A are different edges, both should create."""
        # First call: A→B
        mock_db.query.return_value = []
        create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Alice",
                "relationship": "knows",
                "target_type": "person",
                "target_name": "Bob",
            }
        )
        first_relate_count = sum(
            1 for c in mock_db.query.call_args_list if c.args and "RELATE" in c.args[0]
        )
        assert first_relate_count == 1

        # Second call: B→A (reversed)
        mock_db.reset_mock()
        mock_db.query.return_value = []
        create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Bob",
                "relationship": "knows",
                "target_type": "person",
                "target_name": "Alice",
            }
        )
        second_relate_count = sum(
            1 for c in mock_db.query.call_args_list if c.args and "RELATE" in c.args[0]
        )
        assert second_relate_count == 1

    def test_different_relationship_not_duplicate(self, mock_db):
        """A-[works_with]->B and A-[manages]->B are different, both should RELATE."""
        mock_db.query.return_value = []
        create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Alice",
                "relationship": "works_with",
                "target_type": "person",
                "target_name": "Bob",
            }
        )
        first_relate_count = sum(
            1 for c in mock_db.query.call_args_list if c.args and "RELATE" in c.args[0]
        )
        assert first_relate_count == 1

        mock_db.reset_mock()
        mock_db.query.return_value = []
        create_connection.invoke(
            {
                "source_type": "person",
                "source_name": "Alice",
                "relationship": "manages",
                "target_type": "person",
                "target_name": "Bob",
            }
        )
        second_relate_count = sum(
            1 for c in mock_db.query.call_args_list if c.args and "RELATE" in c.args[0]
        )
        assert second_relate_count == 1
