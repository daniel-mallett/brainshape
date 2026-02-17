import { useCallback, useEffect, useRef, useState } from "react";
import {
  searchKeyword,
  searchSemantic,
  getTags,
  type SearchResult,
} from "../lib/api";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";

type SearchMode = "keyword" | "semantic";

interface SearchPanelProps {
  onNavigateToNote: (path: string) => void;
}

export function SearchPanel({ onNavigateToNote }: SearchPanelProps) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("keyword");
  const [tag, setTag] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [tags, setTags] = useState<string[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const requestIdRef = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch available tags on mount
  useEffect(() => {
    getTags()
      .then((data) => setTags(data.tags))
      .catch(console.error);
  }, []);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const doSearch = useCallback(
    async (q: string, m: SearchMode, t: string) => {
      if (!q.trim()) {
        setResults([]);
        setHasSearched(false);
        return;
      }
      const thisRequest = ++requestIdRef.current;
      setLoading(true);
      try {
        const searchFn = m === "semantic" ? searchSemantic : searchKeyword;
        const data = await searchFn(q, t || undefined);
        if (thisRequest !== requestIdRef.current) return; // stale
        setResults(data.results);
        setHasSearched(true);
      } catch (err) {
        if (thisRequest !== requestIdRef.current) return; // stale
        console.error("Search failed:", err);
        setResults([]);
        setHasSearched(true);
      } finally {
        if (thisRequest === requestIdRef.current) setLoading(false);
      }
    },
    []
  );

  // Debounced search on query/mode/tag change
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    const delay = mode === "semantic" ? 500 : 300;
    timerRef.current = setTimeout(() => doSearch(query, mode, tag), delay);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [query, mode, tag, doSearch]);

  const highlightSnippet = (snippet: string, q: string) => {
    if (!q.trim() || mode === "semantic") return snippet;
    const escaped = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const parts = snippet.split(new RegExp(`(${escaped})`, "gi"));
    return parts.map((part, i) =>
      part.toLowerCase() === q.toLowerCase() ? (
        <mark key={i} className="bg-yellow-500/30 text-inherit rounded px-0.5">
          {part}
        </mark>
      ) : (
        part
      )
    );
  };

  const formatScore = (score: number) => {
    if (mode === "semantic") return `${(score * 100).toFixed(0)}%`;
    return score.toFixed(2);
  };

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex flex-col gap-3 p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <Input
            ref={inputRef}
            placeholder={
              mode === "semantic"
                ? "Search by meaning..."
                : "Search by keyword..."
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1"
          />
        </div>
        <div className="flex items-center gap-2">
          {/* Mode toggle */}
          <div className="flex rounded-md overflow-hidden border border-border" role="radiogroup" aria-label="Search mode">
            <button
              role="radio"
              aria-checked={mode === "keyword"}
              onClick={() => setMode("keyword")}
              className={`px-3 py-1 text-xs font-medium transition-colors ${
                mode === "keyword"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              Keyword
            </button>
            <button
              role="radio"
              aria-checked={mode === "semantic"}
              onClick={() => setMode("semantic")}
              className={`px-3 py-1 text-xs font-medium transition-colors ${
                mode === "semantic"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              Smart
            </button>
          </div>
          {/* Tag filter */}
          {tags.length > 0 && (
            <select
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              className="text-xs px-2 py-1 rounded border border-border bg-muted text-muted-foreground"
            >
              <option value="">All tags</option>
              {tags.map((t) => (
                <option key={t} value={t}>
                  #{t}
                </option>
              ))}
            </select>
          )}
          {/* Result count */}
          {hasSearched && (
            <span className="text-xs ml-auto text-muted-foreground">
              {results.length} result{results.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
      </div>

      {/* Results */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-2">
          {loading && (
            <p className="text-sm text-muted-foreground">Searching...</p>
          )}
          {!loading && !hasSearched && !query.trim() && (
            <div className="text-center py-12">
              <p className="text-sm text-muted-foreground">
                Type to search your notes
              </p>
              <p className="text-xs mt-1 text-muted-foreground">
                Use <strong>Keyword</strong> for exact matches or{" "}
                <strong>Smart</strong> for meaning-based search
              </p>
            </div>
          )}
          {!loading && hasSearched && results.length === 0 && (
            <p className="text-sm text-center py-8 text-muted-foreground">
              No results found
            </p>
          )}
          {results.map((r, i) => (
            <button
              key={`${r.path}-${i}`}
              onClick={() => onNavigateToNote(r.path)}
              className="w-full text-left p-3 rounded-lg border border-border bg-card text-card-foreground transition-colors hover:bg-accent"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-sm">
                  {r.title}
                </span>
                <span className="text-xs px-1.5 py-0.5 rounded bg-primary text-primary-foreground opacity-80">
                  {formatScore(r.score)}
                </span>
              </div>
              <p className="text-xs leading-relaxed line-clamp-2 text-muted-foreground">
                {highlightSnippet(r.snippet || "", query)}
              </p>
              <span className="text-xs mt-1 block text-muted-foreground/70">
                {r.path}
              </span>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
