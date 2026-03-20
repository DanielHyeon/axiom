/**
 * 스키마 트리 데이터 로딩 훅.
 * Oracle Meta API에서 테이블/컬럼 데이터를 계층적으로 로드.
 * TanStack Query 캐싱 + 지연 로딩 패턴 적용.
 */

import { useQuery } from '@tanstack/react-query';
import { useState, useCallback, useMemo } from 'react';
import { getTables, getTableColumns } from '../api/oracleNl2sqlApi';
import type { TableMeta, ColumnMeta } from '../types/nl2sql';
import type { TreeSelection, SchemaSearchResult } from '../types/schema';

/** 스키마별 테이블 그룹 */
interface SchemaGroup {
  schema: string;
  tables: TableMeta[];
}

/** useSchemaTree 훅의 반환값 */
interface UseSchemaTreeReturn {
  /** 스키마별 그룹 목록 */
  schemaGroups: SchemaGroup[];
  /** 전체 로딩 상태 */
  isLoading: boolean;
  /** 에러 */
  error: Error | null;
  /** 펼쳐진 스키마 집합 */
  expandedSchemas: Set<string>;
  /** 스키마 펼치기/접기 토글 */
  toggleSchema: (schema: string) => void;
  /** 현재 선택 상태 */
  selection: TreeSelection | null;
  /** 테이블 선택 */
  selectTable: (schema: string, table: string) => void;
  /** 컬럼 선택 */
  selectColumn: (schema: string, table: string, column: string) => void;
  /** 선택 해제 */
  clearSelection: () => void;
  /** 특정 테이블의 컬럼 로드 (캐시됨) */
  getColumns: (tableName: string) => ColumnMeta[] | undefined;
  /** 컬럼 로딩 중인 테이블 */
  loadingColumns: string | null;
  /** 테이블 클릭 시 컬럼 로드 트리거 */
  loadColumnsForTable: (tableName: string) => void;
  /** 검색 기능 */
  searchResults: SchemaSearchResult[];
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  /** 데이터 새로고침 */
  refetch: () => void;
}

export function useSchemaTree(datasourceId: string | null): UseSchemaTreeReturn {
  // 상태: 확장/선택/검색
  const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(new Set(['public']));
  const [selection, setSelection] = useState<TreeSelection | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // 컬럼 캐시 (테이블명 → 컬럼 목록)
  const [columnsCache, setColumnsCache] = useState<Record<string, ColumnMeta[]>>({});
  const [loadingColumns, setLoadingColumns] = useState<string | null>(null);

  // 1단계: 전체 테이블 목록 조회
  const {
    data: tablesData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['nl2sql', 'schemaTree', 'tables', datasourceId],
    queryFn: async () => {
      if (!datasourceId) return { tables: [], pagination: { page: 1, page_size: 200, total_count: 0, total_pages: 0 } };
      return getTables({ datasource_id: datasourceId, page_size: 200 });
    },
    enabled: !!datasourceId,
    staleTime: 5 * 60 * 1000, // 5분 캐시
  });

  // 스키마별 그룹화
  const schemaGroups: SchemaGroup[] = useMemo(() => {
    const tables = tablesData?.tables ?? [];
    const groups = new Map<string, TableMeta[]>();

    for (const table of tables) {
      const schema = table.schema || 'public';
      if (!groups.has(schema)) groups.set(schema, []);
      groups.get(schema)!.push(table);
    }

    // 알파벳 정렬
    return Array.from(groups.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([schema, tables]) => ({
        schema,
        tables: tables.sort((a, b) => a.name.localeCompare(b.name)),
      }));
  }, [tablesData]);

  // 스키마 토글
  const toggleSchema = useCallback((schema: string) => {
    setExpandedSchemas((prev) => {
      const next = new Set(prev);
      if (next.has(schema)) next.delete(schema);
      else next.add(schema);
      return next;
    });
  }, []);

  // 테이블 선택
  const selectTable = useCallback((schema: string, table: string) => {
    setSelection({ type: 'table', schema, table });
  }, []);

  // 컬럼 선택
  const selectColumn = useCallback((schema: string, table: string, column: string) => {
    setSelection({ type: 'column', schema, table, column });
  }, []);

  // 선택 해제
  const clearSelection = useCallback(() => {
    setSelection(null);
  }, []);

  // 컬럼 로드
  const loadColumnsForTable = useCallback(async (tableName: string) => {
    if (columnsCache[tableName] || !datasourceId) return;
    setLoadingColumns(tableName);
    try {
      const cols = await getTableColumns(tableName, datasourceId);
      setColumnsCache((prev) => ({ ...prev, [tableName]: cols }));
    } catch {
      // 에러 시 빈 배열 캐싱 (재시도 가능)
      setColumnsCache((prev) => ({ ...prev, [tableName]: [] }));
    } finally {
      setLoadingColumns(null);
    }
  }, [columnsCache, datasourceId]);

  // 컬럼 조회
  const getColumns = useCallback((tableName: string) => {
    return columnsCache[tableName];
  }, [columnsCache]);

  // 검색 결과 계산
  const searchResults: SchemaSearchResult[] = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    const results: SchemaSearchResult[] = [];

    for (const group of schemaGroups) {
      for (const table of group.tables) {
        // 테이블명 매칭
        if (table.name.toLowerCase().includes(q)) {
          results.push({
            type: 'table',
            tableName: table.name,
            schema: group.schema,
            matchedText: table.name,
          });
        }

        // 컬럼명 매칭 (캐시된 컬럼만)
        const cols = columnsCache[table.name];
        if (cols) {
          for (const col of cols) {
            if (col.name.toLowerCase().includes(q)) {
              results.push({
                type: 'column',
                tableName: table.name,
                columnName: col.name,
                schema: group.schema,
                matchedText: `${table.name}.${col.name}`,
              });
            }
          }
        }
      }
    }

    return results.slice(0, 50); // 최대 50개 결과
  }, [searchQuery, schemaGroups, columnsCache]);

  return {
    schemaGroups,
    isLoading,
    error: error as Error | null,
    expandedSchemas,
    toggleSchema,
    selection,
    selectTable,
    selectColumn,
    clearSelection,
    getColumns,
    loadingColumns,
    loadColumnsForTable,
    searchResults,
    searchQuery,
    setSearchQuery,
    refetch: () => refetch(),
  };
}
