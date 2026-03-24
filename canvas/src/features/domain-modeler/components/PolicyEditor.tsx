/**
 * PolicyEditor — Policy 전체 편집 패널
 *
 * 정책 이름, 설명, 활성 토글, 트리거 이벤트,
 * 트리거 조건 빌더, 대상 서비스/커맨드, 페이로드 템플릿,
 * 쿨다운 설정, 저장/삭제 버튼을 제공한다.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Save, Trash2, Plus, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { usePolicies } from '../hooks/useActionTypes';
import type {
  Policy,
  TriggerCondition,
  ComparisonOperator,
} from '../types/domainModeler.types';

// 대상 서비스 옵션
const SERVICE_OPTIONS = [
  { value: 'core', label: 'Core (BPM/Agent)' },
  { value: 'synapse', label: 'Synapse (온톨로지)' },
  { value: 'weaver', label: 'Weaver (데이터패브릭)' },
  { value: 'oracle', label: 'Oracle (NL2SQL)' },
  { value: 'vision', label: 'Vision (OLAP/What-if)' },
];

// 비교 연산자 옵션
const OPERATORS: { value: ComparisonOperator; label: string }[] = [
  { value: '==', label: '==' },
  { value: '!=', label: '!=' },
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
];

interface PolicyEditorProps {
  /** 편집 대상 Policy (null 이면 신규 생성 모드) */
  policy: Policy | null;
}

