/**
 * 데이터 품질(Data Quality) 도메인 타입 정의
 * KAIR DataQuality.vue / IncidentManager.vue 기반 이식
 */

// DQ 규칙 유형
export type DQRuleType = 'not_null' | 'unique' | 'range' | 'regex' | 'custom_sql';

// 심각도
export type DQSeverity = 'critical' | 'warning' | 'info';

// 인시던트 상태
export type IncidentStatus = 'open' | 'acknowledged' | 'resolved';

// 테스트 레벨 (테이블/컬럼/커스텀)
export type TestLevel = 'table' | 'column' | 'custom';

// 테스트 실행 상태
export type TestRunStatus = 'success' | 'failed' | 'aborted' | 'running';

/** DQ 규칙 — 단일 품질 검증 규칙 */
export interface DQRule {
  id: string;
  name: string;
  tableName: string;
  columnName?: string;
  type: DQRuleType;
  expression: string;
  severity: DQSeverity;
  enabled: boolean;
  level: TestLevel;
  tags?: string[];
  lastResult?: {
    passed: boolean;
    failedRows: number;
    totalRows: number;
    checkedAt: string;
  };
}

/** DQ 인시던트 — 규칙 위반으로 생성된 사고 */
export interface DQIncident {
  id: string;
  ruleId: string;
  ruleName: string;
  tableName: string;
  severity: DQSeverity;
  status: IncidentStatus;
  failedRows: number;
  assignee?: string;
  detectedAt: string;
  resolvedAt?: string;
}

/** DQ 점수 — 전체 품질 지표 */
export interface DQScore {
  overall: number;
  completeness: number;
  accuracy: number;
  consistency: number;
  timeliness: number;
}

/** DQ 통계 — 대시보드 요약 카드용 */
export interface DQStats {
  totalTests: number;
  successCount: number;
  failedCount: number;
  abortedCount: number;
  successRate: number;
  healthyAssets: number;
  totalAssets: number;
  healthyRate: number;
  coverageRate: number;
}

/** DQ 추이 데이터 포인트 */
export interface DQTrendPoint {
  date: string;
  score: number;
  testsPassed: number;
  testsFailed: number;
}

/** 테스트 케이스 생성 요청 DTO */
export interface CreateDQRulePayload {
  name: string;
  tableName: string;
  columnName?: string;
  type: DQRuleType;
  expression: string;
  severity: DQSeverity;
  level: TestLevel;
  tags?: string[];
}

/** 테스트 실행 결과 DTO */
export interface DQTestRunResult {
  ruleId: string;
  status: TestRunStatus;
  failedRows: number;
  totalRows: number;
  executionTimeMs: number;
  checkedAt: string;
  sampleFailures?: Record<string, unknown>[];
}

/** DQ 필터 상태 */
export interface DQFilters {
  searchQuery: string;
  tableFilter: string;
  typeFilter: DQRuleType | '';
  statusFilter: TestRunStatus | '';
  severityFilter: DQSeverity | '';
}
