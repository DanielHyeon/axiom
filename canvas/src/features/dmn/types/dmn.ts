/**
 * DMN 결정 테이블 타입 정의.
 * KG-1: KAIR DmnEditor 이식 — Synapse DMN 엔진 연동.
 */

/** 적중 정책 — 규칙이 여러 개 매칭될 때 처리 방식 */
export type HitPolicy = 'FIRST' | 'COLLECT' | 'PRIORITY';

/** 결정 테이블 컬럼 타입 */
export type ColumnKind = 'input' | 'output';

/** 결정 테이블 컬럼 정의 */
export interface DmnColumn {
  id: string;
  name: string;
  kind: ColumnKind;
  dataType: 'string' | 'number' | 'boolean';
  description?: string;
}

/** 결정 규칙 (테이블 행) */
export interface DmnRule {
  id: string;
  priority: number;
  cells: Record<string, string>; // columnId → 조건/결과 표현식
  annotation?: string;
}

/** 결정 테이블 */
export interface DecisionTable {
  id: string;
  name: string;
  hitPolicy: HitPolicy;
  columns: DmnColumn[];
  rules: DmnRule[];
  description?: string;
  tenantId: string;
  createdAt: string;
  updatedAt: string;
}

/** 테스트 실행 요청 */
export interface DmnTestRequest {
  inputs: Record<string, unknown>; // inputColumnName → 값
}

/** 테스트 실행 결과 */
export interface DmnTestResult {
  matchedRules: string[];  // 매칭된 규칙 ID 목록
  outputs: Record<string, unknown>; // outputColumnName → 결과값
  hitPolicy: HitPolicy;
  executionTimeMs: number;
}
