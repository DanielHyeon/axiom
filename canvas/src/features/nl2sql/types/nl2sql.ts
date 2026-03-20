/** Chart Type — matches Oracle API visualization.chart_type */
export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'kpi_card' | 'table';

export interface ResultColumn {
    name: string;
    type: string; // 'varchar' | 'numeric' | 'bigint' | 'date' | ...
}

export interface ChartConfig {
    chart_type: ChartType;
    config: Record<string, string>;
}

export type ReactStepType =
    | 'select'    // Table Selection
    | 'generate'  // SQL Gen
    | 'validate'  // SQL validation
    | 'fix'       // SQL fix
    | 'execute'   // Execution
    | 'quality'   // Quality check
    | 'triage'    // Triage
    | 'result'    // Final result
    | 'error';    // Error

export interface Nl2SqlState {
    status: 'idle' | 'thinking' | 'sql_generated' | 'executing' | 'result' | 'error';
    thinkingText: string;
    sql: string | null;
    explanation: string | null;
    columns: ResultColumn[];
    rows: (string | number | null)[][];
    rowCount: number;
    queryTime: number;
    chartRecommendation: ChartConfig | null;
}

/** Oracle Meta API — datasource info */
export interface DatasourceInfo {
    id: string;
    name: string;
    type: string;
    host: string;
    database: string;
    schema: string;
    status: string;
}

/** Oracle Meta API — table metadata */
export interface TableMeta {
    name: string;
    schema: string;
    db: string;
    description: string | null;
    column_count: number;
    is_valid: boolean;
    has_vector: boolean;
}

/** Oracle Meta API — column metadata */
export interface ColumnMeta {
    name: string;
    fqn: string;
    data_type: string;
    nullable: boolean;
    is_primary_key: boolean;
    description: string | null;
    has_vector: boolean;
}

/** Execution metadata from API response */
export interface ExecutionMetadata {
    execution_time_ms?: number;
    tables_used?: string[];
    schema_source?: string;
    guard_status?: string;
    guard_fixes?: string[];
    cache_hit?: boolean;
    query_id?: string | null;
}
