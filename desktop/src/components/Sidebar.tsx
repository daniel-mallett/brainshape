import { useCallback, useEffect, useState } from "react";
import { getVaultFiles, type VaultFile } from "../lib/api";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { SyncStatus } from "./SyncStatus";

interface FolderTree {
  [key: string]: FolderTree | VaultFile;
}

function buildTree(files: VaultFile[]): FolderTree {
  const tree: FolderTree = {};
  for (const file of files) {
    const parts = file.path.split("/");
    let current = tree;
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]] || typeof (current[parts[i]] as VaultFile).path === "string") {
        current[parts[i]] = {} as FolderTree;
      }
      current = current[parts[i]] as FolderTree;
    }
    current[parts[parts.length - 1]] = file;
  }
  return tree;
}

function isFile(node: FolderTree | VaultFile): node is VaultFile {
  return typeof (node as VaultFile).path === "string";
}

interface TreeNodeProps {
  name: string;
  node: FolderTree | VaultFile;
  selectedPath: string | null;
  onSelect: (path: string) => void;
  depth: number;
}

function TreeNode({ name, node, selectedPath, onSelect, depth }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(true);

  if (isFile(node)) {
    const isSelected = node.path === selectedPath;
    return (
      <button
        onClick={() => onSelect(node.path)}
        className={`w-full text-left px-2 py-0.5 text-sm truncate rounded transition-colors ${
          isSelected
            ? "bg-accent text-accent-foreground"
            : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {node.title}
      </button>
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
  const [files, setFiles] = useState<VaultFile[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { files } = await getVaultFiles();
      setFiles(files);
    } catch (err) {
      console.error("Failed to fetch vault files:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const tree = buildTree(files);

  return (
    <div className="w-60 flex-shrink-0 border-r border-border flex flex-col">
      <div className="px-3 py-2 border-b border-border flex items-center justify-between">
        <span className="text-sm font-medium">Files</span>
        <Button variant="ghost" size="sm" onClick={refresh} className="h-6 w-6 p-0">
          ↻
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="py-1">
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
                  depth={0}
                />
              ))
          )}
        </div>
      </ScrollArea>
      <SyncStatus />
    </div>
  );
}
