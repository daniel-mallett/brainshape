# Agent Tools

## Overview

The Brain agent has 9 tools, all defined as plain Python functions in `brain/tools.py`. LangChain's `create_agent` infers the tool schema from type hints and docstrings.

Tools use module-level `db` and `pipeline` variables set by `create_brain_agent()` in `agent.py` before tools are used.

Tool responses only include notes-relative paths — absolute system paths are never exposed to the agent.

## Tool Reference

### 1. search_notes(query: str)
Full-text keyword search across notes using SurrealDB's BM25 fulltext index. Returns up to 10 results with titles, paths, snippets, and relevance scores.

### 2. semantic_search(query: str)
Vector similarity search over chunk embeddings. Embeds the query text using the pipeline's embedding model, then runs a cosine similarity search against the `chunk_embeddings` HNSW vector index. Returns matching chunks with their parent note title and similarity score. Use when keyword search misses conceptually related content.

### 3. read_note(title: str)
Read the full content of a specific note by title. Queries the graph for the note record and returns its content.

### 4. create_note(title: str, content: str, tags: str = "", folder: str = "")
Create a new note in the notes directory and sync it to the graph. Tags are comma-separated. Folder specifies the subdirectory within the notes directory (e.g., 'Notes', 'Projects/2026'). Flow:
1. Write markdown file to notes directory (with frontmatter)
2. Run structural sync via `_sync_note_structural()` (UPSERT note, create tags, wikilinks)

### 5. edit_note(title: str, new_content: str)
Rewrite an existing note's content while preserving frontmatter. Looks up the note's actual path from the graph so it works with notes in subdirectories. Flow:
1. Query graph for the note's notes-relative path
2. Read existing file, replace content, preserve frontmatter
3. Re-sync structural data via `_sync_note_structural()` (clears old edges, recreates)

### 6. query_graph(surql: str)
Run arbitrary SurrealQL queries against the knowledge graph. The agent constructs SurrealQL based on its understanding of the graph schema (described in its system prompt). Returns up to 20 result rows. This is the most powerful tool — it can traverse both structural and semantic layers.

### 7. find_related(title: str)
Find notes and knowledge related to a given note title. Shows wikilink connections, shared tags, and any agent-created relationships. First tries exact title match, falls back to case-insensitive substring match.

### 8. store_memory(memory_type: str, content: str)
Store a piece of knowledge about the user as a persistent memory. The agent uses this whenever it learns something worth remembering: preferences, personal info, goals, project details, etc. Creates a `memory` record with a UUID, type, content, and timestamp.

### 9. create_connection(source_type, source_name, relationship, target_type, target_name)
Create entities and a relationship between them in the knowledge graph. Used to model the user's world: people, projects, concepts, and how they relate.

- For `note` and `memory` types, the entity must already exist (looked up by title or content respectively).
- For other types (person, project, concept, etc.), entities are created automatically via UPSERT if they don't exist.
- Reserved table names (`note`, `tag`, `memory`, `chunk`, `tagged_with`, `links_to`, `from_document`) are blocked as relationship names to prevent schema corruption.
- Edge tables are defined as `TYPE RELATION` so they appear in graph visualization.
- Duplicate edges (same source, target, and relationship type) are detected and skipped.

## Memory Persistence

The agent stores user preferences, personal info, and things to remember via two dedicated tools:

- **`store_memory`** — creates `memory` records with type, content, and timestamp
- **`create_connection`** — links memories, notes, and custom entities (people, projects, concepts) together in the graph

The system prompt instructs the agent to proactively store memories and create connections when the user shares relevant information.

## Helper: _sync_note_structural()

Shared by `create_note` and `edit_note`. UPSERTs the note record by path, sets properties (path, title, content, modified_at), then:
1. Deletes old `tagged_with` and `links_to` edges (cleanup before recreation)
2. UPSERTs tag records and creates `tagged_with` edges
3. Creates `links_to` edges for wikilinks (only if target note exists)

Edge cleanup runs unconditionally, even if the note has no tags or links, ensuring stale edges from previous edits are always removed.

## System Prompt

The agent's system prompt (in `agent.py`) describes the full graph schema so the agent can construct meaningful SurrealQL queries. It includes instructions to:
- Use keyword vs semantic search appropriately
- Place notes in the right folder
- Preserve user's voice when editing notes
- Persist memories and preferences via `store_memory` and `create_connection`
- Use markdown conventions (wikilinks, tags, headings)
