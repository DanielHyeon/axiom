import { Checkbox } from '@/components/ui/checkbox';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import type { OntologyLayer } from '@/features/ontology/types/ontology';
import { useTranslation } from 'react-i18next';

// 5계층 온톨로지 필터 (Driver 추가: KPI > Driver > Measure > Process > Resource)
const LAYER_INFO: { id: OntologyLayer; label: string; color: string }[] = [
 { id: 'kpi', label: 'KPI', color: 'bg-destructive' },
 { id: 'driver', label: 'Driver', color: 'bg-amber-500' },
 { id: 'measure', label: 'Measure', color: 'bg-warning' },
 { id: 'process', label: 'Process', color: 'bg-primary' },
 { id: 'resource', label: 'Resource', color: 'bg-success' }
];

export function LayerFilter() {
  const { t } = useTranslation();
 const { filters, toggleLayer } = useOntologyStore();

 return (
 <div className="flex gap-4 items-center bg-muted p-2 rounded border border-border">
 <span className="text-[11px] text-foreground/60 font-mono mr-2">{t('ontologyPage.msg09c27f8d')}</span>
 {LAYER_INFO.map(layer => (
 <div key={layer.id} className="flex items-center space-x-2">
 <Checkbox
 id={`layer-${layer.id}`}
 checked={filters.layers.has(layer.id)}
 onCheckedChange={() => toggleLayer(layer.id)}
 />
 <label
 htmlFor={`layer-${layer.id}`}
 className="text-[13px] cursor-pointer flex items-center gap-1.5 text-muted-foreground font-heading"
 >
 <span className={`w-2.5 h-2.5 rounded-full ${layer.color}`} />
 {layer.label}
 </label>
 </div>
 ))}
 </div>
 );
}
