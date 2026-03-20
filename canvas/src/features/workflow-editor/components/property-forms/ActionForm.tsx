/**
 * ActionForm — 액션(Then) 노드 속성 편집 폼
 *
 * GWT(Given-When-Then) 패턴의 Then 부분을 편집한다.
 * 여러 액션을 추가할 수 있으며, 각 액션은 [오퍼레이션] [타겟] [페이로드] 구조.
 * 오퍼레이션 종류: SET(값 설정), EMIT(이벤트 발행), NOTIFY(알림), INVOKE(서비스 호출).
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
import type { ActionData, ActionOperation } from '../../types/workflowEditor.types';

// 액션 오퍼레이션 키 (label은 런타임에 t()로 번역)
const ACTION_OP_KEYS: { value: ActionOperation; labelKey: string }[] = [
  { value: 'SET', labelKey: 'workflowEditor.action.operations.SET' },
  { value: 'EMIT', labelKey: 'workflowEditor.action.operations.EMIT' },
  { value: 'NOTIFY', labelKey: 'workflowEditor.action.operations.NOTIFY' },
  { value: 'INVOKE', labelKey: 'workflowEditor.action.operations.INVOKE' },
];

interface ActionFormProps {
  data: ActionData;
  onChange: (data: ActionData) => void;
}

export const ActionForm: React.FC<ActionFormProps> = ({ data, onChange }) => {
  const { t } = useTranslation();

  // 새 액션 행 추가
  const addRow = () => {
    onChange({
      ...data,
      actions: [
        ...data.actions,
        { id: crypto.randomUUID(), operation: 'SET', target: '', payload: '' },
      ],
    });
  };

  // 액션 행 삭제
  const removeRow = (id: string) => {
    onChange({
      ...data,
      actions: data.actions.filter((a) => a.id !== id),
    });
  };

  // 액션 행 업데이트
  const updateRow = (id: string, patch: Partial<(typeof data.actions)[0]>) => {
    onChange({
      ...data,
      actions: data.actions.map((a) => (a.id === id ? { ...a, ...patch } : a)),
    });
  };

  return (
    <div className="space-y-3">
      <Label className="text-xs font-semibold">{t('workflowEditor.action.title')}</Label>

      {/* 액션 행 목록 */}
      {data.actions.map((row) => (
        <div key={row.id} className="space-y-1 p-2 border border-border rounded-md">
          <div className="flex gap-1 items-center">
            <Select
              value={row.operation}
              onValueChange={(v) => updateRow(row.id, { operation: v as ActionOperation })}
            >
              <SelectTrigger className="h-7 w-28 text-[10px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ACTION_OP_KEYS.map((op) => (
                  <SelectItem key={op.value} value={op.value} className="text-[10px]">
                    {t(op.labelKey)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0 ml-auto"
              onClick={() => removeRow(row.id)}
            >
              <X className="h-3 w-3" />
            </Button>
          </div>
          <Input
            value={row.target}
            onChange={(e) => updateRow(row.id, { target: e.target.value })}
            className="h-7 text-[10px]"
            placeholder={t('workflowEditor.action.target')}
          />
          <Input
            value={row.payload}
            onChange={(e) => updateRow(row.id, { payload: e.target.value })}
            className="h-7 text-[10px]"
            placeholder={t('workflowEditor.action.payload')}
          />
        </div>
      ))}

      {/* 액션 추가 버튼 */}
      <Button variant="outline" size="sm" className="w-full h-7 text-xs" onClick={addRow}>
        <Plus className="h-3 w-3 mr-1" />
        {t('workflowEditor.action.addAction')}
      </Button>
    </div>
  );
};
