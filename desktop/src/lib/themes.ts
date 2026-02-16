/**
 * Theme engine for Brain desktop app.
 *
 * A theme is a flat object mapping CSS variable names to color values.
 * Built-in themes ship as defaults; users can customize any property.
 */

export interface Theme {
  name: string;

  // Base
  background: string;
  foreground: string;
  border: string;

  // Surfaces
  card: string;
  "card-foreground": string;
  popover: string;
  "popover-foreground": string;
  muted: string;
  "muted-foreground": string;

  // Interactive
  primary: string;
  "primary-foreground": string;
  secondary: string;
  "secondary-foreground": string;
  accent: string;
  "accent-foreground": string;
  destructive: string;

  // Input
  input: string;
  ring: string;

  // Editor syntax
  "editor-heading": string;
  "editor-bold": string;
  "editor-italic": string;
  "editor-link": string;
  "editor-code": string;
  "editor-tag": string;
  "editor-selection": string;
  "editor-cursor": string;
  "editor-line-highlight": string;

  // Graph
  "graph-note": string;
  "graph-tag": string;
  "graph-memory": string;
  "graph-chunk": string;
  "graph-edge": string;
  "graph-label": string;
  "graph-highlight": string;

  // Sidebar
  sidebar: string;
  "sidebar-foreground": string;
  "sidebar-accent": string;
  "sidebar-accent-foreground": string;
}

/** All themeable keys (excluding 'name') */
export const THEME_KEYS = [
  "background",
  "foreground",
  "border",
  "card",
  "card-foreground",
  "popover",
  "popover-foreground",
  "muted",
  "muted-foreground",
  "primary",
  "primary-foreground",
  "secondary",
  "secondary-foreground",
  "accent",
  "accent-foreground",
  "destructive",
  "input",
  "ring",
  "editor-heading",
  "editor-bold",
  "editor-italic",
  "editor-link",
  "editor-code",
  "editor-tag",
  "editor-selection",
  "editor-cursor",
  "editor-line-highlight",
  "graph-note",
  "graph-tag",
  "graph-memory",
  "graph-chunk",
  "graph-edge",
  "graph-label",
  "graph-highlight",
  "sidebar",
  "sidebar-foreground",
  "sidebar-accent",
  "sidebar-accent-foreground",
] as const satisfies readonly (keyof Omit<Theme, "name">)[];

// ─── Color groups for the settings UI ───────────────────────────

export const THEME_GROUPS: { label: string; keys: (keyof Omit<Theme, "name">)[] }[] = [
  {
    label: "Base Colors",
    keys: ["background", "foreground", "border", "primary", "primary-foreground", "accent", "accent-foreground", "destructive"],
  },
  {
    label: "Surfaces",
    keys: ["card", "card-foreground", "popover", "popover-foreground", "muted", "muted-foreground", "secondary", "secondary-foreground", "input", "ring"],
  },
  {
    label: "Editor",
    keys: ["editor-heading", "editor-bold", "editor-italic", "editor-link", "editor-code", "editor-tag", "editor-selection", "editor-cursor", "editor-line-highlight"],
  },
  {
    label: "Graph",
    keys: ["graph-note", "graph-tag", "graph-memory", "graph-chunk", "graph-edge", "graph-label", "graph-highlight"],
  },
  {
    label: "Sidebar",
    keys: ["sidebar", "sidebar-foreground", "sidebar-accent", "sidebar-accent-foreground"],
  },
];

