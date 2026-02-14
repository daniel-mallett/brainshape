# Agent Tools

## Overview

The Brain agent has 7 tools, all defined as plain Python functions in `brain/tools.py`. LangChain's `create_agent` infers the tool schema from type hints and docstrings.

Tools use module-level `db` and `pipeline` variables set by `create_brain_agent()` in `agent.py` before tools are used.

Tool responses only include vault-relative paths — absolute system paths are never exposed to the agent.

## Tool Reference

### 1. search_notes(query: str)
Full-text keyword search across notes using Neo4j's Lucene-based fulltext index. Returns up to 10 results with titles, paths, snippets, and relevance scores.

### 2. semantic_search(query: str)
Vector similarity search over chunk embeddings. Embeds the query text using the pipeline's embedding model, then runs a cosine similarity search against the `chunk_embeddings` vector index. Returns matching chunks with their parent note title and similarity score. Use when keyword search misses conceptually related content.

### 3. read_note(title: str)
Read the full content of a specific note by title. Queries the graph for the Note node and returns its content.

### 4. create_note(title: str, content: str, tags: str = "", folder: str = "")
Create a new note in the Obsidian vault and sync it to the graph. Tags are comma-separated. Folder specifies the subdirectory within the vault (e.g., 'Notes', 'Projects/2026'). Flow:
1. Write markdown file to vault (with frontmatter)
2. Run semantic extraction (KG pipeline creates Document + Chunk + Entity nodes)
3. Run structural sync (adds :Note label, tags, wikilinks)

### 5. edit_note(title: str, new_content: str)
Rewrite an existing note's content while preserving frontmatter. Looks up the note's actual path from the graph so it works with notes in subdirectories. Flow:
1. Query graph for the note's vault-relative path
2. Read existing file, replace content, preserve frontmatter
3. Re-run semantic extraction
4. Clear old TAGGED_WITH and LINKS_TO relationships
5. Re-sync structural data

### 6. query_graph(cypher: str)
Run arbitrary Cypher queries against the knowledge graph. The agent constructs Cypher based on its understanding of the graph schema (described in its system prompt). Returns up to 20 result rows. This is the most powerful tool — it can traverse both structural and semantic layers. Also used to persist user preferences and memories as `:Memory` nodes.

### 7. find_related(entity_name: str)
Find entities and notes related to a given concept/person/project. First tries exact name match, falls back to case-insensitive substring match. Returns relationship triples showing connections.

## Memory Persistence

The agent stores user preferences, personal info, and things to remember as `:Memory` nodes in the graph via `query_graph`. The system prompt instructs the agent to:
- Create `(:Memory {type, content, created_at})` nodes when the user shares preferences or personal info
- Check for existing memories at the start of each conversation

## Helper: _sync_note_structural()

Shared by `create_note` and `edit_note`. Merges `:Note` and `:Document` labels onto a node by path, sets properties, and creates Tag/wikilink relationships. Uses `MERGE` for idempotent node updates and `MATCH` (not `MERGE`) for wikilink targets to avoid creating placeholder nodes.

## System Prompt

The agent's system prompt (in `agent.py`) describes the full graph schema so the agent can construct meaningful Cypher queries. It includes instructions to:
- Use keyword vs semantic search appropriately
- Place notes in the right folder
- Preserve user's voice when editing notes
- Persist memories and preferences to the graph
- Use Obsidian conventions (wikilinks, tags, headings)
