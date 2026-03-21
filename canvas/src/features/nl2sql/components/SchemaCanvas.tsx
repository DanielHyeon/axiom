/**
 * SchemaCanvas — ERD 드래그&드롭 캔버스 (Mermaid 기반).
 *
 * 선택된 테이블들의 ERD 시각화:
 *  - 기존 MermaidERDRenderer + mermaidCodeGen 재활용
 *  - 테이블 선택/해제 체크박스
 *  - "NL2SQL에 포함" 토글 — 선택된 테이블만 LLM 컨텍스트에 포함
 *  - FK 관계 자동 표시
 *
 * G1~G8 갭 기능 통합:
 *  - G1: FK 가시성 토글 (소스별 DDL/User/Fabric)
 *  - G2: 관계 편집 모달 (CardinalityModal)
 *  - G3: 스키마 편집 API 연동 (useSchemaEdit)
 *  - G4: column_pairs 구조 (ERD 렌더링에 반영)
 *  - G5: 실시간 캔버스 업데이트 (useCanvasPolling)
 *  - G6: 시맨틱 검색 (useSemanticSearch — 상위에서 사용)
 *  - G7: 논리명/물리명 토글 (useDisplayMode)
 *  - G8: 데이터 프리뷰 패널 (DataPreviewPanel)
 */

