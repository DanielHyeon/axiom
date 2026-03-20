/**
 * InstanceSearch — 인스턴스 검색 컴포넌트
 *
 * ObjectType 내부 또는 전체 범위에서 인스턴스를 검색한다.
 * 검색어 입력 + 정렬 설정 UI를 제공.
 */

import React from 'react';
import { Search, ArrowUpDown } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { InstanceFilter } from '../types/object-explorer';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface InstanceSearchProps {
  /** 현재 필터 상태 */
  filter: InstanceFilter;
  /** 필터 변경 콜백 */
  onFilterChange: (partial: Partial<InstanceFilter>) => void;
  /** 검색 실행 콜백 (Enter 키 또는 버튼 클릭) */
  onSearch: () => void;
  /** 선택된 ObjectType 이름 (표시용) */
  objectTypeName?: string;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const InstanceSearch: React.FC<InstanceSearchProps> = ({
  filter,
  onFilterChange,
  onSearch,
  objectTypeName,
}) => {
  // Enter 키 핸들러
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      onSearch();
    }
  };

  // 정렬 순서 토글
  const toggleSortOrder = () => {
    onFilterChange({
      sortOrder: filter.sortOrder === 'asc' ? 'desc' : 'asc',
    });
  };

  return (
    <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-card">
      {/* 검색 입력 */}
      <div className="relative flex-1">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          value={filter.search}
          onChange={(e) => onFilterChange({ search: e.target.value, page: 1 })}
          onKeyDown={handleKeyDown}
          placeholder={
            objectTypeName
              ? `${objectTypeName} 인스턴스 검색...`
              : '인스턴스 검색...'
          }
          className="h-8 pl-8 text-xs"
        />
      </div>

      {/* 정렬 토글 */}
      <Button
        variant="outline"
        size="icon"
        className="h-8 w-8 shrink-0"
        onClick={toggleSortOrder}
        title={`정렬: ${filter.sortOrder === 'asc' ? '오름차순' : '내림차순'}`}
      >
        <ArrowUpDown className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
};
