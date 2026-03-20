// features/process-designer/components/property-panel/TemporalProperties.tsx
// 시간축 속성 — businessEvent, businessAction 전용 (설계 §4.1)

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

const STATUS_LABELS: Record<string, string> = {
 ok: 'SLA 이내',
 warning: 'SLA 근접',
 violation: 'SLA 위반',
};

export function TemporalProperties({ temporal, onUpdate }: TemporalPropertiesProps) {
 const t = temporal ?? {};
 const status = computeStatus(t as TemporalData);

 const update = (field: keyof TemporalData, value: number | undefined) => {
 onUpdate({ ...t, [field]: value });
 };

 return (
 <section className="space-y-3">
 <h3 className="text-xs text-foreground0 uppercase tracking-wider">시간축 속성</h3>

 <div className="grid grid-cols-2 gap-2">
 <div>
 <label className="text-xs text-foreground0 block mb-1">예상 소요 (분)</label>
 <input
 type="number"
 value={t.expectedDuration ?? ''}
 onChange={(e) => update('expectedDuration', e.target.value ? Number(e.target.value) : undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1 text-sm text-white"
 placeholder="—"
 />
 </div>
 <div>
 <label className="text-xs text-foreground0 block mb-1">SLA (분)</label>
 <input
 type="number"
 value={t.sla ?? ''}
 onChange={(e) => update('sla', e.target.value ? Number(e.target.value) : undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1 text-sm text-white"
 placeholder="—"
 />
 </div>
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">실제 평균 (분)</label>
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">
 {t.actualAvg != null ? `${t.actualAvg}분` : '마이닝 결과 없음'}
 </div>
 </div>

 {status && (
 <div className={`text-xs px-2 py-1 rounded border ${STATUS_STYLES[status]}`}>
 {STATUS_LABELS[status]}
 </div>
 )}
 </section>
 );
}
