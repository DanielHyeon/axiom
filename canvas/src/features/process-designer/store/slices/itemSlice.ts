/**
 * 아이템 CRUD 슬라이스
 *
 * 캔버스 아이템(노드)의 추가, 수정, 이동, 삭제를 담당한다.
 * Yjs가 연결된 경우 Y.Array를 통해 CRDT 동기화를 수행하고,
 * 미연결 시에는 Zustand 직접 상태 업데이트로 폴백한다.
 */

import type { StateCreator } from 'zustand';
import type { CanvasItem, Connection } from '../../types/processDesigner';
import { NODE_CONFIGS } from '../../utils/nodeConfig';
import { toYMap, updateYMap } from '../../utils/yjs-helpers';
import {
  getYDoc, getYItems, getYConnections, findIndexById,
} from './yjsInternals';

// ── 슬라이스 인터페이스 ──

export interface ItemSlice {
  items: CanvasItem[];
  addItem: (item: Omit<CanvasItem, 'id'>) => string;
  updateItem: (id: string, updates: Partial<CanvasItem>) => void;
  updateItemPosition: (id: string, x: number, y: number) => void;
  deleteItems: (ids: string[]) => void;
}

// ── 슬라이스 생성 함수 ──

export const createItemSlice: StateCreator<
  ItemSlice & { connections: Connection[] },
  [],
  [],
  ItemSlice
> = (set) => ({
  items: [],

  // 아이템 추가: UUID 생성 후 Yjs 또는 직접 상태에 반영
  addItem: (item) => {
    const id = crypto.randomUUID();
    const config = NODE_CONFIGS[item.type];
    const newItem: CanvasItem = {
      ...item,
      id,
      width: item.width || config.defaultWidth,
      height: item.height || config.defaultHeight,
      color: item.color || config.color,
    };

    const yItems = getYItems();
    const yDoc = getYDoc();
    if (yItems && yDoc) {
      yDoc.transact(() => {
        yItems.push([toYMap(newItem as unknown as Record<string, unknown>)]);
      });
    } else {
      set((s) => ({ items: [...s.items, newItem] }));
    }
    return id;
  },

  // 아이템 속성 업데이트
  updateItem: (id, updates) => {
    const yItems = getYItems();
    const yDoc = getYDoc();
    if (yItems && yDoc) {
      const idx = findIndexById(yItems, id);
      if (idx === -1) return;
      const yItem = yItems.get(idx);
      yDoc.transact(() => {
        updateYMap(yItem, updates as Record<string, unknown>);
      });
    } else {
      set((s) => ({
        items: s.items.map((it) => (it.id === id ? { ...it, ...updates } : it)),
      }));
    }
  },

  // 아이템 위치만 업데이트 (드래그 성능 최적화)
  updateItemPosition: (id, x, y) => {
    const yItems = getYItems();
    const yDoc = getYDoc();
    if (yItems && yDoc) {
      const idx = findIndexById(yItems, id);
      if (idx === -1) return;
      const yItem = yItems.get(idx);
      yDoc.transact(() => {
        yItem.set('x', x);
        yItem.set('y', y);
      });
    } else {
      set((s) => ({
        items: s.items.map((it) => (it.id === id ? { ...it, x, y } : it)),
      }));
    }
  },

  // 아이템 삭제 (연결된 연결선도 함께 삭제)
  deleteItems: (ids) => {
    const yItems = getYItems();
    const yConns = getYConnections();
    const yDoc = getYDoc();
    if (yItems && yConns && yDoc) {
      const idSet = new Set(ids);
      yDoc.transact(() => {
        // 역순 삭제 (인덱스 안정성)
        for (let i = yItems.length - 1; i >= 0; i--) {
          if (idSet.has(yItems.get(i).get('id') as string)) {
            yItems.delete(i, 1);
          }
        }
        // 연결된 연결선도 삭제
        for (let i = yConns.length - 1; i >= 0; i--) {
          const conn = yConns.get(i);
          if (idSet.has(conn.get('sourceId') as string) || idSet.has(conn.get('targetId') as string)) {
            yConns.delete(i, 1);
          }
        }
      });
    } else {
      const idSet = new Set(ids);
      set((s) => ({
        items: s.items.filter((it) => !idSet.has(it.id)),
        connections: s.connections.filter(
          (c) => !idSet.has(c.sourceId) && !idSet.has(c.targetId),
        ),
      }));
    }
  },
});
