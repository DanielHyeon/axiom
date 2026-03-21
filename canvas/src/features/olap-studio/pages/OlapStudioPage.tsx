/**
 * OlapStudioPage — OLAP Studio 피벗 분석 페이지.
 *
 * 좌측: 큐브 선택 + 차원/측정값 목록 (클릭으로 추가)
 * 중앙: PivotBuilder (4개 드롭 영역) + PivotResultGrid
 * 하단: SQL 미리보기
 */
import { useMemo, useState } from 'react';
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
  Filter as FilterIcon,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePivot } from '../hooks/usePivot';
import { PivotBuilder } from '../components/PivotBuilder';
import { PivotResultGrid } from '../components/PivotResultGrid';
import { PivotSqlPreview } from '../components/PivotSqlPreview';
import { cubes, type CubeDetail } from '../api/olapStudioApi';

// ─── 메인 페이지 ─────────────────────────────────────────

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

export function OlapStudioPage() {
  const pivot = usePivot();
  const [showSql, setShowSql] = useState(false);
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  // 선택된 큐브의 상세 정보 (차원 + 측정값) 동적 로드
  const cubeDetail = useQuery({
    queryKey: ['olap', 'cubes', pivot.selectedCubeId, 'detail'],
    queryFn: () => cubes.get(pivot.selectedCubeId!),
    enabled: !!pivot.selectedCubeId,
  });

  // API 응답에서 차원 목록 변환: dimension_name 기준으로 그룹핑
  const dimensions = useMemo<DimEntry[]>(() => {
    if (!cubeDetail.data?.dimensions) return [];
    const dimMap = new Map<string, string[]>();
    // display_order 기준 정렬 후 그룹핑
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

  // API 응답에서 측정값 목록 변환
  const measures = useMemo<MeasureEntry[]>(() => {
    if (!cubeDetail.data?.measures) return [];
    return cubeDetail.data.measures.map((m) => ({
      name: m.name,
      aggregator: m.aggregation_type,
    }));
  }, [cubeDetail.data?.measures]);

  return (
    <div className="flex h-full">
      {/* ─── 좌측 패널: 큐브 선택 + 필드 목록 ──────────── */}
      <div className="w-[240px] border-r border-[#E5E5E5] flex flex-col shrink-0 bg-white">
        {/* 큐브 선택 드롭다운 */}
        <div className="px-3 py-3 border-b border-[#E5E5E5]">
          <label className="text-[10px] text-foreground/50 font-[IBM_Plex_Mono] mb-1 block">
            큐브 선택
          </label>
          <select
            value={pivot.selectedCubeId || ''}
            onChange={(e) => {
              const cube = pivot.cubeList.data?.find((c) => c.id === e.target.value);
              if (cube) pivot.selectCube(cube);
            }}
            className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1.5 text-[11px] font-[IBM_Plex_Mono]"
            aria-label="큐브 선택"
          >
            <option value="">선택...</option>
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
          {/* 차원 섹션 헤더 */}
          <div className="px-3 py-2 text-[10px] text-foreground/40 font-[IBM_Plex_Mono] font-medium border-b border-[#F0F0F0]">
            차원 (Dimensions)
          </div>

          {/* 큐브 미선택 또는 로딩 중 안내 */}
          {!pivot.selectedCubeId && (
            <div className="px-3 py-4 text-[10px] text-foreground/30 font-[IBM_Plex_Mono] text-center">
              큐브를 선택하세요
            </div>
          )}
          {pivot.selectedCubeId && cubeDetail.isLoading && (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-foreground/30" />
            </div>
          )}
          {pivot.selectedCubeId && !cubeDetail.isLoading && dimensions.length === 0 && (
            <div className="px-3 py-4 text-[10px] text-foreground/30 font-[IBM_Plex_Mono] text-center">
              차원이 없습니다
            </div>
          )}

          {/* 차원 목록 — 아코디언으로 레벨 펼침 */}
          {dimensions.map((dim) => (
            <div key={dim.dimension}>
              <button
                type="button"
                onClick={() =>
                  setExpandedDim(expandedDim === dim.dimension ? null : dim.dimension)
                }
                className="flex items-center gap-1.5 w-full text-left px-3 py-1.5 text-[11px] font-[IBM_Plex_Mono] hover:bg-[#F5F5F5] transition-colors"
                aria-expanded={expandedDim === dim.dimension}
              >
                {expandedDim === dim.dimension ? (
                  <ChevronDown className="h-3 w-3 text-foreground/30" />
                ) : (
                  <ChevronRight className="h-3 w-3 text-foreground/30" />
                )}
                <span className="text-foreground/70">{dim.dimension}</span>
              </button>

              {/* 펼쳐진 레벨 목록 — 행/열 추가 버튼 */}
              {expandedDim === dim.dimension && (
                <div className="pl-7 pb-1">
                  {dim.levels.map((level) => (
                    <div key={level} className="flex items-center gap-1 py-0.5">
                      <span className="text-[10px] text-foreground/50 font-[IBM_Plex_Mono] flex-1">
                        {level}
                      </span>
                      <button
                        type="button"
                        onClick={() => pivot.addRow({ dimension: dim.dimension, level })}
                        className="p-0.5 rounded hover:bg-blue-50 text-blue-400"
                        title="행에 추가"
                        aria-label={`${level}을 행에 추가`}
                      >
                        <Rows3 className="h-2.5 w-2.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => pivot.addColumn({ dimension: dim.dimension, level })}
                        className="p-0.5 rounded hover:bg-purple-50 text-purple-400"
                        title="열에 추가"
                        aria-label={`${level}을 열에 추가`}
                      >
                        <Columns3 className="h-2.5 w-2.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* 측정값 섹션 헤더 */}
          <div className="px-3 py-2 text-[10px] text-foreground/40 font-[IBM_Plex_Mono] font-medium border-y border-[#F0F0F0] mt-2">
            측정값 (Measures)
          </div>

          {/* 측정값 목록 — 클릭으로 추가 */}
          {measures.map((m) => (
            <button
              key={m.name}
              type="button"
              onClick={() => pivot.addMeasure(m)}
              className="flex items-center gap-2 w-full text-left px-3 py-1.5 text-[11px] font-[IBM_Plex_Mono] hover:bg-[#F5F5F5] transition-colors"
              aria-label={`측정값 ${m.name} 추가`}
            >
              <BarChart3 className="h-3 w-3 text-emerald-400" />
              <span className="text-foreground/70">{m.name}</span>
              <span className="ml-auto text-[9px] text-foreground/30">{m.aggregator}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ─── 중앙 + 하단 영역 ─────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 상단 바 — 타이틀 + 액션 버튼 */}
        <div className="flex items-center gap-2 px-4 h-10 border-b border-[#E5E5E5] bg-[#FAFAFA] shrink-0">
          <BarChart3 className="h-4 w-4 text-blue-500" />
          <h1 className="text-[14px] font-semibold font-[Sora]">OLAP Studio</h1>
          {pivot.selectedCubeName && (
            <span className="text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
              {pivot.selectedCubeName}
            </span>
          )}

          <div className="ml-auto flex items-center gap-2">
            {/* SQL 미리보기 버튼 */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                pivot.preview();
                setShowSql(true);
              }}
              disabled={pivot.isPreviewing || pivot.config.measures.length === 0}
              className="text-[11px]"
            >
              {pivot.isPreviewing ? (
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
              ) : (
                <Eye className="h-3 w-3 mr-1" />
              )}
              SQL 보기
            </Button>

            {/* 실행 버튼 */}
            <Button
              size="sm"
              onClick={() => pivot.execute()}
              disabled={pivot.isExecuting || pivot.config.measures.length === 0}
              className="text-[11px]"
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

        {/* PivotBuilder — 4개 드롭 영역 */}
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

        {/* 결과 / SQL 프리뷰 — 탭 전환 */}
        <div className="flex-1 flex flex-col border-t border-[#E5E5E5] min-h-0">
          {/* 탭 헤더 */}
          <div className="flex items-center gap-0.5 px-4 pt-1 bg-[#FAFAFA] border-b border-[#E5E5E5] shrink-0">
            <button
              type="button"
              onClick={() => setShowSql(false)}
              className={cn(
                'px-3 py-1 text-[10px] font-[IBM_Plex_Mono] rounded-t transition-colors',
                !showSql
                  ? 'bg-white border border-b-0 border-[#E5E5E5] text-foreground/70 font-medium'
                  : 'text-foreground/30 hover:text-foreground/50',
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
                'px-3 py-1 text-[10px] font-[IBM_Plex_Mono] rounded-t transition-colors',
                showSql
                  ? 'bg-white border border-b-0 border-[#E5E5E5] text-foreground/70 font-medium'
                  : 'text-foreground/30 hover:text-foreground/50',
              )}
              aria-selected={showSql}
              role="tab"
            >
              SQL
            </button>
          </div>

          {/* 탭 내용 */}
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
