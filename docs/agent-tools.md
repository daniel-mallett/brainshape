# Agent Tools

## Overview

The Brain agent has 6 tools, all defined as plain Python functions in `brain/tools.py`. LangChain's `create_agent` infers the tool schema from type hints and docstrings.

Tools are initialized via `init_tools(db, pipeline)` which sets module-level references to the GraphDB and KG pipeline instances.

## Tool Reference

### 1. search_notes(query: str)
Full-text keyword search across notes using Neo4j's Lucene-based fulltext index. Returns up to 10 results with titles, paths, snippets, and relevance scores.

### 2. read_note(title: str)
Read the full content of a specific note by title. Queries the graph for the Note node and returns its content.

### 3. create_note(title: str, content: str, tags: str = "")
Create a new note in the Obsidian vault and sync it to the graph. Tags are comma-separated. Flow:
1. Write markdown file to vault (with frontmatter)
2. Run semantic extraction (KG pipeline creates Document + Chunk + Entity nodes)
3. Run structural sync (adds :Note label, tags, wikilinks)

### 4. edit_note(title: str, new_content: str)
Rewrite an existing note's content while preserving frontmatter. Key workflow: user jots rough notes quickly, later asks the agent to clean up formatting, add wikilinks, expand with context. Flow:
1. Read existing file, replace content, preserve frontmatter
2. Re-run semantic extraction
3. Clear old TAGGED_WITH and LINKS_TO relationships
4. Re-sync structural data

### 5. query_graph(cypher: str)
Run arbitrary Cypher queries against the knowledge graph. The agent constructs Cypher based on its understanding of the graph schema (described in its system prompt). Returns up to 20 result rows. This is the most powerful tool — it can traverse both structural and semantic layers. Also used to query Memory nodes (previously handled by dedicated remember/recall tools).

### 6. find_related(entity_name: str)
Find entities and notes related to a given concept/person/project. First tries exact name match, falls back to case-insensitive substring match. Returns relationship triples showing connections.

## Removed Tools

The following tools were removed as unnecessary:
- **remember** / **recall_memories** — Memory nodes remain in the graph and are queryable via `query_graph` with Cypher. Dedicated tools were redundant.
- **sync_vault_tool** — Running the KG pipeline is expensive and shouldn't be triggered by the agent. Sync is now user-triggered via `/sync` commands in the CLI or overnight batch processing.

## Helper: _sync_note_structural()

Shared by `create_note` and `edit_note`. Merges `:Note` and `:Document` labels onto a node by path, sets properties, and creates Tag/wikilink relationships. Uses `MERGE` for idempotent node updates and `MATCH` (not `MERGE`) for wikilink targets to avoid creating placeholder nodes.

## System Prompt

The agent's system prompt (in `agent.py`) describes the full graph schema so the agent can construct meaningful Cypher queries. It includes instructions to:
- Check notes before answering questions
- Preserve user's voice when editing notes
- Use Obsidian conventions (wikilinks, tags, headings)
