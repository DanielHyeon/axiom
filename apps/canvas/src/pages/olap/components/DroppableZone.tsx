// src/pages/olap/components/DroppableZone.tsx

import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Dimension, Measure } from '@/features/olap/types/olap';
import { X } from 'lucide-react';

interface DroppableZoneProps {
  id: 'rows' | 'columns' | 'measures' | 'filters';
  title: string;
  items: (Dimension | Measure)[];
  accepts: 'dimension' | 'measure' | 'both';
  onRemove: (id: string) => void;
}

export function DroppableZone({ id, title, items, accepts, onRemove }: DroppableZoneProps) {
  const { isOver, setNodeRef } = useDroppable({
    id,
    data: { accepts }
  });

  return (
    <div className="flex items-start mb-3">
      <div className="w-24 pt-2 text-xs font-medium text-neutral-400 shrink-0">
        {title}
      </div>
      <div
        ref={setNodeRef}
        className={`${isOver ? 'bg-indigo-950/20 border-indigo-500/50' : 'bg-neutral-900 border-neutral-800'} flex-1 min-h-[42px] border rounded-md p-1.5 flex flex-wrap gap-2 transition-colors`}
      >
        <SortableContext
          items={items.map(i => `${id}-${i.id}`)}
          strategy={verticalListSortingStrategy}
        >
          {items.map((item) => (
            <SortablePill
              key={`${id}-${item.id}`}
              id={`${id}-${item.id}`}
              item={item}
              onRemove={() => onRemove(item.id)}
            />
          ))}
          {items.length === 0 && (
            <div className="text-xs text-neutral-500 flex items-center pl-2 h-[28px] italic w-full">
              여기에 항목을 드롭하세요
            </div>
          )}
        </SortableContext>
      </div >
    </div >
  );
}

function SortablePill({ id, item, onRemove }: { id: string, item: Dimension | Measure, onRemove: () => void }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const isMeasure = 'aggregation' in item;
  const bgClass = isMeasure ? 'bg-indigo-600 border-indigo-500' : 'bg-neutral-700 border-neutral-600';

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`${bgClass} flex items-center h-[28px] pl-2.5 pr-1 rounded text-xs text-white border`}
    >
      <div {...attributes} {...listeners} className="cursor-grab active:cursor-grabbing font-medium pr-2">
        {item.name}
      </div>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(); }}
        className="p-1 hover:bg-black/20 rounded-sm transition-colors"
      >
        <X size={12} />
      </button>
    </div>
  );
}
