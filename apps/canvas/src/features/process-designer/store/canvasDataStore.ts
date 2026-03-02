// @ts-nocheck
// features/process-designer/store/canvasDataStore.ts
// 캔버스 데이터(items, connections) 관리 레이어 — Yjs CRDT 백엔드.
// Zustand 인터페이스를 유지하여 기존 소비자(ProcessCanvas, hooks 등)에 변경 없이 동작.
// WS 서버가 없으면 IndexedDB 로컬 전용 모드로 graceful degradation.

import { create } from 'zustand';
import * as Y from 'yjs';
import { WebsocketProvider } from 'y-websocket';
import { IndexeddbPersistence } from 'y-indexeddb';
import type { CanvasItem, Connection, ConnectionStyle } from '../types/processDesigner';
import { NODE_CONFIGS, CONNECTION_CONFIGS } from '../utils/nodeConfig';
import { toYMap, updateYMap } from '../utils/yjs-helpers';

// ---------------------------------------------------------------------------
// Collaborator type (Awareness 기반)
// ---------------------------------------------------------------------------

export interface Collaborator {
  clientId: number;
  userId: string;
  name: string;
  color: string;
  cursor: { x: number; y: number } | null;
  selectedItemIds: string[];
}

// ---------------------------------------------------------------------------
// Store Interface
// ---------------------------------------------------------------------------

interface CanvasDataState {
  // 데이터 (Yjs → React 미러)
  items: CanvasItem[];
  connections: Connection[];

  // 아이템 CRUD
  addItem: (item: Omit<CanvasItem, 'id'>) => string;
  updateItem: (id: string, updates: Partial<CanvasItem>) => void;
  updateItemPosition: (id: string, x: number, y: number) => void;
  deleteItems: (ids: string[]) => void;

  // 연결선 CRUD
  addConnection: (conn: Omit<Connection, 'id'>) => string;
  deleteConnections: (ids: string[]) => void;

  // 보드 로드/저장/해제
  loadBoard: (boardId: string) => void;
  saveBoard: (boardId: string) => void;
  clearBoard: () => void;

  // Undo/Redo (Yjs UndoManager)
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConnectionStyle(type: Connection['type']): ConnectionStyle {
  const cfg = CONNECTION_CONFIGS[type];
  return {
    stroke: cfg.stroke,
    strokeWidth: 2,
    dashArray: cfg.dashArray,
    arrowSize: 8,
  };
}

// 협업자 색상 팔레트
const COLLAB_COLORS = [
  '#f87171', '#fb923c', '#facc15', '#4ade80',
  '#22d3ee', '#818cf8', '#c084fc', '#f472b6',
];

function assignColor(clientId: number): string {
  return COLLAB_COLORS[clientId % COLLAB_COLORS.length];
}

// WS 서버 URL — 환경 변수가 명시적으로 설정된 경우에만 활성화
const WS_URL = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_YJS_WS_URL)
  ? import.meta.env.VITE_YJS_WS_URL as string
  : null;

// ---------------------------------------------------------------------------
// Yjs 내부 상태 (Zustand 외부 — 싱글턴)
// ---------------------------------------------------------------------------

let _ydoc: Y.Doc | null = null;
let _wsProvider: WebsocketProvider | null = null;
let _idbPersistence: IndexeddbPersistence | null = null;
let _undoManager: Y.UndoManager | null = null;
let _yItems: Y.Array<Y.Map<unknown>> | null = null;
let _yConnections: Y.Array<Y.Map<unknown>> | null = null;
let _localUserId = '';
let _localUserName = '';

function destroyYjs() {
  if (_undoManager) { _undoManager.destroy(); _undoManager = null; }
  if (_wsProvider) { _wsProvider.destroy(); _wsProvider = null; }
  if (_idbPersistence) { _idbPersistence.destroy(); _idbPersistence = null; }
  if (_ydoc) { _ydoc.destroy(); _ydoc = null; }
  _yItems = null;
  _yConnections = null;
}

/** Y.Array에서 id로 인덱스 검색 */
function findIndexById(yArr: Y.Array<Y.Map<unknown>>, id: string): number {
  for (let i = 0; i < yArr.length; i++) {
    if (yArr.get(i).get('id') === id) return i;
  }
  return -1;
}

