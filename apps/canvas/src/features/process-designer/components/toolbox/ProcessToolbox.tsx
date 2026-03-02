// features/process-designer/components/toolbox/ProcessToolbox.tsx
// 11종 노드 팔레트 — 드래그 앤 드롭으로 캔버스에 배치 (설계 §1, §2.1)

import { BASIC_NODE_TYPES, EXTENDED_NODE_TYPES } from '../../utils/nodeConfig';
import type { CanvasItemType } from '../../types/processDesigner';

interface ProcessToolboxProps {
 disabled?: boolean;
}

export function ProcessToolbox({ disabled = false }: ProcessToolboxProps) {
 const handleDragStart = (e: React.DragEvent, type: CanvasItemType) => {
 if (disabled) return;
 e.dataTransfer.setData('nodeType', type);
 e.dataTransfer.effectAllowed = 'copy';
 };

 return (
 <div className="flex flex-col h-full">
 {/* Basic nodes (8종) */}
 <div className="px-3 pt-3 pb-1">
 <span className="text-[10px] font-semibold uppercase tracking-wider text-foreground0">
 Basic
 </span>
 </div>
 <div className="px-3 space-y-1.5">
 {BASIC_NODE_TYPES.map((cfg) => (
 <div
 key={cfg.type}
 draggable={!disabled}
 onDragStart={(e) => handleDragStart(e, cfg.type)}
 className={`
 flex items-center gap-2 px-3 py-2 rounded text-sm font-medium
 shadow-sm transition-shadow
 ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-grab active:cursor-grabbing hover:shadow-md'}
 `}
 style={{ backgroundColor: cfg.color, color: '#1a1a1a' }}
 >
 <span className="flex-1 truncate">{cfg.label}</span>
 {cfg.shortcut && (
 <kbd className="text-[10px] px-1 py-0.5 rounded bg-sidebar/10 font-mono leading-none">
 {cfg.shortcut}
 </kbd>
 )}
 </div>
 ))}
 </div>

 {/* Separator */}
 <div className="mx-3 my-2 border-t border-border" />

 {/* Extended nodes (3종) */}
 <div className="px-3 pb-1">
 <span className="text-[10px] font-semibold uppercase tracking-wider text-foreground0">
 Extended
 </span>
 </div>
 <div className="px-3 space-y-1.5 pb-3">
 {EXTENDED_NODE_TYPES.map((cfg) => (
 <div
 key={cfg.type}
 draggable={!disabled}
 onDragStart={(e) => handleDragStart(e, cfg.type)}
 className={`
 flex items-center gap-2 px-3 py-2 rounded text-sm font-medium
 shadow-sm transition-shadow
 ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-grab active:cursor-grabbing hover:shadow-md'}
 `}
 style={{ backgroundColor: cfg.color, color: '#1a1a1a' }}
 >
 <span className="flex-1 truncate">{cfg.label}</span>
 </div>
 ))}
 </div>
 </div>
 );
}
