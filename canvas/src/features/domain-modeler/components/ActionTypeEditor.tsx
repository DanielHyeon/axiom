/**
 * ActionTypeEditor — ActionType 전체 편집 패널
 *
 * 이름, 설명, 활성/비활성 토글, 우선순위, GWTRuleBuilder 를 포함하며,
 * 저장, 삭제, Dry-Run 테스트 버튼을 제공한다.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Save, Trash2, Play, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GWTRuleBuilder } from './GWTRuleBuilder';
import { useActionTypes } from '../hooks/useActionTypes';
import type {
  ActionType,
  GWTCondition,
  GWTAction,
} from '../types/domainModeler.types';

interface ActionTypeEditorProps {
  /** 편집 대상 ActionType (null 이면 신규 생성 모드) */
  actionType: ActionType | null;
}

export const ActionTypeEditor: React.FC<ActionTypeEditorProps> = ({
  actionType,
}) => {
  const { t } = useTranslation();
  const { create, update, remove, dryRun, saving, actionTypes } =
    useActionTypes();

  // ── 로컬 폼 상태 ──
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [priority, setPriority] = useState(100);
  const [whenEvent, setWhenEvent] = useState('');
  const [conditions, setConditions] = useState<GWTCondition[]>([]);
  const [actions, setActions] = useState<GWTAction[]>([]);
  const [testing, setTesting] = useState(false);

  // 선택된 ActionType 이 바뀌면 로컬 폼을 동기화
  useEffect(() => {
    if (actionType) {
      setName(actionType.name);
      setDescription(actionType.description);
      setEnabled(actionType.enabled);
      setPriority(actionType.priority);
      setWhenEvent(actionType.when_event);
      setConditions(actionType.conditions);
      setActions(actionType.actions);
    } else {
      // 신규 생성 모드: 초기값
      setName('');
      setDescription('');
      setEnabled(true);
      setPriority(100);
      setWhenEvent('');
      setConditions([]);
      setActions([]);
    }
  }, [actionType]);

  /** EXECUTE op에서 선택 가능한 ActionType 목록 (자기 자신 제외) */
  const availableActionIds = actionTypes
    .filter((at) => at.id !== actionType?.id)
    .map((at) => ({ id: at.id, name: at.name }));

  /** 저장 (생성 또는 수정) */
  const handleSave = useCallback(async () => {
    // 조건/액션에서 프론트 전용 id 를 제거한 페이로드 생성
    const condPayload = conditions.map(({ id: _id, ...rest }) => rest);
    const actPayload = actions.map(({ id: _id, ...rest }) => rest);

    if (actionType) {
      // 수정
      await update(actionType.id, {
        name,
        description,
        enabled,
        priority,
        when_event: whenEvent,
        conditions: condPayload,
        actions: actPayload,
      });
    } else {
      // 생성
      await create({
        name,
        description,
        enabled,
        priority,
        when_event: whenEvent,
        conditions: condPayload,
        actions: actPayload,
      });
    }
  }, [actionType, name, description, enabled, priority, whenEvent, conditions, actions, create, update]);

  /** 삭제 */
  const handleDelete = useCallback(async () => {
    if (!actionType) return;
    // 확인 프롬프트
    if (!window.confirm(t('domainModeler.confirmDeleteActionType', { name: actionType.name }))) return;
    await remove(actionType.id);
  }, [actionType, remove]);

  /** Dry-Run 테스트 */
  const handleDryRun = useCallback(async () => {
    if (!actionType) return;
    setTesting(true);
    try {
      await dryRun(actionType.id);
    } finally {
      setTesting(false);
    }
  }, [actionType, dryRun]);

  /** 저장 가능 여부 */
  const canSave = name.trim().length > 0 && whenEvent.trim().length > 0;

  return (
    <Card className="h-full border-0 shadow-none bg-transparent">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold">
          {actionType ? t('domainModeler.editActionType') : t('domainModeler.newActionType')}
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4 overflow-y-auto">
        {/* 이름 */}
        <div className="space-y-1">
          <Label htmlFor="at-name" className="text-xs">
            {t('domainModeler.name')} <span className="text-destructive">{t('domainModeler.nameRequired')}</span>
          </Label>
          <Input
            id="at-name"
            className="h-9"
            placeholder={t('domainModeler.namePlaceholder')}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* 설명 */}
        <div className="space-y-1">
          <Label htmlFor="at-desc" className="text-xs">
            {t('domainModeler.description')}
          </Label>
          <Input
            id="at-desc"
            className="h-9"
            placeholder={t('domainModeler.descriptionPlaceholder')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* 활성/우선순위 한 줄 */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Checkbox
              id="at-enabled"
              checked={enabled}
              onCheckedChange={(v) => setEnabled(v === true)}
            />
            <Label htmlFor="at-enabled" className="text-xs cursor-pointer">
              {t('domainModeler.enabled')}
            </Label>
          </div>

          <div className="flex items-center gap-2">
            <Label htmlFor="at-priority" className="text-xs whitespace-nowrap">
              {t('domainModeler.priority')}
            </Label>
            <Input
              id="at-priority"
              type="number"
              className="h-8 w-20 text-xs"
              min={0}
              max={9999}
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value) || 0)}
            />
          </div>
        </div>

        {/* 구분선 */}
        <hr className="border-border/50" />

        {/* GWT 규칙 빌더 */}
        <GWTRuleBuilder
          whenEvent={whenEvent}
          onWhenEventChange={setWhenEvent}
          conditions={conditions}
          onConditionsChange={setConditions}
          actions={actions}
          onActionsChange={setActions}
          availableActionIds={availableActionIds}
        />

        {/* 구분선 */}
        <hr className="border-border/50" />

        {/* 하단 버튼 영역 */}
        <div className="flex items-center gap-2 pt-2">
          {/* 저장 */}
          <Button
            className="flex-1"
            onClick={handleSave}
            disabled={!canSave || saving}
          >
            {saving ? (
              <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            ) : (
              <Save className="h-4 w-4 mr-1" />
            )}
            {t('domainModeler.save')}
          </Button>

          {/* Dry-Run 테스트 (기존 항목만) */}
          {actionType && (
            <Button
              variant="outline"
              onClick={handleDryRun}
              disabled={testing || saving}
            >
              {testing ? (
                <Loader2 className="h-4 w-4 mr-1 animate-spin" />
              ) : (
                <Play className="h-4 w-4 mr-1" />
              )}
              {t('domainModeler.test')}
            </Button>
          )}

          {/* 삭제 (기존 항목만) */}
          {actionType && (
            <Button
              variant="destructive"
              size="icon"
              onClick={handleDelete}
              disabled={saving}
              aria-label={t('domainModeler.delete')}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
