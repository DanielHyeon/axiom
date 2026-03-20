/**
 * LineageSearchBar — 테이블/컬럼 검색으로 리니지 탐색 시작점 지정
 * 디바운스된 검색 + 드롭다운 결과 목록
 */

import { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';
import { useLineageSearch } from '../hooks/useLineage';
import { useLineageStore } from '../store/useLineageStore';
import { LINEAGE_NODE_STYLES, type LineageSearchResult } from '../types/lineage';

interface LineageSearchBarProps {
  /** 검색 결과 노드 선택 시 호출 — 해당 노드 기준 그래프 로드 */
  onNodeSelect?: (nodeId: string) => void;
}

export function LineageSearchBar({ onNodeSelect }: LineageSearchBarProps) {
  const { setSearchQuery: setStoreQuery } = useLineageStore();

  const [query, setQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // 디바운스 — 300ms
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 300);
    return () => clearTimeout(timer);
  }, [query]);

  // TanStack Query 검색
  const { data: results = [], isLoading } = useLineageSearch(debouncedQuery);

  // 외부 클릭 시 드롭다운 닫기
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // 결과 항목 클릭
  function handleSelect(item: LineageSearchResult) {
    setQuery(item.name);
    setIsOpen(false);
    setStoreQuery(item.name);
    onNodeSelect?.(item.id);
  }

  // 검색어 초기화
  function handleClear() {
    setQuery('');
    setDebouncedQuery('');
    setStoreQuery('');
    setIsOpen(false);
  }

  return (
    <div ref={wrapperRef} className="relative w-full max-w-xs">
      {/* 검색 입력 */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => query.length >= 2 && setIsOpen(true)}
          placeholder="테이블/컬럼 검색..."
          className="w-full rounded-lg border border-border bg-muted/50 py-2 pl-8 pr-8 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-colors"
          aria-label="리니지 노드 검색"
          aria-expanded={isOpen}
          role="combobox"
          aria-autocomplete="list"
        />
        {query && (
          <button
            onClick={handleClear}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="검색어 지우기"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* 검색 결과 드롭다운 */}
      {isOpen && debouncedQuery.length >= 2 && (
        <div
          className="absolute top-full left-0 z-50 mt-1 w-full max-h-60 overflow-y-auto rounded-lg border border-border bg-card shadow-lg"
          role="listbox"
        >
          {isLoading && (
            <div className="px-3 py-4 text-center text-sm text-muted-foreground">
              검색 중...
            </div>
          )}

          {!isLoading && results.length === 0 && (
            <div className="px-3 py-4 text-center text-sm text-muted-foreground">
              결과 없음
            </div>
          )}

          {!isLoading &&
            results.map((item) => {
              const nodeStyle = LINEAGE_NODE_STYLES[item.type];
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item)}
                  className="flex w-full items-center gap-2.5 px-3 py-2 text-left hover:bg-muted/60 transition-colors"
                  role="option"
                  aria-selected={false}
                >
                  {/* 타입 컬러 도트 */}
                  <span
                    className="h-2.5 w-2.5 rounded-sm shrink-0"
                    style={{ background: nodeStyle.color }}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {item.name}
                    </p>
                    {item.schema && (
                      <p className="truncate text-[10px] text-muted-foreground">
                        {item.schema}
                        {item.datasource ? ` / ${item.datasource}` : ''}
                      </p>
                    )}
                  </div>
                  {/* 타입 뱃지 */}
                  <span
                    className="shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase text-white"
                    style={{ background: nodeStyle.color }}
                  >
                    {nodeStyle.label}
                  </span>
                </button>
              );
            })}
        </div>
      )}
    </div>
  );
}
