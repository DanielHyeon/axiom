/**
 * 피드백 통계 TanStack Query 훅.
 *
 * 날짜 범위와 시간 단위(granularity)에 따라 통계 데이터를 패칭/캐싱한다.
 * staleTime 5분으로 빈번한 재요청을 방지한다.
 */
import { useQuery } from '@tanstack/react-query';
import {
  getFeedbackSummary,
  getFeedbackTrend,
  getFailurePatterns,
  getDatasourceBreakdown,
  getTopFailedQueries,
  getFeedbackList,
} from '../api/feedbackApi';
import type { Granularity } from '../types/feedback';

const STALE_TIME = 5 * 60 * 1000; // 5분

interface DateRange {
  from: string;
  to: string;
}

/** 피드백 요약 통계 훅 */
export function useFeedbackSummary(dateRange: DateRange) {
  return useQuery({
    queryKey: ['feedback', 'summary', dateRange],
    queryFn: () =>
      getFeedbackSummary({ date_from: dateRange.from, date_to: dateRange.to }),
    staleTime: STALE_TIME,
  });
}

/** 트렌드 차트 데이터 훅 */
export function useFeedbackTrend(
  dateRange: DateRange,
  granularity: Granularity = 'day',
) {
  return useQuery({
    queryKey: ['feedback', 'trend', dateRange, granularity],
    queryFn: () =>
      getFeedbackTrend({
        date_from: dateRange.from,
        date_to: dateRange.to,
        granularity,
      }),
    staleTime: STALE_TIME,
  });
}

/** 실패 패턴 데이터 훅 */
export function useFailurePatterns(dateRange: DateRange, limit = 20) {
  return useQuery({
    queryKey: ['feedback', 'failures', dateRange, limit],
    queryFn: () =>
      getFailurePatterns({
        date_from: dateRange.from,
        date_to: dateRange.to,
        limit,
      }),
    staleTime: STALE_TIME,
  });
}

/** 데이터소스별 분포 훅 */
export function useDatasourceBreakdown(dateRange: DateRange) {
  return useQuery({
    queryKey: ['feedback', 'by-datasource', dateRange],
    queryFn: () =>
      getDatasourceBreakdown({
        date_from: dateRange.from,
        date_to: dateRange.to,
      }),
    staleTime: STALE_TIME,
  });
}

/** 가장 많이 실패한 질문 훅 */
export function useTopFailedQueries(dateRange: DateRange, limit = 10) {
  return useQuery({
    queryKey: ['feedback', 'top-failed', dateRange, limit],
    queryFn: () =>
      getTopFailedQueries({
        date_from: dateRange.from,
        date_to: dateRange.to,
        limit,
      }),
    staleTime: STALE_TIME,
  });
}

/** 피드백 목록 (페이지네이션) 훅 */
export function useFeedbackList(params: {
  page?: number;
  page_size?: number;
  rating?: string;
  datasource_id?: string;
  date_from?: string;
  date_to?: string;
}) {
  return useQuery({
    queryKey: ['feedback', 'list', params],
    queryFn: () => getFeedbackList(params),
    staleTime: STALE_TIME,
  });
}
