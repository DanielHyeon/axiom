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
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Database, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const EXAMPLE_QUESTIONS = [
  '2024년 매출 성장률이 가장 높은 사업부는?',
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
    <div className="flex h-full gap-4 p-4">
      {/* Main panel */}
      <div className="flex-1 flex flex-col min-w-0 rounded border border-neutral-800 bg-neutral-950">
        {/* Header */}
        <div className="p-4 border-b border-neutral-800">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-white">NL2SQL</h2>
              <p className="text-sm text-neutral-500">
                자연어로 질문하면 Oracle API가 SQL로 변환·실행합니다.
              </p>
            </div>
            <DatasourceSelector value={datasourceId} onChange={handleDatasourceChange} />
          </div>
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => setMode('react')}
              className={cn(
                'rounded px-2 py-1 text-sm',
                mode === 'react' ? 'bg-blue-600 text-white' : 'bg-neutral-800 text-neutral-400'
              )}
            >
              ReAct 스트림
            </button>
            <button
              type="button"
              onClick={() => setMode('ask')}
              className={cn(
                'rounded px-2 py-1 text-sm',
                mode === 'ask' ? 'bg-blue-600 text-white' : 'bg-neutral-800 text-neutral-400'
              )}
            >
              단일 요청
            </button>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-neutral-500">Rows:</span>
              <Select value={String(rowLimit)} onValueChange={(v) => setRowLimit(Number(v))}>
                <SelectTrigger className="h-7 w-24 border-neutral-700 bg-neutral-900 text-xs">
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
            </div>
            <button
              type="button"
              onClick={() => setHistoryOpen((o) => !o)}
              className="rounded px-2 py-1 text-sm bg-neutral-800 text-neutral-400"
            >
              {historyOpen ? '이력 숨기기' : '이력 보기'}
            </button>
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="gap-1 text-xs text-neutral-500 hover:text-red-400"
                onClick={handleClear}
              >
                <Trash2 className="h-3 w-3" />
                대화 초기화
              </Button>
            )}
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Direct SQL panel — admin only */}
          {isAdmin && <DirectSqlPanel datasourceId={datasourceId} />}

          {/* Empty state */}
          {isEmpty && (
            <div className="flex flex-col items-center py-12">
              <EmptyState
                icon={Database}
                title="AI SQL 어시스턴트"
                description="질문을 입력하면 AI가 SQL을 생성하고 실행합니다."
              />
              <div className="flex flex-wrap gap-2 mt-4">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleExampleClick(q)}
                    className="rounded-full border border-neutral-700 bg-neutral-900 px-3 py-1.5 text-xs text-neutral-400 hover:text-white hover:border-neutral-500 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="rounded border border-red-900/50 bg-red-900/20 p-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {/* Chat messages */}
          {messages.map((msg, i) => (
            <div
              key={i}
              className={cn(
                'rounded border p-3',
                msg.role === 'user'
                  ? 'border-blue-900/50 bg-blue-900/20 ml-8'
                  : 'border-neutral-800 bg-neutral-900/50 mr-8'
              )}
            >
              <span className="text-xs font-medium text-neutral-500">
                {msg.role === 'user' ? '질문' : '응답'}
              </span>
              <p className="text-sm text-neutral-300 mt-1">
                {msg.content ||
                  (msg.role === 'assistant' && 'streaming' in msg && msg.streaming
                    ? '처리 중...'
                    : '')}
              </p>
              {msg.role === 'assistant' && msg.result?.result && msg.result.result.columns.length > 0 && (
                <div className="mt-2 overflow-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr>
                        {msg.result.result.columns.map((col) => (
                          <th
                            key={col.name}
                            className="border border-neutral-700 bg-neutral-800 px-2 py-1 text-left text-neutral-300"
                          >
                            {col.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(msg.result.result.rows ?? []).slice(0, 5).map((row, ri) => (
                        <tr key={ri}>
                          {row.map((cell, ci) => (
                            <td
                              key={ci}
                              className="border border-neutral-700 px-2 py-1 text-neutral-400"
                            >
                              {cell == null ? '--' : String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {(msg.result.result.rows?.length ?? 0) > 5 && (
                    <p className="text-xs text-neutral-500 mt-1">
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

          {/* Result panel (chart/table/sql tabs) */}
          {resultData && resultColumns.length > 0 && (
            <ResultPanel
              sql={resultData.sql}
              columns={resultColumns}
              rows={resultRows}
              rowCount={resultData.result?.row_count ?? 0}
              chartConfig={effectiveChartConfig}
              summary={resultData.summary ?? null}
              metadata={(resultData.metadata as ExecutionMetadata) ?? null}
            />
          )}
        </div>

        {/* Input form */}
        <div className="p-4 border-t border-neutral-800">
          <form onSubmit={handleSubmit(onSubmit)} className="flex gap-2">
            <div className="flex-1 flex flex-col gap-1">
              <input
                type="text"
                placeholder="예: 2024년 매출 성장률이 가장 높은 사업부는?"
                className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-white placeholder:text-neutral-500"
                {...register('prompt')}
              />
              {errors.prompt && <p className="text-xs text-red-400">{errors.prompt.message}</p>}
            </div>
            <button
              type="submit"
              disabled={loading || !promptValue?.trim() || !datasourceId}
              className="rounded bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50 hover:bg-blue-700"
            >
              {loading ? '처리 중...' : '질문'}
            </button>
          </form>
        </div>
      </div>

      {/* History sidebar */}
      {historyOpen && (
        <div className="w-72 flex-shrink-0">
          <QueryHistoryPanel datasourceId={datasourceId} onSelect={handleSelectHistory} />
        </div>
      )}
    </div>
  );
}
