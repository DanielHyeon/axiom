// features/process-designer/components/property-panel/EventLogBindingPanel.tsx
// 이벤트 로그 바인딩 — eventLogBinding 노드 전용 (설계 §4.3)

import { useTranslation } from 'react-i18next';
import type { EventLogBindingData } from '../../types/processDesigner';

interface EventLogBindingPanelProps {
 binding: EventLogBindingData | undefined;
 onUpdate: (binding: EventLogBindingData) => void;
}

export function EventLogBindingPanel({ binding, onUpdate }: EventLogBindingPanelProps) {
 const { t } = useTranslation();
 const b: Partial<EventLogBindingData> = binding ?? {};

 const update = (field: keyof EventLogBindingData, value: string | undefined) => {
 onUpdate({
 sourceTable: b.sourceTable ?? '',
 timestampColumn: b.timestampColumn ?? '',
 caseIdColumn: b.caseIdColumn ?? '',
 ...b,
 [field]: value ?? '',
 });
 };

 return (
 <section className="space-y-3">
 <h3 className="text-xs text-foreground0 uppercase tracking-wider">{t('processDesignerExt.eventLog.title')}</h3>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{t('processDesignerExt.eventLog.sourceTable')}</label>
 <input
 type="text"
 value={b.sourceTable ?? ''}
 onChange={(e) => update('sourceTable', e.target.value)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground font-mono"
 placeholder={t('processDesignerExt.eventLog.weaverPlaceholder')}
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{t('processDesignerExt.eventLog.timestampCol')}</label>
 <input
 type="text"
 value={b.timestampColumn ?? ''}
 onChange={(e) => update('timestampColumn', e.target.value)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground font-mono"
 placeholder="timestamp"
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{t('processDesignerExt.eventLog.caseIdCol')}</label>
 <input
 type="text"
 value={b.caseIdColumn ?? ''}
 onChange={(e) => update('caseIdColumn', e.target.value)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground font-mono"
 placeholder="case_id"
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{t('processDesignerExt.eventLog.activityCol')}</label>
 <input
 type="text"
 value={b.activityColumn ?? ''}
 onChange={(e) => update('activityColumn', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground font-mono"
 placeholder="activity"
 />
 </div>

 <div>
 <label className="text-xs text-foreground0 block mb-1">{t('processDesignerExt.eventLog.filterSql')}</label>
 <input
 type="text"
 value={b.filter ?? ''}
 onChange={(e) => update('filter', e.target.value || undefined)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-primary-foreground font-mono"
 placeholder="status = 'completed'"
 />
 </div>
 </section>
 );
}
