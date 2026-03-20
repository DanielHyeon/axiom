/**
 * 피드백 통계 API 클라이언트.
 *
 * Oracle 서비스의 /feedback/stats/* 엔드포인트를 호출한다.
 */
import { oracleApi } from '@/lib/api/clients';
import type {
  FeedbackSummary,
  FeedbackTrendPoint,
  FailurePattern,
  DatasourceStats,
  FeedbackListResponse,
  FeedbackEntry,
  Granularity,
} from '../types/feedback';

interface DateRangeParams {
  date_from: string;
  date_to: string;
}

/** 피드백 요약 통계 조회 */
export async function getFeedbackSummary(
  params: DateRangeParams,
): Promise<FeedbackSummary> {
  const res = await oracleApi.get('/feedback/stats/summary', { params });
  const body = res as unknown as { success: boolean; data?: FeedbackSummary };
  return (
    body.data ?? {
      total_queries: 0,
      total_feedbacks: 0,
      positive_rate: 0,
      negative_rate: 0,
      partial_rate: 0,
      avg_execution_time_ms: 0,
      period: { from: params.date_from, to: params.date_to },
    }
  );
}

/** 일별/주별 트렌드 데이터 조회 */
export async function getFeedbackTrend(
  params: DateRangeParams & { granularity?: Granularity },
): Promise<FeedbackTrendPoint[]> {
  const res = await oracleApi.get('/feedback/stats/trend', { params });
  const body = res as unknown as { success: boolean; data?: FeedbackTrendPoint[] };
  return body.data ?? [];
}

/** 실패 패턴 분석 조회 */
export async function getFailurePatterns(
  params: DateRangeParams & { limit?: number },
): Promise<FailurePattern[]> {
  const res = await oracleApi.get('/feedback/stats/failures', { params });
  const body = res as unknown as { success: boolean; data?: FailurePattern[] };
  return body.data ?? [];
}

/** 데이터소스별 피드백 분포 조회 */
export async function getDatasourceBreakdown(
  params: DateRangeParams,
): Promise<DatasourceStats[]> {
  const res = await oracleApi.get('/feedback/stats/by-datasource', { params });
  const body = res as unknown as { success: boolean; data?: DatasourceStats[] };
  return body.data ?? [];
}

/** 가장 많이 실패한 질문 TOP-N 조회 */
export async function getTopFailedQueries(
  params: DateRangeParams & { limit?: number },
): Promise<FeedbackEntry[]> {
  const res = await oracleApi.get('/feedback/stats/top-failed', { params });
  const body = res as unknown as { success: boolean; data?: FeedbackEntry[] };
  return body.data ?? [];
}

/** 피드백 목록 조회 (페이지네이션) */
export async function getFeedbackList(params: {
  page?: number;
  page_size?: number;
  rating?: string;
  datasource_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<FeedbackListResponse> {
  const res = await oracleApi.get('/feedback/list', { params });
  const body = res as unknown as { success: boolean; data?: FeedbackListResponse };
  return (
    body.data ?? {
      items: [],
      pagination: { page: 1, page_size: 20, total_count: 0, total_pages: 0 },
    }
  );
}

/** 피드백 삭제 */
export async function deleteFeedback(id: string): Promise<void> {
  await oracleApi.delete(`/feedback/${id}`);
}
