import { oracleApi } from '@/lib/api/clients';
import { createNdjsonStream } from '@/lib/api/streamManager';

/** Oracle /text2sql/ask 단일 요청 응답 */
export interface AskResponse {
  success: boolean;
  data?: {
    question: string;
    sql: string;
    result: { columns: { name: string; type: string }[]; rows: unknown[][]; row_count: number; truncated?: boolean };
    visualization?: { chart_type: string; config?: Record<string, string> } | null;
    summary?: string | null;
    metadata?: { execution_time_ms?: number; tables_used?: string[]; cache_hit?: boolean };
  };
  error?: { code: string; message: string; details?: unknown };
}

/** Oracle /text2sql/react NDJSON 스트림 한 줄 */
export interface ReactStreamStep {
  step: string;
  iteration?: number;
  data?: Record<string, unknown>;
}

/** POST /text2sql/ask — 단일 변환+실행 (oracleApi 사용) */
export async function postAsk(
  question: string,
  datasourceId: string,
  options?: { use_cache?: boolean; include_viz?: boolean; row_limit?: number }
): Promise<AskResponse> {
  const data = await oracleApi.post<AskResponse>('/text2sql/ask', {
    question,
    datasource_id: datasourceId,
    options: options ?? {},
  });
  return data as AskResponse;
}

/** GET /text2sql/history — 쿼리 이력 목록 */
export interface HistoryItem {
  id: string;
  question: string;
  sql: string;
  status: 'success' | 'error';
  execution_time_ms?: number;
  row_count?: number | null;
  datasource_id: string;
  created_at: string;
  feedback?: { rating?: string; comment?: string } | null;
}

export interface HistoryResponse {
  success: boolean;
  data: {
    history: HistoryItem[];
    pagination: { page: number; page_size: number; total_count: number; total_pages: number };
  };
}

/** GET /text2sql/history — oracleApi 사용 */
export async function getHistory(params?: {
  datasource_id?: string;
  page?: number;
  page_size?: number;
  date_from?: string;
  date_to?: string;
  status?: 'success' | 'error';
}): Promise<HistoryResponse> {
  const data = await oracleApi.get<HistoryResponse>('/text2sql/history', { params });
  return data as HistoryResponse;
}

/** POST /text2sql/react — NDJSON 스트림. streamManager 사용, URL은 oracleApi base와 동일. */
export function postReactStream(
  question: string,
  datasourceId: string,
  callbacks: {
    onMessage: (step: ReactStreamStep) => void;
    onComplete: () => void;
    onError: (error: Error) => void;
  }
): Promise<AbortController> {
  const base = (oracleApi.defaults.baseURL || '').replace(/\/$/, '');
  const url = `${base}/text2sql/react`;
  return createNdjsonStream<ReactStreamStep>(
    url,
    {
      question,
      datasource_id: datasourceId,
      options: { max_iterations: 5, stream: true },
    },
    callbacks
  );
}
