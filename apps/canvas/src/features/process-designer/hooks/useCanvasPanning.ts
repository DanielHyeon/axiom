// features/process-designer/hooks/useCanvasPanning.ts
// Space+드래그 패닝 (설계 §2.4)

import { useState, useEffect, useCallback, useRef } from 'react';
import { useProcessDesignerUIStore } from '../store/useProcessDesignerStore';

export function useCanvasPanning() {
  const [isPanning, setIsPanning] = useState(false);
  const [spaceHeld, setSpaceHeld] = useState(false);
  const lastPos = useRef<{ x: number; y: number } | null>(null);

  const stageView = useProcessDesignerUIStore((s) => s.stageView);
  const setStageView = useProcessDesignerUIStore((s) => s.setStageView);
  const editingNodeId = useProcessDesignerUIStore((s) => s.editingNodeId);

  // Track Space key
  useEffect(() => {
    const onDown = (e: KeyboardEvent) => {
      if (editingNodeId) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.code === 'Space' && !e.repeat) {
        e.preventDefault();
        setSpaceHeld(true);
      }
    };
    const onUp = (e: KeyboardEvent) => {
      if (e.code === 'Space') {
        setSpaceHeld(false);
        setIsPanning(false);
        lastPos.current = null;
      }
    };
    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);
    return () => {
      window.removeEventListener('keydown', onDown);
      window.removeEventListener('keyup', onUp);
    };
  }, [editingNodeId]);

  const onMouseDown = useCallback(
    (e: { evt: MouseEvent }) => {
      // Middle mouse button panning
      if (e.evt.button === 1 || spaceHeld) {
        setIsPanning(true);
        lastPos.current = { x: e.evt.clientX, y: e.evt.clientY };
      }
    },
    [spaceHeld],
  );

  const onMouseMove = useCallback(
    (e: { evt: MouseEvent }) => {
      if (!isPanning || !lastPos.current) return;
      const dx = e.evt.clientX - lastPos.current.x;
      const dy = e.evt.clientY - lastPos.current.y;
      lastPos.current = { x: e.evt.clientX, y: e.evt.clientY };
      setStageView({ x: stageView.x + dx, y: stageView.y + dy });
    },
    [isPanning, stageView, setStageView],
  );

  const onMouseUp = useCallback(() => {
    if (isPanning) {
      setIsPanning(false);
      lastPos.current = null;
    }
  }, [isPanning]);

  const cursorStyle = spaceHeld
    ? isPanning ? 'grabbing' : 'grab'
    : undefined;

  return {
    isPanning,
    spaceHeld,
    cursorStyle,
    onMouseDown,
    onMouseMove,
    onMouseUp,
  };
}
