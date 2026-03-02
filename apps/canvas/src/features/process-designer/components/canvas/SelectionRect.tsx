// features/process-designer/components/canvas/SelectionRect.tsx
// 드래그 선택 영역 (rubber band) — 설계 §2.5

import { Rect } from 'react-konva';

export interface SelectionRectData {
 x: number;
 y: number;
 width: number;
 height: number;
}

interface SelectionRectProps {
 rect: SelectionRectData | null;
}

export function SelectionRect({ rect }: SelectionRectProps) {
 if (!rect) return null;

 return (
 <Rect
 x={rect.x}
 y={rect.y}
 width={rect.width}
 height={rect.height}
 fill="rgba(59, 130, 246, 0.08)"
 stroke="#3b82f6"
 strokeWidth={1}
 dash={[4, 4]}
 listening={false}
 />
 );
}