import { useMemo, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  Eye,
  EyeOff,
  X,
  Sparkles,
  ArrowLeftRight,
  Database,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
// ERD 렌더러, 코드 생성, 타입 모두 shared 레이어에서 가져온다 (feature 간 의존 제거)
import { MermaidERDRenderer } from '@/shared/components/MermaidERDRenderer';
import { generateMermaidERCode } from '@/shared/utils/mermaidCodeGen';
import type { ERDTableInfo, ColumnMeta } from '@/shared/types/schema';
import type { SchemaMode } from '@/shared/utils/nodeKey';
import type { SchemaAvailability } from '@/shared/types/schemaNavigation';
import { SchemaEmptyState } from './SchemaEmptyState';
// G1: FK 가시성 토글
import { FkVisibilityToolbar } from './FkVisibilityToolbar';
import { useFkVisibility } from '../hooks/useFkVisibility';
// G2: 관계 편집 모달
import { CardinalityModal } from './CardinalityModal';
// G3: 스키마 편집 API
import { useSchemaEdit } from '../hooks/useSchemaEdit';
// G5: 실시간 캔버스 업데이트
import { useCanvasPolling } from '../hooks/useCanvasPolling';
// G7: 논리명/물리명 토글
import { useDisplayMode } from '../hooks/useDisplayMode';
// G8: 데이터 프리뷰 패널
import { DataPreviewPanel } from './DataPreviewPanel';

// ─── Props ────────────────────────────────────────────────

export interface CanvasTable {
  tableName: string;
  schema: string;
  datasource?: string;  // 데이터소스 이름
  columns: ColumnMeta[];
  /** NL2SQL LLM 컨텍스트 포함 여부 */
  includedInContext: boolean;
  /** 테이블 설명 — G7 논리명 표시에 사용 */
  description?: string;
}

interface SchemaCanvasProps {
  /** 캔버스에 표시할 테이블 목록 */
  tables: CanvasTable[];
  /** 테이블 컨텍스트 토글 핸들러 */
  onToggleContext: (tableName: string) => void;
  /** 테이블 제거 핸들러 */
  onRemoveTable: (tableName: string) => void;
  /** 스키마 네비게이션 통합 props */
  mode?: SchemaMode;
  availability?: SchemaAvailability | null;
  onModeChange?: (mode: SchemaMode) => void;
  onNavigateDatasource?: () => void;
  /** G5: 외부에서 캔버스 리프레시를 트리거할 콜백 */
  onRefresh?: () => void;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function SchemaCanvas({
  tables,
  onToggleContext,
  onRemoveTable,
  mode,
  availability,
  onModeChange,
  onNavigateDatasource,
  onRefresh,
}: SchemaCanvasProps) {
  // G1: FK 가시성 상태
  const { visibility, toggle: toggleFkVisibility, isVisible: isFkVisible } = useFkVisibility();

  // G2: 관계 편집 모달 상태
  const [showCardinalityModal, setShowCardinalityModal] = useState(false);

  // G3: 스키마 편집 API 훅
  const { createRel } = useSchemaEdit();

  // G5: 실시간 캔버스 폴링 (테이블이 있을 때만 활성화)
  useCanvasPolling({
    enabled: tables.length > 0,
    onUpdate: () => onRefresh?.(),
  });

  // G7: 논리명/물리명 토글
  const { displayMode, toggleDisplayMode, getDisplayName } = useDisplayMode();

  // G8: 데이터 프리뷰 패널 상태
  const [previewTable, setPreviewTable] = useState<CanvasTable | null>(null);

  // Mermaid ERD 코드 생성 — G7 displayMode 반영
  const { code } = useMemo(() => {
    if (tables.length === 0) {
      return { code: '', stats: { tables: 0, relationships: 0, columns: 0 } };
    }

    // CanvasTable → ERDTableInfo 변환 — G7: 표시 모드에 따라 name/description 전환
    const erdTables: ERDTableInfo[] = tables.map((t) => ({
      name: getDisplayName(t.tableName, t.description),
      schema: t.schema,
      columns: t.columns.map((col) => ({
        name: getDisplayName(col.name, col.description),
        dataType: col.data_type,
        isPrimaryKey: col.is_primary_key,
        isForeignKey: col.name.endsWith('_id') && !col.is_primary_key,
        nullable: col.nullable,
      })),
    }));

    return generateMermaidERCode(erdTables, { maxColumnsPerTable: 6 });
  }, [tables, getDisplayName]);

  // 컨텍스트에 포함된 테이블 수
  const includedCount = tables.filter((t) => t.includedInContext).length;

  // G2: 관계 저장 핸들러
  const handleSaveRelationship = useCallback(
    (payload: {
      source_table: string;
      source_column: string;
      target_table: string;
      target_column: string;
      relationship_type: string;
      description: string;
    }) => {
      createRel.mutate(payload);
    },
    [createRel],
  );

  // G2: CardinalityModal에 전달할 테이블 옵션
  const tableOptions = useMemo(
    () =>
      tables.map((t) => ({
        name: t.tableName,
        schema: t.schema,
        columns: t.columns.map((c) => c.name),
      })),
    [tables],
  );

  // 빈 상태 — SchemaEmptyState 컴포넌트로 위임
  if (tables.length === 0) {
    return (
      <SchemaEmptyState
        mode={mode || 'text2sql'}
        availability={availability ?? null}
        onNavigateDatasource={onNavigateDatasource}
        onSwitchToText2sql={onModeChange ? () => onModeChange('text2sql') : undefined}
        onSwitchToRobo={onModeChange ? () => onModeChange('robo') : undefined}
      />
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 상단 바: 모드 전환 + 통계 + 테이블 칩 + 도구 버튼 */}
      <div className="flex items-center gap-2 px-3 py-2 bg-[#FAFAFA] border-b border-[#E5E5E5] overflow-x-auto">
        {/* 모드 전환 탭 — 제공된 경우에만 표시 */}
        {mode && onModeChange && (
          <div className="flex items-center gap-0.5 mr-3 shrink-0">
            <button
              type="button"
              onClick={() => onModeChange('robo')}
              className={cn(
                'px-2 py-0.5 rounded text-[10px] font-[IBM_Plex_Mono] transition-colors',
                mode === 'robo'
                  ? 'bg-foreground/10 text-foreground/70 font-medium'
                  : 'text-foreground/30 hover:text-foreground/50'
              )}
            >
              코드분석
              {availability && (
                <span className="ml-1 text-[9px] opacity-60">
                  {availability.robo.table_count}
                </span>
              )}
            </button>
            <button
              type="button"
              onClick={() => onModeChange('text2sql')}
              className={cn(
                'px-2 py-0.5 rounded text-[10px] font-[IBM_Plex_Mono] transition-colors',
                mode === 'text2sql'
                  ? 'bg-foreground/10 text-foreground/70 font-medium'
                  : 'text-foreground/30 hover:text-foreground/50'
              )}
            >
              데이터소스
              {availability && (
                <span className="ml-1 text-[9px] opacity-60">
                  {availability.text2sql.table_count}
                </span>
              )}
            </button>
          </div>
        )}

        {/* 통계 */}
        <div className="flex items-center gap-2 text-[10px] text-foreground/40 font-[IBM_Plex_Mono] shrink-0 mr-2">
          <Sparkles className="h-3 w-3" />
          <span>{includedCount}/{tables.length} 컨텍스트 포함</span>
        </div>

        {/* 테이블 칩 목록 */}
        {tables.map((t) => (
          <TableChip
            key={t.tableName}
            tableName={getDisplayName(t.tableName)}
            rawName={t.tableName}
            includedInContext={t.includedInContext}
            onToggleContext={() => onToggleContext(t.tableName)}
            onRemove={() => onRemoveTable(t.tableName)}
            onPreview={() => setPreviewTable(t)}
          />
        ))}

        {/* 우측 도구 버튼 그룹 — ml-auto로 오른쪽 정렬 */}
        <div className="flex items-center gap-1 ml-auto shrink-0">
          {/* G1: FK 가시성 토글 */}
          <FkVisibilityToolbar visibility={visibility} onToggle={toggleFkVisibility} />

          {/* 구분선 */}
          <div className="w-px h-4 bg-[#E5E5E5] mx-1" />

          {/* G7: 논리명/물리명 토글 */}
          <button
            type="button"
            onClick={toggleDisplayMode}
            className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-[IBM_Plex_Mono] text-foreground/50 hover:text-foreground/70 transition-colors"
            title={displayMode === 'physical' ? '논리명으로 전환' : '물리명으로 전환'}
          >
            {displayMode === 'physical' ? (
              <ToggleLeft className="h-3 w-3" />
            ) : (
              <ToggleRight className="h-3 w-3 text-blue-500" />
            )}
            <span>{displayMode === 'physical' ? '물리명' : '논리명'}</span>
          </button>

          {/* G2: 관계 추가 버튼 */}
          <button
            type="button"
            onClick={() => setShowCardinalityModal(true)}
            className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-[IBM_Plex_Mono] text-foreground/50 hover:text-foreground/70 transition-colors"
            title="FK 관계 추가"
          >
            <ArrowLeftRight className="h-3 w-3" />
            <span>관계추가</span>
          </button>
        </div>
      </div>

      {/* ERD 다이어그램 + G8 프리뷰 패널 */}
      <div className="flex flex-1 overflow-hidden">
        {/* ERD 영역 */}
        <div className="flex-1 overflow-hidden relative">
          {code ? (
            <MermaidERDRenderer mermaidCode={code} />
          ) : (
            <div className="flex items-center justify-center h-full text-foreground/30 text-[11px] font-[IBM_Plex_Mono]">
              ERD를 생성할 수 없습니다
            </div>
          )}
        </div>

        {/* G8: 데이터 프리뷰 패널 — 선택된 테이블이 있을 때만 표시 */}
        {previewTable && (
          <DataPreviewPanel
            tableName={previewTable.tableName}
            schema={previewTable.schema}
            datasource={previewTable.datasource}
            onClose={() => setPreviewTable(null)}
          />
        )}
      </div>

      {/* G2: 관계 편집 모달 */}
      <CardinalityModal
        open={showCardinalityModal}
        onClose={() => setShowCardinalityModal(false)}
        tables={tableOptions}
        onSave={handleSaveRelationship}
      />
    </div>
  );
}

// ─── 테이블 칩 ────────────────────────────────────────────

interface TableChipProps {
  tableName: string;
  rawName: string;
  includedInContext: boolean;
  onToggleContext: () => void;
  onRemove: () => void;
  onPreview: () => void;
}

function TableChip({
  tableName,
  rawName,
  includedInContext,
  onToggleContext,
  onRemove,
  onPreview,
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
        aria-label={`${rawName} 컨텍스트 ${includedInContext ? '제외' : '포함'}`}
      >
        {includedInContext ? (
          <Eye className="h-3 w-3" />
        ) : (
          <EyeOff className="h-3 w-3" />
        )}
      </button>

      <span className="truncate max-w-[100px]">{tableName}</span>

      {/* G8: 데이터 프리뷰 버튼 */}
      <button
        type="button"
        onClick={onPreview}
        className="hover:text-emerald-500 transition-colors"
        title="데이터 프리뷰"
        aria-label={`${rawName} 데이터 프리뷰`}
      >
        <Database className="h-2.5 w-2.5" />
      </button>

      {/* 제거 */}
      <button
        type="button"
        onClick={onRemove}
        className="hover:text-red-500 transition-colors"
        aria-label={`${rawName} 제거`}
      >
        <X className="h-2.5 w-2.5" />
      </button>
    </div>
  );
}
