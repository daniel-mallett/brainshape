import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { GraphNode, GraphEdge } from "../lib/api";

const LABEL_SIZES: Record<string, number> = {
  Note: 6,
  Tag: 4,
  Memory: 5,
  Chunk: 3,
};

/** Read a CSS variable value from the document root */
function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** Map graph node labels to CSS variable names */
const LABEL_CSS_VARS: Record<string, string> = {
  Note: "--graph-note",
  Tag: "--graph-tag",
  Memory: "--graph-memory",
  Chunk: "--graph-chunk",
  Document: "--graph-note",
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

/** Read all graph colors from CSS variables once, cache for render loop */
function readGraphColors() {
  return {
    note: cssVar("--graph-note") || "#64748b",
    tag: cssVar("--graph-tag") || "#3b82f6",
    memory: cssVar("--graph-memory") || "#a855f7",
    chunk: cssVar("--graph-chunk") || "#6b7280",
    edge: cssVar("--graph-edge") || "#334155",
    label: cssVar("--graph-label") || "#e2e8f0",
  };
}

export function GraphView({ nodes, edges, onNodeClick }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const colorsRef = useRef(readGraphColors());

  // Re-read colors when CSS variables change (theme switch)
  useEffect(() => {
    const observer = new MutationObserver(() => {
      colorsRef.current = readGraphColors();
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["style"] });
    return () => observer.disconnect();
  }, []);

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
      const varName = LABEL_CSS_VARS[node.label] || "--graph-note";
      const colorKey = varName.replace("--graph-", "") as keyof ReturnType<typeof readGraphColors>;
      const color = colorsRef.current[colorKey] || "#64748b";

      ctx.beginPath();
      ctx.arc(node.x ?? 0, node.y ?? 0, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      if (globalScale > 1.5) {
        const fontSize = Math.max(10 / globalScale, 2);
        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = colorsRef.current.label;
        ctx.fillText(label || "", node.x ?? 0, (node.y ?? 0) + size + 2);
      }
    },
    []
  );

  const linkColor = useCallback(() => colorsRef.current.edge, []);

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
