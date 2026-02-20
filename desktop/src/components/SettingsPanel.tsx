import { useCallback, useEffect, useRef, useState } from "react";
import {
  getSettings,
  getBaseUrl,
  updateSettings,
  importVault,
  getOllamaModels,
  type Settings,
  type MCPServer,
} from "../lib/api";
import {
  BUILTIN_THEMES,
  DEFAULT_THEME,
  THEME_GROUPS,
  THEME_KEY_LABELS,
  THEME_MIGRATION,
  applyTheme,
  type Theme,
} from "../lib/themes";
import { isTauri, pickDirectory } from "../lib/tauri";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

interface ModelOption {
  value: string;
  label: string;
}

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "ollama", label: "Ollama" },
  { value: "claude-code", label: "Claude Code" },
] as const;

const SUGGESTED_MODELS: Record<string, ModelOption[]> = {
  anthropic: [
    { value: "claude-opus-4-6", label: "Claude Opus 4.6" },
    { value: "claude-sonnet-4-5-20250929", label: "Claude Sonnet 4.5" },
    { value: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5" },
  ],
  openai: [
    { value: "gpt-4o", label: "GPT-4o" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "o3-mini", label: "o3 Mini" },
  ],
  ollama: [
    { value: "llama3.3", label: "Llama 3.3" },
    { value: "mistral", label: "Mistral" },
    { value: "deepseek-r1", label: "DeepSeek R1" },
  ],
  "claude-code": [
    { value: "sonnet", label: "Sonnet" },
    { value: "opus", label: "Opus" },
    { value: "haiku", label: "Haiku" },
  ],
};

const TRANSCRIPTION_PROVIDERS = [
  { value: "openai", label: "OpenAI Whisper" },
  { value: "mistral", label: "Mistral Voxtral" },
] as const;

const SUGGESTED_TRANSCRIPTION_MODELS: Record<string, ModelOption[]> = {
  openai: [
    { value: "gpt-4o-mini-transcribe", label: "GPT-4o Mini Transcribe" },
    { value: "gpt-4o-transcribe", label: "GPT-4o Transcribe" },
    { value: "whisper-1", label: "Whisper 1" },
  ],
  mistral: [
    { value: "voxtral-mini-latest", label: "Voxtral Mini" },
  ],
};

const FONTS = [
  { value: "", label: "System Default" },
  { value: "Inter, system-ui, sans-serif", label: "Inter" },
  { value: "'SF Pro Display', system-ui, sans-serif", label: "SF Pro" },
  { value: "'JetBrains Mono', monospace", label: "JetBrains Mono" },
  { value: "'Fira Code', monospace", label: "Fira Code" },
  { value: "'Cascadia Code', monospace", label: "Cascadia Code" },
  { value: "'SF Mono', monospace", label: "SF Mono" },
  { value: "Menlo, monospace", label: "Menlo" },
  { value: "Monaco, monospace", label: "Monaco" },
];

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground pb-1 border-b border-border">
      {children}
    </h3>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="text-sm font-medium">{children}</label>;
}

function FieldHint({ children }: { children: React.ReactNode }) {
  return <p className="text-xs text-muted-foreground">{children}</p>;
}

