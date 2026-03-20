/**
 * 도메인 레이어 Zustand 스토어
 *
 * UI 상태 관리: 선택된 ObjectType, 편집 모드, 패널 상태 등
 */

import { create } from 'zustand';
import type { ObjectType } from '../types/domain';

// ──────────────────────────────────────
// 뷰 모드
// ──────────────────────────────────────

export type DomainViewMode = 'detail' | 'graph';

// ──────────────────────────────────────
// 스토어 인터페이스
// ──────────────────────────────────────

interface DomainState {
  /** 현재 선택된 ObjectType ID */
  selectedObjectTypeId: string | null;
  /** 검색어 (좌측 목록 필터) */
  searchQuery: string;
  /** 뷰 모드: 상세 vs 그래프 */
  viewMode: DomainViewMode;
  /** 생성 다이얼로그 열림 여부 */
  isCreateDialogOpen: boolean;
  /** 편집 대상 ObjectType (null 이면 닫힘) */
  editingObjectType: ObjectType | null;
  /** Behavior 편집 모달 열림 정보 */
  behaviorEditorState: {
    open: boolean;
    objectTypeId: string | null;
    behaviorId: string | null;
    mode: 'create' | 'edit';
  };
  /** 우측 그래프 패널 접힘 여부 */
  isGraphPanelCollapsed: boolean;

  // ── Actions ──
  selectObjectType: (id: string | null) => void;
  setSearchQuery: (q: string) => void;
  setViewMode: (mode: DomainViewMode) => void;
  openCreateDialog: () => void;
  closeCreateDialog: () => void;
  startEditing: (ot: ObjectType) => void;
  stopEditing: () => void;
  openBehaviorEditor: (objectTypeId: string, behaviorId: string | null, mode: 'create' | 'edit') => void;
  closeBehaviorEditor: () => void;
  toggleGraphPanel: () => void;
  reset: () => void;
}

export const useDomainStore = create<DomainState>((set) => ({
  selectedObjectTypeId: null,
  searchQuery: '',
  viewMode: 'detail',
  isCreateDialogOpen: false,
  editingObjectType: null,
  behaviorEditorState: { open: false, objectTypeId: null, behaviorId: null, mode: 'create' },
  isGraphPanelCollapsed: false,

  selectObjectType: (id) => set({ selectedObjectTypeId: id }),

  setSearchQuery: (q) => set({ searchQuery: q }),

  setViewMode: (mode) => set({ viewMode: mode }),

  openCreateDialog: () => set({ isCreateDialogOpen: true }),
  closeCreateDialog: () => set({ isCreateDialogOpen: false }),

  startEditing: (ot) => set({ editingObjectType: ot }),
  stopEditing: () => set({ editingObjectType: null }),

  openBehaviorEditor: (objectTypeId, behaviorId, mode) =>
    set({ behaviorEditorState: { open: true, objectTypeId, behaviorId, mode } }),
  closeBehaviorEditor: () =>
    set({ behaviorEditorState: { open: false, objectTypeId: null, behaviorId: null, mode: 'create' } }),

  toggleGraphPanel: () => set((s) => ({ isGraphPanelCollapsed: !s.isGraphPanelCollapsed })),

  reset: () =>
    set({
      selectedObjectTypeId: null,
      searchQuery: '',
      viewMode: 'detail',
      isCreateDialogOpen: false,
      editingObjectType: null,
      behaviorEditorState: { open: false, objectTypeId: null, behaviorId: null, mode: 'create' },
      isGraphPanelCollapsed: false,
    }),
}));
