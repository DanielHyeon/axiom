/**
 * DraggableItem — 팔레트에서 드래그 가능한 차원/측정값 칩
 *
 * .pen 디자인 사양:
 * - 32px 높이, 흰색 bg, 6px radius, 1px border #E5E5E5
 * - 차원: 파란색(#3B82F6) lucide 아이콘 12px + 텍스트 Geist 12px
 * - 측정값: 녹색(#22C55E) hash 아이콘 12px + 텍스트 Geist 12px
 * - 좌우 padding 10px, gap 6px
 */
import { useDraggable } from '@dnd-kit/core';
import { Calendar, MapPin, Box, Hash } from 'lucide-react';
import type { Dimension, Measure } from '@/features/olap/types/olap';

interface DraggableItemProps {
  item: Dimension | Measure;
  type: 'dimension' | 'measure';
  disabled?: boolean;
}

/** 차원 이름으로 적절한 아이콘 선택 */
function DimensionIcon({ name }: { name: string }) {
  const lower = name.toLowerCase();
  const cls = 'text-accent-blue shrink-0';
  if (lower.includes('time') || lower.includes('date') || lower.includes('period') || lower.includes('quarter') || lower.includes('year') || lower.includes('month')) {
    return <Calendar size={12} className={cls} />;
  }
  if (lower.includes('region') || lower.includes('location') || lower.includes('geo') || lower.includes('country') || lower.includes('city')) {
    return <MapPin size={12} className={cls} />;
  }
  return <Box size={12} className={cls} />;
}

export function DraggableItem({ item, type, disabled }: DraggableItemProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `${type}-${item.id}`,
    data: { item, type },
    disabled,
  });

  // 비활성 상태면 숨김
  if (disabled) return null;

  const isMeasure = type === 'measure';

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      className={[
        // 기본: 32px 높이, 흰색 bg, 6px radius, 1px border
        'flex items-center h-8 px-2.5 gap-1.5 rounded-[6px] bg-card border border-border',
        // 커서 & 드래그 상태
        'cursor-grab active:cursor-grabbing select-none transition-shadow',
        isDragging ? 'opacity-50 shadow-md' : 'hover:shadow-sm',
      ].join(' ')}
    >
      {/* 아이콘 — 차원은 컨텍스트별, 측정값은 hash */}
      {isMeasure ? (
        <Hash size={12} className="text-accent-green shrink-0" />
      ) : (
        <DimensionIcon name={item.name} />
      )}
      {/* 텍스트 — Geist 12px */}
      <span className="text-xs text-foreground truncate">{item.name}</span>
    </div>
  );
}
