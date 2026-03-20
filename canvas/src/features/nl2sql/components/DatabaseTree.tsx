/**
 * DatabaseTree — DB 스키마 트리 네비게이터.
 *
 * 3단계 계층: Schema → Table → Column
 * - 접기/펼치기 (TreeView 패턴)
 * - 아이콘: Schema(Database), Table(Table2), Column(Columns)
 * - 클릭 시 테이블/컬럼 선택 → 상위 컴포넌트에 이벤트 전달
 * - KAIR DatabaseTree.vue를 React+Tailwind+shadcn 패턴으로 이식
 */

import { useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  ChevronRight,
  ChevronDown,
  Database,
  Table2,
  Columns3,
  Key,
  Loader2,
} from 'lucide-react';
import type { TableMeta, ColumnMeta } from '../types/nl2sql';
import type { TreeSelection } from '../types/schema';

// ─── Props ────────────────────────────────────────────────

interface SchemaGroup {
  schema: string;
  tables: TableMeta[];
}

interface DatabaseTreeProps {
  /** 스키마별 그룹 목록 */
  schemaGroups: SchemaGroup[];
  /** 전체 로딩 상태 */
  isLoading: boolean;
  /** 펼쳐진 스키마 집합 */
  expandedSchemas: Set<string>;
  /** 스키마 토글 핸들러 */
  onToggleSchema: (schema: string) => void;
  /** 현재 선택 상태 */
  selection: TreeSelection | null;
  /** 테이블 선택 핸들러 */
  onSelectTable: (schema: string, table: string) => void;
  /** 컬럼 데이터 조회 함수 */
  getColumns?: (tableName: string) => ColumnMeta[] | undefined;
  /** 컬럼 로딩 중인 테이블명 */
  loadingColumns?: string | null;
  /** 컬럼 로드 트리거 */
  onLoadColumns?: (tableName: string) => void;
  /** 펼쳐진 테이블 (컬럼 표시 용) */
  expandedTables?: Set<string>;
  /** 테이블 펼치기 토글 */
  onToggleTable?: (tableName: string) => void;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function DatabaseTree({
  schemaGroups,
  isLoading,
  expandedSchemas,
  onToggleSchema,
  selection,
  onSelectTable,
  getColumns,
  loadingColumns,
  onLoadColumns,
  expandedTables,
  onToggleTable,
}: DatabaseTreeProps) {
  // 테이블 클릭: 선택 + 컬럼 로드
  const handleTableClick = useCallback(
    (schema: string, tableName: string) => {
      onSelectTable(schema, tableName);
    },
    [onSelectTable]
  );

  // 테이블 chevron 클릭: 컬럼 펼치기/접기
  const handleTableToggle = useCallback(
    (tableName: string) => {
      onToggleTable?.(tableName);
      // 컬럼이 아직 로드되지 않았으면 로드
      if (getColumns && !getColumns(tableName)) {
        onLoadColumns?.(tableName);
      }
    },
    [onToggleTable, getColumns, onLoadColumns]
  );

  // 로딩 상태
  if (isLoading) {
    return (
      <div className="flex flex-col h-full bg-white">
        <TreeHeader />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-4 w-4 animate-spin text-foreground/40" />
        </div>
      </div>
    );
  }

  // 빈 상태
  if (schemaGroups.length === 0) {
    return (
      <div className="flex flex-col h-full bg-white">
        <TreeHeader />
        <div className="flex-1 flex items-center justify-center px-4">
          <p className="text-xs text-foreground/40 font-[IBM_Plex_Mono] text-center">
            데이터소스를 선택하면<br />스키마 트리가 표시됩니다.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white">
      <TreeHeader />

      {/* 트리 컨텐츠 */}
      <div className="flex-1 overflow-y-auto py-1">
        {schemaGroups.map((group) => (
          <SchemaNode
            key={group.schema}
            schema={group.schema}
            tables={group.tables}
            isExpanded={expandedSchemas.has(group.schema)}
            onToggle={() => onToggleSchema(group.schema)}
            selection={selection}
            onSelectTable={handleTableClick}
            getColumns={getColumns}
            loadingColumns={loadingColumns}
            expandedTables={expandedTables}
            onToggleTable={handleTableToggle}
          />
        ))}
      </div>
    </div>
  );
}

// ─── 내부 컴포넌트 ────────────────────────────────────────

/** 트리 헤더 */
function TreeHeader() {
  return (
    <div className="flex items-center h-10 px-4 border-b border-[#E5E5E5] shrink-0">
      <span className="text-[11px] font-semibold text-foreground/50 font-[IBM_Plex_Mono] uppercase tracking-[1px]">
        데이터 자산
      </span>
    </div>
  );
}

// ─── SchemaNode ───────────────────────────────────────────

interface SchemaNodeProps {
  schema: string;
  tables: TableMeta[];
  isExpanded: boolean;
  onToggle: () => void;
  selection: TreeSelection | null;
  onSelectTable: (schema: string, table: string) => void;
  getColumns?: (tableName: string) => ColumnMeta[] | undefined;
  loadingColumns?: string | null;
  expandedTables?: Set<string>;
  onToggleTable?: (tableName: string) => void;
}

function SchemaNode({
  schema,
  tables,
  isExpanded,
  onToggle,
  selection,
  onSelectTable,
  getColumns,
  loadingColumns,
  expandedTables,
  onToggleTable,
}: SchemaNodeProps) {
  const ChevronIcon = isExpanded ? ChevronDown : ChevronRight;

  return (
    <div>
      {/* 스키마 행 */}
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-2 w-full text-left px-3 py-1.5 hover:bg-[#F5F5F5] transition-colors"
      >
        <ChevronIcon className="h-3 w-3 text-foreground/40 shrink-0" />
        <Database className="h-3.5 w-3.5 text-amber-500 shrink-0" />
        <span className="text-[12px] font-medium text-foreground/80 font-[IBM_Plex_Mono] truncate">
          {schema}
        </span>
        <span className="ml-auto text-[10px] text-foreground/30 font-[IBM_Plex_Mono]">
          {tables.length}
        </span>
      </button>

      {/* 테이블 목록 */}
      {isExpanded && (
        <div className="ml-3 border-l border-[#E5E5E5]">
          {tables.map((table) => {
            const isSelected =
              selection?.type === 'table' &&
              selection.schema === schema &&
              selection.table === table.name;
            const isTableExpanded = expandedTables?.has(table.name) ?? false;
            const columns = getColumns?.(table.name);
            const isColumnLoading = loadingColumns === table.name;

            return (
              <div key={table.name}>
                {/* 테이블 행 */}
                <div
                  className={cn(
                    'flex items-center gap-1.5 w-full text-left pl-3 pr-3 py-1 transition-colors cursor-pointer',
                    isSelected
                      ? 'bg-blue-50 text-blue-700'
                      : 'hover:bg-[#F5F5F5] text-foreground/70'
                  )}
                >
                  {/* Chevron (컬럼 펼치기) */}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onToggleTable?.(table.name);
                    }}
                    className="p-0.5 hover:bg-black/5 rounded shrink-0"
                    aria-label={`${table.name} 컬럼 ${isTableExpanded ? '접기' : '펼치기'}`}
                  >
                    {isTableExpanded ? (
                      <ChevronDown className="h-2.5 w-2.5 text-foreground/40" />
                    ) : (
                      <ChevronRight className="h-2.5 w-2.5 text-foreground/40" />
                    )}
                  </button>

                  {/* 테이블명 (클릭 → 선택) */}
                  <button
                    type="button"
                    onClick={() => onSelectTable(schema, table.name)}
                    className="flex items-center gap-1.5 flex-1 min-w-0 text-left"
                  >
                    <Table2 className="h-3 w-3 text-blue-400 shrink-0" />
                    <span className="text-[11px] font-[IBM_Plex_Mono] truncate">
                      {table.name}
                    </span>
                  </button>

                  {/* 컬럼 수 뱃지 */}
                  <span className="text-[9px] text-foreground/30 font-[IBM_Plex_Mono] shrink-0">
                    {table.column_count}
                  </span>
                </div>

                {/* 컬럼 목록 (펼쳐진 경우) */}
                {isTableExpanded && (
                  <div className="ml-6 border-l border-[#E5E5E5]">
                    {isColumnLoading && (
                      <div className="flex items-center gap-1.5 px-3 py-1">
                        <Loader2 className="h-2.5 w-2.5 animate-spin text-foreground/30" />
                        <span className="text-[10px] text-foreground/30 font-[IBM_Plex_Mono]">
                          로딩 중...
                        </span>
                      </div>
                    )}
                    {columns?.map((col) => (
                      <ColumnRow key={col.name} column={col} />
                    ))}
                    {!isColumnLoading && columns && columns.length === 0 && (
                      <div className="px-3 py-1">
                        <span className="text-[10px] text-foreground/30 font-[IBM_Plex_Mono]">
                          컬럼 없음
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── ColumnRow ────────────────────────────────────────────

interface ColumnRowProps {
  column: ColumnMeta;
}

function ColumnRow({ column }: ColumnRowProps) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-0.5 text-foreground/50 hover:bg-[#F5F5F5] transition-colors">
      {column.is_primary_key ? (
        <Key className="h-2.5 w-2.5 text-amber-400 shrink-0" />
      ) : (
        <Columns3 className="h-2.5 w-2.5 text-foreground/25 shrink-0" />
      )}
      <span className="text-[10px] font-[IBM_Plex_Mono] truncate flex-1">
        {column.name}
      </span>
      <span className="text-[9px] text-foreground/25 font-[IBM_Plex_Mono] shrink-0">
        {normalizeTypeDisplay(column.data_type)}
      </span>
    </div>
  );
}

/** 데이터 타입을 축약 표시 */
function normalizeTypeDisplay(rawType: string): string {
  const t = rawType.toLowerCase();
  if (t.includes('varchar') || t.includes('character varying')) return 'varchar';
  if (t.includes('timestamp')) return 'timestamp';
  if (t.includes('integer') || t === 'int4') return 'int';
  if (t.includes('bigint') || t === 'int8') return 'bigint';
  if (t.includes('boolean')) return 'bool';
  if (t.includes('numeric') || t.includes('decimal')) return 'numeric';
  if (t.includes('text')) return 'text';
  if (t.includes('uuid')) return 'uuid';
  if (t.includes('json')) return 'json';
  if (t.includes('date')) return 'date';
  return rawType.length > 10 ? rawType.slice(0, 10) : rawType;
}
