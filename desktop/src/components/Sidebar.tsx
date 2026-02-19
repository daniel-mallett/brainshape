import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { createFolder, createNoteFile, deleteFolder, deleteNoteFile, emptyTrash, getNoteFiles, getTrashNotes, renameFolder, renameNoteFile, restoreFromTrash, syncStructural, type NoteFile } from "../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";

interface FolderTree {
  [key: string]: FolderTree | NoteFile;
}

function buildTree(files: NoteFile[], folders: string[]): FolderTree {
  const tree: FolderTree = {};
  // Ensure all folder paths exist in the tree (including empty folders)
  for (const folderPath of folders) {
    const parts = folderPath.split("/");
    let current = tree;
    for (const part of parts) {
      if (!current[part] || isFile(current[part] as FolderTree | NoteFile)) {
        current[part] = {} as FolderTree;
      }
      current = current[part] as FolderTree;
    }
  }
  // Add files
  for (const file of files) {
    const parts = file.path.split("/");
    let current = tree;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]] || isFile(current[parts[i]] as FolderTree | NoteFile)) {
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
  type: "file" | "folder" | "background";
  path: string;
  x: number;
  y: number;
}

interface TreeNodeProps {
  name: string;
  node: FolderTree | NoteFile;
  path: string;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onMenuOpen: (path: string, x: number, y: number, type: "file" | "folder") => void;
  renamingPath: string | null;
  renameValue: string;
  onRenameChange: (v: string) => void;
  onRenameSubmit: () => void;
  onRenameCancel: () => void;
  renamingFolderPath: string | null;
  folderRenameValue: string;
  onFolderRenameChange: (v: string) => void;
  onFolderRenameSubmit: () => void;
  onFolderRenameCancel: () => void;
  creatingIn: string;
  creatingType: "file" | "folder";
  isCreating: boolean;
  newTitle: string;
  onNewTitleChange: (v: string) => void;
  onCreateSubmit: () => void;
  onCreateCancel: () => void;
  createInputRef: React.RefObject<HTMLInputElement | null>;
  depth: number;
}

