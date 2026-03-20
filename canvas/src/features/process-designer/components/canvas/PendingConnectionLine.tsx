// features/process-designer/components/canvas/PendingConnectionLine.tsx
// 소스 노드 → 마우스 커서까지의 임시 점선 화살표

import { Arrow } from 'react-konva';
import type { CanvasItem, PendingConnection } from '../../types/processDesigner';

interface PendingConnectionLineProps {
 pending: PendingConnection;
 sourceItem: CanvasItem;
}

export function PendingConnectionLine({ pending, sourceItem }: PendingConnectionLineProps) {
 const sx = sourceItem.x + sourceItem.width / 2;
 const sy = sourceItem.y + sourceItem.height / 2;

 return (
 <Arrow
 points={[sx, sy, pending.mousePos.x, pending.mousePos.y]}
 stroke="#94a3b8"
 strokeWidth={2}
 fill="#94a3b8"
 pointerLength={8}
 pointerWidth={8}
 dash={[8, 4]}
 opacity={0.7}
 listening={false}
 />
 );
}
