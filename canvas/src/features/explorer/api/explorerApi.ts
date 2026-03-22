/**
 * Object Explorer 드릴다운 API — Weaver 서비스 연동
 *
 * Weaver의 Object Explorer 엔드포인트를 호출하여
 * 오브젝트 검색, 자식 드릴다운, 관계 조회를 수행한다.
 *
 * 엔드포인트:
 *   - POST /api/v3/weaver/object-explorer/search      — 오브젝트 검색
 *   - POST /api/v3/weaver/object-explorer/children     — 자식 드릴다운
 *   - GET  /api/v3/weaver/object-explorer/relationships/{name} — 관계 조회
 */

import { weaverApi } from '@/lib/api/clients';
import type {
  SearchResponse,
  ChildrenResponse,
  RelationshipsResponse,
} from '../types/explorer';

const BASE = '/api/v3/weaver/object-explorer';

// ──────────────────────────────────────
// 오브젝트 검색
// ──────────────────────────────────────

/**
 * 키워드로 오브젝트를 검색한다.
 * @param query - 검색어 (예: "삼성전자")
 * @param limit - 최대 결과 수 (기본 100)
 * @param datasource - 특정 데이터소스 필터 (빈 문자열이면 전체)
 */
export async function searchObjects(
  query: string,
  limit = 100,
  datasource = '',
): Promise<SearchResponse> {
  const res = await weaverApi.post(`${BASE}/search`, {
    query: query.trim(),
    limit,
    datasource,
  });
  return res as unknown as SearchResponse;
}

// ──────────────────────────────────────
// 자식 드릴다운
// ──────────────────────────────────────

/**
 * 선택된 부모 오브젝트의 자식 항목을 조회한다.
 * @param parentType - 부모 오브젝트 유형
 * @param parentId - 부모 식별 값
 * @param parentProperties - 부모의 속성 (서버에서 자식 결정에 사용)
 * @param limit - 자식 최대 수 (기본 50)
 */
export async function getChildren(
  parentType: string,
  parentId: string,
  parentProperties: Record<string, unknown>,
  limit = 50,
): Promise<ChildrenResponse> {
  const res = await weaverApi.post(`${BASE}/children`, {
    parent_type: parentType,
    parent_id: parentId,
    parent_properties: parentProperties,
    limit,
  });
  return res as unknown as ChildrenResponse;
}

// ──────────────────────────────────────
// 관계 조회
// ──────────────────────────────────────

/**
 * 특정 오브젝트 유형의 관계(outgoing/incoming)를 조회한다.
 * @param objectTypeName - 오브젝트 유형 이름
 */
export async function getRelationships(
  objectTypeName: string,
): Promise<RelationshipsResponse> {
  const res = await weaverApi.get(
    `${BASE}/relationships/${encodeURIComponent(objectTypeName)}`,
  );
  return res as unknown as RelationshipsResponse;
}
