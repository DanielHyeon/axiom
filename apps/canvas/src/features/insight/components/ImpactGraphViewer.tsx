// features/insight/components/ImpactGraphViewer.tsx
// Cytoscape.js graph renderer for Impact Graph

import { useEffect, useRef, useCallback } from 'react';
import cytoscape from 'cytoscape';
import coseBilkent from 'cytoscape-cose-bilkent';
import dagre from 'cytoscape-dagre';
import { Loader2, Network } from 'lucide-react';
import type { GraphData, GraphNode } from '../types/insight';
import {
  toCytoscapeElements,
  getLayoutConfig,
  getCytoscapeStylesheet,
} from '../utils/graphTransformer';

// Register layouts once
let layoutsRegistered = false;
if (!layoutsRegistered) {
  cytoscape.use(coseBilkent);
  cytoscape.use(dagre);
  layoutsRegistered = true;
}

interface ImpactGraphViewerProps {
  graphData: GraphData | null;
  loading?: boolean;
  error?: string | null;
  highlightedPaths?: string[];
  /** Path node id arrays for each highlighted path_id */
  pathNodeMap?: Record<string, string[]>;
  /** Node to softly highlight (e.g. from DriverRankingPanel hover) */
  hoveredNodeId?: string | null;
  onNodeClick?: (nodeId: string, nodeData: GraphNode) => void;
  onRetry?: () => void;
}

export function ImpactGraphViewer({
  graphData,
  loading,
  error,
  highlightedPaths = [],
  pathNodeMap = {},
  hoveredNodeId,
  onNodeClick,
  onRetry,
}: ImpactGraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  // Initialize Cytoscape
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    const elements = toCytoscapeElements(graphData);
    const layout = getLayoutConfig('impact');
    const stylesheet = getCytoscapeStylesheet();

    // Destroy previous instance
    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: stylesheet,
      layout,
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });

    cyRef.current = cy;

    // Node click handler
    cy.on('tap', 'node', (evt) => {
      const node = evt.target;
      const nodeId = node.id();
      const nodeData = node.data();

      // Build a GraphNode-compatible object from Cytoscape data
      const graphNode: GraphNode = {
        id: nodeId,
        label: nodeData.label ?? nodeId,
        type: nodeData.nodeType ?? 'TABLE',
        source: nodeData.source ?? 'query_log',
        confidence: nodeData.confidence ?? 1,
        score: nodeData.score,
        layer: nodeData.layer,
        properties: nodeData.properties ?? {},
      };

      onNodeClick?.(nodeId, graphNode);
    });

    // Background click — deselect
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        // Clicked on background
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graphData]);

  // Handle hover highlight (soft ring on a single node)
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().removeClass('hovered');
    if (hoveredNodeId) {
      cy.getElementById(hoveredNodeId).addClass('hovered');
    }
  }, [hoveredNodeId]);

  // Handle path highlight updates
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // Remove all highlight/dim classes first
    cy.elements().removeClass('highlighted dimmed');

    if (highlightedPaths.length === 0) return;

    // Collect all node IDs that are part of highlighted paths
    const highlightedNodeIds = new Set<string>();
    for (const pathId of highlightedPaths) {
      const nodeIds = pathNodeMap[pathId];
      if (nodeIds) {
        nodeIds.forEach((id) => highlightedNodeIds.add(id));
      }
    }

    if (highlightedNodeIds.size === 0) return;

    // Dim everything first
    cy.elements().addClass('dimmed');

    // Highlight nodes in path
    cy.nodes().forEach((node) => {
      if (highlightedNodeIds.has(node.id())) {
        node.removeClass('dimmed').addClass('highlighted');
      }
    });

    // Highlight edges connecting highlighted nodes
    cy.edges().forEach((edge) => {
      const srcId = edge.source().id();
      const tgtId = edge.target().id();
      if (highlightedNodeIds.has(srcId) && highlightedNodeIds.has(tgtId)) {
        edge.removeClass('dimmed').addClass('highlighted');
      }
    });
  }, [highlightedPaths, pathNodeMap]);

  // Fit to viewport helper
  const handleFit = useCallback(() => {
    cyRef.current?.fit(undefined, 40);
  }, []);

  // ---------------------------------------------------------------------------
  // Render states
  // ---------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-neutral-500">
        <Loader2 className="h-8 w-8 animate-spin mb-3" />
        <p className="text-sm">Impact 그래프를 분석하고 있습니다...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-neutral-500">
        <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-full bg-destructive/10 text-destructive">
          <Network className="h-6 w-6" />
        </div>
        <p className="text-sm text-red-400 mb-3">{error}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-xs text-primary hover:underline"
          >
            다시 시도
          </button>
        )}
      </div>
    );
  }

  if (!graphData) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[300px] text-neutral-500">
        <Network className="h-10 w-10 mb-3 opacity-30" />
        <p className="text-sm">KPI를 선택하면 Impact 그래프가 표시됩니다</p>
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <div
        ref={containerRef}
        className="h-full w-full min-h-[300px] rounded-lg border border-neutral-800 bg-neutral-950"
      />

      {/* Controls overlay */}
      <div className="absolute top-2 right-2 flex gap-1">
        <button
          onClick={handleFit}
          className="rounded border border-neutral-700 bg-neutral-800/80 px-2 py-1 text-[10px] text-neutral-400 hover:text-white hover:bg-neutral-700 transition-colors"
          title="화면에 맞추기"
        >
          Fit
        </button>
      </div>

      {/* Node count indicator */}
      <div className="absolute bottom-2 left-2 text-[10px] text-neutral-600">
        {graphData.nodes.length} nodes &middot; {graphData.edges.length} edges
      </div>
    </div>
  );
}
