/**
 * TriggerForm — 트리거 노드 속성 편집 폼
 *
 * 워크플로의 시작점인 트리거 노드를 설정한다.
 * 이벤트 유형(수동, 케이스 생성, 스케줄 등)에 따라
 * 추가 입력 필드(cron 표현식, webhook URL, KPI 임계값)가 표시된다.
 */

import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { TriggerData, TriggerEventType } from '../../types/workflowEditor.types';

// 트리거 이벤트 타입 키 (label은 런타임에 t()로 번역)
const TRIGGER_EVENT_KEYS: { value: TriggerEventType; labelKey: string }[] = [
  { value: 'manual', labelKey: 'workflowEditor.trigger.events.manual' },
  { value: 'case_created', labelKey: 'workflowEditor.trigger.events.case_created' },
  { value: 'case_updated', labelKey: 'workflowEditor.trigger.events.case_updated' },
  { value: 'kpi_threshold', labelKey: 'workflowEditor.trigger.events.kpi_threshold' },
  { value: 'schedule_cron', labelKey: 'workflowEditor.trigger.events.schedule_cron' },
  { value: 'webhook', labelKey: 'workflowEditor.trigger.events.webhook' },
];

interface TriggerFormProps {
  data: TriggerData;
  onChange: (data: TriggerData) => void;
}

export const TriggerForm: React.FC<TriggerFormProps> = ({ data, onChange }) => {
  const { t } = useTranslation();
  return (
    <div className="space-y-3">
      <Label className="text-xs font-semibold">{t('workflowEditor.trigger.title')}</Label>

      {/* 이벤트 유형 선택 */}
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

      {/* Webhook URL (webhook 전용) */}
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

      {/* KPI 임계값 설정 (kpi_threshold 전용) */}
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
