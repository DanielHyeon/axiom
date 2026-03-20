/**
 * ERD 다이어그램 툴바 — 검색, 필터, SVG 다운로드, 통계 표시.
 */

import { useRef, useCallback, useEffect } from 'react';
import { Search, Download, RotateCw, Table, Link, Columns3 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import type { ERDStats, ERDFilter } from '../types/erd';

interface ERDToolbarProps {
  filter: ERDFilter;
  onFilterChange: (filter: ERDFilter) => void;
  stats: ERDStats;
  onDownloadSvg: () => void;
  onRefresh: () => void;
  isLoading: boolean;
}

/** 최대 테이블 수 옵션 */
const MAX_TABLE_OPTIONS = [10, 20, 30, 50, 100, 200];

export function ERDToolbar({
  filter,
  onFilterChange,
  stats,
  onDownloadSvg,
  onRefresh,
  isLoading,
}: ERDToolbarProps) {
  // 디바운스 타이머를 ref로 관리 (불필요한 리렌더 방지 + 클린업 보장)
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 컴포넌트 언마운트 시 타이머 정리
  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, []);

  // 검색 입력 — 300ms 디바운스
  const handleSearchChange = useCallback(
    (value: string) => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
      searchTimeoutRef.current = setTimeout(() => {
        onFilterChange({ ...filter, searchQuery: value });
        searchTimeoutRef.current = null;
      }, 300);
    },
    [filter, onFilterChange]
  );

  return (
    <div className="flex items-center gap-3 p-3 border-b border-[#E5E5E5] bg-[#FAFAFA]">
      {/* 검색 */}
      <div className="relative flex-1 max-w-xs">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-foreground/40" />
        <Input
          placeholder="테이블 검색..."
          defaultValue={filter.searchQuery}
          onChange={(e) => handleSearchChange(e.target.value)}
          className="pl-8 h-8 text-xs bg-white border-[#E5E5E5] font-[IBM_Plex_Mono]"
        />
      </div>

      {/* 연결된 테이블만 보기 */}
      <div className="flex items-center gap-1.5">
        <Checkbox
          id="erd-connected-only"
          checked={filter.showConnectedOnly}
          onCheckedChange={(checked) =>
            onFilterChange({ ...filter, showConnectedOnly: checked === true })
          }
        />
        <label
          htmlFor="erd-connected-only"
          className="text-[11px] text-foreground/60 font-[IBM_Plex_Mono] cursor-pointer whitespace-nowrap"
        >
          연결된 테이블만
        </label>
      </div>

      {/* 최대 테이블 수 */}
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] text-foreground/60 font-[IBM_Plex_Mono]">최대:</span>
        <select
          value={filter.maxTables}
          onChange={(e) =>
            onFilterChange({ ...filter, maxTables: Number(e.target.value) })
          }
          className="h-7 px-2 text-[11px] border border-[#E5E5E5] rounded bg-white font-[IBM_Plex_Mono] text-foreground/80"
          aria-label="최대 테이블 수"
        >
          {MAX_TABLE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n}개
            </option>
          ))}
        </select>
      </div>

      {/* 구분선 */}
      <div className="h-5 w-px bg-[#E5E5E5]" />

      {/* 통계 표시 */}
      <div className="flex items-center gap-3 text-[10px] text-foreground/50 font-[IBM_Plex_Mono]">
        <span className="flex items-center gap-1">
          <Table className="h-3 w-3" />
          {stats.tables}
        </span>
        <span className="flex items-center gap-1">
          <Link className="h-3 w-3" />
          {stats.relationships}
        </span>
        <span className="flex items-center gap-1">
          <Columns3 className="h-3 w-3" />
          {stats.columns}
        </span>
      </div>

      {/* 액션 버튼 */}
      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          className="p-1.5 rounded text-foreground/60 hover:text-black hover:bg-[#F0F0F0] transition-colors disabled:opacity-40"
          title="새로고침"
        >
          <RotateCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
        <button
          type="button"
          onClick={onDownloadSvg}
          className="p-1.5 rounded text-foreground/60 hover:text-black hover:bg-[#F0F0F0] transition-colors"
          title="SVG 다운로드"
        >
          <Download className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
