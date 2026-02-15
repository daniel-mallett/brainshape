import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphNode, GraphEdge } from "../lib/api";

const LABEL_COLORS: Record<string, string> = {
  Note: "#64748b",
  Tag: "#3b82f6",
  Memory: "#a855f7",
  Chunk: "#6b7280",
  Document: "#64748b",
};

const LABEL_SIZES: Record<string, number> = {
  Note: 6,
  Tag: 4,
  Memory: 5,
  Chunk: 3,
};

interface GraphViewProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (node: GraphNode) => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ForceNode = GraphNode & { x?: number; y?: number; [key: string]: any };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ForceLink = GraphEdge & { [key: string]: any };

export function GraphView({ nodes, edges, onNodeClick }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  // Track container size so ForceGraph2D gets explicit dimensions
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Build graph data with validated edges (filter out edges referencing missing nodes)
  const graphData = useMemo(() => {
    const nodeIds = new Set(nodes.map((n) => n.id));
    const validLinks = (edges as ForceLink[]).filter(
      (e) => nodeIds.has(e.source) && nodeIds.has(e.target)
    );
    return {
      nodes: nodes as ForceNode[],
      links: validLinks,
    };
  }, [nodes, edges]);

  const handleNodeClick = useCallback(
    (node: ForceNode) => {
      onNodeClick?.(node as GraphNode);
    },
    [onNodeClick]
  );

  const nodeCanvasObject = useCallback(
    (
      node: ForceNode,
      ctx: CanvasRenderingContext2D,
      globalScale: number
    ) => {
      const label = node.name || node.label;
      const size = LABEL_SIZES[node.label] || 4;
      const color = LABEL_COLORS[node.label] || "#94a3b8";

      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Draw label when zoomed in enough
      if (globalScale > 1.5) {
        const fontSize = Math.max(10 / globalScale, 2);
        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = "#e2e8f0";
        ctx.fillText(label || "", node.x ?? 0, (node.y ?? 0) + size + 2);
      }
    },
    []
  );

  const linkColor = useCallback(() => "#334155", []);

  return (
    <div ref={containerRef} className="w-full h-full bg-background">
      {dimensions.width > 0 && dimensions.height > 0 && (
        <ForceGraph2D
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeId="id"
          linkSource="source"
          linkTarget="target"
          nodeCanvasObject={nodeCanvasObject}
          linkColor={linkColor}
          linkWidth={0.5}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          onNodeClick={handleNodeClick}
          backgroundColor="transparent"
          cooldownTicks={200}
          warmupTicks={100}
        />
      )}
    </div>
  );
}
