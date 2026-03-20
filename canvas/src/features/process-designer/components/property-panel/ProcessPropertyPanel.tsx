// features/process-designer/components/property-panel/ProcessPropertyPanel.tsx
// 속성 패널 컨테이너 — 노드 타입별 조건부 서브 패널 (설계 §4, §12 RBAC)

import { useCallback } from 'react';
import type { CanvasItem, TemporalData, MeasureBindingData, EventLogBindingData } from '../../types/processDesigner';
import { useCanvasDataStore } from '../../store/canvasDataStore';
import { BasicProperties } from './BasicProperties';
import { TemporalProperties } from './TemporalProperties';
import { MeasureBindingPanel } from './MeasureBindingPanel';
import { EventLogBindingPanel } from './EventLogBindingPanel';

interface ProcessPropertyPanelProps {
 selectedItem: CanvasItem | null;
 /** 읽기 전용 모드 — input → 텍스트 표시 */
 readOnly?: boolean;
}

const TEMPORAL_TYPES = new Set(['businessEvent', 'businessAction']);

// No-op handler for read-only mode
const NOOP_UPDATE = () => {};

export function ProcessPropertyPanel({ selectedItem, readOnly = false }: ProcessPropertyPanelProps) {
 const items = useCanvasDataStore((s) => s.items);
 const updateItem = useCanvasDataStore((s) => s.updateItem);

 const contextBoxes = items.filter((it) => it.type === 'contextBox');

 const handleUpdate = useCallback(
 (id: string, updates: Partial<CanvasItem>) => {
 if (readOnly) return;
 updateItem(id, updates);
 },
 [readOnly, updateItem],
 );

 const handleTemporalUpdate = useCallback(
 (temporal: TemporalData) => {
 if (readOnly || !selectedItem) return;
 updateItem(selectedItem.id, { temporal });
 },
 [readOnly, selectedItem, updateItem],
 );

 const handleMeasureUpdate = useCallback(
 (measureBinding: MeasureBindingData) => {
 if (readOnly || !selectedItem) return;
 updateItem(selectedItem.id, { measureBinding });
 },
 [readOnly, selectedItem, updateItem],
 );

 const handleEventLogUpdate = useCallback(
 (eventLogBinding: EventLogBindingData) => {
 if (readOnly || !selectedItem) return;
 updateItem(selectedItem.id, { eventLogBinding });
 },
 [readOnly, selectedItem, updateItem],
 );

 return (
 <div className="w-80 border-l border-border bg-card flex flex-col">
 <div className="p-4 border-b border-border font-bold text-sm text-foreground/80 flex items-center justify-between">
 <span>속성 패널 (Property Panel)</span>
 {readOnly && (
 <span className="text-[10px] text-warning bg-amber-900/40 px-1.5 py-0.5 rounded">읽기 전용</span>
 )}
 </div>
 <div className="p-4 flex-1 overflow-auto">
 {selectedItem ? (
 <div className="space-y-5">
 <BasicProperties
 item={selectedItem}
 contextBoxes={contextBoxes}
 onUpdate={handleUpdate}
 readOnly={readOnly}
 />

 {/* businessEvent, businessAction → 시간축 */}
 {TEMPORAL_TYPES.has(selectedItem.type) && (
 <TemporalProperties
 temporal={selectedItem.temporal}
 onUpdate={readOnly ? NOOP_UPDATE : handleTemporalUpdate}
 />
 )}

 {/* measure → 측정값 바인딩 */}
 {selectedItem.type === 'measure' && (
 <MeasureBindingPanel
 binding={selectedItem.measureBinding}
 onUpdate={readOnly ? NOOP_UPDATE : handleMeasureUpdate}
 />
 )}

 {/* eventLogBinding → 로그 바인딩 */}
 {selectedItem.type === 'eventLogBinding' && (
 <EventLogBindingPanel
 binding={selectedItem.eventLogBinding}
 onUpdate={readOnly ? NOOP_UPDATE : handleEventLogUpdate}
 />
 )}
 </div>
 ) : (
 <div className="h-full flex items-center justify-center text-sm text-foreground0 text-center">
 캔버스에서 노드를 선택하여<br />속성을 확인하세요.
 </div>
 )}
 </div>
 </div>
 );
}
