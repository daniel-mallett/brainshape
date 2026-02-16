const BASE_URL = "http://127.0.0.1:8765";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

// --- Health ---

export function health(): Promise<{ status: string }> {
  return request("/health");
}

// --- Config ---

export interface Config {
  notes_path: string;
  model_name: string;
  neo4j_uri: string;
}

export function getConfig(): Promise<Config> {
  return request("/config");
}

// --- Notes ---

export interface NoteFile {
  path: string;
  title: string;
}

export interface Note {
  path: string;
  title: string;
  content: string;
  metadata: Record<string, unknown>;
  links: string[];
  tags: string[];
}

export function getNoteFiles(): Promise<{ files: NoteFile[] }> {
  return request("/notes/files");
}

export function getNoteFile(path: string): Promise<Note> {
  return request(`/notes/file/${path}`);
}

export function updateNoteFile(
  path: string,
  content: string
): Promise<{ path: string; title: string }> {
  return request(`/notes/file/${path}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export function deleteNoteFile(path: string): Promise<{ status: string }> {
  return request(`/notes/file/${path}`, { method: "DELETE" });
}

export function createNoteFile(
  title: string,
  content = "",
  folder = ""
): Promise<{ path: string; title: string }> {
  return request("/notes/file", {
    method: "POST",
    body: JSON.stringify({ title, content, folder }),
  });
}

export function syncStructural(): Promise<{ status: string; stats: Record<string, number> }> {
  return request("/sync/structural", { method: "POST" });
}

// --- Import ---

export interface ImportVaultResult {
  status: string;
  stats: {
    files_copied: number;
    files_skipped: number;
    folders_created: number;
  };
}

export function importVault(sourcePath: string): Promise<ImportVaultResult> {
  return request("/import/vault", {
    method: "POST",
    body: JSON.stringify({ source_path: sourcePath }),
  });
}

// --- Settings ---

export interface MCPServer {
  name: string;
  transport: "stdio" | "http" | "sse";
  command?: string;
  args?: string[];
  url?: string;
}

export interface Settings {
  llm_provider: string;
  llm_model: string;
  ollama_base_url: string;
  anthropic_api_key_set: boolean;
  openai_api_key_set: boolean;
  mistral_api_key_set: boolean;
  transcription_provider: string;
  transcription_model: string;
  mcp_servers: MCPServer[];
  theme: Record<string, string>;
  font_family: string;
  editor_font_size: number;
  editor_keymap: string;
  editor_line_numbers: boolean;
  editor_word_wrap: boolean;
}

export function getSettings(): Promise<Settings> {
  return request("/settings");
}

export function updateSettings(
  updates: Partial<{
    llm_provider: string;
    llm_model: string;
    ollama_base_url: string;
    anthropic_api_key: string;
    openai_api_key: string;
    mistral_api_key: string;
    transcription_provider: string;
    transcription_model: string;
    mcp_servers: MCPServer[];
    theme: Record<string, string>;
    font_family: string;
    editor_font_size: number;
    editor_keymap: string;
    editor_line_numbers: boolean;
    editor_word_wrap: boolean;
  }>
): Promise<Settings> {
  return request("/settings", {
    method: "PUT",
    body: JSON.stringify(updates),
  });
}

// --- Transcription ---

export interface TranscriptionResult {
  text: string;
  segments: { start: number; end: number; text: string }[];
}

export async function transcribeAudio(
  audioBlob: Blob
): Promise<TranscriptionResult> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.wav");
  const res = await fetch(`${BASE_URL}/transcribe`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export interface MeetingResult {
  path: string;
  title: string;
  text: string;
  segment_count: number;
}

export async function transcribeMeeting(
  audioBlob: Blob,
  title = "",
  folder = "",
  tags = ""
): Promise<MeetingResult> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.wav");
  if (title) formData.append("title", title);
  if (folder) formData.append("folder", folder);
  if (tags) formData.append("tags", tags);
  const res = await fetch(`${BASE_URL}/transcribe/meeting`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

// --- Tags ---

export function getTags(): Promise<{ tags: string[] }> {
  return request("/notes/tags");
}

// --- Agent ---

export function initSession(): Promise<{ session_id: string }> {
  return request("/agent/init", { method: "POST" });
}

// --- Graph ---

export interface GraphNode {
  id: string;
  label: string;
  name: string | null;
  path?: string | null;
  type?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphStats {
  nodes: Record<string, number>;
  relationships: Record<string, number>;
}

export interface Memory {
  id: string;
  type: string;
  content: string;
  created_at: number | null;
  connections: { name: string; relationship: string }[];
}

export function getGraphStats(): Promise<GraphStats> {
  return request("/graph/stats");
}

export function getGraphOverview(
  limit = 200,
  label = ""
): Promise<GraphData> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (label) params.set("label", label);
  return request(`/graph/overview?${params}`);
}

export function getMemories(): Promise<{ memories: Memory[] }> {
  return request("/graph/memories");
}

export function deleteMemory(id: string): Promise<{ status: string }> {
  return request(`/graph/memory/${id}`, { method: "DELETE" });
}

export function updateMemory(
  id: string,
  content: string
): Promise<{ status: string }> {
  return request(`/graph/memory/${id}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}
