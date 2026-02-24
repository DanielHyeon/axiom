"""
EventLogStatistics — 이벤트 로그 통계 계산 전담 (DDD-P2-04).

EventLogService에서 추출한 통계 계산 책임.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median
from typing import Any

from app.services.event_log_parser import parse_timestamp
from app.services.mining_utils import percentile


class EventLogStatistics:
    """이벤트 로그 통계 계산 전담."""

    @staticmethod
    def compute(events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {
                "total_events": 0,
                "total_cases": 0,
                "unique_activities": 0,
                "date_range": {"start": None, "end": None},
                "ingestion_duration_seconds": 0.0,
            }

        timestamps = [parse_timestamp(item["timestamp"]) for item in events]
        total_events = len(events)
        case_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        activity_counter: Counter[str] = Counter()
        resource_counter: Counter[str] = Counter()
        for event in events:
            case_map[event["case_id"]].append(event)
            activity_counter[event["activity"]] += 1
            if event.get("resource"):
                resource_counter[str(event["resource"])] += 1

        total_cases = len(case_map)
        case_durations: list[float] = []
        variants_counter: Counter[str] = Counter()
        for case_id, items in case_map.items():
            sorted_items = sorted(items, key=lambda x: x["timestamp"])
            first = parse_timestamp(sorted_items[0]["timestamp"])
            last = parse_timestamp(sorted_items[-1]["timestamp"])
            case_durations.append((last - first).total_seconds())
            variant = " > ".join(item["activity"] for item in sorted_items)
            variants_counter[variant] += 1

        case_durations_sorted = sorted(case_durations)
        avg_duration = sum(case_durations) / len(case_durations) if case_durations else 0.0
        unique_activities = len(activity_counter)
        total_variants = len(variants_counter)
        top3 = variants_counter.most_common(3)
        top3_cases = sum(count for _, count in top3)
        top3_coverage = (top3_cases / total_cases) if total_cases else 0.0

        activities = []
        for name, freq in activity_counter.most_common():
            activities.append({
                "name": name,
                "frequency": freq,
                "relative_frequency": round(freq / total_events, 3) if total_events else 0.0,
                "avg_duration_seconds": round(avg_duration / max(unique_activities, 1), 2),
            })

        resources = []
        for name, event_count in resource_counter.most_common(20):
            touched_cases = len({e["case_id"] for e in events if e.get("resource") == name})
            resources.append({"name": name, "event_count": event_count, "case_count": touched_cases})

        overview = {
            "total_events": total_events,
            "total_cases": total_cases,
            "unique_activities": unique_activities,
            "avg_events_per_case": round(total_events / total_cases, 3) if total_cases else 0.0,
            "date_range_start": min(timestamps).isoformat(),
            "date_range_end": max(timestamps).isoformat(),
        }
        case_duration = {
            "avg_seconds": round(avg_duration, 2),
            "median_seconds": round(median(case_durations_sorted), 2) if case_durations_sorted else 0.0,
            "min_seconds": round(min(case_durations_sorted), 2) if case_durations_sorted else 0.0,
            "max_seconds": round(max(case_durations_sorted), 2) if case_durations_sorted else 0.0,
            "p25_seconds": round(percentile(case_durations_sorted, 0.25), 2),
            "p75_seconds": round(percentile(case_durations_sorted, 0.75), 2),
            "p95_seconds": round(percentile(case_durations_sorted, 0.95), 2),
        }
        return {
            "overview": overview,
            "activities": activities,
            "case_duration": case_duration,
            "variants": {"total_variants": total_variants, "top_3_coverage": round(top3_coverage, 3)},
            "resources": resources,
            "date_range": {"start": overview["date_range_start"], "end": overview["date_range_end"]},
            "ingestion_duration_seconds": 0.0,
        }
