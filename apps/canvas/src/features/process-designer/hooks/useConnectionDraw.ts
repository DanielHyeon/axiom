// features/process-designer/hooks/useConnectionDraw.ts
// 연결선 생성 모드 로직 (설계 §3.1)

import { useCallback } from 'react';
import { useProcessDesignerUIStore } from '../store/useProcessDesignerStore';
import { useCanvasDataStore } from '../store/canvasDataStore';
import { inferConnectionType } from '../utils/connectionRules';
import { CONNECTION_CONFIGS } from '../utils/nodeConfig';
import type { CanvasItem, ConnectionType } from '../types/processDesigner';

export function useConnectionDraw() {
  const toolMode = useProcessDesignerUIStore((s) => s.toolMode);
  const pendingConnection = useProcessDesignerUIStore((s) => s.pendingConnection);
  const setPendingConnection = useProcessDesignerUIStore((s) => s.setPendingConnection);
  const setToolMode = useProcessDesignerUIStore((s) => s.setToolMode);

  const items = useCanvasDataStore((s) => s.items);
  const addConnection = useCanvasDataStore((s) => s.addConnection);

  /** 연결선 모드에서 노드 클릭 시 호출 */
  const handleNodeClickInConnectMode = useCallback(
    (clickedItem: CanvasItem) => {
      if (toolMode !== 'connect') return;

      if (!pendingConnection) {
        // 소스 노드 설정
        setPendingConnection({ sourceId: clickedItem.id, mousePos: { x: clickedItem.x, y: clickedItem.y } });
      } else {
        // 타겟 노드 — 연결선 생성
        const sourceItem = items.find((it) => it.id === pendingConnection.sourceId);
        if (!sourceItem || sourceItem.id === clickedItem.id) {
          setPendingConnection(null);
          return;
        }

        const connType: ConnectionType = inferConnectionType(sourceItem.type, clickedItem.type);
        const cfg = CONNECTION_CONFIGS[connType];

        addConnection({
          type: connType,
          sourceId: sourceItem.id,
          targetId: clickedItem.id,
          label: cfg.label,
          style: {
            stroke: cfg.stroke,
            strokeWidth: 2,
            dashArray: cfg.dashArray,
            arrowSize: 8,
          },
        });

        setPendingConnection(null);
        setToolMode('select');
      }
    },
    [toolMode, pendingConnection, setPendingConnection, setToolMode, items, addConnection],
  );

  /** 마우스 이동 시 임시 연결선 업데이트 */
  const updatePendingMousePos = useCallback(
    (x: number, y: number) => {
      if (pendingConnection) {
        setPendingConnection({ ...pendingConnection, mousePos: { x, y } });
      }
    },
    [pendingConnection, setPendingConnection],
  );

  /** 연결 모드 취소 */
  const cancelConnection = useCallback(() => {
    setPendingConnection(null);
    setToolMode('select');
  }, [setPendingConnection, setToolMode]);

  return {
    isConnectMode: toolMode === 'connect',
    pendingConnection,
    handleNodeClickInConnectMode,
    updatePendingMousePos,
    cancelConnection,
  };
}
