/**
 * CodeMirror 6 extension for clickable wikilinks and visual decoration.
 *
 * - Highlights [[wikilinks]] with a distinct style
 * - Ctrl/Cmd+click navigates to the linked note
 * - Highlights #tags with a distinct style
 */
import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
} from "@codemirror/view";
import { RangeSetBuilder } from "@codemirror/state";

// TODO: Module-level mutable state — works for single-editor usage but would
// need a facet-based approach if multiple editors are ever mounted.
let navigateCallback: ((title: string) => void) | null = null;

export function setWikilinkNavigate(cb: (title: string) => void) {
  navigateCallback = cb;
}

const wikilinkMark = Decoration.mark({ class: "cm-wikilink" });
const tagMark = Decoration.mark({ class: "cm-tag-highlight" });

const WIKILINK_RE = /\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g;
const TAG_RE = /(?:^|\s)(#[a-zA-Z][\w/-]*)/gm;

function buildDecorations(view: EditorView): DecorationSet {
  const builder = new RangeSetBuilder<Decoration>();

  for (const { from, to } of view.visibleRanges) {
    const text = view.state.doc.sliceString(from, to);

    // Collect all marks, then sort by position (RangeSetBuilder requires sorted order)
    const marks: { start: number; end: number; mark: Decoration }[] = [];

    let match;
    WIKILINK_RE.lastIndex = 0;
    while ((match = WIKILINK_RE.exec(text)) !== null) {
      marks.push({ start: from + match.index, end: from + match.index + match[0].length, mark: wikilinkMark });
    }

    TAG_RE.lastIndex = 0;
    while ((match = TAG_RE.exec(text)) !== null) {
      const tagStart = from + match.index + match[0].indexOf("#");
      marks.push({ start: tagStart, end: tagStart + match[1].length, mark: tagMark });
    }

    marks.sort((a, b) => a.start - b.start || a.end - b.end);
    for (const { start, end, mark } of marks) {
      builder.add(start, end, mark);
    }
  }

  return builder.finish();
}

const decorationPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = buildDecorations(view);
    }

    update(update: ViewUpdate) {
      if (update.docChanged || update.viewportChanged) {
        this.decorations = buildDecorations(update.view);
      }
    }
  },
  {
    decorations: (v) => v.decorations,
  }
);

// Click handler for wikilinks
const clickHandler = EditorView.domEventHandlers({
  click(event: MouseEvent, view: EditorView) {
    if (!(event.metaKey || event.ctrlKey)) return false;

    const pos = view.posAtCoords({ x: event.clientX, y: event.clientY });
    if (pos === null) return false;

    // Check if we clicked inside a wikilink
    const line = view.state.doc.lineAt(pos);
    const lineText = line.text;
    const offsetInLine = pos - line.from;

    WIKILINK_RE.lastIndex = 0;
    let match;
    while ((match = WIKILINK_RE.exec(lineText)) !== null) {
      const start = match.index;
      const end = start + match[0].length;
      if (offsetInLine >= start && offsetInLine <= end) {
        const title = match[1];
        if (navigateCallback) {
          navigateCallback(title);
          event.preventDefault();
          return true;
        }
      }
    }

    return false;
  },
});

// Theme for wikilinks and tags — uses CSS variables so colors follow the active theme
const wikilinkTheme = EditorView.baseTheme({
  ".cm-wikilink": {
    color: "var(--editor-link, #3b82f6)",
    textDecoration: "underline",
    textDecorationStyle: "dotted",
    cursor: "pointer",
  },
  ".cm-tag-highlight": {
    color: "var(--editor-tag, #a855f7)",
  },
});

export const wikilinkExtension = [decorationPlugin, clickHandler, wikilinkTheme];
