/**
 * GatewayForm — 게이트웨이 노드 속성 편집 폼
 *
 * 워크플로의 분기/합류 지점인 게이트웨이 노드를 설정한다.
 * 모드 선택: AND(모두 충족), OR(하나라도 충족), XOR(정확히 하나만 충족).
 */

import { useTranslation } from 'react-i18next';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { GatewayData, GatewayMode } from '../../types/workflowEditor.types';

// 게이트웨이 모드 키 (desc는 런타임에 t()로 번역)
const GATEWAY_MODE_KEYS: { value: GatewayMode; label: string; descKey: string }[] = [
  { value: 'AND', label: 'AND', descKey: 'workflowEditor.gateway.modes.AND' },
  { value: 'OR', label: 'OR', descKey: 'workflowEditor.gateway.modes.OR' },
  { value: 'XOR', label: 'XOR', descKey: 'workflowEditor.gateway.modes.XOR' },
];

interface GatewayFormProps {
  data: GatewayData;
  onChange: (data: GatewayData) => void;
}

export const GatewayForm: React.FC<GatewayFormProps> = ({ data, onChange }) => {
  const { t } = useTranslation();
  return (
    <div className="space-y-3">
      <Label className="text-xs font-semibold">{t('workflowEditor.gateway.title')}</Label>

      {/* 게이트웨이 모드 선택 */}
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
