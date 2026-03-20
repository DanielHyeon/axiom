/**
 * 오브젝트 탐색기 Zustand 스토어
 *
 * UI 상태 관리: 선택된 ObjectType, 인스턴스, 패널 상태, 필터 등
 */

import { create } from 'zustand';
import type { InstanceFilter, LeftPanelTab } from '../types/object-explorer';

// ──────────────────────────────────────
// 기본 필터 값
// ──────────────────────────────────────

const DEFAULT_FILTER: InstanceFilter = {
  search: '',
  sortBy: 'id',
  sortOrder: 'asc',
  page: 1,
  pageSize: 20,
};

// ──────────────────────────────────────
// 스토어 인터페이스
// ──────────────────────────────────────

interface ObjectExplorerState {
  /** 선택된 ObjectType ID */
  selectedObjectTypeId: string | null;
  /** 선택된 인스턴스 ID */
  selectedInstanceId: string | null;
  /** 인스턴스 목록 필터 */
  filter: InstanceFilter;
  /** 좌측 패널 현재 탭 */
  leftPanelTab: LeftPanelTab;
  /** 그래프 패널 표시 여부 */
  showGraphPanel: boolean;

  // ── Actions ──
  selectObjectType: (id: string | null) => void;
  selectInstance: (id: string | null) => void;
  setFilter: (partial: Partial<InstanceFilter>) => void;
  resetFilter: () => void;
  setLeftPanelTab: (tab: LeftPanelTab) => void;
  toggleGraphPanel: () => void;
  reset: () => void;
}

export const useObjectExplorerStore = create<ObjectExplorerState>((set) => ({
  selectedObjectTypeId: null,
  selectedInstanceId: null,
  filter: { ...DEFAULT_FILTER },
  leftPanelTab: 'search',
  showGraphPanel: true,

  selectObjectType: (id) =>
    set({
      selectedObjectTypeId: id,
      selectedInstanceId: null,
      filter: { ...DEFAULT_FILTER },
      leftPanelTab: 'search',
    }),

  selectInstance: (id) =>
    set((s) => ({
      selectedInstanceId: id,
      leftPanelTab: id ? 'detail' : s.leftPanelTab,
    })),

  setFilter: (partial) =>
    set((s) => ({
      filter: { ...s.filter, ...partial },
    })),

  resetFilter: () =>
    set({ filter: { ...DEFAULT_FILTER } }),

  setLeftPanelTab: (tab) =>
    set({ leftPanelTab: tab }),

  toggleGraphPanel: () =>
    set((s) => ({ showGraphPanel: !s.showGraphPanel })),

  reset: () =>
    set({
      selectedObjectTypeId: null,
      selectedInstanceId: null,
      filter: { ...DEFAULT_FILTER },
      leftPanelTab: 'search',
      showGraphPanel: true,
    }),
}));
