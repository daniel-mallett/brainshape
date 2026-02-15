import {
  Decoration,
  type DecorationSet,
  EditorView,
  ViewPlugin,
  type ViewUpdate,
  WidgetType,
} from "@codemirror/view";
import { syntaxTree } from "@codemirror/language";
import { type EditorState, type Range } from "@codemirror/state";

// --- Decoration specs ---

const headingStyles: Record<number, Decoration> = {
  1: Decoration.mark({ class: "cm-md-h1" }),
  2: Decoration.mark({ class: "cm-md-h2" }),
  3: Decoration.mark({ class: "cm-md-h3" }),
  4: Decoration.mark({ class: "cm-md-h4" }),
  5: Decoration.mark({ class: "cm-md-h5" }),
  6: Decoration.mark({ class: "cm-md-h6" }),
};

const boldDeco = Decoration.mark({ class: "cm-md-bold" });
const italicDeco = Decoration.mark({ class: "cm-md-italic" });
const codeDeco = Decoration.mark({ class: "cm-md-code" });
const linkTextDeco = Decoration.mark({ class: "cm-md-link" });
const blockquoteDeco = Decoration.mark({ class: "cm-md-blockquote" });
const hideDeco = Decoration.replace({});

class HrWidget extends WidgetType {
  toDOM() {
    const el = document.createElement("hr");
    el.className = "cm-md-hr";
    return el;
  }
}

// --- Helpers ---

function lineOfPos(state: EditorState, pos: number): number {
  return state.doc.lineAt(pos).number;
}

function cursorLines(state: EditorState): Set<number> {
  const lines = new Set<number>();
  for (const range of state.selection.ranges) {
    const start = lineOfPos(state, range.from);
    const end = lineOfPos(state, range.to);
    for (let l = start; l <= end; l++) lines.add(l);
  }
  return lines;
}

// --- Build decorations from the syntax tree ---

function buildDecorations(state: EditorState): DecorationSet {
  const active = cursorLines(state);
  const decos: Range<Decoration>[] = [];
  const tree = syntaxTree(state);

  tree.iterate({
    enter(node) {
      const { from, to } = node;
      const name = node.name;

      // --- Headings ---
      if (/^ATXHeading(\d)$/.test(name)) {
        const level = parseInt(RegExp.$1, 10);
        const deco = headingStyles[level];
        if (deco) {
          decos.push(deco.range(from, to));
        }
        // Hide the # markers when cursor is not on this line
        const headLine = lineOfPos(state, from);
        if (!active.has(headLine)) {
          const child = node.node.firstChild; // HeaderMark
          if (child) {
            // Hide "# " (mark + space)
            const markEnd = Math.min(child.to + 1, to);
            decos.push(hideDeco.range(from, markEnd));
          }
        }
      }

      // --- Bold (StrongEmphasis) ---
      if (name === "StrongEmphasis") {
        decos.push(boldDeco.range(from, to));
        const startLine = lineOfPos(state, from);
        const endLine = lineOfPos(state, to);
        let cursorOnNode = false;
        for (let l = startLine; l <= endLine; l++) {
          if (active.has(l)) {
            cursorOnNode = true;
            break;
          }
        }
        if (!cursorOnNode) {
          // Hide the ** markers (first 2 and last 2 chars)
          if (to - from > 4) {
            decos.push(hideDeco.range(from, from + 2));
            decos.push(hideDeco.range(to - 2, to));
          }
        }
      }

      // --- Italic (Emphasis) ---
      if (name === "Emphasis") {
        decos.push(italicDeco.range(from, to));
        const nodeLine = lineOfPos(state, from);
        if (!active.has(nodeLine)) {
          if (to - from > 2) {
            decos.push(hideDeco.range(from, from + 1));
            decos.push(hideDeco.range(to - 1, to));
          }
        }
      }

      // --- Inline code ---
      if (name === "InlineCode") {
        decos.push(codeDeco.range(from, to));
        const nodeLine = lineOfPos(state, from);
        if (!active.has(nodeLine)) {
          decos.push(hideDeco.range(from, from + 1));
          decos.push(hideDeco.range(to - 1, to));
        }
      }

      // --- Links: [text](url) ---
      if (name === "Link") {
        // Find child nodes for URL and link text
        const linkNode = node.node;
        const urlChild = linkNode.getChild("URL");
        const markChildren: { from: number; to: number }[] = [];
        let cursor = linkNode.firstChild;
        while (cursor) {
          if (cursor.name === "LinkMark") {
            markChildren.push({ from: cursor.from, to: cursor.to });
          }
          cursor = cursor.nextSibling;
        }

        // Style the entire link text
        decos.push(linkTextDeco.range(from, to));

        const nodeLine = lineOfPos(state, from);
        if (!active.has(nodeLine)) {
          // Hide marks: [, ], (, )
          for (const mark of markChildren) {
            decos.push(hideDeco.range(mark.from, mark.to));
          }
          // Hide the URL portion including parens
          if (urlChild) {
            decos.push(hideDeco.range(urlChild.from, urlChild.to));
          }
        }
      }

      // --- Blockquote ---
      if (name === "Blockquote") {
        decos.push(blockquoteDeco.range(from, to));
        // Hide > markers when cursor is not on the line
        let child = node.node.firstChild;
        while (child) {
          if (child.name === "QuoteMark") {
            const markLine = lineOfPos(state, child.from);
            if (!active.has(markLine)) {
              decos.push(hideDeco.range(child.from, Math.min(child.to + 1, to)));
            }
          }
          child = child.nextSibling;
        }
      }

      // --- Horizontal rule ---
      if (name === "HorizontalRule") {
        const hrLine = lineOfPos(state, from);
        if (!active.has(hrLine)) {
          decos.push(hideDeco.range(from, to));
          decos.push(Decoration.widget({ widget: new HrWidget() }).range(from));
        }
      }
    },
  });

  // Sort by from position (required by CodeMirror)
  decos.sort((a, b) => a.from - b.from || a.value.startSide - b.value.startSide);

  return Decoration.set(decos, true);
}

