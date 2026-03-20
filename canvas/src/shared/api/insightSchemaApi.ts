/**
 * Insight 스키마 커버리지 API 공통 클라이언트
 *
 * 온톨로지 노드의 쿼리 로그 커버리지를 조회하는 API 함수.
 * ontology, insight 등 여러 feature에서 사용하므로 shared에 위치한다.
 */

import { weaverApi } from '@/lib/api/clients';
import type { SchemaCoverageResponse } from '@/shared/types/insight';

// re-export — 다른 feature가 타입만 필요할 때 이 파일에서 함께 가져올 수 있다
export type { SchemaCoverageResponse } from '@/shared/types/insight';

type Get<T> = (url: string) => Promise<T>;

// ──────────────────────────────────────
// 스키마 커버리지 조회
// ──────────────────────────────────────

/**
 * GET /api/insight/schema-coverage
 * 특정 테이블(+컬럼)의 쿼리 로그 커버리지와 드라이버 점수를 조회한다.
 */
export function fetchSchemaCoverage(params: {
  table: string;
  column?: string;
  timeRange?: string;
}): Promise<SchemaCoverageResponse> {
  const qs = new URLSearchParams({ table: params.table });
  if (params.column) qs.set('column', params.column);
  if (params.timeRange) qs.set('time_range', params.timeRange);
  return (weaverApi.get as unknown as Get<SchemaCoverageResponse>)(
    `/api/insight/schema-coverage?${qs}`,
  );
}
