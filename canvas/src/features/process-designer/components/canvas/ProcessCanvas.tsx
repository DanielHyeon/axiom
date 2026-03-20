// @ts-nocheck
// features/process-designer/components/canvas/ProcessCanvas.tsx
// 캔버스 영역 — Stage + Layer + 노드/연결선 렌더링 + 인터랙션 (설계 §1-§3, §8, §10)

import { useRef, useState, useEffect, useCallback } from 'react';
import { Stage, Layer, Group, Rect } from 'react-konva';
import { CanvasNode } from './CanvasNode';
import { ContextBoxNode } from './ContextBoxNode';
import { ConnectionLine } from './ConnectionLine';
import { PendingConnectionLine } from './PendingConnectionLine';
import { SelectionRect } from './SelectionRect';
import { InlineLabelEditor } from './InlineLabelEditor';
import { CollaboratorCursors } from './CollaboratorCursors';
import { CollaborationIndicator } from './CollaborationIndicator';
import { ConformanceOverlay } from '../mining/ConformanceOverlay';
import { NODE_CONFIGS } from '../../utils/nodeConfig';
import { useCanvasDataStore } from '../../store/canvasDataStore';
import { useProcessDesignerUIStore } from '../../store/useProcessDesignerStore';
import { useCanvasKeyboard } from '../../hooks/useCanvasKeyboard';
import { useConnectionDraw } from '../../hooks/useConnectionDraw';
import { useCanvasPanning } from '../../hooks/useCanvasPanning';
import { useRubberBandSelect } from '../../hooks/useRubberBandSelect';
import type { CanvasItemType } from '../../types/processDesigner';
import type { ConformanceResult, BottleneckResult } from '../../api/processDesignerApi';

interface ProcessCanvasProps {
 /** 마이닝 오버레이 표시 여부 */
 overlayVisible?: boolean;
 conformance?: ConformanceResult | null;
 bottlenecks?: BottleneckResult | null;
 selectedVariant?: number | null;
 /** 읽기 전용 모드 — RBAC §12 */
 readOnly?: boolean;
}

