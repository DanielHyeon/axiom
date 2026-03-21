/**
 * PivotResultGrid — 피벗 실행 결과 테이블.
 *
 * 컬럼 헤더 + 데이터 행 + 실행 통계를 표시한다.
 * 대량 결과(100행 초과)는 페이지네이션 기반으로 점진 로딩한다.
 */
import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { AlertCircle, Clock, Hash, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { PivotResult } from '../hooks/usePivot';

// ─── 상수 ───────────────────────────────────────────────

/** 한 번에 표시하는 최대 행 수 */
const PAGE_SIZE = 100;

// ─── Props ────────────────────────────────────────────────

interface PivotResultGridProps {
  result: PivotResult | null;
  isLoading: boolean;
}

// ─── 컴포넌트 ────────────────────────────────────────────

export function PivotResultGrid({ result, isLoading }: PivotResultGridProps) {
  // 페이지네이션 — 표시할 행 수 관리
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  // 결과 변경 시 표시 행 수 초기화
  const resultId = result?.sql ?? '';
  useMemo(() => {
    setVisibleCount(PAGE_SIZE);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultId]);

  // 표시할 행만 슬라이싱 — 대량 결과 성능 최적화
  const visibleRows = useMemo(
    () => result?.rows.slice(0, visibleCount) ?? [],
    [result?.rows, visibleCount],
  );

  // 더 보기 가능 여부
  const totalRows = result?.rows.length ?? 0;
  const hasMore = visibleCount < totalRows;
  const remainingCount = totalRows - visibleCount;

  // "더 보기" 클릭 — 다음 PAGE_SIZE만큼 추가 로드
  const handleLoadMore = () => {
    setVisibleCount((prev) => Math.min(prev + PAGE_SIZE, totalRows));
  };

  // ─── 로딩 상태 ──────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="h-5 w-5 border-2 border-foreground/20 border-t-blue-500 rounded-full animate-spin" />
      </div>
    );
  }

  // ─── 초기 상태 — 아직 실행하지 않음 ────────────────────
  if (!result) {
    return (
      <div className="flex items-center justify-center py-12 text-[11px] text-foreground/30 font-[IBM_Plex_Mono]">
        피벗을 실행하면 결과가 여기에 표시됩니다
      </div>
    );
  }

  // ─── 에러 상태 ──────────────────────────────────────────
  if (result.error) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2">
        <AlertCircle className="h-5 w-5 text-red-400" />
        <span className="text-[11px] text-red-500 font-[IBM_Plex_Mono]">{result.error}</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 통계 바 — 행 수, 표시 수, 실행 시간 */}
      <div className="flex items-center gap-4 px-4 py-1.5 bg-[#FAFAFA] border-b border-[#E5E5E5] text-[9px] font-[IBM_Plex_Mono] text-foreground/50 shrink-0">
        <span className="flex items-center gap-1">
          <Hash className="h-3 w-3" />
          {result.row_count.toLocaleString()}행
        </span>
        {/* 페이지네이션 중일 때 표시 행 수 안내 */}
        {totalRows > PAGE_SIZE && (
          <span className="text-foreground/30">
            (표시: {visibleRows.length.toLocaleString()}/{totalRows.toLocaleString()})
          </span>
        )}
        <span className="flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {result.execution_time_ms}ms
        </span>
      </div>

      {/* 결과 테이블 */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-[10px] font-[IBM_Plex_Mono]">
          <thead className="sticky top-0 z-10">
            <tr className="bg-[#F5F5F5] border-b border-[#E5E5E5]">
              {result.columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-1.5 text-left text-foreground/60 font-medium whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className={cn(
                  'border-b border-[#F0F0F0] hover:bg-blue-50/30 transition-colors',
                  rowIdx % 2 === 0 ? 'bg-white' : 'bg-[#FCFCFC]',
                )}
              >
                {(row as unknown[]).map((cell, colIdx) => (
                  <td key={colIdx} className="px-3 py-1 text-foreground/70 whitespace-nowrap">
                    {cell != null ? (
                      String(cell)
                    ) : (
                      <span className="text-foreground/20 italic">NULL</span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        {/* 빈 결과 */}
        {result.rows.length === 0 && (
          <div className="py-8 text-center text-[11px] text-foreground/30 font-[IBM_Plex_Mono]">
            결과가 없습니다
          </div>
        )}

        {/* "더 보기" 버튼 — 표시할 행이 남아있을 때만 렌더링 */}
        {hasMore && (
          <div className="flex justify-center py-3 border-t border-[#F0F0F0]">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLoadMore}
              className="h-7 text-[10px] font-[IBM_Plex_Mono] text-foreground/50 hover:text-foreground/70 gap-1"
            >
              <ChevronDown className="h-3 w-3" />
              더 보기 ({Math.min(PAGE_SIZE, remainingCount).toLocaleString()}행
              {remainingCount > PAGE_SIZE && ` / 남은 ${remainingCount.toLocaleString()}행`})
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
