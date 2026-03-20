/**
 * ConditionForm — 조건(Given) 노드 속성 편집 폼
 *
 * GWT(Given-When-Then) 패턴의 Given 부분을 편집한다.
 * 여러 조건 행을 AND/OR로 결합하여 복합 조건을 구성할 수 있다.
 * 각 행은 [필드] [연산자] [값] 형태.
 */

import { useTranslation } from 'react-i18next';
import { X, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { ConditionData, ConditionOperator } from '../../types/workflowEditor.types';

// 조건 연산자 목록
const CONDITION_OPERATORS: { value: ConditionOperator; label: string }[] = [
  { value: 'equals', label: '==' },
  { value: 'not_equals', label: '!=' },
  { value: 'greater_than', label: '>' },
  { value: 'less_than', label: '<' },
  { value: 'contains', label: 'Contains' },
  { value: 'in', label: 'IN' },
  { value: 'is_null', label: 'NULL' },
  { value: 'is_not_null', label: 'NOT NULL' },
];

interface ConditionFormProps {
  data: ConditionData;
  onChange: (data: ConditionData) => void;
}

export const ConditionForm: React.FC<ConditionFormProps> = ({ data, onChange }) => {
  const { t } = useTranslation();

  // 새 조건 행 추가
  const addRow = () => {
    onChange({
      ...data,
      conditions: [
        ...data.conditions,
        { id: crypto.randomUUID(), field: '', operator: 'equals', value: '' },
      ],
    });
  };

  // 조건 행 삭제
  const removeRow = (id: string) => {
    onChange({
      ...data,
      conditions: data.conditions.filter((c) => c.id !== id),
    });
  };

  // 조건 행 업데이트
  const updateRow = (id: string, patch: Partial<(typeof data.conditions)[0]>) => {
    onChange({
      ...data,
      conditions: data.conditions.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    });
  };

  return (
    <div className="space-y-3">
      {/* 제목 + AND/OR 토글 */}
      <div className="flex items-center justify-between">
        <Label className="text-xs font-semibold">{t('workflowEditor.condition.title')}</Label>
        <Select
          value={data.logicalOp}
          onValueChange={(v) => onChange({ ...data, logicalOp: v as 'AND' | 'OR' })}
        >
          <SelectTrigger className="h-6 w-16 text-[10px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="AND" className="text-xs">AND</SelectItem>
            <SelectItem value="OR" className="text-xs">OR</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* 조건 행 목록 */}
      {data.conditions.map((row) => (
        <div key={row.id} className="flex gap-1 items-start">
          <Input
            value={row.field}
            onChange={(e) => updateRow(row.id, { field: e.target.value })}
            className="h-7 text-[10px] flex-1"
            placeholder={t('workflowEditor.condition.field')}
          />
          <Select
            value={row.operator}
            onValueChange={(v) => updateRow(row.id, { operator: v as ConditionOperator })}
          >
            <SelectTrigger className="h-7 w-14 text-[10px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CONDITION_OPERATORS.map((op) => (
                <SelectItem key={op.value} value={op.value} className="text-[10px]">
                  {op.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={row.value}
            onChange={(e) => updateRow(row.id, { value: e.target.value })}
            className="h-7 text-[10px] flex-1"
            placeholder={t('workflowEditor.condition.value')}
          />
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={() => removeRow(row.id)}
          >
            <X className="h-3 w-3" />
          </Button>
        </div>
      ))}

      {/* 조건 추가 버튼 */}
      <Button variant="outline" size="sm" className="w-full h-7 text-xs" onClick={addRow}>
        <Plus className="h-3 w-3 mr-1" />
        {t('workflowEditor.condition.addCondition')}
      </Button>
    </div>
  );
};
