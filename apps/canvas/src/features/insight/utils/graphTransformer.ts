// features/insight/utils/graphTransformer.ts
// Transform backend API graph response into Cytoscape.js elements

import type { ElementDefinition } from 'cytoscape';
import type { GraphData, GraphNode, GraphEdge, NodeType, EdgeType } from '../types/insight';

// ---------------------------------------------------------------------------
// Node visual mapping
// ---------------------------------------------------------------------------

interface NodeStyle {
  shape: string;
  color: string;
  borderColor: string;
}

const NODE_STYLES: Record<NodeType, NodeStyle> = {
  KPI: { shape: 'star', color: '#60a5fa', borderColor: '#3b82f6' },
  DRIVER: { shape: 'round-rectangle', color: '#34d399', borderColor: '#10b981' },
  DIMENSION: { shape: 'octagon', color: '#a78bfa', borderColor: '#8b5cf6' },
  TRANSFORM: { shape: 'diamond', color: '#fbbf24', borderColor: '#f59e0b' },
  TABLE: { shape: 'rectangle', color: '#94a3b8', borderColor: '#64748b' },
  COLUMN: { shape: 'ellipse', color: '#67e8f9', borderColor: '#22d3ee' },
  RECORD: { shape: 'ellipse', color: '#f9a8d4', borderColor: '#ec4899' },
  PREDICATE: { shape: 'hexagon', color: '#fda4af', borderColor: '#fb7185' },
};

// ---------------------------------------------------------------------------
// Edge visual mapping
// ---------------------------------------------------------------------------

interface EdgeStyle {
  lineStyle: string;
  color: string;
  width: number;
}

const EDGE_STYLES: Record<string, EdgeStyle> = {
  WHERE_FILTER:  { lineStyle: 'dashed', color: '#f97316', width: 2 },
  HAVING_FILTER: { lineStyle: 'dashed', color: '#f97316', width: 2 },
  GROUP_BY:      { lineStyle: 'solid',  color: '#8b5cf6', width: 2 },
  AGGREGATE:     { lineStyle: 'solid',  color: '#34d399', width: 3 },
  IMPACT:        { lineStyle: 'solid',  color: '#f43f5e', width: 3 },
  FK:            { lineStyle: 'solid',  color: '#64748b', width: 1 },
  JOIN:          { lineStyle: 'solid',  color: '#94a3b8', width: 2 },
  DERIVE:        { lineStyle: 'dotted', color: '#a78bfa', width: 2 },
  // Impact Graph edge types (Weaver backend)
  INFLUENCES:    { lineStyle: 'solid',  color: '#f43f5e', width: 3 },
  COUPLED:       { lineStyle: 'dashed', color: '#94a3b8', width: 1.5 },
  EXPLAINS_BY:   { lineStyle: 'dotted', color: '#a78bfa', width: 1.5 },
};

// ---------------------------------------------------------------------------
// Transform functions
// ---------------------------------------------------------------------------

function nodeToElement(node: GraphNode): ElementDefinition {
  const style = NODE_STYLES[node.type] ?? NODE_STYLES.TABLE;

  // Driver/Dimension nodes: width proportional to score (score is 0–1)
  const baseWidth = node.type === 'KPI'
    ? 70
    : (node.type === 'DRIVER' || node.type === 'DIMENSION') && node.score != null
      ? 38 + node.score * 52   // 38px at score=0, 90px at score=1
      : 40;

  return {
    group: 'nodes',
    data: {
      id: node.id,
      label: node.label,
      nodeType: node.type,
      source: node.source,
      confidence: node.confidence,
      score: node.score,
      layer: node.layer,
      meta: node.meta,
      properties: node.properties,
      // Visual data
      color: style.color,
      borderColor: style.borderColor,
      shape: style.shape,
      width: baseWidth,
      height: node.type === 'KPI' ? 60 : 40,
    },
    ...(node.position
      ? { position: { x: node.position.x, y: node.position.y } }
      : {}),
  };
}

function edgeToElement(edge: GraphEdge, index: number): ElementDefinition {
  const style = EDGE_STYLES[edge.type] ?? EDGE_STYLES.JOIN;

  return {
    group: 'edges',
    data: {
      // Prefer backend-provided id; fallback to generated id
      id: edge.id ?? `e${index}_${edge.source}_${edge.target}`,
      source: edge.source,
      target: edge.target,
      edgeType: edge.type,
      label: edge.label ?? '',
      weight: edge.weight ?? 0.5,
      confidence: edge.confidence ?? 1.0,
      // Visual data
      lineStyle: style.lineStyle,
      lineColor: style.color,
      lineWidth: style.width,
    },
  };
}

/**
 * Convert API graph data into Cytoscape element definitions.
 */
