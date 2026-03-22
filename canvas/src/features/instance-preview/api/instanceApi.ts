/**
 * 인스턴스 데이터 프리뷰 API
 *
 * 백엔드: Weaver 서비스 — /api/v3/weaver/nodes/{nodeId}/sample-data
 */
import { weaverApi } from '@/lib/api/clients';
import type { SampleDataResponse } from '../types/instance';

/** 노드의 샘플 데이터 조회 */
export async function getSampleData(
  nodeId: string,
  limit: number = 50,
  schema?: string,
  table?: string,
): Promise<SampleDataResponse> {
  const params: Record<string, unknown> = { limit };
  if (schema) params.schema = schema;
  if (table) params.table = table;

  const res = await weaverApi.get(`/api/v3/weaver/nodes/${encodeURIComponent(nodeId)}/sample-data`, {
    params,
  });
  return res as unknown as SampleDataResponse;
}
