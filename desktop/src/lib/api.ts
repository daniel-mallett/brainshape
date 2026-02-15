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
  vault_path: string;
  model_name: string;
  neo4j_uri: string;
}

export function getConfig(): Promise<Config> {
  return request("/config");
}

// --- Vault ---

export interface VaultFile {
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

export function getVaultFiles(): Promise<{ files: VaultFile[] }> {
  return request("/vault/files");
}

export function getVaultFile(path: string): Promise<Note> {
  return request(`/vault/file/${path}`);
}

export function createVaultFile(data: {
  title: string;
  content: string;
  folder?: string;
  tags?: string[];
}): Promise<{ path: string; title: string }> {
  return request("/vault/file", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateVaultFile(
  path: string,
  content: string
): Promise<{ path: string; title: string }> {
  return request(`/vault/file/${path}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

// --- Agent ---

export function initSession(): Promise<{ session_id: string }> {
  return request("/agent/init", { method: "POST" });
}

// --- Sync ---

export interface SyncStats {
  status: string;
  stats: Record<string, unknown>;
}

export function syncStructural(): Promise<SyncStats> {
  return request("/sync/structural", { method: "POST" });
}

export function syncSemantic(): Promise<SyncStats> {
  return request("/sync/semantic", { method: "POST" });
}

export function syncFull(): Promise<SyncStats> {
  return request("/sync/full", { method: "POST" });
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

export function getGraphNeighborhood(
  path: string,
  depth = 1
): Promise<GraphData> {
  return request(`/graph/neighborhood/${path}?depth=${depth}`);
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
