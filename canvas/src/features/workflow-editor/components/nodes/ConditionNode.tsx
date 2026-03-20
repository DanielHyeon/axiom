/**
 * ConditionNode — 조건(Given) 노드 표시 컴포넌트
 *
 * 조건 요약을 1~2줄로 보여준다 (예: "field == value AND ...").
 */

import { Filter } from 'lucide-react';
import type { ConditionData, ConditionOperator } from '../../types/workflowEditor.types';

// 연산자 표시 심볼
const OP_SYMBOL: Record<ConditionOperator, string> = {
  equals: '==',
  not_equals: '!=',
  greater_than: '>',
  less_than: '<',
  contains: '∋',
  in: '∈',
  is_null: 'NULL',
  is_not_null: '!NULL',
};

interface ConditionNodeProps {
  data: ConditionData;
}

export const ConditionNode: React.FC<ConditionNodeProps> = ({ data }) => {
  const { conditions, logicalOp } = data;
  // 최대 2줄만 표시
  const preview = conditions.slice(0, 2);
  const remaining = conditions.length - preview.length;

  return (
    <div className="flex flex-col items-center gap-1 p-2">
      <Filter className="h-4 w-4 text-sky-400" />
      <div className="text-[9px] text-sky-200 text-center leading-tight max-w-[120px]">
        {preview.map((c, i) => (
          <span key={c.id}>
            {i > 0 && <span className="text-sky-400/60"> {logicalOp} </span>}
            <span className="font-mono">
              {c.field || '?'} {OP_SYMBOL[c.operator]} {c.value || '?'}
            </span>
          </span>
        ))}
        {remaining > 0 && (
          <span className="text-sky-400/50"> +{remaining}</span>
        )}
      </div>
    </div>
  );
};
