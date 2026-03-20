/**
 * InstanceDetail — 인스턴스 상세 패널
 *
 * 선택된 인스턴스의 속성, 관계, Object Type 정보를 표시한다.
 * KAIR ObjectDetailPanel.vue에 대응하는 React 컴포넌트.
 *
 * 주요 기능:
 *  - 인스턴스 속성 key-value 테이블
 *  - 관련 인스턴스 목록
 *  - Object Type 메타 정보
 */

import React, { useMemo, useState } from 'react';
import { X, ChevronDown, Link2, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ObjectInstance, ObjectType } from '../types/object-explorer';

// ──────────────────────────────────────
// 타입별 색상 매핑
// ──────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  Plant: 'bg-green-500',
  ProcessUnit: 'bg-blue-500',
  Equipment: 'bg-amber-500',
  Sensor: 'bg-violet-500',
  Reservoir: 'bg-cyan-500',
  Algorithm: 'bg-pink-500',
  Model: 'bg-red-500',
};

function getTypeColorClass(typeName: string): string {
  return TYPE_COLORS[typeName] || 'bg-zinc-500';
}

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface InstanceDetailProps {
  /** 선택된 인스턴스 */
  instance: ObjectInstance;
  /** 현재 ObjectType */
  objectType: ObjectType | null;
  /** 닫기 콜백 */
  onClose: () => void;
  /** 관련 인스턴스 클릭 콜백 */
  onRelatedClick?: (instanceId: string) => void;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const InstanceDetail: React.FC<InstanceDetailProps> = ({
  instance,
  objectType,
  onClose,
  onRelatedClick,
}) => {
  // 펼침 상태 (긴 값 표시용)
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  // 속성 목록 (id, name 제외)
  const properties = useMemo(() => {
    return Object.entries(instance.fields)
      .filter(([key]) => !['id', 'name', '__typename'].includes(key))
      .map(([key, value]) => ({
        key,
        value:
          typeof value === 'object'
            ? JSON.stringify(value, null, 2)
            : String(value ?? ''),
        isLong: String(value ?? '').length > 50,
      }));
  }, [instance.fields]);

  // 펼침 토글
  const toggleExpand = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-start justify-between p-4 bg-muted/30 border-b border-border">
        <div className="flex flex-col gap-2 min-w-0">
          <Badge className={cn('text-[10px] w-fit', getTypeColorClass(instance.objectTypeName))}>
            {instance.objectTypeName}
          </Badge>
          <h3 className="text-sm font-semibold text-foreground break-words">
            {instance.displayName}
          </h3>
        </div>
        <Button
          variant="outline"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onClose}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* 스크롤 영역 */}
      <div className="flex-1 overflow-y-auto">
        {/* 속성 섹션 */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Info className="h-3 w-3" />
              속성
            </span>
            <span className="text-[11px] text-muted-foreground">
              {properties.length}개
            </span>
          </div>

          {properties.length === 0 ? (
            <div className="text-xs text-muted-foreground text-center py-6">
              속성이 없습니다
            </div>
          ) : (
            <div className="border border-border rounded-lg overflow-hidden divide-y divide-border">
              {properties.map((prop) => (
                <div key={prop.key} className="grid grid-cols-[100px_1fr]">
                  <div className="px-3 py-2 text-[11px] font-medium text-muted-foreground bg-muted/40 border-r border-border">
                    {prop.key}
                  </div>
                  <div className="px-3 py-2">
                    <div
                      className={cn(
                        'text-[11px] font-mono text-primary break-all',
                        !expandedKeys.has(prop.key) && prop.isLong && 'line-clamp-2',
                      )}
                    >
                      {prop.value}
                    </div>
                    {prop.isLong && (
                      <button
                        className="text-[10px] text-primary hover:underline mt-1"
                        onClick={() => toggleExpand(prop.key)}
                      >
                        {expandedKeys.has(prop.key) ? '접기' : '더보기'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 관련 인스턴스 섹션 */}
        {instance.relatedInstances.length > 0 && (
          <div className="p-4 border-t border-border">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                <Link2 className="h-3 w-3" />
                관련 인스턴스
              </span>
              <span className="text-[11px] text-muted-foreground">
                {instance.relatedInstances.length}개
              </span>
            </div>

            <div className="space-y-1.5">
              {instance.relatedInstances.map((rel) => (
                <div
                  key={`${rel.instanceId}-${rel.relationName}`}
                  className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/50 cursor-pointer transition-colors"
                  onClick={() => onRelatedClick?.(rel.instanceId)}
                >
                  <Badge
                    variant="outline"
                    className={cn('text-[9px] shrink-0', getTypeColorClass(rel.objectTypeName))}
                  >
                    {rel.objectTypeName}
                  </Badge>
                  <span className="flex-1 text-xs text-foreground truncate">
                    {rel.displayName}
                  </span>
                  <span className="text-[10px] text-muted-foreground shrink-0">
                    {rel.relationName}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Object Type 정보 */}
        {objectType && (
          <div className="p-4 border-t border-border bg-muted/20">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground block mb-2">
              Object Type 정보
            </span>
            <div className="space-y-1.5 text-xs">
              <div className="flex gap-3">
                <span className="w-14 font-medium text-muted-foreground shrink-0">타입</span>
                <span className="text-foreground">{objectType.name}</span>
              </div>
              {objectType.description && (
                <div className="flex gap-3">
                  <span className="w-14 font-medium text-muted-foreground shrink-0">설명</span>
                  <span className="text-foreground">{objectType.description}</span>
                </div>
              )}
              {objectType.sourceTable && (
                <div className="flex gap-3">
                  <span className="w-14 font-medium text-muted-foreground shrink-0">테이블</span>
                  <span className="text-foreground font-mono text-primary">
                    {objectType.sourceSchema}.{objectType.sourceTable}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
