"""공휴일 저장소 — PostgreSQL 기반 동적 공휴일 관리.

연도별/국가별 공휴일을 DB에서 로드하여 비즈니스 캘린더에서 사용한다.
기본값으로 대한민국 2024-2027 공휴일을 시드한다.
"""
from __future__ import annotations

from datetime import date
from typing import Sequence

import structlog

logger = structlog.get_logger(__name__)

# 기본 공휴일 시드 데이터 (대한민국 2024-2027)
_KR_HOLIDAYS: dict[int, set[date]] = {
    2024: {
        date(2024, 1, 1), date(2024, 2, 9), date(2024, 2, 10), date(2024, 2, 11), date(2024, 2, 12),
        date(2024, 3, 1), date(2024, 5, 5), date(2024, 5, 6), date(2024, 5, 15),
        date(2024, 6, 6), date(2024, 8, 15), date(2024, 9, 16), date(2024, 9, 17), date(2024, 9, 18),
        date(2024, 10, 3), date(2024, 10, 9), date(2024, 12, 25),
    },
    2025: {
        date(2025, 1, 1), date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30),
        date(2025, 3, 1), date(2025, 5, 5), date(2025, 5, 6),
        date(2025, 6, 6), date(2025, 8, 15), date(2025, 10, 3),
        date(2025, 10, 5), date(2025, 10, 6), date(2025, 10, 7),
        date(2025, 10, 9), date(2025, 12, 25),
    },
    2026: {
        date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
        date(2026, 3, 1), date(2026, 5, 5), date(2026, 5, 24),
        date(2026, 6, 6), date(2026, 8, 15), date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26),
        date(2026, 10, 3), date(2026, 10, 9), date(2026, 12, 25),
    },
    2027: {
        date(2027, 1, 1), date(2027, 2, 5), date(2027, 2, 6), date(2027, 2, 7), date(2027, 2, 8),
        date(2027, 3, 1), date(2027, 5, 5), date(2027, 5, 13),
        date(2027, 6, 6), date(2027, 8, 15), date(2027, 9, 14), date(2027, 9, 15), date(2027, 9, 16),
        date(2027, 10, 3), date(2027, 10, 9), date(2027, 12, 25),
    },
}

# 메모리 캐시 — DB에서 로드한 후 캐시
_cached_holidays: dict[tuple[str, int], set[date]] = {}


def get_default_holidays(year: int) -> set[date]:
    """기본 내장 공휴일을 반환한다. DB 미연결 시 폴백으로 사용."""
    return _KR_HOLIDAYS.get(year, set())


def get_holidays_for_range(start: date, end: date, country: str = "KR") -> set[date]:
    """날짜 범위에 해당하는 공휴일 전체를 반환한다.

    여러 연도에 걸치는 경우 각 연도의 공휴일을 합산한다.
    """
    holidays: set[date] = set()
    for year in range(start.year, end.year + 1):
        cache_key = (country, year)
        if cache_key in _cached_holidays:
            holidays |= _cached_holidays[cache_key]
        else:
            # 기본 데이터 사용 (추후 DB 로드로 대체)
            year_holidays = get_default_holidays(year)
            _cached_holidays[cache_key] = year_holidays
            holidays |= year_holidays

    # 범위 필터링
    return {d for d in holidays if start <= d <= end}


async def load_holidays_from_db(db_pool, country: str = "KR", year: int | None = None) -> set[date]:
    """PostgreSQL에서 공휴일을 로드한다.

    테이블: vision.holidays (country, holiday_date, name, year)
    테이블이 없으면 기본 데이터로 폴백.
    """
    global _cached_holidays

    if db_pool is None:
        logger.debug("holiday_db_unavailable_using_defaults")
        if year:
            return get_default_holidays(year)
        return set()

    try:
        async with db_pool.acquire() as conn:
            if year:
                rows = await conn.fetch(
                    "SELECT holiday_date FROM vision.holidays WHERE country = $1 AND year = $2",
                    country, year,
                )
            else:
                rows = await conn.fetch(
                    "SELECT holiday_date FROM vision.holidays WHERE country = $1",
                    country,
                )

            holidays = {row["holiday_date"] for row in rows}

            # 캐시 업데이트
            if year:
                _cached_holidays[(country, year)] = holidays
            else:
                # 연도별로 분류하여 캐시
                by_year: dict[int, set[date]] = {}
                for d in holidays:
                    by_year.setdefault(d.year, set()).add(d)
                for y, hs in by_year.items():
                    _cached_holidays[(country, y)] = hs

            logger.info("holidays_loaded_from_db", country=country, year=year, count=len(holidays))
            return holidays

    except Exception as e:
        logger.warning("holiday_db_load_failed_using_defaults", error=str(e))
        if year:
            return get_default_holidays(year)
        return set()


def clear_holiday_cache() -> None:
    """캐시를 초기화한다 (테스트/리프레시용)."""
    _cached_holidays.clear()
