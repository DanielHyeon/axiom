import { coreApi } from './clients';

export interface CoreReadinessResponse {
  status: string;
  checks?: Record<string, string>;
}

/**
 * Core 서비스 준비 상태 (DB, Redis 등). 인증된 요청으로 호출.
 */
export async function getCoreReadiness(): Promise<CoreReadinessResponse> {
  const response = await coreApi.get('/api/v1/health/ready');
  return response as unknown as CoreReadinessResponse;
}