function ModelSelect({
  value,
  suggestions,
  onChange,
  includeDefault,
}: {
  value: string;
  suggestions: ModelOption[];
  onChange: (value: string) => void;
  includeDefault?: boolean;
}) {
  const [customMode, setCustomMode] = useState(false);
  const customInputRef = useRef<HTMLInputElement>(null);
  const suggestionValues = suggestions.map((s) => s.value);
  const isCustomValue = value !== "" && !suggestionValues.includes(value);
  const showCustomInput = customMode || isCustomValue;

  return (
    <div className="space-y-1.5">
      <select
        value={showCustomInput ? "__custom__" : value}
        onChange={(e) => {
          if (e.target.value === "__custom__") {
            setCustomMode(true);
            if (suggestionValues.includes(value)) onChange("");
            setTimeout(() => customInputRef.current?.focus(), 0);
          } else {
            setCustomMode(false);
            onChange(e.target.value);
          }
        }}
        className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
      >
        {includeDefault && <option value="">Provider default</option>}
        {suggestions.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
        {showCustomInput && <option value="__custom__">{isCustomValue ? value : "Custom..."}</option>}
        {!showCustomInput && <option value="__custom__">Custom...</option>}
      </select>
      {showCustomInput && (
        <Input
          ref={customInputRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter model name..."
          className="h-8 text-sm"
          autoFocus={customMode && !isCustomValue}
        />
      )}
    </div>
  );
}

function ApiKeyField({
  label, value, isSet, onChange, placeholder, hint,
}: {
  label: string; value: string; isSet: boolean; onChange: (value: string) => void; placeholder: string; hint?: string;
}) {
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  if (isSet && !editing && !value) {
    return (
      <section className="space-y-1.5">
        <FieldLabel>{label}</FieldLabel>
        <div className="flex items-center gap-2 h-8">
          <span className="text-sm text-muted-foreground">Configured</span>
          <button onClick={() => { setEditing(true); setTimeout(() => inputRef.current?.focus(), 0); }} className="text-xs text-muted-foreground hover:text-foreground underline">Change</button>
        </div>
        {hint && <FieldHint>{hint}</FieldHint>}
      </section>
    );
  }

  return (
    <section className="space-y-1.5">
      <FieldLabel>{label}</FieldLabel>
      <Input ref={inputRef} type="password" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="h-8 text-sm" autoFocus={editing} />
      {hint && <FieldHint>{hint}</FieldHint>}
    </section>
  );
}

/** Color swatch with native color picker */
function ColorPicker({
  label, value, onChange,
}: {
  label: string; value: string; onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs text-muted-foreground truncate">{label}</span>
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <span className="text-[10px] font-mono text-muted-foreground/60 w-16 text-right">{value}</span>
        <label className="relative cursor-pointer">
          <span
            className="block w-6 h-6 rounded border border-border"
            style={{ backgroundColor: value }}
          />
          <input
            type="color"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
          />
        </label>
      </div>
    </div>
  );
}

export interface SettingsPanelProps {
  dirty: boolean;
  setDirty: (dirty: boolean) => void;
}

export function SettingsPanel({ dirty, setDirty }: SettingsPanelProps) {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);

  // Notes directory
  const [notesPath, setNotesPath] = useState("");

  // LLM settings
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [mistralKey, setMistralKey] = useState("");
  const [txProvider, setTxProvider] = useState("local");
  const [txModel, setTxModel] = useState("");
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([]);

  // Theme & appearance
  const [themeName, setThemeName] = useState(DEFAULT_THEME.name);
  const [themeOverrides, setThemeOverrides] = useState<Record<string, string>>({});
  const [customThemes, setCustomThemes] = useState<Theme[]>([]);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const [savingAsCustom, setSavingAsCustom] = useState(false);
  const [customThemeName, setCustomThemeName] = useState("");
  const [fontFamily, setFontFamily] = useState("");
  const [editorFontSize, setEditorFontSize] = useState(14);

  // Editor
  const [editorKeymap, setEditorKeymap] = useState("vim");
  const [editorLineNumbers, setEditorLineNumbers] = useState(false);
  const [editorWordWrap, setEditorWordWrap] = useState(true);
  const [editorInlineFormatting, setEditorInlineFormatting] = useState(false);

  // Ollama
  const [ollamaModels, setOllamaModels] = useState<ModelOption[]>([]);
  const [ollamaError, setOllamaError] = useState("");
  const [ollamaLoading, setOllamaLoading] = useState(false);

  // MCP connection URL
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpCopied, setMcpCopied] = useState(false);

  // Import
  const [importPath, setImportPath] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ files_copied: number; files_skipped: number; folders_created: number } | null>(null);
  const [importError, setImportError] = useState("");

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      const s = await getSettings();
      setSettings(s);
      setNotesPath(s.notes_path || "");
      setProvider(s.llm_provider);
      setModel(s.llm_model);
      setOllamaUrl(s.ollama_base_url);
      // "local" (mlx-whisper) can't work in the desktop app; default to openai
      setTxProvider(s.transcription_provider === "local" || !s.transcription_provider ? "openai" : s.transcription_provider);
      setTxModel(s.transcription_model || "");
      setMcpServers(s.mcp_servers || []);
      setAnthropicKey("");
      setOpenaiKey("");
      setMistralKey("");

      // Theme
      const t = s.theme || {};
      let loadedName = t.name || DEFAULT_THEME.name;
      if (loadedName in THEME_MIGRATION) loadedName = THEME_MIGRATION[loadedName];
      setThemeName(loadedName);
      const overrides = { ...t };
      delete overrides.name;
      setThemeOverrides(overrides);

      // Custom themes
      const ct = (s.custom_themes || []).map((raw: Record<string, string>) => ({
        ...DEFAULT_THEME,
        ...raw,
        mode: (raw.mode as "light" | "dark") || "dark",
        codeTheme: raw.codeTheme ? JSON.parse(raw.codeTheme as string) : DEFAULT_THEME.codeTheme,
      })) as Theme[];
      setCustomThemes(ct);

      // Fonts & editor
      setFontFamily(s.font_family || "");
      setEditorFontSize(s.editor_font_size || 14);
      setEditorKeymap(s.editor_keymap || "vim");
      setEditorLineNumbers(s.editor_line_numbers ?? false);
      setEditorWordWrap(s.editor_word_wrap ?? true);
      setEditorInlineFormatting(s.editor_inline_formatting ?? false);
    } catch (err) {
      console.error("Failed to load settings:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSettings(); }, [fetchSettings]);

  // Resolve MCP connection URL
  useEffect(() => {
    getBaseUrl().then((base) => setMcpUrl(`${base}/mcp`));
  }, []);

  // Fetch Ollama models when provider is ollama
  useEffect(() => {
    if (provider !== "ollama") {
      setOllamaModels([]);
      setOllamaError("");
      return;
    }
    const url = ollamaUrl || "http://localhost:11434";
    setOllamaLoading(true);
    setOllamaError("");
    getOllamaModels(url)
      .then((data) => {
        const models = data.models.map((m) => ({
          value: m.name,
          label: m.name,
        }));
        setOllamaModels(models);
        if (models.length > 0 && !model) {
          setModel(models[0].value);
        }
      })
      .catch((err) => {
        setOllamaError(
          err instanceof Error && err.message.includes("502")
            ? `Cannot connect to Ollama at ${url}`
            : "Failed to fetch Ollama models"
        );
        setOllamaModels([]);
      })
      .finally(() => setOllamaLoading(false));
  }, [provider, ollamaUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live preview: apply theme as user changes colors
  const livePreviewTheme = useCallback(() => {
    const base =
      BUILTIN_THEMES.find((t) => t.name === themeName) ||
      customThemes.find((t) => t.name === themeName) ||
      DEFAULT_THEME;
    const merged = { ...base, ...themeOverrides, name: themeName } as Theme;
    applyTheme(merged);
  }, [themeName, themeOverrides, customThemes]);

  useEffect(() => { livePreviewTheme(); }, [livePreviewTheme]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const themeData: Record<string, string> = { name: themeName, ...themeOverrides };
      // Serialize custom themes for storage
      const serializedCustomThemes = customThemes.map((t) => {
        const obj: Record<string, string> = {};
        for (const [k, v] of Object.entries(t)) {
          obj[k] = k === "codeTheme" ? JSON.stringify(v) : String(v);
        }
        return obj;
      });
      const updates: Record<string, unknown> = {
        notes_path: notesPath,
        llm_provider: provider,
        llm_model: model,
        ollama_base_url: ollamaUrl,
        transcription_provider: txProvider,
        transcription_model: txModel,
        mcp_servers: mcpServers,
        theme: themeData,
        custom_themes: serializedCustomThemes,
        font_family: fontFamily,
        editor_font_size: editorFontSize,
        editor_keymap: editorKeymap,
        editor_line_numbers: editorLineNumbers,
        editor_word_wrap: editorWordWrap,
        editor_inline_formatting: editorInlineFormatting,
      };
      if (anthropicKey) updates.anthropic_api_key = anthropicKey;
      if (openaiKey) updates.openai_api_key = openaiKey;
      if (mistralKey) updates.mistral_api_key = mistralKey;
      const s = await updateSettings(updates as Parameters<typeof updateSettings>[0]);
      setSettings(s);
      setDirty(false);
      setAnthropicKey("");
      setOpenaiKey("");
      setMistralKey("");
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    } catch (err) {
      console.error("Failed to save settings:", err);
    } finally {
      setSaving(false);
    }
  };

  const markDirty = () => setDirty(true);

  const handleThemeChange = (name: string) => {
    setThemeName(name);
    setThemeOverrides({});
    markDirty();
  };

  const handleColorChange = (key: string, value: string) => {
    setThemeOverrides((prev) => ({ ...prev, [key]: value }));
    markDirty();
  };

  const handleResetColors = () => {
    setThemeOverrides({});
    markDirty();
  };

  const handleSaveCustomTheme = () => {
    const name = customThemeName.trim();
    if (!name) return;
    const base = BUILTIN_THEMES.find((t) => t.name === themeName) ||
      customThemes.find((t) => t.name === themeName) || DEFAULT_THEME;
    const newTheme: Theme = {
      ...base,
      ...themeOverrides,
      name,
      mode: base.mode,
      codeTheme: base.codeTheme,
    } as Theme;
    setCustomThemes((prev) => [...prev.filter((t) => t.name !== name), newTheme]);
    setThemeName(name);
    setThemeOverrides({});
    setSavingAsCustom(false);
    setCustomThemeName("");
    markDirty();
  };

  const handleImport = async () => {
    if (!importPath.trim()) return;
    setImporting(true);
    setImportResult(null);
    setImportError("");
    try {
      const result = await importVault(importPath.trim());
      setImportResult(result.stats);
    } catch (err) {
      setImportError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Loading settings...
      </div>
    );
  }

  const suggestions = provider === "ollama"
    ? ollamaModels
    : (SUGGESTED_MODELS[provider] || []);
  const txSuggestions = SUGGESTED_TRANSCRIPTION_MODELS[txProvider] || [];
  const currentBaseTheme =
    BUILTIN_THEMES.find((t) => t.name === themeName) ||
    customThemes.find((t) => t.name === themeName) ||
    DEFAULT_THEME;

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-lg mx-auto p-6 space-y-8">

          {/* ── Notes Directory ── */}
          <div className="space-y-4">
            <SectionHeading>Notes Directory</SectionHeading>
            <section className="space-y-1.5">
              <FieldLabel>Path</FieldLabel>
              <div className="flex gap-2">
                <Input
                  value={notesPath}
                  onChange={(e) => { setNotesPath(e.target.value); markDirty(); }}
                  placeholder="~/brainshape"
                  className="h-8 text-sm flex-1"
                />
                {isTauri() && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8"
                    onClick={async () => {
                      const dir = await pickDirectory("Select Notes Directory");
                      if (dir) { setNotesPath(dir); markDirty(); }
                    }}
                  >
                    Browse
                  </Button>
                )}
              </div>
              <FieldHint>Directory where your markdown notes are stored.</FieldHint>
            </section>
          </div>

          {/* ── Appearance ── */}
          <div className="space-y-4">
            <SectionHeading>Appearance</SectionHeading>

            <section className="space-y-1.5">
              <FieldLabel>Theme</FieldLabel>
              <div className="flex gap-2">
                <select
                  value={themeName}
                  onChange={(e) => handleThemeChange(e.target.value)}
                  className="flex-1 h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
                >
                  <optgroup label="Built-in">
                    {BUILTIN_THEMES.map((t) => (
                      <option key={t.name} value={t.name}>{t.name}</option>
                    ))}
                  </optgroup>
                  {customThemes.length > 0 && (
                    <optgroup label="Custom">
                      {customThemes.map((t) => (
                        <option key={t.name} value={t.name}>{t.name}</option>
                      ))}
                    </optgroup>
                  )}
                </select>
                <Button
                  variant={customizeOpen ? "secondary" : "outline"}
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setCustomizeOpen(!customizeOpen)}
                >
                  {customizeOpen ? "Close" : "Customize"}
                </Button>
              </div>
              {customThemes.some((t) => t.name === themeName) && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs text-destructive"
                  onClick={() => {
                    setCustomThemes((prev) => prev.filter((t) => t.name !== themeName));
                    setThemeName(DEFAULT_THEME.name);
                    setThemeOverrides({});
                    markDirty();
                  }}
                >
                  Delete custom theme
                </Button>
              )}
            </section>

            {customizeOpen && (
              <div className="border border-border rounded-md p-3 space-y-4">
                {THEME_GROUPS.map((group) => (
                  <div key={group.label} className="space-y-2">
                    <p className="text-xs font-medium text-foreground">{group.label}</p>
                    <div className="space-y-1.5">
                      {group.keys.map((key) => (
                        <ColorPicker
                          key={key}
                          label={THEME_KEY_LABELS[key]}
                          value={themeOverrides[key] || currentBaseTheme[key]}
                          onChange={(v) => handleColorChange(key, v)}
                        />
                      ))}
                    </div>
                  </div>
                ))}
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" className="text-xs flex-1" onClick={handleResetColors}>
                    Reset to defaults
                  </Button>
                  {savingAsCustom ? (
                    <div className="flex gap-1 flex-1">
                      <Input
                        value={customThemeName}
                        onChange={(e) => setCustomThemeName(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleSaveCustomTheme();
                          if (e.key === "Escape") {
                            setSavingAsCustom(false);
                            setCustomThemeName("");
                          }
                        }}
                        placeholder="Theme name..."
                        className="h-7 text-xs flex-1"
                        autoFocus
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={handleSaveCustomTheme}
                        disabled={!customThemeName.trim()}
                      >
                        Save
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs flex-1"
                      onClick={() => setSavingAsCustom(true)}
                    >
                      Save as Custom
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* ── Fonts ── */}
          <div className="space-y-4">
            <SectionHeading>Fonts</SectionHeading>

            <section className="space-y-1.5">
              <FieldLabel>Font</FieldLabel>
              <select
                value={fontFamily}
                onChange={(e) => { setFontFamily(e.target.value); markDirty(); }}
                className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
              >
                {FONTS.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
              <FieldHint>Applied to the entire app including the editor and preview.</FieldHint>
            </section>

            <section className="space-y-1.5">
              <div className="flex items-center justify-between">
                <FieldLabel>Editor Font Size</FieldLabel>
                <span className="text-xs text-muted-foreground tabular-nums">{editorFontSize}px</span>
              </div>
              <input
                type="range"
                min={10}
                max={24}
                step={1}
                value={editorFontSize}
                onChange={(e) => { setEditorFontSize(Number(e.target.value)); markDirty(); }}
                className="w-full h-1.5 accent-primary"
              />
            </section>
          </div>

          {/* ── Editor ── */}
          <div className="space-y-4">
            <SectionHeading>Editor</SectionHeading>

            <section className="space-y-1.5">
              <FieldLabel>Keybindings</FieldLabel>
              <div className="flex gap-1">
                {(["default", "vim"] as const).map((mode) => (
                  <Button
                    key={mode}
                    variant={editorKeymap === mode ? "secondary" : "outline"}
                    size="sm"
                    className="h-7 text-xs flex-1"
                    onClick={() => { setEditorKeymap(mode); markDirty(); }}
                  >
                    {mode === "default" ? "Default" : "Vim"}
                  </Button>
                ))}
              </div>
            </section>

            <section className="flex items-center justify-between">
              <FieldLabel>Line Numbers</FieldLabel>
              <button
                role="switch"
                aria-checked={editorLineNumbers}
                aria-label="Line Numbers"
                onClick={() => { setEditorLineNumbers(!editorLineNumbers); markDirty(); }}
                className={`relative w-9 h-5 rounded-full transition-colors ${editorLineNumbers ? "bg-primary" : "bg-muted"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${editorLineNumbers ? "translate-x-4" : ""}`} />
              </button>
            </section>

            <section className="flex items-center justify-between">
              <FieldLabel>Word Wrap</FieldLabel>
              <button
                role="switch"
                aria-checked={editorWordWrap}
                aria-label="Word Wrap"
                onClick={() => { setEditorWordWrap(!editorWordWrap); markDirty(); }}
                className={`relative w-9 h-5 rounded-full transition-colors ${editorWordWrap ? "bg-primary" : "bg-muted"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${editorWordWrap ? "translate-x-4" : ""}`} />
              </button>
            </section>

            <section className="space-y-1">
              <div className="flex items-center justify-between">
                <FieldLabel>Inline Formatting</FieldLabel>
                <button
                  role="switch"
                  aria-checked={editorInlineFormatting}
                  aria-label="Inline Formatting"
                  onClick={() => { setEditorInlineFormatting(!editorInlineFormatting); markDirty(); }}
                  className={`relative w-9 h-5 rounded-full transition-colors ${editorInlineFormatting ? "bg-primary" : "bg-muted"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${editorInlineFormatting ? "translate-x-4" : ""}`} />
                </button>
              </div>
              <FieldHint>Render headings, bold, italic inline while editing.</FieldHint>
            </section>
          </div>

          {/* ── Import Notes ── */}
          <div className="space-y-4">
            <SectionHeading>Import Notes</SectionHeading>
            <FieldHint>
              Copy markdown notes from another directory into your Brainshape notes folder.
              Preserves folder structure. Only .md files are imported.
            </FieldHint>

            <section className="space-y-1.5">
              <FieldLabel>Source Directory</FieldLabel>
              <div className="flex gap-2">
                <Input
                  value={importPath}
                  onChange={(e) => { setImportPath(e.target.value); setImportResult(null); setImportError(""); }}
                  placeholder="~/Documents/Obsidian Vault"
                  className="h-8 text-sm flex-1"
                />
                {isTauri() && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8"
                    onClick={async () => {
                      const dir = await pickDirectory("Select Vault to Import");
                      if (dir) { setImportPath(dir); setImportResult(null); setImportError(""); }
                    }}
                  >
                    Browse
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8"
                  onClick={handleImport}
                  disabled={importing || !importPath.trim()}
                >
                  {importing ? "Importing..." : "Import"}
                </Button>
              </div>
            </section>

            {importResult && (
              <div className="text-sm border border-border rounded-md p-3 space-y-1">
                <p className="font-medium text-foreground">Import complete</p>
                <p className="text-muted-foreground">
                  {importResult.files_copied} files copied, {importResult.files_skipped} skipped, {importResult.folders_created} folders created
                </p>
              </div>
            )}

            {importError && (
              <p className="text-sm text-destructive">{importError}</p>
            )}
          </div>

          {/* ── Language Model ── */}
          <div className="space-y-4">
            <SectionHeading>Language Model</SectionHeading>

            <section className="space-y-1.5">
              <FieldLabel>Provider</FieldLabel>
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  const defaults = SUGGESTED_MODELS[e.target.value];
                  if (defaults?.length) setModel(defaults[0].value);
                  markDirty();
                }}
                className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </section>

            <section className="space-y-1.5">
              <FieldLabel>Model</FieldLabel>
              <ModelSelect value={model} suggestions={suggestions} onChange={(v) => { setModel(v); markDirty(); }} />
            </section>

            {provider === "anthropic" && (
              <ApiKeyField label="API Key" value={anthropicKey} isSet={!!settings?.anthropic_api_key_set} onChange={(v) => { setAnthropicKey(v); markDirty(); }} placeholder="sk-ant-..." hint="Can also be set via ANTHROPIC_API_KEY environment variable." />
            )}
            {provider === "openai" && (
              <ApiKeyField label="API Key" value={openaiKey} isSet={!!settings?.openai_api_key_set} onChange={(v) => { setOpenaiKey(v); markDirty(); }} placeholder="sk-..." />
            )}
            {provider === "ollama" && (
              <>
                <section className="space-y-1.5">
                  <FieldLabel>Base URL</FieldLabel>
                  <Input value={ollamaUrl} onChange={(e) => { setOllamaUrl(e.target.value); markDirty(); }} placeholder="http://localhost:11434" className="h-8 text-sm" />
                  {ollamaLoading && <FieldHint>Connecting to Ollama...</FieldHint>}
                  {ollamaError && (
                    <p className="text-xs text-destructive">
                      {ollamaError}. For a remote machine, set the URL to <code className="bg-muted px-1 rounded text-[11px]">http://HOSTNAME:11434</code>
                    </p>
                  )}
                  {!ollamaLoading && !ollamaError && ollamaModels.length > 0 && (
                    <FieldHint>Connected — {ollamaModels.length} model{ollamaModels.length !== 1 ? "s" : ""} installed.</FieldHint>
                  )}
                  {!ollamaLoading && !ollamaError && ollamaModels.length === 0 && (
                    <FieldHint>No models found. Run <code className="bg-muted px-1 rounded text-[11px]">ollama pull llama3.1</code> to install one.</FieldHint>
                  )}
                </section>
              </>
            )}
            {provider === "claude-code" && (
              <FieldHint>Uses your Claude Code subscription. No API key needed. Requires the <code className="bg-muted px-1 rounded text-[11px]">claude</code> CLI to be installed.</FieldHint>
            )}
          </div>

          {/* ── Voice Transcription ── */}
          <div className="space-y-4">
            <SectionHeading>Voice Transcription</SectionHeading>

            <section className="space-y-1.5">
              <FieldLabel>Provider</FieldLabel>
              <select
                value={txProvider}
                onChange={(e) => { setTxProvider(e.target.value); setTxModel(""); markDirty(); }}
                className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
              >
                {TRANSCRIPTION_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </section>

            <section className="space-y-1.5">
              <FieldLabel>Model</FieldLabel>
              <ModelSelect value={txModel} suggestions={txSuggestions} onChange={(v) => { setTxModel(v); markDirty(); }} includeDefault />
              <FieldHint>Leave empty to use the provider's default model.</FieldHint>
            </section>

            {txProvider === "openai" && (
              <ApiKeyField label="OpenAI API Key" value={openaiKey} isSet={!!settings?.openai_api_key_set} onChange={(v) => { setOpenaiKey(v); markDirty(); }} placeholder="sk-..." hint="Shared with the OpenAI LLM provider above." />
            )}
            {txProvider === "mistral" && (
              <ApiKeyField label="Mistral API Key" value={mistralKey} isSet={!!settings?.mistral_api_key_set} onChange={(v) => { setMistralKey(v); markDirty(); }} placeholder="mk-..." hint="Can also be set via MISTRAL_API_KEY environment variable." />
            )}
          </div>

          {/* ── MCP Connection ── */}
          <div className="space-y-4">
            <SectionHeading>MCP Connection</SectionHeading>
            <FieldHint>
              Connect external AI agents (Claude Desktop, Claude Code, etc.) to Brainshape using this URL.
            </FieldHint>
            <div className="flex items-center gap-2">
              <Input
                value={mcpUrl}
                readOnly
                className="h-8 text-sm font-mono bg-muted"
                onClick={(e) => (e.target as HTMLInputElement).select()}
              />
              <Button
                variant="secondary"
                size="sm"
                className="h-8 px-3 shrink-0"
                onClick={() => {
                  navigator.clipboard.writeText(mcpUrl);
                  setMcpCopied(true);
                  setTimeout(() => setMcpCopied(false), 2000);
                }}
              >
                {mcpCopied ? "Copied" : "Copy"}
              </Button>
            </div>
          </div>

          {/* ── MCP Servers ── */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SectionHeading>MCP Servers</SectionHeading>
              <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={() => { setMcpServers([...mcpServers, { name: "", transport: "stdio", command: "", args: [] }]); markDirty(); }}>
                + Add
              </Button>
            </div>
            <FieldHint>Connect external MCP servers to extend the agent with additional tools.</FieldHint>

            {mcpServers.map((server, i) => (
              <div key={i} className="border border-border rounded-md p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <Input
                    value={server.name}
                    onChange={(e) => { const u = [...mcpServers]; u[i] = { ...u[i], name: e.target.value }; setMcpServers(u); markDirty(); }}
                    placeholder="Server name"
                    className="h-7 text-sm flex-1 font-medium"
                  />
                  <select
                    value={server.transport}
                    onChange={(e) => { const u = [...mcpServers]; u[i] = { ...u[i], transport: e.target.value as "stdio" | "http" }; setMcpServers(u); markDirty(); }}
                    className="h-7 text-xs rounded-md border border-input bg-background px-2 text-foreground"
                  >
                    <option value="stdio">stdio</option>
                    <option value="http">http</option>
                  </select>
                  <Button variant="ghost" size="sm" className="h-7 text-xs text-destructive px-2" onClick={() => { setMcpServers(mcpServers.filter((_, j) => j !== i)); markDirty(); }}>
                    Remove
                  </Button>
                </div>
                {server.transport === "stdio" ? (
                  <>
                    <div className="space-y-0.5">
                      <label className="text-xs text-muted-foreground">Executable</label>
                      <Input value={server.command || ""} onChange={(e) => { const u = [...mcpServers]; u[i] = { ...u[i], command: e.target.value }; setMcpServers(u); markDirty(); }} placeholder="e.g., npx, python, node" className="h-7 text-sm" />
                    </div>
                    <div className="space-y-0.5">
                      <label className="text-xs text-muted-foreground">Arguments</label>
                      <Input value={(server.args || []).join(" ")} onChange={(e) => { const u = [...mcpServers]; u[i] = { ...u[i], args: e.target.value.split(" ").filter(Boolean) }; setMcpServers(u); markDirty(); }} placeholder="Space-separated arguments" className="h-7 text-sm" />
                    </div>
                  </>
                ) : (
                  <div className="space-y-0.5">
                    <label className="text-xs text-muted-foreground">URL</label>
                    <Input value={server.url || ""} onChange={(e) => { const u = [...mcpServers]; u[i] = { ...u[i], url: e.target.value }; setMcpServers(u); markDirty(); }} placeholder="e.g., http://localhost:8000/mcp" className="h-7 text-sm" />
                  </div>
                )}
              </div>
            ))}
            {mcpServers.length === 0 && (
              <p className="text-xs text-muted-foreground/60 text-center py-2">No MCP servers configured.</p>
            )}
          </div>

          {/* ── Save ── */}
          <div className="pt-2 pb-4">
            <Button onClick={handleSave} disabled={!dirty || saving} className="w-full">
              {saving ? "Saving..." : savedFlash ? "Saved" : "Save Settings"}
            </Button>
            {dirty && (
              <p className="text-xs text-muted-foreground mt-1 text-center">
                Changes require restarting the agent session to take effect.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
