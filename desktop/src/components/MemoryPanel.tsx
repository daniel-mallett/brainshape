import { useCallback, useEffect, useState } from "react";
import {
  getMemories,
  deleteMemory,
  updateMemory,
  type Memory,
} from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { ScrollArea } from "./ui/scroll-area";

const TYPE_LABELS: Record<string, string> = {
  preference: "Preference",
  user_info: "About You",
  fact: "Fact",
  goal: "Goal",
  project: "Project",
};

const TYPE_COLORS: Record<string, string> = {
  preference: "bg-blue-500/20 text-blue-400",
  user_info: "bg-green-500/20 text-green-400",
  fact: "bg-amber-500/20 text-amber-400",
  goal: "bg-purple-500/20 text-purple-400",
  project: "bg-cyan-500/20 text-cyan-400",
};

export function MemoryPanel() {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getMemories();
      setMemories(data.memories);
    } catch (err) {
      console.error("Failed to load memories:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const handleDelete = async (id: string) => {
    try {
      await deleteMemory(id);
      setMemories((prev) => prev.filter((m) => m.id !== id));
      setDeletingId(null);
    } catch (err) {
      console.error("Failed to delete memory:", err);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingId) return;
    try {
      await updateMemory(editingId, editContent);
      setMemories((prev) =>
        prev.map((m) =>
          m.id === editingId ? { ...m, content: editContent } : m
        )
      );
      setEditingId(null);
      setEditContent("");
    } catch (err) {
      console.error("Failed to update memory:", err);
    }
  };

  const startEdit = (memory: Memory) => {
    setEditingId(memory.id);
    setEditContent(memory.content);
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
        Loading memories...
      </div>
    );
  }

  if (memories.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground text-sm mb-1">
            No memories yet.
          </p>
          <p className="text-muted-foreground/60 text-xs">
            Chat with Brain and it will remember things about you.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="px-3 py-1.5 border-b border-border text-xs text-muted-foreground flex items-center justify-between">
        <span>What Brain knows about you</span>
        <span>{memories.length} memories</span>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-3 space-y-2">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="border border-border rounded-md p-3 space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs px-1.5 py-0.5 rounded ${TYPE_COLORS[memory.type] || "bg-gray-500/20 text-gray-400"}`}
                  >
                    {TYPE_LABELS[memory.type] || memory.type}
                  </span>
                  {memory.created_at && (
                    <span className="text-xs text-muted-foreground/60">
                      {new Date(memory.created_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-5 text-xs px-1.5"
                    onClick={() => startEdit(memory)}
                  >
                    Edit
                  </Button>
                  {deletingId === memory.id ? (
                    <div className="flex gap-1">
                      <Button
                        variant="destructive"
                        size="sm"
                        className="h-5 text-xs px-1.5"
                        onClick={() => handleDelete(memory.id)}
                      >
                        Confirm
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-5 text-xs px-1.5"
                        onClick={() => setDeletingId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-5 text-xs px-1.5 text-destructive"
                      onClick={() => setDeletingId(memory.id)}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </div>

              {editingId === memory.id ? (
                <div className="flex gap-2">
                  <Input
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="h-7 text-sm"
                    onKeyDown={(e) => e.key === "Enter" && handleSaveEdit()}
                  />
                  <Button
                    size="sm"
                    className="h-7 text-xs"
                    onClick={handleSaveEdit}
                  >
                    Save
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => setEditingId(null)}
                  >
                    Cancel
                  </Button>
                </div>
              ) : (
                <p className="text-sm">{memory.content}</p>
              )}

              {memory.connections.length > 0 && (
                <div className="flex gap-1 flex-wrap">
                  {memory.connections.map((c, i) => (
                    <span
                      key={i}
                      className="text-xs bg-muted px-1.5 py-0.5 rounded"
                    >
                      {c.relationship} → {c.name}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
