/**
 * SchemaSidebar — 좌측 스키마 트리 + 테이블 상세 패널
 *
 * 데이터베이스 트리에서 테이블을 탐색하고,
 * 선택한 테이블의 컬럼 상세 정보를 보여준다.
 */
import { useCallback, useState } from 'react';
import { DatabaseTree } from '@/features/nl2sql/components/DatabaseTree';
import { SchemaSearchBar } from '@/features/nl2sql/components/SchemaSearchBar';
import { TableDetailPanel } from '@/features/nl2sql/components/TableDetailPanel';
import type { useSchemaTree } from '@/features/nl2sql/hooks/useSchemaTree';
import type { useTableDetail } from '@/features/nl2sql/hooks/useTableDetail';
import type { ColumnMeta } from '@/features/nl2sql/types/nl2sql';

// === 캔버스 테이블 타입 (ERD 시각화에 사용) ===
export interface CanvasTable {
  tableName: string;
  schema: string;
  columns: ColumnMeta[];
  includedInContext: boolean;
}

interface SchemaSidebarProps {
  /** 스키마 트리 훅에서 반환된 객체 */
  schemaTree: ReturnType<typeof useSchemaTree>;
  /** 선택된 테이블 상세 훅에서 반환된 객체 */
  tableDetail: ReturnType<typeof useTableDetail>;
  /** 현재 선택된 테이블 이름 */
  selectedTableName: string | null;
  /** 현재 선택된 테이블의 스키마 */
  selectedTableSchema: string | null;
  /** 캔버스 테이블 목록 업데이트 함수 */
  onCanvasTablesChange: React.Dispatch<React.SetStateAction<CanvasTable[]>>;
}

export function SchemaSidebar({
  schemaTree,
  tableDetail,
  selectedTableName,
  selectedTableSchema,
  onCanvasTablesChange,
}: SchemaSidebarProps) {
  // 테이블 펼침 상태 (컬럼 보기 토글)
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  // 트리에서 테이블 선택 시 캔버스에 자동 추가
  const handleSelectTableInTree = useCallback(
    (schema: string, table: string) => {
      schemaTree.selectTable(schema, table);
      schemaTree.loadColumnsForTable(table);
      // 캔버스에 아직 없으면 추가
      onCanvasTablesChange((prev) => {
        if (prev.some((t) => t.tableName === table)) return prev;
        const cols = schemaTree.getColumns(table) ?? [];
        return [...prev, { tableName: table, schema, columns: cols, includedInContext: true }];
      });
    },
    [schemaTree, onCanvasTablesChange],
  );

  // 테이블 펼침 토글 (컬럼 표시)
  const handleToggleTableExpand = useCallback((tableName: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(tableName)) next.delete(tableName);
      else next.add(tableName);
      return next;
    });
  }, []);

  // 검색 결과 선택 시 트리 노드로 이동
  const handleSearchResultSelect = useCallback(
    (result: { type: string; schema: string; tableName: string }) => {
      schemaTree.toggleSchema(result.schema);
      if (result.type === 'table') {
        handleSelectTableInTree(result.schema, result.tableName);
      }
    },
    [schemaTree, handleSelectTableInTree],
  );

  return (
    <>
      {/* 좌측 사이드바: 데이터베이스 트리 */}
      <div className="w-64 shrink-0 border-r border-[#E5E5E5] flex flex-col bg-white">
        {/* 검색 바 */}
        <SchemaSearchBar
          value={schemaTree.searchQuery}
          onChange={schemaTree.setSearchQuery}
          results={schemaTree.searchResults}
          onSelectResult={handleSearchResultSelect}
        />
        {/* 트리 */}
        <div className="flex-1 overflow-hidden">
          <DatabaseTree
            schemaGroups={schemaTree.schemaGroups}
            isLoading={schemaTree.isLoading}
            expandedSchemas={schemaTree.expandedSchemas}
            onToggleSchema={schemaTree.toggleSchema}
            selection={schemaTree.selection}
            onSelectTable={handleSelectTableInTree}
            getColumns={schemaTree.getColumns}
            loadingColumns={schemaTree.loadingColumns}
            onLoadColumns={schemaTree.loadColumnsForTable}
            expandedTables={expandedTables}
            onToggleTable={handleToggleTableExpand}
          />
        </div>
      </div>

      {/* 선택된 테이블 상세 패널 */}
      {selectedTableName && tableDetail.detail && (
        <div className="w-72 shrink-0">
          <TableDetailPanel
            tableName={selectedTableName}
            schema={selectedTableSchema ?? 'public'}
            columns={tableDetail.detail.columns}
            isLoading={tableDetail.isLoading}
            onClose={schemaTree.clearSelection}
          />
        </div>
      )}
    </>
  );
}
