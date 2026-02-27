// features/insight/api/insightApi.ts
// Weaver Insight API client

import { weaverApi } from '@/lib/api/clients';
import type {
  ImpactRequest,
  ImpactResponse,
  ImpactJobResponse,
  JobStatusResponse,
  DriverDetailResponse,
  DriverListResponse,
  KpiListResponse,
  TimeRange,
} from '../types/insight';

type Post<T> = (url: string, body: unknown) => Promise<T>;
type Get<T> = (url: string) => Promise<T>;

// ---------------------------------------------------------------------------
// POST /api/insight/impact — KPI Impact Graph (returns 200 or 202)
// ---------------------------------------------------------------------------

/**
 * Request impact graph analysis.
 *
 * The response interceptor already unwraps `response.data`, so the return
 * value is the JSON body itself. The caller must inspect `status` / `job_id`
 * to decide whether to start polling.
 *
 * NOTE: Because the response interceptor returns `response.data`, we lose
 * access to `response.status` (202 vs 200). We detect 202 by checking for
 * the presence of `job_id` + absence of `graph` in the body.
 */
export async function requestImpact(
  params: ImpactRequest,
): Promise<ImpactResponse | ImpactJobResponse> {
  const body = {
    kpi_fingerprint: params.kpi_fingerprint,
    kpi_id: params.kpi_id,
    time_range: params.time_range ?? '30d',
    top: params.top_drivers ?? 20,
    datasource_id: params.datasource_id ?? '',
  };

  return (weaverApi.post as unknown as Post<ImpactResponse | ImpactJobResponse>)(
    '/api/insight/impact',
    body,
  );
}

/**
 * Type guard to distinguish a 202 job response from a 200 cached response.
 */
export function isJobResponse(
  res: ImpactResponse | ImpactJobResponse,
): res is ImpactJobResponse {
  return 'job_id' in res && !('graph' in res);
}

// ---------------------------------------------------------------------------
// GET /api/insight/jobs/{job_id} — Poll job status
// ---------------------------------------------------------------------------

export function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return (weaverApi.get as unknown as Get<JobStatusResponse>)(
    `/api/insight/jobs/${jobId}`,
  );
}

// ---------------------------------------------------------------------------
// POST /api/insight/query-subgraph — SQL → subgraph
// ---------------------------------------------------------------------------

export interface QuerySubgraphRequest {
  sql: string;
  datasource?: string;
}

export interface QuerySubgraphResponse {
  parse_result: {
    mode: string;
    confidence: number;
    tables: Array<{ name: string }>;
    joins: unknown[];
    predicates: unknown[];
    select_columns: Array<{ column: string }>;
    group_by_columns: string[];
    warnings: string[];
    errors: string[];
  };
  graph: import('../types/insight').GraphData;
  trace_id: string;
}

export function postQuerySubgraph(
  req: QuerySubgraphRequest,
): Promise<QuerySubgraphResponse> {
  return (weaverApi.post as unknown as Post<QuerySubgraphResponse>)(
    '/api/insight/query-subgraph',
    req,
  );
}

// ---------------------------------------------------------------------------
// GET /api/insight/kpis — KPI list
// ---------------------------------------------------------------------------

export function fetchKpis(params?: {
  datasource?: string;
  time_range?: TimeRange;
  offset?: number;
  limit?: number;
}): Promise<KpiListResponse> {
  const qs = new URLSearchParams();
  if (params?.datasource) qs.set('datasource', params.datasource);
  if (params?.time_range) qs.set('time_range', params.time_range);
  if (params?.offset != null) qs.set('offset', String(params.offset));
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const query = qs.toString();
  return (weaverApi.get as unknown as Get<KpiListResponse>)(
    `/api/insight/kpis${query ? `?${query}` : ''}`,
  );
}

// ---------------------------------------------------------------------------
// GET /api/insight/drivers — Driver ranking
// ---------------------------------------------------------------------------

export function fetchDriverList(params?: {
  datasource?: string;
  kpi_fingerprint?: string;
  time_range?: TimeRange;
  offset?: number;
  limit?: number;
}): Promise<DriverListResponse> {
  const qs = new URLSearchParams();
  if (params?.datasource) qs.set('datasource', params.datasource);
  if (params?.kpi_fingerprint) qs.set('kpi_fingerprint', params.kpi_fingerprint);
  if (params?.time_range) qs.set('time_range', params.time_range);
  if (params?.offset != null) qs.set('offset', String(params.offset));
  if (params?.limit != null) qs.set('limit', String(params.limit));
  const query = qs.toString();
  return (weaverApi.get as unknown as Get<DriverListResponse>)(
    `/api/insight/drivers${query ? `?${query}` : ''}`,
  );
}

// ---------------------------------------------------------------------------
// GET /api/insight/drivers/detail — Driver detail + evidence
// ---------------------------------------------------------------------------

export function fetchDriverDetail(
  driverKey: string,
  timeRange: TimeRange = '30d',
): Promise<DriverDetailResponse> {
  const qs = new URLSearchParams({ driver_key: driverKey, time_range: timeRange });
  return (weaverApi.get as unknown as Get<DriverDetailResponse>)(
    `/api/insight/drivers/detail?${qs}`,
  );
}

// ---------------------------------------------------------------------------
// GET /api/insight/kpi/activity — KPI activity timeseries (P2-A)
// ---------------------------------------------------------------------------

export interface ActivityPoint {
  date: string;
  value: number;
}

export interface KpiActivityResponse {
  kpi_fingerprint: string;
  series_type: 'activity';
  granularity: 'day' | 'week';
  series: ActivityPoint[];
}

export function fetchKpiActivity(params: {
  kpiFingerprint: string;
  driverKey?: string;
  timeRange?: TimeRange;
  granularity?: 'day' | 'week';
}): Promise<KpiActivityResponse> {
  const qs = new URLSearchParams({ kpi_fingerprint: params.kpiFingerprint });
  if (params.driverKey) qs.set('driver_key', params.driverKey);
  if (params.timeRange) qs.set('time_range', params.timeRange);
  if (params.granularity) qs.set('granularity', params.granularity);
  return (weaverApi.get as unknown as Get<KpiActivityResponse>)(
    `/api/insight/kpi/activity?${qs}`,
  );
}

// ---------------------------------------------------------------------------
// GET /api/insight/schema-coverage — Ontology node coverage (P2-B)
// ---------------------------------------------------------------------------

export interface SchemaCoverageResponse {
  table: string;
  column: string | null;
  query_count: number;
  last_seen: string | null;
  driver_score: { score: number; role: string; kpi_fingerprint: string } | null;
}

export function fetchSchemaCoverage(params: {
  table: string;
  column?: string;
  timeRange?: TimeRange;
}): Promise<SchemaCoverageResponse> {
  const qs = new URLSearchParams({ table: params.table });
  if (params.column) qs.set('column', params.column);
  if (params.timeRange) qs.set('time_range', params.timeRange);
  return (weaverApi.get as unknown as Get<SchemaCoverageResponse>)(
    `/api/insight/schema-coverage?${qs}`,
  );
}
