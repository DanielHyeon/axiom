/**
 * SchemaSearchBar — 스키마 검색 (테이블/컬럼).
 *
 * 데이터베이스 트리 상단에 배치되어 테이블명, 컬럼명으로 검색 가능.
 * 검색 결과를 드롭다운으로 표시하고, 클릭 시 해당 노드로 이동.
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Search, Table2, Columns3, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import type { SchemaSearchResult } from '../types/schema';

// ─── Props ────────────────────────────────────────────────

interface SchemaSearchBarProps {
  /** 검색어 */
  value: string;
  /** 검색어 변경 핸들러 */
  onChange: (value: string) => void;
  /** 검색 결과 */
  results: SchemaSearchResult[];
  /** 결과 클릭 핸들러 */
  onSelectResult: (result: SchemaSearchResult) => void;
  /** 플레이스홀더 */
  placeholder?: string;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function SchemaSearchBar({
  value,
  onChange,
  results,
  onSelectResult,
  placeholder = '테이블·컬럼 검색...',
}: SchemaSearchBarProps) {
  const [isFocused, setIsFocused] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsFocused(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 결과 선택
  const handleSelect = useCallback(
    (result: SchemaSearchResult) => {
      onSelectResult(result);
      setIsFocused(false);
    },
    [onSelectResult]
  );

  // 검색어 초기화
  const handleClear = useCallback(() => {
    onChange('');
  }, [onChange]);

  const showDropdown = isFocused && value.trim().length > 0 && results.length > 0;

  return (
    <div ref={containerRef} className="relative px-3 py-2 border-b border-[#E5E5E5]">
      {/* 검색 입력 */}
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-foreground/30" />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          placeholder={placeholder}
          className="pl-7 pr-7 h-7 text-[11px] bg-white border-[#E5E5E5] font-[IBM_Plex_Mono]"
        />
        {value && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-[#F0F0F0]"
            aria-label="검색어 초기화"
          >
            <X className="h-3 w-3 text-foreground/30" />
          </button>
        )}
      </div>

      {/* 검색 결과 드롭다운 */}
      {showDropdown && (
        <div className="absolute left-3 right-3 top-full mt-1 bg-white border border-[#E5E5E5] rounded shadow-lg z-50 max-h-[200px] overflow-y-auto">
          {results.map((result, idx) => (
            <button
              key={`${result.type}-${result.matchedText}-${idx}`}
              type="button"
              onClick={() => handleSelect(result)}
              className="flex items-center gap-2 w-full text-left px-3 py-1.5 hover:bg-[#F5F5F5] transition-colors"
            >
              {result.type === 'table' ? (
                <Table2 className="h-3 w-3 text-blue-400 shrink-0" />
              ) : (
                <Columns3 className="h-3 w-3 text-foreground/30 shrink-0" />
              )}
              <span className="text-[11px] font-[IBM_Plex_Mono] text-foreground/70 truncate">
                {result.matchedText}
              </span>
              <span className="ml-auto text-[9px] text-foreground/25 font-[IBM_Plex_Mono] shrink-0">
                {result.schema}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* 결과 없음 */}
      {isFocused && value.trim().length > 0 && results.length === 0 && (
        <div className="absolute left-3 right-3 top-full mt-1 bg-white border border-[#E5E5E5] rounded shadow-lg z-50 px-3 py-2">
          <span className="text-[10px] text-foreground/30 font-[IBM_Plex_Mono]">
            결과 없음
          </span>
        </div>
      )}
    </div>
  );
}
