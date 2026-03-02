// features/process-designer/hooks/useRubberBandSelect.ts
// 빈 캔버스 드래그 → 선택 사각형 → 교차 노드 다중 선택

import { useState, useCallback, useRef } from 'react';
import type { SelectionRectData } from '../components/canvas/SelectionRect';
import type { CanvasItem } from '../types/processDesigner';
import { useProcessDesignerUIStore } from '../store/useProcessDesignerStore';

export function useRubberBandSelect(items: CanvasItem[]) {
  const [selectionRect, setSelectionRect] = useState<SelectionRectData | null>(null);
  const startPoint = useRef<{ x: number; y: number } | null>(null);
  const selectItem = useProcessDesignerUIStore((s) => s.selectItem);
  const clearSelection = useProcessDesignerUIStore((s) => s.clearSelection);

  /** 빈 배경에서 mousedown */
  const onBackgroundMouseDown = useCallback((canvasX: number, canvasY: number) => {
    startPoint.current = { x: canvasX, y: canvasY };
    setSelectionRect(null);
  }, []);

  /** mousemove — 사각형 업데이트 */
  const onBackgroundMouseMove = useCallback((canvasX: number, canvasY: number) => {
    if (!startPoint.current) return;

    const sp = startPoint.current;
    const x = Math.min(sp.x, canvasX);
    const y = Math.min(sp.y, canvasY);
    const width = Math.abs(canvasX - sp.x);
    const height = Math.abs(canvasY - sp.y);

    // 최소 이동 거리 체크 (5px) — 작은 클릭은 무시
    if (width < 5 && height < 5) return;

    setSelectionRect({ x, y, width, height });
  }, []);

  /** mouseup — 교차 노드 선택 */
  const onBackgroundMouseUp = useCallback(() => {
    if (selectionRect) {
      const { x: rx, y: ry, width: rw, height: rh } = selectionRect;

      // AABB 교차 검사
      const intersecting = items.filter((item) => {
        return (
          item.x < rx + rw &&
          item.x + item.width > rx &&
          item.y < ry + rh &&
          item.y + item.height > ry
        );
      });

      if (intersecting.length > 0) {
        clearSelection();
        for (const item of intersecting) {
          selectItem(item.id, true);
        }
      }
    }

    startPoint.current = null;
    setSelectionRect(null);
  }, [selectionRect, items, clearSelection, selectItem]);

  /** cancel */
  const cancelRubberBand = useCallback(() => {
    startPoint.current = null;
    setSelectionRect(null);
  }, []);

  return {
    selectionRect,
    isSelecting: startPoint.current !== null,
    onBackgroundMouseDown,
    onBackgroundMouseMove,
    onBackgroundMouseUp,
    cancelRubberBand,
  };
}
