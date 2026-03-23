// pages/insight/InsightPage.tsx
// Main Insight page — redesigned with light theme

import { useEffect, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInsightStore } from '@/features/insight/store/useInsightStore';
import { useImpactGraph } from '@/features/insight/hooks/useImpactGraph';
import { NodeDetailPanel } from '@/features/insight/components/NodeDetailPanel';
import { PathComparisonPanel } from '@/features/insight/components/PathComparisonPanel';
import { InsightHeader } from './components/InsightHeader';
import { InsightSidebar } from './components/InsightSidebar';
import { getFingerprintFromParams } from '@/features/insight/utils/fingerprintUtils';
import type { GraphNode } from '@/features/insight/types/insight';
import { useTranslation } from 'react-i18next';
import { Info, ExternalLink, ArrowUpRight } from 'lucide-react';

export function InsightPage() {
 const { t } = useTranslation();
 const [searchParams, setSearchParams] = useSearchParams();

 const {
 selectedKpiFingerprint,
 impactGraph,
 impactGraphLoading,
 impactEvidence,
 impactPaths,
 timeRange,
 selectedDriverId,
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
 useImpactGraph({
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
 <div className="flex flex-col lg:flex-row h-full">
 {/* Content Column */}
 <div className="flex-1 flex flex-col min-w-0">
 <div className="flex-1 overflow-auto py-4 px-4 md:py-6 md:px-8 lg:py-8 lg:px-12 space-y-6 md:space-y-8">
 {/* Header: Title + search + controls */}
 <InsightHeader timeRange={timeRange} onTimeRangeChange={setTimeRange} />

 {/* KPI filter tabs */}
 <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-2.5 overflow-x-auto">
 <span className="text-[11px] font-semibold text-foreground/60 font-mono uppercase tracking-wider shrink-0">{t('insight.selectedKpi')}</span>
 <div className="flex items-center gap-1 sm:gap-2">
 {KPI_FILTERS.map((tab, i) => (
 <button
 key={tab}
 type="button"
 className={`px-3 md:px-4 py-2 md:py-2.5 text-[11px] md:text-[12px] font-heading transition-colors whitespace-nowrap ${
 i === 0
 ? 'text-foreground font-semibold border-b-2 border-red-600'
 : 'text-foreground/60 hover:text-muted-foreground'
 }`}
 >
 {tab}
 </button>
 ))}
 </div>
 </div>

 {/* KPI Summary Cards */}
 {kpiStats && (
 <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4">
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
 <h2 className="text-sm font-semibold text-foreground font-heading">{t('insight.impactDriverRanking')}</h2>
 <div className="flex items-center gap-2">
 <button type="button" title="Grid view" className="p-1.5 rounded text-foreground/60 hover:text-muted-foreground transition-colors">
 <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><rect x="1" y="1" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /><rect x="8" y="1" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /><rect x="1" y="8" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /><rect x="8" y="8" width="5" height="5" stroke="currentColor" strokeWidth="1.5" /></svg>
 </button>
 <button type="button" title="List view" className="p-1.5 rounded bg-muted text-foreground transition-colors">
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
 <div className="border border-border rounded p-3">
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
 <div className="w-full lg:w-80 shrink-0 border-t lg:border-t-0 lg:border-l border-border bg-card flex flex-col max-h-[50vh] lg:max-h-none">
 <div className="flex items-center justify-between h-[52px] px-4 md:px-6 border-b border-border">
 <span className="text-[13px] font-semibold text-foreground font-heading">{t('insight.driverDetail')}</span>
 <button
 type="button"
 onClick={() => selectDriver(null)}
 className="text-foreground/60 hover:text-foreground text-lg"
 >
 ×
 </button>
 </div>
 <div className="flex-1 overflow-auto p-4 md:p-6">
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
 <div className="border border-border rounded py-3 px-4 md:py-5 md:px-6 space-y-1.5 md:space-y-2">
 <p className="text-[11px] text-muted-foreground font-mono font-medium">{label}</p>
 <div className="flex items-end gap-2 md:gap-3">
 <span className="text-xl md:text-[28px] font-semibold tracking-[-1px] text-foreground font-heading">{value}</span>
 {change && (
 <span className={`flex items-center gap-1 text-[12px] font-medium font-mono ${positive ? 'text-success' : 'text-destructive'}`}>
 {positive && <ArrowUpRight className="h-3 w-3" />}
 {change}
 </span>
 )}
 {sublabel && (
 <span className="text-[12px] text-foreground/60 font-mono">{sublabel}</span>
 )}
 </div>
 {showBar && <div className="h-[3px] w-full bg-destructive rounded-sm" />}
 </div>
 );
}

// ---------------------------------------------------------------------------
// Meta bar sub-component
// ---------------------------------------------------------------------------

type MetaType = NonNullable<ReturnType<typeof useInsightStore.getState>['impactGraph']>['meta'];

function MetaBar({ meta }: { meta: MetaType }) {
 return (
 <div className="flex flex-wrap items-center gap-2 md:gap-4 px-3 md:px-4 py-1.5 bg-muted rounded text-[10px] text-foreground/60">
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
 className="flex items-center gap-1 text-amber-600 hover:text-warning"
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
