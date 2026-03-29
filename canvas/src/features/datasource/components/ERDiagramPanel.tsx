/**
 * ERD 메인 패널 — 데이터 로딩 + 필터 적용 + Cytoscape 인터랙티브 ERD 렌더링.
 * DatasourcePage의 ERD 탭에서 사용.
 *
 * v2: MermaidERDRenderer → CytoscapeERDRenderer 교체
 *     - 개별 노드 드래그 지원
 *     - 이미지 다운로드는 Cytoscape cy.png() 사용
 */

import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import type cytoscape from 'cytoscape';
import { useERDData } from '../hooks/useERDData';
import { getConnectedTables } from '../utils/mermaidCodeGen';
import { CytoscapeERDRenderer, countERDRelations } from './CytoscapeERDRenderer';
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

  // 전체화면 상태 관리
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Cytoscape 인스턴스 참조 — SVG/PNG 내보내기에 사용
  const cyInstanceRef = useRef<cytoscape.Core | null>(null);
  const handleCyInit = useCallback((cy: cytoscape.Core) => {
    cyInstanceRef.current = cy;
  }, []);

  /** 전체화면 토글 — CSS 오버레이 방식 (같은 DOM 유지, Cytoscape 캔버스 분리 방지) */
  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
    // 전체화면 전환 후 Cytoscape 캔버스 리사이즈 트리거
    requestAnimationFrame(() => {
      cyInstanceRef.current?.resize();
      cyInstanceRef.current?.fit();
    });
  }, []);

  // ESC 키로 전체화면 종료 + Cytoscape 리사이즈
  useEffect(() => {
    if (!isFullscreen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsFullscreen(false);
        requestAnimationFrame(() => {
          cyInstanceRef.current?.resize();
          cyInstanceRef.current?.fit();
        });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFullscreen]);
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

  // ERD 통계 계산 (Cytoscape 렌더러에서 관계 수 추출)
  const stats = useMemo<ERDStats>(() => {
    if (filteredTables.length === 0) {
      return { tables: 0, relationships: 0, columns: 0 };
    }
    const totalColumns = filteredTables.reduce((sum, t) => sum + t.columns.length, 0);
    const relationships = countERDRelations(filteredTables);
    return { tables: filteredTables.length, relationships, columns: totalColumns };
  }, [filteredTables]);

  // 이미지 다운로드 — Cytoscape cy.png() 사용 (고해상도 2x)
  const handleDownloadSvg = useCallback(() => {
    const cy = cyInstanceRef.current;
    if (!cy) return;

    // PNG base64 데이터 URL 생성 (전체 그래프, 2배 스케일, 흰 배경)
    const pngData = (cy as any).png({
      full: true,
      scale: 2,
      bg: '#FFFFFF',
      output: 'blob',
    });

    // cy.png()은 output:'blob'이 아닌 경우 base64 문자열 반환
    // output:'blob' 미지원 시 base64로 폴백
    if (pngData instanceof Blob) {
      const url = URL.createObjectURL(pngData);
      const a = document.createElement('a');
      a.href = url;
      a.download = `erd-${datasourceId}-${new Date().toISOString().slice(0, 10)}.png`;
      a.click();
      URL.revokeObjectURL(url);
    } else {
      // base64 data URL (기본 반환 형식)
      const dataUrl = (cy as any).png({ full: true, scale: 2, bg: '#FFFFFF' }) as string;
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `erd-${datasourceId}-${new Date().toISOString().slice(0, 10)}.png`;
      a.click();
    }
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

  // CSS-only 전체화면: Portal 대신 같은 DOM 노드에 fixed 스타일 적용
  // Cytoscape 캔버스가 원래 컨테이너에 바인딩되어 있으므로 DOM 이동 없이 CSS만 변경
  return (
    <div
      ref={containerRef}
      className={`flex flex-col ${
        isFullscreen
          ? 'fixed inset-0 z-[9999] w-screen h-screen bg-background'
          : 'h-full'
      }`}
    >
      <ERDToolbar
        filter={filter}
        onFilterChange={setFilter}
        stats={stats}
        onDownloadSvg={handleDownloadSvg}
        onRefresh={() => refetch()}
        isLoading={isLoading}
        onToggleFullscreen={handleToggleFullscreen}
        isFullscreen={isFullscreen}
      />
      <div className="flex-1 min-h-0 overflow-hidden" data-erd-svg-container>
        <CytoscapeERDRenderer
          tables={filteredTables}
          onCyInit={handleCyInit}
        />
      </div>
    </div>
  );
}
