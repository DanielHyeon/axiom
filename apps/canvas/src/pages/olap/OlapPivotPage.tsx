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
import { Loader2, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function OlapPivotPage() {
  const {
    cubeId, setCubeId, addFieldToZone,
    clearAll
  } = usePivotConfig();
  const { cubes, executeQuery, isQuerying, queryResult, error } = useOlapVision();
  const activeCube = cubes.find(c => c.id === cubeId) || null;

  const [activeItem, setActiveItem] = useState<{ item: Dimension | Measure, type: 'dimension' | 'measure' } | null>(null);
  const [chartViewType, setChartViewType] = useState<ChartViewType>('table');

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
    // Collect config and pass to execute
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
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-neutral-950 text-neutral-100">

      {/* Top Header Controls */}
      <div className="h-14 border-b border-neutral-800 bg-[#121212] px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <h1 className="font-semibold flex items-center gap-2">
            <span className="text-xl">📊</span> OLAP 피벗 분석
          </h1>
          <div className="h-6 w-px bg-neutral-800" />
          <div className="w-64">
            <Select
              value={cubeId || ''}
              onValueChange={(val) => { clearAll(); setCubeId(val); }}
            >
              <SelectTrigger className="h-8 bg-neutral-900 border-neutral-700 text-sm">
                <SelectValue placeholder="큐브 선택..." />
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
            <div className="flex-[1.5] bg-[#1a1a1a] p-6 relative overflow-y-auto">
              <div className="flex justify-between items-end mb-4">
                <h3 className="text-sm font-semibold text-neutral-300">분석 결과</h3>
                {queryResult && (
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-neutral-500">
                      쿼리 시간: {queryResult.executionTimeMs}ms • 행: {queryResult.data.length}
                    </span>
                    <Button variant="outline" size="sm" className="h-7 text-xs">
                      <Download size={12} className="mr-1" /> CSV 내보내기
                    </Button>
                  </div>
                )}
              </div>

              <div className="mb-2">
                <DrilldownBreadcrumb />
              </div>

              {isQuerying ? (
                <div className="absolute inset-0 bg-black/40 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
                  <Loader2 className="animate-spin text-indigo-500 mb-2" size={32} />
                  <p className="text-sm text-neutral-300">데이터를 집계하고 있습니다...</p>
                </div>
              ) : null}

              {error && (
                <div className="bg-red-950/30 border border-red-900/50 rounded-md p-4 mt-2">
                  <p className="text-sm text-red-400 font-medium">{error}</p>
                </div>
              )}

              {queryResult && !error && (
                <ChartSwitcher
                  viewType={chartViewType}
                  onViewChange={setChartViewType}
                  headers={queryResult.headers}
                  data={queryResult.data}
                  tableComponent={
                    <div className="border border-neutral-800 rounded-md overflow-hidden bg-neutral-900">
                      <DataTable columns={tableColumns} data={tableData} />
                    </div>
                  }
                />
              )}

              {!queryResult && !error && !isQuerying && (
                <div className="h-32 flex items-center justify-center text-neutral-400 text-sm italic">
                  조건을 구성하고 "분석 실행"을 클릭하세요.
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
