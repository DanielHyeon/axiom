/**
 * ActionNode — 액션(Then) 노드 표시 컴포넌트
 *
 * SET / EMIT 동작 요약을 보여준다.
 */

import { Play } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { ActionData, ActionOperation } from '../../types/workflowEditor.types';

// 동작 유형별 색상 클래스
const OP_COLOR: Record<ActionOperation, string> = {
  SET: 'border-emerald-500/40 text-emerald-300',
  EMIT: 'border-violet-500/40 text-violet-300',
  NOTIFY: 'border-orange-500/40 text-orange-300',
  INVOKE: 'border-rose-500/40 text-rose-300',
};

interface ActionNodeProps {
  data: ActionData;
}

export const ActionNode: React.FC<ActionNodeProps> = ({ data }) => {
  const { actions } = data;
  // 최대 2개만 미리보기
  const preview = actions.slice(0, 2);
  const remaining = actions.length - preview.length;

  return (
    <div className="flex flex-col items-center gap-1 p-2">
      <Play className="h-4 w-4 text-emerald-400" />
      <div className="flex flex-col items-center gap-0.5">
        {preview.map((a) => (
          <Badge
            key={a.id}
            variant="outline"
            className={`text-[9px] ${OP_COLOR[a.operation]} whitespace-nowrap`}
          >
            {a.operation} {a.target || '...'}
          </Badge>
        ))}
        {remaining > 0 && (
          <span className="text-[9px] text-emerald-400/50">+{remaining}</span>
        )}
      </div>
    </div>
  );
};