export const PolicyEditor: React.FC<PolicyEditorProps> = ({ policy }) => {
  const { t } = useTranslation();
  const { create, update, remove, saving } = usePolicies();

  // ── 로컬 폼 상태 ──
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [triggerEvent, setTriggerEvent] = useState('');
  const [triggerConditions, setTriggerConditions] = useState<TriggerCondition[]>([]);
  const [targetService, setTargetService] = useState('core');
  const [targetCommand, setTargetCommand] = useState('');
  const [payloadTemplate, setPayloadTemplate] = useState('{}');
  const [cooldownSeconds, setCooldownSeconds] = useState(60);

  // 선택된 Policy 가 바뀌면 로컬 폼 동기화
  useEffect(() => {
    if (policy) {
      setName(policy.name);
      setDescription(policy.description);
      setEnabled(policy.enabled);
      setTriggerEvent(policy.trigger_event);
      setTriggerConditions(policy.trigger_conditions);
      setTargetService(policy.target_service);
      setTargetCommand(policy.target_command);
      setPayloadTemplate(policy.command_payload_template);
      setCooldownSeconds(policy.cooldown_seconds);
    } else {
      setName('');
      setDescription('');
      setEnabled(true);
      setTriggerEvent('');
      setTriggerConditions([]);
      setTargetService('core');
      setTargetCommand('');
      setPayloadTemplate('{}');
      setCooldownSeconds(60);
    }
  }, [policy]);

  // ── 트리거 조건 관리 ──

  const addTriggerCondition = useCallback(() => {
    setTriggerConditions((prev) => [
      ...prev,
      { field: '', operator: '==' as ComparisonOperator, value: '' },
    ]);
  }, []);

  const updateTriggerCondition = useCallback(
    (index: number, partial: Partial<TriggerCondition>) => {
      setTriggerConditions((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], ...partial };
        return next;
      });
    },
    [],
  );

  const removeTriggerCondition = useCallback((index: number) => {
    setTriggerConditions((prev) => prev.filter((_, i) => i !== index));
  }, []);

  /** 저장 */
  const handleSave = useCallback(async () => {
    const payload = {
      name,
      description,
      enabled,
      trigger_event: triggerEvent,
      trigger_conditions: triggerConditions,
      target_service: targetService,
      target_command: targetCommand,
      command_payload_template: payloadTemplate,
      cooldown_seconds: cooldownSeconds,
    };

    if (policy) {
      await update(policy.id, payload);
    } else {
      await create(payload);
    }
  }, [
    policy, name, description, enabled, triggerEvent, triggerConditions,
    targetService, targetCommand, payloadTemplate, cooldownSeconds,
    create, update,
  ]);

  /** 삭제 */
  const handleDelete = useCallback(async () => {
    if (!policy) return;
    if (!window.confirm(t('domainModeler.confirmDeletePolicy', { name: policy.name }))) return;
    await remove(policy.id);
  }, [policy, remove]);

  /** 저장 가능 여부 */
  const canSave =
    name.trim().length > 0 &&
    triggerEvent.trim().length > 0 &&
    targetCommand.trim().length > 0;

  return (
    <Card className="h-full border-0 shadow-none bg-transparent">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold">
          {policy ? t('domainModeler.editPolicy') : t('domainModeler.newPolicy')}
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4 overflow-y-auto">
        {/* 이름 */}
        <div className="space-y-1">
          <Label htmlFor="pol-name" className="text-xs">
            {t('domainModeler.name')} <span className="text-destructive">{t('domainModeler.nameRequired')}</span>
          </Label>
          <Input
            id="pol-name"
            className="h-9"
            placeholder={t('domainModeler.policyNamePlaceholder')}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* 설명 */}
        <div className="space-y-1">
          <Label htmlFor="pol-desc" className="text-xs">
            {t('domainModeler.description')}
          </Label>
          <Input
            id="pol-desc"
            className="h-9"
            placeholder={t('domainModeler.policyDescPlaceholder')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>

        {/* 활성 토글 */}
        <div className="flex items-center gap-2">
          <Checkbox
            id="pol-enabled"
            checked={enabled}
            onCheckedChange={(v) => setEnabled(v === true)}
          />
          <Label htmlFor="pol-enabled" className="text-xs cursor-pointer">
            {t('domainModeler.enabled')}
          </Label>
        </div>

        <hr className="border-border/50" />

        {/* ── 트리거 설정 ── */}
        <div className="space-y-3">
          <Label className="text-sm font-semibold text-amber-400">
            {t('domainModeler.triggerEvent')}
          </Label>

          <Input
            className="h-9"
            placeholder={t('domainModeler.triggerEventPlaceholder')}
            value={triggerEvent}
            onChange={(e) => setTriggerEvent(e.target.value)}
            aria-label={t('domainModeler.triggerEventAriaLabel')}
          />

          {/* 트리거 조건 목록 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs text-muted-foreground">
                {t('domainModeler.triggerConditionsAnd')}
              </Label>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={addTriggerCondition}
              >
                <Plus className="h-3 w-3 mr-1" />
                {t('domainModeler.addCondition')}
              </Button>
            </div>

            {triggerConditions.length === 0 && (
              <p className="text-xs text-muted-foreground italic">
                {t('domainModeler.noTriggerConditions')}
              </p>
            )}

            {triggerConditions.map((tc, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 rounded-md border border-border/50 bg-muted/30 p-2"
              >
                <Input
                  className="h-8 text-xs flex-1"
                  placeholder={t('domainModeler.fieldPathPlaceholder')}
                  value={tc.field}
                  onChange={(e) =>
                    updateTriggerCondition(idx, { field: e.target.value })
                  }
                  aria-label={t('domainModeler.triggerFieldAriaLabel')}
                />
                <Select
                  value={tc.operator}
                  onValueChange={(v) =>
                    updateTriggerCondition(idx, {
                      operator: v as ComparisonOperator,
                    })
                  }
                >
                  <SelectTrigger className="w-20 h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OPERATORS.map((op) => (
                      <SelectItem key={op.value} value={op.value}>
                        {op.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  className="h-8 text-xs w-24"
                  placeholder={t('domainModeler.valuePlaceholder')}
                  value={tc.value}
                  onChange={(e) =>
                    updateTriggerCondition(idx, { value: e.target.value })
                  }
                  aria-label={t('domainModeler.triggerValueAriaLabel')}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-destructive"
                  onClick={() => removeTriggerCondition(idx)}
                  aria-label={t('domainModeler.deleteTriggerCondition')}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>

        <hr className="border-border/50" />

        {/* ── 대상 서비스/커맨드 ── */}
        <div className="space-y-3">
          <Label className="text-sm font-semibold text-green-400">
            {t('domainModeler.targetCommand')}
          </Label>

          <div className="flex items-center gap-2">
            <div className="space-y-1 flex-1">
              <Label htmlFor="pol-service" className="text-xs">
                {t('domainModeler.targetService')}
              </Label>
              <Select
                value={targetService}
                onValueChange={setTargetService}
              >
                <SelectTrigger id="pol-service" className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SERVICE_OPTIONS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1 flex-1">
              <Label htmlFor="pol-cmd" className="text-xs">
                {t('domainModeler.command')} <span className="text-destructive">{t('domainModeler.nameRequired')}</span>
              </Label>
              <Input
                id="pol-cmd"
                className="h-9"
                placeholder={t('domainModeler.commandPlaceholder')}
                value={targetCommand}
                onChange={(e) => setTargetCommand(e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* 커맨드 페이로드 템플릿 (JSON) */}
        <div className="space-y-1">
          <Label htmlFor="pol-payload" className="text-xs">
            {t('domainModeler.payloadTemplateName')}
          </Label>
          <Textarea
            id="pol-payload"
            className="min-h-[100px] font-mono text-xs"
            placeholder={t('domainModeler.payloadTemplatePlaceholder')}
            value={payloadTemplate}
            onChange={(e) => setPayloadTemplate(e.target.value)}
          />
        </div>

        {/* 쿨다운 */}
        <div className="space-y-1">
          <Label htmlFor="pol-cooldown" className="text-xs">
            {t('domainModeler.cooldown')}
          </Label>
          <Input
            id="pol-cooldown"
            type="number"
            className="h-9 w-32"
            min={0}
            max={86400}
            value={cooldownSeconds}
            onChange={(e) => setCooldownSeconds(Number(e.target.value) || 0)}
          />
        </div>

        <hr className="border-border/50" />

        {/* 하단 버튼 */}
        <div className="flex items-center gap-2 pt-2">
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

          {policy && (
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
