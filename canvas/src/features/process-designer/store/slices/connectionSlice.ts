/**
 * 연결선 CRUD 슬라이스
 *
 * 캔버스 연결선(Connection)의 추가와 삭제를 담당한다.
 * Yjs가 연결된 경우 Y.Array를 통해 CRDT 동기화를 수행하고,
 * 미연결 시에는 Zustand 직접 상태 업데이트로 폴백한다.
 */

import type { StateCreator } from 'zustand';
import type { Connection, ConnectionStyle } from '../../types/processDesigner';
import { CONNECTION_CONFIGS } from '../../utils/nodeConfig';
import { toYMap } from '../../utils/yjs-helpers';
import { getYDoc, getYConnections } from './yjsInternals';

// ── 연결선 스타일 생성 헬퍼 ──

function makeConnectionStyle(type: Connection['type']): ConnectionStyle {
  const cfg = CONNECTION_CONFIGS[type];
  return {
    stroke: cfg.stroke,
    strokeWidth: 2,
    dashArray: cfg.dashArray,
    arrowSize: 8,
  };
}

// ── 슬라이스 인터페이스 ──

export interface ConnectionSlice {
  connections: Connection[];
  addConnection: (conn: Omit<Connection, 'id'>) => string;
  deleteConnections: (ids: string[]) => void;
}

// ── 슬라이스 생성 함수 ──

export const createConnectionSlice: StateCreator<
  ConnectionSlice,
  [],
  [],
  ConnectionSlice
> = (set) => ({
  connections: [],

  // 연결선 추가: UUID 생성 후 Yjs 또는 직접 상태에 반영
  addConnection: (conn) => {
    const id = crypto.randomUUID();
    const newConn: Connection = {
      ...conn,
      id,
      style: conn.style || makeConnectionStyle(conn.type),
    };

    const yConns = getYConnections();
    const yDoc = getYDoc();
    if (yConns && yDoc) {
      yDoc.transact(() => {
        yConns.push([toYMap(newConn as unknown as Record<string, unknown>)]);
      });
    } else {
      set((s) => ({ connections: [...s.connections, newConn] }));
    }
    return id;
  },

  // 연결선 삭제
  deleteConnections: (ids) => {
    const yConns = getYConnections();
    const yDoc = getYDoc();
    if (yConns && yDoc) {
      const idSet = new Set(ids);
      yDoc.transact(() => {
        for (let i = yConns.length - 1; i >= 0; i--) {
          if (idSet.has(yConns.get(i).get('id') as string)) {
            yConns.delete(i, 1);
          }
        }
      });
    } else {
      const idSet = new Set(ids);
      set((s) => ({
        connections: s.connections.filter((c) => !idSet.has(c.id)),
      }));
    }
  },
});
