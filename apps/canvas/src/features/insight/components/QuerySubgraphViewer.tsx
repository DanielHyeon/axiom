// features/insight/components/QuerySubgraphViewer.tsx
// NL2SQL query result visualized as a Cytoscape subgraph

import { useEffect, useRef, useState, useCallback } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import { Loader2, Network, AlertCircle } from 'lucide-react';
import { postQuerySubgraph } from '../api/insightApi';
import type { GraphData } from '../types/insight';
import {
  toCytoscapeElements,
  getLayoutConfig,
  getCytoscapeStylesheet,
} from '../utils/graphTransformer';

// Register dagre layout once
let dagreRegistered = false;
if (!dagreRegistered) {
  cytoscape.use(dagre);
  dagreRegistered = true;
}

interface QuerySubgraphViewerProps {
  sql?: string;
}

export function QuerySubgraphViewer({ sql }: QuerySubgraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parseMode, setParseMode] = useState<string>('');
  const [confidence, setConfidence] = useState<number>(0);

  // Fetch graph data when sql changes
  useEffect(() => {
    if (!sql?.trim()) {
      setGraphData(null);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    postQuerySubgraph({ sql })
      .then((res) => {
        if (cancelled) return;
        setGraphData(res.graph);
        setParseMode(res.parse_result.mode);
        setConfidence(res.parse_result.confidence);
      })
      .catch((err) => {
        if (cancelled) return;
        const msg =
          err?.response?.data?.error_message ??
          err?.message ??
          'SQL 서브그래프 생성 실패';
        setError(msg);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sql]);

  // Initialize / update Cytoscape
  useEffect(() => {
    if (!containerRef.current || !graphData) return;

    if (cyRef.current) {
      cyRef.current.destroy();
      cyRef.current = null;
    }

    const elements = toCytoscapeElements(graphData);
    if (!elements.length) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: getCytoscapeStylesheet(),
      layout: getLayoutConfig('query'),
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    });

    cyRef.current = cy;
    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graphData]);

  const handleFit = useCallback(() => {
    cyRef.current?.fit(undefined, 40);
  }, []);

  // ── Render states ──────────────────────────────────────────

  if (!sql?.trim()) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] text-neutral-500">
        <Network className="h-10 w-10 mb-3 opacity-30" />
        <p className="text-sm">SQL이 실행되면 구조 그래프가 표시됩니다</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] text-neutral-500">
        <Loader2 className="h-8 w-8 animate-spin mb-3" />
        <p className="text-sm">SQL 구조 분석 중...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] text-neutral-500">
        <AlertCircle className="h-8 w-8 mb-3 text-red-500/60" />
        <p className="text-sm text-red-400 mb-2">파싱 실패</p>
        <p className="text-xs text-neutral-600 text-center max-w-xs">{error}</p>
      </div>
    );
  }

  if (!graphData || !graphData.nodes.length) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] text-neutral-500">
        <Network className="h-10 w-10 mb-3 opacity-30" />
        <p className="text-sm">그래프 노드가 없습니다</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-[360px]">
      <div
        ref={containerRef}
        className="h-full w-full rounded-lg border border-neutral-800 bg-neutral-950"
      />

      {/* Fit button */}
      <div className="absolute top-2 right-2">
        <button
          type="button"
          onClick={handleFit}
          className="rounded border border-neutral-700 bg-neutral-800/80 px-2 py-1 text-[10px] text-neutral-400 hover:text-white hover:bg-neutral-700 transition-colors"
        >
          Fit
        </button>
      </div>

      {/* Stats bar */}
      <div className="absolute bottom-2 left-2 flex items-center gap-3 text-[10px] text-neutral-600">
        <span>{graphData.nodes.length} nodes · {graphData.edges.length} edges</span>
        {parseMode && (
          <span className={confidence >= 0.8 ? 'text-emerald-600' : 'text-amber-600'}>
            {parseMode} ({Math.round(confidence * 100)}%)
          </span>
        )}
      </div>
    </div>
  );
}
