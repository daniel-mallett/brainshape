import { useCallback, useEffect, useState } from "react";
import {
  getGraphOverview,
  getGraphStats,
  type GraphNode,
  type GraphEdge,
  type GraphStats,
} from "../lib/api";
import { GraphView } from "./GraphView";
import { Button } from "./ui/button";

const LABEL_CSS_VARS: Record<string, string> = {
  Note: "var(--graph-note)",
  Tag: "var(--graph-tag)",
  Memory: "var(--graph-memory)",
  Chunk: "var(--graph-chunk)",
};

interface GraphPanelProps {
  onNavigateToNote?: (path: string) => void;
}

export function GraphPanel({ onNavigateToNote }: GraphPanelProps) {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [labelFilter, setLabelFilter] = useState("");

  // Fetch stats on mount
  useEffect(() => {
    getGraphStats().then(setStats).catch(console.error);
  }, []);

  // Fetch graph data
  useEffect(() => {
    setLoading(true);
    getGraphOverview(200, labelFilter)
      .then((data) => {
        setNodes(data.nodes);
        setEdges(data.edges);
      })
      .catch((err) => console.error("Failed to load graph:", err))
      .finally(() => setLoading(false));
  }, [labelFilter]);

  const handleNodeClick = useCallback(
    (node: GraphNode) => {
      if (node.label === "Note" && node.path) {
        onNavigateToNote?.(node.path);
      }
    },
    [onNavigateToNote]
  );

  const totalNodes = stats
    ? Object.values(stats.nodes).reduce((a, b) => a + b, 0)
    : 0;
  const totalRels = stats
    ? Object.values(stats.relationships).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border text-xs">
        {/* Label filters */}
        <div className="flex gap-1">
          <Button
            variant={labelFilter === "" ? "secondary" : "ghost"}
            size="sm"
            className="h-6 text-xs"
            onClick={() => setLabelFilter("")}
          >
            All
          </Button>
          {["Note", "Tag", "Memory"].map((l) => (
            <Button
              key={l}
              variant={labelFilter === l ? "secondary" : "ghost"}
              size="sm"
              className="h-6 text-xs"
              onClick={() => setLabelFilter(l)}
            >
              {l}
            </Button>
          ))}
        </div>

        <div className="flex-1" />

        {/* Stats */}
        {stats && (
          <div className="flex gap-2 text-muted-foreground">
            {Object.entries(stats.nodes).map(([label, count]) => (
              <span key={label} className="flex items-center gap-1">
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ backgroundColor: LABEL_CSS_VARS[label] || "var(--graph-note)" }}
                />
                {count} {label === "Memory" ? "Memories" : `${label}s`}
              </span>
            ))}
            <span className="text-muted-foreground/60">
              | {totalNodes} nodes, {totalRels} rels
            </span>
          </div>
        )}
      </div>

      {/* Graph */}
      <div className="flex-1 relative overflow-hidden min-h-0">
        {loading && nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center z-10">
            <span className="text-muted-foreground text-sm">Loading graph...</span>
          </div>
        )}
        {nodes.length > 0 ? (
          <GraphView
            nodes={nodes}
            edges={edges}
            onNodeClick={handleNodeClick}
          />
        ) : (
          !loading && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No graph data. Run a sync first.
            </div>
          )
        )}
      </div>
    </div>
  );
}