export function ProcessCanvas({
 overlayVisible = false,
 conformance = null,
 bottlenecks = null,
 selectedVariant = null,
 readOnly = false,
}: ProcessCanvasProps = {}) {
 const containerRef = useRef<HTMLDivElement>(null);
 const [stageSize, setStageSize] = useState({ width: 800, height: 600 });

 // Data store
 const items = useCanvasDataStore((s) => s.items);
 const connections = useCanvasDataStore((s) => s.connections);
 const addItem = useCanvasDataStore((s) => s.addItem);
 const updateItemPosition = useCanvasDataStore((s) => s.updateItemPosition);
 const collaborators = useCanvasDataStore((s) => s.collaborators);
 const connected = useCanvasDataStore((s) => s.connected);
 const updateLocalCursor = useCanvasDataStore((s) => s.updateLocalCursor);

 // UI store
 const toolMode = useProcessDesignerUIStore((s) => s.toolMode);
 const setToolMode = useProcessDesignerUIStore((s) => s.setToolMode);
 const selectedItemIds = useProcessDesignerUIStore((s) => s.selectedItemIds);
 const selectedConnectionIds = useProcessDesignerUIStore((s) => s.selectedConnectionIds);
 const selectItem = useProcessDesignerUIStore((s) => s.selectItem);
 const selectConnection = useProcessDesignerUIStore((s) => s.selectConnection);
 const clearSelection = useProcessDesignerUIStore((s) => s.clearSelection);
 const setEditingNodeId = useProcessDesignerUIStore((s) => s.setEditingNodeId);
 const stageView = useProcessDesignerUIStore((s) => s.stageView);
 const setStageView = useProcessDesignerUIStore((s) => s.setStageView);
 const focusedNodeId = useProcessDesignerUIStore((s) => s.focusedNodeId);
 const modeAnnouncement = useProcessDesignerUIStore((s) => s.modeAnnouncement);

 // Hooks
 useCanvasKeyboard({ readOnly });
 const { isConnectMode, pendingConnection, handleNodeClickInConnectMode, updatePendingMousePos } = useConnectionDraw();
 const { cursorStyle, spaceHeld, onMouseDown: panMouseDown, onMouseMove: panMouseMove, onMouseUp: panMouseUp } = useCanvasPanning();
 const { selectionRect, onBackgroundMouseDown, onBackgroundMouseMove, onBackgroundMouseUp } = useRubberBandSelect(items);

 // Item lookup
 const itemMap = new Map(items.map((it) => [it.id, it]));

 // Resize observer
 useEffect(() => {
 const el = containerRef.current;
 if (!el) return;
 const ro = new ResizeObserver((entries) => {
 const { width, height } = entries[0].contentRect;
 setStageSize({ width, height });
 });
 ro.observe(el);
 return () => ro.disconnect();
 }, []);

 // Drop handler — toolbox → canvas
 const handleDrop = useCallback(
 (e: React.DragEvent) => {
 if (readOnly) return;
 e.preventDefault();
 const type = e.dataTransfer.getData('nodeType') as CanvasItemType;
 if (!type || !NODE_CONFIGS[type]) return;

 const el = containerRef.current;
 if (!el) return;
 const rect = el.getBoundingClientRect();

 const x = (e.clientX - rect.left - stageView.x) / stageView.scale;
 const y = (e.clientY - rect.top - stageView.y) / stageView.scale;

 const config = NODE_CONFIGS[type];
 addItem({
 type,
 x: x - config.defaultWidth / 2,
 y: y - config.defaultHeight / 2,
 width: config.defaultWidth,
 height: config.defaultHeight,
 label: `New ${config.label}`,
 color: config.color,
 });
 setToolMode('select');
 },
 [readOnly, addItem, stageView, setToolMode],
 );

 // Wheel zoom
 const handleWheel = useCallback(
 (e: { evt: WheelEvent }) => {
 e.evt.preventDefault();
 const scaleBy = 1.05;
 const oldScale = stageView.scale;
 const newScale = e.evt.deltaY > 0 ? oldScale / scaleBy : oldScale * scaleBy;
 const clampedScale = Math.min(Math.max(newScale, 0.1), 3);

 const el = containerRef.current;
 if (!el) return;
 const rect = el.getBoundingClientRect();
 const pointerX = e.evt.clientX - rect.left;
 const pointerY = e.evt.clientY - rect.top;

 const newX = pointerX - ((pointerX - stageView.x) / oldScale) * clampedScale;
 const newY = pointerY - ((pointerY - stageView.y) / oldScale) * clampedScale;

 setStageView({ x: newX, y: newY, scale: clampedScale });
 },
 [stageView, setStageView],
 );

 // Screen → canvas coordinate conversion
 const screenToCanvas = useCallback(
 (clientX: number, clientY: number) => {
 const el = containerRef.current;
 if (!el) return { x: 0, y: 0 };
 const rect = el.getBoundingClientRect();
 return {
 x: (clientX - rect.left - stageView.x) / stageView.scale,
 y: (clientY - rect.top - stageView.y) / stageView.scale,
 };
 },
 [stageView],
 );

 // Background click handler — click-to-add for node tool modes
 const handleBackgroundClick = useCallback(
 (e: { evt: MouseEvent }) => {
 if (spaceHeld) return;

 // Node-add mode: click on canvas to place node
 if (!readOnly && toolMode !== 'select' && toolMode !== 'connect') {
 const config = NODE_CONFIGS[toolMode];
 if (config) {
 const pos = screenToCanvas(e.evt.clientX, e.evt.clientY);
 addItem({
 type: toolMode,
 x: pos.x - config.defaultWidth / 2,
 y: pos.y - config.defaultHeight / 2,
 width: config.defaultWidth,
 height: config.defaultHeight,
 label: `New ${config.label}`,
 color: config.color,
 });
 setToolMode('select');
 return;
 }
 }

 clearSelection();
 },
 [readOnly, toolMode, spaceHeld, screenToCanvas, addItem, setToolMode, clearSelection],
 );

 // Stage mouse events — panning + rubber band
 const handleStageMouseDown = useCallback(
 (e: { evt: MouseEvent }) => {
 panMouseDown(e);
 if (!spaceHeld && toolMode === 'select') {
 const pos = screenToCanvas(e.evt.clientX, e.evt.clientY);
 onBackgroundMouseDown(pos.x, pos.y);
 }
 },
 [panMouseDown, spaceHeld, toolMode, screenToCanvas, onBackgroundMouseDown],
 );

 const handleStageMouseMove = useCallback(
 (e: { evt: MouseEvent }) => {
 panMouseMove(e);

 // Update rubber band
 if (toolMode === 'select' && !spaceHeld) {
 const pos = screenToCanvas(e.evt.clientX, e.evt.clientY);
 onBackgroundMouseMove(pos.x, pos.y);
 }

 // Update pending connection preview
 if (isConnectMode && pendingConnection) {
 const pos = screenToCanvas(e.evt.clientX, e.evt.clientY);
 updatePendingMousePos(pos.x, pos.y);
 }

 // Broadcast cursor position for collaboration
 {
 const pos = screenToCanvas(e.evt.clientX, e.evt.clientY);
 updateLocalCursor(pos.x, pos.y);
 }
 },
 [panMouseMove, toolMode, spaceHeld, screenToCanvas, onBackgroundMouseMove, isConnectMode, pendingConnection, updatePendingMousePos, updateLocalCursor],
 );

 const handleStageMouseUp = useCallback(
 (e: { evt: MouseEvent }) => {
 panMouseUp();
 onBackgroundMouseUp();
 },
 [panMouseUp, onBackgroundMouseUp],
 );

 // Node click — connect mode or select
 const handleNodeSelect = useCallback(
 (id: string, multi: boolean) => {
 if (isConnectMode && !readOnly) {
 const item = itemMap.get(id);
 if (item) handleNodeClickInConnectMode(item);
 return;
 }
 selectItem(id, multi);
 },
 [isConnectMode, readOnly, itemMap, handleNodeClickInConnectMode, selectItem],
 );

 const handleDragEnd = useCallback(
 (id: string, x: number, y: number) => {
 updateItemPosition(id, x, y);
 },
 [updateItemPosition],
 );

 // z-order: contextBoxes first
 const contextBoxes = items.filter((it) => it.type === 'contextBox');
 const otherItems = items.filter((it) => it.type !== 'contextBox');
 const selectedSet = new Set(selectedItemIds);
 const selectedConnSet = new Set(selectedConnectionIds);

 // Cursor
 let canvasCursor = 'default';
 if (cursorStyle) canvasCursor = cursorStyle;
 else if (isConnectMode) canvasCursor = 'crosshair';
 else if (toolMode !== 'select') canvasCursor = 'copy';

 // Pending connection source item
 const pendingSourceItem = pendingConnection ? itemMap.get(pendingConnection.sourceId) : undefined;

 return (
 <div
 ref={containerRef}
 className="flex-1 bg-background relative overflow-hidden"
 style={{ cursor: canvasCursor }}
 onDragOver={(e) => e.preventDefault()}
 onDrop={handleDrop}
 // ARIA: §10.3
 role="application"
 aria-label={`프로세스 디자이너 캔버스. 노드 ${items.length}개, 연결 ${connections.length}개${readOnly ? ' (읽기 전용)' : ''}`}
 aria-roledescription="프로세스 디자이너"
 >
 <Stage
 width={stageSize.width}
 height={stageSize.height}
 onWheel={handleWheel}
 onMouseDown={handleStageMouseDown}
 onMouseMove={handleStageMouseMove}
 onMouseUp={handleStageMouseUp}
 >
 <Layer>
 <Group
 x={stageView.x}
 y={stageView.y}
 scaleX={stageView.scale}
 scaleY={stageView.scale}
 >
 {/* Background — click handler */}
 <Rect
 x={-5000}
 y={-5000}
 width={10000}
 height={10000}
 listening
 onClick={handleBackgroundClick}
 />

 {/* Connections (below nodes) */}
 {connections.map((conn) => {
 const source = itemMap.get(conn.sourceId);
 const target = itemMap.get(conn.targetId);
 if (!source || !target) return null;
 return (
 <ConnectionLine
 key={conn.id}
 connection={conn}
 sourceItem={source}
 targetItem={target}
 selected={selectedConnSet.has(conn.id)}
 onClick={selectConnection}
 />
 );
 })}

 {/* Pending connection line */}
 {pendingConnection && pendingSourceItem && (
 <PendingConnectionLine
 pending={pendingConnection}
 sourceItem={pendingSourceItem}
 />
 )}

 {/* Mining overlay (below nodes, above connections) */}
 {overlayVisible && (
 <ConformanceOverlay
 items={items}
 bottlenecks={bottlenecks}
 conformance={conformance}
 selectedVariant={selectedVariant}
 />
 )}

 {/* contextBox (lower z-order) */}
 {contextBoxes.map((item) => (
 <ContextBoxNode
 key={item.id}
 item={item}
 selected={selectedSet.has(item.id)}
 focused={focusedNodeId === item.id}
 readOnly={readOnly}
 onSelect={handleNodeSelect}
 onDragEnd={handleDragEnd}
 onDblClick={readOnly ? undefined : setEditingNodeId}
 />
 ))}

 {/* Other nodes (upper z-order) */}
 {otherItems.map((item) => (
 <CanvasNode
 key={item.id}
 item={item}
 selected={selectedSet.has(item.id)}
 focused={focusedNodeId === item.id}
 readOnly={readOnly}
 onSelect={handleNodeSelect}
 onDragEnd={handleDragEnd}
 onDblClick={readOnly ? undefined : setEditingNodeId}
 />
 ))}

 {/* Collaborator cursors */}
 <CollaboratorCursors collaborators={collaborators} />

 {/* Rubber band selection rect */}
 <SelectionRect rect={selectionRect} />
 </Group>
 </Layer>
 </Stage>

 {/* Inline label editor (HTML overlay) — only in edit mode */}
 {!readOnly && <InlineLabelEditor stageView={stageView} />}

 {/* Empty canvas hint */}
 {items.length === 0 && (
 <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
 <div className="text-center text-foreground0">
 <p className="text-sm">
 {readOnly ? '캔버스가 비어 있습니다' : '도구 상자에서 노드를 드래그하여 배치하세요'}
 </p>
 {!readOnly && (
 <p className="text-xs mt-1 text-muted-foreground">또는 단축키 B, E, N, R, S, T, M, D 로 노드를 추가하세요</p>
 )}
 </div>
 </div>
 )}

 {/* Collaboration indicator */}
 <CollaborationIndicator collaborators={collaborators} connected={connected} />

 {/* Tool mode indicator */}
 {toolMode !== 'select' && (
 <div className="absolute top-3 left-3 bg-muted/90 text-foreground/80 px-3 py-1.5 rounded text-xs pointer-events-none">
 {toolMode === 'connect'
 ? '연결선 모드 (ESC로 취소)'
 : `${NODE_CONFIGS[toolMode]?.label ?? toolMode} 추가 모드 — 캔버스를 클릭하세요`}
 </div>
 )}

 {/* Read-only indicator */}
 {readOnly && (
 <div className="absolute bottom-3 left-3 bg-amber-900/80 text-amber-200 px-3 py-1.5 rounded text-xs pointer-events-none">
 읽기 전용 모드
 </div>
 )}

 {/* Screen reader: mode change announcements (§10.3) */}
 <div aria-live="assertive" className="sr-only">
 {modeAnnouncement}
 </div>
 </div>
 );
}
