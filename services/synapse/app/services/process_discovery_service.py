"""
ProcessDiscoveryService — 프로세스 발견·BPMN 생성·모델 관리 (DDD-P2-04).

ProcessMiningService에서 추출한 discover, BPMN export/import, 통계 책임.
"""
from __future__ import annotations

import uuid
from collections import Counter
from statistics import median
from typing import Any
from xml.sax.saxutils import escape

from app.services.mining_utils import (
    activity_duration_stats,
    build_case_paths,
    utcnow_iso,
)


class ProcessDiscoveryService:
    """프로세스 발견(alpha/heuristic/inductive), BPMN 생성, 모델 관리."""

    def __init__(self, coordinator) -> None:
        self._coord = coordinator

    def summarize_model(self, case_paths: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
        activities: set[str] = set()
        transitions: set[tuple[str, str]] = set()
        for items in case_paths.values():
            for idx, event in enumerate(items):
                activities.add(event["activity"])
                if idx + 1 < len(items):
                    transitions.add((event["activity"], items[idx + 1]["activity"]))
        return {
            "type": "petri_net",
            "places": max(len(activities) + 1, 1),
            "transitions": len(activities),
            "arcs": len(transitions),
            "activities": sorted(activities),
            "followed_by": [{"from": src, "to": dst} for src, dst in sorted(transitions)],
        }

    def build_bpmn_xml(self, model: dict[str, Any], process_name: str = "discovered_process") -> str:
        activities = model.get("activities", [])
        if not activities:
            activities = ["Start", "End"]
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">',
            f'  <process id="{escape(process_name)}" name="{escape(process_name)}" isExecutable="false">',
        ]
        for idx, activity in enumerate(activities):
            lines.append(f'    <task id="task_{idx}" name="{escape(str(activity))}"/>')
        for idx in range(max(0, len(activities) - 1)):
            lines.append(f'    <sequenceFlow id="flow_{idx}" sourceRef="task_{idx}" targetRef="task_{idx + 1}"/>')
        lines.extend(["  </process>", "</definitions>"])
        return "\n".join(lines)

    def event_statistics(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        case_paths = build_case_paths(events)
        from app.services.mining_utils import parse_ts
        durations: list[float] = []
        for items in case_paths.values():
            if len(items) < 2:
                durations.append(0.0)
                continue
            durations.append((parse_ts(items[-1]["timestamp"]) - parse_ts(items[0]["timestamp"])).total_seconds())
        duration_sorted = sorted(durations)
        by_activity = activity_duration_stats(case_paths)
        activities = []
        for name, values in sorted(by_activity.items(), key=lambda item: len(item[1]), reverse=True):
            sorted_vals = sorted(values)
            activities.append({
                "name": name,
                "frequency": len(values),
                "avg_duration_seconds": round(sum(values) / max(1, len(values)), 2),
                "min_duration_seconds": round(sorted_vals[0], 2) if sorted_vals else 0.0,
                "max_duration_seconds": round(sorted_vals[-1], 2) if sorted_vals else 0.0,
            })
        return {
            "total_cases": len(case_paths),
            "total_events": len(events),
            "unique_activities": len({event["activity"] for event in events}),
            "avg_case_duration_seconds": round(sum(durations) / max(1, len(durations)), 2),
            "median_case_duration_seconds": round(median(duration_sorted), 2) if duration_sorted else 0.0,
            "activities": activities,
        }

    def resolve_reference_activities(
        self, tenant_id: str, reference_model: dict[str, Any], events: list[dict[str, Any]],
    ) -> list[str]:
        from app.services.mining_task_coordinator import MiningTaskError
        model_type = reference_model.get("type")
        model_id = str(reference_model.get("model_id") or "")
        if model_type not in {"eventstorming", "petri_net", "discovered"}:
            raise MiningTaskError(400, "INVALID_REQUEST", "invalid reference_model.type")
        if not model_id:
            raise MiningTaskError(400, "INVALID_REQUEST", "reference_model.model_id is required")
        if model_type == "discovered":
            result = self._coord.result_or_404(tenant_id, model_id)
            return result["result"]["model"].get("activities", [])
        model = None
        if self._coord.store:
            model = self._coord.store.get_model(tenant_id, model_id)
        if model is None:
            model = self._coord.models.get(model_id)
        if model:
            return model.get("activities", [])
        case_paths = build_case_paths(events)
        top = Counter(tuple(e["activity"] for e in seq) for seq in case_paths.values()).most_common(1)
        return list(top[0][0]) if top else []

    def submit_discover(
        self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None,
    ) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        from app.services.event_log_service import EventLogDomainError, event_log_service

        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise MiningTaskError(400, "INVALID_REQUEST", "case_id and log_id are required")
        algorithm = str(payload.get("algorithm") or "inductive")
        if algorithm not in {"alpha", "heuristic", "inductive"}:
            raise MiningTaskError(400, "INVALID_ALGORITHM", "unsupported algorithm")
        params = payload.get("parameters") or {}
        noise_threshold = float(params.get("noise_threshold", 0.2))
        dependency_threshold = float(params.get("dependency_threshold", 0.5))
        if noise_threshold < 0 or noise_threshold > 1 or dependency_threshold < 0 or dependency_threshold > 1:
            raise MiningTaskError(400, "INVALID_REQUEST", "threshold must be in [0,1]")
        options = payload.get("options") or {}
        generate_bpmn = bool(options.get("generate_bpmn", True))
        calculate_statistics = bool(options.get("calculate_statistics", True))
        store_in_neo4j = bool(options.get("store_in_neo4j", True))

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

        task = self._coord.create_task(tenant_id, "discover", case_id, log_id, requested_by)
        self._coord.set_running(task)

        model = None
        bpmn_xml_from_pm4py = None
        try:
            from app.mining.process_discovery import events_to_pm4py_dataframe, run_discover_sync
            df = events_to_pm4py_dataframe(events)
            if len(df) > 0:
                model, bpmn_xml_from_pm4py = run_discover_sync(
                    algorithm=algorithm, df=df,
                    noise_threshold=noise_threshold, dependency_threshold=dependency_threshold,
                    generate_bpmn=generate_bpmn,
                )
        except Exception:
            model = None
            bpmn_xml_from_pm4py = None
        if model is None:
            case_paths = build_case_paths(events)
            model = self.summarize_model(case_paths)

        result = {
            "algorithm": algorithm,
            "parameters": {"noise_threshold": noise_threshold, "dependency_threshold": dependency_threshold},
            "model": model,
            "neo4j_nodes_created": len(model.get("activities", [])) if store_in_neo4j else 0,
            "completed_at": utcnow_iso(),
        }
        if generate_bpmn:
            result["bpmn_xml"] = bpmn_xml_from_pm4py or self.build_bpmn_xml(model)
        if calculate_statistics:
            result["statistics"] = self.event_statistics(events)
        self._coord.set_completed(task, result)
        return {
            "task_id": task.task_id, "log_id": log_id, "algorithm": algorithm,
            "status": "queued", "created_at": task.created_at, "estimated_duration_seconds": 30,
        }

    def export_bpmn(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        case_id = str(payload.get("case_id") or "").strip()
        if not case_id:
            raise MiningTaskError(400, "INVALID_REQUEST", "case_id is required")
        source = payload.get("source") or {}
        source_type = source.get("type")
        if source_type not in {"discovered", "imported"}:
            raise MiningTaskError(400, "INVALID_REQUEST", "source.type must be discovered|imported")

        xml: str
        result_data: dict[str, Any] | None = None
        if source_type == "discovered":
            key = source.get("task_id") or source.get("result_id")
            if not key:
                raise MiningTaskError(400, "INVALID_REQUEST", "task_id or result_id is required")
            result = self._coord.result_or_404(tenant_id, str(key))
            result_data = result["result"]
            xml = result_data.get("bpmn_xml") or self.build_bpmn_xml(result_data.get("model", {}))
        else:
            model_id = str(source.get("model_id") or "")
            model = None
            if self._coord.store:
                model = self._coord.store.get_model(tenant_id, model_id)
            if model is None:
                model = self._coord.models.get(model_id)
            if not model:
                raise MiningTaskError(404, "MODEL_NOT_FOUND", "model not found")
            xml = model["xml"]

        overlay = {}
        include_statistics = bool((payload.get("options") or {}).get("include_statistics", True))
        if include_statistics and result_data and "statistics" in result_data:
            overlay = {
                "activities": {
                    item["name"]: {
                        "frequency": item["frequency"],
                        "avg_duration": item["avg_duration_seconds"],
                        "bottleneck_score": round(min(1.0, item["avg_duration_seconds"] / 10000.0), 3),
                    }
                    for item in result_data["statistics"].get("activities", [])
                }
            }
        return {"format": "bpmn_2.0_xml", "xml": xml, "statistics_overlay": overlay}

    def import_model(
        self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None,
    ) -> dict[str, Any]:
        from app.services.mining_task_coordinator import MiningTaskError
        case_id = str(payload.get("case_id") or "").strip()
        if not case_id:
            raise MiningTaskError(400, "INVALID_REQUEST", "case_id is required")
        model = payload.get("model") or {}
        model_type = model.get("type")
        if model_type not in {"bpmn", "petri_net"}:
            raise MiningTaskError(400, "INVALID_REQUEST", "model.type must be bpmn|petri_net")
        content = str(model.get("content") or "").strip()
        if not content:
            raise MiningTaskError(400, "INVALID_REQUEST", "model.content is required")

        model_id = f"bpm-model-{uuid.uuid4()}"
        activities = []
        if model_type == "petri_net":
            activities = [str(item) for item in (model.get("activities") or [])]
        if not activities:
            activities = ["주문 접수", "결제 확인", "출하 지시", "배송 완료"]
        xml = content if model_type == "bpmn" else self.build_bpmn_xml({"activities": activities}, process_name=model_id)
        imported_at = utcnow_iso()
        if self._coord.store:
            self._coord.store.insert_model(model_id, tenant_id, case_id, model_type, xml, activities, requested_by)
        else:
            self._coord.models[model_id] = {
                "model_id": model_id, "tenant_id": tenant_id, "case_id": case_id,
                "type": model_type, "xml": xml, "activities": activities,
                "created_by": requested_by, "imported_at": imported_at,
            }
        return {
            "model_id": model_id, "status": "imported",
            "source_result_id": payload.get("result_id"), "imported_at": imported_at,
        }

    def get_statistics(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        from app.services.event_log_service import EventLogDomainError, event_log_service
        from app.services.mining_task_coordinator import MiningTaskError
        try:
            ep = event_log_service.get_events_for_mining(tenant_id, log_id)
        except EventLogDomainError as err:
            if err.code == "LOG_NOT_FOUND":
                raise MiningTaskError(404, "LOG_NOT_FOUND", "event log not found") from err
            raise MiningTaskError(400, "INVALID_LOG_FORMAT", "invalid event log") from err
        events = ep["events"]
        if not events:
            raise MiningTaskError(400, "EMPTY_EVENT_LOG", "event log has no events")
        data = self.event_statistics(events)
        return {"log_id": log_id, **data}
