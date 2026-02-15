---
tags:
  - tutorial
  - markdown
  - syntax
---
# Writing Notes

Brain uses standard markdown with a few extras that make your notes interconnected and searchable.

## Markdown basics

Notes are plain markdown files. You can use all standard formatting:

- **Bold**, *italic*, ~~strikethrough~~
- Headings with `#`, `##`, `###`
- Bullet lists, numbered lists
- Code blocks with triple backticks
- Links, images, and more

## Wikilinks

Connect your notes together using wikilinks — double brackets around a note title:

- `[[Welcome]]` links to the Welcome note
- `[[Getting Started|the getting started guide]]` links to Getting Started but displays custom text

Wikilinks create relationships in the knowledge graph, so the agent understands how your ideas connect.

## Tags

Organize your notes with tags. You can add them in two ways:

**In the frontmatter** (the YAML block at the top of a note):
```
---
tags:
  - project
  - important
---
```

**Inline in the body** using `#`:

This note is about #markdown and #syntax.

Tags also show up in the knowledge graph as connections between notes.

## Frontmatter

The YAML block between `---` markers at the top of a note is called frontmatter. Use it for structured metadata:

```
---
tags:
  - tutorial
author: Your Name
status: draft
---
```

The agent can read frontmatter when searching and analyzing your notes.

## Tips

- Keep note titles short and descriptive — they become node names in the graph
- Use wikilinks liberally — they're what make the knowledge graph useful
- Tags work best for broad categories; wikilinks work best for specific connections
- See [[Using the Agent]] for how the agent uses all of this
