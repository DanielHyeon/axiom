// pages/insight/InsightPage.tsx
// Main Insight page with 3-panel layout

import { useEffect, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInsightStore } from '@/features/insight/store/useInsightStore';
import { useImpactGraph } from '@/features/insight/hooks/useImpactGraph';
import { ImpactGraphViewer } from '@/features/insight/components/ImpactGraphViewer';
import { NodeDetailPanel } from '@/features/insight/components/NodeDetailPanel';
import { PathComparisonPanel } from '@/features/insight/components/PathComparisonPanel';
import { InsightHeader } from './components/InsightHeader';
import { InsightSidebar } from './components/InsightSidebar';
import { getFingerprintFromParams } from '@/features/insight/utils/fingerprintUtils';
import type { GraphNode } from '@/features/insight/types/insight';
import { Info, ExternalLink } from 'lucide-react';

export function InsightPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const {
    selectedKpiFingerprint,
    impactGraph,
    impactGraphLoading,
    impactEvidence,
    impactPaths,
    timeRange,
    selectedDriverId,
    hoveredNodeId,
    nodeDetailOpen,
    highlightedPaths,
    selectKpi,
    selectDriver,
    setTimeRange,
    setHoveredNodeId,
    togglePath,
  } = useInsightStore();

  // Deep-link: read ?fp= from URL on mount
  useEffect(() => {
    const fp = getFingerprintFromParams(searchParams);
    if (fp && fp !== selectedKpiFingerprint) {
      selectKpi(fp, fp);
    }
    // Only on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync URL when KPI or timeRange changes
  useEffect(() => {
    if (!selectedKpiFingerprint) return;
    const current = Object.fromEntries(searchParams.entries());
    const next: Record<string, string> = {
      ...current,
      fp: selectedKpiFingerprint,
      tr: timeRange,
    };
    if (selectedDriverId) {
      next.node = selectedDriverId;
    } else {
      delete next.node;
    }
    setSearchParams(next, { replace: true });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKpiFingerprint, timeRange, selectedDriverId]);

  // Impact graph hook
  const { error, retry } = useImpactGraph({
    kpiFingerprint: selectedKpiFingerprint,
    timeRange,
  });

  // Find selected node in graph for NodeDetailPanel
  const selectedNode: GraphNode | null = useMemo(() => {
    if (!selectedDriverId || !impactGraph) return null;
    return impactGraph.nodes.find((n) => n.id === selectedDriverId) ?? null;
  }, [selectedDriverId, impactGraph]);

  // Evidence for selected node
  const selectedEvidence = useMemo(() => {
    if (!selectedDriverId || !impactEvidence) return null;
    return impactEvidence[selectedDriverId] ?? null;
  }, [selectedDriverId, impactEvidence]);

  // Build path node map for path highlighting
  const pathNodeMap = useMemo(() => {
    const map: Record<string, string[]> = {};
    for (const p of impactPaths) {
      map[p.path_id] = p.nodes;
    }
    return map;
  }, [impactPaths]);

  // Build node label map for PathComparisonPanel
  const nodeLabels = useMemo(() => {
    const map: Record<string, string> = {};
    if (impactGraph) {
      for (const n of impactGraph.nodes) {
        map[n.id] = n.label;
      }
    }
    return map;
  }, [impactGraph]);

  const handleKpiSelect = useCallback(
    (kpiId: string, fingerprint: string) => {
      selectKpi(kpiId, fingerprint);
      setSearchParams({ fp: fingerprint, tr: timeRange });
    },
    [selectKpi, setSearchParams, timeRange],
  );

  const handleNodeClick = useCallback(
    (nodeId: string, nodeData: GraphNode) => {
      if (nodeData.type === 'DRIVER' || nodeData.type === 'DIMENSION') {
        selectDriver(nodeId);
      }
    },
    [selectDriver],
  );

  const meta = impactGraph?.meta;

  return (
    <div className="flex flex-col h-full bg-neutral-950">
      {/* Header */}
      <InsightHeader timeRange={timeRange} onTimeRangeChange={setTimeRange} />

      {/* 3-panel body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <InsightSidebar
          onKpiSelect={handleKpiSelect}
          graphData={impactGraph}
          impactEvidence={impactEvidence}
          selectedDriverId={selectedDriverId}
          onSelectDriver={selectDriver}
          onHoverDriver={setHoveredNodeId}
          loading={impactGraphLoading}
        />

        {/* Center: Graph + Path comparison */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Graph */}
          <div className="flex-1 relative">
            <ImpactGraphViewer
              graphData={impactGraph}
              loading={impactGraphLoading}
              error={error}
              highlightedPaths={highlightedPaths}
              pathNodeMap={pathNodeMap}
              hoveredNodeId={hoveredNodeId}
              onNodeClick={handleNodeClick}
              onRetry={retry}
            />
          </div>

          {/* Bottom: Path comparison + Meta bar */}
          <div className="shrink-0 border-t border-neutral-800">
            {impactPaths.length > 0 && (
              <div className="px-3 py-2">
                <PathComparisonPanel
                  paths={impactPaths}
                  nodeLabels={nodeLabels}
                  highlightedPaths={highlightedPaths}
                  onTogglePath={togglePath}
                />
              </div>
            )}

            {meta && <MetaBar meta={meta} />}
          </div>
        </div>

        {/* Right: Node detail panel */}
        {nodeDetailOpen && (
          <div className="w-72 shrink-0">
            <NodeDetailPanel
              nodeId={selectedDriverId}
              graphNode={selectedNode}
              evidence={selectedEvidence}
              loading={false}
              onClose={() => selectDriver(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Meta bar sub-component
// ---------------------------------------------------------------------------

type MetaType = NonNullable<ReturnType<typeof useInsightStore.getState>['impactGraph']>['meta'];

function MetaBar({ meta }: { meta: MetaType }) {
  return (
    <div className="flex items-center gap-4 px-4 py-1.5 bg-neutral-900/60 border-t border-neutral-800/50 text-[10px] text-neutral-500">
      <div className="flex items-center gap-1">
        <Info className="h-3 w-3" />
        <span>
          {meta.explain?.mode === 'fallback' ? 'Fallback' : 'Primary'} mode
        </span>
      </div>

      {meta.explain?.total_queries_analyzed != null && (
        <span>Queries: {meta.explain.total_queries_analyzed.toLocaleString()}</span>
      )}

      {meta.cache_hit && (
        <span className="text-emerald-600">
          Cached ({meta.cache_ttl_remaining_s ? `${meta.cache_ttl_remaining_s}s` : 'hit'})
        </span>
      )}

      {meta.truncated && (
        <button
          type="button"
          className="flex items-center gap-1 text-yellow-500 hover:text-yellow-400"
        >
          <ExternalLink className="h-3 w-3" />
          더 보기
        </button>
      )}

      {meta.trace_id && (
        <span className="ml-auto font-mono">trace: {meta.trace_id}</span>
      )}
    </div>
  );
}
