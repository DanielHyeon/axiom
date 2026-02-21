/** Chart Type — matches Oracle API visualization.chart_type */
export type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'kpi_card' | 'table';

export interface ResultColumn {
    name: string;
    type: string; // 'varchar' | 'numeric' | 'bigint' | 'date' | ...
}

export interface ChartConfig {
    chart_type: ChartType;
    config: {
        x_column: string;
        y_column: string;
        x_label: string;
        y_label: string;
    };
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
