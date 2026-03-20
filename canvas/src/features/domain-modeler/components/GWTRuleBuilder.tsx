/**
 * GWTRuleBuilder — Given-When-Then 규칙 시각적 빌더
 *
 * 3개 섹션으로 구성:
 * - Given: 조건 목록 (ConditionRow 반복)
 * - When: 이벤트 타입 셀렉터
 * - Then: 액션 목록 (ActionRow 반복)
 *
 * 각 섹션에 행 추가/삭제 버튼을 제공한다.
 */

import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ConditionRow } from './ConditionRow';
import { ActionRow } from './ActionRow';
import type { GWTCondition, GWTAction } from '../types/domainModeler.types';

/** UUID v4 간이 생성기 (프론트 전용 임시 ID) */
function uid(): string {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

interface GWTRuleBuilderProps {
  /** When 이벤트 타입 */
  whenEvent: string;
  /** When 이벤트 타입 변경 콜백 */
  onWhenEventChange: (event: string) => void;
  /** Given 조건 목록 */
  conditions: GWTCondition[];
  /** Given 조건 목록 변경 콜백 */
  onConditionsChange: (conditions: GWTCondition[]) => void;
  /** Then 액션 목록 */
  actions: GWTAction[];
  /** Then 액션 목록 변경 콜백 */
  onActionsChange: (actions: GWTAction[]) => void;
  /** EXECUTE op에서 선택 가능한 ActionType 목록 */
  availableActionIds?: { id: string; name: string }[];
  /** 읽기 전용 모드 */
  disabled?: boolean;
}

export const GWTRuleBuilder: React.FC<GWTRuleBuilderProps> = ({
  whenEvent,
  onWhenEventChange,
  conditions,
  onConditionsChange,
  actions,
  onActionsChange,
  availableActionIds = [],
  disabled = false,
}) => {
  const { t } = useTranslation();

  // ── Given 조건 관리 ──

  /** 새 조건 추가 */
  const addCondition = useCallback(() => {
    const newCondition: GWTCondition = {
      id: uid(),
      type: 'state',
      layer: 'kpi',
      field: '',
      operator: '==',
      value: '',
    };
    onConditionsChange([...conditions, newCondition]);
  }, [conditions, onConditionsChange]);

  /** 조건 수정 */
  const updateCondition = useCallback(
    (index: number, updated: GWTCondition) => {
      const next = [...conditions];
      next[index] = updated;
      onConditionsChange(next);
    },
    [conditions, onConditionsChange],
  );

  /** 조건 삭제 */
  const removeCondition = useCallback(
    (index: number) => {
      onConditionsChange(conditions.filter((_, i) => i !== index));
    },
    [conditions, onConditionsChange],
  );

  // ── Then 액션 관리 ──

  /** 새 액션 추가 */
  const addAction = useCallback(() => {
    const newAction: GWTAction = {
      id: uid(),
      op: 'SET',
      targetNodeId: '',
      field: '',
      value: '',
    };
    onActionsChange([...actions, newAction]);
  }, [actions, onActionsChange]);

  /** 액션 수정 */
  const updateAction = useCallback(
    (index: number, updated: GWTAction) => {
      const next = [...actions];
      next[index] = updated;
      onActionsChange(next);
    },
    [actions, onActionsChange],
  );

  /** 액션 삭제 */
  const removeAction = useCallback(
    (index: number) => {
      onActionsChange(actions.filter((_, i) => i !== index));
    },
    [actions, onActionsChange],
  );

  return (
    <div className="space-y-5">
      {/* ── Given (조건) 섹션 ── */}
      <section aria-labelledby="gwt-given-label">
        <div className="flex items-center justify-between mb-2">
          <Label
            id="gwt-given-label"
            className="text-sm font-semibold text-blue-400"
          >
            {t('domainModeler.given')}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              — {t('domainModeler.givenDesc')}
            </span>
          </Label>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={addCondition}
            disabled={disabled}
          >
            <Plus className="h-3 w-3 mr-1" />
            {t('domainModeler.addCondition')}
          </Button>
        </div>

        {conditions.length === 0 ? (
          <p className="text-xs text-muted-foreground italic py-2">
            {t('domainModeler.noConditions')}
          </p>
        ) : (
          <div className="space-y-2">
            {conditions.map((cond, idx) => (
              <ConditionRow
                key={cond.id}
                condition={cond}
                onChange={(updated) => updateCondition(idx, updated)}
                onDelete={() => removeCondition(idx)}
                disabled={disabled}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── When (이벤트) 섹션 ── */}
      <section aria-labelledby="gwt-when-label">
        <Label
          id="gwt-when-label"
          className="text-sm font-semibold text-amber-400 block mb-2"
        >
          {t('domainModeler.when')}
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            — {t('domainModeler.whenDesc')}
          </span>
        </Label>
        <Input
          className="h-9 text-sm"
          placeholder={t('domainModeler.eventPlaceholder')}
          value={whenEvent}
          onChange={(e) => onWhenEventChange(e.target.value)}
          disabled={disabled}
          aria-label={t('domainModeler.whenEventAriaLabel')}
        />
      </section>

      {/* ── Then (액션) 섹션 ── */}
      <section aria-labelledby="gwt-then-label">
        <div className="flex items-center justify-between mb-2">
          <Label
            id="gwt-then-label"
            className="text-sm font-semibold text-green-400"
          >
            {t('domainModeler.then')}
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              — {t('domainModeler.thenDesc')}
            </span>
          </Label>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={addAction}
            disabled={disabled}
          >
            <Plus className="h-3 w-3 mr-1" />
            {t('domainModeler.addAction')}
          </Button>
        </div>

        {actions.length === 0 ? (
          <p className="text-xs text-muted-foreground italic py-2">
            {t('domainModeler.noActions')}
          </p>
        ) : (
          <div className="space-y-2">
            {actions.map((act, idx) => (
              <ActionRow
                key={act.id}
                action={act}
                onChange={(updated) => updateAction(idx, updated)}
                onDelete={() => removeAction(idx)}
                availableActionIds={availableActionIds}
                disabled={disabled}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
};
