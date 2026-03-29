/**
 * ERD 데이터 패칭 훅.
 * Oracle Meta API에서 테이블/컬럼 메타데이터를 조회하여 ERDTableInfo[]로 변환.
 * TanStack Query 캐싱 적용.
 */

import { useQuery, useQueries } from '@tanstack/react-query';
// 공통 Meta API와 타입은 shared 레이어에서 가져온다 (feature 간 의존 제거)
import { getTables, getTableColumns } from '@/shared/api/oracleMetaApi';
import type { ERDTableInfo, ERDColumnInfo } from '@/shared/types/schema';
import type { ColumnMeta } from '@/shared/types/schema';

/**
 * ColumnMeta → ERDColumnInfo 변환.
 *
 * FK 판정 우선순위:
 *  1) API 응답의 foreign_keys 배열에 참조 정보가 있으면 사용
 *  2) 없으면 _id 접미사 + allTableNames 매칭으로 추론
 *  3) PK 컬럼은 FK 추론을 건너뜀
 */
function toERDColumn(
  col: ColumnMeta,
  allTableNames: Set<string>,
): ERDColumnInfo {
  // 1) API 응답에 FK 참조 정보가 있으면 우선 사용
  const apiFk = col.foreign_keys?.find((fk) => fk.target_table);
  if (apiFk) {
    return {
      name: col.name,
      dataType: col.data_type,
      isPrimaryKey: col.is_primary_key,
      isForeignKey: true,
      referencedTable: apiFk.target_table,
      nullable: col.nullable,
    };
  }

  // 2) PK가 아니고 _id 접미사가 있으면 이름 기반 FK 추론
  if (!col.is_primary_key) {
    const lower = col.name.toLowerCase();
    if (lower.endsWith('_id')) {
      const baseName = lower.slice(0, -3); // '_id' 제거
      // 정확한 복수형 후보 탐색: user → user, users, useres
      const exactCandidates = [
        baseName,
        baseName + 's',
        baseName + 'es',
        baseName.replace(/ie$/, 'y'),
        baseName + 'ations', // org → organizations
        baseName + 'izations', // org → organizations
        baseName + 'anizations', // org → organizations
      ];
      for (const candidate of exactCandidates) {
        if (allTableNames.has(candidate)) {
          return {
            name: col.name,
            dataType: col.data_type,
            isPrimaryKey: false,
            isForeignKey: true,
            referencedTable: candidate,
            nullable: col.nullable,
          };
        }
      }
      // 접두사 매칭: baseName으로 시작하는 테이블이 하나만 있으면 매핑
      // 예: org_id → baseName "org" → "organizations" (org로 시작)
      const prefixMatches = [...allTableNames].filter(
        (t) => t.startsWith(baseName) && t !== baseName,
      );
      if (prefixMatches.length === 1) {
        return {
          name: col.name,
          dataType: col.data_type,
          isPrimaryKey: false,
          isForeignKey: true,
          referencedTable: prefixMatches[0],
          nullable: col.nullable,
        };
      }
    }
  }

  // 3) FK 아님
  return {
    name: col.name,
    dataType: col.data_type,
    isPrimaryKey: col.is_primary_key,
    isForeignKey: false,
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

  // 2단계: 각 테이블의 컬럼 병렬 조회 (최대 30개로 제한 — 과도한 동시 요청 방지)
  const columnQueries = useQueries({
    queries: tableNames.slice(0, 30).map((tableName) => ({
      queryKey: ['erd', 'columns', datasourceId, tableName],
      queryFn: () => getTableColumns(tableName, datasourceId!),
      enabled: !!datasourceId && tableNames.length > 0,
      staleTime: 5 * 60 * 1000,
    })),
  });

  // 모든 컬럼 쿼리 로딩 상태
  const columnsLoading = columnQueries.some((q) => q.isLoading);
  const isLoading = tablesLoading || columnsLoading;

  // FK 추론을 위한 전체 테이블명 집합 (소문자로 정규화)
  const allTableNames = new Set(tableNames.map((n) => n.toLowerCase()));

  // ERDTableInfo[] 변환 — FK 추론을 데이터 레이어에서 수행하여
  // getConnectedTables 등 다운스트림에서 isForeignKey 플래그를 올바르게 참조 가능
  const tables: ERDTableInfo[] = (tablesData?.tables ?? []).map((tableMeta, index) => {
    const colData = columnQueries[index]?.data ?? [];
    return {
      name: tableMeta.name,
      schema: tableMeta.schema,
      description: tableMeta.description ?? undefined,
      columns: colData.map((col) => toERDColumn(col, allTableNames)),
    };
  });

  return {
    tables,
    isLoading,
    error: tablesError,
    refetch,
  };
}
