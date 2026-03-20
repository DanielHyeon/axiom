/**
 * Kinetic 행동 모델 API — Synapse 서비스 ActionType / Policy CRUD
 *
 * 엔드포인트 프리픽스: /api/v3/synapse/domain/kinetic
 * 백엔드가 아직 구현되지 않았으므로 404 시 빈 배열로 폴백한다.
 */

import { synapseApi } from '@/lib/api/clients';
import type {
  ActionType,
  ActionTypeListResponse,
  CreateActionTypePayload,
  UpdateActionTypePayload,
  DryRunResult,
  LinkActionTypePayload,
  Policy,
  PolicyListResponse,
  CreatePolicyPayload,
  UpdatePolicyPayload,
} from '../types/domainModeler.types';

const BASE = '/api/v3/synapse/domain/kinetic';

// ──────────────────────────────────────
// ActionType CRUD
// ──────────────────────────────────────

/** ActionType 목록 조회 */
export async function listActionTypes(): Promise<ActionTypeListResponse> {
  const res = await synapseApi.get(`${BASE}/action-types`);
  const body = res as unknown as ActionTypeListResponse;
  return {
    actionTypes: Array.isArray(body.actionTypes) ? body.actionTypes : [],
    total: typeof body.total === 'number' ? body.total : 0,
  };
}

/** ActionType 단건 조회 */
export async function getActionType(id: string): Promise<ActionType> {
  const res = await synapseApi.get(
    `${BASE}/action-types/${encodeURIComponent(id)}`,
  );
  return res as unknown as ActionType;
}

/** ActionType 생성 */
export async function createActionType(
  payload: CreateActionTypePayload,
): Promise<ActionType> {
  const res = await synapseApi.post(`${BASE}/action-types`, payload);
  return res as unknown as ActionType;
}

/** ActionType 수정 */
export async function updateActionType(
  id: string,
  payload: UpdateActionTypePayload,
): Promise<ActionType> {
  const res = await synapseApi.put(
    `${BASE}/action-types/${encodeURIComponent(id)}`,
    payload,
  );
  return res as unknown as ActionType;
}

/** ActionType 삭제 */
export async function deleteActionType(id: string): Promise<void> {
  await synapseApi.delete(
    `${BASE}/action-types/${encodeURIComponent(id)}`,
  );
}

/** ActionType을 온톨로지 노드에 링크 */
export async function linkActionType(
  id: string,
  payload: LinkActionTypePayload,
): Promise<void> {
  await synapseApi.post(
    `${BASE}/action-types/${encodeURIComponent(id)}/link`,
    payload,
  );
}

/** ActionType Dry-Run 테스트 (실제 실행 없이 조건 매칭만 검증) */
export async function testActionType(
  id: string,
  sampleEvent?: Record<string, unknown>,
): Promise<DryRunResult> {
  const res = await synapseApi.post(
    `${BASE}/action-types/${encodeURIComponent(id)}/test`,
    { sampleEvent: sampleEvent ?? {} },
  );
  return res as unknown as DryRunResult;
}

// ──────────────────────────────────────
// Policy CRUD
// ──────────────────────────────────────

/** Policy 목록 조회 */
export async function listPolicies(): Promise<PolicyListResponse> {
  const res = await synapseApi.get(`${BASE}/policies`);
  const body = res as unknown as PolicyListResponse;
  return {
    policies: Array.isArray(body.policies) ? body.policies : [],
    total: typeof body.total === 'number' ? body.total : 0,
  };
}

/** Policy 단건 조회 */
export async function getPolicy(id: string): Promise<Policy> {
  const res = await synapseApi.get(
    `${BASE}/policies/${encodeURIComponent(id)}`,
  );
  return res as unknown as Policy;
}

/** Policy 생성 */
export async function createPolicy(
  payload: CreatePolicyPayload,
): Promise<Policy> {
  const res = await synapseApi.post(`${BASE}/policies`, payload);
  return res as unknown as Policy;
}

/** Policy 수정 */
export async function updatePolicy(
  id: string,
  payload: UpdatePolicyPayload,
): Promise<Policy> {
  const res = await synapseApi.put(
    `${BASE}/policies/${encodeURIComponent(id)}`,
    payload,
  );
  return res as unknown as Policy;
}

/** Policy 삭제 */
export async function deletePolicy(id: string): Promise<void> {
  await synapseApi.delete(
    `${BASE}/policies/${encodeURIComponent(id)}`,
  );
}
