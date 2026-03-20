/**
 * 도메인 모델러 Zustand 스토어
 *
 * ActionType / Policy 데이터 + UI 상태를 한곳에서 관리한다.
 * 서버 데이터 fetch 는 API 호출 후 로컬 상태에 반영하는 패턴.
 * (TanStack Query 훅과 병행 가능하지만, 이 스토어는 편집 중 임시 상태 관리 목적)
 */

import { create } from 'zustand';
import type {
  ActionType,
  Policy,
  CreateActionTypePayload,
  UpdateActionTypePayload,
  CreatePolicyPayload,
  UpdatePolicyPayload,
} from '../types/domainModeler.types';
import * as api from '../api/kineticApi';

// ──────────────────────────────────────
// 에디터 탭 타입
// ──────────────────────────────────────

/** 우측 에디터에서 편집 중인 대상 종류 */
export type EditorTarget = 'actionType' | 'policy' | null;

// ──────────────────────────────────────
// 스토어 인터페이스
// ──────────────────────────────────────

interface DomainModelerState {
  // ── 데이터 ──
  /** ActionType 목록 */
  actionTypes: ActionType[];
  /** Policy 목록 */
  policies: Policy[];

  // ── 선택 상태 ──
  /** 현재 선택된 ActionType */
  selectedActionType: ActionType | null;
  /** 현재 선택된 Policy */
  selectedPolicy: Policy | null;
  /** 에디터 대상 종류 */
  editorTarget: EditorTarget;

  // ── 로딩/에러 ──
  /** ActionType 목록 로딩 중 */
  loadingActionTypes: boolean;
  /** Policy 목록 로딩 중 */
  loadingPolicies: boolean;
  /** 저장/삭제 등 뮤테이션 진행 중 */
  saving: boolean;
  /** ActionType 관련 에러 메시지 */
  actionTypeError: string | null;
  /** Policy 관련 에러 메시지 */
  policyError: string | null;

  // ── UI 상태 ──
  /** 좌측 트리 검색어 */
  treeSearchQuery: string;

  // ── 액션 ──
  setTreeSearchQuery: (q: string) => void;

  /** ActionType 목록 조회 */
  fetchActionTypes: () => Promise<void>;
  /** ActionType 생성 */
  createActionType: (payload: CreateActionTypePayload) => Promise<ActionType | null>;
  /** ActionType 수정 */
  updateActionType: (id: string, payload: UpdateActionTypePayload) => Promise<ActionType | null>;
  /** ActionType 삭제 */
  deleteActionType: (id: string) => Promise<boolean>;
  /** ActionType 선택 */
  selectActionType: (at: ActionType | null) => void;

  /** Policy 목록 조회 */
  fetchPolicies: () => Promise<void>;
  /** Policy 생성 */
  createPolicy: (payload: CreatePolicyPayload) => Promise<Policy | null>;
  /** Policy 수정 */
  updatePolicy: (id: string, payload: UpdatePolicyPayload) => Promise<Policy | null>;
  /** Policy 삭제 */
  deletePolicy: (id: string) => Promise<boolean>;
  /** Policy 선택 */
  selectPolicy: (p: Policy | null) => void;

  /** ActionType 에러 초기화 */
  clearActionTypeError: () => void;
  /** Policy 에러 초기화 */
  clearPolicyError: () => void;
  /** 전체 상태 리셋 */
  reset: () => void;
}

// ──────────────────────────────────────
// 초기 상태
// ──────────────────────────────────────

const initialState = {
  actionTypes: [] as ActionType[],
  policies: [] as Policy[],
  selectedActionType: null as ActionType | null,
  selectedPolicy: null as Policy | null,
  editorTarget: null as EditorTarget,
  loadingActionTypes: false,
  loadingPolicies: false,
  saving: false,
  actionTypeError: null as string | null,
  policyError: null as string | null,
  treeSearchQuery: '',
};

// ──────────────────────────────────────
// 스토어 생성
// ──────────────────────────────────────

