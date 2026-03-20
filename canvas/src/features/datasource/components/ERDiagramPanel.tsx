/**
 * ERD 메인 패널 — 데이터 로딩 + 필터 적용 + Mermaid 렌더링 조합.
 * DatasourcePage의 ERD 탭에서 사용.
 */

import { useState, useMemo, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useERDData } from '../hooks/useERDData';
import { generateMermaidERCode, getConnectedTables } from '../utils/mermaidCodeGen';
import { MermaidERDRenderer } from './MermaidERDRenderer';
import { ERDToolbar } from './ERDToolbar';
import type { ERDFilter, ERDStats } from '../types/erd';
import { Database } from 'lucide-react';

interface ERDiagramPanelProps {
  /** Oracle Meta API에 전달할 데이터소스 ID */
  datasourceId: string;
}

/** 기본 필터 값 */
const DEFAULT_FILTER: ERDFilter = {
  searchQuery: '',
  showConnectedOnly: false,
  maxTables: 50,
};

export function ERDiagramPanel({ datasourceId }: ERDiagramPanelProps) {
  const { t } = useTranslation();
  const { tables, isLoading, error, refetch } = useERDData(datasourceId);
  const [filter, setFilter] = useState<ERDFilter>(DEFAULT_FILTER);
  const svgContainerRef = useRef<HTMLDivElement>(null);

  // 필터 적용된 테이블 목록
  const filteredTables = useMemo(() => {
    let result = tables;

    // 검색 필터
    if (filter.searchQuery) {
      const q = filter.searchQuery.toLowerCase();
      result = result.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.columns.some((c) => c.name.toLowerCase().includes(q))
      );
    }

    // 연결된 테이블만
    if (filter.showConnectedOnly && result.length > 0) {
      result = getConnectedTables(result, tables);
    }

    // 최대 테이블 수 제한
    if (result.length > filter.maxTables) {
      result = result.slice(0, filter.maxTables);
    }

    return result;
  }, [tables, filter]);

  // Mermaid 코드 + 통계 생성
  const { code, stats } = useMemo(() => {
    if (filteredTables.length === 0) {
      return { code: '', stats: { tables: 0, relationships: 0, columns: 0 } as ERDStats };
    }
    return generateMermaidERCode(filteredTables);
  }, [filteredTables]);

  // SVG 다운로드
  const handleDownloadSvg = useCallback(() => {
    // Mermaid 렌더러 내부의 SVG 엘리먼트 찾기
    const container = document.querySelector('[data-erd-svg-container]');
    const svg = container?.querySelector('svg');
    if (!svg) return;

    const serializer = new XMLSerializer();
    const svgString = serializer.serializeToString(svg);
    const blob = new Blob([svgString], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `erd-${datasourceId}-${new Date().toISOString().slice(0, 10)}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }, [datasourceId]);

  // 에러 상태
  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-foreground/60 gap-3 p-8">
        <Database className="h-8 w-8 opacity-30" />
        <p className="text-sm">{t('datasource.erd.errorTitle')}</p>
        <p className="text-xs text-destructive">{error instanceof Error ? error.message : String(error)}</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="text-xs text-blue-600 hover:underline"
        >
          {t('datasource.erd.retryBtn')}
        </button>
      </div>
    );
  }

  // 로딩 상태
  if (isLoading && tables.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-foreground/60 text-sm">
        <div className="flex items-center gap-2">
          <div className="h-4 w-4 border-2 border-foreground/30 border-t-foreground/60 rounded-full animate-spin" />
          {t('datasource.erd.loading')}
        </div>
      </div>
    );
  }

  // 데이터 없음
  if (tables.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-foreground/60 gap-3 p-8">
        <Database className="h-8 w-8 opacity-30" />
        <p className="text-sm">{t('datasource.erd.noTables')}</p>
        <p className="text-xs">{t('datasource.erd.noTablesHint')}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 툴바 */}
      <ERDToolbar
        filter={filter}
        onFilterChange={setFilter}
        stats={stats}
        onDownloadSvg={handleDownloadSvg}
        onRefresh={() => refetch()}
        isLoading={isLoading}
      />

      {/* ERD 렌더링 영역 */}
      <div className="flex-1 overflow-hidden" data-erd-svg-container>
        <MermaidERDRenderer mermaidCode={code} />
      </div>
    </div>
  );
}
