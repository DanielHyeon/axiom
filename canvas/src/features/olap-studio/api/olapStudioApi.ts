/**
 * OLAP Studio API 클라이언트
 *
 * Gateway 경유로 OLAP Studio 백엔드와 통신한다.
 * 데이터소스, 모델, 큐브, ETL, 피벗, 리니지 API를 제공한다.
 */

// NOTE: olapApi는 lib/api/clients.ts에 추가 필요 (gateway prefix: /api/gateway/olap)
// 임시로 fetch wrapper를 사용하되 경로를 /api/gateway/olap으로 설정
const BASE = '/api/gateway/olap';

// ─── Gateway fetch wrapper ────────────────────────────────

/** Gateway 경유 fetch — 공통 헤더 및 에러 처리 */
async function olapFetch<T = unknown>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    credentials: 'include',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API 오류: ${res.status}`);
  }

  const body = await res.json();
  return body.data ?? body;
}

// ─── 데이터소스 ───────────────────────────────────────────

/** OLAP 데이터소스 정보 */
export interface DataSource {
  id: string;
  name: string;
  source_type: string;
  is_active: boolean;
  last_health_status: string | null;
}

/** 데이터소스 CRUD + 연결 테스트 */
export const dataSources = {
  /** 전체 데이터소스 목록 조회 */
  list: () => olapFetch<DataSource[]>('/data-sources'),

  /** 단일 데이터소스 상세 조회 */
  get: (id: string) => olapFetch<DataSource>(`/data-sources/${id}`),

  /** 데이터소스 생성 */
  create: (body: { name: string; source_type: string; connection_config: Record<string, unknown> }) =>
    olapFetch<DataSource>('/data-sources', { method: 'POST', body: JSON.stringify(body) }),

  /** 데이터소스 삭제 */
  delete: (id: string) => olapFetch(`/data-sources/${id}`, { method: 'DELETE' }),

  /** 연결 테스트 — 데이터소스 연결 상태 확인 */
  test: (id: string) =>
    olapFetch<{ status: string; message: string }>(`/data-sources/${id}/test`, { method: 'POST' }),
};

// ─── ETL 파이프라인 ────────────────────────────────────────

/** ETL 파이프라인 정보 */
export interface ETLPipeline {
  id: string;
  name: string;
  description: string;
  pipeline_type: string;
  status: string;
  airflow_dag_id: string | null;
  created_at: string;
}

/** ETL 실행 기록 */
export interface ETLRun {
  id: string;
  run_status: string;
  trigger_type: string;
  started_at: string | null;
  ended_at: string | null;
  rows_read: number;
  rows_written: number;
  error_message: string | null;
}

/** ETL 파이프라인 CRUD + 실행 관리 */
export const etlPipelines = {
  /** 전체 파이프라인 목록 조회 */
  list: () => olapFetch<ETLPipeline[]>('/etl/pipelines'),

  /** 단일 파이프라인 상세 조회 */
  get: (id: string) => olapFetch<ETLPipeline>(`/etl/pipelines/${id}`),

  /** 파이프라인 생성 */
  create: (body: { name: string; description?: string; pipeline_type?: string }) =>
    olapFetch<ETLPipeline>('/etl/pipelines', { method: 'POST', body: JSON.stringify(body) }),

  /** 수동 실행 트리거 */
  run: (id: string) => olapFetch<ETLRun>(`/etl/pipelines/${id}/run`, { method: 'POST' }),

  /** 실행 이력 조회 */
  listRuns: (id: string) => olapFetch<ETLRun[]>(`/etl/pipelines/${id}/runs`),
};

// ─── 큐브 ──────────────────────────────────────────────────

/** OLAP 큐브 정보 */
export interface Cube {
  id: string;
  name: string;
  description: string;
  cube_status: string;
  ai_generated: boolean;
  model_id: string | null;
  created_at: string;
  version_no: number;
}

/** 큐브 차원 정보 */
export interface CubeDimension {
  id: string;
  name: string;
  source_column: string;
  hierarchy_level: number;
}

/** 큐브 측정값 정보 */
export interface CubeMeasure {
  id: string;
  name: string;
  expression: string;
  aggregation_type: string;
}

/** 큐브 상세 (차원 + 측정값 포함) */
export interface CubeDetail extends Cube {
  dimensions: CubeDimension[];
  measures: CubeMeasure[];
}

/** 큐브 CRUD + 검증/게시 워크플로 */
export const cubes = {
  /** 전체 큐브 목록 조회 */
  list: () => olapFetch<Cube[]>('/cubes'),

  /** 큐브 상세 조회 (차원 + 측정값 포함) */
  get: (id: string) => olapFetch<CubeDetail>(`/cubes/${id}`),

  /** 큐브 생성 */
  create: (body: { name: string; description?: string; model_id?: string; ai_generated?: boolean }) =>
    olapFetch<Cube>('/cubes', { method: 'POST', body: JSON.stringify(body) }),

  /** 큐브 스키마 검증 — 에러 목록 반환 */
  validate: (id: string) =>
    olapFetch<{ status: string; errors: string[] }>(`/cubes/${id}/validate`, { method: 'POST' }),

  /** 큐브 게시 — VALIDATED 상태에서만 호출 가능 */
  publish: (id: string) =>
    olapFetch<{ cube_id: string; status: string }>(`/cubes/${id}/publish`, { method: 'POST' }),
};

// ─── 피벗 ──────────────────────────────────────────────────

/** 피벗 실행 결과 */
export interface PivotResult {
  sql: string;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  execution_time_ms: number;
  error?: string;
}

/** 피벗 실행 + SQL 미리보기 API */
export const pivot = {
  /** 피벗 쿼리 실행 */
  execute: (body: unknown) =>
    olapFetch<PivotResult>('/pivot/execute', { method: 'POST', body: JSON.stringify(body) }),

  /** 실행 없이 생성될 SQL만 미리보기 */
  previewSql: (body: unknown) =>
    olapFetch<{ sql: string }>('/pivot/preview-sql', { method: 'POST', body: JSON.stringify(body) }),
};
