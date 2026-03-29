/**
 * OlapPivotPage — OLAP 피벗 분석 페이지
 *
 * .pen 디자인 사양:
 * - 레이아웃: 좌우 수평 분할
 * - LEFT: DimensionPalette (220px, 오른쪽 border)
 * - RIGHT: 피벗 영역 (fill, 16px 패딩, 16px gap)
 *   - Drop Zones row: 3개 동일 컬럼
 *   - Pivot Grid: 흰색 카드, 8px radius, border
 *     - 헤더 행: 36px, surface bg, 컬럼 라벨 우측 정렬
 *     - 데이터 행: 36px, JetBrains Mono 12px, 우측 정렬, 색상(green/red)
 */
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
  type DragStartEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { usePivotConfig } from '@/features/olap/store/usePivotConfig';
import { useOlapVision } from '@/features/olap/hooks/useOlapVision';
import { DimensionPalette } from './components/DimensionPalette';
import { PivotBuilder } from './components/PivotBuilder';
import { DraggableItem } from './components/DraggableItem';
import type { Dimension, Measure } from '@/features/olap/types/olap';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';

export function OlapPivotPage() {
  const { t } = useTranslation();
  const { cubeId, setCubeId, addFieldToZone, clearAll } = usePivotConfig();
  const { cubes, executeQuery, isQuerying, queryResult, error } = useOlapVision();
  const activeCube = cubes.find((c) => c.id === cubeId) || null;

  // 드래그 오버레이용 상태
  const [activeItem, setActiveItem] = useState<{
    item: Dimension | Measure;
    type: 'dimension' | 'measure';
  } | null>(null);

  // DnD 센서 설정
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveItem(event.active.data.current as typeof activeItem);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveItem(null);
    const { active, over } = event;
    if (!over) return;

    const activeData = active.data.current;
    const zone = over.id as string;

    // 드롭 존에 놓인 경우
    if (zone === 'rows' || zone === 'columns' || zone === 'measures') {
      // 타입 검증: 차원은 rows/columns만, 측정값은 measures만
      if (activeData?.type === 'dimension' && zone === 'measures') return;
      if (activeData?.type === 'measure' && zone !== 'measures') return;

      if (activeData?.item) {
        addFieldToZone(zone as 'rows' | 'columns' | 'measures', activeData.item);
      }
    }
  };

  // 쿼리 실행
  const handleRunQuery = () => {
    const config = usePivotConfig.getState();
    executeQuery(config);
  };

  // 결과 데이터를 그리드 형태로 변환
  const headers = queryResult?.headers ?? [];
  const rows = queryResult?.data ?? [];

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-background text-foreground overflow-hidden">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        {/* 좌측: 차원/측정값 팔레트 */}
        <DimensionPalette cube={activeCube} />

        {/* 우측: 피벗 영역 */}
        <div className="flex-1 flex flex-col gap-4 p-4 overflow-hidden">
          {/* 큐브 선택 드롭다운 (팔레트 위가 아니라 피벗 영역 상단) */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-64">
              <Select
                value={cubeId || ''}
                onValueChange={(val) => {
                  clearAll();
                  setCubeId(val);
                }}
              >
                <SelectTrigger className="h-8 bg-card border-border text-xs">
                  <SelectValue placeholder={t('olap.selectCube')} />
                </SelectTrigger>
                <SelectContent>
                  {cubes.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Drop Zones (3열) + 실행 버튼 */}
          <PivotBuilder onRunQuery={handleRunQuery} isQuerying={isQuerying} />

          {/* 피벗 그리드 — 흰색 카드, 8px radius, border */}
          <div className="flex-1 rounded-lg bg-card border border-border overflow-auto">
            {/* 로딩 상태 */}
            {isQuerying && (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="animate-spin text-accent-blue" size={24} />
                <span className="ml-2 text-sm text-text-secondary">{t('olap.aggregating')}</span>
              </div>
            )}

            {/* 에러 상태 */}
            {error && !isQuerying && (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-red-500">{error}</p>
              </div>
            )}

            {/* 결과 그리드 */}
            {queryResult && !isQuerying && !error && (
              <table className="w-full border-collapse">
                {/* 헤더 행: 36px, surface bg, 컬럼 라벨 */}
                <thead>
                  <tr className="bg-muted h-9">
                    {headers.map((h, i) => (
                      <th
                        key={i}
                        className={[
                          'px-4 text-[11px] font-semibold text-text-secondary whitespace-nowrap',
                          i === 0 ? 'text-left' : 'text-right',
                        ].join(' ')}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, ri) => (
                    <tr
                      key={ri}
                      className="h-9 border-b border-border last:border-b-0"
                    >
                      {row.map((cell, ci) => {
                        // 숫자 셀: 색상 적용 (양수=green, 음수=red)
                        const isFirstCol = ci === 0;
                        const numVal = typeof cell === 'number' ? cell : parseFloat(String(cell));
                        const isNumber = !isFirstCol && !isNaN(numVal);
                        let textColor = 'text-foreground';
                        if (isNumber && String(cell).includes('-')) {
                          textColor = 'text-destructive'; // 빨강 — 다크모드 대응
                        }

                        return (
                          <td
                            key={ci}
                            className={[
                              'px-4 whitespace-nowrap',
                              isFirstCol
                                ? 'text-xs font-medium text-foreground'
                                : `text-xs font-mono ${textColor} text-right`,
                            ].join(' ')}
                          >
                            {cell == null ? '' : String(cell)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* 빈 상태 */}
            {!queryResult && !error && !isQuerying && (
              <div className="flex items-center justify-center h-full">
                <p className="text-sm text-text-placeholder italic">{t('olap.emptyHint')}</p>
              </div>
            )}
          </div>
        </div>

        {/* 드래그 오버레이 */}
        <DragOverlay>
          {activeItem ? (
            <div className="opacity-90 scale-105 pointer-events-none">
              <DraggableItem item={activeItem.item} type={activeItem.type} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
