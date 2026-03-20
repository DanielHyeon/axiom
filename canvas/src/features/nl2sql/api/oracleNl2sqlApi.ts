import { oracleApi } from '@/lib/api/clients';
import { createNdjsonStream } from '@/lib/api/streamManager';
import { toast } from 'sonner';
import { AppError } from '@/lib/api/errors';
import type { DatasourceInfo, TableMeta, ColumnMeta } from '@/features/nl2sql/types/nl2sql';

/** NL2SQL 에러 코드별 사용자 메시지 */
const NL2SQL_ERROR_MESSAGES: Record<string, string> = {
  QUESTION_TOO_SHORT: '2자 이상의 질문을 입력해주세요.',
  QUESTION_TOO_LONG: '질문은 2000자 이내로 입력해주세요.',
  DATASOURCE_NOT_FOUND: '지정된 데이터소스를 찾을 수 없습니다.',
  SCHEMA_NOT_FOUND: '질문과 관련된 테이블을 찾지 못했습니다.',
  SQL_GENERATION_FAILED: 'SQL 생성에 실패했습니다. 다시 시도해주세요.',
  SQL_GUARD_REJECT: '생성된 SQL이 안전성 검증을 통과하지 못했습니다.',
  SQL_EXECUTION_TIMEOUT: '쿼리 실행 시간이 초과되었습니다 (30초).',
  SQL_EXECUTION_ERROR: '쿼리 실행 중 오류가 발생했습니다.',
  LLM_UNAVAILABLE: 'AI 서비스에 일시적으로 연결할 수 없습니다.',
  NEO4J_UNAVAILABLE: '메타데이터 서비스에 연결할 수 없습니다.',
};

/** error.code → 한글 메시지 해석. AppError가 아닌 경우 일반 메시지 반환 */
export function resolveNl2sqlError(err: unknown): string {
  if (err instanceof AppError) {
    return NL2SQL_ERROR_MESSAGES[err.code] ?? err.userMessage;
  }
  return (err as Error).message || 'SQL 실행에 실패했습니다.';
}

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

/** Direct SQL 실행 응답 */
export interface DirectSqlResponse {
  success: boolean;
  data?: {
    result: {
      columns: string[];
      rows: unknown[][];
      row_count: number;
      truncated: boolean;
      execution_time_ms: number;
      backend: string;
    };
    metadata: {
      execution_time_ms: number;
      guard_status: string;
      execution_backend: string;
      query_id?: string | null;
    };
  };
  error?: { code: string; message: string; details?: unknown };
}

/** POST /text2sql/direct-sql — Admin 전용 raw SQL 실행 */
export async function postDirectSql(
  sql: string,
  datasourceId: string
): Promise<DirectSqlResponse> {
  try {
    const res = await oracleApi.post('/text2sql/direct-sql', {
      sql,
      datasource_id: datasourceId,
    });
    return res as unknown as DirectSqlResponse;
  } catch (err) {
    if (err instanceof AppError && err.status === 403) {
      toast.error('권한 없음', { description: '관리자만 사용할 수 있습니다.' });
    } else if (err instanceof AppError && err.status === 429) {
      toast.error('요청 제한', { description: resolveNl2sqlError(err) });
    } else {
      toast.error('SQL 실행 오류', { description: resolveNl2sqlError(err) });
    }
    throw err;
  }
}

/** POST /text2sql/ask — 단일 변환+실행 (oracleApi 사용) */
export async function postAsk(
  question: string,
  datasourceId: string,
  options?: { use_cache?: boolean; include_viz?: boolean; row_limit?: number; case_id?: string }
): Promise<AskResponse> {
  try {
    const { case_id, ...restOptions } = options ?? {};
    const res = await oracleApi.post('/text2sql/ask', {
      question,
      datasource_id: datasourceId,
      case_id: case_id || undefined,
      options: restOptions,
    });
    return res as unknown as AskResponse;
  } catch (err) {
    if (err instanceof AppError && err.status === 429) {
      toast.error('요청 제한', { description: resolveNl2sqlError(err) });
    }
    throw err;
  }
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
  const res = await oracleApi.get('/text2sql/history', { params });
  return res as unknown as HistoryResponse;
}

/** POST /text2sql/react — NDJSON 스트림. streamManager 사용, URL은 oracleApi base와 동일. */
export function postReactStream(
  question: string,
  datasourceId: string,
  callbacks: {
    onMessage: (step: ReactStreamStep) => void;
    onComplete: () => void;
    onError: (error: Error) => void;
  },
  options?: { case_id?: string; row_limit?: number }
): Promise<AbortController> {
  const base = (oracleApi.defaults.baseURL || '').replace(/\/$/, '');
  const url = `${base}/text2sql/react`;
  return createNdjsonStream<ReactStreamStep>(
    url,
    {
      question,
      datasource_id: datasourceId,
      case_id: options?.case_id || undefined,
      options: { max_iterations: 5, stream: true, row_limit: options?.row_limit ?? 1000 },
    },
    callbacks
  );
}

// ---------------------------------------------------------------------------
// Meta API
// ---------------------------------------------------------------------------

/** GET /text2sql/meta/datasources */
export async function getDatasources(): Promise<DatasourceInfo[]> {
  const res = await oracleApi.get('/text2sql/meta/datasources');
  const body = res as unknown as { success: boolean; data?: { datasources?: DatasourceInfo[] } };
  return body.data?.datasources ?? [];
}

/** GET /text2sql/meta/tables */
export async function getTables(params: {
  datasource_id: string;
  search?: string;
  page?: number;
  page_size?: number;
  valid_only?: boolean;
}): Promise<{
  tables: TableMeta[];
  pagination: { page: number; page_size: number; total_count: number; total_pages: number };
}> {
  const res = await oracleApi.get('/text2sql/meta/tables', { params });
  const body = res as unknown as {
    success: boolean;
    data?: {
      tables?: TableMeta[];
      pagination?: { page: number; page_size: number; total_count: number; total_pages: number };
    };
  };
  return {
    tables: body.data?.tables ?? [],
    pagination: body.data?.pagination ?? { page: 1, page_size: 50, total_count: 0, total_pages: 0 },
  };
}

/** GET /text2sql/meta/tables/{name}/columns */
export async function getTableColumns(
  tableName: string,
  datasourceId: string
): Promise<ColumnMeta[]> {
  const res = await oracleApi.get(`/text2sql/meta/tables/${encodeURIComponent(tableName)}/columns`, {
    params: { datasource_id: datasourceId },
  });
  const body = res as unknown as { success: boolean; data?: { columns?: ColumnMeta[] } };
  return body.data?.columns ?? [];
}
