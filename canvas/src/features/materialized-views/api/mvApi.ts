/**
 * Materialized View 관리 API
 *
 * 백엔드: Weaver 서비스 — /api/v3/weaver/materialized-views
 */
import { weaverApi } from '@/lib/api/clients';

/** MV 엔티티 */
export interface MaterializedView {
  name: string;
  source_table: string;
  schema: string;
  /** 커스텀 SELECT 쿼리 (없으면 전체 복사) */
  query?: string;
  created_at?: string;
}

/** MV 생성 요청 페이로드 */
export interface MVCreatePayload {
  name: string;
  source_table: string;
  schema: string;
  query?: string;
}

/** 전체 MV 목록 조회 */
export async function listMVs(): Promise<MaterializedView[]> {
  const res = await weaverApi.get('/api/v3/weaver/materialized-views');
  const payload = (res as { data?: unknown })?.data ?? res;
  return Array.isArray(payload) ? (payload as MaterializedView[]) : [];
}

/** MV 생성 */
export async function createMV(params: MVCreatePayload): Promise<MaterializedView> {
  const res = await weaverApi.post('/api/v3/weaver/materialized-views', params);
  return res as unknown as MaterializedView;
}

/** MV 새로고침 (재구성) */
export async function refreshMV(name: string): Promise<void> {
  await weaverApi.post(`/api/v3/weaver/materialized-views/${encodeURIComponent(name)}/refresh`);
}

/** MV 삭제 */
export async function deleteMV(name: string): Promise<void> {
  await weaverApi.delete(`/api/v3/weaver/materialized-views/${encodeURIComponent(name)}`);
}
