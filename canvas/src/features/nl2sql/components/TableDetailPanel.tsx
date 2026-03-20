/**
 * TableDetailPanel — 테이블 상세 패널.
 *
 * 선택된 테이블의 컬럼 목록, 타입, PK/FK, 설명 등을 표시.
 * KAIR TableDetailPanel.vue를 React+shadcn/ui 패턴으로 이식.
 *
 * 표시 항목:
 *  - 컬럼 목록 (이름, 타입, PK/FK, nullable, 설명)
 *  - 테이블 통계 (컬럼 수)
 */

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import {
  X,
  Search,
  Key,
  Link,
  Table2,
  Columns3,
  Copy,
  Check,
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import type { ColumnMeta } from '../types/nl2sql';

// ─── Props ────────────────────────────────────────────────

interface TableDetailPanelProps {
  /** 테이블명 */
  tableName: string;
  /** 스키마명 */
  schema: string;
  /** 컬럼 목록 */
  columns: ColumnMeta[];
  /** 로딩 상태 */
  isLoading?: boolean;
  /** 닫기 핸들러 */
  onClose?: () => void;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function TableDetailPanel({
  tableName,
  schema,
  columns,
  isLoading,
  onClose,
}: TableDetailPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedCol, setCopiedCol] = useState<string | null>(null);

  // 검색 필터
  const filteredColumns = useMemo(() => {
    if (!searchQuery.trim()) return columns;
    const q = searchQuery.toLowerCase();
    return columns.filter(
      (col) =>
        col.name.toLowerCase().includes(q) ||
        col.data_type.toLowerCase().includes(q) ||
        col.description?.toLowerCase().includes(q)
    );
  }, [columns, searchQuery]);

  // PK/FK 통계
  const pkCount = columns.filter((c) => c.is_primary_key).length;
  const fkCount = columns.filter((c) => c.name.endsWith('_id') && !c.is_primary_key).length;

  // 컬럼명 복사
  const handleCopyColumn = (colName: string) => {
    navigator.clipboard.writeText(colName);
    setCopiedCol(colName);
    setTimeout(() => setCopiedCol(null), 1500);
  };

  return (
    <div className="flex flex-col h-full bg-white border-l border-[#E5E5E5]">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 h-10 border-b border-[#E5E5E5] shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Table2 className="h-3.5 w-3.5 text-blue-500 shrink-0" />
          <span className="text-[12px] font-semibold text-black font-[Sora] truncate">
            {tableName}
          </span>
          <span className="text-[10px] text-foreground/40 font-[IBM_Plex_Mono] shrink-0">
            {schema}
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-[#F0F0F0] transition-colors"
            aria-label="닫기"
          >
            <X className="h-3.5 w-3.5 text-foreground/40" />
          </button>
        )}
      </div>

      {/* 통계 바 */}
      <div className="flex items-center gap-4 px-4 py-2 bg-[#FAFAFA] border-b border-[#E5E5E5] text-[10px] font-[IBM_Plex_Mono] text-foreground/50">
        <span className="flex items-center gap-1">
          <Columns3 className="h-3 w-3" />
          {columns.length} 컬럼
        </span>
        {pkCount > 0 && (
          <span className="flex items-center gap-1">
            <Key className="h-3 w-3 text-amber-400" />
            {pkCount} PK
          </span>
        )}
        {fkCount > 0 && (
          <span className="flex items-center gap-1">
            <Link className="h-3 w-3 text-blue-400" />
            ~{fkCount} FK
          </span>
        )}
      </div>

      {/* 검색 */}
      <div className="px-3 py-2 border-b border-[#E5E5E5]">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-foreground/30" />
          <Input
            placeholder="컬럼 검색..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-7 h-7 text-[11px] bg-white border-[#E5E5E5] font-[IBM_Plex_Mono]"
          />
        </div>
      </div>

      {/* 컬럼 목록 */}
      <div className="flex-1 overflow-y-auto">
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <div className="h-4 w-4 border-2 border-foreground/20 border-t-foreground/50 rounded-full animate-spin" />
          </div>
        )}

        {!isLoading && filteredColumns.length === 0 && columns.length > 0 && (
          <div className="py-6 text-center">
            <p className="text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
              검색 결과가 없습니다
            </p>
          </div>
        )}

        {!isLoading && columns.length === 0 && (
          <div className="py-6 text-center">
            <p className="text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
              컬럼 정보 없음
            </p>
          </div>
        )}

        {!isLoading &&
          filteredColumns.map((col) => (
            <div
              key={col.name}
              className="flex items-start gap-2 px-4 py-2 border-b border-[#F0F0F0] hover:bg-[#FAFAFA] transition-colors group"
            >
              {/* 타입 아이콘 */}
              <div className="mt-0.5 shrink-0">
                {col.is_primary_key ? (
                  <Key className="h-3 w-3 text-amber-400" />
                ) : col.name.endsWith('_id') ? (
                  <Link className="h-3 w-3 text-blue-400" />
                ) : (
                  <Columns3 className="h-3 w-3 text-foreground/20" />
                )}
              </div>

              {/* 컬럼 정보 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-medium text-black font-[IBM_Plex_Mono] truncate">
                    {col.name}
                  </span>
                  <span
                    className={cn(
                      'text-[9px] px-1.5 py-0.5 rounded font-[IBM_Plex_Mono]',
                      'bg-[#F0F0F0] text-foreground/50'
                    )}
                  >
                    {col.data_type}
                  </span>
                  {col.nullable && (
                    <span className="text-[9px] text-foreground/30 font-[IBM_Plex_Mono]">
                      NULL
                    </span>
                  )}
                </div>
                {col.description && (
                  <p className="text-[10px] text-foreground/40 mt-0.5 line-clamp-2">
                    {col.description}
                  </p>
                )}
              </div>

              {/* 복사 버튼 */}
              <button
                type="button"
                onClick={() => handleCopyColumn(col.name)}
                className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-[#E5E5E5] transition-all shrink-0"
                aria-label={`${col.name} 복사`}
              >
                {copiedCol === col.name ? (
                  <Check className="h-3 w-3 text-green-500" />
                ) : (
                  <Copy className="h-3 w-3 text-foreground/30" />
                )}
              </button>
            </div>
          ))}
      </div>
    </div>
  );
}
