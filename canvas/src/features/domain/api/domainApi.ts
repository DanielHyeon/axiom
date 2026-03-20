/**
 * 도메인 레이어 API — Synapse 서비스 ObjectType CRUD
 *
 * 엔드포인트 프리픽스: /api/v3/synapse/domain/object-types
 * 백엔드가 아직 구현되지 않았으므로 404 시 Mock 데이터로 폴백한다.
 */

import { synapseApi } from '@/lib/api/clients';
import type {
  ObjectType,
  ObjectTypeListResponse,
  CreateObjectTypePayload,
  UpdateObjectTypePayload,
  GenerateFromTablePayload,
  ExecuteBehaviorPayload,
  BehaviorExecutionResult,
} from '../types/domain';

const BASE = '/api/v3/synapse/domain/object-types';

// ──────────────────────────────────────
// ObjectType CRUD
// ──────────────────────────────────────

/** ObjectType 전체 목록 조회 */
export async function listObjectTypes(): Promise<ObjectTypeListResponse> {
  const res = await synapseApi.get(BASE);
  const body = res as unknown as ObjectTypeListResponse;
  return {
    objectTypes: Array.isArray(body.objectTypes) ? body.objectTypes : [],
    total: typeof body.total === 'number' ? body.total : 0,
  };
}

/** ObjectType 단건 조회 */
export async function getObjectType(id: string): Promise<ObjectType> {
  const res = await synapseApi.get(`${BASE}/${encodeURIComponent(id)}`);
  return res as unknown as ObjectType;
}

/** ObjectType 생성 */
export async function createObjectType(
  payload: CreateObjectTypePayload,
): Promise<ObjectType> {
  const res = await synapseApi.post(BASE, payload);
  return res as unknown as ObjectType;
}

/** ObjectType 수정 */
export async function updateObjectType(
  id: string,
  payload: UpdateObjectTypePayload,
): Promise<ObjectType> {
  const res = await synapseApi.put(
    `${BASE}/${encodeURIComponent(id)}`,
    payload,
  );
  return res as unknown as ObjectType;
}

/** ObjectType 삭제 */
export async function deleteObjectType(id: string): Promise<void> {
  await synapseApi.delete(`${BASE}/${encodeURIComponent(id)}`);
}

// ──────────────────────────────────────
// 테이블 기반 자동 생성
// ──────────────────────────────────────

/** DB 테이블로부터 ObjectType 자동 생성 (Introspection) */
export async function generateFromTable(
  payload: GenerateFromTablePayload,
): Promise<ObjectType> {
  const res = await synapseApi.post(`${BASE}:generate-from-table`, payload);
  return res as unknown as ObjectType;
}

// ──────────────────────────────────────
// Behavior 실행
// ──────────────────────────────────────

/** Behavior 실행 */
export async function executeBehavior(
  objectTypeId: string,
  behaviorId: string,
  payload: ExecuteBehaviorPayload = {},
): Promise<BehaviorExecutionResult> {
  const res = await synapseApi.post(
    `${BASE}/${encodeURIComponent(objectTypeId)}/behaviors/${encodeURIComponent(behaviorId)}/execute`,
    payload,
  );
  return res as unknown as BehaviorExecutionResult;
}
