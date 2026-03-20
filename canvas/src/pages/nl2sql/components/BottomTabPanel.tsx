/**
 * BottomTabPanel — 하단 탭 패널 (결과 / 스키마 캔버스)
 *
 * 쿼리 결과 테이블과 스키마 캔버스(ERD)를 탭으로 전환해서 보여준다.
 * 결과 탭에는 ResultPanel + FeedbackWidget이 포함된다.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Table2, LayoutGrid, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ResultPanel } from './ResultPanel';
import { SchemaCanvas } from '@/features/nl2sql/components/SchemaCanvas';
import { FeedbackWidget } from '@/features/nl2sql/components/FeedbackWidget';
import type { AskResponse } from '@/features/nl2sql/api/oracleNl2sqlApi';
import type { ChartConfig, ExecutionMetadata } from '@/features/nl2sql/types/nl2sql';
import type { CanvasTable } from './SchemaSidebar';

interface BottomTabPanelProps {
  /** 최종 결과 데이터 */
  resultData: AskResponse['data'] | null;
  /** 결과 컬럼 목록 */
  resultColumns: { name: string; type: string }[];
  /** 결과 행 목록 */
  resultRows: unknown[][];
  /** 차트 설정 (자동 감지 포함) */
  effectiveChartConfig: ChartConfig | null;
  /** 캔버스 테이블 목록 */
  canvasTables: CanvasTable[];
  /** 캔버스 테이블 컨텍스트 토글 핸들러 */
  onToggleContext: (tableName: string) => void;
  /** 캔버스 테이블 제거 핸들러 */
  onRemoveCanvasTable: (tableName: string) => void;
}

export function BottomTabPanel({
  resultData,
  resultColumns,
  resultRows,
  effectiveChartConfig,
  canvasTables,
  onToggleContext,
  onRemoveCanvasTable,
}: BottomTabPanelProps) {
  const { t } = useTranslation();
  // 현재 활성 탭: 결과 또는 스키마
  const [bottomTab, setBottomTab] = useState<'results' | 'schema'>('results');

  // 탭이 보일 조건: 결과가 있거나 캔버스 테이블이 있을 때
  const showTabs = resultData || canvasTables.length > 0;
  if (!showTabs) return null;

  return (
    <>
      {/* 탭 전환 바 */}
      <div className="flex items-center gap-1 border-b border-[#E5E5E5]">
        <button
          type="button"
          onClick={() => setBottomTab('results')}
          className={cn(
            'flex items-center gap-1.5 px-4 py-2 text-[12px] font-medium font-[Sora] border-b-2 transition-colors',
            bottomTab === 'results'
              ? 'border-black text-black'
              : 'border-transparent text-foreground/40 hover:text-foreground/60',
          )}
        >
          <Table2 className="h-3.5 w-3.5" />
          {t('nl2sql.queryResult')}
          {resultData?.result?.row_count != null && (
            <span className="ml-1 bg-[#F5F5F5] px-1.5 py-0.5 text-[10px] text-[#5E5E5E] font-[IBM_Plex_Mono] rounded">
              {resultData.result.row_count}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setBottomTab('schema')}
          className={cn(
            'flex items-center gap-1.5 px-4 py-2 text-[12px] font-medium font-[Sora] border-b-2 transition-colors',
            bottomTab === 'schema'
              ? 'border-black text-black'
              : 'border-transparent text-foreground/40 hover:text-foreground/60',
          )}
        >
          <LayoutGrid className="h-3.5 w-3.5" />
          Schema Canvas
          {canvasTables.length > 0 && (
            <span className="ml-1 bg-[#F5F5F5] px-1.5 py-0.5 text-[10px] text-[#5E5E5E] font-[IBM_Plex_Mono] rounded">
              {canvasTables.length}
            </span>
          )}
        </button>
      </div>

      {/* Results 탭 — 쿼리 결과 + 피드백 */}
      {bottomTab === 'results' && resultData && resultColumns.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-[14px] font-semibold text-black font-[Sora]">{t('nl2sql.queryResult')}</h2>
              <span className="bg-[#F5F5F5] px-2.5 py-0.5 text-[11px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                {resultData.result?.row_count ?? 0} rows
              </span>
            </div>
            <button
              type="button"
              className="flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium text-black border border-[#E5E5E5] rounded hover:bg-[#F5F5F5] transition-colors font-[Sora]"
            >
              <Download className="h-3.5 w-3.5" />
              {t('nl2sql.export')}
            </button>
          </div>
          <ResultPanel
            sql={resultData.sql}
            columns={resultColumns}
            rows={resultRows}
            rowCount={resultData.result?.row_count ?? 0}
            chartConfig={effectiveChartConfig}
            summary={resultData.summary ?? null}
            metadata={(resultData.metadata as ExecutionMetadata) ?? null}
          />
          {/* 피드백 위젯 — 결과 하단에 표시 */}
          <FeedbackWidget
            queryId={resultData.metadata?.query_id}
            sql={resultData.sql}
          />
        </div>
      )}

      {/* Schema Canvas 탭 — ERD 시각화 */}
      {bottomTab === 'schema' && (
        <div className="border border-[#E5E5E5] rounded overflow-hidden" style={{ minHeight: 400 }}>
          <SchemaCanvas
            tables={canvasTables}
            onToggleContext={onToggleContext}
            onRemoveTable={onRemoveCanvasTable}
          />
        </div>
      )}
    </>
  );
}
