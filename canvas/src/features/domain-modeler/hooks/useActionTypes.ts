/**
 * ActionType / Policy 관리 커스텀 훅
 *
 * Zustand 스토어 + API 호출을 감싸서
 * 컴포넌트에서 간편하게 CRUD + toast 알림을 사용할 수 있게 한다.
 */

import { useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { useDomainModelerStore } from '../store/useDomainModelerStore';
import { testActionType as apiTestActionType } from '../api/kineticApi';
import type {
  CreateActionTypePayload,
  UpdateActionTypePayload,
  CreatePolicyPayload,
  UpdatePolicyPayload,
  DryRunResult,
} from '../types/domainModeler.types';

/**
 * ActionType CRUD 훅
 *
 * 마운트 시 자동으로 목록을 조회하고,
 * 생성/수정/삭제 시 토스트 알림을 표시한다.
 */
export function useActionTypes() {
  const { t } = useTranslation();
  const {
    actionTypes,
    selectedActionType,
    loadingActionTypes,
    saving,
    actionTypeError,
    fetchActionTypes,
    createActionType: storeCreate,
    updateActionType: storeUpdate,
    deleteActionType: storeDelete,
    selectActionType,
    clearActionTypeError,
  } = useDomainModelerStore();

  // 마운트 시 목록 조회
  useEffect(() => {
    fetchActionTypes();
  }, [fetchActionTypes]);

  // 에러 발생 시 토스트 표시
  useEffect(() => {
    if (actionTypeError) {
      toast.error(actionTypeError);
      clearActionTypeError();
    }
  }, [actionTypeError, clearActionTypeError]);

  /** ActionType 생성 + 토스트 */
  const create = useCallback(
    async (payload: CreateActionTypePayload) => {
      const result = await storeCreate(payload);
      if (result) {
        toast.success(t('domainModeler.toast.actionTypeCreated', { name: result.name }));
      }
      return result;
    },
    [storeCreate, t],
  );

  /** ActionType 수정 + 토스트 */
  const update = useCallback(
    async (id: string, payload: UpdateActionTypePayload) => {
      const result = await storeUpdate(id, payload);
      if (result) {
        toast.success(t('domainModeler.toast.actionTypeUpdated', { name: result.name }));
      }
      return result;
    },
    [storeUpdate, t],
  );

  /** ActionType 삭제 + 토스트 */
  const remove = useCallback(
    async (id: string) => {
      const ok = await storeDelete(id);
      if (ok) {
        toast.success(t('domainModeler.toast.actionTypeDeleted'));
      }
      return ok;
    },
    [storeDelete, t],
  );

  /** Dry-Run 테스트 — API 직접 호출, 결과를 반환 */
  const dryRun = useCallback(
    async (
      id: string,
      sampleEvent?: Record<string, unknown>,
    ): Promise<DryRunResult | null> => {
      try {
        const result = await apiTestActionType(id, sampleEvent);
        if (result.matched) {
          toast.success(
            t('domainModeler.toast.dryRunMatched', {
              matched: result.matchedConditions,
              total: result.totalConditions,
              actions: result.pendingActions.length,
            }),
          );
        } else {
          toast.info(t('domainModeler.toast.dryRunNotMatched'));
        }
        return result;
      } catch (err) {
        const msg = err instanceof Error ? err.message : t('domainModeler.toast.dryRunFailed');
        toast.error(msg);
        return null;
      }
    },
    [t],
  );

  /** 목록 새로고침 */
  const refresh = useCallback(() => {
    fetchActionTypes();
  }, [fetchActionTypes]);

  return {
    actionTypes,
    selectedActionType,
    loading: loadingActionTypes,
    saving,
    select: selectActionType,
    create,
    update,
    remove,
    dryRun,
    refresh,
  };
}

/**
 * Policy CRUD 훅
 *
 * ActionType 훅과 동일한 패턴으로 Policy 를 관리한다.
 */
export function usePolicies() {
  const { t } = useTranslation();
  const {
    policies,
    selectedPolicy,
    loadingPolicies,
    saving,
    policyError,
    fetchPolicies,
    createPolicy: storeCreate,
    updatePolicy: storeUpdate,
    deletePolicy: storeDelete,
    selectPolicy,
    clearPolicyError,
  } = useDomainModelerStore();

  // 마운트 시 목록 조회
  useEffect(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  // 에러 발생 시 토스트 표시
  useEffect(() => {
    if (policyError) {
      toast.error(policyError);
      clearPolicyError();
    }
  }, [policyError, clearPolicyError]);

  /** Policy 생성 + 토스트 */
  const create = useCallback(
    async (payload: CreatePolicyPayload) => {
      const result = await storeCreate(payload);
      if (result) {
        toast.success(t('domainModeler.toast.policyCreated', { name: result.name }));
      }
      return result;
    },
    [storeCreate, t],
  );

  /** Policy 수정 + 토스트 */
  const update = useCallback(
    async (id: string, payload: UpdatePolicyPayload) => {
      const result = await storeUpdate(id, payload);
      if (result) {
        toast.success(t('domainModeler.toast.policyUpdated', { name: result.name }));
      }
      return result;
    },
    [storeUpdate, t],
  );

  /** Policy 삭제 + 토스트 */
  const remove = useCallback(
    async (id: string) => {
      const ok = await storeDelete(id);
      if (ok) {
        toast.success(t('domainModeler.toast.policyDeleted'));
      }
      return ok;
    },
    [storeDelete, t],
  );

  /** 목록 새로고침 */
  const refresh = useCallback(() => {
    fetchPolicies();
  }, [fetchPolicies]);

  return {
    policies,
    selectedPolicy,
    loading: loadingPolicies,
    saving,
    select: selectPolicy,
    create,
    update,
    remove,
    refresh,
  };
}
