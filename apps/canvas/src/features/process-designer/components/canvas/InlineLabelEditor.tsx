// @ts-nocheck
// features/process-designer/components/canvas/InlineLabelEditor.tsx
// 노드 더블클릭 시 인라인 텍스트 입력 오버레이 (설계 §2.6)

import { useEffect, useRef, useState } from 'react';
import type { CanvasItem, StageViewState } from '../../types/processDesigner';
import { useCanvasDataStore } from '../../store/canvasDataStore';
import { useProcessDesignerUIStore } from '../../store/useProcessDesignerStore';

interface InlineLabelEditorProps {
 stageView: StageViewState;
}

export function InlineLabelEditor({ stageView }: InlineLabelEditorProps) {
 const editingNodeId = useProcessDesignerUIStore((s) => s.editingNodeId);
 const setEditingNodeId = useProcessDesignerUIStore((s) => s.setEditingNodeId);
 const items = useCanvasDataStore((s) => s.items);
 const updateItem = useCanvasDataStore((s) => s.updateItem);

 const editingItem = editingNodeId
 ? items.find((it) => it.id === editingNodeId) ?? null
 : null;

 const [value, setValue] = useState('');
 const inputRef = useRef<HTMLInputElement>(null);

 // Sync value when editing starts
 useEffect(() => {
 if (editingItem) {
 setValue(editingItem.label);
 // Focus after next render
 requestAnimationFrame(() => inputRef.current?.select());
 }
 }, [editingItem]);

 if (!editingItem) return null;

 // Calculate screen position from canvas coordinates + stage view
 const screenX = editingItem.x * stageView.scale + stageView.x;
 const screenY = editingItem.y * stageView.scale + stageView.y;
 const screenW = editingItem.width * stageView.scale;
 const screenH = editingItem.height * stageView.scale;

 const commit = () => {
 if (editingItem && value.trim()) {
 updateItem(editingItem.id, { label: value.trim() });
 }
 setEditingNodeId(null);
 };

 const cancel = () => {
 setEditingNodeId(null);
 };

 return (
 <div
 className="absolute pointer-events-auto"
 style={{
 left: screenX,
 top: screenY,
 width: screenW,
 height: screenH,
 display: 'flex',
 alignItems: 'center',
 justifyContent: 'center',
 }}
 >
 <input
 ref={inputRef}
 type="text"
 value={value}
 onChange={(e) => setValue(e.target.value)}
 onKeyDown={(e) => {
 if (e.key === 'Enter') commit();
 if (e.key === 'Escape') cancel();
 e.stopPropagation();
 }}
 onBlur={commit}
 className="bg-white text-black text-center text-sm font-bold px-2 py-1 rounded border-2 border-blue-500 outline-none shadow-lg"
 style={{
 width: Math.max(60, screenW - 16),
 fontSize: Math.max(10, 13 * stageView.scale),
 }}
 />
 </div>
 );
}
