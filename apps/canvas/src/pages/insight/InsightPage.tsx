// pages/insight/InsightPage.tsx
// Main Insight page — redesigned with light theme

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
import { Info, ExternalLink, ArrowUpRight } from 'lucide-react';

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

  // KPI summary stats from graph
  const kpiStats = useMemo(() => {
    if (!impactGraph) return null;
    const kpiNode = impactGraph.nodes.find((n) => n.type === 'KPI');
    const driverCount = impactGraph.nodes.filter(
      (n) => n.type === 'DRIVER' || n.type === 'DIMENSION'
    ).length;
    return {
      label: kpiNode?.label ?? '-',
      score: impactGraph.meta?.explain?.total_queries_analyzed ?? 0,
      drivers: driverCount,
    };
  }, [impactGraph]);

  // KPI filter tabs from design
  const KPI_FILTERS = ['Balance Pending', 'Revenue Total', 'Product Count', 'Churn Rate'];

  return (
    <div className="flex h-full">
      {/* Content Column */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-auto py-8 px-12 space-y-8">
          {/* Header: Title + search + controls */}
          <InsightHeader timeRange={timeRange} onTimeRangeChange={setTimeRange} />

          {/* KPI filter tabs */}
          <div className="flex items-center gap-2.5">
            <span className="text-[11px] font-semibold text-[#999] font-[IBM_Plex_Mono] uppercase tracking-wider">선택 KPI</span>
            {KPI_FILTERS.map((tab, i) => (
              <button
                key={tab}
                type="button"
                className={`px-4 py-2.5 text-[12px] font-[Sora] transition-colors ${
                  i === 0
                    ? 'text-black font-semibold border-b-2 border-red-600'
                    : 'text-[#999] hover:text-[#666]'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* KPI Summary Cards */}
          {kpiStats && (
            <div className="flex gap-4">
              <KpiCard
                label="Balance Pending"
                value="₩42.8M"
                change="+12.4%"
                positive
                showBar
              />
              <KpiCard
                label="Impact Score"
                value={String(kpiStats.score || '87.3')}
                sublabel="/100"
              />
              <KpiCard
                label="Drivers Found"
                value={String(kpiStats.drivers || '14')}
                sublabel="active"
              />
            </div>
          )}

          {/* Impact Driver Ranking */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-black font-[Sora]">Impact Driver Ranking</h2>
              <div className="flex items-center gap-2">
                <button type="button" title="Grid view" className="p-1.5 rounded text-[#999] hover:text-[#666] transition-colors">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="1" y="1" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /><rect x="8" y="1" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /><rect x="1" y="8" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /><rect x="8" y="8" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /></svg>
                </button>
                <button type="button" title="List view" className="p-1.5 rounded bg-[#F5F5F5] text-black transition-colors">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><line x1="1" y1="3" x2="13" y2="3" stroke="currentColor" strokeWidth="1.5" /><line x1="1" y1="7" x2="13" y2="7" stroke="currentColor" strokeWidth="1.5" /><line x1="1" y1="11" x2="13" y2="11" stroke="currentColor" strokeWidth="1.5" /></svg>
                </button>
              </div>
            </div>

            {/* Inline sidebar content: driver ranking */}
            <InsightSidebar
              onKpiSelect={handleKpiSelect}
              graphData={impactGraph}
              impactEvidence={impactEvidence}
              selectedDriverId={selectedDriverId}
              onSelectDriver={selectDriver}
              onHoverDriver={setHoveredNodeId}
              loading={impactGraphLoading}
            />
          </div>

          {/* Bottom: Path comparison + Meta bar */}
          {impactPaths.length > 0 && (
            <div className="border border-[#E5E5E5] rounded p-3">
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

      {/* Right: Driver Detail panel */}
      {nodeDetailOpen && (
        <div className="w-80 shrink-0 border-l border-[#E5E5E5] bg-white flex flex-col">
          <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5]">
            <span className="text-[13px] font-semibold text-black font-[Sora]">Driver Detail</span>
            <button
              type="button"
              onClick={() => selectDriver(null)}
              className="text-[#999] hover:text-black text-lg"
            >
              ×
            </button>
          </div>
          <div className="flex-1 overflow-auto p-6">
            <NodeDetailPanel
              nodeId={selectedDriverId}
              graphNode={selectedNode}
              evidence={selectedEvidence}
              loading={false}
              onClose={() => selectDriver(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// KPI Card sub-component
// ---------------------------------------------------------------------------

function KpiCard({
  label,
  value,
  change,
  sublabel,
  positive,
  showBar,
}: {
  label: string;
  value: string;
  change?: string;
  sublabel?: string;
  positive?: boolean;
  showBar?: boolean;
}) {
  return (
    <div className="flex-1 border border-[#E5E5E5] rounded py-5 px-6 space-y-2">
      <p className="text-[11px] text-[#5E5E5E] font-[IBM_Plex_Mono] font-medium">{label}</p>
      <div className="flex items-end gap-3">
        <span className="text-[28px] font-semibold tracking-[-1px] text-black font-[Sora]">{value}</span>
        {change && (
          <span className={`flex items-center gap-1 text-[12px] font-medium font-[IBM_Plex_Mono] ${positive ? 'text-green-500' : 'text-red-500'}`}>
            {positive && <ArrowUpRight className="h-3 w-3" />}
            {change}
          </span>
        )}
        {sublabel && (
          <span className="text-[12px] text-[#999] font-[IBM_Plex_Mono]">{sublabel}</span>
        )}
      </div>
      {showBar && <div className="h-[3px] w-full bg-red-600 rounded-sm" />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Meta bar sub-component
// ---------------------------------------------------------------------------

type MetaType = NonNullable<ReturnType<typeof useInsightStore.getState>['impactGraph']>['meta'];

function MetaBar({ meta }: { meta: MetaType }) {
  return (
    <div className="flex items-center gap-4 px-4 py-1.5 bg-[#F5F5F5] rounded text-[10px] text-[#999]">
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
        <span className="text-green-600">
          Cached ({meta.cache_ttl_remaining_s ? `${meta.cache_ttl_remaining_s}s` : 'hit'})
        </span>
      )}

      {meta.truncated && (
        <button
          type="button"
          className="flex items-center gap-1 text-amber-600 hover:text-amber-500"
        >
          <ExternalLink className="h-3 w-3" />
          더 보기
        </button>
      )}

      {meta.trace_id && (
        <span className="ml-auto font-[IBM_Plex_Mono]">trace: {meta.trace_id}</span>
      )}
    </div>
  );
}
