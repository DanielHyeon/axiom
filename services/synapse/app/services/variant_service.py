"""
VariantService — 프로세스 변형 분석 (DDD-P2-04).

ProcessMiningService에서 추출한 variant 분석 책임.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from statistics import median
from typing import Any

from app.services.mining_utils import build_case_paths, parse_ts


class VariantService:
    """프로세스 경로 변형(variant) 분석 전담."""

    def analyze(
        self,
        case_paths: dict[str, list[dict[str, Any]]],
        sort_by: str,
        limit: int,
        min_cases: int,
    ) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        if sort_by not in {"frequency_desc", "frequency_asc", "duration_desc", "duration_asc"}:
            raise MiningTaskError(400, "INVALID_REQUEST", "invalid sort_by")

        bucket: dict[tuple[str, ...], list[float]] = defaultdict(list)
        for items in case_paths.values():
            seq = tuple(event["activity"] for event in items)
            if len(items) >= 2:
                duration = (parse_ts(items[-1]["timestamp"]) - parse_ts(items[0]["timestamp"])).total_seconds()
            else:
                duration = 0.0
            bucket[seq].append(max(duration, 0.0))

        total_cases = len(case_paths)
        rows = []
        rank = 1
        for sequence, durations in bucket.items():
            case_count = len(durations)
            if case_count < min_cases:
                continue
            rows.append({
                "variant_id": f"var-{uuid.uuid5(uuid.NAMESPACE_URL, '>'.join(sequence))}",
                "rank": rank,
                "activity_sequence": list(sequence),
                "case_count": case_count,
                "case_percentage": round((case_count / max(1, total_cases)) * 100.0, 2),
                "avg_duration_seconds": round(sum(durations) / max(1, len(durations)), 2),
                "median_duration_seconds": round(median(sorted(durations)), 2),
                "is_designed_path": rank == 1,
            })
            rank += 1

        if sort_by == "frequency_desc":
            rows.sort(key=lambda item: item["case_count"], reverse=True)
        elif sort_by == "frequency_asc":
            rows.sort(key=lambda item: item["case_count"])
        elif sort_by == "duration_desc":
            rows.sort(key=lambda item: item["avg_duration_seconds"], reverse=True)
        else:
            rows.sort(key=lambda item: item["avg_duration_seconds"])

        for idx, item in enumerate(rows, start=1):
            item["rank"] = idx

        safe_limit = max(1, min(limit, 200))
        return {
            "total_variants": len(rows),
            "total_cases": total_cases,
            "variants": rows[:safe_limit],
        }

    def list_variants(
        self,
        tenant_id: str,
        case_id: str,
        log_id: str,
        sort_by: str,
        limit: int,
        min_cases: int,
    ) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        from app.services.event_log_service import EventLogDomainError, event_log_service

        if not case_id or not log_id:
            raise MiningTaskError(400, "INVALID_REQUEST", "case_id and log_id are required")
        try:
            ep = event_log_service.get_events_for_mining(tenant_id, log_id)
        except EventLogDomainError as err:
            if err.code == "LOG_NOT_FOUND":
                raise MiningTaskError(404, "LOG_NOT_FOUND", "event log not found") from err
            raise MiningTaskError(400, "INVALID_LOG_FORMAT", "invalid event log") from err
        event_case_id = ep["case_id"]
        events = ep["events"]
        if case_id != event_case_id:
            raise MiningTaskError(404, "LOG_NOT_FOUND", "log does not belong to case_id")
        case_paths = build_case_paths(events)
        data = self.analyze(case_paths, sort_by=sort_by, limit=limit, min_cases=max(1, min_cases))
        data["log_id"] = log_id
        return data
