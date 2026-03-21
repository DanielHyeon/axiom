"""비즈니스 캘린더 서비스 — 공휴일/주말 제외 시계열 전처리.

KAIR의 ontology_data.py 비즈니스 캘린더 로직을 참조하여
시계열 데이터에서 비영업일을 제거하는 서비스.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

import numpy as np
import structlog

from app.services.holiday_store import get_default_holidays, get_holidays_for_range

logger = structlog.get_logger(__name__)


def is_business_day(
    d: date,
    holidays: set[date] | None = None,
    include_saturday: bool = False,
) -> bool:
    """해당 날짜가 영업일인지 판단한다.

    Args:
        d: 판단할 날짜
        holidays: 공휴일 집합 (None이면 한국 기본값 사용)
        include_saturday: True면 토요일도 영업일로 간주
    """
    # holidays가 None이면 해당 연도의 기본 공휴일을 동적으로 로드
    _holidays = holidays if holidays is not None else get_default_holidays(d.year)

    # 공휴일 제외
    if d in _holidays:
        return False

    weekday = d.weekday()  # 0=월 ~ 6=일

    # 일요일은 항상 비영업일
    if weekday == 6:
        return False

    # 토요일은 설정에 따라
    if weekday == 5 and not include_saturday:
        return False

    return True


def filter_business_days(
    dates: Sequence[date | datetime | str],
    values: Sequence[float],
    holidays: set[date] | None = None,
    include_saturday: bool = False,
) -> tuple[list[date], list[float]]:
    """시계열 데이터에서 비영업일을 제거한다.

    Args:
        dates: 날짜 시퀀스 (date, datetime, 또는 ISO 문자열)
        values: 각 날짜에 대응하는 값
        holidays: 공휴일 집합
        include_saturday: 토요일 포함 여부

    Returns:
        (영업일 날짜 리스트, 영업일 값 리스트)

    빈 입력이나 길이가 맞지 않는 경우 빈 리스트를 반환한다.
    """
    # 엣지 케이스: 빈 데이터
    if not dates or not values:
        return [], []

    # 엣지 케이스: 길이 불일치 — 짧은 쪽에 맞춤
    min_len = min(len(dates), len(values))

    filtered_dates: list[date] = []
    filtered_values: list[float] = []

    for i in range(min_len):
        d_raw = dates[i]
        v = values[i]

        # 날짜 파싱
        if isinstance(d_raw, datetime):
            d = d_raw.date()
        elif isinstance(d_raw, str):
            d = date.fromisoformat(d_raw[:10])
        else:
            d = d_raw

        if is_business_day(d, holidays, include_saturday):
            filtered_dates.append(d)
            filtered_values.append(float(v))

    removed = min_len - len(filtered_dates)
    logger.debug(
        "business_day_filter",
        total=min_len,
        kept=len(filtered_dates),
        removed=removed,
    )
    return filtered_dates, filtered_values


def get_business_days_in_range(
    start: date,
    end: date,
    holidays: set[date] | None = None,
    include_saturday: bool = False,
) -> list[date]:
    """주어진 기간 내 영업일 목록을 반환한다.

    start > end 이면 빈 리스트를 반환한다.
    """
    if start > end:
        return []

    result: list[date] = []
    current = start
    while current <= end:
        if is_business_day(current, holidays, include_saturday):
            result.append(current)
        current += timedelta(days=1)
    return result


def aggregate_to_business_days(
    dates: Sequence[date | datetime | str],
    values: Sequence[float],
    method: str = "mean",
    holidays: set[date] | None = None,
) -> tuple[list[date], list[float]]:
    """영업일 데이터만 필터링하고 날짜별로 집계한다.

    비영업일 데이터는 제거된다 (다음 영업일로 이월하지 않음).

    Args:
        dates: 날짜 시퀀스
        values: 값 시퀀스
        method: 집계 방법 — mean, sum, last, first, max, min

    Returns:
        (영업일 날짜 리스트, 집계된 값 리스트)
    """
    # 엣지 케이스: 빈 데이터
    if not dates or not values:
        return [], []

    min_len = min(len(dates), len(values))

    # 날짜별 그룹핑
    day_groups: dict[date, list[float]] = {}
    for i in range(min_len):
        d_raw = dates[i]
        v = values[i]

        if isinstance(d_raw, datetime):
            d = d_raw.date()
        elif isinstance(d_raw, str):
            d = date.fromisoformat(d_raw[:10])
        else:
            d = d_raw
        day_groups.setdefault(d, []).append(float(v))

    # 집계 함수 매핑
    agg_func = {
        "mean": np.mean,
        "sum": np.sum,
        "last": lambda x: x[-1],
        "first": lambda x: x[0],
        "max": np.max,
        "min": np.min,
    }.get(method, np.mean)

    result_dates: list[date] = []
    result_values: list[float] = []
    for d in sorted(day_groups.keys()):
        if is_business_day(d, holidays):
            result_dates.append(d)
            result_values.append(round(float(agg_func(day_groups[d])), 6))

    return result_dates, result_values
