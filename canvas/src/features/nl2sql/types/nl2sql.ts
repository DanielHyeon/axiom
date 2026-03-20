/**
 * NL2SQL feature 타입 정의
 *
 * 스키마 관련 공통 타입(DatasourceInfo, TableMeta, ColumnMeta)은
 * shared/types/schema.ts에서 관리하며, 여기서는 re-export한다.
 * NL2SQL 전용 타입(ChartType, ReactStepType, HilRequest 등)만 이 파일에 정의한다.
 */

// ── 공통 스키마 타입 re-export (하위 호환성 유지) ──
export type { DatasourceInfo, TableMeta, ColumnMeta } from '@/shared/types/schema';

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
    | 'error'     // Error
    | 'needs_user_input';  // HIL: 에이전트가 사용자 입력을 요청

/** HIL: 에이전트가 제시하는 선택지 */
export interface HilOption {
    label: string;
    value: string;
    description?: string;
}

/** HIL: 에이전트가 사용자에게 보내는 입력 요청 */
export interface HilRequest {
    type: 'select' | 'confirm' | 'text';
    question: string;
    options?: HilOption[];
    context?: string;
    session_state: string;  // base64 인코딩된 세션 상태
}

/** HIL: 사용자가 에이전트에게 보내는 응답 */
export interface HilResponse {
    session_state: string;
    user_response: string;
}

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
