/**
 * InstanceTable — 인스턴스 데이터 테이블
 *
 * 선택된 ObjectType의 인스턴스를 동적 컬럼 테이블로 표시한다.
 * KAIR ObjectExplorerTab의 인스턴스 목록 기능에 대응.
 *
 * 주요 기능:
 *  - ObjectType의 fields를 동적 컬럼으로 생성
 *  - 컬럼 헤더 클릭 시 정렬
 *  - 페이지네이션 (20건/페이지)
 *  - 행 클릭 시 인스턴스 선택
 */

import React, { useMemo } from 'react';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import {
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ObjectType, ObjectInstance, InstanceFilter } from '../types/object-explorer';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface InstanceTableProps {
  /** 현재 ObjectType (컬럼 정의용) */
  objectType: ObjectType | null;
  /** 인스턴스 목록 */
  instances: ObjectInstance[];
  /** 전체 건수 */
  total: number;
  /** 현재 필터 */
  filter: InstanceFilter;
  /** 필터 변경 콜백 */
  onFilterChange: (partial: Partial<InstanceFilter>) => void;
  /** 선택된 인스턴스 ID */
  selectedInstanceId: string | null;
  /** 인스턴스 선택 콜백 */
  onSelectInstance: (instance: ObjectInstance) => void;
  /** 로딩 상태 */
  isLoading: boolean;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const InstanceTable: React.FC<InstanceTableProps> = ({
  objectType,
  instances,
  total,
  filter,
  onFilterChange,
  selectedInstanceId,
  onSelectInstance,
  isLoading,
}) => {
  // 동적 컬럼 (ObjectType의 fields에서 가시 필드만)
  const columns = useMemo(() => {
    if (!objectType?.fields) return [];
    return objectType.fields
      .filter((f) => f.isVisible !== false)
      .slice(0, 8); // 최대 8개 컬럼 표시
  }, [objectType]);

  // 페이지 계산
  const totalPages = Math.max(1, Math.ceil(total / filter.pageSize));
  const currentPage = filter.page;

  // 정렬 핸들러 — 컬럼 헤더 클릭
  const handleSort = (columnName: string) => {
    if (filter.sortBy === columnName) {
      // 같은 컬럼 클릭 → 순서 토글
      onFilterChange({ sortOrder: filter.sortOrder === 'asc' ? 'desc' : 'asc' });
    } else {
      // 새 컬럼 선택 → 오름차순 시작
      onFilterChange({ sortBy: columnName, sortOrder: 'asc' });
    }
  };

  // 페이지 이동
  const goToPage = (page: number) => {
    const safePage = Math.max(1, Math.min(page, totalPages));
    onFilterChange({ page: safePage });
  };

  // 셀 값 포매팅
  const formatCellValue = (value: unknown): string => {
    if (value == null) return '-';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  // 빈 상태 (ObjectType 미선택)
  if (!objectType) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        좌측에서 Object Type을 선택하세요
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 테이블 헤더 정보 */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
        <span className="text-xs font-medium text-foreground">
          {objectType.displayName || objectType.name}
          <span className="text-muted-foreground ml-2">({total}건)</span>
        </span>
      </div>

      {/* 테이블 본문 */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground text-xs gap-2">
            <div className="h-5 w-5 border-2 border-muted-foreground/30 border-t-primary rounded-full animate-spin" />
            <span>데이터 로딩 중...</span>
          </div>
        ) : instances.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-muted-foreground text-xs">
            인스턴스가 없습니다
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                {/* 항상 표시되는 ID 컬럼 */}
                <TableHead
                  className="w-[100px] cursor-pointer select-none text-xs"
                  onClick={() => handleSort('id')}
                >
                  <span className="flex items-center gap-1">
                    ID
                    {filter.sortBy === 'id' &&
                      (filter.sortOrder === 'asc' ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      ))}
                  </span>
                </TableHead>

                {/* 표시명 컬럼 */}
                <TableHead
                  className="cursor-pointer select-none text-xs"
                  onClick={() => handleSort('displayName')}
                >
                  <span className="flex items-center gap-1">
                    이름
                    {filter.sortBy === 'displayName' &&
                      (filter.sortOrder === 'asc' ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      ))}
                  </span>
                </TableHead>

                {/* 동적 필드 컬럼 */}
                {columns.map((col) => (
                  <TableHead
                    key={col.id}
                    className="cursor-pointer select-none text-xs"
                    onClick={() => handleSort(col.name)}
                  >
                    <span className="flex items-center gap-1">
                      {col.displayName || col.name}
                      {filter.sortBy === col.name &&
                        (filter.sortOrder === 'asc' ? (
                          <ArrowUp className="h-3 w-3" />
                        ) : (
                          <ArrowDown className="h-3 w-3" />
                        ))}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>

            <TableBody>
              {instances.map((inst) => (
                <TableRow
                  key={inst.id}
                  className={cn(
                    'cursor-pointer transition-colors',
                    selectedInstanceId === inst.id && 'bg-primary/5',
                  )}
                  onClick={() => onSelectInstance(inst)}
                >
                  {/* ID */}
                  <TableCell className="text-xs font-mono text-muted-foreground">
                    {inst.id.length > 8 ? `${inst.id.slice(0, 8)}...` : inst.id}
                  </TableCell>

                  {/* 표시명 */}
                  <TableCell className="text-xs font-medium">
                    {inst.displayName}
                  </TableCell>

                  {/* 동적 필드 */}
                  {columns.map((col) => (
                    <TableCell key={col.id} className="text-xs text-muted-foreground">
                      {formatCellValue(inst.fields[col.name])}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </div>

      {/* 페이지네이션 */}
      {total > 0 && (
        <div className="flex items-center justify-between px-4 py-2 border-t border-border bg-muted/30">
          <span className="text-[11px] text-muted-foreground">
            {(currentPage - 1) * filter.pageSize + 1}–
            {Math.min(currentPage * filter.pageSize, total)} / {total}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={currentPage <= 1}
              onClick={() => goToPage(1)}
              title="첫 페이지"
            >
              <ChevronsLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={currentPage <= 1}
              onClick={() => goToPage(currentPage - 1)}
              title="이전 페이지"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <span className="text-xs text-muted-foreground px-2">
              {currentPage} / {totalPages}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={currentPage >= totalPages}
              onClick={() => goToPage(currentPage + 1)}
              title="다음 페이지"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              disabled={currentPage >= totalPages}
              onClick={() => goToPage(totalPages)}
              title="마지막 페이지"
            >
              <ChevronsRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
