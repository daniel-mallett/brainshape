import { useCallback, useEffect, useRef, useState } from "react";
import { createNoteFile, deleteNoteFile, getNoteFiles, syncStructural, type NoteFile } from "../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";

interface FolderTree {
  [key: string]: FolderTree | NoteFile;
}

function buildTree(files: NoteFile[]): FolderTree {
  const tree: FolderTree = {};
  for (const file of files) {
    const parts = file.path.split("/");
    let current = tree;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]] || typeof (current[parts[i]] as NoteFile).path === "string") {
        current[parts[i]] = {} as FolderTree;
      }
      current = current[parts[i]] as FolderTree;
    }
    current[parts[parts.length - 1]] = file;
  }
  return tree;
}

function isFile(node: FolderTree | NoteFile): node is NoteFile {
  return typeof (node as NoteFile).path === "string";
}

interface MenuState {
  path: string;
  x: number;
  y: number;
}

interface TreeNodeProps {
  name: string;
  node: FolderTree | NoteFile;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onMenuOpen: (path: string, x: number, y: number) => void;
  depth: number;
}

function TreeNode({ name, node, selectedPath, onSelect, onMenuOpen, depth }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(true);

  if (isFile(node)) {
    const isSelected = node.path === selectedPath;
    return (
      <div
        className={`group flex items-center rounded transition-colors ${
          isSelected
            ? "bg-accent text-accent-foreground"
            : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
        }`}
        onContextMenu={(e) => {
          e.preventDefault();
          onMenuOpen(node.path, e.clientX, e.clientY);
        }}
      >
        <button
          onClick={() => onSelect(node.path)}
          className="flex-1 text-left px-2 py-0.5 text-sm truncate min-w-0"
          style={{ paddingLeft: `${depth * 12 + 8}px` }}
        >
          {node.title}
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            const rect = e.currentTarget.getBoundingClientRect();
            onMenuOpen(node.path, rect.right, rect.bottom);
          }}
          className="opacity-0 group-hover:opacity-100 px-1 text-muted-foreground hover:text-foreground text-xs flex-shrink-0"
          title="More actions"
        >
          &#x22EF;
        </button>
      </div>
    );
  }

  const entries = Object.entries(node).sort(([a, va], [b, vb]) => {
    const aIsFile = isFile(va);
    const bIsFile = isFile(vb);
    if (aIsFile !== bIsFile) return aIsFile ? 1 : -1;
    return a.localeCompare(b);
  });

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left px-2 py-0.5 text-sm text-foreground hover:bg-accent/50 rounded flex items-center gap-1 transition-colors"
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        <span className="text-xs text-muted-foreground">{expanded ? "▼" : "▶"}</span>
        {name}
      </button>
      {expanded && (
        <div>
          {entries.map(([key, val]) => (
            <TreeNode
              key={key}
              name={key}
              node={val}
              selectedPath={selectedPath}
              onSelect={onSelect}
              onMenuOpen={onMenuOpen}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

interface SidebarProps {
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
}

export function Sidebar({ selectedPath, onSelectFile }: SidebarProps) {
  const [files, setFiles] = useState<NoteFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [confirmPath, setConfirmPath] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const { files } = await getNoteFiles();
      setFiles(files);
    } catch (err) {
      console.error("Failed to fetch note files:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (creating) inputRef.current?.focus();
  }, [creating]);

  const handleCreate = async () => {
    const title = newTitle.trim();
    if (!title) return;
    try {
      const { path } = await createNoteFile(title);
      setCreating(false);
      setNewTitle("");
      await refresh();
      onSelectFile(path);
      syncStructural().catch((err) =>
        console.error("Failed to sync after note creation:", err)
      );
    } catch (err) {
      console.error("Failed to create note:", err);
    }
  };

  const handleMenuOpen = (path: string, x: number, y: number) => {
    setMenu({ path, x, y });
  };

  const handleDeleteClick = (path: string) => {
    setMenu(null);
    setConfirmPath(path);
  };

  const handleDeleteConfirm = async () => {
    if (!confirmPath) return;
    const path = confirmPath;
    setConfirmPath(null);
    try {
      await deleteNoteFile(path);
      await refresh();
      if (selectedPath === path) {
        onSelectFile("");
      }
    } catch (err) {
      console.error("Failed to delete note:", err);
    }
  };

  const tree = buildTree(files);

  return (
    <div className="w-60 flex-shrink-0 border-r border-border flex flex-col">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <span className="text-sm font-medium">Files</span>
        <button
          onClick={() => setCreating(true)}
          className="text-muted-foreground hover:text-foreground text-lg leading-none"
          title="New note"
        >
          +
        </button>
      </div>
      <ScrollArea className="flex-1">
        <div className="py-1">
          {creating && (
            <div className="px-2 py-1">
              <Input
                ref={inputRef}
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                  if (e.key === "Escape") {
                    setCreating(false);
                    setNewTitle("");
                  }
                }}
                placeholder="Note title..."
                className="h-7 text-sm"
              />
            </div>
          )}
          {loading ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">Loading...</p>
          ) : files.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">No notes found</p>
          ) : (
            Object.entries(tree)
              .sort(([a, va], [b, vb]) => {
                const aIsFile = isFile(va);
                const bIsFile = isFile(vb);
                if (aIsFile !== bIsFile) return aIsFile ? 1 : -1;
                return a.localeCompare(b);
              })
              .map(([key, val]) => (
                <TreeNode
                  key={key}
                  name={key}
                  node={val}
                  selectedPath={selectedPath}
                  onSelect={onSelectFile}
                  onMenuOpen={handleMenuOpen}
                  depth={0}
                />
              ))
          )}
        </div>
      </ScrollArea>

      {menu && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setMenu(null)}
          />
          <div
            className="fixed z-50 min-w-[120px] rounded-md border border-border bg-popover p-1 shadow-md"
            style={{ left: menu.x, top: menu.y }}
          >
            <button
              onClick={() => handleDeleteClick(menu.path)}
              className="w-full text-left px-2 py-1.5 text-sm rounded-sm text-destructive hover:bg-accent hover:text-destructive transition-colors"
            >
              Delete
            </button>
          </div>
        </>
      )}

      {confirmPath && (
        <>
          <div
            className="fixed inset-0 z-50 bg-black/50"
            onClick={() => setConfirmPath(null)}
          />
          <div className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 rounded-lg border border-border bg-popover p-4 shadow-lg">
            <p className="text-sm mb-1 font-medium">Delete note</p>
            <p className="text-sm text-muted-foreground mb-4">
              Are you sure you want to delete &ldquo;{confirmPath}&rdquo;? This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmPath(null)}
                className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteConfirm}
                className="px-3 py-1.5 text-sm rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