/** Human-readable labels for each theme key */
export const THEME_KEY_LABELS: Record<keyof Omit<Theme, "name">, string> = {
  background: "Background",
  foreground: "Text",
  border: "Borders",
  card: "Card Background",
  "card-foreground": "Card Text",
  popover: "Popover Background",
  "popover-foreground": "Popover Text",
  muted: "Muted Background",
  "muted-foreground": "Muted Text",
  primary: "Primary",
  "primary-foreground": "Primary Text",
  secondary: "Secondary",
  "secondary-foreground": "Secondary Text",
  accent: "Accent",
  "accent-foreground": "Accent Text",
  destructive: "Destructive",
  input: "Input Border",
  ring: "Focus Ring",
  "editor-heading": "Headings",
  "editor-bold": "Bold",
  "editor-italic": "Italic",
  "editor-link": "Links",
  "editor-code": "Code",
  "editor-tag": "Tags",
  "editor-selection": "Selection",
  "editor-cursor": "Cursor",
  "editor-line-highlight": "Active Line",
  "graph-note": "Note Nodes",
  "graph-tag": "Tag Nodes",
  "graph-memory": "Memory Nodes",
  "graph-chunk": "Chunk Nodes",
  "graph-edge": "Edges",
  "graph-label": "Labels",
  "graph-highlight": "Highlighted Node",
  sidebar: "Sidebar Background",
  "sidebar-foreground": "Sidebar Text",
  "sidebar-accent": "Sidebar Accent",
  "sidebar-accent-foreground": "Sidebar Accent Text",
};

// ─── Built-in themes ────────────────────────────────────────────

export const MIDNIGHT: Theme = {
  name: "Midnight",
  background: "#1a1a1a",
  foreground: "#fafafa",
  border: "#333333",
  card: "#242424",
  "card-foreground": "#fafafa",
  popover: "#242424",
  "popover-foreground": "#fafafa",
  muted: "#2a2a2a",
  "muted-foreground": "#a1a1aa",
  primary: "#e8e8e8",
  "primary-foreground": "#1a1a1a",
  secondary: "#2a2a2a",
  "secondary-foreground": "#fafafa",
  accent: "#2a2a2a",
  "accent-foreground": "#fafafa",
  destructive: "#dc2626",
  input: "#333333",
  ring: "#71717a",
  "editor-heading": "#f87171",
  "editor-bold": "#fafafa",
  "editor-italic": "#a78bfa",
  "editor-link": "#60a5fa",
  "editor-code": "#a78bfa",
  "editor-tag": "#34d399",
  "editor-selection": "#3b3b4f",
  "editor-cursor": "#fafafa",
  "editor-line-highlight": "#1f1f2e",
  "graph-note": "#64748b",
  "graph-tag": "#3b82f6",
  "graph-memory": "#a855f7",
  "graph-chunk": "#6b7280",
  "graph-edge": "#334155",
  "graph-label": "#e2e8f0",
  "graph-highlight": "#f59e0b",
  sidebar: "#1a1a1a",
  "sidebar-foreground": "#fafafa",
  "sidebar-accent": "#2a2a2a",
  "sidebar-accent-foreground": "#fafafa",
};

export const DAWN: Theme = {
  name: "Dawn",
  background: "#faf8f5",
  foreground: "#1c1917",
  border: "#e7e5e4",
  card: "#ffffff",
  "card-foreground": "#1c1917",
  popover: "#ffffff",
  "popover-foreground": "#1c1917",
  muted: "#f5f5f4",
  "muted-foreground": "#78716c",
  primary: "#292524",
  "primary-foreground": "#fafaf9",
  secondary: "#f5f5f4",
  "secondary-foreground": "#1c1917",
  accent: "#f5f5f4",
  "accent-foreground": "#1c1917",
  destructive: "#dc2626",
  input: "#d6d3d1",
  ring: "#a8a29e",
  "editor-heading": "#b45309",
  "editor-bold": "#1c1917",
  "editor-italic": "#7c3aed",
  "editor-link": "#2563eb",
  "editor-code": "#9333ea",
  "editor-tag": "#059669",
  "editor-selection": "#dbeafe",
  "editor-cursor": "#1c1917",
  "editor-line-highlight": "#fef3c7",
  "graph-note": "#78716c",
  "graph-tag": "#2563eb",
  "graph-memory": "#7c3aed",
  "graph-chunk": "#a8a29e",
  "graph-edge": "#d6d3d1",
  "graph-label": "#44403c",
  "graph-highlight": "#d97706",
  sidebar: "#faf8f5",
  "sidebar-foreground": "#1c1917",
  "sidebar-accent": "#f5f5f4",
  "sidebar-accent-foreground": "#1c1917",
};

