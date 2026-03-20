/**
 * 데이터 품질 UI 상태 스토어 (Zustand)
 * 필터, 활성 탭, 선택된 규칙 등 클라이언트 측 UI 상태만 관리
 */
import { create } from 'zustand';
import type { DQFilters, DQSeverity, DQRuleType, TestRunStatus } from '../types/data-quality';

// 활성 서브탭: 테스트 케이스 | 테스트 스위트 | 인시던트
export type DQSubTab = 'test-cases' | 'incidents' | 'trend';

interface DQState {
  // 현재 서브탭
  activeTab: DQSubTab;
  setActiveTab: (tab: DQSubTab) => void;

  // 필터
  filters: DQFilters;
  setSearchQuery: (q: string) => void;
  setTableFilter: (t: string) => void;
  setTypeFilter: (t: DQRuleType | '') => void;
  setStatusFilter: (s: TestRunStatus | '') => void;
  setSeverityFilter: (s: DQSeverity | '') => void;
  resetFilters: () => void;

  // 선택된 규칙 ID (상세 패널용)
  selectedRuleId: string | null;
  selectRule: (id: string | null) => void;

  // 테스트 케이스 생성 다이얼로그
  showCreateDialog: boolean;
  setShowCreateDialog: (show: boolean) => void;
}

const defaultFilters: DQFilters = {
  searchQuery: '',
  tableFilter: '',
  typeFilter: '',
  statusFilter: '',
  severityFilter: '',
};

export const useDQStore = create<DQState>((set) => ({
  activeTab: 'test-cases',
  setActiveTab: (tab) => set({ activeTab: tab }),

  filters: { ...defaultFilters },
  setSearchQuery: (q) => set((s) => ({ filters: { ...s.filters, searchQuery: q } })),
  setTableFilter: (t) => set((s) => ({ filters: { ...s.filters, tableFilter: t } })),
  setTypeFilter: (t) => set((s) => ({ filters: { ...s.filters, typeFilter: t } })),
  setStatusFilter: (s) => set((st) => ({ filters: { ...st.filters, statusFilter: s } })),
  setSeverityFilter: (s) => set((st) => ({ filters: { ...st.filters, severityFilter: s } })),
  resetFilters: () => set({ filters: { ...defaultFilters } }),

  selectedRuleId: null,
  selectRule: (id) => set({ selectedRuleId: id }),

  showCreateDialog: false,
  setShowCreateDialog: (show) => set({ showCreateDialog: show }),
}));
