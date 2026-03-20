/**
 * 테이블 상세 정보 로딩 훅.
 * 선택된 테이블의 컬럼 목록 + 샘플 데이터를 TanStack Query로 로드.
 */

import { useQuery } from '@tanstack/react-query';
import { getTableColumns } from '../api/oracleNl2sqlApi';
import type { ColumnMeta } from '../types/nl2sql';
import type { TableDetail, TableStats } from '../types/schema';

interface UseTableDetailReturn {
  /** 테이블 상세 정보 */
  detail: TableDetail | null;
  /** 로딩 상태 */
  isLoading: boolean;
  /** 에러 */
  error: Error | null;
  /** 새로고침 */
  refetch: () => void;
}

/**
 * 테이블명으로 상세 정보 (컬럼 목록) 로드.
 *
 * @param tableName - 조회할 테이블명 (null이면 비활성)
 * @param datasourceId - 데이터소스 ID
 * @param schema - 스키마명 (통계 표시용)
 */
export function useTableDetail(
  tableName: string | null,
  datasourceId: string | null,
  schema?: string
): UseTableDetailReturn {
  const {
    data: columns,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['nl2sql', 'tableDetail', datasourceId, tableName],
    queryFn: async (): Promise<ColumnMeta[]> => {
      if (!tableName || !datasourceId) return [];
      return getTableColumns(tableName, datasourceId);
    },
    enabled: !!tableName && !!datasourceId,
    staleTime: 5 * 60 * 1000, // 5분 캐시
  });

  // 컬럼 데이터를 TableDetail 형태로 변환
  const detail: TableDetail | null =
    tableName && columns
      ? {
          meta: {
            name: tableName,
            schema: schema || 'public',
            db: '',
            description: null,
            column_count: columns.length,
            is_valid: true,
            has_vector: false,
          },
          columns,
          stats: {
            rowCount: 0, // 실제 row count는 API 확장 필요
            columnCount: columns.length,
          } satisfies TableStats,
        }
      : null;

  return {
    detail,
    isLoading,
    error: error as Error | null,
    refetch: () => refetch(),
  };
}
