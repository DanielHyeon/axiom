/**
 * 데이터소스 연결 테스트 공통 API
 *
 * ingestion, datasource 등 여러 feature에서 사용하는
 * Weaver 데이터소스 연결 테스트 함수를 shared로 추출한 파일이다.
 */

import { weaverApi } from '@/lib/api/clients';

// ──────────────────────────────────────
// 연결 테스트
// ──────────────────────────────────────

/**
 * POST /api/datasources/{name}/test
 * 데이터소스에 실제 연결을 시도하고 성공 여부와 응답 시간을 반환한다.
 */
export async function testConnection(name: string): Promise<{
  success: boolean;
  name: string;
  response_time_ms?: number;
  message?: string;
}> {
  const res = await weaverApi.post(`/api/datasources/${encodeURIComponent(name)}/test`);
  return res as unknown as {
    success: boolean;
    name: string;
    response_time_ms?: number;
    message?: string;
  };
}