export const useDomainModelerStore = create<DomainModelerState>((set, get) => ({
  ...initialState,

  setTreeSearchQuery: (q) => set({ treeSearchQuery: q }),

  // ── ActionType CRUD ──

  fetchActionTypes: async () => {
    set({ loadingActionTypes: true, actionTypeError: null });
    try {
      const res = await api.listActionTypes();
      set({ actionTypes: res.actionTypes, loadingActionTypes: false });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '액션타입 목록 조회 실패';
      set({ loadingActionTypes: false, actionTypeError: msg });
    }
  },

  createActionType: async (payload) => {
    set({ saving: true, actionTypeError: null });
    try {
      const created = await api.createActionType(payload);
      set((s) => ({
        actionTypes: [...s.actionTypes, created],
        selectedActionType: created,
        editorTarget: 'actionType',
        saving: false,
      }));
      return created;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '액션타입 생성 실패';
      set({ saving: false, actionTypeError: msg });
      return null;
    }
  },

  updateActionType: async (id, payload) => {
    set({ saving: true, actionTypeError: null });
    try {
      const updated = await api.updateActionType(id, payload);
      set((s) => ({
        actionTypes: s.actionTypes.map((at) => (at.id === id ? updated : at)),
        selectedActionType: s.selectedActionType?.id === id ? updated : s.selectedActionType,
        saving: false,
      }));
      return updated;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '액션타입 수정 실패';
      set({ saving: false, actionTypeError: msg });
      return null;
    }
  },

  deleteActionType: async (id) => {
    set({ saving: true, actionTypeError: null });
    try {
      await api.deleteActionType(id);
      set((s) => ({
        actionTypes: s.actionTypes.filter((at) => at.id !== id),
        selectedActionType: s.selectedActionType?.id === id ? null : s.selectedActionType,
        editorTarget: s.selectedActionType?.id === id ? null : s.editorTarget,
        saving: false,
      }));
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '액션타입 삭제 실패';
      set({ saving: false, actionTypeError: msg });
      return false;
    }
  },

  selectActionType: (at) =>
    set({
      selectedActionType: at,
      selectedPolicy: null,
      editorTarget: at ? 'actionType' : null,
    }),

  // ── Policy CRUD ──

  fetchPolicies: async () => {
    set({ loadingPolicies: true, policyError: null });
    try {
      const res = await api.listPolicies();
      set({ policies: res.policies, loadingPolicies: false });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '정책 목록 조회 실패';
      set({ loadingPolicies: false, policyError: msg });
    }
  },

  createPolicy: async (payload) => {
    set({ saving: true, policyError: null });
    try {
      const created = await api.createPolicy(payload);
      set((s) => ({
        policies: [...s.policies, created],
        selectedPolicy: created,
        editorTarget: 'policy',
        saving: false,
      }));
      return created;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '정책 생성 실패';
      set({ saving: false, policyError: msg });
      return null;
    }
  },

  updatePolicy: async (id, payload) => {
    set({ saving: true, policyError: null });
    try {
      const updated = await api.updatePolicy(id, payload);
      set((s) => ({
        policies: s.policies.map((p) => (p.id === id ? updated : p)),
        selectedPolicy: s.selectedPolicy?.id === id ? updated : s.selectedPolicy,
        saving: false,
      }));
      return updated;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '정책 수정 실패';
      set({ saving: false, policyError: msg });
      return null;
    }
  },

  deletePolicy: async (id) => {
    set({ saving: true, policyError: null });
    try {
      await api.deletePolicy(id);
      set((s) => ({
        policies: s.policies.filter((p) => p.id !== id),
        selectedPolicy: s.selectedPolicy?.id === id ? null : s.selectedPolicy,
        editorTarget: s.selectedPolicy?.id === id ? null : s.editorTarget,
        saving: false,
      }));
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '정책 삭제 실패';
      set({ saving: false, policyError: msg });
      return false;
    }
  },

  selectPolicy: (p) =>
    set({
      selectedPolicy: p,
      selectedActionType: null,
      editorTarget: p ? 'policy' : null,
    }),

  clearActionTypeError: () => set({ actionTypeError: null }),
  clearPolicyError: () => set({ policyError: null }),

  reset: () => set(initialState),
}));
