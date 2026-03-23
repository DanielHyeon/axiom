/**
 * 비즈니스 캘린더 API — Vision Calendar 연동.
 * KG-2: 공휴일 CRUD + 영업일 계산.
 */

import { visionApi } from '@/lib/api/clients';
import type { BusinessCalendar, Holiday, WorkingDayResult } from '../types/calendar';

const BASE = '/api/v3/vision/calendar';

/** 캘린더 목록 조회 */
export async function fetchCalendars(): Promise<BusinessCalendar[]> {
  const res = await visionApi.get(BASE);
  return res as unknown as BusinessCalendar[];
}

/** 캘린더 상세 조회 */
export async function fetchCalendar(id: string): Promise<BusinessCalendar> {
  const res = await visionApi.get(`${BASE}/${id}`);
  return res as unknown as BusinessCalendar;
}

/** 공휴일 추가 */
export async function addHoliday(calendarId: string, holiday: Omit<Holiday, 'id'>): Promise<Holiday> {
  const res = await visionApi.post(`${BASE}/${calendarId}/holidays`, holiday);
  return res as unknown as Holiday;
}

/** 공휴일 삭제 */
export async function removeHoliday(calendarId: string, holidayId: string): Promise<void> {
  await visionApi.delete(`${BASE}/${calendarId}/holidays/${holidayId}`);
}

/** 영업일 계산 */
export async function calculateWorkingDays(
  calendarId: string,
  startDate: string,
  endDate: string,
): Promise<WorkingDayResult> {
  const res = await visionApi.get(`${BASE}/${calendarId}/working-days`, {
    params: { start_date: startDate, end_date: endDate },
  });
  return res as unknown as WorkingDayResult;
}
