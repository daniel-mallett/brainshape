import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getNoteFiles, createNoteFile, syncStructural, type NoteFile } from "../lib/api";
import { Input } from "./ui/input";

interface Command {
  id: string;
  label: string;
  category: "note" | "action";
  action: () => void;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onSelectNote: (path: string) => void;
  onCreateNote: () => void;
  onSwitchView: (view: string) => void;
  onSync: () => void;
  onOpenSettings?: () => void;
}

export function CommandPalette({
  open,
  onClose,
  onSelectNote,
  onCreateNote,
  onSwitchView,
  onSync,
  onOpenSettings,
}: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [notes, setNotes] = useState<NoteFile[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch notes when opening
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      getNoteFiles()
        .then((res) => setNotes(res.files))
        .catch(console.error);
      // Focus after render
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  const handleCreateNote = useCallback(async () => {
    const title = query.trim();
    if (!title) {
      // No title typed — just switch to editor so the sidebar + button is visible
      onClose();
      onCreateNote();
      return;
    }
    try {
      const { path } = await createNoteFile(title);
      onClose();
      onSelectNote(path);
      syncStructural().catch(console.error);
    } catch (err) {
      console.error("Failed to create note:", err);
      onClose();
    }
  }, [query, onClose, onCreateNote, onSelectNote]);

  const actionCommands: Command[] = useMemo(
    () => [
      {
        id: "new-note",
        label: query.trim() ? `New Note: "${query.trim()}"` : "New Note",
        category: "action",
        action: handleCreateNote,
      },
      {
        id: "view-editor",
        label: "Switch to Editor",
        category: "action",
        action: () => {
          onClose();
          onSwitchView("editor");
        },
      },
      {
        id: "view-graph",
        label: "Switch to Graph",
        category: "action",
        action: () => {
          onClose();
          onSwitchView("graph");
        },
      },
      {
        id: "view-memory",
        label: "Switch to Memory",
        category: "action",
        action: () => {
          onClose();
          onSwitchView("memory");
        },
      },
      {
        id: "view-settings",
        label: "Open Settings",
        category: "action",
        action: () => {
          onClose();
          onOpenSettings?.();
        },
      },
      {
        id: "sync",
        label: "Run Sync",
        category: "action",
        action: () => {
          onClose();
          onSync();
        },
      },
    ],
    [query, handleCreateNote, onClose, onSwitchView, onSync, onOpenSettings]
  );

  const noteCommands: Command[] = useMemo(
    () =>
      notes.map((n) => ({
        id: `note:${n.path}`,
        label: n.title,
        category: "note" as const,
        action: () => {
          onClose();
          onSelectNote(n.path);
        },
      })),
    [notes, onClose, onSelectNote]
  );

  const filtered = useMemo(() => {
    const all = [...actionCommands, ...noteCommands];
    if (!query.trim()) return all;
    const q = query.toLowerCase();
    return all.filter((cmd) => cmd.label.toLowerCase().includes(q));
  }, [query, actionCommands, noteCommands]);

  // Clamp selected index
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const executeSelected = useCallback(() => {
    const cmd = filtered[selectedIndex];
    if (cmd) cmd.action();
  }, [filtered, selectedIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      executeSelected();
    }
  };

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 z-50 bg-black/50" onClick={onClose} />
      <div className="fixed z-50 top-[15%] left-1/2 -translate-x-1/2 w-[500px] rounded-lg border border-border bg-popover shadow-2xl overflow-hidden">
        <div className="p-2 border-b border-border">
          <Input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search notes and commands..."
            className="h-9 text-sm border-0 shadow-none focus-visible:ring-0"
          />
        </div>
        <div className="max-h-[300px] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-sm text-muted-foreground">
              No results
            </div>
          ) : (
            filtered.slice(0, 50).map((cmd, i) => (
              <button
                key={cmd.id}
                onClick={cmd.action}
                onMouseEnter={() => setSelectedIndex(i)}
                className={`w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 transition-colors ${
                  i === selectedIndex
                    ? "bg-accent text-accent-foreground"
                    : "text-foreground"
                }`}
              >
                <span
                  className={`text-xs w-4 flex-shrink-0 ${
                    cmd.category === "action"
                      ? "text-blue-400"
                      : "text-muted-foreground"
                  }`}
                >
                  {cmd.category === "action" ? ">" : "#"}
                </span>
                <span className="truncate">{cmd.label}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </>
  );
}
