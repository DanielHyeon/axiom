/**
 * 월별 캘린더 그리드 — 공휴일 하이라이트.
 * KG-2: 달력 UI + 공휴일 표시 + 영업일 계산 결과.
 */

import { useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { Holiday } from '../types/calendar';

interface CalendarGridProps {
  holidays: Holiday[];
  onDateClick?: (date: string) => void;
  weekendDays?: number[];
}

const DAY_NAMES = ['일', '월', '화', '수', '목', '금', '토'];

function formatDate(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

export function CalendarGrid({ holidays, onDateClick, weekendDays = [0, 6] }: CalendarGridProps) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());

  // 공휴일 날짜 Set (빠른 조회)
  const holidaySet = useMemo(() => {
    const set = new Set<string>();
    for (const h of holidays) {
      if (h.recurring) {
        // 매년 반복 — 해당 월/일만 비교
        const [, mm, dd] = h.date.split('-');
        set.add(formatDate(year, Number(mm) - 1, Number(dd)));
      } else {
        set.add(h.date);
      }
    }
    return set;
  }, [holidays, year]);

  // 월의 날짜 배열 생성
  const days = useMemo(() => {
    const firstDay = new Date(year, month, 1).getDay();
    const lastDate = new Date(year, month + 1, 0).getDate();
    const cells: (number | null)[] = [];
    // 첫 주 빈칸
    for (let i = 0; i < firstDay; i++) cells.push(null);
    // 날짜
    for (let d = 1; d <= lastDate; d++) cells.push(d);
    return cells;
  }, [year, month]);

  const prevMonth = () => {
    if (month === 0) { setYear(year - 1); setMonth(11); }
    else setMonth(month - 1);
  };

  const nextMonth = () => {
    if (month === 11) { setYear(year + 1); setMonth(0); }
    else setMonth(month + 1);
  };

  return (
    <div className="border border-border rounded-lg bg-card p-4">
      {/* 월 네비게이션 */}
      <div className="flex items-center justify-between mb-4">
        <Button variant="ghost" size="sm" onClick={prevMonth} aria-label="이전 달">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <h3 className="text-sm font-medium">{year}년 {month + 1}월</h3>
        <Button variant="ghost" size="sm" onClick={nextMonth} aria-label="다음 달">
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {/* 요일 헤더 */}
      <div className="grid grid-cols-7 gap-1 mb-1">
        {DAY_NAMES.map((d, i) => (
          <div
            key={d}
            className={`text-center text-xs font-medium py-1 ${
              weekendDays.includes(i) ? 'text-destructive' : 'text-muted-foreground'
            }`}
          >
            {d}
          </div>
        ))}
      </div>

      {/* 날짜 그리드 */}
      <div className="grid grid-cols-7 gap-1">
        {days.map((day, idx) => {
          if (day === null) return <div key={`e-${idx}`} />;

          const dateStr = formatDate(year, month, day);
          const dayOfWeek = new Date(year, month, day).getDay();
          const isWeekend = weekendDays.includes(dayOfWeek);
          const isHoliday = holidaySet.has(dateStr);
          const isToday = dateStr === formatDate(today.getFullYear(), today.getMonth(), today.getDate());

          // 공휴일 이름 (툴팁용)
          const holidayName = holidays.find((h) => {
            if (h.recurring) {
              const [, mm, dd] = h.date.split('-');
              return Number(mm) - 1 === month && Number(dd) === day;
            }
            return h.date === dateStr;
          })?.name;

          return (
            <button
              key={dateStr}
              type="button"
              onClick={() => onDateClick?.(dateStr)}
              title={holidayName ?? (isWeekend ? '주말' : undefined)}
              className={`relative h-8 rounded text-xs transition-colors ${
                isToday ? 'ring-1 ring-primary font-bold' : ''
              } ${
                isHoliday
                  ? 'bg-destructive/15 text-destructive font-medium'
                  : isWeekend
                    ? 'text-destructive/60'
                    : 'text-foreground hover:bg-muted'
              }`}
            >
              {day}
              {isHoliday && (
                <div className="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-destructive" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
