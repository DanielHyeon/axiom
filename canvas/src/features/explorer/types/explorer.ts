/**
 * Object Explorer 드릴다운 — TypeScript 타입 정의
 *
 * Weaver Object Explorer API (/api/v3/weaver/object-explorer)의
 * 요청/응답 모델을 정의한다.
 */

// ──────────────────────────────────────
// 검색 결과
// ──────────────────────────────────────

/** 검색 결과 개별 항목 */
export interface ObjectSearchResult {
  /** 오브젝트 유형 (예: "고객", "계약") */
  object_type: string;
  /** 식별 값 (PK 또는 유니크 키) */
  id_value: string;
  /** 표시명 (사람이 읽기 쉬운 이름) */
  name_value: string;
  /** 동적 속성 (컬럼명 → 값) */
  properties: Record<string, unknown>;
}

/** 검색 API 응답 */
export interface SearchResponse {
  success: boolean;
  results: ObjectSearchResult[];
  query: string;
}

// ──────────────────────────────────────
// 자식 노드 (드릴다운)
// ──────────────────────────────────────

/** 자식 노드 그룹 (object_type별) */
export interface ChildGroup {
  /** 자식 오브젝트 유형 */
  object_type: string;
  /** 해당 유형의 자식 항목 목록 */
  items: ObjectSearchResult[];
  /** 총 건수 */
  count: number;
}

/** 자식 조회 API 응답 */
export interface ChildrenResponse {
  success: boolean;
  children: ChildGroup[];
  parent_type: string;
}

// ──────────────────────────────────────
// 관계 (Relationships)
// ──────────────────────────────────────

/** 관계 정보 */
export interface Relationship {
  /** 관계명 */
  name: string;
  /** 대상 오브젝트 유형 */
  target_type: string;
  /** 관계 설명 */
  description?: string;
}

/** 관계 조회 API 응답 */
export interface RelationshipsResponse {
  success: boolean;
  object_type: string;
  outgoing: Relationship[];
  incoming: Relationship[];
}

// ──────────────────────────────────────
// 요청 타입
// ──────────────────────────────────────

/** 검색 요청 */
export interface SearchRequest {
  query: string;
  limit?: number;
  datasource?: string;
}

/** 자식 조회 요청 */
export interface ChildrenRequest {
  parent_type: string;
  parent_id: string;
  parent_properties: Record<string, unknown>;
  limit?: number;
}

// ──────────────────────────────────────
// 브레드크럼 항목
// ──────────────────────────────────────

/** 네비게이션 경로의 각 단계 */
export interface BreadcrumbItem {
  /** 오브젝트 유형 */
  object_type: string;
  /** 표시명 */
  name_value: string;
  /** 식별 값 */
  id_value: string;
  /** 속성 (자식 조회 시 parent_properties로 사용) */
  properties: Record<string, unknown>;
}
