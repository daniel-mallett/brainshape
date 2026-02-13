# Knowledge Graph Design

## Core Principle: Unified Nodes

Each Obsidian markdown file is represented as a **single node** with dual labels `:Document:Note`. This node is the hub connecting both the structural world (tags, wikilinks) and the semantic world (chunks, extracted entities).

```
(:Tag) <-TAGGED_WITH- (:Document:Note) <-FROM_DOCUMENT- (:Chunk) <-FROM_CHUNK- (:Person)
                            |                            (:Chunk) <-FROM_CHUNK- (:Concept)
                        LINKS_TO
                            v
                      (:Document:Note) ...
```

## Why Unified?

We initially had two disconnected subgraphs — `Note` nodes from our parser, `Document`/`Chunk`/`Entity` nodes from the KG Builder, with no connection between them. This made cross-layer queries impossible.

The unified design means a single Cypher query can traverse both layers. For example, "find all people mentioned in notes tagged #meeting":

```cypher
MATCH (t:Tag {name: "meeting"})<-[:TAGGED_WITH]-(n:Note)
      -[:HAS_CHUNK]->(c:Chunk)<-[:FROM_CHUNK]-(p:Person)
RETURN n.title, p.name
```

## Two Layers, One Graph

Everything lives in a single Neo4j graph database. "Layers" are a conceptual distinction, not physical separation.

### Structural Layer (from our parser in `obsidian.py`)

Created by `sync_structural()` in `sync.py`. Mirrors Obsidian's explicit connections.

| Node | Properties | Unique Key |
|------|-----------|------------|
| `:Note` (also `:Document`) | `path`, `title`, `content`, `created_at`, `modified_at` | `path` (vault-relative) |
| `:Tag` | `name` | `name` |
| `:Memory` | `id` (uuid), `type`, `content`, `created_at` | `id` |

| Relationship | Pattern | Source |
|-------------|---------|--------|
| `LINKS_TO` | `(:Note)-[:LINKS_TO]->(:Note)` | Wikilinks `[[Other Note]]` |
| `TAGGED_WITH` | `(:Note)-[:TAGGED_WITH]->(:Tag)` | Tags `#tag` or frontmatter |
| `ABOUT` | `(:Memory)-[:ABOUT]->(:Note)` | Agent memory referencing a note |
| `ABOUT_TAG` | `(:Memory)-[:ABOUT_TAG]->(:Tag)` | Agent memory referencing a topic |

### Semantic Layer (from KG Builder in `kg_pipeline.py`)

Created by `sync_semantic()` in `sync.py` using `neo4j-graphrag`'s `SimpleKGPipeline`.

| Node | Properties | Created By |
|------|-----------|------------|
| `:Document` (also `:Note`) | `path` (vault-relative) | KG Builder (via `ObsidianLoader`) |
| `:Chunk` | `text`, `index`, embedding vector | KG Builder (text splitter) |
| Entity nodes (`:Person`, `:Concept`, `:Project`, `:Location`, `:Event`, `:Tool`, `:Organization`) | `name` + type-specific props | KG Builder (LLM extraction) |

| Relationship | Pattern | Created By |
|-------------|---------|------------|
| `FROM_DOCUMENT` | `(:Chunk)-[:FROM_DOCUMENT]->(:Document)` | KG Builder |
| `NEXT_CHUNK` | `(:Chunk)-[:NEXT_CHUNK]->(:Chunk)` | KG Builder |
| `FROM_CHUNK` | `(entity)-[:FROM_CHUNK]->(:Chunk)` | KG Builder |
| `RELATED_TO`, `WORKS_ON`, `USES`, `LOCATED_IN`, `PART_OF`, `CREATED_BY` | Between entity nodes | KG Builder (LLM extraction) |

## Sync Order

**Semantic runs first**, then structural:

1. `sync_semantic()` — KG Builder processes each note file via `ObsidianLoader`, creates `:Document` nodes (keyed by vault-relative path), Chunk nodes, Entity nodes with relationships
2. `sync_structural()` — Finds existing Document nodes by `path`, adds `:Note` label, sets `title`/`content` properties, creates `Tag` nodes and `TAGGED_WITH`/`LINKS_TO` relationships

This order ensures the structural sync can merge onto the Document nodes the KG Builder already created.

## Path as Unique Key

Node paths are **vault-relative** (e.g., `notes/meeting.md`) not absolute (e.g., `/Users/dmallett/obsidian-vault/notes/meeting.md`). This ensures the same note doesn't create duplicate nodes when the vault is synced across devices with different mount points.

Implemented in `obsidian.py:parse_note()` using `file_path.relative_to(vault_path)`.

## Constraints and Indexes

Created by `graph_db.py:bootstrap_schema()` on startup:

```cypher
-- Uniqueness (prevents duplicates on re-sync via MERGE)
CREATE CONSTRAINT note_path IF NOT EXISTS FOR (n:Note) REQUIRE n.path IS UNIQUE
CREATE CONSTRAINT tag_name IF NOT EXISTS FOR (t:Tag) REQUIRE t.name IS UNIQUE
CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE

-- Fast lookups
CREATE INDEX note_title IF NOT EXISTS FOR (n:Note) ON (n.title)

-- Full-text search (powers search_notes tool)
CREATE FULLTEXT INDEX note_content IF NOT EXISTS FOR (n:Note) ON EACH [n.content, n.title]
```

## Entity Schema

Configurable in `kg_pipeline.py`. Starting point:

```python
NODE_TYPES = ["Person", "Concept", "Project", "Location", "Event", "Tool", "Organization"]
RELATIONSHIP_TYPES = ["RELATED_TO", "WORKS_ON", "USES", "LOCATED_IN", "PART_OF", "CREATED_BY"]
PATTERNS = [
    ("Person", "WORKS_ON", "Project"),
    ("Person", "USES", "Tool"),
    ("Person", "PART_OF", "Organization"),
    ("Project", "USES", "Tool"),
    ("Event", "LOCATED_IN", "Location"),
    ("Concept", "RELATED_TO", "Concept"),
    ("Person", "RELATED_TO", "Person"),
    ("Project", "RELATED_TO", "Concept"),
    ("Organization", "LOCATED_IN", "Location"),
    ("Person", "CREATED_BY", "Organization"),
]
```

## Embeddings (Placeholder)

Currently using `NoOpEmbedder` (returns zero vectors) to satisfy the KG Builder's required `embedder` parameter without pulling in `torch` (~2GB). Entity extraction works fine — it uses the LLM, not embeddings. Swap in `SentenceTransformerEmbeddings` later for real vector-based semantic search over chunks.
