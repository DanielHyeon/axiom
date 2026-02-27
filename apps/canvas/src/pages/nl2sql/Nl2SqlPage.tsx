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
import { nl2sqlPromptSchema, type Nl2sqlPromptFormValues } from './nl2sqlFormSchema';
import type { ChartConfig, ExecutionMetadata } from '@/features/nl2sql/types/nl2sql';

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
import { Database, Trash2, ArrowRight, Download, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';

const EXAMPLE_QUESTIONS = [
  '2024-06-20 서울전자 매출은?',
  '2024년 회사별 매출 성장률이 가장 높은 곳은?',
  '최근 3개월 처리 건수 추이',
  '지역별 평균 처리 시간 비교',
];

type ChatMessage =
  | { role: 'user'; content: string }
  | {
      role: 'assistant';
      content: string;
      sql?: string;
      result?: AskResponse['data'];
      error?: string;
      streaming?: boolean;
    };

const ROW_LIMIT_OPTIONS = [100, 500, 1000, 2000, 5000, 10000];

export function NL2SQLPage() {
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const caseId = searchParams.get('case_id') || undefined;
  const isAdmin = useRole(['admin']);

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
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
  };

  const onSubmit = async (data: Nl2sqlPromptFormValues) => {
    const question = data.prompt.trim();
    if (!question || loading || !datasourceId) return;

    setLoading(true);
    setError(null);
    setFinalResult(null);
    setReactSteps([]);
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
              content: d.summary ?? '쿼리 실행이 완료되었습니다.',
              sql: d.sql,
              result: d,
            },
          ]);
          queryClient.invalidateQueries({ queryKey: ['nl2sql', 'history'] });
        } else {
          const errMsg = res.error?.message ?? '요청 처리에 실패했습니다.';
          setError(errMsg);
          setMessages((prev) => [...prev, { role: 'assistant', content: errMsg, error: errMsg }]);
        }
      } catch (err) {
        const errMsg =
          err instanceof AppError
            ? err.userMessage
            : (err as Error).message || 'Oracle API 호출에 실패했습니다.';
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
        {
          onMessage: (step: ReactStreamStep) => {
            setReactSteps((prev) => [...prev, step]);

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
                      content: resultData.summary ?? '쿼리 실행이 완료되었습니다.',
                      sql: resultData.sql,
                      result: resultData,
                    },
                  ];
                });
                queryClient.invalidateQueries({ queryKey: ['nl2sql', 'history'] });
              }
            }
            if (step.step === 'error' && step.data) {
              const msg =
                (step.data as { message?: string }).message ?? 'ReAct 단계에서 오류가 발생했습니다.';
              setError(msg);
              setMessages((prev) => {
                const rest = prev.slice(0, -1);
                return [...rest, { role: 'assistant', content: msg, error: msg }];
              });
            }
          },
          onComplete: () => setLoading(false),
          onError: (err) => {
            const msg = err.message || '스트림 연결에 실패했습니다.';
            setError(msg);
            setMessages((prev) => {
              const rest = prev.slice(0, -1);
              return [...rest, { role: 'assistant', content: msg, error: msg }];
            });
            setLoading(false);
          },
        },
        { case_id: caseId, row_limit: rowLimit }
      );
    } catch (err) {
      const errMsg =
        err instanceof AppError
          ? err.userMessage
          : (err as Error).message || '요청을 시작하지 못했습니다.';
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
      {/* Content Column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Content Body */}
        <div className="flex-1 overflow-auto p-12 space-y-10">
          {/* Title Section */}
          <div className="space-y-2">
            <h1 className="text-[48px] font-semibold tracking-[-2px] text-black font-[Sora]">NL2SQL</h1>
            <p className="text-[13px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
              자연어를 SQL로 변환하여 데이터베이스를 쉽게 조회하세요
            </p>
          </div>

          {/* Query Section */}
          <div className="space-y-4">
            {/* Connection badges + controls */}
            <div className="flex items-center gap-3">
              <DatasourceSelector value={datasourceId} onChange={handleDatasourceChange} />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setMode('react')}
                  className={cn(
                    'px-3 py-1 text-[11px] font-medium font-[IBM_Plex_Mono] rounded transition-colors',
                    mode === 'react'
                      ? 'bg-[#F5F5F5] text-black'
                      : 'text-[#999] hover:text-[#666]'
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
                      : 'text-[#999] hover:text-[#666]'
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
                  className="flex items-center gap-1 text-xs text-[#999] hover:text-red-500 transition-colors"
                >
                  <Trash2 className="h-3 w-3" />
                  초기화
                </button>
              )}
            </div>

            {/* Query input row */}
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div className="flex items-end gap-3">
                <div className="flex-1 flex items-center gap-3 px-5 py-3.5 border border-[#E5E5E5] rounded">
                  <MessageSquare className="h-4 w-4 text-[#999] shrink-0" />
                  <input
                    type="text"
                    placeholder="예: 최근 3개월간 매출이 가장 높은 상품 10개를 조회하세요"
                    className="flex-1 bg-transparent text-[13px] text-black placeholder:text-[#999] font-[IBM_Plex_Mono] outline-none"
                    {...register('prompt')}
                  />
                </div>
                <button
                  type="submit"
                  disabled={loading || !promptValue?.trim() || !datasourceId}
                  className="flex items-center gap-2 px-4 py-2.5 bg-red-600 text-white text-[12px] font-medium font-[Sora] rounded disabled:opacity-50 hover:bg-red-700 transition-colors shrink-0"
                >
                  <ArrowRight className="h-3.5 w-3.5" />
                  실행
                </button>
              </div>
              {errors.prompt && <p className="text-xs text-red-500">{errors.prompt.message}</p>}
            </form>

            {/* SQL Preview */}
            {resultData?.sql && (
              <div className="bg-[#F5F5F5] rounded py-4 px-5 space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-[#999] font-[IBM_Plex_Mono] uppercase tracking-[1px]">Generated SQL</span>
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
                title="AI SQL 어시스턴트"
                description="질문을 입력하면 AI가 SQL을 생성하고 실행합니다."
              />
              <div className="flex flex-wrap gap-2 mt-6">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleExampleClick(q)}
                    className="rounded-full border border-[#E5E5E5] bg-white px-3 py-1.5 text-xs text-[#666] hover:text-black hover:border-[#999] transition-colors"
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
                  : 'border border-[#E5E5E5] mr-12'
              )}
            >
              <span className="text-[11px] font-medium text-[#999] font-[IBM_Plex_Mono] uppercase">
                {msg.role === 'user' ? '질문' : '응답'}
              </span>
              <p className="text-sm text-black mt-1">
                {msg.content ||
                  (msg.role === 'assistant' && 'streaming' in msg && msg.streaming
                    ? '처리 중...'
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
                            className="bg-[#F5F5F5] px-3 py-2 text-left text-[11px] font-medium text-[#666] font-[IBM_Plex_Mono] uppercase border-b border-[#E5E5E5]"
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
                    <p className="text-xs text-[#999] mt-2">
                      상위 5행만 표시 (총 {msg.result.result.row_count}행)
                    </p>
                  )}
                </div>
              )}
            </div>
          ))}

          {/* ReAct progress timeline */}
          {mode === 'react' && reactSteps.length > 0 && (
            <ReactProgressTimeline steps={reactSteps} isRunning={loading} />
          )}

          {/* Results section */}
          {resultData && resultColumns.length > 0 && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <h2 className="text-[14px] font-semibold text-black font-[Sora]">조회 결과</h2>
                  <span className="bg-[#F5F5F5] px-2.5 py-0.5 text-[11px] text-[#5E5E5E] font-[IBM_Plex_Mono]">
                    {resultData.result?.row_count ?? 0} rows
                  </span>
                </div>
                <button type="button" className="flex items-center gap-2 px-4 py-2.5 text-[12px] font-medium text-black border border-[#E5E5E5] rounded hover:bg-[#F5F5F5] transition-colors font-[Sora]">
                  <Download className="h-3.5 w-3.5" />
                  Export
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
            </div>
          )}
        </div>
      </div>

      {/* Query History sidebar */}
      {historyOpen && (
        <div className="w-80 shrink-0 border-l border-[#E5E5E5] flex flex-col">
          <div className="flex items-center justify-between h-[52px] px-6 border-b border-[#E5E5E5]">
            <span className="text-[13px] font-semibold text-black font-[Sora]">Query History</span>
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
