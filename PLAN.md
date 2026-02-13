# Bug Fixes: Get the app running

## Context

Phase 1 code changes are complete (incremental sync, tool cleanup, pipeline upgrade, CLI commands, batch entry point). But the app crashes on startup with Cypher errors in `sync_structural`. We need to fix these bugs, plus update `kg_pipeline.py` for the neo4j-graphrag v1.13.0 API (deps were upgraded from v1.1.0).

Python was downgraded to 3.13 to work around a pydantic/3.14rc1 incompatibility. All imports pass and `ruff check` is clean.

---

## Fix 1: Wikilink path-as-title bug (brain/obsidian.py + brain/sync.py)

**Problem:** Obsidian wikilinks can contain full paths like `[[LeetCode/2026/ProblemNotes/LC150 Evaluate Reverse Polish Notation]]`. The regex captures the full path as the "link title". Then the wikilink MERGE does:
```cypher
MERGE (target:Note {title: $target_title})
ON CREATE SET target.path = $target_title + '.md'
```
This generates `LeetCode/2026/ProblemNotes/LC150 Evaluate Reverse Polish Notation.md` as the path, which collides with the real note's path → constraint violation.

**Fix in `brain/obsidian.py` line 27:**
```python
links = [link.split("/")[-1] for link in WIKILINK_RE.findall(content)]
```
Strip directory prefixes — wikilinks resolve by note title, not path.

## Fix 2: Wikilink MERGE should not create placeholder nodes with paths (brain/sync.py)

**Problem:** Even after Fix 1, ordering issues remain. If Note A links to Note B, and B hasn't been synced yet, the MERGE creates a placeholder `:Note` node with a made-up path (`title + '.md'`). But B's real path might be in a subdirectory (`subdir/title.md`). Now we have two Note nodes for the same note.

**Fix in `brain/sync.py` wikilinks query (line ~128):**
- Don't create placeholder nodes at all. Only link to notes that already exist.
- Replace `MERGE (target:Note {title: ...})` with `MATCH (target:Note {title: ...})`.
- If the target doesn't exist yet, the link just doesn't get created this sync. It'll appear next time both notes are synced.

```cypher
MATCH (source:Note {path: $source_path})
MATCH (target:Note {title: $target_title})
MERGE (source)-[:LINKS_TO]->(target)
```

This is simpler and avoids all placeholder/duplicate problems. Structural sync runs on startup anyway — after all notes are MERGE'd, the links will resolve.

**But wait — ordering matters.** The current loop creates notes AND their links in one pass. Links to notes that come later alphabetically won't resolve. **Solution: two-pass approach.** First pass: MERGE all note nodes. Second pass: create all tag + link relationships.

```python
# Pass 1: MERGE all note nodes
for note in notes:
    # hash check, MERGE node, store hash
    ...

# Pass 2: create relationships for changed notes
for note in changed_notes:
    # clear old TAGGED_WITH/LINKS_TO
    # create tags
    # create links (MATCH target, not MERGE)
    ...
```

## Fix 3: Schema removal already done (brain/kg_pipeline.py)

Schema types (`SchemaEntity`, `SchemaRelation`, `SchemaBuilder`) were removed per user request — the LLM should auto-discover entities/relationships. No predefined schema. This is already applied.

## Files to modify

1. **`brain/obsidian.py`** — Strip path prefixes from wikilink extraction (line 27)
2. **`brain/sync.py`** — Two-pass sync_structural; MATCH-only for link targets (no placeholders)

## Verification

1. `uv run ruff check` passes
2. `uv run main.py` starts without errors
3. Structural sync processes all 212 notes on first run (no stored hashes)
4. Notes appear in Neo4j with correct paths, titles, tags, and LINKS_TO relationships
5. Second startup skips all notes (hashes match)
6. `/sync` works, `/help` works
