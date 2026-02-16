/**
 * Tauri runtime detection and native dialog helpers.
 *
 * Uses dynamic imports so the Tauri plugin is only loaded when
 * actually running inside Tauri (not in browser / Vite dev).
 */

/** Detect if running inside Tauri (vs. plain browser / Vite dev). */
export function isTauri(): boolean {
  return "__TAURI__" in window;
}

/**
 * Open a native directory picker.
 * Returns the selected path, or null if cancelled or not in Tauri.
 */
export async function pickDirectory(title?: string): Promise<string | null> {
  if (!isTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  const selected = await open({
    directory: true,
    multiple: false,
    title: title || "Select Directory",
  });
  return typeof selected === "string" ? selected : null;
}
