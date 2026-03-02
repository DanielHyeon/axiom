// features/process-designer/components/canvas/CollaborationIndicator.tsx
// 협업 참여자 아바타 + N명 협업 중 표시 (설계 §1 와이어프레임)

import type { Collaborator } from '../../store/canvasDataStore';

interface CollaborationIndicatorProps {
 collaborators: Collaborator[];
 connected: boolean;
}

export function CollaborationIndicator({ collaborators, connected }: CollaborationIndicatorProps) {
 if (!connected && collaborators.length === 0) return null;

 return (
 <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-muted/80 rounded-full px-3 py-1.5 pointer-events-none">
 {collaborators.map((c) => (
 <div
 key={c.clientId}
 className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white"
 style={{ backgroundColor: c.color }}
 title={c.name}
 >
 {c.name[0]?.toUpperCase() ?? '?'}
 </div>
 ))}
 <span className="text-xs text-muted-foreground ml-1">
 {collaborators.length + 1}명 협업 중
 </span>
 </div>
 );
}
