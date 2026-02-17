/**
 * Custom CodeMirror 6 theme that reads all colors from CSS custom properties.
 * This allows the theme engine to control editor syntax highlighting colors.
 */

import { EditorView } from "@codemirror/view";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags } from "@lezer/highlight";

const themeSpec = {
  "&": {
    height: "100%",
    backgroundColor: "var(--background)",
    color: "var(--foreground)",
  },
  ".cm-scroller": {
    fontFamily: "var(--editor-font, 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace)",
    fontSize: "var(--editor-font-size, 14px)",
  },
  ".cm-content": {
    padding: "16px 0",
    caretColor: "var(--editor-cursor)",
  },
  ".cm-cursor, .cm-dropCursor": {
    borderLeftColor: "var(--editor-cursor)",
  },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
    backgroundColor: "var(--editor-selection)",
  },
  ".cm-activeLine": {
    backgroundColor: "var(--editor-line-highlight)",
  },
  ".cm-gutters": {
    backgroundColor: "transparent",
    color: "var(--muted-foreground)",
    border: "none",
  },
  ".cm-activeLineGutter": {
    backgroundColor: "var(--editor-line-highlight)",
  },
  ".cm-foldPlaceholder": {
    backgroundColor: "var(--muted)",
    color: "var(--muted-foreground)",
    border: "none",
  },
  ".cm-tooltip": {
    backgroundColor: "var(--popover)",
    color: "var(--popover-foreground)",
    border: "1px solid var(--border)",
  },
  ".cm-tooltip .cm-tooltip-arrow::before": {
    borderTopColor: "var(--border)",
    borderBottomColor: "var(--border)",
  },
  ".cm-tooltip .cm-tooltip-arrow::after": {
    borderTopColor: "var(--popover)",
    borderBottomColor: "var(--popover)",
  },
  ".cm-tooltip-autocomplete": {
    "& > ul > li[aria-selected]": {
      backgroundColor: "var(--accent)",
      color: "var(--accent-foreground)",
    },
  },
  ".cm-panels": {
    backgroundColor: "var(--card)",
    color: "var(--card-foreground)",
  },
  ".cm-search.cm-panel": {
    "& input, & button, & label": {
      color: "var(--foreground)",
    },
  },
};

/** Syntax highlighting that reads from CSS variables */
const brainHighlightStyle = HighlightStyle.define([
  // Headings
  { tag: tags.heading, color: "var(--editor-heading)", fontWeight: "bold" },
  { tag: tags.heading1, color: "var(--editor-heading)", fontWeight: "bold", fontSize: "1.4em" },
  { tag: tags.heading2, color: "var(--editor-heading)", fontWeight: "bold", fontSize: "1.2em" },
  { tag: tags.heading3, color: "var(--editor-heading)", fontWeight: "bold", fontSize: "1.1em" },

  // Emphasis
  { tag: tags.strong, color: "var(--editor-bold)", fontWeight: "bold" },
  { tag: tags.emphasis, color: "var(--editor-italic)", fontStyle: "italic" },
  { tag: tags.strikethrough, color: "var(--muted-foreground)", textDecoration: "line-through" },

  // Links
  { tag: tags.link, color: "var(--editor-link)", textDecoration: "underline" },
  { tag: tags.url, color: "var(--editor-link)" },

  // Code
  { tag: tags.monospace, color: "var(--editor-code)", fontFamily: "var(--editor-font, monospace)" },

  // Lists, quotes
  { tag: tags.quote, color: "var(--muted-foreground)", fontStyle: "italic" },
  { tag: tags.list, color: "var(--foreground)" },

  // Meta (frontmatter, etc.)
  { tag: tags.meta, color: "var(--muted-foreground)" },
  { tag: tags.processingInstruction, color: "var(--muted-foreground)" },

  // Content
  { tag: tags.content, color: "var(--foreground)" },
  { tag: tags.contentSeparator, color: "var(--border)" },

  // Comments and special
  { tag: tags.comment, color: "var(--muted-foreground)" },
  { tag: tags.invalid, color: "var(--destructive)" },
]);

const highlightExt = syntaxHighlighting(brainHighlightStyle);

/** Detect whether the current theme is dark via the .dark class on <html>. */
export function isDarkTheme(): boolean {
  return document.documentElement.classList.contains("dark");
}

/** Build theme extension with correct dark/light mode. Called when editor is created. */
export function brainThemeExtension(dark?: boolean) {
  const isDark = dark ?? isDarkTheme();
  return [EditorView.theme(themeSpec, { dark: isDark }), highlightExt];
}
