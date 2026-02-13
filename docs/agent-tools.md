# Agent Tools

## Overview

The Brain agent has 9 tools, all defined as plain Python functions in `brain/tools.py`. LangChain's `create_agent` infers the tool schema from type hints and docstrings.

Tools are initialized via `init_tools(db, pipeline)` which sets module-level references to the GraphDB and KG pipeline instances.

## Tool Reference

### 1. search_notes(query: str)
Full-text keyword search across notes using Neo4j's Lucene-based fulltext index. Returns up to 10 results with titles, paths, snippets, and relevance scores.

### 2. read_note(title: str)
Read the full content of a specific note by title. Queries the graph for the Note node and returns its content.

### 3. create_note(title: str, content: str, tags: str = "")
Create a new note in the Obsidian vault and sync it to the graph. Tags are comma-separated. Flow:
1. Write markdown file to vault (with frontmatter)
2. Run semantic extraction (KG Builder creates Document + Chunk + Entity nodes)
3. Run structural sync (adds :Note label, tags, wikilinks)

### 4. edit_note(title: str, new_content: str)
Rewrite an existing note's content while preserving frontmatter. Key workflow: user jots rough notes quickly, later asks the agent to clean up formatting, add wikilinks, expand with context. Flow:
1. Read existing file, replace content, preserve frontmatter
2. Re-run semantic extraction
3. Clear old TAGGED_WITH and LINKS_TO relationships
4. Re-sync structural data

### 5. query_graph(cypher: str)
Run arbitrary Cypher queries against the knowledge graph. The agent constructs Cypher based on its understanding of the graph schema (described in its system prompt). Returns up to 20 result rows. This is the most powerful tool — it can traverse both structural and semantic layers.

### 6. remember(content: str, memory_type: str = "fact")
Store a memory in the graph as a `:Memory` node. Types: `fact`, `preference`, `instruction`. Examples:
- fact: "User works at Acme Corp"
- preference: "User prefers bullet points over paragraphs"
- instruction: "Always use wikilinks when mentioning other notes"

### 7. recall_memories(query: str = "")
Retrieve stored memories, optionally filtered by keyword. Returns up to 20 most recent memories. The agent should call this at the start of conversations to load context.

### 8. sync_vault_tool()
Re-sync the entire Obsidian vault to the graph. Runs both semantic (KG Builder) and structural sync. Use after notes have been edited outside of Brain (e.g., directly in Obsidian).

### 9. find_related(entity_name: str)
Find entities and notes related to a given concept/person/project. First tries exact name match, falls back to case-insensitive substring match. Returns relationship triples showing connections.

## Helper: _sync_note_structural()

Shared by `create_note` and `edit_note`. Merges `:Note` and `:Document` labels onto a node by path, sets properties, and creates Tag/wikilink relationships. Uses `MERGE` for idempotent updates.

## System Prompt

The agent's system prompt (in `agent.py`) describes the full graph schema so the agent can construct meaningful Cypher queries. It includes instructions to:
- Check notes and memories before answering questions
- Use `recall_memories` at conversation start
- Preserve user's voice when editing notes
- Use Obsidian conventions (wikilinks, tags, headings)
