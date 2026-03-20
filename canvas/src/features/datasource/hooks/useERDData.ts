/**
 * ERD 데이터 패칭 훅.
 * Oracle Meta API에서 테이블/컬럼 메타데이터를 조회하여 ERDTableInfo[]로 변환.
 * TanStack Query 캐싱 적용.
 */

import { useQuery, useQueries } from '@tanstack/react-query';
import { getTables, getTableColumns } from '@/features/nl2sql/api/oracleNl2sqlApi';
import type { ERDTableInfo, ERDColumnInfo } from '../types/erd';
import type { ColumnMeta } from '@/features/nl2sql/types/nl2sql';

/** ColumnMeta → ERDColumnInfo 변환 */
function toERDColumn(col: ColumnMeta): ERDColumnInfo {
  return {
    name: col.name,
    dataType: col.data_type,
    isPrimaryKey: col.is_primary_key,
    isForeignKey: false, // _id 추론은 mermaidCodeGen에서 수행
    nullable: col.nullable,
  };
}

/**
 * 데이터소스 ID를 기반으로 ERD 테이블 + 컬럼 데이터를 로드하는 훅.
 *
 * @param datasourceId - Oracle Meta API에 전달할 데이터소스 ID (null이면 비활성)
 * @returns { tables, isLoading, error, refetch }
 */
export function useERDData(datasourceId: string | null) {
  // 1단계: 테이블 목록 조회
  const {
    data: tablesData,
    isLoading: tablesLoading,
    error: tablesError,
    refetch,
  } = useQuery({
    queryKey: ['erd', 'tables', datasourceId],
    queryFn: async () => {
      if (!datasourceId) return { tables: [] };
      // 최대 200개 테이블 로드 (ERD 렌더링 성능 고려)
      const res = await getTables({ datasource_id: datasourceId, page_size: 200 });
      return res;
    },
    enabled: !!datasourceId,
    staleTime: 5 * 60 * 1000, // 5분 캐시
  });

  const tableNames = tablesData?.tables?.map((t) => t.name) ?? [];

  // 2단계: 각 테이블의 컬럼 병렬 조회
  const columnQueries = useQueries({
    queries: tableNames.map((tableName) => ({
      queryKey: ['erd', 'columns', datasourceId, tableName],
      queryFn: () => getTableColumns(tableName, datasourceId!),
      enabled: !!datasourceId && tableNames.length > 0,
      staleTime: 5 * 60 * 1000,
    })),
  });

  // 모든 컬럼 쿼리 로딩 상태
  const columnsLoading = columnQueries.some((q) => q.isLoading);
  const isLoading = tablesLoading || columnsLoading;

  // ERDTableInfo[] 변환
  const tables: ERDTableInfo[] = (tablesData?.tables ?? []).map((tableMeta, index) => {
    const colData = columnQueries[index]?.data ?? [];
    return {
      name: tableMeta.name,
      schema: tableMeta.schema,
      description: tableMeta.description ?? undefined,
      columns: colData.map(toERDColumn),
    };
  });

  return {
    tables,
    isLoading,
    error: tablesError,
    refetch,
  };
}
