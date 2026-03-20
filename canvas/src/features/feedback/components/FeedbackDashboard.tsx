/**
 * FeedbackDashboard — 피드백 통계 대시보드 메인 컨테이너.
 *
 * 기간 선택 (DateRangePicker) + 시간 단위(granularity) 컨트롤을 제공하고,
 * 하위 컴포넌트(KPI 카드, 트렌드 차트, 피드백 테이블)를 조합한다.
 */
import { useState, useMemo } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { FeedbackSummaryCards } from './FeedbackSummaryCards';
import { FeedbackTrendChart } from './FeedbackTrendChart';
import { FeedbackTable } from './FeedbackTable';
import {
  useFeedbackSummary,
  useFeedbackTrend,
  useFeedbackList,
} from '../hooks/useFeedbackStats';
import type { Granularity } from '../types/feedback';

/** 기본 날짜 범위: 최근 30일 */
function getDefaultDateRange() {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - 30);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

export function FeedbackDashboard() {
  const defaultRange = useMemo(() => getDefaultDateRange(), []);
  const [dateFrom, setDateFrom] = useState(defaultRange.from);
  const [dateTo, setDateTo] = useState(defaultRange.to);
  const [granularity, setGranularity] = useState<Granularity>('day');
  const [ratingFilter, setRatingFilter] = useState<string>('all');
  const [listPage, setListPage] = useState(1);

  const dateRange = useMemo(() => ({ from: dateFrom, to: dateTo }), [dateFrom, dateTo]);

  // 데이터 패칭
  const summary = useFeedbackSummary(dateRange);
  const trend = useFeedbackTrend(dateRange, granularity);
  const feedbackList = useFeedbackList({
    page: listPage,
    page_size: 20,
    rating: ratingFilter === 'all' ? undefined : ratingFilter,
    date_from: dateFrom,
    date_to: dateTo,
  });

  return (
    <div className="space-y-6">
      {/* 필터 바 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-muted-foreground font-[IBM_Plex_Mono]">기간:</label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => {
              setDateFrom(e.target.value);
              setListPage(1);
            }}
            className="h-8 w-36 text-xs"
          />
          <span className="text-xs text-muted-foreground">~</span>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => {
              setDateTo(e.target.value);
              setListPage(1);
            }}
            className="h-8 w-36 text-xs"
          />
        </div>

        <Select
          value={granularity}
          onValueChange={(v) => setGranularity(v as Granularity)}
        >
          <SelectTrigger className="h-8 w-24 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="day">일별</SelectItem>
            <SelectItem value="week">주별</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={ratingFilter}
          onValueChange={(v) => {
            setRatingFilter(v);
            setListPage(1);
          }}
        >
          <SelectTrigger className="h-8 w-28 text-xs">
            <SelectValue placeholder="평가 필터" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">전체</SelectItem>
            <SelectItem value="positive">긍정</SelectItem>
            <SelectItem value="negative">부정</SelectItem>
            <SelectItem value="partial">수정</SelectItem>
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          onClick={() => {
            summary.refetch();
            trend.refetch();
            feedbackList.refetch();
          }}
        >
          새로고침
        </Button>
      </div>

      {/* KPI 카드 */}
      <FeedbackSummaryCards data={summary.data} isLoading={summary.isLoading} />

      {/* 트렌드 차트 */}
      <FeedbackTrendChart data={trend.data} isLoading={trend.isLoading} />

      {/* 피드백 목록 */}
      <FeedbackTable
        data={feedbackList.data}
        isLoading={feedbackList.isLoading}
        page={listPage}
        onPageChange={setListPage}
      />
    </div>
  );
}
