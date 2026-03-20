/**
 * FeedbackSummaryCards -- 피드백 통계 KPI 카드 4개.
 *
 * 총 쿼리 수, 만족률(%), 불만족률(%), 평균 응답시간(ms)을 표시한다.
 */
import { Card, CardContent } from '@/components/ui/card';
import { BarChart3, ThumbsUp, ThumbsDown, Clock } from 'lucide-react';
import type { FeedbackSummary } from '../types/feedback';

interface FeedbackSummaryCardsProps {
  data: FeedbackSummary | undefined;
  isLoading: boolean;
}

interface KpiCardProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  subtext?: string;
  color: string;
}

function KpiCard({ icon, label, value, subtext, color }: KpiCardProps) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground font-[IBM_Plex_Mono] uppercase tracking-wide">
              {label}
            </p>
            <p className="text-2xl font-semibold text-foreground font-[Sora]">{value}</p>
            {subtext && (
              <p className="text-xs text-muted-foreground">{subtext}</p>
            )}
          </div>
          <div className={`flex items-center justify-center w-9 h-9 rounded-lg ${color}`}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function FeedbackSummaryCards({ data, isLoading }: FeedbackSummaryCardsProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i}>
            <CardContent className="p-5">
              <div className="animate-pulse space-y-3">
                <div className="h-3 w-16 bg-muted rounded" />
                <div className="h-7 w-20 bg-muted rounded" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const totalQueries = data?.total_queries ?? 0;
  const positiveRate = data?.positive_rate ?? 0;
  const negativeRate = data?.negative_rate ?? 0;
  const avgTime = data?.avg_execution_time_ms ?? 0;
  const totalFeedbacks = data?.total_feedbacks ?? 0;

  return (
    <div className="grid grid-cols-4 gap-4">
      <KpiCard
        icon={<BarChart3 className="h-4 w-4 text-blue-600" />}
        label="총 쿼리"
        value={totalQueries.toLocaleString()}
        subtext={`피드백 ${totalFeedbacks}건`}
        color="bg-blue-50"
      />
      <KpiCard
        icon={<ThumbsUp className="h-4 w-4 text-green-600" />}
        label="만족률"
        value={`${(positiveRate * 100).toFixed(1)}%`}
        subtext="positive 비율"
        color="bg-green-50"
      />
      <KpiCard
        icon={<ThumbsDown className="h-4 w-4 text-red-600" />}
        label="불만족률"
        value={`${(negativeRate * 100).toFixed(1)}%`}
        subtext="negative 비율"
        color="bg-red-50"
      />
      <KpiCard
        icon={<Clock className="h-4 w-4 text-amber-600" />}
        label="평균 응답시간"
        value={`${Math.round(avgTime)}ms`}
        subtext="SQL 실행 시간"
        color="bg-amber-50"
      />
    </div>
  );
}
