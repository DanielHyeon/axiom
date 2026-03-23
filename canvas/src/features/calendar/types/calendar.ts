/**
 * 비즈니스 캘린더 타입 정의.
 * KG-2: KAIR BusinessDayCalendar 이식 — Vision Calendar 연동.
 */

/** 공휴일 정의 */
export interface Holiday {
  id: string;
  name: string;
  date: string;       // YYYY-MM-DD
  recurring: boolean;  // 매년 반복 여부
  country: string;     // 국가 코드 (KR, US 등)
}

/** 비즈니스 캘린더 설정 */
export interface BusinessCalendar {
  id: string;
  name: string;
  country: string;
  weekendDays: number[];  // 0(일)~6(토), 기본 [0, 6]
  holidays: Holiday[];
  fiscalYearStartMonth: number; // 1~12, 기본 1(1월)
  tenantId: string;
}

/** 영업일 계산 결과 */
export interface WorkingDayResult {
  startDate: string;
  endDate: string;
  totalDays: number;
  workingDays: number;
  holidays: string[];  // 기간 내 공휴일 날짜 목록
}
