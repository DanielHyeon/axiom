// features/process-designer/components/property-panel/MeasureBindingPanel.tsx
// 측정값 바인딩 — measure 노드 전용 (설계 §4.2)

import type { MeasureBindingData } from '../../types/processDesigner';

interface MeasureBindingPanelProps {
 binding: MeasureBindingData | undefined;
 onUpdate: (binding: MeasureBindingData) => void;
}

export function MeasureBindingPanel({ binding, onUpdate }: MeasureBindingPanelProps) {
 const b = binding ?? {};

 const update = (field: keyof MeasureBindingData, value: string | undefined) => {
 onUpdate({ ...b, [field]: value });
 };

 return (
 <section className="space-y-3">
 <h3 className="text-xs text-foreground0 uppercase tracking-wider">측정값 바인딩</h3>

 <div>
 <label className="text-xs text-foreground0 block mb-1">KPI ID</label>
 <input
 type="text"
 value={b.kpiId ?? ''}
 onChange={(e) => update('kpiId', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-white"
 placeholder="KPI 연동 예정"
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">공식 (Formula)</label>
 <input
 type="text"
 value={b.formula ?? ''}
 onChange={(e) => update('formula', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-white font-mono"
 placeholder="예: count(완료) / count(요청)"
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">단위 (Unit)</label>
 <input
 type="text"
 value={b.unit ?? ''}
 onChange={(e) => update('unit', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-white"
 placeholder="%, 건, 시간"
 />
 </div>
 </section>
 );
}
