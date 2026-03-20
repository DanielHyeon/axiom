/**
 * WorkflowPropertyPanel — 선택 노드 속성 편집 패널 (우측 30%)
 *
 * 노드 타입에 따라 적절한 편집 폼을 렌더링한다:
 * - trigger: 이벤트 유형 셀렉터
 * - condition: GWT Given 조건 편집기
 * - action: GWT Then 액션 편집기
 * - policy: 정책 설정
 * - gateway: 분기 모드 선택
 */

import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Trash2, X, Plus } from 'lucide-react';
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
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useWorkflowEditorStore } from '../store/useWorkflowEditorStore';
import type {
  WorkflowNode,
  TriggerData,
  TriggerEventType,
  ConditionData,
  ConditionOperator,
  ActionData,
  ActionOperation,
  PolicyData,
  GatewayData,
  GatewayMode,
} from '../types/workflowEditor.types';

// ──────────────────────────────────────
// 속성 패널 메인
// ──────────────────────────────────────

export const WorkflowPropertyPanel: React.FC = () => {
  const { t } = useTranslation();
  const selectedNodeId = useWorkflowEditorStore((s) => s.selectedNodeId);
  const nodes = useWorkflowEditorStore((s) => s.nodes);
  const updateNode = useWorkflowEditorStore((s) => s.updateNode);
  const updateNodeData = useWorkflowEditorStore((s) => s.updateNodeData);
  const removeNode = useWorkflowEditorStore((s) => s.removeNode);
  const setSelectedNode = useWorkflowEditorStore((s) => s.setSelectedNode);

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId],
  );

  const handleLabelChange = useCallback(
    (label: string) => {
      if (selectedNodeId) updateNode(selectedNodeId, { label });
    },
    [selectedNodeId, updateNode],
  );

  const handleDelete = useCallback(() => {
    if (selectedNodeId) {
      removeNode(selectedNodeId);
    }
  }, [selectedNodeId, removeNode]);

  // 선택 없음 상태
  if (!selectedNode) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        <p>{t('workflowEditor.property.selectNode')}</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-4">
        {/* 헤더: 노드 이름 + 닫기 */}
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            {t('workflowEditor.property.title')}
          </h3>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setSelectedNode(null)}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        {/* 공통: 라벨 편집 */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t('workflowEditor.property.label')}</Label>
          <Input
            value={selectedNode.label}
            onChange={(e) => handleLabelChange(e.target.value)}
            className="h-8 text-sm"
            placeholder={t('workflowEditor.property.label')}
          />
        </div>

        {/* 노드 타입 표시 */}
        <div className="space-y-1.5">
          <Label className="text-xs">{t('workflowEditor.property.type')}</Label>
          <div className="text-xs font-mono text-muted-foreground bg-muted px-2 py-1 rounded">
            {selectedNode.type}
          </div>
        </div>

        <Separator />

        {/* 타입별 속성 폼 */}
        {selectedNode.type === 'trigger' && (
          <TriggerForm
            data={selectedNode.data as TriggerData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'condition' && (
          <ConditionForm
            data={selectedNode.data as ConditionData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'action' && (
          <ActionForm
            data={selectedNode.data as ActionData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'policy' && (
          <PolicyForm
            data={selectedNode.data as PolicyData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}
        {selectedNode.type === 'gateway' && (
          <GatewayForm
            data={selectedNode.data as GatewayData}
            onChange={(d) => updateNodeData(selectedNode.id, d)}
          />
        )}

        <Separator />

        {/* 삭제 버튼 */}
        <Button
          variant="destructive"
          size="sm"
          className="w-full gap-1.5"
          onClick={handleDelete}
        >
          <Trash2 className="h-3.5 w-3.5" />
          {t('common.delete')}
        </Button>
      </div>
    </ScrollArea>
  );
};

// ──────────────────────────────────────
// 트리거 폼
// ──────────────────────────────────────

// 트리거 이벤트 타입 키 (label은 런타임에 t()로 번역)
const TRIGGER_EVENT_KEYS: { value: TriggerEventType; labelKey: string }[] = [
  { value: 'manual', labelKey: 'workflowEditor.trigger.events.manual' },
  { value: 'case_created', labelKey: 'workflowEditor.trigger.events.case_created' },
  { value: 'case_updated', labelKey: 'workflowEditor.trigger.events.case_updated' },
  { value: 'kpi_threshold', labelKey: 'workflowEditor.trigger.events.kpi_threshold' },
  { value: 'schedule_cron', labelKey: 'workflowEditor.trigger.events.schedule_cron' },
  { value: 'webhook', labelKey: 'workflowEditor.trigger.events.webhook' },
];

const TriggerForm: React.FC<{
  data: TriggerData;
  onChange: (data: TriggerData) => void;
}> = ({ data, onChange }) => {
  const { t } = useTranslation();
  return (
  <div className="space-y-3">
    <Label className="text-xs font-semibold">{t('workflowEditor.trigger.title')}</Label>

    {/* 이벤트 유형 */}
    <div className="space-y-1">
      <Label className="text-xs">{t('workflowEditor.trigger.eventType')}</Label>
      <Select
        value={data.eventType}
        onValueChange={(v) => onChange({ ...data, eventType: v as TriggerEventType })}
      >
        <SelectTrigger className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {TRIGGER_EVENT_KEYS.map((e) => (
            <SelectItem key={e.value} value={e.value} className="text-xs">
              {t(e.labelKey)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>

    {/* Cron 표현식 (schedule_cron 전용) */}
    {data.eventType === 'schedule_cron' && (
      <div className="space-y-1">
        <Label className="text-xs">{t('workflowEditor.trigger.cronExpression')}</Label>
        <Input
          value={data.cronExpression ?? ''}
          onChange={(e) => onChange({ ...data, cronExpression: e.target.value })}
          className="h-8 text-xs font-mono"
          placeholder="0 */5 * * *"
        />
      </div>
    )}

    {/* Webhook URL */}
    {data.eventType === 'webhook' && (
      <div className="space-y-1">
        <Label className="text-xs">{t('workflowEditor.trigger.webhookUrl')}</Label>
        <Input
          value={data.webhookUrl ?? ''}
          onChange={(e) => onChange({ ...data, webhookUrl: e.target.value })}
          className="h-8 text-xs"
          placeholder="https://..."
        />
      </div>
    )}

    {/* KPI 임계값 설정 */}
    {data.eventType === 'kpi_threshold' && (
      <>
        <div className="space-y-1">
          <Label className="text-xs">{t('workflowEditor.trigger.kpiField')}</Label>
          <Input
            value={data.kpiField ?? ''}
            onChange={(e) => onChange({ ...data, kpiField: e.target.value })}
            className="h-8 text-xs"
            placeholder="예: oee"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">{t('workflowEditor.trigger.kpiThreshold')}</Label>
          <Input
            type="number"
            value={data.kpiThreshold ?? ''}
            onChange={(e) => onChange({ ...data, kpiThreshold: parseFloat(e.target.value) || 0 })}
            className="h-8 text-xs"
            placeholder="80"
          />
        </div>
      </>
    )}
  </div>
  );
};

// ──────────────────────────────────────
// 조건(Given) 폼
// ──────────────────────────────────────

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

const ConditionForm: React.FC<{
  data: ConditionData;
  onChange: (data: ConditionData) => void;
}> = ({ data, onChange }) => {
  const { t } = useTranslation();

  const addRow = () => {
    onChange({
      ...data,
      conditions: [
        ...data.conditions,
        { id: crypto.randomUUID(), field: '', operator: 'equals', value: '' },
      ],
    });
  };

  const removeRow = (id: string) => {
    onChange({
      ...data,
      conditions: data.conditions.filter((c) => c.id !== id),
    });
  };

  const updateRow = (id: string, patch: Partial<(typeof data.conditions)[0]>) => {
    onChange({
      ...data,
      conditions: data.conditions.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    });
  };

  return (
    <div className="space-y-3">
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

      <Button variant="outline" size="sm" className="w-full h-7 text-xs" onClick={addRow}>
        <Plus className="h-3 w-3 mr-1" />
        {t('workflowEditor.condition.addCondition')}
      </Button>
    </div>
  );
};

// ──────────────────────────────────────
// 액션(Then) 폼
// ──────────────────────────────────────

// 액션 오퍼레이션 키 (label은 런타임에 t()로 번역)
const ACTION_OP_KEYS: { value: ActionOperation; labelKey: string }[] = [
  { value: 'SET', labelKey: 'workflowEditor.action.operations.SET' },
  { value: 'EMIT', labelKey: 'workflowEditor.action.operations.EMIT' },
  { value: 'NOTIFY', labelKey: 'workflowEditor.action.operations.NOTIFY' },
  { value: 'INVOKE', labelKey: 'workflowEditor.action.operations.INVOKE' },
];

const ActionForm: React.FC<{
  data: ActionData;
  onChange: (data: ActionData) => void;
}> = ({ data, onChange }) => {
  const { t } = useTranslation();

  const addRow = () => {
    onChange({
      ...data,
      actions: [
        ...data.actions,
        { id: crypto.randomUUID(), operation: 'SET', target: '', payload: '' },
      ],
    });
  };

  const removeRow = (id: string) => {
    onChange({
      ...data,
      actions: data.actions.filter((a) => a.id !== id),
    });
  };

  const updateRow = (id: string, patch: Partial<(typeof data.actions)[0]>) => {
    onChange({
      ...data,
      actions: data.actions.map((a) => (a.id === id ? { ...a, ...patch } : a)),
    });
  };

  return (
    <div className="space-y-3">
      <Label className="text-xs font-semibold">{t('workflowEditor.action.title')}</Label>

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

      <Button variant="outline" size="sm" className="w-full h-7 text-xs" onClick={addRow}>
        <Plus className="h-3 w-3 mr-1" />
        {t('workflowEditor.action.addAction')}
      </Button>
    </div>
  );
};

// ──────────────────────────────────────
// 정책 폼
// ──────────────────────────────────────

const PolicyForm: React.FC<{
  data: PolicyData;
  onChange: (data: PolicyData) => void;
}> = ({ data, onChange }) => {
  const { t } = useTranslation();
  return (
  <div className="space-y-3">
    <Label className="text-xs font-semibold">{t('workflowEditor.policy.title')}</Label>

    <div className="space-y-1">
      <Label className="text-xs">{t('workflowEditor.policy.targetService')}</Label>
      <Select
        value={data.targetService || '__none'}
        onValueChange={(v) => onChange({ ...data, targetService: v === '__none' ? '' : v })}
      >
        <SelectTrigger className="h-8 text-xs">
          <SelectValue placeholder={t('workflowEditor.policy.targetService')} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__none" className="text-xs">---</SelectItem>
          <SelectItem value="core" className="text-xs">Core</SelectItem>
          <SelectItem value="synapse" className="text-xs">Synapse</SelectItem>
          <SelectItem value="weaver" className="text-xs">Weaver</SelectItem>
          <SelectItem value="oracle" className="text-xs">Oracle</SelectItem>
          <SelectItem value="vision" className="text-xs">Vision</SelectItem>
        </SelectContent>
      </Select>
    </div>

    <div className="space-y-1">
      <Label className="text-xs">{t('workflowEditor.policy.command')}</Label>
      <Input
        value={data.command}
        onChange={(e) => onChange({ ...data, command: e.target.value })}
        className="h-8 text-xs"
        placeholder="예: recalculate_kpi"
      />
    </div>

    <div className="space-y-1">
      <Label className="text-xs">{t('workflowEditor.policy.parameters')}</Label>
      <Input
        value={data.parameters}
        onChange={(e) => onChange({ ...data, parameters: e.target.value })}
        className="h-8 text-xs font-mono"
        placeholder='{}'
      />
    </div>

    <div className="grid grid-cols-2 gap-2">
      <div className="space-y-1">
        <Label className="text-xs">{t('workflowEditor.policy.retryCount')}</Label>
        <Input
          type="number"
          value={data.retryCount}
          onChange={(e) => onChange({ ...data, retryCount: parseInt(e.target.value) || 0 })}
          className="h-8 text-xs"
          min={0}
          max={10}
        />
      </div>
      <div className="space-y-1">
        <Label className="text-xs">{t('workflowEditor.policy.timeoutMs')}</Label>
        <Input
          type="number"
          value={data.timeoutMs}
          onChange={(e) => onChange({ ...data, timeoutMs: parseInt(e.target.value) || 5000 })}
          className="h-8 text-xs"
          min={1000}
          step={1000}
        />
      </div>
    </div>
  </div>
  );
};

// ──────────────────────────────────────
// 게이트웨이 폼
// ──────────────────────────────────────

// 게이트웨이 모드 키 (desc는 런타임에 t()로 번역)
const GATEWAY_MODE_KEYS: { value: GatewayMode; label: string; descKey: string }[] = [
  { value: 'AND', label: 'AND', descKey: 'workflowEditor.gateway.modes.AND' },
  { value: 'OR', label: 'OR', descKey: 'workflowEditor.gateway.modes.OR' },
  { value: 'XOR', label: 'XOR', descKey: 'workflowEditor.gateway.modes.XOR' },
];

const GatewayForm: React.FC<{
  data: GatewayData;
  onChange: (data: GatewayData) => void;
}> = ({ data, onChange }) => {
  const { t } = useTranslation();
  return (
  <div className="space-y-3">
    <Label className="text-xs font-semibold">{t('workflowEditor.gateway.title')}</Label>

    <div className="space-y-1">
      <Label className="text-xs">{t('workflowEditor.gateway.mode')}</Label>
      <Select
        value={data.mode}
        onValueChange={(v) => onChange({ mode: v as GatewayMode })}
      >
        <SelectTrigger className="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {GATEWAY_MODE_KEYS.map((m) => (
            <SelectItem key={m.value} value={m.value} className="text-xs">
              <span className="font-mono font-bold mr-1">{m.label}</span>
              <span className="text-muted-foreground">— {t(m.descKey)}</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  </div>
  );
};
