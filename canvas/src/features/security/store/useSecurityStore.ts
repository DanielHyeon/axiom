/**
 * 보안 관리 UI 상태 스토어 (Zustand)
 * 활성 탭, 선택된 사용자/역할, 다이얼로그 열림 상태 등 로컬 UI 상태 관리
 */

import { create } from 'zustand';
import type { SecurityTab, SecurityUser } from '../types/security';

interface SecurityStoreState {
  /** 현재 활성 서브탭 */
  activeTab: SecurityTab;
  /** 편집 중인 사용자 (null이면 신규 생성) */
  editingUser: SecurityUser | null;
  /** 사용자 생성/수정 다이얼로그 표시 여부 */
  isUserDialogOpen: boolean;
  /** 삭제 확인 대상 사용자 */
  deletingUser: SecurityUser | null;
}

interface SecurityStoreActions {
  setActiveTab: (tab: SecurityTab) => void;
  openCreateUserDialog: () => void;
  openEditUserDialog: (user: SecurityUser) => void;
  closeUserDialog: () => void;
  openDeleteConfirm: (user: SecurityUser) => void;
  closeDeleteConfirm: () => void;
}

export const useSecurityStore = create<SecurityStoreState & SecurityStoreActions>(
  (set) => ({
    // 초기 상태
    activeTab: 'users',
    editingUser: null,
    isUserDialogOpen: false,
    deletingUser: null,

    // 액션
    setActiveTab: (tab) => set({ activeTab: tab }),

    openCreateUserDialog: () =>
      set({ editingUser: null, isUserDialogOpen: true }),

    openEditUserDialog: (user) =>
      set({ editingUser: user, isUserDialogOpen: true }),

    closeUserDialog: () =>
      set({ editingUser: null, isUserDialogOpen: false }),

    openDeleteConfirm: (user) => set({ deletingUser: user }),

    closeDeleteConfirm: () => set({ deletingUser: null }),
  }),
);
