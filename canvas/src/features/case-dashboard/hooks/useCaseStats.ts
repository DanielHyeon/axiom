import { useMemo } from 'react';
import type { Case } from './useCases';

export interface CaseStats {
  total: number;
  inProgress: number;
  inReview: number;
  dueThisWeek: number;
}

function getWeekRange(): { start: Date; end: Date } {
  const now = new Date();
  const day = now.getDay();
  const diff = now.getDate() - day + (day === 0 ? -6 : 1);
  const start = new Date(now);
  start.setDate(diff);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  end.setHours(23, 59, 59, 999);
  return { start, end };
}

export function useCaseStats(cases: Case[] | undefined): CaseStats {
  return useMemo(() => {
    if (!cases) return { total: 0, inProgress: 0, inReview: 0, dueThisWeek: 0 };
    const { start, end } = getWeekRange();
    let dueThisWeek = 0;
    for (const c of cases) {
      if (c.dueDate) {
        const d = new Date(c.dueDate);
        if (d >= start && d <= end) dueThisWeek++;
      }
    }
    return {
      total: cases.length,
      inProgress: cases.filter((c) => c.status === 'IN_PROGRESS').length,
      inReview: cases.filter((c) => c.status === 'PENDING').length,
      dueThisWeek,
    };
  }, [cases]);
}
