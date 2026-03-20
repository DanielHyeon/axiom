/**
 * 보드 관리 + 협업 슬라이스
 *
 * 보드 로드/저장/해제, Undo/Redo, 실시간 협업(Awareness)을 담당한다.
 * loadBoard()는 Yjs 인스턴스를 초기화하고 IndexedDB 영속화,
 * WebSocket 실시간 동기화, UndoManager를 설정한다.
 */

import type { StateCreator } from 'zustand';
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { IndexeddbPersistence } from 'y-indexeddb';
import type { CanvasItem, Connection } from '../../types/processDesigner';
import { toYMap } from '../../utils/yjs-helpers';
import {
  getUndoManager, getWsProvider, getLocalUserId, getLocalUserName,
  destroyYjs, yArrayToJSON, assignColor, WS_URL,
  setYDoc, setWsProvider, setIdbPersistence, setUndoManager,
  setYItems, setYConnections, setLocalUserId, setLocalUserName,
} from './yjsInternals';

// ── Awareness 원시 상태 타입 (Yjs awareness에서 수신) ──

interface AwarenessState {
  userId?: string;
  name?: string;
  color?: string;
  cursor?: { x: number; y: number } | null;
  selectedItemIds?: string[];
}

// ── Collaborator 타입 ──

export interface Collaborator {
  clientId: number;
  userId: string;
  name: string;
  color: string;
  cursor: { x: number; y: number } | null;
  selectedItemIds: string[];
}

// ── 슬라이스 인터페이스 ──

export interface BoardSlice {
  // Undo/Redo
  canUndo: boolean;
  canRedo: boolean;
  undo: () => void;
  redo: () => void;

  // 보드 로드/저장/해제
  loadBoard: (boardId: string) => void;
  saveBoard: (boardId: string) => void;
  clearBoard: () => void;

  // 협업 상태
  collaborators: Collaborator[];
  connected: boolean;
  wsEnabled: boolean;
  synced: boolean;

  // Awareness 업데이트
  updateLocalCursor: (x: number, y: number) => void;
  updateLocalSelection: (itemIds: string[]) => void;
  setLocalUser: (userId: string, name: string) => void;
}

// ── 슬라이스 생성 함수 ──

export const createBoardSlice: StateCreator<
  BoardSlice & { items: CanvasItem[]; connections: Connection[] },
  [],
  [],
  BoardSlice
