// @ts-nocheck
// features/process-designer/components/canvas/CanvasNode.tsx
// 일반 노드 (contextBox 제외 10종) — react-konva 렌더링 (설계 §2.3, §10.2 포커스 링)

import { Group, Rect, Text } from 'react-konva';
import type { CanvasItem } from '../../types/processDesigner';
import { NODE_CONFIGS } from '../../utils/nodeConfig';

interface CanvasNodeProps {
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

export function CanvasNode({
 item,
 selected,
 focused = false,
 readOnly = false,
 onSelect,
 onDragEnd,
 onDblClick,
}: CanvasNodeProps) {
 const config = NODE_CONFIGS[item.type];
 const typeLabel = config.label;

 // 테두리 색상: 포커스(파란 점선) > 선택(흰색 실선) > 없음
 const strokeColor = focused ? '#3b82f6' : selected ? '#ffffff' : 'transparent';
 const strokeDash = focused && !selected ? [4, 3] : undefined;

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
 {/* 포커스 링 (선택 테두리 뒤에 — 포커스 전용) */}
 {focused && (
 <Rect
 x={-3}
 y={-3}
 width={item.width + 6}
 height={item.height + 6}
 stroke="#3b82f6"
 strokeWidth={2}
 cornerRadius={8}
 dash={[4, 3]}
 listening={false}
 />
 )}

 {/* 노드 본체 */}
 <Rect
 width={item.width}
 height={item.height}
 fill={item.color}
 cornerRadius={6}
 shadowColor="black"
 shadowBlur={selected ? 12 : 3}
 shadowOpacity={selected ? 0.5 : 0.2}
 stroke={selected ? '#ffffff' : 'transparent'}
 strokeWidth={2}
 />

 {/* 타입 라벨 (상단) */}
 <Text
 x={0}
 y={6}
 width={item.width}
 text={typeLabel}
 fontSize={9}
 fill="rgba(0,0,0,0.45)"
 align="center"
 fontStyle="bold"
 letterSpacing={0.5}
 />

 {/* 인스턴스 라벨 (중앙) */}
 <Text
 x={0}
 y={0}
 width={item.width}
 height={item.height}
 text={item.label}
 fontSize={13}
 fill="#1a1a1a"
 align="center"
 verticalAlign="middle"
 fontStyle="bold"
 padding={10}
 />
 </Group>
 );
}
