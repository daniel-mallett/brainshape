/**
 * Theme engine for Brainshape desktop app.
 *
 * A theme is a flat object mapping CSS variable names to color values.
 * Built-in themes ship as defaults; users can customize any property.
 */

/** CSS-variable keys that get applied to the document root. */
type ThemeColorKey =
  | "background" | "foreground" | "border"
  | "card" | "card-foreground"
  | "popover" | "popover-foreground"
  | "muted" | "muted-foreground"
  | "primary" | "primary-foreground"
  | "secondary" | "secondary-foreground"
  | "accent" | "accent-foreground"
  | "destructive" | "input" | "ring"
  | "editor-heading" | "editor-bold" | "editor-italic" | "editor-link"
  | "editor-code" | "editor-tag" | "editor-selection" | "editor-cursor"
  | "editor-line-highlight"
  | "graph-note" | "graph-tag" | "graph-memory" | "graph-chunk"
  | "graph-edge" | "graph-label" | "graph-highlight"
  | "sidebar" | "sidebar-foreground" | "sidebar-accent"
  | "sidebar-accent-foreground";

export interface Theme extends Record<ThemeColorKey, string> {
  name: string;
  mode: "light" | "dark";
  codeTheme: [string, string]; // [light shiki theme, dark shiki theme]
}

/** All themeable keys (excluding metadata like name, mode, codeTheme) */
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
] as const satisfies readonly ThemeColorKey[];

// ─── Color groups for the settings UI ───────────────────────────

