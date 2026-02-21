// src/pages/olap/components/DraggableItem.tsx

import { useDraggable } from '@dnd-kit/core';
import type { Dimension, Measure } from '@/features/olap/types/olap';

interface DraggableItemProps {
  item: Dimension | Measure;
  type: 'dimension' | 'measure';
  disabled?: boolean;
}

export function DraggableItem({ item, type, disabled }: DraggableItemProps) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `${type}-${item.id}`,
    data: { item, type },
    disabled
  });

  const baseStyle = "px-3 py-1.5 text-sm rounded-md border flex items-center justify-between transition-colors shadow-sm select-none cursor-grab active:cursor-grabbing";
  const typeStyle = type === 'dimension'
    ? "bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800"
    : "bg-indigo-950/50 border-indigo-900 text-indigo-300 hover:bg-indigo-900/50";

  const stateStyle = disabled
    ? "opacity-40 cursor-not-allowed hidden" // hide disabled items in palette
    : isDragging ? "opacity-50 ring-2 ring-indigo-500" : "";

  if (disabled) return null; // We can choose to hide or gray out. Hiding is cleaner for palettes.

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
    >
      <div className={`${baseStyle} ${typeStyle} ${stateStyle} mb-2`}>
        <span className="text-xs text-neutral-500">{type === 'dimension' ? 'A' : '#'}</span>
        <span className="font-medium">{item.name}</span>
      </div>
      <span className="text-neutral-600 text-[10px] uppercase">
        {'aggregation' in item ? item.aggregation : item.type}
      </span>
    </div>
  );
}
