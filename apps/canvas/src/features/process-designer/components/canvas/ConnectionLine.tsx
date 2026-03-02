// features/process-designer/components/canvas/ConnectionLine.tsx
// 연결선 렌더링 — 4종 스타일 (설계 §3)

import { Arrow } from 'react-konva';
import type { Connection, CanvasItem } from '../../types/processDesigner';
import { computeEdgePoints } from '../../utils/edgePoints';

interface ConnectionLineProps {
 connection: Connection;
 sourceItem: CanvasItem;
 targetItem: CanvasItem;
 selected: boolean;
 onClick: (connId: string) => void;
}

export function ConnectionLine({ connection, sourceItem, targetItem, selected, onClick }: ConnectionLineProps) {
 const [sx, sy, tx, ty] = computeEdgePoints(sourceItem, targetItem);

 const { style } = connection;
 const stroke = selected ? '#3b82f6' : style.stroke;
 const strokeWidth = selected ? style.strokeWidth + 1.5 : style.strokeWidth;

 return (
 <Arrow
 points={[sx, sy, tx, ty]}
 stroke={stroke}
 strokeWidth={strokeWidth}
 fill={stroke}
 pointerLength={style.arrowSize}
 pointerWidth={style.arrowSize}
 dash={style.dashArray ? style.dashArray.split(',').map(Number) : undefined}
 hitStrokeWidth={12}
 onClick={(e) => {
 e.cancelBubble = true;
 onClick(connection.id);
 }}
 />
 );
}
