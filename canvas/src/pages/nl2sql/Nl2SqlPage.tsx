/**
 * NL2SQL 페이지 — 자연어 → SQL 변환 + 실행.
 *
 * 주요 기능:
 *  - ReAct 스트림 모드 (NDJSON)
 *  - Ask 단일 요청 모드
 *  - HIL (Human-in-the-Loop): 에이전트가 추가 정보를 요청할 때 사용자 입력 UI 표시
 *  - 결과에 대한 피드백 위젯 (thumbs up/down + SQL 수정)
 *  - 좌측 사이드바: DatabaseTree (스키마 트리 탐색)
 *  - 하단 탭: SchemaCanvas (ERD 시각화)
 *  - ReactSummaryPanel (ReAct 실행 요약)
 */
import { useState, useRef, useCallback } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  postReactStream,
  postAsk,
  type AskResponse,
  type ReactStreamStep,
} from '@/features/nl2sql/api/oracleNl2sqlApi';
import { AppError } from '@/lib/api/errors';
import { QueryHistoryPanel } from '@/features/nl2sql/components/QueryHistoryPanel';
import { HumanInTheLoopInput } from '@/features/nl2sql/components/HumanInTheLoopInput';
import { FeedbackWidget } from '@/features/nl2sql/components/FeedbackWidget';
import { DatabaseTree } from '@/features/nl2sql/components/DatabaseTree';
import { SchemaSearchBar } from '@/features/nl2sql/components/SchemaSearchBar';
import { TableDetailPanel } from '@/features/nl2sql/components/TableDetailPanel';
import { SchemaCanvas } from '@/features/nl2sql/components/SchemaCanvas';
import { ReactSummaryPanel } from '@/features/nl2sql/components/ReactSummaryPanel';
import { useSchemaTree } from '@/features/nl2sql/hooks/useSchemaTree';
import { useTableDetail } from '@/features/nl2sql/hooks/useTableDetail';
import { nl2sqlPromptSchema, type Nl2sqlPromptFormValues } from './nl2sqlFormSchema';
import type { ChartConfig, ExecutionMetadata, HilRequest, HilResponse, ColumnMeta } from '@/features/nl2sql/types/nl2sql';

import { DatasourceSelector } from './components/DatasourceSelector';
import { ResultPanel } from './components/ResultPanel';
import { ReactProgressTimeline } from './components/ReactProgressTimeline';
import { DirectSqlPanel } from './components/DirectSqlPanel';

import { useRole } from '@/shared/hooks/useRole';
import { EmptyState } from '@/shared/components/EmptyState';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Database, Trash2, ArrowRight, Download, MessageSquare, PanelLeftClose, PanelLeftOpen, LayoutGrid, Table2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';

type ChatMessage =
  | { role: 'user'; content: string }
  | {
      role: 'assistant';
      content: string;
      sql?: string;
      result?: AskResponse['data'];
      error?: string;
      streaming?: boolean;
      /** HIL 질문 메시지 — 경고 스타일로 표시 */
      isHilQuestion?: boolean;
    };

const ROW_LIMIT_OPTIONS = [100, 500, 1000, 2000, 5000, 10000];

