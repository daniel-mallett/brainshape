/**
 * Remark plugin that transforms [[wikilink]] syntax into clickable links.
 *
 * Supports:
 *   [[Note Title]]           → link with text "Note Title"
 *   [[Note Title|Display]]   → link with text "Display"
 *
 * Links use fragment URLs (e.g., href="#brain/Note Title") so they pass
 * through rehype-sanitize without being stripped. The custom `a` component
 * in WikilinkComponents.tsx intercepts these and navigates to the note.
 */
import { findAndReplace } from "mdast-util-find-and-replace";
import type { Root } from "mdast";

const WIKILINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;

export function remarkWikilinks() {
  return (tree: Root) => {
    findAndReplace(tree, [
      [
        WIKILINK_RE,
        (_match: string, target: string, display?: string) => {
          return {
            type: "link" as const,
            url: `#brain/${target.trim()}`,
            children: [{ type: "text" as const, value: (display || target).trim() }],
          };
        },
      ],
    ]);
  };
}
