/**
 * 비즈니스 글로서리 타입 정의
 * Weaver MetadataCatalog 기반의 용어집/용어 도메인 모델
 */

// ---------------------------------------------------------------------------
// 용어 상태 (Draft → Approved | Deprecated)
// ---------------------------------------------------------------------------
export type TermStatus = 'draft' | 'approved' | 'deprecated';

// ---------------------------------------------------------------------------
// 용어집 유형
// ---------------------------------------------------------------------------
export type GlossaryType = 'Business' | 'Technical' | 'DataQuality';

// ---------------------------------------------------------------------------
// 용어집(Glossary) — 여러 용어를 묶는 상위 컨테이너
// ---------------------------------------------------------------------------
export interface Glossary {
  id: string;
  name: string;
  description: string;
  type: GlossaryType;
  termCount: number;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// 용어(Term) — 개별 비즈니스 용어
// ---------------------------------------------------------------------------
export interface GlossaryTerm {
  id: string;
  name: string;
  definition: string;
  category: string;
  status: TermStatus;
  synonyms: string[];
  /** 관련 테이블/컬럼 매핑 */
  relatedTables: RelatedTable[];
  /** 온톨로지 노드 연결 (선택) */
  ontologyNodeId?: string;
  owner: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// 관련 테이블 매핑
// ---------------------------------------------------------------------------
export interface RelatedTable {
  tableName: string;
  columnName?: string;
}

// ---------------------------------------------------------------------------
// 카테고리 (태그 형태)
// ---------------------------------------------------------------------------
export interface GlossaryCategory {
  id: string;
  name: string;
  color: string;
  termCount: number;
}

// ---------------------------------------------------------------------------
// API 요청/응답 타입
// ---------------------------------------------------------------------------

/** 용어집 목록 응답 */
export interface GlossaryListResponse {
  glossaries: Glossary[];
  total: number;
}

/** 용어 목록 응답 */
export interface TermListResponse {
  terms: GlossaryTerm[];
  total: number;
}

/** 카테고리 목록 응답 */
export interface CategoryListResponse {
  categories: GlossaryCategory[];
}

/** 용어 생성/수정 요청 */
export interface TermCreateRequest {
  name: string;
  definition: string;
  category: string;
  status: TermStatus;
  synonyms: string[];
  relatedTables: RelatedTable[];
  ontologyNodeId?: string;
  owner: string;
  tags: string[];
}

/** 용어집 생성/수정 요청 */
export interface GlossaryCreateRequest {
  name: string;
  description: string;
  type: GlossaryType;
}

/** 용어 검색 파라미터 */
export interface TermSearchParams {
  query?: string;
  category?: string;
  status?: TermStatus;
  glossaryId: string;
}
