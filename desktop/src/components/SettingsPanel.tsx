import { useCallback, useEffect, useState } from "react";
import {
  getSettings,
  updateSettings,
  type Settings,
  type MCPServer,
} from "../lib/api";
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

const TRANSCRIPTION_PROVIDERS = [
  { value: "local", label: "Local (mlx-whisper)" },
  { value: "openai", label: "OpenAI Whisper" },
  { value: "mistral", label: "Mistral Voxtral" },
] as const;

const SUGGESTED_TRANSCRIPTION_MODELS: Record<string, string[]> = {
  local: ["mlx-community/whisper-small", "mlx-community/whisper-large-v3-turbo"],
  openai: ["gpt-4o-mini-transcribe", "gpt-4o-transcribe", "whisper-1"],
  mistral: ["voxtral-mini-latest"],
};

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

export function SettingsPanel() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  // Local form state
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiKey, setOpenaiKey] = useState("");
  const [mistralKey, setMistralKey] = useState("");
  const [txProvider, setTxProvider] = useState("local");
  const [txModel, setTxModel] = useState("");
  const [mcpServers, setMcpServers] = useState<MCPServer[]>([]);

  const fetchSettings = useCallback(async () => {
    try {
      setLoading(true);
      const s = await getSettings();
      setSettings(s);
      setProvider(s.llm_provider);
      setModel(s.llm_model);
      setOllamaUrl(s.ollama_base_url);
      setTxProvider(s.transcription_provider || "local");
      setTxModel(s.transcription_model || "");
      setMcpServers(s.mcp_servers || []);
      setAnthropicKey("");
      setOpenaiKey("");
      setMistralKey("");
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
        transcription_provider: txProvider,
        transcription_model: txModel,
        mcp_servers: mcpServers,
      };
      if (anthropicKey) updates.anthropic_api_key = anthropicKey;
      if (openaiKey) updates.openai_api_key = openaiKey;
      if (mistralKey) updates.mistral_api_key = mistralKey;
      const s = await updateSettings(
        updates as Parameters<typeof updateSettings>[0]
      );
      setSettings(s);
      setDirty(false);
      setAnthropicKey("");
      setOpenaiKey("");
      setMistralKey("");
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
        <div className="max-w-lg mx-auto p-6 space-y-8">
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
                  if (defaults?.length) setModel(defaults[0]);
                  markDirty();
                }}
                className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
              >
                {PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </section>

            <section className="space-y-1.5">
              <FieldLabel>Model</FieldLabel>
              <select
                value={suggestions.includes(model) ? model : "__custom__"}
                onChange={(e) => {
                  if (e.target.value !== "__custom__") {
                    setModel(e.target.value);
                    markDirty();
                  }
                }}
                className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
              >
                {suggestions.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
                {!suggestions.includes(model) && (
                  <option value="__custom__">{model || "Custom..."}</option>
                )}
                {suggestions.includes(model) && (
                  <option value="__custom__">Custom...</option>
                )}
              </select>
              {(!suggestions.includes(model) ||
                model === "__custom__") && (
                <Input
                  value={model === "__custom__" ? "" : model}
                  onChange={(e) => {
                    setModel(e.target.value);
                    markDirty();
                  }}
                  placeholder="Enter custom model name..."
                  className="h-8 text-sm"
                />
              )}
            </section>
          </div>

          {/* ── API Keys ── */}
          <div className="space-y-4">
            <SectionHeading>API Keys</SectionHeading>

            {provider === "anthropic" && (
              <section className="space-y-1.5">
                <FieldLabel>Anthropic API Key</FieldLabel>
                <Input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => {
                    setAnthropicKey(e.target.value);
                    markDirty();
                  }}
                  placeholder={
                    settings?.anthropic_api_key_set
                      ? "Key is set (enter new to update)"
                      : "sk-ant-..."
                  }
                  className="h-8 text-sm"
                />
                <FieldHint>
                  Can also be set via ANTHROPIC_API_KEY environment variable.
                </FieldHint>
              </section>
            )}

            {provider === "openai" && (
              <section className="space-y-1.5">
                <FieldLabel>OpenAI API Key</FieldLabel>
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

            {provider === "ollama" && (
              <section className="space-y-1.5">
                <FieldLabel>Ollama Base URL</FieldLabel>
                <Input
                  value={ollamaUrl}
                  onChange={(e) => {
                    setOllamaUrl(e.target.value);
                    markDirty();
                  }}
                  placeholder="http://localhost:11434"
                  className="h-8 text-sm"
                />
                <FieldHint>No API key needed for local Ollama.</FieldHint>
              </section>
            )}
          </div>

          {/* ── Voice ── */}
          <div className="space-y-4">
            <SectionHeading>Voice Transcription</SectionHeading>

            <section className="space-y-1.5">
              <FieldLabel>Provider</FieldLabel>
              <select
                value={txProvider}
                onChange={(e) => {
                  setTxProvider(e.target.value);
                  setTxModel("");
                  markDirty();
                }}
                className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
              >
                {TRANSCRIPTION_PROVIDERS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
              {txProvider === "local" && (
                <FieldHint>
                  Runs locally via mlx-whisper. Requires Apple Silicon.
                </FieldHint>
              )}
            </section>

            <section className="space-y-1.5">
              <FieldLabel>Model</FieldLabel>
              {(() => {
                const txSuggestions =
                  SUGGESTED_TRANSCRIPTION_MODELS[txProvider] || [];
                return (
                  <>
                    <select
                      value={
                        txSuggestions.includes(txModel) ? txModel : "__custom__"
                      }
                      onChange={(e) => {
                        if (e.target.value !== "__custom__") {
                          setTxModel(e.target.value);
                          markDirty();
                        }
                      }}
                      className="w-full h-8 text-sm rounded-md border border-input bg-background px-3 text-foreground"
                    >
                      <option value="">Provider default</option>
                      {txSuggestions.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                      {txModel && !txSuggestions.includes(txModel) && (
                        <option value="__custom__">{txModel}</option>
                      )}
                      {(txModel === "" || txSuggestions.includes(txModel)) && (
                        <option value="__custom__">Custom...</option>
                      )}
                    </select>
                    {txModel !== "" &&
                      !txSuggestions.includes(txModel) && (
                        <Input
                          value={txModel === "__custom__" ? "" : txModel}
                          onChange={(e) => {
                            setTxModel(e.target.value);
                            markDirty();
                          }}
                          placeholder="Enter custom model name..."
                          className="h-8 text-sm"
                        />
                      )}
                  </>
                );
              })()}
              <FieldHint>
                Leave empty to use the provider's default model.
              </FieldHint>
            </section>

            {txProvider === "openai" && (
              <section className="space-y-1.5">
                <FieldLabel>OpenAI API Key</FieldLabel>
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
                <FieldHint>
                  Shared with the OpenAI LLM provider above.
                </FieldHint>
              </section>
            )}

            {txProvider === "mistral" && (
              <section className="space-y-1.5">
                <FieldLabel>Mistral API Key</FieldLabel>
                <Input
                  type="password"
                  value={mistralKey}
                  onChange={(e) => {
                    setMistralKey(e.target.value);
                    markDirty();
                  }}
                  placeholder={
                    settings?.mistral_api_key_set
                      ? "Key is set (enter new to update)"
                      : "mk-..."
                  }
                  className="h-8 text-sm"
                />
                <FieldHint>
                  Can also be set via MISTRAL_API_KEY environment variable.
                </FieldHint>
              </section>
            )}
          </div>

          {/* ── MCP Servers ── */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SectionHeading>MCP Servers</SectionHeading>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 text-xs"
                onClick={() => {
                  setMcpServers([
                    ...mcpServers,
                    { name: "", transport: "stdio", command: "", args: [] },
                  ]);
                  markDirty();
                }}
              >
                + Add
              </Button>
            </div>
            <FieldHint>
              Connect external MCP servers to extend the agent with additional
              tools.
            </FieldHint>

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
                  <select
                    value={server.transport}
                    onChange={(e) => {
                      const updated = [...mcpServers];
                      updated[i] = {
                        ...updated[i],
                        transport: e.target.value as "stdio" | "http",
                      };
                      setMcpServers(updated);
                      markDirty();
                    }}
                    className="h-7 text-xs rounded-md border border-input bg-background px-2 text-foreground"
                  >
                    <option value="stdio">stdio</option>
                    <option value="http">http</option>
                  </select>
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
                        updated[i] = {
                          ...updated[i],
                          command: e.target.value,
                        };
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
          </div>

          {/* ── Save ── */}
          <div className="pt-2 pb-4">
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
