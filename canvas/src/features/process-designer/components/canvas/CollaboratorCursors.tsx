// features/process-designer/components/canvas/CollaboratorCursors.tsx
// 다른 사용자의 커서 위치 + 이름 태그를 캔버스 위에 표시 (설계 §6.2)

import { Group, Line, Rect, Text } from 'react-konva';
import type { Collaborator } from '../../store/canvasDataStore';

interface CollaboratorCursorsProps {
 collaborators: Collaborator[];
}

/**
 * 각 협업자의 커서를 삼각형 포인터 + 이름 태그로 렌더링.
 * cursor가 null인 사용자(아직 마우스를 움직이지 않은)는 표시하지 않음.
 */
export function CollaboratorCursors({ collaborators }: CollaboratorCursorsProps) {
 return (
 <>
 {collaborators.map((c) => {
 if (!c.cursor) return null;
 const { x, y } = c.cursor;

 return (
 <Group key={c.clientId} x={x} y={y} listening={false}>
 {/* 삼각형 커서 포인터 */}
 <Line
 points={[0, 0, 0, 14, 10, 10]}
 fill={c.color}
 stroke="#000"
 strokeWidth={0.5}
 closed
 />
 {/* 이름 태그 배경 */}
 <Rect
 x={12}
 y={10}
 width={Math.max(c.name.length * 7 + 8, 30)}
 height={18}
 fill={c.color}
 cornerRadius={3}
 />
 {/* 이름 텍스트 */}
 <Text
 x={16}
 y={12}
 text={c.name}
 fontSize={11}
 fontFamily="system-ui, sans-serif"
 fill="#fff"
 />
 </Group>
 );
 })}
 </>
 );
}
