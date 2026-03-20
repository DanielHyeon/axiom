/**
 * ObjectTypeList — 좌측 사이드바 ObjectType 목록
 *
 * 검색, 생성 버튼, 클릭 선택 지원.
 * KAIR ObjectTypeModeler.vue 좌측 패널을 React + Tailwind로 재구현.
 */

import React, { useMemo } from 'react';
import {
  Database,
  Plus,
  Search,
  RefreshCw,
  Pencil,
  Trash2,
  Zap,
  MoreVertical,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ObjectType } from '../types/domain';
import { useDomainStore } from '../store/useDomainStore';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface ObjectTypeListProps {
  /** ObjectType 목록 */
  objectTypes: ObjectType[];
  /** 로딩 상태 */
  isLoading: boolean;
  /** 새로고침 콜백 */
  onRefresh: () => void;
  /** 삭제 콜백 */
  onDelete: (ot: ObjectType) => void;
}

// ──────────────────────────────────────
// 상태 색상 매핑
// ──────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  draft: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  deprecated: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
};

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const ObjectTypeList: React.FC<ObjectTypeListProps> = ({
  objectTypes,
  isLoading,
  onRefresh,
  onDelete,
}) => {
  const {
    selectedObjectTypeId,
    selectObjectType,
    searchQuery,
    setSearchQuery,
    openCreateDialog,
    startEditing,
    openBehaviorEditor,
  } = useDomainStore();

  // 검색 필터링
  const filtered = useMemo(() => {
    if (!searchQuery) return objectTypes;
    const q = searchQuery.toLowerCase();
    return objectTypes.filter(
      (ot) =>
        ot.name.toLowerCase().includes(q) ||
        ot.displayName.toLowerCase().includes(q) ||
        ot.description?.toLowerCase().includes(q),
    );
  }, [objectTypes, searchQuery]);

  return (
    <aside className="w-72 min-w-[260px] flex flex-col border-r border-border bg-card">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Database className="h-4 w-4 text-primary" />
          ObjectTypes
        </h2>
        <Button
          size="icon"
          variant="default"
          className="h-7 w-7"
          onClick={openCreateDialog}
          title="새 ObjectType 생성"
        >
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* 검색 */}
      <div className="px-3 py-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="ObjectType 검색..."
            className="pl-8 h-8 text-sm"
          />
        </div>
      </div>

      {/* 목록 (스크롤 영역) */}
      <div className="flex-1 overflow-y-auto px-2">
        {isLoading ? (
          <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin mr-2" />
            로딩 중...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground gap-3">
            <p>ObjectType이 없습니다</p>
            <Button size="sm" variant="secondary" onClick={openCreateDialog}>
              <Plus className="h-3.5 w-3.5 mr-1" />
              첫 ObjectType 생성
            </Button>
          </div>
        ) : (
          <div className="space-y-1 py-1">
            {filtered.map((ot) => (
              <ObjectTypeItem
                key={ot.id}
                objectType={ot}
                isSelected={selectedObjectTypeId === ot.id}
                onSelect={() => selectObjectType(ot.id)}
                onEdit={() => startEditing(ot)}
                onDelete={() => onDelete(ot)}
                onAddBehavior={() => openBehaviorEditor(ot.id, null, 'create')}
              />
            ))}
          </div>
        )}
      </div>

      {/* 하단 새로고침 */}
      <div className="px-3 py-2 border-t border-border">
        <Button
          variant="outline"
          size="sm"
          className="w-full text-xs"
          onClick={onRefresh}
          disabled={isLoading}
        >
          <RefreshCw className={cn('h-3 w-3 mr-1.5', isLoading && 'animate-spin')} />
          새로고침
        </Button>
      </div>
    </aside>
  );
};

// ──────────────────────────────────────
// 개별 아이템
// ──────────────────────────────────────

interface ObjectTypeItemProps {
  objectType: ObjectType;
  isSelected: boolean;
  onSelect: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onAddBehavior: () => void;
}

const ObjectTypeItem: React.FC<ObjectTypeItemProps> = ({
  objectType,
  isSelected,
  onSelect,
  onEdit,
  onDelete,
  onAddBehavior,
}) => {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
      className={cn(
        'flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-colors group',
        isSelected
          ? 'bg-primary/10 border border-primary/30'
          : 'hover:bg-muted/50 border border-transparent',
      )}
    >
      {/* 아이콘 */}
      <div className="flex items-center justify-center w-8 h-8 rounded-md bg-primary/10 text-primary shrink-0">
        <Database className="h-4 w-4" />
      </div>

      {/* 이름 + 메타 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-foreground truncate">
            {objectType.displayName || objectType.name}
          </span>
          <Badge variant="outline" className={cn('text-[10px] h-4 px-1', STATUS_COLORS[objectType.status])}>
            {objectType.status}
          </Badge>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
          <span>{objectType.fields.length} 필드</span>
          {objectType.behaviors.length > 0 && (
            <span className="flex items-center gap-0.5 text-violet-400">
              <Zap className="h-3 w-3" />
              {objectType.behaviors.length}
            </span>
          )}
        </div>
      </div>

      {/* 액션 버튼 (호버 시 표시) */}
      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          type="button"
          className="p-1 rounded hover:bg-primary/10 text-muted-foreground hover:text-primary"
          onClick={(e) => { e.stopPropagation(); onEdit(); }}
          title="편집"
        >
          <Pencil className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          className="p-1 rounded hover:bg-violet-500/10 text-muted-foreground hover:text-violet-400"
          onClick={(e) => { e.stopPropagation(); onAddBehavior(); }}
          title="Behavior 추가"
        >
          <Zap className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
          onClick={(e) => { e.stopPropagation(); onDelete(); }}
          title="삭제"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
};
