/**
 * CEP (Complex Event Processing) 규칙 관련 타입 정의
 */

/** 조건 유형 — 규칙 평가 시 사용하는 비교 연산자 */
export type ConditionType =
  | 'greater_than'
  | 'less_than'
  | 'equal'
  | 'not_equal'
  | 'greater_equal'
  | 'less_equal'
  | 'between'
  | 'contains';

/** 심각도 레벨 */
export type Severity = 'critical' | 'warning' | 'info';

/** CEP 규칙 엔티티 */
export interface CEPRule {
  id: string;
  name: string;
  description?: string;
  /** SQL 쿼리 — 모니터링 대상 데이터 추출용 */
  sql_query: string;
  /** 비교 조건 유형 */
  condition_type: ConditionType;
  /** 임계값 */
  threshold: number;
  /** 추가 임계값 (between 조건일 때 상한) */
  threshold_upper?: number;
  /** 심각도 */
  severity: Severity;
  /** 활성화 여부 */
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

/** 규칙 생성/수정 요청 페이로드 */
export interface CEPRulePayload {
  name: string;
  description?: string;
  sql_query: string;
  condition_type: ConditionType;
  threshold: number;
  threshold_upper?: number;
  severity: Severity;
  enabled?: boolean;
}

/** 규칙 평가 결과 */
export interface CEPResult {
  rule_id: string;
  /** 평가된 값 */
  evaluated_value: number;
  /** 조건 충족 여부 */
  triggered: boolean;
  /** 평가 시각 */
  evaluated_at: string;
  /** 상세 메시지 */
  message?: string;
}

/** 규칙 평가 이력 항목 */
export interface CEPHistoryItem {
  id: string;
  rule_id: string;
  evaluated_value: number;
  triggered: boolean;
  evaluated_at: string;
  message?: string;
}