export const NORD: Theme = {
  name: "Nord",
  background: "#2e3440",
  foreground: "#d8dee9",
  border: "#3b4252",
  card: "#3b4252",
  "card-foreground": "#d8dee9",
  popover: "#3b4252",
  "popover-foreground": "#d8dee9",
  muted: "#3b4252",
  "muted-foreground": "#81a1c1",
  primary: "#88c0d0",
  "primary-foreground": "#2e3440",
  secondary: "#434c5e",
  "secondary-foreground": "#d8dee9",
  accent: "#434c5e",
  "accent-foreground": "#d8dee9",
  destructive: "#bf616a",
  input: "#3b4252",
  ring: "#5e81ac",
  "editor-heading": "#88c0d0",
  "editor-bold": "#eceff4",
  "editor-italic": "#b48ead",
  "editor-link": "#81a1c1",
  "editor-code": "#a3be8c",
  "editor-tag": "#a3be8c",
  "editor-selection": "#434c5e",
  "editor-cursor": "#d8dee9",
  "editor-line-highlight": "#3b4252",
  "graph-note": "#81a1c1",
  "graph-tag": "#88c0d0",
  "graph-memory": "#b48ead",
  "graph-chunk": "#4c566a",
  "graph-edge": "#4c566a",
  "graph-label": "#d8dee9",
  "graph-highlight": "#ebcb8b",
  sidebar: "#2e3440",
  "sidebar-foreground": "#d8dee9",
  "sidebar-accent": "#3b4252",
  "sidebar-accent-foreground": "#d8dee9",
};

export const SOLARIZED_DARK: Theme = {
  name: "Solarized Dark",
  background: "#002b36",
  foreground: "#839496",
  border: "#073642",
  card: "#073642",
  "card-foreground": "#839496",
  popover: "#073642",
  "popover-foreground": "#839496",
  muted: "#073642",
  "muted-foreground": "#586e75",
  primary: "#93a1a1",
  "primary-foreground": "#002b36",
  secondary: "#073642",
  "secondary-foreground": "#93a1a1",
  accent: "#073642",
  "accent-foreground": "#93a1a1",
  destructive: "#dc322f",
  input: "#073642",
  ring: "#268bd2",
  "editor-heading": "#cb4b16",
  "editor-bold": "#93a1a1",
  "editor-italic": "#6c71c4",
  "editor-link": "#268bd2",
  "editor-code": "#2aa198",
  "editor-tag": "#859900",
  "editor-selection": "#073642",
  "editor-cursor": "#839496",
  "editor-line-highlight": "#073642",
  "graph-note": "#657b83",
  "graph-tag": "#268bd2",
  "graph-memory": "#6c71c4",
  "graph-chunk": "#586e75",
  "graph-edge": "#073642",
  "graph-label": "#93a1a1",
  "graph-highlight": "#b58900",
  sidebar: "#002b36",
  "sidebar-foreground": "#839496",
  "sidebar-accent": "#073642",
  "sidebar-accent-foreground": "#93a1a1",
};

export const BUILTIN_THEMES: Theme[] = [MIDNIGHT, DAWN, NORD, SOLARIZED_DARK];

export const DEFAULT_THEME = MIDNIGHT;

// ─── Runtime application ────────────────────────────────────────

/** Apply a theme by setting CSS custom properties on the document root. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  for (const key of THEME_KEYS) {
    root.style.setProperty(`--${key}`, theme[key]);
  }
}

/** Get the current value of a theme CSS variable. */
export function getThemeValue(key: keyof Omit<Theme, "name">): string {
  return getComputedStyle(document.documentElement).getPropertyValue(`--${key}`).trim();
}
