/**
 * PolicyForm — 정책 노드 속성 편집 폼
 *
 * 워크플로에서 외부 서비스 호출을 정의하는 정책 노드를 설정한다.
 * 대상 서비스, 실행 커맨드, 파라미터, 재시도 횟수, 타임아웃을 구성.
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
import type { PolicyData } from '../../types/workflowEditor.types';

interface PolicyFormProps {
  data: PolicyData;
  onChange: (data: PolicyData) => void;
}

export const PolicyForm: React.FC<PolicyFormProps> = ({ data, onChange }) => {
  const { t } = useTranslation();
  return (
    <div className="space-y-3">
      <Label className="text-xs font-semibold">{t('workflowEditor.policy.title')}</Label>

      {/* 대상 서비스 선택 */}
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

      {/* 실행 커맨드 입력 */}
      <div className="space-y-1">
        <Label className="text-xs">{t('workflowEditor.policy.command')}</Label>
        <Input
          value={data.command}
          onChange={(e) => onChange({ ...data, command: e.target.value })}
          className="h-8 text-xs"
          placeholder="예: recalculate_kpi"
        />
      </div>

      {/* JSON 파라미터 입력 */}
      <div className="space-y-1">
        <Label className="text-xs">{t('workflowEditor.policy.parameters')}</Label>
        <Input
          value={data.parameters}
          onChange={(e) => onChange({ ...data, parameters: e.target.value })}
          className="h-8 text-xs font-mono"
          placeholder='{}'
        />
      </div>

      {/* 재시도 횟수 + 타임아웃 */}
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
