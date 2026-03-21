/**
 * 스키마 편집 API 클라이언트
 *
 * Synapse schema-edit 엔드포인트와 통신한다.
 * 테이블/컬럼 설명 수정, 관계 CRUD, 임베딩 재생성을 지원한다.
 */
import { synapseApi } from '@/lib/api/clients';

const BASE = '/api/v3/synapse/schema-edit';

// ─── 응답 타입 정의 ──────────────────────────────────────

/** Synapse 공통 응답 래퍼 */
interface SynapseResponse<T> {
  success: boolean;
  data?: T;
}

/** 테이블 정보 */
export interface SchemaTableInfo {
  name: string;
  schema_name: string;
  description?: string;
}

/** 관계 정보 */
export interface SchemaRelationshipInfo {
  id: string;
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
  relationship_type?: string;
  description?: string;
}

/** 임베딩 재생성 결과 */
interface EmbeddingResult {
  table_name: string;
  status: string;
}

// ─── API 함수 ────────────────────────────────────────────

/** 테이블 목록 조회 */
export async function listTables(): Promise<SchemaTableInfo[]> {
  const res = await synapseApi.get(`${BASE}/tables`) as unknown as SynapseResponse<SchemaTableInfo[]>;
  return res?.data ?? [];
}

/** 테이블 설명 수정 */
export async function updateTableDescription(
  tableName: string,
  description: string,
): Promise<SchemaTableInfo | null> {
  const res = await synapseApi.put(
    `${BASE}/tables/${encodeURIComponent(tableName)}/description`,
    { description },
  ) as unknown as SynapseResponse<SchemaTableInfo>;
  return res?.data ?? null;
}

/** 컬럼 설명 수정 */
export async function updateColumnDescription(
  tableName: string,
  columnName: string,
  description: string,
): Promise<{ name: string; description: string } | null> {
  const res = await synapseApi.put(
    `${BASE}/columns/${encodeURIComponent(tableName)}/${encodeURIComponent(columnName)}/description`,
    { description },
  ) as unknown as SynapseResponse<{ name: string; description: string }>;
  return res?.data ?? null;
}

/** 관계 목록 조회 */
export async function listRelationships(): Promise<SchemaRelationshipInfo[]> {
  const res = await synapseApi.get(`${BASE}/relationships`) as unknown as SynapseResponse<SchemaRelationshipInfo[]>;
  return res?.data ?? [];
}

/** 관계 추가 */
export async function createRelationship(payload: {
  source_table: string;
  source_column: string;
  target_table: string;
  target_column: string;
  relationship_type?: string;
  description?: string;
}): Promise<SchemaRelationshipInfo | null> {
  const res = await synapseApi.post(`${BASE}/relationships`, payload) as unknown as SynapseResponse<SchemaRelationshipInfo>;
  return res?.data ?? null;
}

/** 관계 삭제 */
export async function deleteRelationship(relId: string): Promise<{ deleted: boolean }> {
  const res = await synapseApi.delete(
    `${BASE}/relationships/${encodeURIComponent(relId)}`,
  ) as unknown as SynapseResponse<{ deleted: boolean }>;
  return res?.data ?? { deleted: false };
}

/** 테이블 임베딩 재생성 */
export async function rebuildTableEmbedding(tableName: string): Promise<EmbeddingResult | null> {
  const res = await synapseApi.post(
    `${BASE}/tables/${encodeURIComponent(tableName)}/embedding`,
  ) as unknown as SynapseResponse<EmbeddingResult>;
  return res?.data ?? null;
}
