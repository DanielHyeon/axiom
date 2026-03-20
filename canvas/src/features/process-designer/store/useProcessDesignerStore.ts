// features/process-designer/store/useProcessDesignerStore.ts
// UI 전용 스토어 — 캔버스 데이터(items, connections)는 canvasDataStore에 분리

import { create } from 'zustand';
import type { ToolMode, StageViewState, PendingConnection } from '../types/processDesigner';

/** 캔버스 뷰 vs 트리 뷰 */
export type ViewMode = 'canvas' | 'tree';

interface ProcessDesignerUIState {
  // 도구 모드
  toolMode: ToolMode;
  setToolMode: (mode: ToolMode) => void;

  // 선택 상태
  selectedItemIds: string[];
  selectedConnectionIds: string[];
  selectItem: (id: string, multi?: boolean) => void;
  selectConnection: (id: string) => void;
  clearSelection: () => void;
  selectAll: (allItemIds: string[]) => void;

  // 스테이지 뷰 (패닝/줌)
  stageView: StageViewState;
  setStageView: (view: Partial<StageViewState>) => void;

  // 연결선 그리기 임시 상태
  pendingConnection: PendingConnection | null;
  setPendingConnection: (conn: PendingConnection | null) => void;

  // 인라인 편집
  editingNodeId: string | null;
  setEditingNodeId: (id: string | null) => void;

  // 접근성: 포커스 노드 (Tab 탐색용, 선택과 별도)
  focusedNodeId: string | null;
  setFocusedNodeId: (id: string | null) => void;

  // 뷰 모드: 캔버스 / 트리
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;

  // 단축키 도움말 패널
  shortcutsOpen: boolean;
  setShortcutsOpen: (open: boolean) => void;

  // 모드 전환 공지 (스크린 리더 aria-live)
  modeAnnouncement: string;
  setModeAnnouncement: (msg: string) => void;
}

const initialState = {
  toolMode: 'select' as ToolMode,
  selectedItemIds: [] as string[],
  selectedConnectionIds: [] as string[],
  stageView: { x: 0, y: 0, scale: 1 },
  pendingConnection: null as PendingConnection | null,
  editingNodeId: null as string | null,
  focusedNodeId: null as string | null,
  viewMode: 'canvas' as ViewMode,
  shortcutsOpen: false,
  modeAnnouncement: '',
};

export const useProcessDesignerUIStore = create<ProcessDesignerUIState>((set) => ({
  ...initialState,

  setToolMode: (mode) => set({ toolMode: mode, pendingConnection: null }),

  selectItem: (id, multi = false) =>
    set((state) => {
      if (multi) {
        const exists = state.selectedItemIds.includes(id);
        return {
          selectedItemIds: exists
            ? state.selectedItemIds.filter((i) => i !== id)
            : [...state.selectedItemIds, id],
          selectedConnectionIds: [],
        };
      }
      return { selectedItemIds: [id], selectedConnectionIds: [] };
    }),

  selectConnection: (id) =>
    set({ selectedItemIds: [], selectedConnectionIds: [id] }),

  clearSelection: () =>
    set({ selectedItemIds: [], selectedConnectionIds: [] }),

  selectAll: (allItemIds) =>
    set({ selectedItemIds: allItemIds, selectedConnectionIds: [] }),

  setStageView: (view) =>
    set((state) => ({ stageView: { ...state.stageView, ...view } })),

  setPendingConnection: (conn) => set({ pendingConnection: conn }),

  setEditingNodeId: (id) => set({ editingNodeId: id }),

  focusedNodeId: initialState.focusedNodeId,
  setFocusedNodeId: (id) => set({ focusedNodeId: id }),

  viewMode: initialState.viewMode,
  setViewMode: (mode) => set({ viewMode: mode }),

  shortcutsOpen: initialState.shortcutsOpen,
  setShortcutsOpen: (open) => set({ shortcutsOpen: open }),

  modeAnnouncement: initialState.modeAnnouncement,
  setModeAnnouncement: (msg) => set({ modeAnnouncement: msg }),
}));
