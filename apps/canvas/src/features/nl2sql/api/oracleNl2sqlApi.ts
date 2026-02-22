import { createNdjsonStream } from '@/lib/api/streamManager';
import { useAuthStore } from '@/stores/authStore';

const getOracleBaseUrl = (): string =>
  (import.meta.env.VITE_ORACLE_URL || 'http://localhost:8004').replace(/\/$/, '');

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

/** POST /text2sql/ask — 단일 변환+실행 */
export async function postAsk(
  question: string,
  datasourceId: string,
  options?: { use_cache?: boolean; include_viz?: boolean; row_limit?: number }
): Promise<AskResponse> {
  const token = useAuthStore.getState().accessToken;
  const url = `${getOracleBaseUrl()}/text2sql/ask`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      question,
      datasource_id: datasourceId,
      options: options ?? {},
    }),
  });
  const json = (await res.json()) as AskResponse;
  if (!res.ok) {
    throw new Error(json.error?.message || `Request failed: ${res.status}`);
  }
  return json;
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

export async function getHistory(params?: {
  datasource_id?: string;
  page?: number;
  page_size?: number;
  date_from?: string;
  date_to?: string;
  status?: 'success' | 'error';
}): Promise<HistoryResponse> {
  const token = useAuthStore.getState().accessToken;
  const url = new URL(`${getOracleBaseUrl()}/text2sql/history`);
  if (params?.datasource_id) url.searchParams.set('datasource_id', params.datasource_id);
  if (params?.page != null) url.searchParams.set('page', String(params.page));
  if (params?.page_size != null) url.searchParams.set('page_size', String(params.page_size));
  if (params?.date_from) url.searchParams.set('date_from', params.date_from);
  if (params?.date_to) url.searchParams.set('date_to', params.date_to);
  if (params?.status) url.searchParams.set('status', params.status);

  const res = await fetch(url.toString(), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const json = (await res.json()) as HistoryResponse;
  if (!res.ok) {
    throw new Error('Failed to load history');
  }
  return json;
}

/** POST /text2sql/react — NDJSON 스트림. streamManager 사용. */
export function postReactStream(
  question: string,
  datasourceId: string,
  callbacks: {
    onMessage: (step: ReactStreamStep) => void;
    onComplete: () => void;
    onError: (error: Error) => void;
  }
): Promise<AbortController> {
  const url = `${getOracleBaseUrl()}/text2sql/react`;
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
