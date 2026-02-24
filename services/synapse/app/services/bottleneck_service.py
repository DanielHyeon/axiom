"""
BottleneckService — 병목 분석 (DDD-P2-04).

ProcessMiningService에서 추출한 bottleneck 분석 책임.
"""
from __future__ import annotations

from statistics import median
from typing import Any

from app.services.mining_utils import (
    activity_duration_stats,
    build_case_paths,
    parse_ts,
    utcnow_iso,
)


class BottleneckService:
    """프로세스 병목 지점 분석 전담."""

    def __init__(self, coordinator) -> None:
        self._coord = coordinator

    def analyze(
        self, events: list[dict[str, Any]], sort_by: str, _sla_source: str,
    ) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        if sort_by not in {"bottleneck_score_desc", "avg_duration_desc", "violation_rate_desc"}:
            raise MiningTaskError(400, "INVALID_REQUEST", "invalid sort_by")

        case_paths = build_case_paths(events)
        durations_by_activity = activity_duration_stats(case_paths)
        if not durations_by_activity:
            return {
                "bottlenecks": [],
                "overall_process": {
                    "avg_duration_seconds": 0.0, "median_duration_seconds": 0.0,
                    "total_sla_violations": 0, "overall_compliance_rate": 1.0,
                },
            }

        max_avg = max(sum(vals) / max(1, len(vals)) for vals in durations_by_activity.values())
        rows = []
        total_violations = 0
        for activity, values in durations_by_activity.items():
            sorted_vals = sorted(values)
            avg_seconds = sum(values) / max(1, len(values))
            med_seconds = median(sorted_vals)
            p95_index = int((len(sorted_vals) - 1) * 0.95)
            p95_seconds = sorted_vals[p95_index]
            sla_threshold = max(med_seconds * 1.5, avg_seconds)
            violations = sum(1 for val in values if val > sla_threshold)
            violation_rate = violations / max(1, len(values))
            total_violations += violations
            duration_factor = avg_seconds / max(1.0, max_avg)
            score = round(min(1.0, 0.7 * duration_factor + 0.3 * violation_rate), 3)
            rows.append({
                "activity": activity,
                "bottleneck_score": score,
                "duration_stats": {
                    "avg_seconds": round(avg_seconds, 2),
                    "median_seconds": round(med_seconds, 2),
                    "p95_seconds": round(p95_seconds, 2),
                    "min_seconds": round(sorted_vals[0], 2),
                    "max_seconds": round(sorted_vals[-1], 2),
                },
                "waiting_time": {
                    "avg_seconds": round(avg_seconds * 0.5, 2),
                    "median_seconds": round(med_seconds * 0.5, 2),
                },
                "sla": {
                    "threshold_seconds": round(sla_threshold, 2),
                    "violation_count": violations,
                    "total_cases": len(values),
                    "violation_rate": round(violation_rate, 3),
                },
                "trend": {
                    "direction": "stable" if violation_rate < 0.2 else "worsening",
                    "change_rate_per_month": round(violation_rate / 6.0, 3),
                    "description": "안정적" if violation_rate < 0.2 else "최근 SLA 위반률 증가 추세",
                },
            })

        if sort_by == "avg_duration_desc":
            rows.sort(key=lambda item: item["duration_stats"]["avg_seconds"], reverse=True)
        elif sort_by == "violation_rate_desc":
            rows.sort(key=lambda item: item["sla"]["violation_rate"], reverse=True)
        else:
            rows.sort(key=lambda item: item["bottleneck_score"], reverse=True)

        for idx, item in enumerate(rows, start=1):
            item["bottleneck_rank"] = idx

        process_durations = []
        for path in case_paths.values():
            if len(path) < 2:
                process_durations.append(0.0)
                continue
            process_durations.append(
                (parse_ts(path[-1]["timestamp"]) - parse_ts(path[0]["timestamp"])).total_seconds()
            )
        process_durations.sort()
        compliance_rate = 1.0 - (total_violations / max(1, sum(len(v) for v in durations_by_activity.values())))
        timestamps = sorted(parse_ts(event["timestamp"]) for event in events)
        return {
            "analysis_period": {"start": timestamps[0].isoformat(), "end": timestamps[-1].isoformat()},
            "bottlenecks": rows,
            "overall_process": {
                "avg_duration_seconds": round(sum(process_durations) / max(1, len(process_durations)), 2),
                "median_duration_seconds": round(median(process_durations), 2) if process_durations else 0.0,
                "total_sla_violations": total_violations,
                "overall_compliance_rate": round(max(0.0, compliance_rate), 3),
            },
        }

    def submit_bottlenecks(
        self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None,
    ) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        from app.services.event_log_service import EventLogDomainError, event_log_service

        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise MiningTaskError(400, "INVALID_REQUEST", "case_id and log_id are required")
        sort_by = str((payload.get("options") or {}).get("sort_by", "bottleneck_score_desc"))
        sla_source = str((payload.get("options") or {}).get("sla_source", "eventstorming"))

        self._coord.require_rate_limit()
        try:
            ep = event_log_service.get_events_for_mining(tenant_id, log_id)
        except EventLogDomainError as err:
            if err.code == "LOG_NOT_FOUND":
                raise MiningTaskError(404, "LOG_NOT_FOUND", "event log not found") from err
            raise MiningTaskError(400, "INVALID_LOG_FORMAT", "invalid event log") from err
        events = ep["events"]
        if not events:
            raise MiningTaskError(400, "EMPTY_EVENT_LOG", "event log has no events")

        task = self._coord.create_task(tenant_id, "bottlenecks", case_id, log_id, requested_by)
        self._coord.set_running(task)
        result = self.analyze(events, sort_by=sort_by, _sla_source=sla_source)
        result["completed_at"] = utcnow_iso()
        self._coord.set_completed(task, result)
        return {"task_id": task.task_id, "status": "queued", "created_at": task.created_at}

    def get_bottlenecks(
        self, tenant_id: str, case_id: str, log_id: str, sort_by: str, sla_source: str,
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
        data = self.analyze(events, sort_by=sort_by, _sla_source=sla_source)
        data["log_id"] = log_id
        return data