/** Y.Array 전체를 JSON으로 변환 */
function yArrayToJSON<T>(yArr: Y.Array<Y.Map<unknown>>): T[] {
  return yArr.toJSON() as T[];
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useCanvasDataStore = create<CanvasDataState>((set, get) => ({
  items: [],
  connections: [],

  // Undo/Redo
  canUndo: false,
  canRedo: false,

  // 협업
  collaborators: [],
  connected: false,
  wsEnabled: !!WS_URL,
  synced: false,

  // -----------------------------------------------------------------------
  // 아이템 CRUD — Yjs Y.Array 조작
  // -----------------------------------------------------------------------

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

    if (_yItems && _ydoc) {
      _ydoc.transact(() => {
        _yItems!.push([toYMap(newItem as unknown as Record<string, unknown>)]);
      });
    } else {
      // 폴백: Yjs 미연결 시 직접 상태 업데이트
      set((s) => ({ items: [...s.items, newItem] }));
    }
    return id;
  },

  updateItem: (id, updates) => {
    if (_yItems && _ydoc) {
      const idx = findIndexById(_yItems, id);
      if (idx === -1) return;
      const yItem = _yItems.get(idx);
      _ydoc.transact(() => {
        updateYMap(yItem, updates as Record<string, unknown>);
      });
    } else {
      set((s) => ({
        items: s.items.map((it) => (it.id === id ? { ...it, ...updates } : it)),
      }));
    }
  },

  updateItemPosition: (id, x, y) => {
    if (_yItems && _ydoc) {
      const idx = findIndexById(_yItems, id);
      if (idx === -1) return;
      const yItem = _yItems.get(idx);
      _ydoc.transact(() => {
        yItem.set('x', x);
        yItem.set('y', y);
      });
    } else {
      set((s) => ({
        items: s.items.map((it) => (it.id === id ? { ...it, x, y } : it)),
      }));
    }
  },

  deleteItems: (ids) => {
    if (_yItems && _yConnections && _ydoc) {
      const idSet = new Set(ids);
      _ydoc.transact(() => {
        // 역순 삭제 (인덱스 안정성)
        for (let i = _yItems!.length - 1; i >= 0; i--) {
          if (idSet.has(_yItems!.get(i).get('id') as string)) {
            _yItems!.delete(i, 1);
          }
        }
        // 연결된 연결선도 삭제
        for (let i = _yConnections!.length - 1; i >= 0; i--) {
          const conn = _yConnections!.get(i);
          if (idSet.has(conn.get('sourceId') as string) || idSet.has(conn.get('targetId') as string)) {
            _yConnections!.delete(i, 1);
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

  // -----------------------------------------------------------------------
  // 연결선 CRUD
  // -----------------------------------------------------------------------

  addConnection: (conn) => {
    const id = crypto.randomUUID();
    const newConn: Connection = {
      ...conn,
      id,
      style: conn.style || makeConnectionStyle(conn.type),
    };

    if (_yConnections && _ydoc) {
      _ydoc.transact(() => {
        _yConnections!.push([toYMap(newConn as unknown as Record<string, unknown>)]);
      });
    } else {
      set((s) => ({ connections: [...s.connections, newConn] }));
    }
    return id;
  },

  deleteConnections: (ids) => {
    if (_yConnections && _ydoc) {
      const idSet = new Set(ids);
      _ydoc.transact(() => {
        for (let i = _yConnections!.length - 1; i >= 0; i--) {
          if (idSet.has(_yConnections!.get(i).get('id') as string)) {
            _yConnections!.delete(i, 1);
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

  // -----------------------------------------------------------------------
  // Undo/Redo
  // -----------------------------------------------------------------------

  undo: () => { _undoManager?.undo(); },
  redo: () => { _undoManager?.redo(); },

  // -----------------------------------------------------------------------
  // 보드 로드/저장/해제
  // -----------------------------------------------------------------------

  loadBoard: (boardId) => {
    // 기존 Yjs 인스턴스 정리
    destroyYjs();

    const doc = new Y.Doc();
    _ydoc = doc;
    _yItems = doc.getArray<Y.Map<unknown>>('items');
    _yConnections = doc.getArray<Y.Map<unknown>>('connections');

    // --- IndexedDB 영속화 (오프라인 지원) ---
    _idbPersistence = new IndexeddbPersistence(`board:${boardId}`, doc);
    _idbPersistence.on('synced', () => {
      // IndexedDB에서 데이터 로드 완료 → React 상태 반영
      set({
        items: yArrayToJSON<CanvasItem>(_yItems!),
        connections: yArrayToJSON<Connection>(_yConnections!),
        synced: true,
      });
    });

    // --- WebSocket Provider (실시간 협업) — WS_URL이 설정된 경우에만 ---
    if (WS_URL) {
      try {
        const provider = new WebsocketProvider(WS_URL, `board:${boardId}`, doc, {
          connect: true,
          maxBackoffTime: 10000,
        });
        _wsProvider = provider;

        provider.on('status', ({ status }: { status: string }) => {
          set({ connected: status === 'connected' });
        });

        provider.on('synced', (synced: boolean) => {
          if (synced) {
            set({
              items: yArrayToJSON<CanvasItem>(_yItems!),
              connections: yArrayToJSON<Connection>(_yConnections!),
              synced: true,
            });
          }
        });

        // Awareness 설정
        const { awareness } = provider;
        awareness.setLocalState({
          userId: _localUserId || `user-${doc.clientID}`,
          name: _localUserName || `User ${doc.clientID}`,
          color: assignColor(doc.clientID),
          cursor: null,
          selectedItemIds: [],
        });

        // 다른 사용자 상태 변경 감지
        awareness.on('change', () => {
          const states = Array.from(awareness.getStates().entries());
          const collaborators: Collaborator[] = states
            .filter(([id]) => id !== doc.clientID)
            .map(([clientId, state]) => ({
              clientId,
              userId: (state as Record<string, unknown>).userId as string || '',
              name: (state as Record<string, unknown>).name as string || '',
              color: (state as Record<string, unknown>).color as string || '',
              cursor: (state as Record<string, unknown>).cursor as { x: number; y: number } | null,
              selectedItemIds: (state as Record<string, unknown>).selectedItemIds as string[] || [],
            }));
          set({ collaborators });
        });
      } catch {
        // WS 연결 실패 — 로컬 모드 유지
        set({ connected: false });
      }
    }

    // --- Y.Doc 변경 감지 → React 상태 동기화 ---
    const syncToReact = () => {
      if (_yItems && _yConnections) {
        set({
          items: yArrayToJSON<CanvasItem>(_yItems),
          connections: yArrayToJSON<Connection>(_yConnections),
        });
      }
    };

    _yItems.observeDeep(syncToReact);
    _yConnections.observeDeep(syncToReact);

    // --- UndoManager ---
    _undoManager = new Y.UndoManager([_yItems, _yConnections]);
    _undoManager.on('stack-item-added', () => {
      set({
        canUndo: _undoManager!.undoStack.length > 0,
        canRedo: _undoManager!.redoStack.length > 0,
      });
    });
    _undoManager.on('stack-item-popped', () => {
      set({
        canUndo: _undoManager!.undoStack.length > 0,
        canRedo: _undoManager!.redoStack.length > 0,
      });
    });

    // localStorage 마이그레이션: 기존 데이터가 있으면 Yjs로 이관
    const STORAGE_PREFIX = 'axiom:process-board:';
    try {
      const raw = localStorage.getItem(`${STORAGE_PREFIX}${boardId}`);
      if (raw && _yItems.length === 0) {
        const data = JSON.parse(raw) as { items: CanvasItem[]; connections: Connection[] };
        if (data.items?.length > 0) {
          doc.transact(() => {
            for (const item of data.items) {
              _yItems!.push([toYMap(item as unknown as Record<string, unknown>)]);
            }
            for (const conn of data.connections) {
              _yConnections!.push([toYMap(conn as unknown as Record<string, unknown>)]);
            }
          });
          // 마이그레이션 후 localStorage 키 제거
          localStorage.removeItem(`${STORAGE_PREFIX}${boardId}`);
        }
      }
    } catch {
      // 마이그레이션 실패 — 무시
    }

    // 초기 상태 반영
    set({
      items: yArrayToJSON<CanvasItem>(_yItems),
      connections: yArrayToJSON<Connection>(_yConnections),
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

  // -----------------------------------------------------------------------
  // Awareness 업데이트
  // -----------------------------------------------------------------------

  updateLocalCursor: (x, y) => {
    _wsProvider?.awareness.setLocalStateField('cursor', { x, y });
  },

  updateLocalSelection: (itemIds) => {
    _wsProvider?.awareness.setLocalStateField('selectedItemIds', itemIds);
  },

  setLocalUser: (userId, name) => {
    _localUserId = userId;
    _localUserName = name;
    if (_wsProvider) {
      _wsProvider.awareness.setLocalStateField('userId', userId);
      _wsProvider.awareness.setLocalStateField('name', name);
    }
  },
}));
