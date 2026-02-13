# KG Builder Pipeline

## Overview

The knowledge graph is built using `neo4j-graphrag` v1.1.0's `SimpleKGPipeline`. It uses an LLM (Claude via `AnthropicLLM`) to extract entities and relationships from note content — producing a much richer graph than Obsidian's simple link-based visualization.

## Pipeline Components

### ObsidianLoader (custom DataLoader)

`brain/kg_pipeline.py:ObsidianLoader` is a custom `DataLoader` that reads Obsidian markdown files instead of PDFs. It returns `PdfDocument` (the library's expected return type) with:
- `text`: the markdown file content
- `document_info.path`: vault-relative path (e.g., `notes/meeting.md`)
- `document_info.metadata`: includes the note title

This is critical for the unified graph design — the `document_info.path` becomes the Document node's `id` and `path` property, which the structural sync later uses to merge the `:Note` label onto the same node.

### SimpleKGPipeline Configuration

```python
SimpleKGPipeline(
    llm=AnthropicLLM(...),
    driver=neo4j_driver,
    embedder=NoOpEmbedder(),      # placeholder, swap for real embeddings later
    entities=NODE_TYPES,           # Person, Concept, Project, etc.
    relations=RELATIONSHIP_TYPES,  # RELATED_TO, WORKS_ON, etc.
    potential_schema=PATTERNS,     # allowed (source, rel, target) triples
    from_pdf=True,                 # True because we use ObsidianLoader
    pdf_loader=ObsidianLoader(vault_path),
    on_error="IGNORE",            # skip chunks where extraction fails
    perform_entity_resolution=True, # merge duplicate entities
)
```

Key: `from_pdf=True` is set despite processing markdown, because this mode activates the loader → splitter → extractor pipeline that passes `document_info` through. With `from_pdf=False`, no `document_info` is passed and no Document nodes are created.

### Pipeline Flow

```
ObsidianLoader (reads .md file)
    ↓ text + document_info
FixedSizeSplitter (chunks text)
    ↓ text_chunks
TextChunkEmbedder (embeds chunks — currently no-op)
    ↓ embedded_chunks
LLMEntityRelationExtractor (extracts entities + relationships via Claude)
    ↓ Neo4jGraph (Document + Chunk + Entity nodes, all relationships)
Neo4jWriter (writes to Neo4j)
    ↓
SinglePropertyExactMatchResolver (merges duplicate entities by name)
```

### What the Extractor Creates

When `document_info` is provided (which our ObsidianLoader ensures):
1. **Document node** with `id = document_info.path` (vault-relative)
2. **Chunk nodes** linked to Document via `FROM_DOCUMENT`
3. **Chunk → Chunk** via `NEXT_CHUNK` (document flow)
4. **Entity nodes** (Person, Concept, etc.) linked to Chunks via `FROM_CHUNK`
5. **Entity → Entity** relationships (WORKS_ON, RELATED_TO, etc.)

### Process Functions

- `process_note(pipeline, file_path)` — synchronous, processes one note file
- `process_note_async(pipeline, file_path)` — async version

## Reference Implementation

A more advanced KG pipeline exists at `/Users/dmallett/Developer/ambition/ahi/kg/pipeline.py`. Key differences:
- Uses a **newer version** of neo4j-graphrag with `LexicalGraphBuilder` as a standalone component
- Builds pipeline from **individual components** instead of `SimpleKGPipeline` (more control)
- Uses **Anthropic Batch API** for 50% cost discount on bulk processing
- Uses **SentenceTransformerEmbeddings** for real vector embeddings
- Includes **preflight checks** (Neo4j connectivity, APOC plugin, LLM, embedder)
- Has **post-processing** to create document-level edges (e.g., `ATTENDED`)
- Includes **GraphPruning** to enforce schema constraints
- Supports **incremental processing** (skip already-processed documents)

When upgrading neo4j-graphrag to a newer version, consider migrating to the component-based approach for more control.

## Entity Schema Design

The schema is intentionally broad for a personal notes use case:

| Entity Type | Description |
|------------|-------------|
| Person | People mentioned in notes |
| Concept | Abstract ideas, topics, themes |
| Project | Work projects, side projects, initiatives |
| Location | Places, cities, countries |
| Event | Meetings, conferences, milestones |
| Tool | Software, languages, frameworks |
| Organization | Companies, teams, groups |

The `PATTERNS` list constrains which relationships the LLM can extract between entity types. This prevents hallucinated connections while still allowing rich extraction.
