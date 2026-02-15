import { useCallback, useEffect, useState } from "react";
import { getSettings, updateSettings, type Settings, type MCPServer } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

const PROVIDERS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "ollama", label: "Ollama" },
] as const;

const SUGGESTED_MODELS: Record<string, string[]> = {
  anthropic: [
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
  ],
  openai: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
  ollama: ["llama3.3", "mistral", "deepseek-r1"],
};

export function SettingsPanel() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Local form state
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [whisperModel, setWhisperModel] = useState("");
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([]);

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      const s = await getSettings();
      setSettings(s);
      setProvider(s.llm_provider);
      setModel(s.llm_model);
      setOllamaUrl(s.ollama_base_url);
      setWhisperModel(s.whisper_model);
      setMcpServers(s.mcp_servers || []);
      setOpenaiKey("");
    } catch (err) {
      console.error("Failed to load settings:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updates: Record<string, unknown> = {
        llm_provider: provider,
        llm_model: model,
        ollama_base_url: ollamaUrl,
        whisper_model: whisperModel,
        mcp_servers: mcpServers,
      };
      if (openaiKey) {
        updates.openai_api_key = openaiKey;
      }
      const s = await updateSettings(updates as Parameters<typeof updateSettings>[0]);
      setSettings(s);
      setDirty(false);
      setOpenaiKey("");
    } catch (err) {
      console.error("Failed to save settings:", err);
    } finally {
      setSaving(false);
    }
  };

  const markDirty = () => setDirty(true);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
        Loading settings...
      </div>
    );
  }

  const suggestions = SUGGESTED_MODELS[provider] || [];

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="px-3 py-1.5 border-b border-border text-xs text-muted-foreground">
        Settings
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-lg mx-auto p-6 space-y-6">
          {/* LLM Provider */}
          <section className="space-y-2">
            <label className="text-sm font-medium">LLM Provider</label>
            <div className="flex gap-2">
              {PROVIDERS.map((p) => (
                <Button
                  key={p.value}
                  variant={provider === p.value ? "secondary" : "ghost"}
                  size="sm"
                  className="h-8"
                  onClick={() => {
                    setProvider(p.value);
                    const defaults = SUGGESTED_MODELS[p.value];
                    if (defaults?.length) setModel(defaults[0]);
                    markDirty();
                  }}
                >
                  {p.label}
                </Button>
              ))}
            </div>
          </section>

          {/* Model */}
          <section className="space-y-2">
            <label className="text-sm font-medium">Model</label>
            <Input
              value={model}
              onChange={(e) => {
                setModel(e.target.value);
                markDirty();
              }}
              placeholder="Model name..."
              className="h-8 text-sm"
            />
            {suggestions.length > 0 && (
              <div className="flex gap-1 flex-wrap">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setModel(s);
                      markDirty();
                    }}
                    className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                      model === s
                        ? "border-primary bg-primary/10 text-foreground"
                        : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </section>

          {/* Provider-specific settings */}
          {provider === "ollama" && (
            <section className="space-y-2">
              <label className="text-sm font-medium">Ollama Base URL</label>
              <Input
                value={ollamaUrl}
                onChange={(e) => {
                  setOllamaUrl(e.target.value);
                  markDirty();
                }}
                placeholder="http://localhost:11434"
                className="h-8 text-sm"
              />
            </section>
          )}

          {provider === "openai" && (
            <section className="space-y-2">
              <label className="text-sm font-medium">OpenAI API Key</label>
              <Input
                type="password"
                value={openaiKey}
                onChange={(e) => {
                  setOpenaiKey(e.target.value);
                  markDirty();
                }}
                placeholder={
                  settings?.openai_api_key_set
                    ? "Key is set (enter new to update)"
                    : "sk-..."
                }
                className="h-8 text-sm"
              />
            </section>
          )}

          {/* Whisper model */}
          <section className="space-y-2">
            <label className="text-sm font-medium">Whisper Model</label>
            <Input
              value={whisperModel}
              onChange={(e) => {
                setWhisperModel(e.target.value);
                markDirty();
              }}
              placeholder="mlx-community/whisper-large-v3-turbo"
              className="h-8 text-sm"
            />
            <p className="text-xs text-muted-foreground">
              Used for local voice transcription. Requires Apple Silicon.
            </p>
          </section>

          {/* MCP Servers */}
          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">MCP Servers</label>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => {
                  setMcpServers([
                    ...mcpServers,
                    { name: "", transport: "stdio", command: "", args: [] },
                  ]);
                  markDirty();
                }}
              >
                + Add Server
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Connect external MCP servers to extend the agent with additional tools.
            </p>
            {mcpServers.map((server, i) => (
              <div
                key={i}
                className="border border-border rounded-md p-3 space-y-2"
              >
                <div className="flex items-center gap-2">
                  <Input
                    value={server.name}
                    onChange={(e) => {
                      const updated = [...mcpServers];
                      updated[i] = { ...updated[i], name: e.target.value };
                      setMcpServers(updated);
                      markDirty();
                    }}
                    placeholder="Server name"
                    className="h-7 text-sm flex-1"
                  />
                  <div className="flex gap-1">
                    {(["stdio", "http"] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => {
                          const updated = [...mcpServers];
                          updated[i] = { ...updated[i], transport: t };
                          setMcpServers(updated);
                          markDirty();
                        }}
                        className={`text-xs px-2 py-0.5 rounded border transition-colors ${
                          server.transport === t
                            ? "border-primary bg-primary/10 text-foreground"
                            : "border-border text-muted-foreground"
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs text-destructive px-2"
                    onClick={() => {
                      setMcpServers(mcpServers.filter((_, j) => j !== i));
                      markDirty();
                    }}
                  >
                    Remove
                  </Button>
                </div>
                {server.transport === "stdio" ? (
                  <>
                    <Input
                      value={server.command || ""}
                      onChange={(e) => {
                        const updated = [...mcpServers];
                        updated[i] = { ...updated[i], command: e.target.value };
                        setMcpServers(updated);
                        markDirty();
                      }}
                      placeholder="Command (e.g., npx, python, node)"
                      className="h-7 text-sm"
                    />
                    <Input
                      value={(server.args || []).join(" ")}
                      onChange={(e) => {
                        const updated = [...mcpServers];
                        updated[i] = {
                          ...updated[i],
                          args: e.target.value.split(" ").filter(Boolean),
                        };
                        setMcpServers(updated);
                        markDirty();
                      }}
                      placeholder="Args (space-separated)"
                      className="h-7 text-sm"
                    />
                  </>
                ) : (
                  <Input
                    value={server.url || ""}
                    onChange={(e) => {
                      const updated = [...mcpServers];
                      updated[i] = { ...updated[i], url: e.target.value };
                      setMcpServers(updated);
                      markDirty();
                    }}
                    placeholder="URL (e.g., http://localhost:8000/mcp)"
                    className="h-7 text-sm"
                  />
                )}
              </div>
            ))}
            {mcpServers.length === 0 && (
              <p className="text-xs text-muted-foreground/60 text-center py-2">
                No MCP servers configured.
              </p>
            )}
          </section>

          {/* Save */}
          <div className="pt-2">
            <Button
              onClick={handleSave}
              disabled={!dirty || saving}
              className="w-full"
            >
              {saving ? "Saving..." : dirty ? "Save Settings" : "Settings Saved"}
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
