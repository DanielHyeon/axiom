/**
 * SchemaCanvas — ERD 드래그&드롭 캔버스 (Mermaid 기반).
 *
 * 선택된 테이블들의 ERD 시각화:
 *  - 기존 MermaidERDRenderer + mermaidCodeGen 재활용
 *  - 테이블 선택/해제 체크박스
 *  - "NL2SQL에 포함" 토글 — 선택된 테이블만 LLM 컨텍스트에 포함
 *  - FK 관계 자동 표시
 *
 * KAIR SchemaCanvas.vue를 Mermaid 기반으로 단순 이식 (ReactFlow 전환은 Phase 2.5).
 */

import { useState, useMemo, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  Table2,
  Eye,
  EyeOff,
  X,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Sparkles,
} from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
// ERD 렌더러, 코드 생성, 타입 모두 shared 레이어에서 가져온다 (feature 간 의존 제거)
import { MermaidERDRenderer } from '@/shared/components/MermaidERDRenderer';
import { generateMermaidERCode } from '@/shared/utils/mermaidCodeGen';
import type { ERDTableInfo, ColumnMeta } from '@/shared/types/schema';

// ─── Props ────────────────────────────────────────────────

interface CanvasTable {
  tableName: string;
  schema: string;
  columns: ColumnMeta[];
  /** NL2SQL LLM 컨텍스트 포함 여부 */
  includedInContext: boolean;
}

interface SchemaCanvasProps {
  /** 캔버스에 표시할 테이블 목록 */
  tables: CanvasTable[];
  /** 테이블 컨텍스트 토글 핸들러 */
  onToggleContext: (tableName: string) => void;
  /** 테이블 제거 핸들러 */
  onRemoveTable: (tableName: string) => void;
  /** 전체 테이블 목록 (추가 가능한 테이블 필터용) */
  allTableNames?: string[];
  /** 테이블 추가 핸들러 */
  onAddTable?: (tableName: string) => void;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function SchemaCanvas({
  tables,
  onToggleContext,
  onRemoveTable,
}: SchemaCanvasProps) {
  // Mermaid ERD 코드 생성
  const { code, stats } = useMemo(() => {
    if (tables.length === 0) {
      return { code: '', stats: { tables: 0, relationships: 0, columns: 0 } };
    }

    // CanvasTable → ERDTableInfo 변환
    const erdTables: ERDTableInfo[] = tables.map((t) => ({
      name: t.tableName,
      schema: t.schema,
      columns: t.columns.map((col) => ({
        name: col.name,
        dataType: col.data_type,
        isPrimaryKey: col.is_primary_key,
        isForeignKey: col.name.endsWith('_id') && !col.is_primary_key,
        nullable: col.nullable,
      })),
    }));

    return generateMermaidERCode(erdTables, { maxColumnsPerTable: 6 });
  }, [tables]);

  // 컨텍스트에 포함된 테이블 수
  const includedCount = tables.filter((t) => t.includedInContext).length;

  // 빈 상태
  if (tables.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <Table2 className="h-8 w-8 text-foreground/15 mb-3" />
        <p className="text-[13px] text-foreground/40 font-[Sora]">
          스키마 캔버스
        </p>
        <p className="text-[11px] text-foreground/25 font-[IBM_Plex_Mono] mt-1">
          좌측 트리에서 테이블을 선택하면 ERD가 표시됩니다
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 상단 바: 테이블 체크박스 + 통계 */}
      <div className="flex items-center gap-2 px-3 py-2 bg-[#FAFAFA] border-b border-[#E5E5E5] overflow-x-auto">
        {/* 통계 */}
        <div className="flex items-center gap-2 text-[10px] text-foreground/40 font-[IBM_Plex_Mono] shrink-0 mr-2">
          <Sparkles className="h-3 w-3" />
          <span>{includedCount}/{tables.length} 컨텍스트 포함</span>
        </div>

        {/* 테이블 칩 목록 */}
        {tables.map((t) => (
          <TableChip
            key={t.tableName}
            tableName={t.tableName}
            includedInContext={t.includedInContext}
            onToggleContext={() => onToggleContext(t.tableName)}
            onRemove={() => onRemoveTable(t.tableName)}
          />
        ))}
      </div>

      {/* ERD 다이어그램 */}
      <div className="flex-1 overflow-hidden relative">
        {code ? (
          <MermaidERDRenderer mermaidCode={code} />
        ) : (
          <div className="flex items-center justify-center h-full text-foreground/30 text-[11px] font-[IBM_Plex_Mono]">
            ERD를 생성할 수 없습니다
          </div>
        )}
      </div>
    </div>
  );
}

// ─── 테이블 칩 ────────────────────────────────────────────

interface TableChipProps {
  tableName: string;
  includedInContext: boolean;
  onToggleContext: () => void;
  onRemove: () => void;
}

function TableChip({
  tableName,
  includedInContext,
  onToggleContext,
  onRemove,
}: TableChipProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-[IBM_Plex_Mono] shrink-0 transition-colors',
        includedInContext
          ? 'bg-blue-50 text-blue-700 border border-blue-200'
          : 'bg-[#F0F0F0] text-foreground/40 border border-[#E5E5E5]'
      )}
    >
      {/* NL2SQL 컨텍스트 토글 */}
      <button
        type="button"
        onClick={onToggleContext}
        className="hover:opacity-70 transition-opacity"
        title={includedInContext ? 'NL2SQL 컨텍스트에서 제외' : 'NL2SQL 컨텍스트에 포함'}
        aria-label={`${tableName} 컨텍스트 ${includedInContext ? '제외' : '포함'}`}
      >
        {includedInContext ? (
          <Eye className="h-3 w-3" />
        ) : (
          <EyeOff className="h-3 w-3" />
        )}
      </button>

      <span className="truncate max-w-[100px]">{tableName}</span>

      {/* 제거 */}
      <button
        type="button"
        onClick={onRemove}
        className="hover:text-red-500 transition-colors"
        aria-label={`${tableName} 제거`}
      >
        <X className="h-2.5 w-2.5" />
      </button>
    </div>
  );
}
