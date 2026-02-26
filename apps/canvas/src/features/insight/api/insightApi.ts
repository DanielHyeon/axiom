// features/insight/api/insightApi.ts
// Weaver Insight API client

import { weaverApi } from '@/lib/api/clients';
import type {
  ImpactRequest,
  ImpactResponse,
  ImpactJobResponse,
  JobStatusResponse,
  DriverDetailResponse,
  TimeRange,
} from '../types/insight';

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

  // weaverApi interceptor returns `response.data` directly
  const data = await (weaverApi.post as unknown as (
    url: string,
    body: unknown,
  ) => Promise<ImpactResponse | ImpactJobResponse>)(
    '/api/insight/impact',
    body,
  );

  return data;
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

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const data = await (weaverApi.get as unknown as (
    url: string,
  ) => Promise<JobStatusResponse>)(`/api/insight/jobs/${jobId}`);
  return data;
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

export async function postQuerySubgraph(
  req: QuerySubgraphRequest,
): Promise<QuerySubgraphResponse> {
  const data = await (weaverApi.post as unknown as (
    url: string,
    body: unknown,
  ) => Promise<QuerySubgraphResponse>)('/api/insight/query-subgraph', req);
  return data;
}

// ---------------------------------------------------------------------------
// GET /api/insight/kpis — KPI list (NOT YET IMPLEMENTED on backend)
// ---------------------------------------------------------------------------

export interface KpiListItem {
  id: string;
  name: string;
  fingerprint: string;
  source: string;
  table?: string;
  column?: string;
  aggregate?: string;
  query_count?: number;
  last_value?: number;
  trend?: 'up' | 'down' | 'stable';
  change_pct?: number;
}

export async function getKpiList(
  _timeRange?: TimeRange,
  _datasource?: string,
): Promise<KpiListItem[]> {
  // API not implemented yet — return empty mock
  return [];
}

// ---------------------------------------------------------------------------
// GET /api/insight/drivers — Driver ranking (NOT YET IMPLEMENTED)
// ---------------------------------------------------------------------------

export async function getDriverList(
  _kpiFingerprint?: string,
  _timeRange?: TimeRange,
): Promise<unknown[]> {
  // API not implemented yet — return empty
  return [];
}

// ---------------------------------------------------------------------------
// GET /api/insight/drivers/{id} — Driver detail (NOT YET IMPLEMENTED)
// ---------------------------------------------------------------------------

export async function getDriverDetail(
  driverId: string,
  _timeRange?: TimeRange,
): Promise<DriverDetailResponse> {
  // Return mock data since API is not yet implemented
  return {
    driver: {
      driver_id: driverId,
      label: driverId.replace('drv_', '').replace(/_/g, '.'),
      type: 'DRIVER',
      source: 'query_log',
      score: 0.75,
      breakdown: {
        usage: 0.25,
        kpi_connection: 0.20,
        centrality: 0.15,
        discriminative: 0.08,
        volatility: 0.07,
        cardinality_adjust: -0.03,
        sample_size_guard: 0.03,
      },
      cardinality_est: 100,
      sample_size: 50,
      total_rows: 10000,
    },
    evidence: {
      top_queries: [],
      paths: [],
    },
  };
}
