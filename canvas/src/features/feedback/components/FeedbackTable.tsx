/**
 * FeedbackTable — 피드백 목록 테이블.
 *
 * 개별 피드백 항목을 테이블 형태로 표시하고,
 * 평가 유형별 필터링과 페이지네이션을 지원한다.
 */
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ThumbsUp, ThumbsDown, Edit3, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { FeedbackEntry, FeedbackListResponse } from '../types/feedback';

interface FeedbackTableProps {
  data: FeedbackListResponse | undefined;
  isLoading: boolean;
  page: number;
  onPageChange: (page: number) => void;
}

/** 평가 유형에 따른 배지 표시 — i18n 적용 */
function RatingBadge({ rating }: { rating: FeedbackEntry['rating'] }) {
  const { t } = useTranslation();
  switch (rating) {
    case 'positive':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-50 text-green-700">
          <ThumbsUp className="h-3 w-3" /> {t('feedback.table.positive')}
        </span>
      );
    case 'negative':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-50 text-red-700">
          <ThumbsDown className="h-3 w-3" /> {t('feedback.table.negative')}
        </span>
      );
    case 'partial':
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-amber-50 text-amber-700">
          <Edit3 className="h-3 w-3" /> {t('feedback.table.partial')}
        </span>
      );
    default:
      return null;
  }
}

export function FeedbackTable({
  data,
  isLoading,
  page,
  onPageChange,
}: FeedbackTableProps) {
  const { t } = useTranslation();
  const items = data?.items ?? [];
  const pagination = data?.pagination;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold font-[Sora]">{t('feedback.table.title')}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse h-12 bg-muted rounded" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-8 text-center text-xs text-muted-foreground">
            {t('feedback.table.noData')}
          </div>
        ) : (
          <>
            <div className="overflow-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="px-3 py-2 text-left text-[11px] font-medium text-muted-foreground font-[IBM_Plex_Mono] uppercase">
                      {t('feedback.table.date')}
                    </th>
                    <th className="px-3 py-2 text-left text-[11px] font-medium text-muted-foreground font-[IBM_Plex_Mono] uppercase">
                      {t('feedback.table.question')}
                    </th>
                    <th className="px-3 py-2 text-left text-[11px] font-medium text-muted-foreground font-[IBM_Plex_Mono] uppercase">
                      {t('feedback.table.rating')}
                    </th>
                    <th className="px-3 py-2 text-left text-[11px] font-medium text-muted-foreground font-[IBM_Plex_Mono] uppercase">
                      {t('feedback.table.comment')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr
                      key={item.id}
                      className="border-b border-border last:border-0 hover:bg-muted/50"
                    >
                      <td className="px-3 py-2.5 text-xs text-muted-foreground font-[IBM_Plex_Mono] whitespace-nowrap">
                        {new Date(item.created_at).toLocaleDateString('ko-KR')}
                      </td>
                      <td className="px-3 py-2.5 text-xs text-foreground max-w-[300px] truncate">
                        {item.question}
                      </td>
                      <td className="px-3 py-2.5">
                        <RatingBadge rating={item.rating} />
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground max-w-[200px] truncate">
                        {item.comment || '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 페이지네이션 */}
            {pagination && pagination.total_pages > 1 && (
              <div className="flex items-center justify-between mt-4">
                <span className="text-xs text-muted-foreground font-[IBM_Plex_Mono]">
                  {pagination.total_count}건 중 {(page - 1) * pagination.page_size + 1}-
                  {Math.min(page * pagination.page_size, pagination.total_count)}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    disabled={page <= 1}
                    onClick={() => onPageChange(page - 1)}
                  >
                    <ChevronLeft className="h-3.5 w-3.5" />
                  </Button>
                  <span className="text-xs font-[IBM_Plex_Mono] px-2">
                    {page} / {pagination.total_pages}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    disabled={page >= pagination.total_pages}
                    onClick={() => onPageChange(page + 1)}
                  >
                    <ChevronRight className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
