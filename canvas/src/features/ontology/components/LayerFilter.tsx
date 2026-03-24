/**
 * 온톨로지 계층 필터 — 5계층 체크박스.
 * Sprint 4b: KPI/Driver/Measure/Process/Resource 계층별 표시 토글.
 */

import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { useTranslation } from 'react-i18next';

const LAYERS = [
  { id: 'kpi', label: 'KPI', color: 'bg-destructive' },
  { id: 'driver', label: 'Driver', color: 'bg-warning' },
  { id: 'measure', label: 'Measure', color: 'bg-primary' },
  { id: 'process', label: 'Process', color: 'bg-success' },
  { id: 'resource', label: 'Resource', color: 'bg-accent' },
] as const;

export type LayerId = (typeof LAYERS)[number]['id'];

interface LayerFilterProps {
  activeLayers: Set<string>;
  onChange: (layers: Set<string>) => void;
}

export function LayerFilter({ activeLayers, onChange }: LayerFilterProps) {
  const { t } = useTranslation();
  const toggle = (layerId: string) => {
    const next = new Set(activeLayers);
    if (next.has(layerId)) next.delete(layerId);
    else next.add(layerId);
    onChange(next);
  };

  return (
    <div className="space-y-2">
      <span className="text-xs font-medium text-muted-foreground">{t('ontologyExt.wizard.layerFilter')}</span>
      {LAYERS.map((layer) => (
        <div key={layer.id} className="flex items-center gap-2">
          <Checkbox
            id={`layer-${layer.id}`}
            checked={activeLayers.has(layer.id)}
            onCheckedChange={() => toggle(layer.id)}
          />
          <div className={`w-2.5 h-2.5 rounded-full ${layer.color}`} />
          <Label htmlFor={`layer-${layer.id}`} className="text-sm cursor-pointer">
            {layer.label}
          </Label>
        </div>
      ))}
    </div>
  );
}
