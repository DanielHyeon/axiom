// features/process-designer/components/property-panel/BasicProperties.tsx
// 기본 속성 섹션 — label, description, size, parentContextBoxId (설계 §4, §12 RBAC)

import type { CanvasItem } from '../../types/processDesigner';
import { NODE_CONFIGS } from '../../utils/nodeConfig';

interface BasicPropertiesProps {
 item: CanvasItem;
 contextBoxes: CanvasItem[];
 onUpdate: (id: string, updates: Partial<CanvasItem>) => void;
 /** 읽기 전용 — input → 텍스트 표시 (§12) */
 readOnly?: boolean;
}

const readOnlyTextClass = 'text-sm px-2 py-1.5 bg-background rounded text-foreground/80 truncate';

export function BasicProperties({ item, contextBoxes, onUpdate, readOnly = false }: BasicPropertiesProps) {
 const config = NODE_CONFIGS[item.type];

 const parentBox = item.parentContextBoxId
 ? contextBoxes.find((cb) => cb.id === item.parentContextBoxId)
 : null;

 return (
 <section className="space-y-3">
 <h3 className="text-xs text-foreground0 uppercase tracking-wider">기본 속성</h3>

 {/* ID (always read-only) */}
 <Field label="ID">
 <div className="text-sm font-mono bg-background px-2 py-1 rounded text-muted-foreground truncate">
 {item.id}
 </div>
 </Field>

 {/* Type (always read-only) */}
 <Field label="Type">
 <div className="flex items-center gap-2 text-sm px-2 py-1 rounded bg-background text-foreground/80">
 <span
 className="w-3 h-3 rounded-sm shrink-0"
 style={{ backgroundColor: config?.color }}
 />
 {config?.label ?? item.type}
 </div>
 </Field>

 {/* Label */}
 <Field label="Label">
 {readOnly ? (
 <div className={readOnlyTextClass}>{item.label}</div>
 ) : (
 <input
 type="text"
 value={item.label}
 onChange={(e) => onUpdate(item.id, { label: e.target.value })}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-white"
 />
 )}
 </Field>

 {/* Description */}
 <Field label="Description">
 {readOnly ? (
 <div className={readOnlyTextClass}>{item.description || '—'}</div>
 ) : (
 <textarea
 value={item.description ?? ''}
 onChange={(e) => onUpdate(item.id, { description: e.target.value || undefined })}
 rows={2}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-white resize-none"
 placeholder="노드 설명을 입력하세요"
 />
 )}
 </Field>

 {/* Position (always read-only) */}
 <div className="grid grid-cols-2 gap-2">
 <Field label="X">
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">{Math.round(item.x)}</div>
 </Field>
 <Field label="Y">
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">{Math.round(item.y)}</div>
 </Field>
 </div>

 {/* Size */}
 <div className="grid grid-cols-2 gap-2">
 <Field label="Width">
 {readOnly ? (
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">{item.width}</div>
 ) : (
 <input
 type="number"
 value={item.width}
 onChange={(e) => onUpdate(item.id, { width: Math.max(40, Number(e.target.value)) })}
 aria-label="Width"
 className="w-full bg-muted border border-border rounded px-2 py-1 text-sm text-white"
 />
 )}
 </Field>
 <Field label="Height">
 {readOnly ? (
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">{item.height}</div>
 ) : (
 <input
 type="number"
 value={item.height}
 onChange={(e) => onUpdate(item.id, { height: Math.max(30, Number(e.target.value)) })}
 aria-label="Height"
 className="w-full bg-muted border border-border rounded px-2 py-1 text-sm text-white"
 />
 )}
 </Field>
 </div>

 {/* Parent Context Box (not for contextBox itself) */}
 {item.type !== 'contextBox' && contextBoxes.length > 0 && (
 <Field label="소속 Domain">
 {readOnly ? (
 <div className={readOnlyTextClass}>{parentBox?.label ?? '없음'}</div>
 ) : (
 <select
 value={item.parentContextBoxId ?? ''}
 onChange={(e) => onUpdate(item.id, { parentContextBoxId: e.target.value || null })}
 aria-label="소속 Domain"
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-white"
 >
 <option value="">없음</option>
 {contextBoxes.map((cb) => (
 <option key={cb.id} value={cb.id}>{cb.label}</option>
 ))}
 </select>
 )}
 </Field>
 )}
 </section>
 );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
 return (
 <div>
 <label className="text-xs text-foreground0 uppercase tracking-wider block mb-1">{label}</label>
 {children}
 </div>
 );
}
