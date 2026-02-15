/**
 * CodeMirror 6 autocompletion for wikilinks ([[...]]) and tags (#...).
 *
 * - Typing [[ triggers note title suggestions
 * - Typing # triggers tag suggestions
 */
import {
  autocompletion,
  type CompletionContext,
  type CompletionResult,
} from "@codemirror/autocomplete";
import { getNoteFiles, getTags } from "./api";

// Cache to avoid fetching on every keystroke
let noteCache: string[] = [];
let tagCache: string[] = [];
let lastFetch = 0;
const CACHE_TTL = 10_000; // 10s
let fetchPromise: Promise<void> | null = null;

async function refreshCache() {
  const now = Date.now();
  if (now - lastFetch < CACHE_TTL) return;
  lastFetch = now;

  try {
    const [notesRes, tagsRes] = await Promise.all([getNoteFiles(), getTags()]);
    noteCache = notesRes.files.map((f) => f.title);
    tagCache = tagsRes.tags;
  } catch {
    // Silently fail — use stale cache
  }
}

/** Pre-fetch the cache so first autocomplete keystroke has data. */
export function prefetchCompletions() {
  if (!fetchPromise) {
    fetchPromise = refreshCache().finally(() => {
      fetchPromise = null;
    });
  }
}

function wikilinkCompletion(
  context: CompletionContext
): CompletionResult | null {
  // Match [[ followed by optional text
  const match = context.matchBefore(/\[\[([^\]]*)/);
  if (!match) return null;

  const query = match.text.slice(2).toLowerCase(); // strip [[
  const from = match.from + 2; // position after [[

  refreshCache();

  const options = noteCache
    .filter((title) => title.toLowerCase().includes(query))
    .map((title) => ({
      label: title,
      apply: `${title}]]`,
      type: "text" as const,
    }));

  return { from, options, filter: false };
}

function tagCompletion(context: CompletionContext): CompletionResult | null {
  // Match # followed by word chars (but not at start of line for headings)
  const match = context.matchBefore(/(?:^|\s)#([a-zA-Z][\w/-]*)/);
  if (!match) return null;

  // Find the # position
  const hashIndex = match.text.lastIndexOf("#");
  const query = match.text.slice(hashIndex + 1).toLowerCase();
  const from = match.from + hashIndex + 1; // position after #

  refreshCache();

  const options = tagCache
    .filter((tag) => tag.toLowerCase().includes(query))
    .map((tag) => ({
      label: tag,
      type: "keyword" as const,
    }));

  return { from, options, filter: false };
}

export const brainAutocompletion = autocompletion({
  override: [wikilinkCompletion, tagCompletion],
  activateOnTyping: true,
});
