# Knowledge Graph Design

## Core Principle: Single-Table Nodes

Each markdown file is represented as a single record in the `note` table. This record is the hub connecting both the structural world (tags, wikilinks) and the semantic world (chunks with embeddings).

```
(tag) <-tagged_with- (note) <-from_document- (chunk)  [embedding vector]
                       |
                   links_to                    (memory) -relates_to-> (note)
                       v
                     (note) ...                (person), (concept), ... [agent-created]
```

## Two Layers, One Graph

Everything lives in a single SurrealDB embedded database (`surrealkv://`). "Layers" are a conceptual distinction, not physical separation.

### Structural Layer (from our parser in `notes.py`)

Created by `sync_structural()` in `sync.py`. Mirrors the notes directory's explicit connections.

| Table | Properties | Unique Key |
|-------|-----------|------------|
| `note` | `path`, `title`, `content`, `created_at`, `modified_at`, `content_hash` | `path` (notes-relative) |
| `tag` | `name` | `name` |
| `memory` | `mid` (uuid), `type`, `content`, `created_at` | `mid` |

| Relationship | Pattern | Source |
|-------------|---------|--------|
| `links_to` | `note -> note` | Wikilinks `[[Other Note]]` |
| `tagged_with` | `note -> tag` | Tags `#tag` or frontmatter |
| Custom edges | `memory -> note`, `person -> person`, etc. | Agent via `create_connection` tool |

### Semantic Layer (from embedding pipeline in `kg_pipeline.py`)

Created by `sync_semantic()` in `sync.py` using the `KGPipeline` in `kg_pipeline.py`.

| Table | Properties | Created By |
|-------|-----------|------------|
| `chunk` | `text`, `idx`, `embedding` (768-dim vector) | Pipeline (text splitter + embedder) |

| Relationship | Pattern | Created By |
|-------------|---------|------------|
| `from_document` | `chunk -> note` | Pipeline |

Entity tables (`person`, `concept`, `project`, etc.) and their relationships are created by the agent during conversation via `create_connection`, not by automated extraction. This keeps indexing cheap (local embeddings only, no LLM calls) while producing higher-quality entities driven by user context.

## Sync Order

**Structural runs on every startup**, semantic is incremental and user-triggered:

1. `sync_structural()` — Two-pass: first UPSERT all note records (so every note exists before linking), then create tag and wikilink relationships. Runs unconditionally — it's cheap SurrealQL queries.
2. `sync_semantic()` — Pipeline processes each note file, creates chunk records with embeddings. SHA-256 content hash gates processing — only changed files are re-embedded.

## Path as Unique Key

Record paths are **notes-relative** (e.g., `meeting.md`) not absolute (e.g., `/Users/dmallett/Brainshape/meeting.md`). This ensures the same note doesn't create duplicate records when the notes directory is synced across devices with different mount points.

Implemented in `notes.py:parse_note()` using `file_path.relative_to(notes_path)`.

## Schema Bootstrap

Created by `graph_db.py:bootstrap_schema()` on startup:

```surql
-- Tables
DEFINE TABLE IF NOT EXISTS note SCHEMALESS
DEFINE TABLE IF NOT EXISTS tag SCHEMALESS
DEFINE TABLE IF NOT EXISTS chunk SCHEMALESS
DEFINE TABLE IF NOT EXISTS memory SCHEMALESS

-- Edge tables (TYPE RELATION)
DEFINE TABLE IF NOT EXISTS tagged_with TYPE RELATION IN note OUT tag
DEFINE TABLE IF NOT EXISTS links_to TYPE RELATION IN note OUT note
DEFINE TABLE IF NOT EXISTS from_document TYPE RELATION IN chunk OUT note

-- Unique indexes (prevents duplicates on re-sync)
DEFINE INDEX IF NOT EXISTS note_path ON TABLE note FIELDS path UNIQUE
DEFINE INDEX IF NOT EXISTS tag_name ON TABLE tag FIELDS name UNIQUE
DEFINE INDEX IF NOT EXISTS memory_mid ON TABLE memory FIELDS mid UNIQUE

-- Fast lookups
DEFINE INDEX IF NOT EXISTS note_title ON TABLE note FIELDS title
DEFINE INDEX IF NOT EXISTS note_hash ON TABLE note FIELDS content_hash

-- Full-text search (powers search_notes tool)
DEFINE ANALYZER IF NOT EXISTS note_analyzer TOKENIZERS class FILTERS lowercase, ascii
DEFINE INDEX IF NOT EXISTS note_content_ft ON TABLE note FIELDS content SEARCH ANALYZER note_analyzer BM25
DEFINE INDEX IF NOT EXISTS note_title_ft ON TABLE note FIELDS title SEARCH ANALYZER note_analyzer BM25
```

## Dynamic Table Discovery

The graph visualization and stats endpoints discover edge and entity tables dynamically via `INFO FOR DB`:

- `get_relation_tables()` — finds all tables defined as `TYPE RELATION`, excludes internal tables (`from_document`)
- `get_custom_node_tables()` — finds non-core, non-relation tables (e.g., `person`, `project`)

Custom edge tables created by `create_connection` are defined as `TYPE RELATION` via `DEFINE TABLE OVERWRITE` so they appear in discovery. Reserved table names are blocked to prevent schema corruption.

## Entity Schema

No predefined entity schema. Entity tables and relationships are created by the agent during conversation via `create_connection`. Common types include person, concept, project, location, event, tool, organization, with relationships like relates_to, works_with, about, part_of, etc.

## Embeddings

Default model: `sentence-transformers/all-mpnet-base-v2` (768 dimensions, ungated). Runs locally — no API cost. Configurable via the settings UI (`embedding_model` and `embedding_dimensions`). Changing the model triggers automatic vector index migration. An HNSW vector index (`chunk_embeddings`) on `chunk.embedding` enables cosine similarity search via the `semantic_search` tool.
