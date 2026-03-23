/**
 * 비즈니스 캘린더 훅 — CRUD + 영업일 계산.
 * KG-2: TanStack Query 기반.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { fetchCalendars, fetchCalendar, addHoliday, removeHoliday, calculateWorkingDays } from '../api/calendarApi';
import type { Holiday } from '../types/calendar';

const keys = {
  list: ['calendars'] as const,
  detail: (id: string) => ['calendars', id] as const,
  workingDays: (id: string, start: string, end: string) => ['working-days', id, start, end] as const,
};

export function useCalendars() {
  return useQuery({ queryKey: keys.list, queryFn: fetchCalendars });
}

export function useCalendar(id: string) {
  return useQuery({ queryKey: keys.detail(id), queryFn: () => fetchCalendar(id), enabled: !!id });
}

export function useAddHoliday(calendarId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (holiday: Omit<Holiday, 'id'>) => addHoliday(calendarId, holiday),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(calendarId) });
      toast.success('공휴일이 추가되었습니다');
    },
    onError: () => toast.error('공휴일 추가에 실패했습니다'),
  });
}

export function useRemoveHoliday(calendarId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (holidayId: string) => removeHoliday(calendarId, holidayId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(calendarId) });
      toast.success('공휴일이 삭제되었습니다');
    },
    onError: () => toast.error('삭제에 실패했습니다'),
  });
}

export function useWorkingDays(calendarId: string, startDate: string, endDate: string) {
  return useQuery({
    queryKey: keys.workingDays(calendarId, startDate, endDate),
    queryFn: () => calculateWorkingDays(calendarId, startDate, endDate),
    enabled: !!calendarId && !!startDate && !!endDate,
  });
}
