// src/pages/olap/OlapPivotPage.tsx

import { useState } from 'react';
import {
 DndContext,
 type DragEndEvent,
 useSensor,
 useSensors,
 PointerSensor,
 KeyboardSensor,
 closestCenter,
 DragOverlay,
 type DragStartEvent
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { usePivotConfig } from '@/features/olap/store/usePivotConfig';
import { useOlapVision } from '@/features/olap/hooks/useOlapVision';
import { DrilldownBreadcrumb } from '@/features/olap/components/DrilldownBreadcrumb';
import { ChartSwitcher, type ChartViewType } from '@/features/olap/components/ChartSwitcher';
import { DimensionPalette } from './components/DimensionPalette';
import { PivotBuilder } from './components/PivotBuilder';
import { DraggableItem } from './components/DraggableItem';
import { DataTable } from '@/components/shared/DataTable';
import type { Dimension, Measure } from '@/features/olap/types/olap';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { useTranslation } from 'react-i18next';
import { Loader2, Download, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function OlapPivotPage() {
 const { t } = useTranslation();
 const {
 cubeId, setCubeId, addFieldToZone,
 clearAll
 } = usePivotConfig();
 const { cubes, executeQuery, isQuerying, queryResult, error } = useOlapVision();
 const activeCube = cubes.find(c => c.id === cubeId) || null;

 const [activeItem, setActiveItem] = useState<{ item: Dimension | Measure, type: 'dimension' | 'measure' } | null>(null);
 const [chartViewType, setChartViewType] = useState<ChartViewType>('table');
 // 에러 배너 닫기 상태
 const [errorDismissed, setErrorDismissed] = useState(false);

 // Auto-run query if config changes and valid? We use explicit "run query" button as per spec.

 const sensors = useSensors(
 useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
 useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
 );

 const handleDragStart = (event: DragStartEvent) => {
 // eslint-disable-next-line @typescript-eslint/no-explicit-any
 setActiveItem(event.active.data.current as any);
 };

 const handleDragEnd = (event: DragEndEvent) => {
 setActiveItem(null);
 const { active, over } = event;

 if (!over) return;

 const activeData = active.data.current;

 // Dropped over a zone
 if (over.id === 'rows' || over.id === 'columns' || over.id === 'measures' || over.id === 'filters') {
 const zoneId = over.id as 'rows' | 'columns' | 'measures' | 'filters';

 // Validate drop rules
 if (activeData?.type === 'dimension' && zoneId === 'measures') return;
 if (activeData?.type === 'measure' && zoneId !== 'measures') return;

 if (activeData?.item) {
 addFieldToZone(zoneId, activeData.item);
 }
 }
 // Reordering inside a zone (Sortable)
 else {
 // Logic for reordering if dropping onto another sortable item
 const activeZone = String(active.id).split('-')[0];
 const overZone = String(over.id).split('-')[0];

 if (activeZone === overZone && ['rows', 'columns', 'measures', 'filters'].includes(activeZone)) {
 // Need to find indices in the corresponding state array
 // A robust DnD implementation tracks local sortable list state. 
 // For simplicity here, we assume it's appended by drop if cross-zone is tricky
 // This is a minimal mock implementation.
 }
 }
 };

 const handleRunQuery = () => {
 // 새 쿼리 실행 시 이전 에러 배너 닫기 상태 초기화
 setErrorDismissed(false);
 const config = usePivotConfig.getState();
 executeQuery(config);
 };

 // Convert array data to TanStack table columns
 const tableColumns = queryResult?.headers.map((h, i) => ({
 accessorKey: `col_${i}`,
 header: h
 })) || [];

 const tableData = queryResult?.data.map((row) => {
 // eslint-disable-next-line @typescript-eslint/no-explicit-any
 const obj: any = {};
 row.forEach((cell, i) => {
 obj[`col_${i}`] = cell;
 });
 return obj;
 }) || [];

 return (
 <div className="flex flex-col h-[calc(100vh-4rem)] bg-background text-foreground">

 {/* Top Header Controls */}
 <div className="h-14 border-b border-border bg-[#121212] px-6 flex items-center justify-between shrink-0">
 <div className="flex items-center gap-4">
 <h1 className="font-semibold flex items-center gap-2">
 <span className="text-xl">📊</span> {t('olap.title')}
 </h1>
 <div className="h-6 w-px bg-muted" />
 <div className="w-64">
 <Select
 value={cubeId || ''}
 onValueChange={(val) => { clearAll(); setCubeId(val); }}
 >
 <SelectTrigger className="h-8 bg-card border-border text-sm">
 <SelectValue placeholder={t('olap.selectCube')} />
 </SelectTrigger>
 <SelectContent>
 {cubes.map(c => (
 <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
 ))}
 </SelectContent>
 </Select>
 </div>
 </div>
 </div>

 {/* Main Body Layout */}
 <div className="flex flex-1 overflow-hidden">
 <DndContext
 sensors={sensors}
 collisionDetection={closestCenter}
 onDragStart={handleDragStart}
 onDragEnd={handleDragEnd}
 >
 {/* Left Palette */}
 <DimensionPalette cube={activeCube} />

 {/* Middle Builder & Right Result */}
 <div className="flex-1 flex flex-col relative w-full overflow-hidden">
 {/* Top half: Builder */}
 <PivotBuilder onRunQuery={handleRunQuery} isQuerying={isQuerying} />

 {/* Bottom half: Results */}
 <div className="flex-[1.5] bg-popover p-6 relative overflow-y-auto">
 <div className="flex justify-between items-end mb-4">
 <h3 className="text-sm font-semibold text-foreground/80">{t('olap.analysisResult')}</h3>
 {queryResult && (
 <div className="flex items-center gap-4">
 <span className="text-xs text-foreground0">
 {t('olap.queryTime', { time: queryResult.executionTimeMs })} • {t('olap.rowCount', { count: queryResult.data.length })}
 </span>
 <Button variant="outline" size="sm" className="h-7 text-xs">
 <Download size={12} className="mr-1" /> {t('olap.csvExport')}
 </Button>
 </div>
 )}
 </div>

 <div className="mb-2">
 <DrilldownBreadcrumb />
 </div>

 {isQuerying ? (
 <div className="absolute inset-0 bg-sidebar/40 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
 <Loader2 className="animate-spin text-primary mb-2" size={32} />
 <p className="text-sm text-foreground/80">{t('olap.aggregating')}</p>
 </div>
 ) : null}

 {error && !errorDismissed && (
 <div className="bg-red-950/30 border border-red-900/50 rounded-md p-4 mt-2 flex items-start justify-between gap-2">
 <p className="text-sm text-destructive font-medium">{error}</p>
 <button
   type="button"
   onClick={() => setErrorDismissed(true)}
   className="shrink-0 p-0.5 rounded text-destructive/60 hover:text-destructive transition-colors"
   aria-label="에러 배너 닫기"
 >
   <X className="h-4 w-4" />
 </button>
 </div>
 )}

 {queryResult && !error && (
 <ChartSwitcher
 viewType={chartViewType}
 onViewChange={setChartViewType}
 headers={queryResult.headers}
 data={queryResult.data}
 tableComponent={
 <div className="border border-border rounded-md overflow-hidden bg-card">
 <DataTable columns={tableColumns} data={tableData} />
 </div>
 }
 />
 )}

 {!queryResult && !error && !isQuerying && (
 <div className="h-32 flex items-center justify-center text-muted-foreground text-sm italic">
 {t('olap.emptyHint')}
 </div>
 )}
 </div>
 </div>

 <DragOverlay>
 {activeItem ? (
 <div className="opacity-90 scale-105 pointer-events-none">
 <DraggableItem item={activeItem.item} type={activeItem.type} />
 </div>
 ) : null}
 </DragOverlay>

 </DndContext>
 </div>
 </div>
 );
}
