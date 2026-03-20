// features/process-designer/hooks/useCanvasKeyboard.ts
// 16+ 키보드 단축키 (설계 §8) + 접근성 키보드 모드 (설계 §10.2)

import { useEffect } from 'react';
import { SHORTCUT_TO_TYPE, NODE_CONFIGS } from '../utils/nodeConfig';
import { useProcessDesignerUIStore } from '../store/useProcessDesignerStore';
import { useCanvasDataStore } from '../store/canvasDataStore';

interface UseCanvasKeyboardOptions {
  /** 캔버스가 포커스 가능 상태인지 (비활성 시 단축키 무시) */
  enabled?: boolean;
  /** 읽기 전용 모드 (편집 단축키 비활성) */
  readOnly?: boolean;
}

/** 캔버스 패닝 이동량 (px) */
const PAN_STEP = 50;

export function useCanvasKeyboard({ enabled = true, readOnly = false }: UseCanvasKeyboardOptions = {}) {
  const toolMode = useProcessDesignerUIStore((s) => s.toolMode);
  const setToolMode = useProcessDesignerUIStore((s) => s.setToolMode);
  const selectedItemIds = useProcessDesignerUIStore((s) => s.selectedItemIds);
  const selectedConnectionIds = useProcessDesignerUIStore((s) => s.selectedConnectionIds);
  const selectItem = useProcessDesignerUIStore((s) => s.selectItem);
  const selectAll = useProcessDesignerUIStore((s) => s.selectAll);
  const clearSelection = useProcessDesignerUIStore((s) => s.clearSelection);
  const editingNodeId = useProcessDesignerUIStore((s) => s.editingNodeId);
  const setEditingNodeId = useProcessDesignerUIStore((s) => s.setEditingNodeId);
  const setPendingConnection = useProcessDesignerUIStore((s) => s.setPendingConnection);
  const focusedNodeId = useProcessDesignerUIStore((s) => s.focusedNodeId);
  const setFocusedNodeId = useProcessDesignerUIStore((s) => s.setFocusedNodeId);
  const stageView = useProcessDesignerUIStore((s) => s.stageView);
  const setStageView = useProcessDesignerUIStore((s) => s.setStageView);
  const setShortcutsOpen = useProcessDesignerUIStore((s) => s.setShortcutsOpen);
  const setModeAnnouncement = useProcessDesignerUIStore((s) => s.setModeAnnouncement);

  const items = useCanvasDataStore((s) => s.items);
  const addItem = useCanvasDataStore((s) => s.addItem);
  const updateItemPosition = useCanvasDataStore((s) => s.updateItemPosition);
  const deleteItems = useCanvasDataStore((s) => s.deleteItems);
  const deleteConnections = useCanvasDataStore((s) => s.deleteConnections);
  const undo = useCanvasDataStore((s) => s.undo);
  const redo = useCanvasDataStore((s) => s.redo);

  useEffect(() => {
    if (!enabled) return;

    const handler = (e: KeyboardEvent) => {
      // input/textarea/select 포커스 시 스킵 (K-AIR 패턴)
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      // 인라인 편집 중에는 단축키 무시
      if (editingNodeId) return;

      const { key, ctrlKey, metaKey, shiftKey: shift } = e;
      const ctrl = ctrlKey || metaKey;
      const keyLower = key.toLowerCase();

      // --- Shift+? → 단축키 도움말 ---
      if (key === '?' && shift) {
        e.preventDefault();
        setShortcutsOpen(true);
        return;
      }

      // --- Tab / Shift+Tab → 노드 포커스 이동 (§10.2) ---
      if (keyLower === 'tab' && !ctrl) {
        if (items.length === 0) return;
        e.preventDefault();
        const currentIdx = focusedNodeId
          ? items.findIndex((it) => it.id === focusedNodeId)
          : -1;

        let nextIdx: number;
        if (shift) {
          nextIdx = currentIdx <= 0 ? items.length - 1 : currentIdx - 1;
        } else {
          nextIdx = currentIdx >= items.length - 1 ? 0 : currentIdx + 1;
        }

        const nextItem = items[nextIdx];
        setFocusedNodeId(nextItem.id);
        setModeAnnouncement(`${nextItem.label} (${NODE_CONFIGS[nextItem.type]?.label ?? nextItem.type}) 포커스`);
        return;
      }

      // --- Enter → 포커스된 노드 선택 (§10.2) ---
      if (keyLower === 'enter' && !ctrl && focusedNodeId) {
        e.preventDefault();
        selectItem(focusedNodeId, false);
        const item = items.find((it) => it.id === focusedNodeId);
        if (item) {
          setModeAnnouncement(`${item.label} 선택됨`);
        }
        return;
      }

      // --- Arrow Keys → 노드 이동 / 캔버스 패닝 (§10.2) ---
      if (['arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(keyLower)) {
        // Ctrl+Arrow → 캔버스 패닝
        if (ctrl) {
          e.preventDefault();
          const dx = keyLower === 'arrowleft' ? PAN_STEP : keyLower === 'arrowright' ? -PAN_STEP : 0;
          const dy = keyLower === 'arrowup' ? PAN_STEP : keyLower === 'arrowdown' ? -PAN_STEP : 0;
          setStageView({ x: stageView.x + dx, y: stageView.y + dy });
          return;
        }

        // Arrow / Shift+Arrow → 선택된 노드 이동
        if (!readOnly && selectedItemIds.length > 0) {
          e.preventDefault();
          const step = shift ? 1 : 10;
          const dx = keyLower === 'arrowleft' ? -step : keyLower === 'arrowright' ? step : 0;
          const dy = keyLower === 'arrowup' ? -step : keyLower === 'arrowdown' ? step : 0;

          for (const id of selectedItemIds) {
            const item = items.find((it) => it.id === id);
            if (item) {
              updateItemPosition(id, item.x + dx, item.y + dy);
            }
          }
          return;
        }
      }

      // --- + / - → 줌 인/아웃 (§10.2) ---
      if ((key === '+' || key === '=') && !ctrl) {
        e.preventDefault();
        const newScale = Math.min(stageView.scale * 1.15, 3);
        setStageView({ scale: newScale });
        return;
      }
      if ((key === '-' || key === '_') && !ctrl) {
        e.preventDefault();
        const newScale = Math.max(stageView.scale / 1.15, 0.1);
        setStageView({ scale: newScale });
        return;
      }

      // --- Ctrl+계열 ---
      if (ctrl && keyLower === 'a') {
        e.preventDefault();
        selectAll(items.map((it) => it.id));
        return;
      }

      if (ctrl && keyLower === 'd' && !readOnly) {
        e.preventDefault();
        for (const id of selectedItemIds) {
          const orig = items.find((it) => it.id === id);
          if (!orig) continue;
          addItem({
            type: orig.type,
            x: orig.x + 20,
            y: orig.y + 20,
            width: orig.width,
            height: orig.height,
            label: `${orig.label} (copy)`,
            color: orig.color,
            parentContextBoxId: orig.parentContextBoxId,
          });
        }
        return;
      }

      if (ctrl && keyLower === 'z' && !readOnly) {
        e.preventDefault();
        if (shift) {
          redo();
        } else {
          undo();
        }
        return;
      }

      // --- 단일키 ---
      if (keyLower === 'escape') {
        if (toolMode === 'connect') {
          setPendingConnection(null);
          setToolMode('select');
          setModeAnnouncement('선택 모드');
        } else if (editingNodeId) {
          setEditingNodeId(null);
        } else {
          clearSelection();
          setFocusedNodeId(null);
        }
        return;
      }

      if ((keyLower === 'delete' || keyLower === 'backspace') && !readOnly) {
        e.preventDefault();
        if (selectedItemIds.length > 0) {
          deleteItems(selectedItemIds);
          clearSelection();
        }
        if (selectedConnectionIds.length > 0) {
          deleteConnections(selectedConnectionIds);
          clearSelection();
        }
        return;
      }

      // readOnly 모드에서는 편집 도구 전환 차단
      if (readOnly) return;

      if (keyLower === 'v') {
        setToolMode('select');
        setModeAnnouncement('선택 모드');
        return;
      }

      if (keyLower === 'c' && !ctrl) {
        setToolMode('connect');
        setModeAnnouncement('연결선 모드 활성화');
        return;
      }

      // 노드 추가 단축키 (B, E, N, R, S, T, M, D)
      const nodeType = SHORTCUT_TO_TYPE[keyLower];
      if (nodeType) {
        setToolMode(nodeType);
        setModeAnnouncement(`${NODE_CONFIGS[nodeType]?.label ?? nodeType} 추가 모드`);
        return;
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [
    enabled, readOnly, toolMode, setToolMode, selectedItemIds, selectedConnectionIds,
    selectItem, selectAll, clearSelection, editingNodeId, setEditingNodeId, setPendingConnection,
    focusedNodeId, setFocusedNodeId, stageView, setStageView,
    setShortcutsOpen, setModeAnnouncement,
    items, addItem, updateItemPosition, deleteItems, deleteConnections, undo, redo,
  ]);
}
