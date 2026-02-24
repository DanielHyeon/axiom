"""
마이닝 서비스 공유 유틸리티 (DDD-P2-04).

여러 분할 서비스에서 공통 사용하는 헬퍼 함수들.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    weight = pos - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def build_case_paths(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """이벤트를 case_id별로 그룹화하고 시간순 정렬."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event["case_id"])].append(event)
    for case_id in grouped:
        grouped[case_id].sort(key=lambda item: item["timestamp"])
    return grouped


def activity_duration_stats(
    case_paths: dict[str, list[dict[str, Any]]],
) -> dict[str, list[float]]:
    """활동별 소요 시간(초) 목록 계산."""
    durations: dict[str, list[float]] = defaultdict(list)
    for items in case_paths.values():
        for idx in range(len(items) - 1):
            current = items[idx]
            nxt = items[idx + 1]
            delta = (parse_ts(nxt["timestamp"]) - parse_ts(current["timestamp"])).total_seconds()
            durations[current["activity"]].append(max(delta, 0.0))
    return durations
