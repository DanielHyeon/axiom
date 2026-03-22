/**
 * 인스턴스 데이터 프리뷰 관련 타입
 */

/** 컬럼 데이터 타입 */
export type ColumnType = 'text' | 'number' | 'date' | 'boolean' | 'json' | 'unknown';

/** 샘플 데이터 응답 */
export interface SampleDataResponse {
  /** 컬럼 이름 배열 */
  columns: string[];
  /** 컬럼별 데이터 타입 */
  column_types: Record<string, ColumnType>;
  /** 샘플 데이터 행 (각 행은 컬럼 순서에 맞는 값 배열) */
  preview: unknown[][];
  /** 전체 레코드 수 */
  total_count: number;
}
