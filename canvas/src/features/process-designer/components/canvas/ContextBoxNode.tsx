// features/process-designer/components/canvas/ContextBoxNode.tsx
// contextBox (Business Domain 영역) 전용 — 큰 영역 + 상단 라벨 (설계 §2.1, §10.2 포커스 링)

import { Group, Rect, Text } from 'react-konva';
import type { CanvasItem } from '../../types/processDesigner';

interface ContextBoxNodeProps {
 item: CanvasItem;
 selected: boolean;
 /** 접근성 포커스 상태 (Tab 탐색 — 선택과 별도) */
 focused?: boolean;
 /** 읽기 전용 모드 — 드래그 불가 */
 readOnly?: boolean;
 onSelect: (id: string, multi: boolean) => void;
 onDragEnd: (id: string, x: number, y: number) => void;
 onDblClick?: (id: string) => void;
}

export function ContextBoxNode({
 item,
 selected,
 focused = false,
 readOnly = false,
 onSelect,
 onDragEnd,
 onDblClick,
}: ContextBoxNodeProps) {
 return (
 <Group
 x={item.x}
 y={item.y}
 draggable={!readOnly}
 onClick={(e) => {
 e.cancelBubble = true;
 onSelect(item.id, e.evt.shiftKey || e.evt.metaKey);
 }}
 onDblClick={() => onDblClick?.(item.id)}
 onDragEnd={(e) => {
 onDragEnd(item.id, e.target.x(), e.target.y());
 }}
 >
 {/* 포커스 링 (§10.2) */}
 {focused && (
 <Rect
 x={-3}
 y={-3}
 width={item.width + 6}
 height={item.height + 6}
 stroke="#3b82f6"
 strokeWidth={2}
 cornerRadius={12}
 dash={[4, 3]}
 listening={false}
 />
 )}

 {/* 영역 배경 */}
 <Rect
 width={item.width}
 height={item.height}
 fill={item.color}
 opacity={0.35}
 cornerRadius={10}
 stroke={selected ? '#ffffff' : 'rgba(255,255,255,0.15)'}
 strokeWidth={selected ? 2 : 1}
 dash={selected ? undefined : [8, 4]}
 />

 {/* 상단 라벨 배경 */}
 <Rect
 x={0}
 y={0}
 width={item.width}
 height={28}
 fill={item.color}
 opacity={0.5}
 cornerRadius={[10, 10, 0, 0]}
 />

 {/* 라벨 텍스트 */}
 <Text
 x={12}
 y={6}
 text={item.label || 'Domain'}
 fontSize={12}
 fill="#1a1a1a"
 fontStyle="bold"
 />
 </Group>
 );
}
