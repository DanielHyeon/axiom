"""공휴일 저장소 단위 테스트.

holiday_store 모듈의 기본 공휴일 데이터, 범위 조회, 캐시 동작,
DB 미연결 폴백을 검증한다. 실제 DB 연결 없이 순수 함수만 테스트한다.
"""
from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio

from app.services.holiday_store import (
    get_default_holidays,
    get_holidays_for_range,
    load_holidays_from_db,
    clear_holiday_cache,
    _cached_holidays,
)


@pytest.fixture(autouse=True)
def _캐시_초기화():
    """각 테스트 전후에 캐시를 비운다."""
    clear_holiday_cache()
    yield
    clear_holiday_cache()


# ──────────────────────────────────────────────────────────────
# 기본 공휴일 데이터 검증
# ──────────────────────────────────────────────────────────────

class TestGetDefaultHolidays:
    """get_default_holidays() — 연도별 기본 공휴일 시드 데이터 검증."""

    def test_기본_공휴일_2026_포함(self):
        """2026년 공휴일에 설날(2/16~18), 추석(9/24~26) 등이 포함된다."""
        holidays = get_default_holidays(2026)
        assert len(holidays) > 0, "2026년 공휴일이 비어있다"
        # 설날 연휴
        assert date(2026, 2, 16) in holidays
        assert date(2026, 2, 17) in holidays
        assert date(2026, 2, 18) in holidays
        # 추석 연휴
        assert date(2026, 9, 24) in holidays
        assert date(2026, 9, 25) in holidays
        assert date(2026, 9, 26) in holidays

    def test_기본_공휴일_2024_포함(self):
        """2024년 공휴일 데이터가 존재한다."""
        holidays = get_default_holidays(2024)
        assert len(holidays) > 0, "2024년 공휴일이 비어있다"
        # 삼일절
        assert date(2024, 3, 1) in holidays
        # 광복절
        assert date(2024, 8, 15) in holidays

    def test_기본_공휴일_2027_포함(self):
        """2027년 공휴일 데이터가 존재한다."""
        holidays = get_default_holidays(2027)
        assert len(holidays) > 0, "2027년 공휴일이 비어있다"
        # 설날 연휴 (2/5~8)
        assert date(2027, 2, 5) in holidays
        assert date(2027, 2, 6) in holidays

    def test_미지원_연도_빈_집합(self):
        """지원하지 않는 연도(2030)는 빈 집합을 반환한다."""
        holidays = get_default_holidays(2030)
        assert holidays == set()

    def test_신정_포함_확인(self):
        """1월 1일(신정)이 모든 지원 연도에 포함된다."""
        for year in (2024, 2025, 2026, 2027):
            holidays = get_default_holidays(year)
            assert date(year, 1, 1) in holidays, f"{year}년 신정이 누락되었다"

    def test_크리스마스_포함_확인(self):
        """12월 25일(크리스마스)이 모든 지원 연도에 포함된다."""
        for year in (2024, 2025, 2026, 2027):
            holidays = get_default_holidays(year)
            assert date(year, 12, 25) in holidays, f"{year}년 크리스마스가 누락되었다"


# ──────────────────────────────────────────────────────────────
# 범위 조회 테스트
# ──────────────────────────────────────────────────────────────

class TestGetHolidaysForRange:
    """get_holidays_for_range() — 날짜 범위 기반 공휴일 조회 검증."""

    def test_범위_단일_연도(self):
        """같은 연도 내의 시작/종료일 범위에서 올바른 공휴일을 반환한다."""
        # 2026년 상반기만 조회
        start = date(2026, 1, 1)
        end = date(2026, 6, 30)
        holidays = get_holidays_for_range(start, end)
        # 상반기 공휴일이 포함되어야 한다
        assert date(2026, 1, 1) in holidays  # 신정
        assert date(2026, 3, 1) in holidays  # 삼일절
        assert date(2026, 6, 6) in holidays  # 현충일
        # 하반기 공휴일은 제외
        assert date(2026, 12, 25) not in holidays

    def test_범위_다중_연도(self):
        """2025~2026 두 해에 걸친 범위에서 양쪽 공휴일이 합산된다."""
        start = date(2025, 12, 1)
        end = date(2026, 2, 28)
        holidays = get_holidays_for_range(start, end)
        # 2025년 12월 크리스마스
        assert date(2025, 12, 25) in holidays
        # 2026년 1월 신정
        assert date(2026, 1, 1) in holidays
        # 2026년 설날 연휴
        assert date(2026, 2, 16) in holidays

    def test_범위_필터링(self):
        """범위 밖의 공휴일은 반환하지 않는다."""
        # 3월만 조회
        start = date(2026, 3, 1)
        end = date(2026, 3, 31)
        holidays = get_holidays_for_range(start, end)
        # 삼일절만 포함
        assert date(2026, 3, 1) in holidays
        # 2월 설날은 범위 밖
        assert date(2026, 2, 17) not in holidays
        # 5월 어린이날도 범위 밖
        assert date(2026, 5, 5) not in holidays


# ──────────────────────────────────────────────────────────────
# 캐시 동작 테스트
# ──────────────────────────────────────────────────────────────

class TestCache:
    """캐시 저장/초기화 동작 검증."""

    def test_캐시_동작(self):
        """첫 호출 후 캐시에 저장되어 두 번째 호출 시 캐시를 사용한다."""
        assert len(_cached_holidays) == 0, "초기 캐시는 비어있어야 한다"

        # 첫 번째 호출 — 캐시에 저장
        get_holidays_for_range(date(2026, 1, 1), date(2026, 12, 31))
        assert ("KR", 2026) in _cached_holidays

        # 캐시 내용을 수정하여 캐시가 사용되는지 확인
        sentinel = date(2026, 12, 31)
        _cached_holidays[("KR", 2026)].add(sentinel)

        holidays = get_holidays_for_range(date(2026, 1, 1), date(2026, 12, 31))
        assert sentinel in holidays, "캐시된 데이터가 사용되어야 한다"

    def test_캐시_초기화(self):
        """clear_holiday_cache()가 모든 캐시를 비운다."""
        get_holidays_for_range(date(2025, 1, 1), date(2026, 12, 31))
        assert len(_cached_holidays) > 0

        clear_holiday_cache()
        assert len(_cached_holidays) == 0


# ──────────────────────────────────────────────────────────────
# DB 미연결 폴백 테스트
# ──────────────────────────────────────────────────────────────

class TestLoadHolidaysFromDb:
    """load_holidays_from_db() — DB 미연결 시 폴백 동작 검증."""

    @pytest.mark.asyncio
    async def test_DB_미연결_폴백(self):
        """db_pool이 None이면 해당 연도의 기본 공휴일을 반환한다."""
        result = await load_holidays_from_db(None, year=2026)
        expected = get_default_holidays(2026)
        assert result == expected

    @pytest.mark.asyncio
    async def test_DB_미연결_연도_미지정_빈집합(self):
        """db_pool이 None이고 year도 없으면 빈 집합을 반환한다."""
        result = await load_holidays_from_db(None)
        assert result == set()
