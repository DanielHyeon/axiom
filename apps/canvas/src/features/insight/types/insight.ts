// features/insight/types/insight.ts
// Insight feature type definitions based on design spec v3.1

// ---------------------------------------------------------------------------
// Graph Node / Edge / Data
// ---------------------------------------------------------------------------

/** Graph node type discriminator */
export type NodeType =
  | 'KPI'
  | 'DRIVER'
  | 'DIMENSION'
  | 'TRANSFORM'
  | 'TABLE'
  | 'COLUMN'
  | 'RECORD'
  | 'PREDICATE';

/** Graph edge type discriminator */
export type EdgeType =
  | 'FK'
  | 'JOIN'
  | 'WHERE_FILTER'
  | 'HAVING_FILTER'
  | 'AGGREGATE'
  | 'DERIVE'
  | 'IMPACT'
  | 'GROUP_BY'
  // Impact Graph specific (from Weaver backend)
  | 'INFLUENCES'
  | 'COUPLED'
  | 'EXPLAINS_BY';

/** Graph node source */
export type NodeSource =
  | 'ontology'
  | 'query_log'
  | 'fk'
  | 'sql_parse'
  | 'manual'
  | 'rule'
  | 'merged';

/** Common graph node */
export interface GraphNode {
  id: string;
  label: string;
  type: NodeType;
  source?: NodeSource;
  confidence?: number;
  labels?: string[];
  layer?: string;
  score?: number;
  /** Breakdown or other server-side metadata (breakdown keys: usage, kpi_connection, ...) */
  meta?: Record<string, unknown>;
  properties?: Record<string, unknown>;
  position?: { x: number; y: number };
}

/** Common graph edge */
export interface GraphEdge {
  id?: string;
  source: string;
  target: string;
  type: EdgeType;
  label?: string;
  weight?: number;
  source_type?: NodeSource;
  confidence?: number;
  meta?: Record<string, unknown>;
}

/** Enhanced metadata (all API responses) */
export interface GraphMeta {
  schema_version: string;
  analysis_version: string;
  generated_at: string;
  time_range: { from: string; to: string };
  datasource: string;
  cache_hit: boolean;
  cache_ttl_remaining_s?: number;
  limits: {
    max_nodes: number;
    max_edges: number;
    depth: number;
    top_drivers?: number;
  };
  truncated: boolean;
  layout?: { name: string; computed_by: 'server' | 'client' };
  trace_id?: string;
  explain?: {
    scoring_formula?: string;
    total_queries_analyzed: number;
    time_range_used: string;
    fallback_used?: boolean;
    mode?: 'primary' | 'fallback';
  };
}

/** Graph data container */
export interface GraphData {
  meta: GraphMeta;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

// ---------------------------------------------------------------------------
// Impact Path
// ---------------------------------------------------------------------------

export interface ImpactPath {
  path_id: string;
  kpi_id: string;
  driver_id: string;
  nodes: string[];
  strength: number;
  queries_count: number;
}

// ---------------------------------------------------------------------------
// Driver Score Breakdown
// ---------------------------------------------------------------------------

export interface DriverScoreBreakdown {
  driver_id: string;
  score: number;
  breakdown: {
    usage: number;
    kpi_connection: number;
    centrality: number;
    discriminative: number;
    volatility: number;
    cardinality_adjust: number;
    sample_size_guard: number;
  };
  cardinality_est: number;
  sample_size: number;
}

// ---------------------------------------------------------------------------
// Async Job
// ---------------------------------------------------------------------------

export interface InsightJob {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  progress_pct?: number;
  poll_after_ms: number;
  created_at?: string;
  completed_at?: string;
  result_url?: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// API Request / Response Types
// ---------------------------------------------------------------------------

export type TimeRange = '7d' | '30d' | '90d';

export interface ImpactRequest {
  kpi_fingerprint: string;
  kpi_id?: string;
  time_range?: TimeRange;
  top_drivers?: number;
  datasource_id?: string;
}

/** Impact API response — 200 (cache hit) */
export interface ImpactResponse {
  kpi?: {
    id: string;
    name: string;
    fingerprint: string;
    current_value?: number;
    trend?: 'up' | 'down' | 'stable';
    source?: string;
    primary?: boolean;
  };
  graph: GraphData;
  paths?: ImpactPath[];
}

/** Impact API response — 202 (job created) */
export interface ImpactJobResponse {
  job_id: string;
  status: 'queued' | 'running';
  poll_url?: string;
  poll_after_ms: number;
}

/** Compact evidence entry from job response (per-node query samples) */
export interface CompactEvidence {
  query_id: string;
  executed_at: string;
  tables: unknown[];
  joins: unknown[];
  predicates: unknown[];
  group_by: unknown[];
  select: unknown[];
}

/** Backend path entry from impact graph job result */
export interface BackendPath {
  nodes: string[];
  score: number;
  why?: unknown[];
}

/** Driver rank item (derived from graph data) */
export interface DriverRankItem {
  node_id: string;
  label: string;
  type: NodeType;
  score: number;
  evidence_count: number;
}

/** Job status polling response */
export interface JobStatusResponse {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  progress?: number;
  error?: string;
  graph?: {
    graph: GraphData;
    paths?: BackendPath[];
    kpi?: ImpactResponse['kpi'];
    evidence?: Record<string, CompactEvidence[]>;
  };
  trace_id?: string;
}

// ---------------------------------------------------------------------------
// KPI List (P0-A)
// ---------------------------------------------------------------------------

export interface KpiListItem {
  id: string;
  name: string;
  source: 'ontology' | 'query_log' | 'merged';
  primary: boolean;
  fingerprint: string;
  datasource: string;
  query_count: number;
  last_seen: string | null;
  trend: 'up' | 'down' | 'flat' | null;
  aliases: string[];
}

export interface KpiListResponse {
  kpis: KpiListItem[];
  total: number;
  pagination: { offset: number; limit: number; has_more: boolean };
}

// ---------------------------------------------------------------------------
// Driver List (P0-B)
// ---------------------------------------------------------------------------

export interface DriverListItem {
  driver_key: string;
  role: string;
  score: number;
  breakdown: Record<string, number>;
  kpi_fingerprint: string;
  created_at: string | null;
}

export interface DriverListResponse {
  drivers: DriverListItem[];
  total: number;
  pagination: { offset: number; limit: number; has_more: boolean };
  meta: {
    source: 'driver_scores' | 'empty';
    kpi_fingerprint: string | null;
    datasource: string | null;
    generated_at: string;
  };
}

/** Driver detail response (from GET /api/insight/drivers/{id}) */
export interface DriverDetailResponse {
  driver: {
    driver_id: string;
    label: string;
    type: 'DRIVER';
    source: NodeSource;
    score: number;
    breakdown: DriverScoreBreakdown['breakdown'];
    cardinality_est: number;
    sample_size: number;
    total_rows?: number;
  };
  evidence: {
    top_queries: Array<{
      query_id: string;
      normalized_sql: string;
      count: number;
      executed_at?: string;
    }>;
    paths: Array<{
      path_id: string;
      nodes: string[];
      weight: number;
    }>;
  };
}
