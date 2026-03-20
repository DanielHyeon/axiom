/**
 * Insight 공통 타입 정의
 *
 * ontology 등 다른 feature에서 참조하는 Insight 관련 타입을
 * shared 레이어로 추출한 파일이다.
 * insight feature 내부에서만 쓰이는 타입은 여기에 포함하지 않는다.
 */

/** 온톨로지 노드의 스키마 커버리지 응답 (쿼리 로그 + 드라이버 점수) */
export interface SchemaCoverageResponse {
  table: string;
  column: string | null;
  query_count: number;
  last_seen: string | null;
  driver_score: { score: number; role: string; kpi_fingerprint: string } | null;
}
