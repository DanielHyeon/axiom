/**
 * 스키마 네비게이션 API 클라이언트
 *
 * Synapse 서비스의 통합 related-tables API를 호출한다.
 * :Table 노드의 datasource_name 유무로 robo/text2sql 모드를 구분하며,
 * 프론트엔드는 이 내부 구분 로직을 알 필요 없이 동일한 API를 사용한다.
 */
import { synapseApi } from '@/lib/api/clients';
import type {
  SchemaAvailability,
  RelatedTableRequest,
  RelatedTableResponse,
} from '@/shared/types/schemaNavigation';

/** 스키마 가용성 조회 — robo/text2sql 각 모드의 테이블 수 확인 */
export async function getSchemaAvailability(
  datasourceName?: string,
): Promise<SchemaAvailability> {
  const params: Record<string, string> = {};
  if (datasourceName) params.datasourceName = datasourceName;
  const res = await synapseApi.get('/api/v3/synapse/schema-nav/availability', { params });
  const body = res as unknown as { success: boolean; data?: SchemaAvailability };
  return body.data ?? { robo: { table_count: 0 }, text2sql: { table_count: 0 } };
}

/** 통합 related-tables 조회 — 모드에 따라 Analyzer 또는 Fabric 관련 테이블 반환 */
export async function getRelatedTables(
  request: RelatedTableRequest,
): Promise<RelatedTableResponse> {
  const res = await synapseApi.post('/api/v3/synapse/schema-nav/related-tables', {
    mode: request.mode,
    tableName: request.tableName,
    schemaName: request.schemaName || 'public',
    datasourceName: request.datasourceName || '',
    nodeKey: request.nodeKey,
    alreadyLoadedTableIds: request.alreadyLoadedTableIds || [],
    limit: request.limit || 5,
    depth: request.depth || 1,
  });
  const body = res as unknown as { success: boolean; data?: RelatedTableResponse };
  if (!body.data) {
    throw new Error('Invalid response from related-tables API');
  }
  return body.data;
}
