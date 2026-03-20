/**
 * ActionRow — GWT 규칙의 Then 액션 한 행 편집기
 *
 * Op 유형(SET/EMIT/EXECUTE)에 따라 동적으로 입력 필드를 전환한다.
 * - SET: 대상 노드 + 필드 + 값
 * - EMIT: 이벤트 타입 + 페이로드
 * - EXECUTE: 실행할 ActionType ID
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { GWTAction, ActionOp } from '../types/domainModeler.types';

// 오퍼레이션 유형 키 (label은 고유명사, desc만 번역)
const OP_KEYS: { value: ActionOp; label: string; descKey: string }[] = [
  { value: 'SET', label: 'SET', descKey: 'domainModeler.opSetDesc' },
  { value: 'EMIT', label: 'EMIT', descKey: 'domainModeler.opEmitDesc' },
  { value: 'EXECUTE', label: 'EXECUTE', descKey: 'domainModeler.opExecuteDesc' },
];

interface ActionRowProps {
  /** 액션 데이터 */
  action: GWTAction;
  /** 액션 변경 콜백 */
  onChange: (updated: GWTAction) => void;
  /** 삭제 콜백 */
  onDelete: () => void;
  /** EXECUTE op에서 선택 가능한 ActionType ID 목록 (선택) */
  availableActionIds?: { id: string; name: string }[];
  /** 읽기 전용 모드 */
  disabled?: boolean;
}

export const ActionRow: React.FC<ActionRowProps> = ({
  action,
  onChange,
  onDelete,
  availableActionIds = [],
  disabled = false,
}) => {
  const { t } = useTranslation();

  /** 필드 하나를 업데이트하는 헬퍼 */
  const patch = (partial: Partial<GWTAction>) => {
    onChange({ ...action, ...partial });
  };

  return (
    <div
      className="flex flex-col gap-2 rounded-md border border-border/50 bg-muted/30 p-2"
      role="group"
      aria-label={t('domainModeler.actionAriaLabel', { op: action.op })}
    >
      {/* 첫 번째 줄: Op 선택 + 삭제 버튼 */}
      <div className="flex items-center gap-2">
        <Select
          value={action.op}
          onValueChange={(v) => patch({ op: v as ActionOp })}
          disabled={disabled}
        >
          <SelectTrigger className="w-28 h-8 text-xs">
            <SelectValue placeholder={t('domainModeler.opPlaceholder')} />
          </SelectTrigger>
          <SelectContent>
            {OP_KEYS.map((op) => (
              <SelectItem key={op.value} value={op.value}>
                <span className="font-mono">{op.label}</span>
                <span className="ml-1 text-muted-foreground text-[10px]">
                  — {t(op.descKey)}
                </span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex-1" />

        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0 text-destructive hover:text-destructive"
          onClick={onDelete}
          disabled={disabled}
          aria-label={t('domainModeler.deleteAction')}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* SET: 대상 노드 ID + 필드 + 값 */}
      {action.op === 'SET' && (
        <div className="flex items-center gap-2">
          <Input
            className="h-8 text-xs flex-1"
            placeholder={t('domainModeler.targetNodePlaceholder')}
            value={action.targetNodeId ?? ''}
            onChange={(e) => patch({ targetNodeId: e.target.value })}
            disabled={disabled}
            aria-label={t('domainModeler.targetNodeAriaLabel')}
          />
          <Input
            className="h-8 text-xs w-28"
            placeholder={t('domainModeler.fieldPlaceholder')}
            value={action.field ?? ''}
            onChange={(e) => patch({ field: e.target.value })}
            disabled={disabled}
            aria-label={t('domainModeler.changeFieldAriaLabel')}
          />
          <Input
            className="h-8 text-xs w-24"
            placeholder={t('domainModeler.valuePlaceholder')}
            value={action.value ?? ''}
            onChange={(e) => patch({ value: e.target.value })}
            disabled={disabled}
            aria-label={t('domainModeler.setValueAriaLabel')}
          />
        </div>
      )}

      {/* EMIT: 이벤트 타입 + 페이로드 */}
      {action.op === 'EMIT' && (
        <div className="flex items-center gap-2">
          <Input
            className="h-8 text-xs flex-1"
            placeholder={t('domainModeler.emitEventPlaceholder')}
            value={action.eventType ?? ''}
            onChange={(e) => patch({ eventType: e.target.value })}
            disabled={disabled}
            aria-label={t('domainModeler.emitEventAriaLabel')}
          />
          <Input
            className="h-8 text-xs flex-1"
            placeholder={t('domainModeler.payloadPlaceholder')}
            value={action.payload ?? ''}
            onChange={(e) => patch({ payload: e.target.value })}
            disabled={disabled}
            aria-label={t('domainModeler.payloadAriaLabel')}
          />
        </div>
      )}

      {/* EXECUTE: 실행할 ActionType ID */}
      {action.op === 'EXECUTE' && (
        <div className="flex items-center gap-2">
          {availableActionIds.length > 0 ? (
            <Select
              value={action.actionId ?? ''}
              onValueChange={(v) => patch({ actionId: v })}
              disabled={disabled}
            >
              <SelectTrigger className="h-8 text-xs flex-1">
                <SelectValue placeholder={t('domainModeler.selectActionType')} />
              </SelectTrigger>
              <SelectContent>
                {availableActionIds.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              className="h-8 text-xs flex-1"
              placeholder={t('domainModeler.actionTypeIdPlaceholder')}
              value={action.actionId ?? ''}
              onChange={(e) => patch({ actionId: e.target.value })}
              disabled={disabled}
              aria-label={t('domainModeler.actionTypeIdAriaLabel')}
            />
          )}
        </div>
      )}
    </div>
  );
};
