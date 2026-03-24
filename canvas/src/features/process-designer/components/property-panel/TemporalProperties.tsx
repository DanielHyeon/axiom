// features/process-designer/components/property-panel/TemporalProperties.tsx
// 시간축 속성 — businessEvent, businessAction 전용 (설계 §4.1)

import { useTranslation } from 'react-i18next';
import type { TemporalData } from '../../types/processDesigner';

interface TemporalPropertiesProps {
 temporal: TemporalData | undefined;
 onUpdate: (temporal: TemporalData) => void;
}

function computeStatus(t: TemporalData): 'ok' | 'warning' | 'violation' | undefined {
 if (t.actualAvg == null || t.expectedDuration == null || t.sla == null) return undefined;
 if (t.actualAvg <= t.expectedDuration) return 'ok';
 if (t.actualAvg <= t.sla) return 'warning';
 return 'violation';
}

const STATUS_STYLES: Record<string, string> = {
 ok: 'bg-green-900/50 text-green-300 border-green-700',
 warning: 'bg-amber-900/50 text-amber-300 border-amber-700',
 violation: 'bg-red-900/50 text-red-300 border-red-700',
};

const STATUS_LABEL_KEYS: Record<string, string> = {
 ok: 'processDesignerExt.temporal.slaOk',
 warning: 'processDesignerExt.temporal.slaWarning',
 violation: 'processDesignerExt.temporal.slaViolation',
};

export function TemporalProperties({ temporal, onUpdate }: TemporalPropertiesProps) {
 const { t: tr } = useTranslation();
 const td = temporal ?? {};
 const status = computeStatus(td as TemporalData);

 const update = (field: keyof TemporalData, value: number | undefined) => {
 onUpdate({ ...td, [field]: value });
 };

 return (
 <section className="space-y-3">
 <h3 className="text-xs text-foreground0 uppercase tracking-wider">{tr('processDesignerExt.temporal.title')}</h3>

 <div className="grid grid-cols-2 gap-2">
 <div>
 <label className="text-xs text-foreground0 block mb-1">{tr('processDesignerExt.temporal.expectedDuration')}</label>
 <input
 type="number"
 value={td.expectedDuration ?? ''}
 onChange={(e) => update('expectedDuration', e.target.value ? Number(e.target.value) : undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1 text-sm text-primary-foreground"
 placeholder="—"
 />
 </div>
 <div>
 <label className="text-xs text-foreground0 block mb-1">SLA (min)</label>
 <input
 type="number"
 value={td.sla ?? ''}
 onChange={(e) => update('sla', e.target.value ? Number(e.target.value) : undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1 text-sm text-primary-foreground"
 placeholder="—"
 />
 </div>
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{tr('processDesignerExt.temporal.actualAvg')}</label>
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">
 {td.actualAvg != null ? `${td.actualAvg}` : tr('processDesignerExt.temporal.noMiningResult')}
 </div>
 </div>

 {status && (
 <div className={`text-xs px-2 py-1 rounded border ${STATUS_STYLES[status]}`}>
 {tr(STATUS_LABEL_KEYS[status])}
 </div>
 )}
 </section>
 );
}