function TreeNode({
  name, node, path, selectedPath, onSelect, onMenuOpen,
  renamingPath, renameValue, onRenameChange, onRenameSubmit, onRenameCancel,
  renamingFolderPath, folderRenameValue, onFolderRenameChange, onFolderRenameSubmit, onFolderRenameCancel,
  creatingIn, creatingType, isCreating, newTitle, onNewTitleChange, onCreateSubmit, onCreateCancel, createInputRef,
  depth,
}: TreeNodeProps) {
  const [expanded, setExpanded] = useState(true);
  const renameRef = useRef<HTMLInputElement>(null);
  const folderRenameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isFile(node) && renamingPath === node.path) {
      renameRef.current?.focus();
      renameRef.current?.select();
    }
  }, [renamingPath, node]);

  useEffect(() => {
    if (!isFile(node) && renamingFolderPath === path) {
      folderRenameRef.current?.focus();
      folderRenameRef.current?.select();
    }
  }, [renamingFolderPath, node, path]);

  // Auto-expand folder when creating inside it
  useEffect(() => {
    if (isCreating && creatingIn === path && !expanded) {
      setExpanded(true);
    }
  }, [isCreating, creatingIn, path, expanded]);

  if (isFile(node)) {
    const isSelected = node.path === selectedPath;
    const isRenaming = renamingPath === node.path;

    return (
      <div
        className={`group flex items-center rounded transition-colors ${
          isSelected
            ? "bg-accent text-accent-foreground"
            : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
        }`}
        onContextMenu={(e) => {
          e.preventDefault();
          onMenuOpen(node.path, e.clientX, e.clientY, "file");
        }}
      >
        {isRenaming ? (
          <input
            ref={renameRef}
            value={renameValue}
            onChange={(e) => onRenameChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onRenameSubmit();
              if (e.key === "Escape") onRenameCancel();
            }}
            onBlur={onRenameSubmit}
            className="flex-1 h-6 text-sm bg-background border border-border rounded px-2 mx-1 outline-none"
            style={{ paddingLeft: `${depth * 12 + 4}px` }}
          />
        ) : (
          <>
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
                onMenuOpen(node.path, rect.right, rect.bottom, "file");
              }}
              className="opacity-0 group-hover:opacity-100 px-1 text-muted-foreground hover:text-foreground text-xs flex-shrink-0"
              title="More actions"
              aria-label="More actions"
            >
              &#x22EF;
            </button>
          </>
        )}
      </div>
    );
  }

  const isRenamingThisFolder = renamingFolderPath === path;
  const entries = Object.entries(node).sort(([a, va], [b, vb]) => {
    const aIsFile = isFile(va);
    const bIsFile = isFile(vb);
    if (aIsFile !== bIsFile) return aIsFile ? 1 : -1;
    return a.localeCompare(b);
  });

  const showCreateInput = isCreating && creatingIn === path;

  return (
    <div>
      {isRenamingThisFolder ? (
        <input
          ref={folderRenameRef}
          value={folderRenameValue}
          onChange={(e) => onFolderRenameChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onFolderRenameSubmit();
            if (e.key === "Escape") onFolderRenameCancel();
          }}
          onBlur={onFolderRenameSubmit}
          className="w-full h-6 text-sm bg-background border border-border rounded px-2 mx-1 outline-none"
          style={{ paddingLeft: `${depth * 12 + 4}px` }}
        />
      ) : (
        <div
          className="group flex items-center"
          onContextMenu={(e) => {
            e.preventDefault();
            onMenuOpen(path, e.clientX, e.clientY, "folder");
          }}
        >
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex-1 text-left px-2 py-0.5 text-sm text-foreground hover:bg-accent/50 rounded flex items-center gap-1 transition-colors"
            style={{ paddingLeft: `${depth * 12 + 8}px` }}
          >
            <span className="text-xs text-muted-foreground">{expanded ? "\u25BC" : "\u25B6"}</span>
            {name}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              const rect = e.currentTarget.getBoundingClientRect();
              onMenuOpen(path, rect.right, rect.bottom, "folder");
            }}
            className="opacity-0 group-hover:opacity-100 px-1 text-muted-foreground hover:text-foreground text-xs flex-shrink-0"
            title="More actions"
            aria-label="More actions"
          >
            &#x22EF;
          </button>
        </div>
      )}
      {expanded && (
        <div>
          {showCreateInput && (
            <div className="px-2 py-0.5" style={{ paddingLeft: `${(depth + 1) * 12 + 8}px` }}>
              <Input
                ref={createInputRef}
                value={newTitle}
                onChange={(e) => onNewTitleChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onCreateSubmit();
                  if (e.key === "Escape") onCreateCancel();
                }}
                placeholder={creatingType === "folder" ? "Folder name..." : "Note title..."}
                className="h-7 text-sm"
              />
            </div>
          )}
          {entries.map(([key, val]) => (
            <TreeNode
              key={key}
              name={key}
              node={val}
              path={`${path}/${key}`}
              selectedPath={selectedPath}
              onSelect={onSelect}
              onMenuOpen={onMenuOpen}
              renamingPath={renamingPath}
              renameValue={renameValue}
              onRenameChange={onRenameChange}
              onRenameSubmit={onRenameSubmit}
              onRenameCancel={onRenameCancel}
              renamingFolderPath={renamingFolderPath}
              folderRenameValue={folderRenameValue}
              onFolderRenameChange={onFolderRenameChange}
              onFolderRenameSubmit={onFolderRenameSubmit}
              onFolderRenameCancel={onFolderRenameCancel}
              creatingIn={creatingIn}
              creatingType={creatingType}
              isCreating={isCreating}
              newTitle={newTitle}
              onNewTitleChange={onNewTitleChange}
              onCreateSubmit={onCreateSubmit}
              onCreateCancel={onCreateCancel}
              createInputRef={createInputRef}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export interface SidebarHandle {
  startCreating: () => void;
  refresh: () => void;
}

interface SidebarProps {
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
}

const menuBtnClass = "w-full text-left px-2 py-1.5 text-sm rounded-sm hover:bg-accent transition-colors";
const menuBtnDestructiveClass = "w-full text-left px-2 py-1.5 text-sm rounded-sm text-destructive hover:bg-accent hover:text-destructive transition-colors";

export const Sidebar = forwardRef<SidebarHandle, SidebarProps>(function Sidebar({ selectedPath, onSelectFile }, ref) {
  const [files, setFiles] = useState<NoteFile[]>([]);
  const [folders, setFolders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [creatingIn, setCreatingIn] = useState("");
  const [creatingType, setCreatingType] = useState<"file" | "folder">("file");
  const [newTitle, setNewTitle] = useState("");
  const [filter, setFilter] = useState("");
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [plusMenuOpen, setPlusMenuOpen] = useState(false);
  const [confirmPath, setConfirmPath] = useState<string | null>(null);
  const [confirmFolderPath, setConfirmFolderPath] = useState<string | null>(null);
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renamingFolderPath, setRenamingFolderPath] = useState<string | null>(null);
  const [folderRenameValue, setFolderRenameValue] = useState("");
  const renameInFlightRef = useRef(false);
  const folderRenameInFlightRef = useRef(false);
  const [trashOpen, setTrashOpen] = useState(false);
  const [trashFiles, setTrashFiles] = useState<NoteFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const { files, folders } = await getNoteFiles();
      setFiles(files);
      setFolders(folders ?? []);
    } catch (err) {
      console.error("Failed to fetch note files:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useImperativeHandle(ref, () => ({
    startCreating: () => startCreatingIn("", "file"),
    refresh,
  }), [refresh]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (creating) inputRef.current?.focus();
  }, [creating]);

  const startCreatingIn = (folder: string, type: "file" | "folder") => {
    setMenu(null);
    setPlusMenuOpen(false);
    setCreatingIn(folder);
    setCreatingType(type);
    setNewTitle("");
    setCreating(true);
  };

  const handleCreate = async () => {
    const title = newTitle.trim();
    if (!title) return;
    try {
      if (creatingType === "folder") {
        const folderPath = creatingIn ? `${creatingIn}/${title}` : title;
        await createFolder(folderPath);
        setCreating(false);
        setNewTitle("");
        await refresh();
      } else {
        const { path } = await createNoteFile(title, "", creatingIn);
        setCreating(false);
        setNewTitle("");
        await refresh();
        onSelectFile(path);
        syncStructural().catch((err) =>
          console.error("Failed to sync after note creation:", err)
        );
      }
    } catch (err) {
      console.error(`Failed to create ${creatingType}:`, err);
    }
  };

  const handleCreateCancel = () => {
    setCreating(false);
    setNewTitle("");
  };

  const handleMenuOpen = (path: string, x: number, y: number, type: "file" | "folder") => {
    setMenu({ type, path, x, y });
  };

  // File rename handlers
  const handleRenameClick = (path: string) => {
    setMenu(null);
    const file = files.find((f) => f.path === path);
    if (file) {
      setRenamingPath(path);
      setRenameValue(file.title);
    }
  };

  const handleRenameSubmit = async () => {
    if (!renamingPath || renameInFlightRef.current) return;
    const newTitle = renameValue.trim();
    if (!newTitle) {
      setRenamingPath(null);
      return;
    }
    const oldPath = renamingPath;
    const oldFile = files.find((f) => f.path === oldPath);
    if (oldFile && newTitle === oldFile.title) {
      setRenamingPath(null);
      return;
    }
    renameInFlightRef.current = true;
    try {
      const { path: newPath } = await renameNoteFile(oldPath, newTitle);
      setRenamingPath(null);
      setRenameValue("");
      await refresh();
      if (selectedPath === oldPath) {
        onSelectFile(newPath);
      }
    } catch (err) {
      console.error("Failed to rename note:", err);
      setRenamingPath(null);
    } finally {
      renameInFlightRef.current = false;
    }
  };

  const handleRenameCancel = () => {
    setRenamingPath(null);
    setRenameValue("");
  };

  // Folder rename handlers
  const handleFolderRenameClick = (path: string) => {
    setMenu(null);
    const folderName = path.split("/").pop() || path;
    setRenamingFolderPath(path);
    setFolderRenameValue(folderName);
  };

  const handleFolderRenameSubmit = async () => {
    if (!renamingFolderPath || folderRenameInFlightRef.current) return;
    const newName = folderRenameValue.trim();
    if (!newName) {
      setRenamingFolderPath(null);
      return;
    }
    const oldName = renamingFolderPath.split("/").pop() || renamingFolderPath;
    if (newName === oldName) {
      setRenamingFolderPath(null);
      return;
    }
    folderRenameInFlightRef.current = true;
    try {
      const { new_path } = await renameFolder(renamingFolderPath, newName);
      setRenamingFolderPath(null);
      setFolderRenameValue("");
      await refresh();
      // If selected file was inside the renamed folder, update selection
      if (selectedPath && selectedPath.startsWith(renamingFolderPath + "/")) {
        const newSelectedPath = selectedPath.replace(renamingFolderPath + "/", new_path + "/");
        onSelectFile(newSelectedPath);
      }
    } catch (err) {
      console.error("Failed to rename folder:", err);
      setRenamingFolderPath(null);
    } finally {
      folderRenameInFlightRef.current = false;
    }
  };

  const handleFolderRenameCancel = () => {
    setRenamingFolderPath(null);
    setFolderRenameValue("");
  };

  // File delete handlers
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

  // Folder delete handlers
  const handleFolderDeleteClick = (path: string) => {
    setMenu(null);
    setConfirmFolderPath(path);
  };

  const handleFolderDeleteConfirm = async () => {
    if (!confirmFolderPath) return;
    const path = confirmFolderPath;
    setConfirmFolderPath(null);
    try {
      await deleteFolder(path);
      await refresh();
      if (selectedPath && selectedPath.startsWith(path + "/")) {
        onSelectFile("");
      }
    } catch (err) {
      console.error("Failed to delete folder:", err);
    }
  };

  // Trash handlers
  const refreshTrash = useCallback(async () => {
    try {
      const { files } = await getTrashNotes();
      setTrashFiles(files);
    } catch (err) {
      console.error("Failed to fetch trash:", err);
    }
  }, []);

  useEffect(() => {
    if (trashOpen) refreshTrash();
  }, [trashOpen, refreshTrash]);

  const handleRestoreClick = async (trashPath: string) => {
    try {
      const { path } = await restoreFromTrash(trashPath);
      await refreshTrash();
      await refresh();
      onSelectFile(path);
    } catch (err) {
      console.error("Failed to restore note:", err);
    }
  };

  const handleEmptyTrash = async () => {
    try {
      await emptyTrash();
      await refreshTrash();
    } catch (err) {
      console.error("Failed to empty trash:", err);
    }
  };

  // Filter
  const filteredFiles = filter
    ? files.filter((f) => f.title.toLowerCase().includes(filter.toLowerCase()))
    : files;

  const tree = filter ? null : buildTree(filteredFiles, folders);

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-border space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Files</span>
          <div className="flex gap-1">
            <button
              onClick={() => setTrashOpen(true)}
              className="text-muted-foreground hover:text-foreground text-xs leading-none px-1"
              title="Trash"
              aria-label="Trash"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="w-3.5 h-3.5">
                <path fillRule="evenodd" d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.285a1.5 1.5 0 0 0 1.493-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.787l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5A.75.75 0 0 1 9.95 6Z" clipRule="evenodd" />
              </svg>
            </button>
            <div className="relative">
              <button
                onClick={() => setPlusMenuOpen(!plusMenuOpen)}
                className="text-muted-foreground hover:text-foreground text-lg leading-none"
                title="New..."
                aria-label="New note or folder"
              >
                +
              </button>
              {plusMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setPlusMenuOpen(false)} />
                  <div className="absolute right-0 top-full mt-1 z-50 min-w-[120px] rounded-md border border-border bg-popover p-1 shadow-md">
                    <button
                      onClick={() => startCreatingIn("", "file")}
                      className={menuBtnClass}
                    >
                      New Note
                    </button>
                    <button
                      onClick={() => startCreatingIn("", "folder")}
                      className={menuBtnClass}
                    >
                      New Folder
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="relative">
          <Input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter notes..."
            className="h-7 text-sm pr-6"
          />
          {filter && (
            <button
              onClick={() => setFilter("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground text-sm"
              title="Clear filter"
            >
              &times;
            </button>
          )}
        </div>
      </div>
      <ScrollArea className="flex-1">
        <div
          className="py-1"
          onContextMenu={(e) => {
            if (e.target === e.currentTarget) {
              e.preventDefault();
              setMenu({ type: "background", path: "", x: e.clientX, y: e.clientY });
            }
          }}
        >
          {/* Root-level create input */}
          {creating && creatingIn === "" && (
            <div className="px-2 py-1">
              <Input
                ref={inputRef}
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                  if (e.key === "Escape") handleCreateCancel();
                }}
                placeholder={creatingType === "folder" ? "Folder name..." : "Note title..."}
                className="h-7 text-sm"
              />
            </div>
          )}
          {loading ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">Loading...</p>
          ) : filteredFiles.length === 0 && folders.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">
              {filter ? "No matching notes" : "No notes found"}
            </p>
          ) : filter ? (
            /* Flat list when filtering */
            filteredFiles.map((file) => (
              <div
                key={file.path}
                className={`group flex items-center rounded transition-colors ${
                  file.path === selectedPath
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                }`}
                onContextMenu={(e) => {
                  e.preventDefault();
                  handleMenuOpen(file.path, e.clientX, e.clientY, "file");
                }}
              >
                <button
                  onClick={() => onSelectFile(file.path)}
                  className="flex-1 text-left px-2 py-0.5 text-sm truncate min-w-0"
                >
                  {file.title}
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    const rect = e.currentTarget.getBoundingClientRect();
                    handleMenuOpen(file.path, rect.right, rect.bottom, "file");
                  }}
                  className="opacity-0 group-hover:opacity-100 px-1 text-muted-foreground hover:text-foreground text-xs flex-shrink-0"
                  title="More actions"
                  aria-label="More actions"
                >
                  &#x22EF;
                </button>
              </div>
            ))
          ) : (
            /* Tree view */
            Object.entries(tree!)
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
                  path={key}
                  selectedPath={selectedPath}
                  onSelect={onSelectFile}
                  onMenuOpen={handleMenuOpen}
                  renamingPath={renamingPath}
                  renameValue={renameValue}
                  onRenameChange={setRenameValue}
                  onRenameSubmit={handleRenameSubmit}
                  onRenameCancel={handleRenameCancel}
                  renamingFolderPath={renamingFolderPath}
                  folderRenameValue={folderRenameValue}
                  onFolderRenameChange={setFolderRenameValue}
                  onFolderRenameSubmit={handleFolderRenameSubmit}
                  onFolderRenameCancel={handleFolderRenameCancel}
                  creatingIn={creatingIn}
                  creatingType={creatingType}
                  isCreating={creating}
                  newTitle={newTitle}
                  onNewTitleChange={setNewTitle}
                  onCreateSubmit={handleCreate}
                  onCreateCancel={handleCreateCancel}
                  createInputRef={inputRef}
                  depth={0}
                />
              ))
          )}
        </div>
      </ScrollArea>

      {/* Context menu */}
      {menu && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setMenu(null)}
          />
          <div
            className="fixed z-50 min-w-[140px] rounded-md border border-border bg-popover p-1 shadow-md"
            style={{
              left: Math.min(menu.x, window.innerWidth - 160),
              top: Math.min(menu.y, window.innerHeight - 120),
            }}
          >
            {menu.type === "file" && (
              <>
                <button
                  onClick={() => handleRenameClick(menu.path)}
                  className={menuBtnClass}
                >
                  Rename
                </button>
                <button
                  onClick={() => handleDeleteClick(menu.path)}
                  className={menuBtnDestructiveClass}
                >
                  Move to Trash
                </button>
              </>
            )}
            {menu.type === "folder" && (
              <>
                <button
                  onClick={() => startCreatingIn(menu.path, "file")}
                  className={menuBtnClass}
                >
                  New Note
                </button>
                <button
                  onClick={() => startCreatingIn(menu.path, "folder")}
                  className={menuBtnClass}
                >
                  New Folder
                </button>
                <div className="my-1 border-t border-border" />
                <button
                  onClick={() => handleFolderRenameClick(menu.path)}
                  className={menuBtnClass}
                >
                  Rename
                </button>
                <button
                  onClick={() => handleFolderDeleteClick(menu.path)}
                  className={menuBtnDestructiveClass}
                >
                  Delete
                </button>
              </>
            )}
            {menu.type === "background" && (
              <>
                <button
                  onClick={() => startCreatingIn("", "file")}
                  className={menuBtnClass}
                >
                  New Note
                </button>
                <button
                  onClick={() => startCreatingIn("", "folder")}
                  className={menuBtnClass}
                >
                  New Folder
                </button>
              </>
            )}
          </div>
        </>
      )}

      {/* Delete file confirmation */}
      {confirmPath && (
        <>
          <div
            className="fixed inset-0 z-50 bg-black/50"
            onClick={() => setConfirmPath(null)}
          />
          <div className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 rounded-lg border border-border bg-popover p-4 shadow-lg">
            <p className="text-sm mb-1 font-medium">Move to Trash</p>
            <p className="text-sm text-muted-foreground mb-4">
              Move &ldquo;{confirmPath}&rdquo; to trash? You can restore it later.
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
                Move to Trash
              </button>
            </div>
          </div>
        </>
      )}

      {/* Delete folder confirmation */}
      {confirmFolderPath && (
        <>
          <div
            className="fixed inset-0 z-50 bg-black/50"
            onClick={() => setConfirmFolderPath(null)}
          />
          <div className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-80 rounded-lg border border-border bg-popover p-4 shadow-lg">
            <p className="text-sm mb-1 font-medium">Delete Folder</p>
            <p className="text-sm text-muted-foreground mb-4">
              Delete &ldquo;{confirmFolderPath.split("/").pop()}&rdquo; and move its contents to trash?
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmFolderPath(null)}
                className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-accent transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleFolderDeleteConfirm}
                className="px-3 py-1.5 text-sm rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </>
      )}

      {/* Trash modal */}
      {trashOpen && (
        <>
          <div
            className="fixed inset-0 z-50 bg-black/50"
            onClick={() => setTrashOpen(false)}
          />
          <div className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 max-h-[70vh] rounded-lg border border-border bg-popover shadow-lg flex flex-col">
            <div className="flex items-center justify-between px-3 py-2 border-b border-border">
              <span className="text-sm font-medium">Trash</span>
              <div className="flex items-center gap-2">
                {trashFiles.length > 0 && (
                  <button
                    onClick={handleEmptyTrash}
                    className="text-xs text-destructive hover:underline"
                  >
                    Empty Trash
                  </button>
                )}
                <button
                  onClick={() => setTrashOpen(false)}
                  className="text-muted-foreground hover:text-foreground text-sm"
                  aria-label="Close trash"
                >
                  &times;
                </button>
              </div>
            </div>
            <ScrollArea className="flex-1 max-h-[50vh]">
              <div className="p-2 space-y-1">
                {trashFiles.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">Trash is empty</p>
                ) : (
                  trashFiles.map((file) => (
                    <div key={file.path} className="flex items-center justify-between px-2 py-1 rounded hover:bg-accent group">
                      <span className="text-sm truncate">{file.title}</span>
                      <button
                        onClick={() => handleRestoreClick(file.path)}
                        className="text-xs text-primary opacity-0 group-hover:opacity-100 transition-opacity shrink-0 ml-2"
                      >
                        Restore
                      </button>
                    </div>
                  ))
                )}
              </div>
            </ScrollArea>
          </div>
        </>
      )}
    </div>
  );
});
