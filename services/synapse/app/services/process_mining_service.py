"""
ProcessMiningService — Facade (DDD-P2-04).

기존 인터페이스를 유지하며 내부를 전문 서비스에 위임한다.
API Router는 변경 없이 이 Facade를 계속 사용한다.

위임 대상:
- MiningTaskCoordinator: 태스크 라이프사이클
- ProcessDiscoveryService: 프로세스 발견·BPMN·모델 관리
- ConformanceService: 적합도 검증
- BottleneckService: 병목 분석
- VariantService: 변형 분석
"""
from __future__ import annotations

from collections import Counter
from statistics import median
from typing import Any

from app.services.bottleneck_service import BottleneckService
from app.services.conformance_service import ConformanceService
from app.services.mining_task_coordinator import MiningTaskCoordinator, MiningTaskError
from app.services.mining_utils import (
    activity_duration_stats,
    build_case_paths,
    parse_ts,
    percentile,
    utcnow_iso,
)
from app.services.process_discovery_service import ProcessDiscoveryService
from app.services.variant_service import VariantService


# Backward compat: re-export so existing imports still work
ProcessMiningDomainError = MiningTaskError


class ProcessMiningService:
    """기존 인터페이스 유지하는 Facade. 내부를 전문 서비스에 위임."""

    def __init__(self) -> None:
        self._coord = MiningTaskCoordinator()
        self._discovery = ProcessDiscoveryService(self._coord)
        self._conformance = ConformanceService(self._coord, self._discovery)
        self._bottleneck = BottleneckService(self._coord)
        self._variant = VariantService()

    def clear(self) -> None:
        self._coord.clear()

    # ──── Discovery delegation ──── #

    def submit_discover(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        return self._discovery.submit_discover(tenant_id, payload, requested_by)

    def export_bpmn(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._discovery.export_bpmn(tenant_id, payload)

    def import_model(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        return self._discovery.import_model(tenant_id, payload, requested_by)

    def get_statistics(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        return self._discovery.get_statistics(tenant_id, log_id)

    # ──── Conformance delegation ──── #

    def submit_conformance(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        return self._conformance.submit_conformance(tenant_id, payload, requested_by)

    # ──── Bottleneck delegation ──── #

    def submit_bottlenecks(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        return self._bottleneck.submit_bottlenecks(tenant_id, payload, requested_by)

    def get_bottlenecks(self, tenant_id: str, case_id: str, log_id: str, sort_by: str, sla_source: str) -> dict[str, Any]:
        return self._bottleneck.get_bottlenecks(tenant_id, case_id, log_id, sort_by, sla_source)

    # ──── Performance (uses bottleneck internally) ──── #

    def submit_performance(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        from app.services.event_log_service import EventLogDomainError, event_log_service

        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id and log_id are required")

        self._coord.require_rate_limit()
        try:
            ep = event_log_service.get_events_for_mining(tenant_id, log_id)
        except EventLogDomainError as err:
            if err.code == "LOG_NOT_FOUND":
                raise ProcessMiningDomainError(404, "LOG_NOT_FOUND", "event log not found") from err
            raise ProcessMiningDomainError(400, "INVALID_LOG_FORMAT", "invalid event log") from err
        events = ep["events"]
        if not events:
            raise ProcessMiningDomainError(400, "EMPTY_EVENT_LOG", "event log has no events")

        include_bottlenecks = bool((payload.get("options") or {}).get("include_bottlenecks", True))
        task = self._coord.create_task(tenant_id, "performance", case_id, log_id, requested_by)
        self._coord.set_running(task)
        result = self._performance(events, include_bottlenecks=include_bottlenecks)
        result["completed_at"] = utcnow_iso()
        self._coord.set_completed(task, result)
        return {"task_id": task.task_id, "status": "queued", "created_at": task.created_at}

    def _performance(self, events: list[dict[str, Any]], include_bottlenecks: bool) -> dict[str, Any]:
        case_paths = build_case_paths(events)
        case_durations: list[float] = []
        throughput_by_day: Counter[str] = Counter()
        timestamps = []
        for items in case_paths.values():
            first_ts = parse_ts(items[0]["timestamp"])
            last_ts = parse_ts(items[-1]["timestamp"])
            timestamps.extend([first_ts, last_ts])
            throughput_by_day[last_ts.date().isoformat()] += 1
            case_durations.append(max((last_ts - first_ts).total_seconds(), 0.0))
        sorted_case_durations = sorted(case_durations)
        by_activity = activity_duration_stats(case_paths)
        activity_rows = []
        for name, values in sorted(by_activity.items(), key=lambda item: len(item[1]), reverse=True):
            sorted_vals = sorted(values)
            activity_rows.append({
                "activity": name,
                "frequency": len(values),
                "avg_duration_seconds": round(sum(values) / max(1, len(values)), 2),
                "median_duration_seconds": round(median(sorted_vals), 2) if sorted_vals else 0.0,
                "p95_duration_seconds": round(percentile(sorted_vals, 0.95), 2),
            })
        throughput_values = list(throughput_by_day.values())
        bottlenecks = []
        if include_bottlenecks:
            bottlenecks = self._bottleneck.analyze(
                events, sort_by="bottleneck_score_desc", _sla_source="eventstorming",
            ).get("bottlenecks", [])[:5]
        return {
            "overall_performance": {
                "total_cases": len(case_paths),
                "avg_case_duration_seconds": round(sum(case_durations) / max(1, len(case_durations)), 2),
                "median_case_duration_seconds": round(median(sorted_case_durations), 2) if sorted_case_durations else 0.0,
                "p95_case_duration_seconds": round(percentile(sorted_case_durations, 0.95), 2),
            },
            "throughput": {
                "daily_avg_cases": round(sum(throughput_values) / max(1, len(throughput_values)), 3) if throughput_values else 0.0,
                "daily_peak_cases": max(throughput_values) if throughput_values else 0,
            },
            "time_window": {
                "start": min(timestamps).isoformat() if timestamps else None,
                "end": max(timestamps).isoformat() if timestamps else None,
            },
            "activity_performance": activity_rows,
            "bottlenecks": bottlenecks,
        }

    # ──── Variant delegation ──── #

    def list_variants(self, tenant_id: str, case_id: str, log_id: str, sort_by: str, limit: int, min_cases: int) -> dict[str, Any]:
        return self._variant.list_variants(tenant_id, case_id, log_id, sort_by, limit, min_cases)

    # ──── Task lifecycle delegation ──── #

    def get_task(self, tenant_id: str, task_id: str) -> dict[str, Any]:
        return self._coord.get_task_dict(tenant_id, task_id)

    def get_task_result(self, tenant_id: str, task_id: str) -> dict[str, Any]:
        return self._coord.get_task_result_dict(tenant_id, task_id)

    def get_result(self, tenant_id: str, result_or_task_id: str) -> dict[str, Any]:
        return self._coord.get_result_dict(tenant_id, result_or_task_id)


process_mining_service = ProcessMiningService()