export const THEME_GROUPS: { label: string; keys: ThemeColorKey[] }[] = [
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
export const THEME_KEY_LABELS: Record<ThemeColorKey, string> = {
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

// Monochrome — clean grayscale
export const MONOCHROME_LIGHT: Theme = {
  name: "Monochrome Light", mode: "light", codeTheme: ["min-light", "min-dark"],
  background: "#ffffff", foreground: "#1a1a1a", border: "#e0e0e0",
  card: "#f7f7f7", "card-foreground": "#1a1a1a",
  popover: "#ffffff", "popover-foreground": "#1a1a1a",
  muted: "#f0f0f0", "muted-foreground": "#737373",
  primary: "#1a1a1a", "primary-foreground": "#ffffff",
  secondary: "#f0f0f0", "secondary-foreground": "#1a1a1a",
  accent: "#e8e8e8", "accent-foreground": "#1a1a1a",
  destructive: "#dc2626", input: "#d4d4d4", ring: "#a3a3a3",
  "editor-heading": "#1a1a1a", "editor-bold": "#1a1a1a",
  "editor-italic": "#525252", "editor-link": "#404040",
  "editor-code": "#525252", "editor-tag": "#404040",
  "editor-selection": "#b0b0b0", "editor-cursor": "#1a1a1a",
  "editor-line-highlight": "#f5f5f5",
  "graph-note": "#737373", "graph-tag": "#404040",
  "graph-memory": "#525252", "graph-chunk": "#a3a3a3",
  "graph-edge": "#d4d4d4", "graph-label": "#1a1a1a", "graph-highlight": "#404040",
  sidebar: "#fafafa", "sidebar-foreground": "#1a1a1a",
  "sidebar-accent": "#f0f0f0", "sidebar-accent-foreground": "#1a1a1a",
};

export const MONOCHROME_DARK: Theme = {
  name: "Monochrome Dark", mode: "dark", codeTheme: ["min-light", "min-dark"],
  background: "#1a1a1a", foreground: "#e5e5e5", border: "#333333",
  card: "#242424", "card-foreground": "#e5e5e5",
  popover: "#242424", "popover-foreground": "#e5e5e5",
  muted: "#2a2a2a", "muted-foreground": "#a3a3a3",
  primary: "#e5e5e5", "primary-foreground": "#1a1a1a",
  secondary: "#2a2a2a", "secondary-foreground": "#e5e5e5",
  accent: "#333333", "accent-foreground": "#e5e5e5",
  destructive: "#dc2626", input: "#333333", ring: "#737373",
  "editor-heading": "#e5e5e5", "editor-bold": "#e5e5e5",
  "editor-italic": "#a3a3a3", "editor-link": "#d4d4d4",
  "editor-code": "#a3a3a3", "editor-tag": "#d4d4d4",
  "editor-selection": "#404040", "editor-cursor": "#e5e5e5",
  "editor-line-highlight": "#222222",
  "graph-note": "#737373", "graph-tag": "#a3a3a3",
  "graph-memory": "#d4d4d4", "graph-chunk": "#525252",
  "graph-edge": "#333333", "graph-label": "#e5e5e5", "graph-highlight": "#d4d4d4",
  sidebar: "#1a1a1a", "sidebar-foreground": "#e5e5e5",
  "sidebar-accent": "#2a2a2a", "sidebar-accent-foreground": "#e5e5e5",
};

// Gruvbox — warm retro palette (morhetz/gruvbox canonical colors)
export const GRUVBOX_LIGHT: Theme = {
  name: "Gruvbox Light", mode: "light", codeTheme: ["gruvbox-light-medium", "gruvbox-dark-medium"],
  background: "#fbf1c7", foreground: "#3c3836", border: "#d5c4a1",
  card: "#f2e5bc", "card-foreground": "#3c3836",
  popover: "#fbf1c7", "popover-foreground": "#3c3836",
  muted: "#ebdbb2", "muted-foreground": "#7c6f64",
  primary: "#d65d0e", "primary-foreground": "#fbf1c7",
  secondary: "#ebdbb2", "secondary-foreground": "#3c3836",
  accent: "#d5c4a1", "accent-foreground": "#3c3836",
  destructive: "#cc241d", input: "#bdae93", ring: "#928374",
  "editor-heading": "#cc241d", "editor-bold": "#3c3836",
  "editor-italic": "#b16286", "editor-link": "#458588",
  "editor-code": "#98971a", "editor-tag": "#689d6a",
  "editor-selection": "#bdae93", "editor-cursor": "#3c3836",
  "editor-line-highlight": "#f2e5bc",
  "graph-note": "#7c6f64", "graph-tag": "#458588",
  "graph-memory": "#b16286", "graph-chunk": "#928374",
  "graph-edge": "#d5c4a1", "graph-label": "#3c3836", "graph-highlight": "#d79921",
  sidebar: "#f9f5d7", "sidebar-foreground": "#3c3836",
  "sidebar-accent": "#ebdbb2", "sidebar-accent-foreground": "#3c3836",
};

export const GRUVBOX_DARK: Theme = {
  name: "Gruvbox Dark", mode: "dark", codeTheme: ["gruvbox-light-medium", "gruvbox-dark-medium"],
  background: "#282828", foreground: "#ebdbb2", border: "#3c3836",
  card: "#32302f", "card-foreground": "#ebdbb2",
  popover: "#32302f", "popover-foreground": "#ebdbb2",
  muted: "#3c3836", "muted-foreground": "#a89984",
  primary: "#fe8019", "primary-foreground": "#282828",
  secondary: "#3c3836", "secondary-foreground": "#ebdbb2",
  accent: "#504945", "accent-foreground": "#ebdbb2",
  destructive: "#fb4934", input: "#504945", ring: "#665c54",
  "editor-heading": "#fb4934", "editor-bold": "#ebdbb2",
  "editor-italic": "#d3869b", "editor-link": "#83a598",
  "editor-code": "#b8bb26", "editor-tag": "#8ec07c",
  "editor-selection": "#504945", "editor-cursor": "#ebdbb2",
  "editor-line-highlight": "#32302f",
  "graph-note": "#a89984", "graph-tag": "#83a598",
  "graph-memory": "#d3869b", "graph-chunk": "#665c54",
  "graph-edge": "#504945", "graph-label": "#ebdbb2", "graph-highlight": "#fabd2f",
  sidebar: "#282828", "sidebar-foreground": "#ebdbb2",
  "sidebar-accent": "#3c3836", "sidebar-accent-foreground": "#ebdbb2",
};

// Tokyo Night — cool neon purple/blue (Day variant from enkia/tokyo-night-vscode-theme)
export const TOKYO_NIGHT_LIGHT: Theme = {
  name: "Tokyo Night Light", mode: "light", codeTheme: ["vitesse-light", "tokyo-night"],
  background: "#e6e7ed", foreground: "#343b59", border: "#c1c2c7",
  card: "#d6d8df", "card-foreground": "#343b59",
  popover: "#e6e7ed", "popover-foreground": "#343b59",
  muted: "#d6d8df", "muted-foreground": "#707280",
  primary: "#2959aa", "primary-foreground": "#e6e7ed",
  secondary: "#d6d8df", "secondary-foreground": "#343b59",
  accent: "#c1c2c7", "accent-foreground": "#343b59",
  destructive: "#8c4351", input: "#c1c2c7", ring: "#2959aa",
  "editor-heading": "#8c4351", "editor-bold": "#343b59",
  "editor-italic": "#7b43ba", "editor-link": "#2959aa",
  "editor-code": "#385f0d", "editor-tag": "#33635c",
  "editor-selection": "#9ca0b0", "editor-cursor": "#343b59",
  "editor-line-highlight": "#d6d8df",
  "graph-note": "#707280", "graph-tag": "#2959aa",
  "graph-memory": "#7b43ba", "graph-chunk": "#888b94",
  "graph-edge": "#c1c2c7", "graph-label": "#343b59", "graph-highlight": "#8f5e15",
  sidebar: "#d6d8df", "sidebar-foreground": "#343b59",
  "sidebar-accent": "#c1c2c7", "sidebar-accent-foreground": "#343b59",
};

export const TOKYO_NIGHT_DARK: Theme = {
  name: "Tokyo Night Dark", mode: "dark", codeTheme: ["vitesse-light", "tokyo-night"],
  background: "#1a1b26", foreground: "#a9b1d6", border: "#101014",
  card: "#24283b", "card-foreground": "#a9b1d6",
  popover: "#24283b", "popover-foreground": "#a9b1d6",
  muted: "#292e42", "muted-foreground": "#565f89",
  primary: "#7aa2f7", "primary-foreground": "#1a1b26",
  secondary: "#292e42", "secondary-foreground": "#a9b1d6",
  accent: "#33467c", "accent-foreground": "#c0caf5",
  destructive: "#f7768e", input: "#292e42", ring: "#3d59a1",
  "editor-heading": "#f7768e", "editor-bold": "#c0caf5",
  "editor-italic": "#bb9af7", "editor-link": "#7aa2f7",
  "editor-code": "#9ece6a", "editor-tag": "#73daca",
  "editor-selection": "#33467c", "editor-cursor": "#c0caf5",
  "editor-line-highlight": "#1e202e",
  "graph-note": "#565f89", "graph-tag": "#7dcfff",
  "graph-memory": "#bb9af7", "graph-chunk": "#3b4261",
  "graph-edge": "#292e42", "graph-label": "#a9b1d6", "graph-highlight": "#e0af68",
  sidebar: "#16161e", "sidebar-foreground": "#a9b1d6",
  "sidebar-accent": "#292e42", "sidebar-accent-foreground": "#a9b1d6",
};

// Catppuccin — pastel dark/light (catppuccin/catppuccin canonical Latte + Mocha)
export const CATPPUCCIN_LIGHT: Theme = {
  name: "Catppuccin Light", mode: "light", codeTheme: ["catppuccin-latte", "catppuccin-mocha"],
  background: "#eff1f5", foreground: "#4c4f69", border: "#ccd0da",
  card: "#e6e9ef", "card-foreground": "#4c4f69",
  popover: "#eff1f5", "popover-foreground": "#4c4f69",
  muted: "#e6e9ef", "muted-foreground": "#6c6f85",
  primary: "#1e66f5", "primary-foreground": "#dce0e8",
  secondary: "#dce0e8", "secondary-foreground": "#4c4f69",
  accent: "#bcc0cc", "accent-foreground": "#4c4f69",
  destructive: "#d20f39", input: "#bcc0cc", ring: "#7287fd",
  "editor-heading": "#d20f39", "editor-bold": "#4c4f69",
  "editor-italic": "#8839ef", "editor-link": "#1e66f5",
  "editor-code": "#40a02b", "editor-tag": "#179299",
  "editor-selection": "#acb0be", "editor-cursor": "#4c4f69",
  "editor-line-highlight": "#e6e9ef",
  "graph-note": "#9ca0b0", "graph-tag": "#209fb5",
  "graph-memory": "#ea76cb", "graph-chunk": "#ccd0da",
  "graph-edge": "#ccd0da", "graph-label": "#4c4f69", "graph-highlight": "#fe640b",
  sidebar: "#e6e9ef", "sidebar-foreground": "#4c4f69",
  "sidebar-accent": "#dce0e8", "sidebar-accent-foreground": "#5c5f77",
};

export const CATPPUCCIN_DARK: Theme = {
  name: "Catppuccin Dark", mode: "dark", codeTheme: ["catppuccin-latte", "catppuccin-mocha"],
  background: "#1e1e2e", foreground: "#cdd6f4", border: "#313244",
  card: "#181825", "card-foreground": "#cdd6f4",
  popover: "#181825", "popover-foreground": "#cdd6f4",
  muted: "#313244", "muted-foreground": "#a6adc8",
  primary: "#89b4fa", "primary-foreground": "#1e1e2e",
  secondary: "#313244", "secondary-foreground": "#cdd6f4",
  accent: "#45475a", "accent-foreground": "#cdd6f4",
  destructive: "#f38ba8", input: "#313244", ring: "#b4befe",
  "editor-heading": "#f38ba8", "editor-bold": "#cdd6f4",
  "editor-italic": "#cba6f7", "editor-link": "#89b4fa",
  "editor-code": "#a6e3a1", "editor-tag": "#94e2d5",
  "editor-selection": "#45475a", "editor-cursor": "#f5e0dc",
  "editor-line-highlight": "#181825",
  "graph-note": "#9399b2", "graph-tag": "#74c7ec",
  "graph-memory": "#f5c2e7", "graph-chunk": "#45475a",
  "graph-edge": "#313244", "graph-label": "#cdd6f4", "graph-highlight": "#fab387",
  sidebar: "#181825", "sidebar-foreground": "#bac2de",
  "sidebar-accent": "#313244", "sidebar-accent-foreground": "#cdd6f4",
};

// Nord — arctic blue (nordtheme/nord canonical 16-color palette)
export const NORD_LIGHT: Theme = {
  name: "Nord Light", mode: "light", codeTheme: ["one-light", "nord"],
  background: "#eceff4", foreground: "#2e3440", border: "#d8dee9",
  card: "#e5e9f0", "card-foreground": "#2e3440",
  popover: "#eceff4", "popover-foreground": "#2e3440",
  muted: "#e5e9f0", "muted-foreground": "#4c566a",
  primary: "#5e81ac", "primary-foreground": "#eceff4",
  secondary: "#d8dee9", "secondary-foreground": "#2e3440",
  accent: "#d8dee9", "accent-foreground": "#2e3440",
  destructive: "#bf616a", input: "#d8dee9", ring: "#5e81ac",
  "editor-heading": "#bf616a", "editor-bold": "#2e3440",
  "editor-italic": "#b48ead", "editor-link": "#5e81ac",
  "editor-code": "#a3be8c", "editor-tag": "#8fbcbb",
  "editor-selection": "#b8c5d9", "editor-cursor": "#2e3440",
  "editor-line-highlight": "#e5e9f0",
  "graph-note": "#4c566a", "graph-tag": "#81a1c1",
  "graph-memory": "#b48ead", "graph-chunk": "#d8dee9",
  "graph-edge": "#d8dee9", "graph-label": "#2e3440", "graph-highlight": "#d08770",
  sidebar: "#e5e9f0", "sidebar-foreground": "#2e3440",
  "sidebar-accent": "#d8dee9", "sidebar-accent-foreground": "#2e3440",
};

export const NORD_DARK: Theme = {
  name: "Nord Dark", mode: "dark", codeTheme: ["one-light", "nord"],
  background: "#2e3440", foreground: "#d8dee9", border: "#3b4252",
  card: "#3b4252", "card-foreground": "#eceff4",
  popover: "#3b4252", "popover-foreground": "#eceff4",
  muted: "#434c5e", "muted-foreground": "#81a1c1",
  primary: "#88c0d0", "primary-foreground": "#2e3440",
  secondary: "#434c5e", "secondary-foreground": "#d8dee9",
  accent: "#434c5e", "accent-foreground": "#eceff4",
  destructive: "#bf616a", input: "#3b4252", ring: "#5e81ac",
  "editor-heading": "#88c0d0", "editor-bold": "#eceff4",
  "editor-italic": "#b48ead", "editor-link": "#81a1c1",
  "editor-code": "#a3be8c", "editor-tag": "#8fbcbb",
  "editor-selection": "#434c5e", "editor-cursor": "#d8dee9",
  "editor-line-highlight": "#3b4252",
  "graph-note": "#81a1c1", "graph-tag": "#8fbcbb",
  "graph-memory": "#b48ead", "graph-chunk": "#4c566a",
  "graph-edge": "#434c5e", "graph-label": "#eceff4", "graph-highlight": "#d08770",
  sidebar: "#2e3440", "sidebar-foreground": "#d8dee9",
  "sidebar-accent": "#3b4252", "sidebar-accent-foreground": "#d8dee9",
};

// Everforest — soft green forest (sainnhe/everforest canonical colors)
export const EVERFOREST_LIGHT: Theme = {
  name: "Everforest Light", mode: "light", codeTheme: ["everforest-light", "everforest-dark"],
  background: "#fdf6e3", foreground: "#5c6a72", border: "#e6e2cc",
  card: "#f4f0d9", "card-foreground": "#5c6a72",
  popover: "#fdf6e3", "popover-foreground": "#5c6a72",
  muted: "#efebd4", "muted-foreground": "#829181",
  primary: "#8da101", "primary-foreground": "#fdf6e3",
  secondary: "#efebd4", "secondary-foreground": "#5c6a72",
  accent: "#e6e2cc", "accent-foreground": "#5c6a72",
  destructive: "#f85552", input: "#e0dcc7", ring: "#8da101",
  "editor-heading": "#f85552", "editor-bold": "#5c6a72",
  "editor-italic": "#df69ba", "editor-link": "#3a94c5",
  "editor-code": "#8da101", "editor-tag": "#35a77c",
  "editor-selection": "#c9c5ad", "editor-cursor": "#5c6a72",
  "editor-line-highlight": "#f4f0d9",
  "graph-note": "#829181", "graph-tag": "#3a94c5",
  "graph-memory": "#df69ba", "graph-chunk": "#bdc3af",
  "graph-edge": "#e6e2cc", "graph-label": "#5c6a72", "graph-highlight": "#dfa000",
  sidebar: "#efebd4", "sidebar-foreground": "#5c6a72",
  "sidebar-accent": "#e6e2cc", "sidebar-accent-foreground": "#5c6a72",
};

export const EVERFOREST_DARK: Theme = {
  name: "Everforest Dark", mode: "dark", codeTheme: ["everforest-light", "everforest-dark"],
  background: "#2d353b", foreground: "#d3c6aa", border: "#3d484d",
  card: "#343f44", "card-foreground": "#d3c6aa",
  popover: "#343f44", "popover-foreground": "#d3c6aa",
  muted: "#3d484d", "muted-foreground": "#859289",
  primary: "#a7c080", "primary-foreground": "#2d353b",
  secondary: "#3d484d", "secondary-foreground": "#d3c6aa",
  accent: "#475258", "accent-foreground": "#d3c6aa",
  destructive: "#e67e80", input: "#3d484d", ring: "#83c092",
  "editor-heading": "#e67e80", "editor-bold": "#d3c6aa",
  "editor-italic": "#d699b6", "editor-link": "#7fbbb3",
  "editor-code": "#a7c080", "editor-tag": "#83c092",
  "editor-selection": "#475258", "editor-cursor": "#d3c6aa",
  "editor-line-highlight": "#343f44",
  "graph-note": "#859289", "graph-tag": "#7fbbb3",
  "graph-memory": "#d699b6", "graph-chunk": "#4f585e",
  "graph-edge": "#475258", "graph-label": "#d3c6aa", "graph-highlight": "#dbbc7f",
  sidebar: "#232a2e", "sidebar-foreground": "#d3c6aa",
  "sidebar-accent": "#3d484d", "sidebar-accent-foreground": "#d3c6aa",
};

export const BUILTIN_THEMES: Theme[] = [
  MONOCHROME_LIGHT, MONOCHROME_DARK,
  GRUVBOX_LIGHT, GRUVBOX_DARK,
  TOKYO_NIGHT_LIGHT, TOKYO_NIGHT_DARK,
  CATPPUCCIN_LIGHT, CATPPUCCIN_DARK,
  NORD_LIGHT, NORD_DARK,
  EVERFOREST_LIGHT, EVERFOREST_DARK,
];

export const DEFAULT_THEME = MONOCHROME_DARK;

/** Maps old theme names to new ones for migration. */
export const THEME_MIGRATION: Record<string, string> = {
  Midnight: "Monochrome Dark",
  Dawn: "Gruvbox Light",
  Nord: "Nord Dark",
  "Solarized Dark": "Monochrome Dark",
};

// ─── Runtime application ────────────────────────────────────────

/** Apply a theme by setting CSS custom properties on the document root. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  for (const key of THEME_KEYS) {
    root.style.setProperty(`--${key}`, theme[key]);
  }
  // Toggle dark class for Tailwind dark: variant (shiki code blocks)
  if (theme.mode === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
  // Expose theme name so CSS can target specific themes (e.g. monochrome code blocks)
  root.dataset.theme = theme.name;
}
