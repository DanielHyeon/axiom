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
    | 'needs_user_input'  // HIL: 에이전트가 사용자 입력을 요청
    | 'c_pipeline';  // C-Pipeline: 탐색/수렴/탈출 단계

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
    /** P3: 시멘틱 계약 컨텍스트 사용 여부 */
    semantic_context_used?: boolean;
    /** P3: 시멘틱 계약 품질 경고 목록 */
    quality_warnings?: string[];
    /** P4: ContextPack 사용 시 intent 유형 */
    intent_type?: string;
    /** Sprint 2: 품질 신뢰 등급 (TRUSTED / CAUTION / REFERENCE_ONLY / BLOCKED) */
    quality_grade?: string;
    /** Sprint 2: 품질 최종 점수 (0~100) */
    quality_score?: number;
    /** Sprint 2: 품질 등급 안내 문구 (한국어) */
    quality_banner?: string;
    /** Sprint 4: 의도 분류 신뢰도 (0.0~1.0) */
    intent_confidence?: number;
    /** Sprint 4: 의도 분류 모호성 점수 (0.0~1.0, 높을수록 모호) */
    intent_ambiguity?: number;
    /** Sprint 4: 동의어 매칭 수 */
    synonym_matches?: number;
    /** Sprint 4: 폴백 모드 (NONE / SAFE_NARROW / REFERENCE_ONLY) */
    fallback_mode?: string;
    /** Sprint 3: 시멘틱 스냅샷 버전 (요청 단위 고정) */
    snapshot_version?: string;
    /** Sprint 1: 시멘틱 계약 위반 목록 */
    contract_violations?: { code: string; message: string }[];
    /** Sprint 1: 시멘틱 가드 모드 (log_only / warn / enforce) */
    semantic_guard_mode?: string;
}
