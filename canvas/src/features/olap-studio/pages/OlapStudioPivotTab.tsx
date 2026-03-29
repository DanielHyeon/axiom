/**
 * OlapStudioPivotTab — OLAP Studio 내 피벗 탭 콘텐츠
 *
 * 기존 OlapStudioPage의 피벗 분석 UI를 탭 형태로 분리.
 * 좌측 큐브 필드 선택 + 중앙 PivotBuilder + PivotResultGrid 구조.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import {
  BarChart3,
  Play,
  Eye,
  Loader2,
  ChevronDown,
  ChevronRight,
  Rows3,
  Columns3,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePivot } from '../hooks/usePivot';
import { PivotBuilder } from '../components/PivotBuilder';
import { PivotResultGrid } from '../components/PivotResultGrid';
import { PivotSqlPreview } from '../components/PivotSqlPreview';
import { cubes } from '../api/olapStudioApi';

/** 차원 목록 형식 — dimension 이름 + 하위 레벨 배열 */
interface DimEntry {
  dimension: string;
  levels: string[];
}

/** 측정값 목록 형식 */
interface MeasureEntry {
  name: string;
  aggregator: string;
}

export function OlapStudioPivotTab() {
  const { t } = useTranslation();
  const pivot = usePivot();
  const [showSql, setShowSql] = useState(false);
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  // 선택된 큐브의 상세 정보 (차원 + 측정값) 동적 로드
  const cubeDetail = useQuery({
    queryKey: ['olap', 'cubes', pivot.selectedCubeId, 'detail'],
    queryFn: () => cubes.get(pivot.selectedCubeId!),
    enabled: !!pivot.selectedCubeId,
  });

  // 차원 목록 변환
  const dimensions = useMemo<DimEntry[]>(() => {
    if (!cubeDetail.data?.dimensions) return [];
    const dimMap = new Map<string, string[]>();
    const sorted = [...cubeDetail.data.dimensions].sort(
      (a, b) => (a.hierarchy_level ?? 0) - (b.hierarchy_level ?? 0),
    );
    for (const d of sorted) {
      const dimName = d.source_column?.split('.')[0] || d.name;
      if (!dimMap.has(dimName)) dimMap.set(dimName, []);
      dimMap.get(dimName)!.push(d.name);
    }
    return Array.from(dimMap.entries()).map(([dimension, levels]) => ({
      dimension,
      levels,
    }));
  }, [cubeDetail.data?.dimensions]);

  // 측정값 목록 변환
  const measures = useMemo<MeasureEntry[]>(() => {
    if (!cubeDetail.data?.measures) return [];
    return cubeDetail.data.measures.map((m) => ({
      name: m.name,
      aggregator: m.aggregation_type,
    }));
  }, [cubeDetail.data?.measures]);

  return (
    <div className="flex h-[calc(100vh-12rem)] border border-border rounded-lg bg-card overflow-hidden">
      {/* 좌측 패널: 큐브 선택 + 필드 목록 */}
      <div className="w-[240px] border-r border-border flex flex-col shrink-0">
        {/* 큐브 선택 */}
        <div className="px-3 py-3 border-b border-border">
          <label className="text-[10px] text-text-placeholder font-mono mb-1 block">
            큐브 선택
          </label>
          <select
            value={pivot.selectedCubeId || ''}
            onChange={(e) => {
              const cube = pivot.cubeList.data?.find((c) => c.id === e.target.value);
              if (cube) pivot.selectCube(cube);
            }}
            className="w-full rounded border border-border bg-card px-2 py-1.5 text-[11px] font-mono"
            aria-label="큐브 선택"
          >
            <option value="">큐브를 선택하세요</option>
            {(pivot.cubeList.data || [])
              .filter((c) => c.cube_status === 'PUBLISHED')
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
        </div>

        {/* 차원 + 측정값 목록 */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-3 py-2 text-[10px] text-text-placeholder font-mono font-medium border-b border-border">
            차원
          </div>

          {!pivot.selectedCubeId && (
            <div className="px-3 py-4 text-[10px] text-muted-foreground font-mono text-center">
              큐브를 먼저 선택하세요
            </div>
          )}
          {pivot.selectedCubeId && cubeDetail.isLoading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          )}

          {dimensions.map((dim) => (
            <div key={dim.dimension}>
              <button
                type="button"
                onClick={() =>
                  setExpandedDim(expandedDim === dim.dimension ? null : dim.dimension)
                }
                className="flex items-center gap-1.5 w-full text-left px-3 py-1.5 text-[11px] font-mono hover:bg-muted transition-colors"
                aria-expanded={expandedDim === dim.dimension}
              >
                {expandedDim === dim.dimension ? (
                  <ChevronDown className="h-3 w-3 text-text-placeholder" />
                ) : (
                  <ChevronRight className="h-3 w-3 text-text-placeholder" />
                )}
                <span className="text-foreground">{dim.dimension}</span>
              </button>

              {expandedDim === dim.dimension && (
                <div className="pl-7 pb-1">
                  {dim.levels.map((level) => (
                    <div key={level} className="flex items-center gap-1 py-0.5">
                      <span className="text-[10px] text-muted-foreground font-mono flex-1">{level}</span>
                      <button
                        type="button"
                        onClick={() => pivot.addRow({ dimension: dim.dimension, level })}
                        className="p-0.5 rounded hover:bg-blue-50 text-blue-400"
                        title="행에 추가"
                        aria-label={`${level} 행에 추가`}
                      >
                        <Rows3 className="h-2.5 w-2.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => pivot.addColumn({ dimension: dim.dimension, level })}
                        className="p-0.5 rounded hover:bg-purple-50 text-purple-400"
                        title="열에 추가"
                        aria-label={`${level} 열에 추가`}
                      >
                        <Columns3 className="h-2.5 w-2.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          <div className="px-3 py-2 text-[10px] text-text-placeholder font-mono font-medium border-y border-border mt-2">
            측정값
          </div>

          {measures.map((m) => (
            <button
              key={m.name}
              type="button"
              onClick={() => pivot.addMeasure(m)}
              className="flex items-center gap-2 w-full text-left px-3 py-1.5 text-[11px] font-mono hover:bg-muted transition-colors"
              aria-label={`${m.name} 추가`}
            >
              <BarChart3 className="h-3 w-3 text-emerald-400" />
              <span className="text-foreground">{m.name}</span>
              <span className="ml-auto text-[9px] text-muted-foreground">{m.aggregator}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 중앙 + 하단 영역 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 상단 바 */}
        <div className="flex items-center gap-2 px-4 h-10 border-b border-border bg-background shrink-0">
          <BarChart3 className="h-4 w-4 text-blue-500" />
          <h2 className="text-sm font-semibold">Pivot</h2>
          {pivot.selectedCubeName && (
            <span className="text-[11px] text-text-placeholder font-mono">{pivot.selectedCubeName}</span>
          )}

          <div className="ml-auto flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                pivot.preview();
                setShowSql(true);
              }}
              disabled={pivot.isPreviewing || pivot.config.measures.length === 0}
              className="text-[11px] h-7"
            >
              {pivot.isPreviewing ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <Eye className="h-3 w-3 mr-1" />
              )}
              SQL
            </Button>

            <Button
              type="button"
              size="sm"
              onClick={() => pivot.execute()}
              disabled={pivot.isExecuting || pivot.config.measures.length === 0}
              className="text-[11px] h-7 bg-primary hover:bg-primary/90 text-primary-foreground border-0"
            >
              {pivot.isExecuting ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <Play className="h-3 w-3 mr-1" />
              )}
              실행
            </Button>
          </div>
        </div>

        {/* PivotBuilder */}
        <PivotBuilder
          rows={pivot.config.rows}
          columns={pivot.config.columns}
          measures={pivot.config.measures}
          filters={pivot.config.filters}
          onRemoveRow={pivot.removeRow}
          onRemoveColumn={pivot.removeColumn}
          onRemoveMeasure={pivot.removeMeasure}
          onRemoveFilter={pivot.removeFilter}
        />

        {/* 결과 / SQL 프리뷰 */}
        <div className="flex-1 flex flex-col border-t border-border min-h-0">
          <div className="flex items-center gap-0.5 px-4 pt-1 bg-background border-b border-border shrink-0">
            <button
              type="button"
              onClick={() => setShowSql(false)}
              className={cn(
                'px-3 py-1 text-[10px] font-mono rounded-t transition-colors',
                !showSql
                  ? 'bg-card border border-b-0 border-border text-foreground font-medium'
                  : 'text-muted-foreground hover:text-muted-foreground',
              )}
              aria-selected={!showSql}
              role="tab"
            >
              결과
            </button>
            <button
              type="button"
              onClick={() => setShowSql(true)}
              className={cn(
                'px-3 py-1 text-[10px] font-mono rounded-t transition-colors',
                showSql
                  ? 'bg-card border border-b-0 border-border text-foreground font-medium'
                  : 'text-muted-foreground hover:text-muted-foreground',
              )}
              aria-selected={showSql}
              role="tab"
            >
              SQL
            </button>
          </div>

          <div className="flex-1 min-h-0" role="tabpanel">
            {showSql ? (
              <PivotSqlPreview sql={pivot.previewSql} isLoading={pivot.isPreviewing} />
            ) : (
              <PivotResultGrid result={pivot.result} isLoading={pivot.isExecuting} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