// --- ViewPlugin ---

const inlineMarkdownPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet;

    constructor(view: EditorView) {
      this.decorations = buildDecorations(view.state);
    }

    update(update: ViewUpdate) {
      if (update.docChanged || update.selectionSet || update.viewportChanged) {
        this.decorations = buildDecorations(update.state);
      }
    }
  },
  {
    decorations: (v) => v.decorations,
  }
);

// --- Theme ---

const inlineMarkdownTheme = EditorView.baseTheme({
  ".cm-md-h1": {
    fontSize: "1.8em",
    fontWeight: "700",
    lineHeight: "1.3",
  },
  ".cm-md-h2": {
    fontSize: "1.5em",
    fontWeight: "700",
    lineHeight: "1.3",
  },
  ".cm-md-h3": {
    fontSize: "1.25em",
    fontWeight: "600",
    lineHeight: "1.3",
  },
  ".cm-md-h4": {
    fontSize: "1.1em",
    fontWeight: "600",
    lineHeight: "1.3",
  },
  ".cm-md-h5": {
    fontSize: "1.05em",
    fontWeight: "600",
    lineHeight: "1.3",
  },
  ".cm-md-h6": {
    fontSize: "1em",
    fontWeight: "600",
    lineHeight: "1.3",
  },
  ".cm-md-bold": {
    fontWeight: "700",
  },
  ".cm-md-italic": {
    fontStyle: "italic",
  },
  ".cm-md-code": {
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    backgroundColor: "rgba(255,255,255,0.08)",
    borderRadius: "3px",
    padding: "1px 4px",
  },
  ".cm-md-link": {
    color: "#3b82f6",
    textDecoration: "underline",
    textDecorationStyle: "dotted",
  },
  ".cm-md-blockquote": {
    borderLeft: "3px solid rgba(255,255,255,0.2)",
    paddingLeft: "12px",
    color: "rgba(255,255,255,0.6)",
  },
  ".cm-md-hr": {
    border: "none",
    borderTop: "1px solid rgba(255,255,255,0.2)",
    margin: "8px 0",
  },
});

// --- Export ---

export const inlineMarkdownExtension = [inlineMarkdownPlugin, inlineMarkdownTheme];
