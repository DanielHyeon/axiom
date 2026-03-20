/**
 * 피드백 통계 대시보드 타입 정의.
 *
 * Oracle 피드백 통계 API 응답과 프론트엔드 컴포넌트에서 사용하는 타입.
 */

/** 개별 피드백 항목 */
export interface FeedbackEntry {
  id: string;
  question: string;
  sql: string;
  rating: 'positive' | 'negative' | 'partial';
  corrected_sql?: string;
  comment?: string;
  user_id: string;
  datasource_id: string;
  created_at: string;
}

/** 피드백 요약 통계 */
export interface FeedbackSummary {
  total_queries: number;
  total_feedbacks: number;
  positive_rate: number;
  negative_rate: number;
  partial_rate: number;
  avg_execution_time_ms: number;
  period: { from: string; to: string };
}

/** 일별/주별 트렌드 데이터 포인트 */
export interface FeedbackTrendPoint {
  date: string;
  positive: number;
  negative: number;
  partial: number;
  total: number;
}

/** 실패 패턴 */
export interface FailurePattern {
  pattern: string;
  count: number;
  last_occurred: string;
  example_question?: string;
}

/** 데이터소스별 통계 */
export interface DatasourceStats {
  datasource_id: string;
  datasource_name?: string;
  total_queries: number;
  positive: number;
  negative: number;
  partial: number;
}

/** 피드백 목록 페이지네이션 응답 */
export interface FeedbackListResponse {
  items: FeedbackEntry[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
  };
}

/** 날짜 범위 필터 */
export interface DateRangeFilter {
  from: string; // ISO date string (YYYY-MM-DD)
  to: string;
}

/** 트렌드 시간 단위 */
export type Granularity = 'day' | 'week';
