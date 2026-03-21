"""비즈니스 캘린더 서비스 단위 테스트.

대상 모듈: app.services.business_calendar
순수 함수만 테스트 (DB 의존 없음).
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services.business_calendar import (
    is_business_day,
    filter_business_days,
    get_business_days_in_range,
    aggregate_to_business_days,
)


# ===================================================================
# is_business_day — 영업일 판정
# ===================================================================

class TestIsBusinessDay:
    """영업일 여부 판정 테스트."""

    def test_평일_영업일_판정(self):
        """월~금 평일은 영업일이어야 한다."""
        # 2026-03-23은 월요일
        monday = date(2026, 3, 23)
        assert is_business_day(monday) is True

        # 2026-03-27은 금요일
        friday = date(2026, 3, 27)
        assert is_business_day(friday) is True

    def test_일요일_비영업일(self):
        """일요일은 항상 비영업일이어야 한다."""
        # 2026-03-22는 일요일
        sunday = date(2026, 3, 22)
        assert is_business_day(sunday) is False

    def test_토요일_기본_비영업일(self):
        """토요일은 기본 설정에서 비영업일이어야 한다."""
        # 2026-03-21은 토요일
        saturday = date(2026, 3, 21)
        assert is_business_day(saturday) is False

    def test_토요일_포함_설정(self):
        """include_saturday=True면 토요일도 영업일이어야 한다."""
        saturday = date(2026, 3, 21)
        assert is_business_day(saturday, include_saturday=True) is True

    def test_공휴일_비영업일(self):
        """법정 공휴일은 비영업일이어야 한다."""
        # 2026-01-01은 신정 (목요일이지만 공휴일)
        new_year = date(2026, 1, 1)
        assert is_business_day(new_year) is False

    def test_사용자_공휴일_목록(self):
        """커스텀 공휴일 집합이 올바르게 적용되어야 한다."""
        custom_holidays = {date(2026, 4, 1)}
        # 2026-04-01은 수요일 — 기본은 영업일이지만 커스텀 공휴일로 지정
        assert is_business_day(date(2026, 4, 1), holidays=custom_holidays) is False
        # 커스텀에 없는 날짜는 영업일
        assert is_business_day(date(2026, 4, 2), holidays=custom_holidays) is True


# ===================================================================
# filter_business_days — 비영업일 필터링
# ===================================================================

class TestFilterBusinessDays:
    """비영업일 제거 필터 테스트."""

    def test_필터_비영업일_제거(self):
        """7일(월~일) 시리즈에서 주말 2일을 제거해 5일이 남아야 한다."""
        # 2026-03-23(월) ~ 2026-03-29(일)
        dates = [date(2026, 3, 23 + i) for i in range(7)]
        values = [float(i) for i in range(7)]

        filtered_dates, filtered_values = filter_business_days(dates, values)
        assert len(filtered_dates) == 5
        assert len(filtered_values) == 5

        # 필터링된 날짜가 모두 영업일인지 확인
        for d in filtered_dates:
            assert is_business_day(d) is True

    def test_필터_빈_데이터(self):
        """빈 입력은 빈 리스트를 반환해야 한다."""
        dates, values = filter_business_days([], [])
        assert dates == []
        assert values == []

    def test_날짜_문자열_파싱(self):
        """ISO 문자열 날짜도 올바르게 파싱되어야 한다."""
        dates = ["2026-03-23", "2026-03-24"]  # 월, 화
        values = [10.0, 20.0]

        filtered_dates, filtered_values = filter_business_days(dates, values)
        assert len(filtered_dates) == 2
        assert filtered_values == [10.0, 20.0]

    def test_datetime_객체_파싱(self):
        """datetime 객체도 올바르게 처리되어야 한다."""
        dates = [datetime(2026, 3, 23, 9, 0), datetime(2026, 3, 24, 10, 0)]
        values = [100.0, 200.0]

        filtered_dates, filtered_values = filter_business_days(dates, values)
        assert len(filtered_dates) == 2


# ===================================================================
# get_business_days_in_range — 영업일 범위 조회
# ===================================================================

class TestGetBusinessDaysInRange:
    """기간 내 영업일 조회 테스트."""

    def test_영업일_범위_조회(self):
        """1주일(월~일) 범위에서 5영업일이 반환되어야 한다."""
        start = date(2026, 3, 23)  # 월요일
        end = date(2026, 3, 29)    # 일요일
        bdays = get_business_days_in_range(start, end)
        assert len(bdays) == 5

    def test_시작_종료_역전_빈리스트(self):
        """start > end이면 빈 리스트를 반환해야 한다."""
        bdays = get_business_days_in_range(date(2026, 4, 1), date(2026, 3, 1))
        assert bdays == []


# ===================================================================
# aggregate_to_business_days — 집계
# ===================================================================

class TestAggregateToBusinessDays:
    """비영업일 데이터 집계 테스트."""

    def test_집계_mean(self):
        """mean 집계가 올바르게 수행되어야 한다."""
        # 2026-03-23(월), 2026-03-23(월) — 같은 날 2개 데이터
        dates = [date(2026, 3, 23), date(2026, 3, 23)]
        values = [10.0, 20.0]

        result_dates, result_values = aggregate_to_business_days(dates, values, method="mean")
        assert len(result_dates) == 1
        assert result_values[0] == pytest.approx(15.0, abs=1e-4)

    def test_집계_sum(self):
        """sum 집계가 올바르게 수행되어야 한다."""
        dates = [date(2026, 3, 23), date(2026, 3, 23)]
        values = [10.0, 20.0]

        result_dates, result_values = aggregate_to_business_days(dates, values, method="sum")
        assert result_values[0] == pytest.approx(30.0, abs=1e-4)

    def test_집계_last(self):
        """last 집계가 마지막 값을 반환해야 한다."""
        dates = [date(2026, 3, 23), date(2026, 3, 23)]
        values = [10.0, 20.0]

        result_dates, result_values = aggregate_to_business_days(dates, values, method="last")
        assert result_values[0] == pytest.approx(20.0, abs=1e-4)

    def test_집계_빈_데이터(self):
        """빈 입력은 빈 리스트를 반환해야 한다."""
        result_dates, result_values = aggregate_to_business_days([], [])
        assert result_dates == []
        assert result_values == []
