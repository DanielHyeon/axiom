/**
 * DroppableZone — 피벗 영역의 드롭 존 (ROWS / COLUMNS / VALUES)
 *
 * .pen 디자인 사양:
 * - 3개 동일 너비 컬럼, 60px 높이, surface bg (#F5F5F5), 8px radius
 * - 대시 border (#E5E5E5)
 * - 존 라벨: Geist 10px semibold #5E5E5E (uppercase)
 * - ROWS/COLUMNS 존 칩: 파란색(#3B82F6) bg, 24px 높이, 4px radius, 흰색 텍스트
 * - VALUES 존 칩: 녹색(#22C55E) bg, 24px 높이, 4px radius, 흰색 텍스트
 */
import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Dimension, Measure } from '@/features/olap/types/olap';
import { X } from 'lucide-react';

interface DroppableZoneProps {
  /** 존 ID (rows/columns/measures) */
  id: 'rows' | 'columns' | 'measures';
  /** 존 라벨 (ROWS, COLUMNS, VALUES) */
  title: string;
  items: (Dimension | Measure)[];
  onRemove: (id: string) => void;
}

export function DroppableZone({ id, title, items, onRemove }: DroppableZoneProps) {
  const { isOver, setNodeRef } = useDroppable({
    id,
    data: { accepts: id === 'measures' ? 'measure' : 'dimension' },
  });

  // VALUES 존은 녹색, 나머지는 파란색
  const isValueZone = id === 'measures';

  return (
    <div
      ref={setNodeRef}
      className={[
        // 기본 스타일: 60px 높이, surface bg, 8px radius, dashed border
        'flex flex-col gap-1 rounded-lg p-2 px-3 min-h-[60px] w-full',
        'border border-dashed transition-colors',
        isOver
          ? 'bg-blue-50 border-blue-300'
          : 'bg-muted border-border',
      ].join(' ')}
    >
      {/* 존 라벨 */}
      <span className="text-[10px] font-semibold text-text-secondary uppercase tracking-wide">
        {title}
      </span>

      {/* 칩 목록 */}
      <SortableContext
        items={items.map((i) => `${id}-${i.id}`)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex flex-wrap gap-1.5">
          {items.map((item) => (
            <SortablePill
              key={`${id}-${item.id}`}
              id={`${id}-${item.id}`}
              item={item}
              isGreen={isValueZone}
              onRemove={() => onRemove(item.id)}
            />
          ))}
        </div>
      </SortableContext>

      {/* 빈 상태 안내 */}
      {items.length === 0 && (
        <span className="text-[10px] text-text-placeholder italic">
          여기에 항목을 드롭하세요
        </span>
      )}
    </div>
  );
}

/** 존 안의 정렬 가능한 칩 */
function SortablePill({
  id,
  item,
  isGreen,
  onRemove,
}: {
  id: string;
  item: Dimension | Measure;
  isGreen: boolean;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  // 색상: VALUES 존은 녹색, ROWS/COLUMNS 존은 파란색
  const bgClass = isGreen ? 'bg-accent-green' : 'bg-accent-blue';

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={[
        bgClass,
        // 24px 높이, 4px radius, 8px 좌우 패딩, gap 4px
        'flex items-center h-6 px-2 gap-1 rounded',
      ].join(' ')}
    >
      {/* 라벨 — 흰색 Geist 11px */}
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-[11px] text-white font-medium"
      >
        {item.name}
      </div>
      {/* 삭제 버튼 */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="p-0.5 rounded-sm hover:bg-white/20 transition-colors"
        aria-label={`${item.name} 제거`}
      >
        <X size={10} className="text-white" />
      </button>
    </div>
  );
}
