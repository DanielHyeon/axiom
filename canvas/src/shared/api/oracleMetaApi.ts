/**
 * Oracle Meta API 공통 클라이언트
 *
 * 데이터소스, 테이블, 컬럼 메타데이터를 조회하는 API 함수 모음.
 * datasource, nl2sql 등 여러 feature에서 공통으로 호출하기 때문에
 * shared 레이어에 위치한다.
 */

import { oracleApi } from '@/lib/api/clients';
import type { DatasourceInfo, TableMeta, ColumnMeta } from '@/shared/types/schema';

// ──────────────────────────────────────
// 데이터소스 목록 조회
// ──────────────────────────────────────

/** GET /text2sql/meta/datasources — 전체 데이터소스 목록 */
export async function getDatasources(): Promise<DatasourceInfo[]> {
  const res = await oracleApi.get('/text2sql/meta/datasources');
  const body = res as unknown as { success: boolean; data?: { datasources?: DatasourceInfo[] } };
  return body.data?.datasources ?? [];
}

// ──────────────────────────────────────
// 테이블 목록 조회
// ──────────────────────────────────────

/** GET /text2sql/meta/tables — 테이블 목록 (페이징 지원) */
export async function getTables(params: {
  datasource_id: string;
  search?: string;
  page?: number;
  page_size?: number;
  valid_only?: boolean;
}): Promise<{
  tables: TableMeta[];
  pagination: { page: number; page_size: number; total_count: number; total_pages: number };
}> {
  const res = await oracleApi.get('/text2sql/meta/tables', { params });
  const body = res as unknown as {
    success: boolean;
    data?: {
      tables?: TableMeta[];
      pagination?: { page: number; page_size: number; total_count: number; total_pages: number };
    };
  };
  return {
    tables: body.data?.tables ?? [],
    pagination: body.data?.pagination ?? { page: 1, page_size: 50, total_count: 0, total_pages: 0 },
  };
}

// ──────────────────────────────────────
// 컬럼 목록 조회
// ──────────────────────────────────────

/** GET /text2sql/meta/tables/{name}/columns — 특정 테이블의 컬럼 목록 */
export async function getTableColumns(
  tableName: string,
  datasourceId: string,
): Promise<ColumnMeta[]> {
  const res = await oracleApi.get(`/text2sql/meta/tables/${encodeURIComponent(tableName)}/columns`, {
    params: { datasource_id: datasourceId },
  });
  const body = res as unknown as { success: boolean; data?: { columns?: ColumnMeta[] } };
  return body.data?.columns ?? [];
}