export function toCytoscapeElements(graphData: GraphData): ElementDefinition[] {
  const nodeElements = graphData.nodes.map(nodeToElement);
  const edgeElements = graphData.edges.map(edgeToElement);
  return [...nodeElements, ...edgeElements];
}

// ---------------------------------------------------------------------------
// Layout configuration
// ---------------------------------------------------------------------------

export type GraphType = 'impact' | 'instance' | 'query';

export interface LayoutOptions {
  name: string;
  [key: string]: unknown;
}

export function getLayoutConfig(graphType: GraphType): LayoutOptions {
  switch (graphType) {
    case 'impact':
      return {
        name: 'cose-bilkent',
        animate: true,
        animationDuration: 500,
        nodeDimensionsIncludeLabels: true,
        idealEdgeLength: 120,
        nodeRepulsion: 6500,
        edgeElasticity: 0.45,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        tile: true,
        fit: true,
        padding: 40,
      };

    case 'instance':
      return {
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 60,
        rankSep: 80,
        fit: true,
        padding: 30,
        animate: true,
        animationDuration: 400,
      };

    case 'query':
      return {
        name: 'dagre',
        rankDir: 'LR',
        nodeSep: 50,
        rankSep: 100,
        fit: true,
        padding: 30,
        animate: true,
        animationDuration: 400,
      };

    default:
      return {
        name: 'cose-bilkent',
        animate: true,
        fit: true,
        padding: 40,
      };
  }
}

// ---------------------------------------------------------------------------
// Cytoscape stylesheet
// ---------------------------------------------------------------------------

export function getCytoscapeStylesheet(): cytoscape.Stylesheet[] {
  return [
    // Base node style
    {
      selector: 'node',
      style: {
        label: 'data(label)',
        'text-valign': 'bottom',
        'text-halign': 'center',
        'font-size': '11px',
        color: '#d4d4d8',
        'text-margin-y': 6,
        'background-color': 'data(color)',
        'border-color': 'data(borderColor)',
        'border-width': 2,
        shape: 'data(shape)' as unknown as cytoscape.Css.NodeShape,
        width: 'data(width)',
        height: 'data(height)',
        'text-wrap': 'ellipsis',
        'text-max-width': '100px',
        'overlay-opacity': 0,
        'transition-property': 'opacity, border-width, border-color',
        'transition-duration': 200,
      } as unknown as cytoscape.Css.Node,
    },
    // KPI node
    {
      selector: 'node[nodeType="KPI"]',
      style: {
        'font-size': '13px',
        'font-weight': 'bold',
        'text-valign': 'center',
        'text-halign': 'center',
        color: '#ffffff',
      } as unknown as cytoscape.Css.Node,
    },
    // Score label for DRIVER nodes
    {
      selector: 'node[nodeType="DRIVER"]',
      style: {
        'text-valign': 'center',
        'text-halign': 'center',
        color: '#ffffff',
        'font-size': '10px',
      } as unknown as cytoscape.Css.Node,
    },
    // Base edge style
    {
      selector: 'edge',
      style: {
        width: 'data(lineWidth)',
        'line-color': 'data(lineColor)',
        'line-style': 'data(lineStyle)' as unknown as cytoscape.Css.LineStyle,
        'target-arrow-color': 'data(lineColor)',
        'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
        opacity: 0.7,
        'transition-property': 'opacity, line-color, width',
        'transition-duration': 200,
      } as unknown as cytoscape.Css.Edge,
    },
    // Selected node
    {
      selector: 'node:selected',
      style: {
        'border-width': 4,
        'border-color': '#ffffff',
      } as unknown as cytoscape.Css.Node,
    },
    // Highlighted (path) node
    {
      selector: 'node.highlighted',
      style: {
        'border-width': 3,
        'border-color': '#f43f5e',
        opacity: 1,
      } as unknown as cytoscape.Css.Node,
    },
    // Highlighted (path) edge
    {
      selector: 'edge.highlighted',
      style: {
        'line-color': '#f43f5e',
        'target-arrow-color': '#f43f5e',
        width: 4,
        opacity: 1,
      } as unknown as cytoscape.Css.Edge,
    },
    // Hovered node (soft ring from DriverRankingPanel hover)
    {
      selector: 'node.hovered',
      style: {
        'border-width': 3,
        'border-color': '#facc15',
        opacity: 1,
      } as unknown as cytoscape.Css.Node,
    },
    // Dimmed state (when paths are highlighted, other elements get dimmed)
    {
      selector: 'node.dimmed',
      style: {
        opacity: 0.2,
      } as unknown as cytoscape.Css.Node,
    },
    {
      selector: 'edge.dimmed',
      style: {
        opacity: 0.1,
      } as unknown as cytoscape.Css.Edge,
    },
  ];
}
