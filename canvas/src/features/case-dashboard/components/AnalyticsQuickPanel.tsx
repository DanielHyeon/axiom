/**
 * 분석 빠른 접근 패널 — analyst 역할 전용.
 * 최근 NL2SQL 쿼리 이력과 즐겨찾기 분석을 보여준다.
 */

import { useQuery } from '@tanstack/react-query';
import { oracleApi } from '@/lib/api/clients';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { BarChart3, MessageSquareText } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface RecentQuery {
  id: string;
  question: string;
  datasource: string;
  createdAt: string;
}

/** 최근 NL2SQL 쿼리 조회 */
async function fetchRecentQueries(): Promise<RecentQuery[]> {
  try {
    const res = await oracleApi.get('/text2sql/history?limit=5');
    const list = res as unknown as Array<Record<string, unknown>>;
    return list.map((q) => ({
      id: String(q.id ?? q.session_id ?? ''),
      question: String(q.question ?? q.user_question ?? ''),
      datasource: String(q.datasource ?? ''),
      createdAt: String(q.created_at ?? ''),
    }));
  } catch {
    return [];
  }
}

export function AnalyticsQuickPanel() {
  const navigate = useNavigate();
  const { data: queries = [] } = useQuery({
    queryKey: ['recent-queries'],
    queryFn: fetchRecentQueries,
  });

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          <h3 className="text-sm font-medium">최근 분석</h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs"
          onClick={() => navigate(ROUTES.ANALYSIS.NL2SQL)}
        >
          <MessageSquareText className="h-3 w-3 mr-1" />
          새 질문
        </Button>
      </div>

      {queries.length === 0 ? (
        <p className="text-xs text-muted-foreground">최근 분석 이력이 없습니다</p>
      ) : (
        <div className="space-y-2">
          {queries.map((q) => (
            <button
              key={q.id}
              onClick={() => navigate(ROUTES.ANALYSIS.NL2SQL)}
              className="w-full text-left rounded-md p-2 hover:bg-muted/50 transition-colors"
            >
              <p className="text-sm truncate">{q.question}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {q.datasource} · {q.createdAt}
              </p>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
