/**
 * ObjectTypeSelector — ObjectType 선택 사이드바
 *
 * 좌측 패널에서 ObjectType 목록을 표시하고 선택할 수 있게 한다.
 * KAIR ObjectSearchPanel.vue에 대응하는 React 컴포넌트.
 *
 * 주요 기능:
 *  - ObjectType 목록 표시 (필터 지원)
 *  - ObjectType 선택 시 인스턴스 테이블 로딩 트리거
 *  - 각 타입의 필드/설명 펼침 보기
 */

import React, { useState, useMemo } from 'react';
import { Search, RotateCcw, ChevronRight, Package } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ObjectType } from '../types/object-explorer';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface ObjectTypeSelectorProps {
  /** ObjectType 목록 */
  objectTypes: ObjectType[];
  /** 현재 선택된 ObjectType ID */
  selectedId: string | null;
  /** 로딩 상태 */
  isLoading: boolean;
  /** ObjectType 선택 콜백 */
  onSelect: (objectType: ObjectType) => void;
  /** 초기화 콜백 */
  onReset: () => void;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ObjectTypeSelector: React.FC<ObjectTypeSelectorProps> = ({
  objectTypes,
  selectedId,
  isLoading,
  onSelect,
  onReset,
}) => {
  // 필터 텍스트
  const [filterText, setFilterText] = useState('');
  // 펼침 상태
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  // 필터링된 ObjectType 목록
  const filteredTypes = useMemo(() => {
    if (!filterText.trim()) return objectTypes;
    const q = filterText.toLowerCase();
    return objectTypes.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.displayName.toLowerCase().includes(q) ||
        t.description?.toLowerCase().includes(q),
    );
  }, [objectTypes, filterText]);

  // 펼침 토글
  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <Search className="h-4 w-4 text-muted-foreground" />
          오브젝트 탐색기
        </h3>
        <Button
          variant="outline"
          size="icon"
          className="h-7 w-7"
          onClick={onReset}
          title="초기화"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* 필터 입력 */}
      <div className="px-4 pb-3">
        <Input
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          placeholder="Object Type 필터..."
          className="h-8 text-xs"
        />
      </div>

      {/* 목록 헤더 */}
      <div className="flex items-center justify-between px-4 pb-2 border-b border-border">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Object Types
        </span>
        <span className="text-[11px] text-muted-foreground">
          {filteredTypes.length}개
        </span>
      </div>

      {/* 목록 */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {/* 로딩 */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground text-xs gap-2">
            <div className="h-5 w-5 border-2 border-muted-foreground/30 border-t-primary rounded-full animate-spin" />
            <span>로딩 중...</span>
          </div>
        )}

        {/* 빈 상태 */}
        {!isLoading && filteredTypes.length === 0 && (
          <div className="text-center py-8 text-muted-foreground text-xs">
            Object Type이 없습니다
          </div>
        )}

        {/* 타입 아이템 */}
        {!isLoading &&
          filteredTypes.map((type) => (
            <div
              key={type.id}
              className={cn(
                'rounded-lg border cursor-pointer transition-colors',
                selectedId === type.id
                  ? 'border-primary bg-primary/5'
                  : 'border-border hover:border-primary/50 hover:bg-muted/50',
              )}
              onClick={() => onSelect(type)}
            >
              {/* 메인 행 */}
              <div className="flex items-center gap-2 px-3 py-2.5">
                <button
                  className={cn(
                    'flex items-center justify-center h-5 w-5 transition-transform shrink-0',
                    expandedIds.has(type.id) && 'rotate-90',
                  )}
                  onClick={(e) => toggleExpand(type.id, e)}
                >
                  <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
                <Package className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="flex-1 text-xs font-medium text-foreground truncate">
                  {type.displayName || type.name}
                </span>
                {type.materializedViewSql && (
                  <Badge variant="secondary" className="text-[9px] px-1.5 py-0">
                    MV
                  </Badge>
                )}
              </div>

              {/* 펼침 상세 */}
              {expandedIds.has(type.id) && (
                <div className="px-3 pb-3 pt-1 border-t border-border/50">
                  {type.description && (
                    <p className="text-[11px] text-muted-foreground mb-2 leading-relaxed">
                      {type.description}
                    </p>
                  )}
                  <div>
                    <span className="text-[10px] font-semibold text-muted-foreground block mb-1.5">
                      필드 ({type.fields?.length ?? 0})
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {type.fields?.slice(0, 6).map((f) => (
                        <span
                          key={f.id}
                          className="px-1.5 py-0.5 text-[10px] bg-muted rounded text-muted-foreground"
                          title={f.dataType}
                        >
                          {f.name}
                        </span>
                      ))}
                      {(type.fields?.length ?? 0) > 6 && (
                        <span className="px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          +{(type.fields?.length ?? 0) - 6}개
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
      </div>
    </div>
  );
};
