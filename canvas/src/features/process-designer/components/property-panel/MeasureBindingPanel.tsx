// features/process-designer/components/property-panel/MeasureBindingPanel.tsx
// 측정값 바인딩 — measure 노드 전용 (설계 §4.2)

import { useTranslation } from 'react-i18next';
import type { MeasureBindingData } from '../../types/processDesigner';

interface MeasureBindingPanelProps {
 binding: MeasureBindingData | undefined;
 onUpdate: (binding: MeasureBindingData) => void;
}

export function MeasureBindingPanel({ binding, onUpdate }: MeasureBindingPanelProps) {
 const { t } = useTranslation();
 const b = binding ?? {};

 const update = (field: keyof MeasureBindingData, value: string | undefined) => {
 onUpdate({ ...b, [field]: value });
 };

 return (
 <section className="space-y-3">
 <h3 className="text-xs text-foreground0 uppercase tracking-wider">{t('processDesignerExt.measure.title')}</h3>

 <div>
 <label className="text-xs text-foreground0 block mb-1">KPI ID</label>
 <input
 type="text"
 value={b.kpiId ?? ''}
 onChange={(e) => update('kpiId', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground"
 placeholder={t('processDesignerExt.measure.kpiPlaceholder')}
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{t('processDesignerExt.measure.formulaLabel')}</label>
 <input
 type="text"
 value={b.formula ?? ''}
 onChange={(e) => update('formula', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground font-mono"
 placeholder={t('processDesignerExt.measure.formulaPlaceholder')}
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{t('processDesignerExt.measure.unitLabel')}</label>
 <input
 type="text"
 value={b.unit ?? ''}
 onChange={(e) => update('unit', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground"
 placeholder={t('processDesignerExt.measure.unitPlaceholder')}
 />
 </div>
 </section>
 );
}
