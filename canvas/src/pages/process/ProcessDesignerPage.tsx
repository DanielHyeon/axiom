// ProcessDesignerPage — 조립 구조 (설계 §1 와이어프레임, §10 접근성, §12 RBAC)
// Toolbox | Canvas/TreeView | PropertyPanel + MiningPanel

import { useEffect, useCallback, useState, useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { usePermission } from '@/shared/hooks/usePermission';

import { ProcessToolbox } from '@/features/process-designer/components/toolbox/ProcessToolbox';
import { ProcessCanvas } from '@/features/process-designer/components/canvas/ProcessCanvas';
import { ProcessPropertyPanel } from '@/features/process-designer/components/property-panel/ProcessPropertyPanel';
import { ConnectionStatusBanner } from '@/features/process-designer/components/canvas/ConnectionStatusBanner';
import { MiningPanel } from '@/features/process-designer/components/mining/MiningPanel';
import { AiDiscoverDialog } from '@/features/process-designer/components/AiDiscoverDialog';
import { TreeView } from '@/features/process-designer/components/TreeView';
import { KeyboardShortcutsPanel } from '@/features/process-designer/components/KeyboardShortcutsPanel';
import { useCanvasDataStore } from '@/features/process-designer/store/canvasDataStore';
import { useProcessDesignerUIStore } from '@/features/process-designer/store/useProcessDesignerStore';
import { useProcessMining } from '@/features/process-designer/hooks/useProcessMining';
import { layoutDiscoveredProcess } from '@/features/process-designer/utils/autoLayout';
import type { EventLogBindingData } from '@/features/process-designer/types/processDesigner';
import type { DiscoveredProcess } from '@/features/process-designer/api/processDesignerApi';

import { Minimap } from './Minimap';

export function ProcessDesignerPage() {
 const { boardId } = useParams<{ boardId: string }>();
 const [searchParams] = useSearchParams();
 const fromOntology = searchParams.get('fromOntology');

 // RBAC (§12)
 const canEdit = usePermission('process:initiate');
 const canChat = usePermission('agent:chat');
 const canRunAI = canEdit && canChat;

 // Data store
 const items = useCanvasDataStore((s) => s.items);
 const connections = useCanvasDataStore((s) => s.connections);
 const loadBoard = useCanvasDataStore((s) => s.loadBoard);
 const saveBoard = useCanvasDataStore((s) => s.saveBoard);
 const connected = useCanvasDataStore((s) => s.connected);
 const wsEnabled = useCanvasDataStore((s) => s.wsEnabled);
 const clearBoard = useCanvasDataStore((s) => s.clearBoard);
 const addItem = useCanvasDataStore((s) => s.addItem);
 const addConnection = useCanvasDataStore((s) => s.addConnection);

 // UI store
 const selectedItemIds = useProcessDesignerUIStore((s) => s.selectedItemIds);
 const selectItem = useProcessDesignerUIStore((s) => s.selectItem);
 const stageView = useProcessDesignerUIStore((s) => s.stageView);
 const setStageView = useProcessDesignerUIStore((s) => s.setStageView);
 const viewMode = useProcessDesignerUIStore((s) => s.viewMode);
 const setViewMode = useProcessDesignerUIStore((s) => s.setViewMode);
 const shortcutsOpen = useProcessDesignerUIStore((s) => s.shortcutsOpen);
 const setShortcutsOpen = useProcessDesignerUIStore((s) => s.setShortcutsOpen);

 // Load board on mount, cleanup on unmount
 useEffect(() => {
 if (boardId) loadBoard(boardId);
 return () => clearBoard();
 }, [boardId, loadBoard, clearBoard]);

 // Selected item for property panel (first selected)
 const selectedNode = selectedItemIds.length > 0
 ? items.find((it) => it.id === selectedItemIds[0]) ?? null
 : null;

 // Collect event log bindings from all eventLogBinding nodes
 const bindings = useMemo<EventLogBindingData[]>(
 () =>
 items
 .filter((it) => it.type === 'eventLogBinding' && it.eventLogBinding)
 .map((it) => it.eventLogBinding!),
 [items],
 );

 // Process mining hook
 const mining = useProcessMining({
 boardId,
 bindings,
 });

 // Mining variant selection
 const [selectedVariant, setSelectedVariant] = useState<number | null>(null);

 // AI Discover dialog
 const [aiDiscoverOpen, setAiDiscoverOpen] = useState(false);

 const handleAiDiscover = useCallback(
 (result: DiscoveredProcess) => {
 const { items: newItems, connections: newConns } = layoutDiscoveredProcess(result);

 const idMap = new Map<string, string>();
 newItems.forEach((item, idx) => {
 const id = addItem(item);
 idMap.set(`__placeholder_${idx}`, id);
 });

 for (const conn of newConns) {
 const sourceId = idMap.get(conn.sourceId);
 const targetId = idMap.get(conn.targetId);
 if (sourceId && targetId) {
 addConnection({ ...conn, sourceId, targetId });
 }
 }
 },
 [addItem, addConnection],
 );

 const handleSaveBoard = useCallback(() => {
 if (boardId) saveBoard(boardId);
 }, [boardId, saveBoard]);

 // Minimap click → center viewport
 const handleMinimapClick = useCallback(
 (virtualX: number, virtualY: number) => {
 setStageView({
 x: -virtualX + 400,
 y: -virtualY + 300,
 });
 },
 [setStageView],
 );

 // TreeView: focus canvas on node (zoom to node position)
 const handleFocusCanvas = useCallback(
 (id: string) => {
 const item = items.find((it) => it.id === id);
 if (!item) return;
 setStageView({
 x: -item.x + 400,
 y: -item.y + 300,
 });
 setViewMode('canvas');
 },
 [items, setStageView, setViewMode],
 );

 return (
 <div className="flex flex-col h-[calc(100vh-4rem)] bg-background text-white overflow-hidden border-t border-border">
 <ConnectionStatusBanner connected={connected} wsEnabled={wsEnabled} />
 {fromOntology && (
 <div className="shrink-0 text-xs text-primary/80 bg-blue-950/50 border-b border-blue-800 px-3 py-1.5">
 온톨로지 연동: <span className="font-mono">{fromOntology}</span>
 </div>
 )}
 <div className="flex flex-1 min-h-0">
 {/* 1. Toolbox + Mining Panel */}
 <div className="w-64 border-r border-border bg-card flex flex-col">
 <div className="p-4 border-b border-border font-bold text-sm text-foreground/80 flex items-center justify-between gap-2">
 <span>도구 상자 (Toolbox)</span>
 <div className="flex items-center gap-2 shrink-0">
 {boardId && canEdit && (
 <button
 type="button"
 onClick={handleSaveBoard}
 className="rounded bg-success text-white px-2 py-1 text-xs font-medium"
 >
 저장
 </button>
 )}
 <Link
 to={ROUTES.PROCESS_DESIGNER.LIST}
 className="text-xs text-muted-foreground hover:text-foreground"
 >
 목록
 </Link>
 </div>
 </div>
 <div className="flex-1 overflow-auto">
 <ProcessToolbox disabled={!canEdit} />
 </div>

 {/* Mining panel (하단) */}
 <MiningPanel
 conformance={mining.conformance}
 bottlenecks={mining.bottlenecks}
 loading={mining.loading}
 error={mining.error}
 overlayVisible={mining.overlayVisible}
 onToggleOverlay={mining.toggleOverlay}
 onRefresh={mining.refresh}
 selectedVariant={selectedVariant}
 onSelectVariant={setSelectedVariant}
 />
 </div>

 {/* 2. Canvas / Tree View Area */}
 <div className="flex-1 relative flex flex-col">
 {/* View mode tabs (§10.1) */}
 <div className="shrink-0 flex items-center gap-1 px-3 py-1.5 bg-card border-b border-border">
 <div role="tablist" aria-label="뷰 전환" className="flex items-center gap-1">
 <button
 type="button"
 role="tab"
 aria-selected={viewMode === 'canvas' || undefined}
 onClick={() => setViewMode('canvas')}
 className={`px-3 py-1 text-xs rounded ${viewMode === 'canvas' ? 'bg-muted text-white' : 'text-muted-foreground hover:text-foreground'}`}
 >
 캔버스 뷰
 </button>
 <button
 type="button"
 role="tab"
 aria-selected={viewMode === 'tree' || undefined}
 onClick={() => setViewMode('tree')}
 className={`px-3 py-1 text-xs rounded ${viewMode === 'tree' ? 'bg-muted text-white' : 'text-muted-foreground hover:text-foreground'}`}
 >
 트리 뷰
 </button>
 </div>
 <span className="flex-1" />
 <button
 type="button"
 onClick={() => setShortcutsOpen(true)}
 className="text-[10px] text-foreground0 hover:text-foreground/80"
 aria-label="키보드 단축키 도움말"
 >
 Shift+?
 </button>
 </div>

 {/* Canvas view */}
 {viewMode === 'canvas' && (
 <div className="flex-1 relative">
 <ProcessCanvas
 overlayVisible={mining.overlayVisible}
 conformance={mining.conformance}
 bottlenecks={mining.bottlenecks}
 selectedVariant={selectedVariant}
 readOnly={!canEdit}
 />
 <Minimap
 nodes={items}
 stageSize={{ width: 800, height: 600 }}
 stageView={stageView}
 onViewportClick={handleMinimapClick}
 />

 {/* AI 프로세스 발견 버튼 (빈 캔버스 + 권한 있을 때만) */}
 {items.length === 0 && canRunAI && (
 <button
 type="button"
 onClick={() => setAiDiscoverOpen(true)}
 className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-primary hover:bg-primary text-white px-4 py-2 rounded text-sm font-medium shadow-lg"
 >
 AI 프로세스 발견
 </button>
 )}
 </div>
 )}

 {/* Tree view (§10.1) */}
 {viewMode === 'tree' && (
 <TreeView
 items={items}
 connections={connections}
 selectedItemIds={selectedItemIds}
 onSelectItem={(id) => selectItem(id, false)}
 onFocusCanvas={handleFocusCanvas}
 />
 )}
 </div>

 {/* 3. Property Panel */}
 <ProcessPropertyPanel selectedItem={selectedNode} readOnly={!canEdit} />
 </div>

 {/* AI Discover Dialog */}
 <AiDiscoverDialog
 open={aiDiscoverOpen}
 onClose={() => setAiDiscoverOpen(false)}
 onDiscover={handleAiDiscover}
 />

 {/* Keyboard Shortcuts Panel (§10.2) */}
 <KeyboardShortcutsPanel
 open={shortcutsOpen}
 onClose={() => setShortcutsOpen(false)}
 />
 </div>
 );
}
