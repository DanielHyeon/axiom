/**
 * NL2SQL 페이지 — 자연어 → SQL 변환 + 실행 (오케스트레이터)
 *
 * 이 파일은 하위 컴포넌트와 훅을 조합하는 얇은 조립 계층이다.
 * 비즈니스 로직은 useNl2SqlChat 훅에, UI 조각은 각 서브 컴포넌트에 있다.
 */
import { useState, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { useRole } from '@/shared/hooks/useRole';
import { useSchemaTree } from '@/features/nl2sql/hooks/useSchemaTree';
import { useTableDetail } from '@/features/nl2sql/hooks/useTableDetail';
import { useNl2SqlChat } from '@/features/nl2sql/hooks/useNl2SqlChat';

import { HumanInTheLoopInput } from '@/features/nl2sql/components/HumanInTheLoopInput';
import { QueryHistoryPanel } from '@/features/nl2sql/components/QueryHistoryPanel';
import { ReactSummaryPanel } from '@/features/nl2sql/components/ReactSummaryPanel';
import { EmptyState } from '@/shared/components/EmptyState';

import { SchemaSidebar, type CanvasTable } from './components/SchemaSidebar';
import { QueryToolbar } from './components/QueryToolbar';
import { QueryInputForm } from './components/QueryInputForm';
import { ChatMessageList } from './components/ChatMessageList';
import { BottomTabPanel } from './components/BottomTabPanel';
import { DirectSqlPanel } from './components/DirectSqlPanel';
import { ReactProgressTimeline } from './components/ReactProgressTimeline';

import { Database } from 'lucide-react';

export function NL2SQLPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case_id') || undefined;
  const isAdmin = useRole(['admin']);

  // === 페이지 수준 상태 ===
  const [datasourceId, setDatasourceId] = useState('');
  const [rowLimit, setRowLimit] = useState<number>(1000);
  const [mode, setMode] = useState<'react' | 'ask'>('react');
  const [schemaTreeOpen, setSchemaTreeOpen] = useState(false);
  const [historyOpen] = useState(true);
  const [canvasTables, setCanvasTables] = useState<CanvasTable[]>([]);

  // === QueryInputForm에서 prompt 값을 설정하는 함수를 받아오기 위한 ref ===
  const setPromptRef = useRef<((value: string) => void) | null>(null);

  // === 채팅 + 스트리밍 로직 (커스텀 훅) ===
  const chat = useNl2SqlChat({ datasourceId, caseId, rowLimit, mode });

  // === 스키마 트리 + 테이블 상세 ===
  const schemaTree = useSchemaTree(datasourceId || null);
  const selectedTableName = schemaTree.selection?.type === 'table' ? schemaTree.selection.table : null;
  const selectedTableSchema = schemaTree.selection?.type === 'table' ? schemaTree.selection.schema : null;
  const tableDetail = useTableDetail(selectedTableName, datasourceId || null, selectedTableSchema ?? undefined);

  // === 캔버스 테이블 조작 ===
  const handleToggleContext = useCallback((tableName: string) => {
    setCanvasTables((prev) =>
      prev.map((t) => (t.tableName === tableName ? { ...t, includedInContext: !t.includedInContext } : t)),
    );
  }, []);

  const handleRemoveCanvasTable = useCallback((tableName: string) => {
    setCanvasTables((prev) => prev.filter((t) => t.tableName !== tableName));
  }, []);

  // === 예제 질문 ===
  const EXAMPLE_QUESTIONS = [
    t('nl2sql.exampleQuestions.q1'),
    t('nl2sql.exampleQuestions.q2'),
    t('nl2sql.exampleQuestions.q3'),
    t('nl2sql.exampleQuestions.q4'),
  ];

  const isEmpty = chat.messages.length === 0 && !chat.loading;

  return (
    <div className="flex h-full">
      {/* 좌측 사이드바: 스키마 트리 + 테이블 상세 */}
      {schemaTreeOpen && (
        <SchemaSidebar
          schemaTree={schemaTree}
          tableDetail={tableDetail}
          selectedTableName={selectedTableName}
          selectedTableSchema={selectedTableSchema}
          onCanvasTablesChange={setCanvasTables}
        />
      )}

      {/* 메인 콘텐츠 영역 */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-auto p-12 space-y-10">
          {/* 제목 */}
          <div className="space-y-2">
            <h1 className="text-[48px] font-semibold tracking-[-2px] text-black font-[Sora]">{t('nl2sql.title')}</h1>
            <p className="text-[13px] text-[#5E5E5E] font-[IBM_Plex_Mono]">{t('nl2sql.subtitle')}</p>
          </div>

          {/* 쿼리 영역 */}
          <div className="space-y-4">
            <QueryToolbar
              schemaTreeOpen={schemaTreeOpen}
              onToggleSchemaTree={() => setSchemaTreeOpen((v) => !v)}
              datasourceId={datasourceId}
              onDatasourceChange={setDatasourceId}
              mode={mode}
              onModeChange={setMode}
              rowLimit={rowLimit}
              onRowLimitChange={setRowLimit}
              hasMessages={chat.messages.length > 0}
              onClear={chat.handleClear}
            />

            <QueryInputForm
              onSubmit={chat.submitQuestion}
              loading={chat.loading}
              datasourceId={datasourceId}
              hilActive={!!chat.hilRequest}
              generatedSql={chat.finalResult?.sql ?? null}
              setPromptRef={(setter) => { setPromptRef.current = setter; }}
            />
          </div>

          {/* Admin 전용: Direct SQL */}
          {isAdmin && <DirectSqlPanel datasourceId={datasourceId} />}

          {/* 빈 상태 + 예제 질문 */}
          {isEmpty && (
            <div className="flex flex-col items-center py-16">
              <EmptyState icon={Database} title={t('nl2sql.emptyTitle')} description={t('nl2sql.emptyDescription')} />
              <div className="flex flex-wrap gap-2 mt-6">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setPromptRef.current?.(q)}
                    className="rounded-full border border-[#E5E5E5] bg-white px-3 py-1.5 text-xs text-muted-foreground hover:text-black hover:border-[#999] transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 에러 배너 */}
          {chat.error && (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{chat.error}</div>
          )}

          {/* 채팅 메시지 목록 */}
          <ChatMessageList messages={chat.messages} />

          {/* HIL 입력 UI — 에이전트가 추가 정보 요청 시 표시 */}
          {chat.hilRequest && (
            <HumanInTheLoopInput
              request={chat.hilRequest}
              onSubmit={chat.handleHilSubmit}
              onCancel={chat.handleHilCancel}
              isSubmitting={chat.hilSubmitting}
            />
          )}

          {/* ReAct 진행 타임라인 + 요약 */}
          {mode === 'react' && chat.reactSteps.length > 0 && (
            <div className="space-y-3">
              <ReactProgressTimeline steps={chat.reactSteps} isRunning={chat.loading} />
              <ReactSummaryPanel steps={chat.reactSteps} isRunning={chat.loading} />
            </div>
          )}

          {/* 하단 탭: 결과 / 스키마 캔버스 */}
          <BottomTabPanel
            resultData={chat.finalResult}
            resultColumns={chat.resultColumns}
            resultRows={chat.resultRows}
            effectiveChartConfig={chat.effectiveChartConfig}
            canvasTables={canvasTables}
            onToggleContext={handleToggleContext}
            onRemoveCanvasTable={handleRemoveCanvasTable}
          />
        </div>
      </div>

      {/* 우측 사이드바: 쿼리 히스토리 */}
      {historyOpen && (
        <div className="w-80 shrink-0 border-l border-[#E5E5E5] flex flex-col">
          <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5]">
            <span className="text-[13px] font-semibold text-black font-[Sora]">{t('nl2sql.queryHistory')}</span>
            <span className="bg-[#F5F5F5] px-2.5 py-1 text-[11px] text-[#5E5E5E] font-[IBM_Plex_Mono] font-medium rounded">12</span>
          </div>
          <div className="flex-1 overflow-auto">
            <QueryHistoryPanel datasourceId={datasourceId} onSelect={(item) => setPromptRef.current?.(item.question)} />
          </div>
        </div>
      )}
    </div>
  );
}