export function NL2SQLPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case_id') || undefined;
  const isAdmin = useRole(['admin']);

  /** 예제 질문 목록 — i18n에서 가져옴 */
  const EXAMPLE_QUESTIONS = [
    t('nl2sql.exampleQuestions.q1'),
    t('nl2sql.exampleQuestions.q2'),
    t('nl2sql.exampleQuestions.q3'),
    t('nl2sql.exampleQuestions.q4'),
  ];

  const [datasourceId, setDatasourceId] = useState('');
  const [rowLimit, setRowLimit] = useState<number>(1000);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [reactSteps, setReactSteps] = useState<ReactStreamStep[]>([]);
  const [finalResult, setFinalResult] = useState<AskResponse['data'] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'react' | 'ask'>('react');
  const [historyOpen, setHistoryOpen] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  // === 스키마 트리 + 캔버스 상태 ===
  const [schemaTreeOpen, setSchemaTreeOpen] = useState(false);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const [bottomTab, setBottomTab] = useState<'results' | 'schema'>('results');
  // 캔버스 테이블 목록: 사용자가 트리에서 선택한 테이블 (ERD 표시 + NL2SQL 컨텍스트 제어)
  const [canvasTables, setCanvasTables] = useState<
    { tableName: string; schema: string; columns: ColumnMeta[]; includedInContext: boolean }[]
  >([]);

  // 스키마 트리 훅
  const schemaTree = useSchemaTree(datasourceId || null);

  // 선택된 테이블의 상세 정보
  const selectedTableName = schemaTree.selection?.type === 'table' ? schemaTree.selection.table : null;
  const selectedTableSchema = schemaTree.selection?.type === 'table' ? schemaTree.selection.schema : null;
  const tableDetail = useTableDetail(selectedTableName, datasourceId || null, selectedTableSchema ?? undefined);

  // 테이블 선택 시 캔버스에 자동 추가
  const handleSelectTableInTree = useCallback((schema: string, table: string) => {
    schemaTree.selectTable(schema, table);
    // 테이블 상세 패널용 컬럼 로드
    schemaTree.loadColumnsForTable(table);
    // 캔버스에 아직 없으면 추가
    setCanvasTables((prev) => {
      if (prev.some((t) => t.tableName === table)) return prev;
      const cols = schemaTree.getColumns(table) ?? [];
      return [...prev, { tableName: table, schema, columns: cols, includedInContext: true }];
    });
  }, [schemaTree]);

  // 캔버스 테이블 컨텍스트 토글
  const handleToggleContext = useCallback((tableName: string) => {
    setCanvasTables((prev) =>
      prev.map((t) => (t.tableName === tableName ? { ...t, includedInContext: !t.includedInContext } : t))
    );
  }, []);

  // 캔버스 테이블 제거
  const handleRemoveCanvasTable = useCallback((tableName: string) => {
    setCanvasTables((prev) => prev.filter((t) => t.tableName !== tableName));
  }, []);

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
  const handleSearchResultSelect = useCallback((result: { type: string; schema: string; tableName: string }) => {
    schemaTree.toggleSchema(result.schema); // 스키마 펼치기
    if (result.type === 'table') {
      handleSelectTableInTree(result.schema, result.tableName);
    }
  }, [schemaTree, handleSelectTableInTree]);

  // === HIL 상태 ===
  const [hilRequest, setHilRequest] = useState<HilRequest | null>(null);
  const [hilSubmitting, setHilSubmitting] = useState(false);
  // 현재 질문 텍스트 (HIL 재개 시 원래 질문 참조용)
  const currentQuestionRef = useRef<string>('');

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<Nl2sqlPromptFormValues>({
    resolver: zodResolver(nl2sqlPromptSchema),
    defaultValues: { prompt: '' },
  });
  const promptValue = watch('prompt');

  const handleDatasourceChange = useCallback((id: string) => {
    setDatasourceId(id);
  }, []);

  const handleClear = () => {
    setMessages([]);
    setFinalResult(null);
    setReactSteps([]);
    setError(null);
    setHilRequest(null);
    setHilSubmitting(false);
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
  };

  /** NDJSON 스트림 콜백 — ReAct 단계별 처리 + HIL 이벤트 감지 */
  const buildStreamCallbacks = (question: string) => ({
    onMessage: (step: ReactStreamStep) => {
      setReactSteps((prev) => [...prev, step]);

      // === HIL: needs_user_input 이벤트 처리 ===
      if (step.step === 'needs_user_input' && step.data) {
        const d = step.data as Record<string, unknown>;
        const hilReq: HilRequest = {
          type: (d.type as HilRequest['type']) || 'text',
          question: String(d.question_to_user ?? d.question ?? t('nl2sql.hilNeedInfo')),
          options: d.options as HilRequest['options'],
          context: d.context ? String(d.context) : d.partial_sql ? String(d.partial_sql) : undefined,
          session_state: String(d.session_state ?? ''),
        };
        setHilRequest(hilReq);
        // 에이전트 질문을 채팅 히스토리에 추가
        setMessages((prev) => {
          const rest = prev.slice(0, -1); // 스트리밍 메시지 제거
          return [
            ...rest,
            {
              role: 'assistant',
              content: hilReq.question,
              isHilQuestion: true,
            },
          ];
        });
        setLoading(false); // 스트림이 일시 정지됨 — 로딩 해제
        return;
      }

      // === 결과 이벤트 ===
      if (step.step === 'result' && step.data) {
        const d = step.data as Record<string, unknown>;
        const table = d.result as
          | { columns: { name: string; type: string }[]; rows: unknown[][]; row_count: number }
          | undefined;
        if (table || d.sql) {
          const resultData = {
            question,
            sql: String(d.sql ?? ''),
            result: table ?? { columns: [], rows: [], row_count: 0 },
            summary: d.summary != null ? String(d.summary) : null,
            visualization:
              d.visualization != null
                ? (d.visualization as { chart_type: string; config?: Record<string, string> })
                : null,
            metadata: d.metadata as ExecutionMetadata | undefined,
          };
          setFinalResult(resultData);
          setMessages((prev) => {
            const rest = prev.slice(0, -1);
            return [
              ...rest,
              {
                role: 'assistant',
                content: resultData.summary ?? t('nl2sql.queryComplete'),
                sql: resultData.sql,
                result: resultData,
              },
            ];
          });
          queryClient.invalidateQueries({ queryKey: ['nl2sql', 'history'] });
        }
      }

      // === 에러 이벤트 ===
      if (step.step === 'error' && step.data) {
        const msg =
          (step.data as { message?: string }).message ?? t('nl2sql.reactError');
        setError(msg);
        setMessages((prev) => {
          const rest = prev.slice(0, -1);
          return [...rest, { role: 'assistant', content: msg, error: msg }];
        });
      }
    },
    onComplete: () => setLoading(false),
    onError: (err: Error) => {
      const msg = err.message || t('nl2sql.streamFailed');
      setError(msg);
      setMessages((prev) => {
        const rest = prev.slice(0, -1);
        return [...rest, { role: 'assistant', content: msg, error: msg }];
      });
      setLoading(false);
    },
  });

  /** 사용자 HIL 응답 제출 — 세션을 이어서 ReAct 스트림 재개 */
  const handleHilSubmit = async (response: HilResponse) => {
    setHilSubmitting(true);
    setHilRequest(null);
    setLoading(true);

    // 사용자 답변을 채팅 히스토리에 추가
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: response.user_response },
      { role: 'assistant', content: '', streaming: true },
    ]);

    try {
      abortRef.current = await postReactStream(
        currentQuestionRef.current,
        datasourceId,
        buildStreamCallbacks(currentQuestionRef.current),
        {
          case_id: caseId,
          row_limit: rowLimit,
          session_state: response.session_state,
          user_response: response.user_response,
        },
      );
    } catch (err) {
      const errMsg =
        err instanceof AppError
          ? err.userMessage
          : (err as Error).message || t('nl2sql.hilResumeFailed');
      setError(errMsg);
      setMessages((prev) => {
        const rest = prev.slice(0, -1);
        return [...rest, { role: 'assistant', content: errMsg, error: errMsg }];
      });
      setLoading(false);
    } finally {
      setHilSubmitting(false);
    }
  };

  /** HIL 취소 — 현재 세션을 중단 */
  const handleHilCancel = () => {
    setHilRequest(null);
    setLoading(false);
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  };

  const onSubmit = async (data: Nl2sqlPromptFormValues) => {
    const question = data.prompt.trim();
    if (!question || loading || !datasourceId) return;

    // 질문 기록 (HIL 재개 시 참조)
    currentQuestionRef.current = question;

    setLoading(true);
    setError(null);
    setFinalResult(null);
    setReactSteps([]);
    setHilRequest(null);
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    reset({ prompt: '' });

    if (mode === 'ask') {
      try {
        const res = await postAsk(question, datasourceId, { case_id: caseId, row_limit: rowLimit });
        if (res.success && res.data) {
          const d = res.data;
          setFinalResult(d);
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: d.summary ?? t('nl2sql.queryComplete'),
              sql: d.sql,
              result: d,
            },
          ]);
          queryClient.invalidateQueries({ queryKey: ['nl2sql', 'history'] });
        } else {
          const errMsg = res.error?.message ?? t('nl2sql.requestFailed');
          setError(errMsg);
          setMessages((prev) => [...prev, { role: 'assistant', content: errMsg, error: errMsg }]);
        }
      } catch (err) {
        const errMsg =
          err instanceof AppError
            ? err.userMessage
            : (err as Error).message || t('nl2sql.oracleApiFailed');
        setError(errMsg);
        setMessages((prev) => [...prev, { role: 'assistant', content: errMsg, error: errMsg }]);
      } finally {
        setLoading(false);
      }
      return;
    }

    // ReAct stream mode
    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }]);

    try {
      abortRef.current = await postReactStream(
        question,
        datasourceId,
        buildStreamCallbacks(question),
        { case_id: caseId, row_limit: rowLimit },
      );
    } catch (err) {
      const errMsg =
        err instanceof AppError
          ? err.userMessage
          : (err as Error).message || t('nl2sql.startFailed');
      setError(errMsg);
      setMessages((prev) => {
        const rest = prev.slice(0, -1);
        return [...rest, { role: 'assistant', content: errMsg, error: errMsg }];
      });
      setLoading(false);
    }
  };

  const handleSelectHistory = (item: { question: string }) => {
    setValue('prompt', item.question);
  };

  const handleExampleClick = (q: string) => {
    setValue('prompt', q);
  };

  // Derived state for ResultPanel
  const resultData = finalResult;
  const resultColumns = resultData?.result?.columns ?? [];
  const resultRows = resultData?.result?.rows ?? [];
  const chartConfig: ChartConfig | null =
    resultData?.visualization?.chart_type && resultData.visualization.config
      ? {
          chart_type: resultData.visualization.chart_type as ChartConfig['chart_type'],
          config: resultData.visualization.config,
        }
      : null;

  // Auto-detect KPI card: single row, single numeric column
  const effectiveChartConfig: ChartConfig | null = (() => {
    if (chartConfig) return chartConfig;
    if (
      resultData?.result &&
      resultData.result.columns.length === 1 &&
      resultData.result.rows.length === 1 &&
      typeof resultData.result.rows[0]?.[0] === 'number'
    ) {
      return {
        chart_type: 'kpi_card' as ChartConfig['chart_type'],
        config: { value_column: resultData.result.columns[0].name },
      };
    }
    return null;
  })();

  const isEmpty = messages.length === 0 && !loading;

  return (
    <div className="flex h-full">
      {/* === 좌측 사이드바: DatabaseTree (토글 가능) === */}
      {schemaTreeOpen && (
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
      )}

      {/* === 선택된 테이블 상세 패널 === */}
      {schemaTreeOpen && selectedTableName && tableDetail.detail && (
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

      {/* Content Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Content Body */}
        <div className="flex-1 overflow-auto p-12 space-y-10">
          {/* Title Section */}
          <div className="space-y-2">
            <h1 className="text-[48px] font-semibold tracking-[-2px] text-black font-[Sora]">{t('nl2sql.title')}</h1>
            <p className="text-[13px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
              {t('nl2sql.subtitle')}
            </p>
          </div>

          {/* Query Section */}
          <div className="space-y-4">
            {/* Connection badges + controls */}
            <div className="flex items-center gap-3">
              {/* 스키마 트리 토글 버튼 */}
              <button
                type="button"
                onClick={() => setSchemaTreeOpen((v) => !v)}
                className={cn(
                  'p-2 rounded transition-colors',
                  schemaTreeOpen
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-foreground/40 hover:text-foreground/60 hover:bg-[#F5F5F5]'
                )}
                title={schemaTreeOpen ? '스키마 트리 닫기' : '스키마 트리 열기'}
                aria-label={schemaTreeOpen ? '스키마 트리 닫기' : '스키마 트리 열기'}
              >
                {schemaTreeOpen ? (
                  <PanelLeftClose className="h-4 w-4" />
                ) : (
                  <PanelLeftOpen className="h-4 w-4" />
                )}
              </button>
              <DatasourceSelector value={datasourceId} onChange={handleDatasourceChange} />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setMode('react')}
                  className={cn(
                    'px-3 py-1 text-[11px] font-medium font-[IBM_Plex_Mono] rounded transition-colors',
                    mode === 'react'
                      ? 'bg-[#F5F5F5] text-black'
                      : 'text-foreground/60 hover:text-muted-foreground',
                  )}
                >
                  ReAct
                </button>
                <button
                  type="button"
                  onClick={() => setMode('ask')}
                  className={cn(
                    'px-3 py-1 text-[11px] font-medium font-[IBM_Plex_Mono] rounded transition-colors',
                    mode === 'ask'
                      ? 'bg-[#F5F5F5] text-black'
                      : 'text-foreground/60 hover:text-muted-foreground',
                  )}
                >
                  Ask
                </button>
              </div>
              <Select value={String(rowLimit)} onValueChange={(v) => setRowLimit(Number(v))}>
                <SelectTrigger className="h-7 w-20 border-[#E5E5E5] bg-white text-xs text-[#5E5E5E]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROW_LIMIT_OPTIONS.map((n) => (
                    <SelectItem key={n} value={String(n)}>
                      {n.toLocaleString()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={handleClear}
                  className="flex items-center gap-1 text-xs text-foreground/60 hover:text-destructive transition-colors"
                >
                  <Trash2 className="h-3 w-3" />
                  {t('nl2sql.reset')}
                </button>
              )}
            </div>

            {/* Query input row — HIL 활성화 시 비활성화 */}
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div className="flex items-end gap-3">
                <div
                  className={cn(
                    'flex-1 flex items-center gap-3 px-5 py-3.5 border border-[#E5E5E5] rounded',
                    hilRequest && 'opacity-50 pointer-events-none',
                  )}
                >
                  <MessageSquare className="h-4 w-4 text-foreground/60 shrink-0" />
                  <input
                    type="text"
                    placeholder={t('nl2sql.placeholder')}
                    className="flex-1 bg-transparent text-[13px] text-black placeholder:text-foreground/60 font-[IBM_Plex_Mono] outline-none"
                    disabled={!!hilRequest}
                    {...register('prompt')}
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading || !promptValue?.trim() || !datasourceId || !!hilRequest}
                  className="flex items-center gap-2 px-4 py-2.5 bg-destructive text-white text-[12px] font-medium font-[Sora] rounded disabled:opacity-50 hover:bg-red-700 transition-colors shrink-0"
                >
                  <ArrowRight className="h-3.5 w-3.5" />
                  {t('nl2sql.run')}
                </button>
              </div>
              {errors.prompt && <p className="text-xs text-destructive">{errors.prompt.message}</p>}
            </form>

            {/* SQL Preview */}
            {resultData?.sql && (
              <div className="bg-[#F5F5F5] rounded py-4 px-5 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-foreground/60 font-[IBM_Plex_Mono] uppercase tracking-[1px]">{t('nl2sql.generatedSql')}</span>
                </div>
                <pre className="text-[12px] text-black font-[IBM_Plex_Mono] whitespace-pre-wrap break-words">
                  {resultData.sql}
                </pre>
              </div>
            )}
          </div>

          {/* Admin: Direct SQL */}
          {isAdmin && <DirectSqlPanel datasourceId={datasourceId} />}

          {/* Empty state */}
          {isEmpty && (
            <div className="flex flex-col items-center py-16">
              <EmptyState
                icon={Database}
                title={t('nl2sql.emptyTitle')}
                description={t('nl2sql.emptyDescription')}
              />
              <div className="flex flex-wrap gap-2 mt-6">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleExampleClick(q)}
                    className="rounded-full border border-[#E5E5E5] bg-white px-3 py-1.5 text-xs text-muted-foreground hover:text-black hover:border-[#999] transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Chat messages */}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                'rounded p-4',
                msg.role === 'user'
                  ? 'bg-[#F5F5F5] ml-12'
                  : msg.role === 'assistant' && 'isHilQuestion' in msg && msg.isHilQuestion
                    ? 'border border-amber-300 bg-amber-50/50 mr-12'
                    : 'border border-[#E5E5E5] mr-12',
              )}
            >
              <span className="text-[11px] font-medium text-foreground/60 font-[IBM_Plex_Mono] uppercase">
                {msg.role === 'user'
                  ? t('nl2sql.chatUser')
                  : msg.role === 'assistant' && 'isHilQuestion' in msg && msg.isHilQuestion
                    ? t('nl2sql.chatHilQuestion')
                    : t('nl2sql.chatAssistant')}
              </span>
              <p className="text-sm text-black mt-1">
                {msg.content ||
                  (msg.role === 'assistant' && 'streaming' in msg && msg.streaming
                    ? t('common.processing')
                    : '')}
              </p>
              {msg.role === 'assistant' && msg.result?.result && msg.result.result.columns.length > 0 && (
                <div className="mt-3 overflow-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr>
                        {msg.result.result.columns.map((col) => (
                          <th
                            key={col.name}
                            className="bg-[#F5F5F5] px-3 py-2 text-left text-[11px] font-medium text-muted-foreground font-[IBM_Plex_Mono] uppercase border-b border-[#E5E5E5]"
                          >
                            {col.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(msg.result.result.rows ?? []).slice(0, 5).map((row, ri) => (
                        <tr key={ri} className="border-b border-[#E5E5E5] last:border-0">
                          {row.map((cell, ci) => (
                            <td
                              key={ci}
                              className="px-3 py-2 text-[13px] text-[#333] font-[IBM_Plex_Mono]"
                            >
                              {cell == null ? '--' : String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {(msg.result.result.rows?.length ?? 0) > 5 && (
                    <p className="text-xs text-foreground/60 mt-2">
                      {t('nl2sql.topRowsOnly', { count: msg.result.result.row_count })}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* === HIL 입력 UI === */}
          {hilRequest && (
            <HumanInTheLoopInput
              request={hilRequest}
              onSubmit={handleHilSubmit}
              onCancel={handleHilCancel}
              isSubmitting={hilSubmitting}
            />
          )}

          {/* ReAct progress + summary 패널 */}
          {mode === 'react' && reactSteps.length > 0 && (
            <div className="space-y-3">
              <ReactProgressTimeline steps={reactSteps} isRunning={loading} />
              <ReactSummaryPanel steps={reactSteps} isRunning={loading} />
            </div>
          )}

          {/* 결과 탭 전환: Results | Schema Canvas */}
          {(resultData || canvasTables.length > 0) && (
            <div className="flex items-center gap-1 border-b border-[#E5E5E5]">
              <button
                type="button"
                onClick={() => setBottomTab('results')}
                className={cn(
                  'flex items-center gap-1.5 px-4 py-2 text-[12px] font-medium font-[Sora] border-b-2 transition-colors',
                  bottomTab === 'results'
                    ? 'border-black text-black'
                    : 'border-transparent text-foreground/40 hover:text-foreground/60'
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
                    : 'border-transparent text-foreground/40 hover:text-foreground/60'
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
          )}

          {/* Results 탭 */}
          {bottomTab === 'results' && resultData && resultColumns.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <h2 className="text-[14px] font-semibold text-black font-[Sora]">{t('nl2sql.queryResult')}</h2>
                  <span className="bg-[#F5F5F5] px-2.5 py-0.5 text-[11px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                    {resultData.result?.row_count ?? 0} rows
                  </span>
                </div>
                <button type="button" className="flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium text-black border border-[#E5E5E5] rounded hover:bg-[#F5F5F5] transition-colors font-[Sora]">
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

          {/* Schema Canvas 탭 */}
          {bottomTab === 'schema' && (
            <div className="border border-[#E5E5E5] rounded overflow-hidden" style={{ minHeight: 400 }}>
              <SchemaCanvas
                tables={canvasTables}
                onToggleContext={handleToggleContext}
                onRemoveTable={handleRemoveCanvasTable}
              />
            </div>
          )}
        </div>
      </div>

      {/* Query History sidebar */}
      {historyOpen && (
        <div className="w-80 shrink-0 border-l border-[#E5E5E5] flex flex-col">
          <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5]">
            <span className="text-[13px] font-semibold text-black font-[Sora]">{t('nl2sql.queryHistory')}</span>
            <span className="bg-[#F5F5F5] px-2.5 py-1 text-[11px] text-[#5E5E5E] font-[IBM_Plex_Mono] font-medium rounded">
              12
            </span>
          </div>
          <div className="flex-1 overflow-auto">
            <QueryHistoryPanel datasourceId={datasourceId} onSelect={handleSelectHistory} />
          </div>
        </div>
      )}
    </div>
  );
}
