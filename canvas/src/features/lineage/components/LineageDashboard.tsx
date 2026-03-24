/**
 * LineageDashboard — 리니지 메인 페이지
 * 헤더(검색+필터) + 통계 바 + 그래프 + 상세 패널로 구성
 */

import { useCallback, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useLineageOverview, useLineageGraph } from '../hooks/useLineage';
import { useLineageStore } from '../store/useLineageStore';
import { LineageSearchBar } from './LineageSearchBar';
import { LineageFilter } from './LineageFilter';
import { LineageGraph } from './LineageGraph';
import { LineageNodeDetail } from './LineageNodeDetail';
import { LineageLegend } from './LineageLegend';
import { LINEAGE_NODE_STYLES } from '../types/lineage';
import { useTranslation } from 'react-i18next';

/** 통계 카드 항목 */
const STAT_CARDS = [
  { key: 'sourceCount' as const, label: t('mvExt.sourceTable'), color: LINEAGE_NODE_STYLES.source.color },
  { key: 'tableCount' as const, label: t('olapExt.chartTable'), color: LINEAGE_NODE_STYLES.table.color },
  { key: 'transformCount' as const, label: t('lineageExt.dashboard.transform'), color: LINEAGE_NODE_STYLES.transform.color },
  { key: 'viewCount' as const, label: t('lineageExt.dashboard.view'), color: LINEAGE_NODE_STYLES.view.color },
  { key: 'reportCount' as const, label: t('lineageExt.dashboard.report'), color: LINEAGE_NODE_STYLES.report.color },
  { key: 'edgeCount' as const, label: t('lineageExt.dataFlowLabel'), color: '#F59E0B' },
] as const;

export function LineageDashboard() {
  const { t } = useTranslation();
  // 전체 개요 쿼리
  const { isLoading: overviewLoading, refetch: refetchOverview } = useLineageOverview();

  // 검색으로 선택된 노드 기준 그래프 (없으면 overview 사용)
  const [focusNodeId, setFocusNodeId] = useState<string | null>(null);
  const { filters } = useLineageStore();
  const { isLoading: graphLoading } = useLineageGraph(
    focusNodeId,
    filters.direction,
    filters.depth,
  );

  const stats = useLineageStore((s) => s.stats);
  const isDetailOpen = useLineageStore((s) => s.isDetailOpen);

  const isLoading = overviewLoading || graphLoading;

  // 새로고침
  const handleRefresh = useCallback(() => {
    setFocusNodeId(null);
    refetchOverview();
  }, [refetchOverview]);

  // 검색 결과 노드 선택 → 해당 노드 기준 그래프 로드
  const handleSearchSelect = useCallback((nodeId: string) => {
    setFocusNodeId(nodeId);
  }, []);

  return (
    <div className="flex h-full flex-col bg-background">
      {/* ── 헤더 ── */}
      <header className="flex flex-wrap items-center justify-between gap-2 md:gap-3 border-b border-border bg-card px-4 md:px-6 py-3 md:py-4">
        <div className="flex items-center gap-3">
          <h2 className="text-base md:text-lg font-semibold text-foreground">
            {t('olapStudioExt.dataLineage')}
          </h2>
        </div>

        <div className="flex items-center gap-2 md:gap-3">
          {/* 검색 */}
          <LineageSearchBar onNodeSelect={handleSearchSelect} />

          {/* 새로고침 */}
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className="flex items-center gap-1.5 rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={t('lineageExt.refresh')}
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{t('lineageExt.refresh')}</span>
          </button>
        </div>
      </header>

      {/* ── 통계 바 ── */}
      {stats && (
        <div className="grid grid-cols-3 md:grid-cols-6 gap-2 md:gap-3 border-b border-border bg-card px-4 md:px-6 py-2 md:py-3">
          {STAT_CARDS.map(({ key, label, color }) => (
            <div
              key={key}
              className="flex flex-col items-center rounded-xl border border-border/60 bg-muted/20 p-2 md:p-3"
              style={{
                background: `linear-gradient(135deg, ${color}15 0%, ${color}05 100%)`,
                borderColor: `${color}30`,
              }}
            >
              <span className="text-lg md:text-xl font-bold leading-none" style={{ color }}>
                {stats[key]}
              </span>
              <span className="mt-0.5 md:mt-1 text-[10px] md:text-[11px] uppercase tracking-wider text-muted-foreground">
                {label}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── 필터 도구 모음 ── */}
      <div className="border-b border-border bg-card px-4 md:px-6 py-2 md:py-2.5">
        <LineageFilter />
      </div>

      {/* ── 메인 컨텐츠: 그래프 + 상세 패널 ── */}
      <div className="relative flex-1 overflow-hidden">
        <LineageGraph isLoading={isLoading} />
        <LineageLegend />
        {isDetailOpen && <LineageNodeDetail />}
      </div>
    </div>
  );
}
