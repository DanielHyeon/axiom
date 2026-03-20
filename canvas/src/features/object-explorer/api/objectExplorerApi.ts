/**
 * 오브젝트 탐색기 API — Synapse 서비스 인스턴스 조회
 *
 * 도메인 feature의 ObjectType CRUD API를 재사용하고,
 * 인스턴스 목록/상세/검색을 위한 추가 엔드포인트를 정의한다.
 *
 * 엔드포인트:
 *   - GET  /api/v3/synapse/domain/object-types                  — 타입 목록 (도메인 API 재사용)
 *   - GET  /api/v3/synapse/domain/object-types/{id}/instances   — 인스턴스 목록
 *   - GET  /api/v3/synapse/domain/instances/{id}                 — 인스턴스 상세 + 관계
 *   - GET  /api/v3/synapse/domain/instances/search               — 전체 검색
 */

import { synapseApi } from '@/lib/api/clients';
import type {
  InstanceListResponse,
  InstanceDetailResponse,
  InstanceFilter,
} from '../types/object-explorer';

const BASE = '/api/v3/synapse/domain';

// ──────────────────────────────────────
// 인스턴스 목록 (페이지네이션)
// ──────────────────────────────────────

/** ObjectType에 속한 인스턴스 목록 조회 */
export async function listInstances(
  objectTypeId: string,
  filter: InstanceFilter,
): Promise<InstanceListResponse> {
  const params = new URLSearchParams({
    page: String(filter.page),
    pageSize: String(filter.pageSize),
    sortBy: filter.sortBy,
    sortOrder: filter.sortOrder,
  });

  // 검색어가 있으면 추가
  if (filter.search.trim()) {
    params.set('search', filter.search.trim());
  }

  const res = await synapseApi.get(
    `${BASE}/object-types/${encodeURIComponent(objectTypeId)}/instances?${params.toString()}`,
  );

  const body = res as unknown as InstanceListResponse;
  return {
    instances: Array.isArray(body.instances) ? body.instances : [],
    total: typeof body.total === 'number' ? body.total : 0,
    page: typeof body.page === 'number' ? body.page : filter.page,
    pageSize: typeof body.pageSize === 'number' ? body.pageSize : filter.pageSize,
  };
}

// ──────────────────────────────────────
// 인스턴스 상세 + 관계
// ──────────────────────────────────────

/** 인스턴스 단건 상세 조회 (관련 인스턴스 포함) */
export async function getInstanceDetail(
  instanceId: string,
): Promise<InstanceDetailResponse> {
  const res = await synapseApi.get(
    `${BASE}/instances/${encodeURIComponent(instanceId)}`,
  );
  return res as unknown as InstanceDetailResponse;
}

// ──────────────────────────────────────
// 전체 텍스트 검색
// ──────────────────────────────────────

/** 모든 ObjectType에서 인스턴스 검색 */
export async function searchInstances(
  query: string,
  page = 1,
  pageSize = 20,
): Promise<InstanceListResponse> {
  const params = new URLSearchParams({
    q: query.trim(),
    page: String(page),
    pageSize: String(pageSize),
  });

  const res = await synapseApi.get(
    `${BASE}/instances/search?${params.toString()}`,
  );

  const body = res as unknown as InstanceListResponse;
  return {
    instances: Array.isArray(body.instances) ? body.instances : [],
    total: typeof body.total === 'number' ? body.total : 0,
    page: typeof body.page === 'number' ? body.page : page,
    pageSize: typeof body.pageSize === 'number' ? body.pageSize : pageSize,
  };
}
