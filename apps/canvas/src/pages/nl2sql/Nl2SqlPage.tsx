import { useState, useRef, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { postReactStream, postAsk, type AskResponse, type ReactStreamStep } from '@/features/nl2sql/api/oracleNl2sqlApi';
import { QueryHistoryPanel } from '@/features/nl2sql/components/QueryHistoryPanel';
import { ChartRecommender } from './components/ChartRecommender';
import type { ChartConfig } from '@/features/nl2sql/types/nl2sql';
import { nl2sqlPromptSchema, type Nl2sqlPromptFormValues } from './nl2sqlFormSchema';

const DEFAULT_DATASOURCE = 'ds_business_main';

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

export function NL2SQLPage() {
  const queryClient = useQueryClient();
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streamLog, setStreamLog] = useState<string[]>([]);
  const [finalResult, setFinalResult] = useState<AskResponse['data'] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'react' | 'ask'>('react');
  const [historyOpen, setHistoryOpen] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  const { register, handleSubmit, reset, setValue, watch, formState: { errors } } = useForm<Nl2sqlPromptFormValues>({
    resolver: zodResolver(nl2sqlPromptSchema),
    defaultValues: { prompt: '' },
  });
  const promptValue = watch('prompt');

  const onSubmit = async (data: Nl2sqlPromptFormValues) => {
    const question = data.prompt.trim();
    if (!question || loading) return;

    setLoading(true);
    setError(null);
    setFinalResult(null);
    setStreamLog([]);
    setMessages((prev) => [...prev, { role: 'user', content: question }]);
    reset({ prompt: '' });

    if (mode === 'ask') {
      try {
        const res = await postAsk(question, DEFAULT_DATASOURCE);
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
        const errMsg = (err as Error).message || 'Oracle API 호출에 실패했습니다.';
        setError(errMsg);
        setMessages((prev) => [...prev, { role: 'assistant', content: errMsg, error: errMsg }]);
      } finally {
        setLoading(false);
      }
      return;
    }

    setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }]);

    try {
      abortRef.current = await postReactStream(
        question,
        DEFAULT_DATASOURCE,
        {
          onMessage: (step: ReactStreamStep) => {
            const line = step.step + (step.data?.reasoning ? `: ${String(step.data.reasoning).slice(0, 80)}...` : '');
            setStreamLog((prev) => [...prev, line]);
            if (step.step === 'result' && step.data) {
              const d = step.data as Record<string, unknown>;
              const table = d.result as { columns: { name: string; type: string }[]; rows: unknown[][]; row_count: number } | undefined;
              if (table || d.sql) {
                const resultData = {
                  question,
                  sql: String(d.sql ?? ''),
                  result: table ?? { columns: [], rows: [], row_count: 0 },
                  summary: d.summary != null ? String(d.summary) : null,
                  visualization: d.visualization != null ? (d.visualization as { chart_type: string; config?: Record<string, string> }) : null,
                  metadata: d.metadata as { execution_time_ms?: number; tables_used?: string[]; cache_hit?: boolean } | undefined,
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
              const msg = (step.data as { message?: string }).message ?? 'ReAct 단계에서 오류가 발생했습니다.';
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
        }
      );
    } catch (err) {
      const errMsg = (err as Error).message || '요청을 시작하지 못했습니다.';
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

  const data = finalResult;
  const columns = data?.result?.columns ?? [];
  const rows = data?.result?.rows ?? [];

  const chartData = useMemo(() => {
    if (rows.length === 0 || columns.length === 0) return [];
    return rows.map((row) => {
      const obj: Record<string, unknown> = {};
      columns.forEach((col, i) => {
        obj[col.name] = row[i];
      });
      return obj;
    });
  }, [rows, columns]);

  const chartConfig: ChartConfig | null =
    data?.visualization?.chart_type && data.visualization.config
      ? {
          chart_type: data.visualization.chart_type as ChartConfig['chart_type'],
          config: {
            x_column: data.visualization.config.x_column ?? columns[0]?.name ?? 'x',
            y_column: data.visualization.config.y_column ?? columns[1]?.name ?? 'y',
            x_label: data.visualization.config.x_label ?? '',
            y_label: data.visualization.config.y_label ?? '',
          },
        }
      : null;

  return (
    <div className="flex h-full gap-4 p-4">
      <div className="flex-1 flex flex-col min-w-0 rounded border border-neutral-800 bg-neutral-950">
        <div className="p-4 border-b border-neutral-800">
          <h2 className="text-xl font-semibold text-white">NL2SQL</h2>
          <p className="text-sm text-neutral-500">
            자연어로 질문하면 Oracle API가 SQL로 변환·실행합니다.
          </p>
          <div className="mt-2 flex gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => setMode('react')}
              className={`rounded px-2 py-1 text-sm ${mode === 'react' ? 'bg-blue-600 text-white' : 'bg-neutral-800 text-neutral-400'}`}
            >
              ReAct 스트림
            </button>
            <button
              type="button"
              onClick={() => setMode('ask')}
              className={`rounded px-2 py-1 text-sm ${mode === 'ask' ? 'bg-blue-600 text-white' : 'bg-neutral-800 text-neutral-400'}`}
            >
              단일 요청
            </button>
            <button
              type="button"
              onClick={() => setHistoryOpen((o) => !o)}
              className="rounded px-2 py-1 text-sm bg-neutral-800 text-neutral-400"
            >
              {historyOpen ? '이력 숨기기' : '이력 보기'}
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-4">
          {error && (
            <div className="rounded border border-red-900/50 bg-red-900/20 p-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={i}
              className={`rounded border p-3 ${
                msg.role === 'user'
                  ? 'border-blue-900/50 bg-blue-900/20 ml-8'
                  : 'border-neutral-800 bg-neutral-900/50 mr-8'
              }`}
            >
              <span className="text-xs font-medium text-neutral-500">{msg.role === 'user' ? '질문' : '응답'}</span>
              <p className="text-sm text-neutral-300 mt-1">
                {msg.content || (msg.role === 'assistant' && 'streaming' in msg && msg.streaming ? '처리 중...' : '')}
              </p>
              {msg.role === 'assistant' && msg.sql && (
                <pre className="mt-2 rounded bg-neutral-950 p-2 text-xs text-neutral-400 overflow-auto whitespace-pre-wrap">
                  {msg.sql}
                </pre>
              )}
              {msg.role === 'assistant' && msg.result?.result && msg.result.result.columns.length > 0 && (
                <div className="mt-2 overflow-auto">
                  <table className="w-full border-collapse text-sm">
                    <thead>
                      <tr>
                        {msg.result.result.columns.map((col) => (
                          <th key={col.name} className="border border-neutral-700 bg-neutral-800 px-2 py-1 text-left text-neutral-300">
                            {col.name}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(msg.result.result.rows ?? []).slice(0, 5).map((row, ri) => (
                        <tr key={ri}>
                          {row.map((cell, ci) => (
                            <td key={ci} className="border border-neutral-700 px-2 py-1 text-neutral-400">
                              {cell == null ? '—' : String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {(msg.result.result.rows?.length ?? 0) > 5 && (
                    <p className="text-xs text-neutral-500 mt-1">상위 5행만 표시 (총 {msg.result.result.row_count}행)</p>
                  )}
                </div>
              )}
            </div>
          ))}

          {streamLog.length > 0 && (
            <div className="rounded border border-neutral-800 bg-neutral-900/50 p-3 text-xs text-neutral-400 font-mono">
              {streamLog.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          )}

          {data?.sql && (
            <div>
              <h3 className="text-sm font-medium text-neutral-400 mb-1">SQL</h3>
              <pre className="rounded border border-neutral-800 bg-neutral-900 p-3 text-sm text-neutral-300 overflow-auto whitespace-pre-wrap">
                {data.sql}
              </pre>
            </div>
          )}

          {chartConfig && chartData.length > 0 && (
            <ChartRecommender data={chartData} config={chartConfig} />
          )}

          {columns.length > 0 && !chartConfig && (
            <div className="overflow-auto">
              <h3 className="text-sm font-medium text-neutral-400 mb-2">결과</h3>
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    {columns.map((col) => (
                      <th key={col.name} className="border border-neutral-700 bg-neutral-800 px-2 py-1 text-left text-neutral-300">
                        {col.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j} className="border border-neutral-700 px-2 py-1 text-neutral-400">
                          {cell == null ? '—' : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {data?.result?.row_count != null && (
                <p className="mt-1 text-xs text-neutral-500">총 {data.result.row_count}행</p>
              )}
            </div>
          )}
        </div>

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
              disabled={loading || !promptValue?.trim()}
              className="rounded bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50 hover:bg-blue-700"
            >
              {loading ? '처리 중...' : '질문'}
            </button>
          </form>
        </div>
      </div>

      {historyOpen && (
        <div className="w-72 flex-shrink-0">
          <QueryHistoryPanel datasourceId={DEFAULT_DATASOURCE} onSelect={handleSelectHistory} />
        </div>
      )}
    </div>
  );
}
