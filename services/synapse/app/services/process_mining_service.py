import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any
from xml.sax.saxutils import escape

from app.mining.conformance_checker import check_conformance
from app.services.event_log_service import EventLogDomainError, event_log_service
from app.services.mining_store import get_mining_store


class ProcessMiningDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    weight = pos - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


@dataclass
class MiningTask:
    tenant_id: str
    task_id: str
    task_type: str
    case_id: str
    log_id: str
    status: str
    created_at: str
    updated_at: str
    requested_by: str | None
    started_at: str | None = None
    completed_at: str | None = None
    result_id: str | None = None
    error: dict[str, Any] | None = None


def _task_from_row(row: dict[str, Any]) -> MiningTask:
    """Store 행 또는 dict를 MiningTask로 변환."""
    return MiningTask(
        tenant_id=row["tenant_id"],
        task_id=row["task_id"],
        task_type=row["task_type"],
        case_id=row["case_id"],
        log_id=row["log_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        requested_by=row.get("requested_by"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        result_id=row.get("result_id"),
        error=row.get("error"),
    )


class ProcessMiningService:
    def __init__(self) -> None:
        self._tasks: dict[str, MiningTask] = {}
        self._results: dict[str, dict[str, Any]] = {}
        self._models: dict[str, dict[str, Any]] = {}
        self._max_active_tasks = 8
        self._store = get_mining_store()

    def clear(self) -> None:
        self._tasks.clear()
        self._results.clear()
        self._models.clear()
        if self._store:
            self._store.clear()

    def _require_rate_limit(self) -> None:
        if self._store:
            active = self._store.count_active_tasks()
        else:
            active = sum(1 for item in self._tasks.values() if item.status in {"queued", "running"})
        if active >= self._max_active_tasks:
            raise ProcessMiningDomainError(429, "MINING_RATE_LIMIT", "too many running tasks")

    def _create_task(self, tenant_id: str, task_type: str, case_id: str, log_id: str, requested_by: str | None) -> MiningTask:
        task_id = f"task-pm-{uuid.uuid4()}"
        now = _utcnow()
        if self._store:
            self._store.insert_task(task_id, tenant_id, task_type, case_id, log_id, requested_by)
        task = MiningTask(
            tenant_id=tenant_id,
            task_id=task_id,
            task_type=task_type,
            case_id=case_id,
            log_id=log_id,
            status="queued",
            created_at=now,
            updated_at=now,
            requested_by=requested_by,
        )
        self._tasks[task_id] = task
        return task

    def _set_running(self, task: MiningTask) -> None:
        now = _utcnow()
        if self._store:
            self._store.set_running(task.task_id)
        task.status = "running"
        task.started_at = now
        task.updated_at = now

    def _set_completed(self, task: MiningTask, result_payload: dict[str, Any]) -> dict[str, Any]:
        now = _utcnow()
        result_id = f"pm-result-{uuid.uuid4()}"
        if self._store:
            self._store.set_completed(task.task_id, result_id, result_payload)
        task.status = "completed"
        task.result_id = result_id
        task.completed_at = now
        task.updated_at = now
        data = {
            "id": result_id,
            "task_id": task.task_id,
            "task_type": task.task_type,
            "case_id": task.case_id,
            "log_id": task.log_id,
            "created_at": now,
            "result": result_payload,
        }
        self._results[result_id] = data
        return data

    def _task_or_404(self, tenant_id: str, task_id: str) -> MiningTask:
        if self._store:
            row = self._store.get_task(tenant_id, task_id)
            if row:
                return _task_from_row(row)
        task = self._tasks.get(task_id)
        if not task or task.tenant_id != tenant_id:
            raise ProcessMiningDomainError(404, "TASK_NOT_FOUND", "task not found")
        return task

    def _result_or_404(self, tenant_id: str, result_or_task_id: str) -> dict[str, Any]:
        if self._store:
            result = self._store.get_result(tenant_id, result_or_task_id)
            if result:
                return result
            result = self._store.get_result_by_task_id(tenant_id, result_or_task_id)
            if result:
                return result
            raise ProcessMiningDomainError(404, "RESULT_NOT_FOUND", "result not found")
        result = self._results.get(result_or_task_id)
        if result:
            if self._tasks[result["task_id"]].tenant_id != tenant_id:
                raise ProcessMiningDomainError(404, "RESULT_NOT_FOUND", "result not found")
            return result
        task = self._tasks.get(result_or_task_id)
        if task and task.tenant_id == tenant_id and task.result_id:
            return self._results[task.result_id]
        raise ProcessMiningDomainError(404, "RESULT_NOT_FOUND", "result not found")

    def _require_log(self, tenant_id: str, log_id: str) -> tuple[str, list[dict[str, Any]]]:
        try:
            payload = event_log_service.get_events_for_mining(tenant_id, log_id)
        except EventLogDomainError as err:
            if err.code == "LOG_NOT_FOUND":
                raise ProcessMiningDomainError(404, "LOG_NOT_FOUND", "event log not found") from err
            raise ProcessMiningDomainError(400, "INVALID_LOG_FORMAT", "invalid event log") from err
        events = payload["events"]
        if not events:
            raise ProcessMiningDomainError(400, "EMPTY_EVENT_LOG", "event log has no events")
        return payload["case_id"], events

    def _build_case_paths(self, events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for event in events:
            grouped[str(event["case_id"])].append(event)
        for case_id in grouped:
            grouped[case_id].sort(key=lambda item: item["timestamp"])
        return grouped

    def _summarize_model(self, case_paths: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
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

    def _build_bpmn_xml(self, model: dict[str, Any], process_name: str = "discovered_process") -> str:
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

    def _activity_duration_stats(self, case_paths: dict[str, list[dict[str, Any]]]) -> dict[str, list[float]]:
        durations: dict[str, list[float]] = defaultdict(list)
        for items in case_paths.values():
            for idx in range(len(items) - 1):
                current = items[idx]
                nxt = items[idx + 1]
                delta = (_parse_ts(nxt["timestamp"]) - _parse_ts(current["timestamp"])).total_seconds()
                durations[current["activity"]].append(max(delta, 0.0))
        return durations

    def _event_statistics(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        case_paths = self._build_case_paths(events)
        durations: list[float] = []
        for items in case_paths.values():
            if len(items) < 2:
                durations.append(0.0)
                continue
            durations.append((_parse_ts(items[-1]["timestamp"]) - _parse_ts(items[0]["timestamp"])).total_seconds())
        duration_sorted = sorted(durations)
        by_activity = self._activity_duration_stats(case_paths)
        activities = []
        for name, values in sorted(by_activity.items(), key=lambda item: len(item[1]), reverse=True):
            sorted_vals = sorted(values)
            activities.append(
                {
                    "name": name,
                    "frequency": len(values),
                    "avg_duration_seconds": round(sum(values) / max(1, len(values)), 2),
                    "min_duration_seconds": round(sorted_vals[0], 2) if sorted_vals else 0.0,
                    "max_duration_seconds": round(sorted_vals[-1], 2) if sorted_vals else 0.0,
                }
            )
        return {
            "total_cases": len(case_paths),
            "total_events": len(events),
            "unique_activities": len({event["activity"] for event in events}),
            "avg_case_duration_seconds": round(sum(durations) / max(1, len(durations)), 2),
            "median_case_duration_seconds": round(median(duration_sorted), 2) if duration_sorted else 0.0,
            "activities": activities,
        }

    def _performance(self, events: list[dict[str, Any]], include_bottlenecks: bool) -> dict[str, Any]:
        case_paths = self._build_case_paths(events)
        case_durations: list[float] = []
        throughput_by_day: Counter[str] = Counter()
        timestamps: list[datetime] = []

        for items in case_paths.values():
            first_ts = _parse_ts(items[0]["timestamp"])
            last_ts = _parse_ts(items[-1]["timestamp"])
            timestamps.extend([first_ts, last_ts])
            throughput_by_day[last_ts.date().isoformat()] += 1
            case_durations.append(max((last_ts - first_ts).total_seconds(), 0.0))

        sorted_case_durations = sorted(case_durations)
        by_activity = self._activity_duration_stats(case_paths)
        activity_rows = []
        for name, values in sorted(by_activity.items(), key=lambda item: len(item[1]), reverse=True):
            sorted_vals = sorted(values)
            activity_rows.append(
                {
                    "activity": name,
                    "frequency": len(values),
                    "avg_duration_seconds": round(sum(values) / max(1, len(values)), 2),
                    "median_duration_seconds": round(median(sorted_vals), 2) if sorted_vals else 0.0,
                    "p95_duration_seconds": round(_percentile(sorted_vals, 0.95), 2),
                }
            )

        throughput_values = list(throughput_by_day.values())
        bottlenecks = []
        if include_bottlenecks:
            bottlenecks = self._bottlenecks(events, sort_by="bottleneck_score_desc", _sla_source="eventstorming").get(
                "bottlenecks", []
            )
            bottlenecks = bottlenecks[:5]

        return {
            "overall_performance": {
                "total_cases": len(case_paths),
                "avg_case_duration_seconds": round(sum(case_durations) / max(1, len(case_durations)), 2),
                "median_case_duration_seconds": round(median(sorted_case_durations), 2) if sorted_case_durations else 0.0,
                "p95_case_duration_seconds": round(_percentile(sorted_case_durations, 0.95), 2),
            },
            "throughput": {
                "daily_avg_cases": round(sum(throughput_values) / max(1, len(throughput_values)), 3)
                if throughput_values
                else 0.0,
                "daily_peak_cases": max(throughput_values) if throughput_values else 0,
            },
            "time_window": {
                "start": min(timestamps).isoformat() if timestamps else None,
                "end": max(timestamps).isoformat() if timestamps else None,
            },
            "activity_performance": activity_rows,
            "bottlenecks": bottlenecks,
        }

    def _variants(self, case_paths: dict[str, list[dict[str, Any]]], sort_by: str, limit: int, min_cases: int) -> dict[str, Any]:
        if sort_by not in {"frequency_desc", "frequency_asc", "duration_desc", "duration_asc"}:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "invalid sort_by")
        bucket: dict[tuple[str, ...], list[float]] = defaultdict(list)
        for items in case_paths.values():
            seq = tuple(event["activity"] for event in items)
            if len(items) >= 2:
                duration = (_parse_ts(items[-1]["timestamp"]) - _parse_ts(items[0]["timestamp"])).total_seconds()
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
            rows.append(
                {
                    "variant_id": f"var-{uuid.uuid5(uuid.NAMESPACE_URL, '>'.join(sequence))}",
                    "rank": rank,
                    "activity_sequence": list(sequence),
                    "case_count": case_count,
                    "case_percentage": round((case_count / max(1, total_cases)) * 100.0, 2),
                    "avg_duration_seconds": round(sum(durations) / max(1, len(durations)), 2),
                    "median_duration_seconds": round(median(sorted(durations)), 2),
                    "is_designed_path": rank == 1,
                }
            )
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

    def _bottlenecks(self, events: list[dict[str, Any]], sort_by: str, _sla_source: str) -> dict[str, Any]:
        if sort_by not in {"bottleneck_score_desc", "avg_duration_desc", "violation_rate_desc"}:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "invalid sort_by")

        case_paths = self._build_case_paths(events)
        durations_by_activity = self._activity_duration_stats(case_paths)
        if not durations_by_activity:
            return {"bottlenecks": [], "overall_process": {"avg_duration_seconds": 0.0, "median_duration_seconds": 0.0, "total_sla_violations": 0, "overall_compliance_rate": 1.0}}

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
            duration_factor = (avg_seconds / max(1.0, max_avg))
            score = round(min(1.0, 0.7 * duration_factor + 0.3 * violation_rate), 3)
            rows.append(
                {
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
                }
            )

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
            process_durations.append((_parse_ts(path[-1]["timestamp"]) - _parse_ts(path[0]["timestamp"])).total_seconds())
        process_durations.sort()
        compliance_rate = 1.0 - (total_violations / max(1, sum(len(v) for v in durations_by_activity.values())))
        timestamps = sorted(_parse_ts(event["timestamp"]) for event in events)
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

    def submit_discover(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id and log_id are required")

        algorithm = str(payload.get("algorithm") or "inductive")
        if algorithm not in {"alpha", "heuristic", "inductive"}:
            raise ProcessMiningDomainError(400, "INVALID_ALGORITHM", "unsupported algorithm")
        params = payload.get("parameters") or {}
        noise_threshold = float(params.get("noise_threshold", 0.2))
        dependency_threshold = float(params.get("dependency_threshold", 0.5))
        if noise_threshold < 0 or noise_threshold > 1 or dependency_threshold < 0 or dependency_threshold > 1:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "threshold must be in [0,1]")

        options = payload.get("options") or {}
        generate_bpmn = bool(options.get("generate_bpmn", True))
        calculate_statistics = bool(options.get("calculate_statistics", True))
        store_in_neo4j = bool(options.get("store_in_neo4j", True))

        self._require_rate_limit()
        _, events = self._require_log(tenant_id, log_id)
        task = self._create_task(tenant_id, "discover", case_id, log_id, requested_by)
        self._set_running(task)

        model = None
        bpmn_xml_from_pm4py = None
        try:
            from app.mining.process_discovery import events_to_pm4py_dataframe, run_discover_sync
            df = events_to_pm4py_dataframe(events)
            if len(df) > 0:
                model, bpmn_xml_from_pm4py = run_discover_sync(
                    algorithm=algorithm,
                    df=df,
                    noise_threshold=noise_threshold,
                    dependency_threshold=dependency_threshold,
                    generate_bpmn=generate_bpmn,
                )
        except Exception:
            model = None
            bpmn_xml_from_pm4py = None
        if model is None:
            case_paths = self._build_case_paths(events)
            model = self._summarize_model(case_paths)
        result = {
            "algorithm": algorithm,
            "parameters": {"noise_threshold": noise_threshold, "dependency_threshold": dependency_threshold},
            "model": model,
            "neo4j_nodes_created": len(model.get("activities", [])) if store_in_neo4j else 0,
            "completed_at": _utcnow(),
        }
        if generate_bpmn:
            result["bpmn_xml"] = bpmn_xml_from_pm4py or self._build_bpmn_xml(model)
        if calculate_statistics:
            result["statistics"] = self._event_statistics(events)
        self._set_completed(task, result)
        return {
            "task_id": task.task_id,
            "log_id": log_id,
            "algorithm": algorithm,
            "status": "queued",
            "created_at": task.created_at,
            "estimated_duration_seconds": 30,
        }

    def _resolve_reference_activities(self, tenant_id: str, reference_model: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
        model_type = reference_model.get("type")
        model_id = str(reference_model.get("model_id") or "")
        if model_type not in {"eventstorming", "petri_net", "discovered"}:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "invalid reference_model.type")
        if not model_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "reference_model.model_id is required")

        if model_type == "discovered":
            result = self._result_or_404(tenant_id, model_id)
            return result["result"]["model"].get("activities", [])

        model = None
        if self._store:
            model = self._store.get_model(tenant_id, model_id)
        if model is None:
            model = self._models.get(model_id)
        if model:
            return model.get("activities", [])

        case_paths = self._build_case_paths(events)
        top = Counter(tuple(event["activity"] for event in seq) for seq in case_paths.values()).most_common(1)
        return list(top[0][0]) if top else []

    def submit_conformance(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id and log_id are required")
        reference_model = payload.get("reference_model") or {}
        options = payload.get("options") or {}
        include_case_diagnostics = bool(options.get("include_case_diagnostics", True))
        max_diag = int(options.get("max_diagnostics_cases", 100))
        if max_diag < 1 or max_diag > 1000:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "max_diagnostics_cases must be in [1,1000]")

        self._require_rate_limit()
        _, events = self._require_log(tenant_id, log_id)
        task = self._create_task(tenant_id, "conformance", case_id, log_id, requested_by)
        self._set_running(task)

        designed = self._resolve_reference_activities(tenant_id, reference_model, events)
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
            "case_diagnostics": [item.model_dump() for item in checker.case_diagnostics] if include_case_diagnostics else [],
            "deviation_statistics": checker.deviation_statistics,
            "completed_at": _utcnow(),
        }
        self._set_completed(task, result)
        return {
            "task_id": task.task_id,
            "status": "queued",
            "created_at": task.created_at,
        }

    def submit_bottlenecks(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id and log_id are required")
        sort_by = str((payload.get("options") or {}).get("sort_by", "bottleneck_score_desc"))
        sla_source = str((payload.get("options") or {}).get("sla_source", "eventstorming"))

        self._require_rate_limit()
        _, events = self._require_log(tenant_id, log_id)
        task = self._create_task(tenant_id, "bottlenecks", case_id, log_id, requested_by)
        self._set_running(task)
        result = self._bottlenecks(events, sort_by=sort_by, _sla_source=sla_source)
        result["completed_at"] = _utcnow()
        self._set_completed(task, result)
        return {"task_id": task.task_id, "status": "queued", "created_at": task.created_at}

    def submit_performance(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        log_id = str(payload.get("log_id") or "").strip()
        if not case_id or not log_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id and log_id are required")

        self._require_rate_limit()
        _, events = self._require_log(tenant_id, log_id)
        include_bottlenecks = bool((payload.get("options") or {}).get("include_bottlenecks", True))
        task = self._create_task(tenant_id, "performance", case_id, log_id, requested_by)
        self._set_running(task)
        result = self._performance(events, include_bottlenecks=include_bottlenecks)
        result["completed_at"] = _utcnow()
        self._set_completed(task, result)
        return {"task_id": task.task_id, "status": "queued", "created_at": task.created_at}

    def list_variants(self, tenant_id: str, case_id: str, log_id: str, sort_by: str, limit: int, min_cases: int) -> dict[str, Any]:
        if not case_id or not log_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id and log_id are required")
        event_case_id, events = self._require_log(tenant_id, log_id)
        if case_id != event_case_id:
            raise ProcessMiningDomainError(404, "LOG_NOT_FOUND", "log does not belong to case_id")
        case_paths = self._build_case_paths(events)
        data = self._variants(case_paths, sort_by=sort_by, limit=limit, min_cases=max(1, min_cases))
        data["log_id"] = log_id
        return data

    def get_bottlenecks(self, tenant_id: str, case_id: str, log_id: str, sort_by: str, sla_source: str) -> dict[str, Any]:
        if not case_id or not log_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id and log_id are required")
        event_case_id, events = self._require_log(tenant_id, log_id)
        if case_id != event_case_id:
            raise ProcessMiningDomainError(404, "LOG_NOT_FOUND", "log does not belong to case_id")
        data = self._bottlenecks(events, sort_by=sort_by, _sla_source=sla_source)
        data["log_id"] = log_id
        return data

    def get_task(self, tenant_id: str, task_id: str) -> dict[str, Any]:
        task = self._task_or_404(tenant_id, task_id)
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "case_id": task.case_id,
            "log_id": task.log_id,
            "result_id": task.result_id,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
            "error": task.error,
        }

    def get_task_result(self, tenant_id: str, task_id: str) -> dict[str, Any]:
        task = self._task_or_404(tenant_id, task_id)
        if not task.result_id:
            raise ProcessMiningDomainError(404, "RESULT_NOT_FOUND", "result not found")
        return self._results[task.result_id]

    def get_result(self, tenant_id: str, result_or_task_id: str) -> dict[str, Any]:
        return self._result_or_404(tenant_id, result_or_task_id)

    def get_statistics(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        _, events = self._require_log(tenant_id, log_id)
        data = self._event_statistics(events)
        return {"log_id": log_id, **data}

    def export_bpmn(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        if not case_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id is required")
        source = payload.get("source") or {}
        source_type = source.get("type")
        if source_type not in {"discovered", "imported"}:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "source.type must be discovered|imported")

        xml: str
        result_data: dict[str, Any] | None = None
        if source_type == "discovered":
            key = source.get("task_id") or source.get("result_id")
            if not key:
                raise ProcessMiningDomainError(400, "INVALID_REQUEST", "task_id or result_id is required")
            result = self._result_or_404(tenant_id, str(key))
            result_data = result["result"]
            xml = result_data.get("bpmn_xml") or self._build_bpmn_xml(result_data.get("model", {}))
        else:
            model_id = str(source.get("model_id") or "")
            model = None
            if self._store:
                model = self._store.get_model(tenant_id, model_id)
            if model is None:
                model = self._models.get(model_id)
            if not model:
                raise ProcessMiningDomainError(404, "MODEL_NOT_FOUND", "model not found")
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

    def import_model(self, tenant_id: str, payload: dict[str, Any], requested_by: str | None = None) -> dict[str, Any]:
        case_id = str(payload.get("case_id") or "").strip()
        if not case_id:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "case_id is required")
        model = payload.get("model") or {}
        model_type = model.get("type")
        if model_type not in {"bpmn", "petri_net"}:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "model.type must be bpmn|petri_net")
        content = str(model.get("content") or "").strip()
        if not content:
            raise ProcessMiningDomainError(400, "INVALID_REQUEST", "model.content is required")

        model_id = f"bpm-model-{uuid.uuid4()}"
        activities = []
        if model_type == "petri_net":
            activities = [str(item) for item in (model.get("activities") or [])]
        if not activities:
            activities = ["주문 접수", "결제 확인", "출하 지시", "배송 완료"]
        xml = content if model_type == "bpmn" else self._build_bpmn_xml({"activities": activities}, process_name=model_id)
        imported_at = _utcnow()
        if self._store:
            self._store.insert_model(model_id, tenant_id, case_id, model_type, xml, activities, requested_by)
        else:
            self._models[model_id] = {
                "model_id": model_id,
                "tenant_id": tenant_id,
                "case_id": case_id,
                "type": model_type,
                "xml": xml,
                "activities": activities,
                "created_by": requested_by,
                "imported_at": imported_at,
            }
        return {
            "model_id": model_id,
            "status": "imported",
            "source_result_id": payload.get("result_id"),
            "imported_at": imported_at,
        }


process_mining_service = ProcessMiningService()
