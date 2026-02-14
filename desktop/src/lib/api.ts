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