> = (set) => ({
  canUndo: false,
  canRedo: false,
  collaborators: [],
  connected: false,
  wsEnabled: !!WS_URL,
  synced: false,

  undo: () => { getUndoManager()?.undo(); },
  redo: () => { getUndoManager()?.redo(); },

  // 보드 로드: Yjs 초기화 + IndexedDB + WebSocket + UndoManager
  loadBoard: (boardId) => {
    destroyYjs();

    const doc = new Y.Doc();
    setYDoc(doc);
    const yItems = doc.getArray<Y.Map<unknown>>('items');
    const yConns = doc.getArray<Y.Map<unknown>>('connections');
    setYItems(yItems);
    setYConnections(yConns);

    // IndexedDB 영속화 (오프라인 지원)
    const idb = new IndexeddbPersistence(`board:${boardId}`, doc);
    setIdbPersistence(idb);
    idb.on('synced', () => {
      set({
        items: yArrayToJSON<CanvasItem>(yItems),
        connections: yArrayToJSON<Connection>(yConns),
        synced: true,
      });
    });

    // WebSocket Provider (실시간 협업) — WS_URL이 설정된 경우에만
    if (WS_URL) {
      try {
        const provider = new WebsocketProvider(WS_URL, `board:${boardId}`, doc, {
          connect: true,
          maxBackoffTime: 10000,
        });
        setWsProvider(provider);

        provider.on('status', ({ status }: { status: string }) => {
          set({ connected: status === 'connected' });
        });

        provider.on('synced', (synced: boolean) => {
          if (synced) {
            set({
              items: yArrayToJSON<CanvasItem>(yItems),
              connections: yArrayToJSON<Connection>(yConns),
              synced: true,
            });
          }
        });

        // Awareness 설정: 로컬 사용자 정보 공유
        const { awareness } = provider;
        awareness.setLocalState({
          userId: getLocalUserId() || `user-${doc.clientID}`,
          name: getLocalUserName() || `User ${doc.clientID}`,
          color: assignColor(doc.clientID),
          cursor: null,
          selectedItemIds: [],
        });

        // 다른 사용자 상태 변경 감지
        awareness.on('change', () => {
          const states = Array.from(awareness.getStates().entries());
          const collaborators: Collaborator[] = states
            .filter(([id]) => id !== doc.clientID)
            .map(([clientId, rawState]) => {
              const state = rawState as AwarenessState;
              return {
                clientId,
                userId: state.userId ?? '',
                name: state.name ?? '',
                color: state.color ?? '',
                cursor: state.cursor ?? null,
                selectedItemIds: state.selectedItemIds ?? [],
              };
            });
          set({ collaborators });
        });
      } catch {
        set({ connected: false });
      }
    }

    // Y.Doc 변경 감지 → React 상태 동기화
    const syncToReact = () => {
      set({
        items: yArrayToJSON<CanvasItem>(yItems),
        connections: yArrayToJSON<Connection>(yConns),
      });
    };
    yItems.observeDeep(syncToReact);
    yConns.observeDeep(syncToReact);

    // UndoManager 설정
    const um = new Y.UndoManager([yItems, yConns]);
    setUndoManager(um);
    um.on('stack-item-added', () => {
      set({ canUndo: um.undoStack.length > 0, canRedo: um.redoStack.length > 0 });
    });
    um.on('stack-item-popped', () => {
      set({ canUndo: um.undoStack.length > 0, canRedo: um.redoStack.length > 0 });
    });

    // localStorage 마이그레이션: 기존 데이터가 있으면 Yjs로 이관
    const STORAGE_PREFIX = 'axiom:process-board:';
    try {
      const raw = localStorage.getItem(`${STORAGE_PREFIX}${boardId}`);
      if (raw && yItems.length === 0) {
        const data = JSON.parse(raw) as { items: CanvasItem[]; connections: Connection[] };
        if (data.items?.length > 0) {
          doc.transact(() => {
            for (const item of data.items) {
              yItems.push([toYMap(item as unknown as Record<string, unknown>)]);
            }
            for (const conn of data.connections) {
              yConns.push([toYMap(conn as unknown as Record<string, unknown>)]);
            }
          });
          localStorage.removeItem(`${STORAGE_PREFIX}${boardId}`);
        }
      }
    } catch {
      // 마이그레이션 실패 — 무시
    }

    // 초기 상태 반영
    set({
      items: yArrayToJSON<CanvasItem>(yItems),
      connections: yArrayToJSON<Connection>(yConns),
      canUndo: false,
      canRedo: false,
    });
  },

  saveBoard: (_boardId) => {
    // Yjs 모드에서는 자동 저장 (IndexedDB + WS 동기화)
    // 명시적 저장은 no-op (하위 호환)
  },

  clearBoard: () => {
    destroyYjs();
    set({
      items: [],
      connections: [],
      collaborators: [],
      connected: false,
      synced: false,
      canUndo: false,
      canRedo: false,
    });
  },

  // Awareness: 로컬 커서 위치 공유
  updateLocalCursor: (x, y) => {
    getWsProvider()?.awareness.setLocalStateField('cursor', { x, y });
  },

  // Awareness: 선택된 아이템 ID 공유
  updateLocalSelection: (itemIds) => {
    getWsProvider()?.awareness.setLocalStateField('selectedItemIds', itemIds);
  },

  // 로컬 사용자 정보 설정
  setLocalUser: (userId, name) => {
    setLocalUserId(userId);
    setLocalUserName(name);
    const ws = getWsProvider();
    if (ws) {
      ws.awareness.setLocalStateField('userId', userId);
      ws.awareness.setLocalStateField('name', name);
    }
  },
});
