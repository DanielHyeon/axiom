"""
ConformanceService — 적합도 검증 (DDD-P2-04).

ProcessMiningService에서 추출한 conformance 책임.
"""
from __future__ import annotations

from typing import Any

from app.mining.conformance_checker import check_conformance
from app.services.mining_utils import utcnow_iso


class ConformanceService:
    """프로세스 모델 적합도 검증 전담."""

    def __init__(self, coordinator, discovery) -> None:
        self._coord = coordinator
        self._discovery = discovery

    def submit_conformance(
        self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None,
    ) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        from app.services.event_log_service import EventLogDomainError, event_log_service

        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise MiningTaskError(400, "INVALID_REQUEST", "case_id and log_id are required")
        reference_model = payload.get("reference_model") or {}
        options = payload.get("options") or {}
        include_case_diagnostics = bool(options.get("include_case_diagnostics", True))
        max_diag = int(options.get("max_diagnostics_cases", 100))
        if max_diag < 1 or max_diag > 1000:
            raise MiningTaskError(400, "INVALID_REQUEST", "max_diagnostics_cases must be in [1,1000]")

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

        task = self._coord.create_task(tenant_id, "conformance", case_id, log_id, requested_by)
        self._coord.set_running(task)

        designed = self._discovery.resolve_reference_activities(tenant_id, reference_model, events)
        checker = check_conformance(
            events=events,
            designed_activities=designed,
            include_case_diagnostics=include_case_diagnostics,
            max_diagnostics_cases=max_diag,
        )
        result = {
            "reference_model": {
                "type": reference_model.get("type"),
                "model_id": reference_model.get("model_id"),
                "name": f"reference-{reference_model.get('type', 'model')}",
            },
            "metrics": {
                "fitness": checker.fitness,
                "precision": checker.precision,
                "generalization": checker.generalization,
                "simplicity": checker.simplicity,
            },
            "summary": {
                "total_cases": checker.total_cases,
                "conformant_cases": checker.conformant_cases,
                "non_conformant_cases": max(0, checker.total_cases - checker.conformant_cases),
                "conformance_rate": checker.fitness,
            },
            "case_diagnostics": [item.model_dump() for item in checker.case_diagnostics]
            if include_case_diagnostics
            else [],
            "deviation_statistics": checker.deviation_statistics,
            "completed_at": utcnow_iso(),
        }
        self._coord.set_completed(task, result)
        return {"task_id": task.task_id, "status": "queued", "created_at": task.created_at}
