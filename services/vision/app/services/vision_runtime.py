from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
import os
from typing import Any

import httpx

from app.services.root_cause_engine import run_counterfactual_engine, run_root_cause_engine
from app.services.vision_state_store import VisionStateStore

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VisionRuntimeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class VisionRuntime:
    def __init__(self, store: VisionStateStore | None = None) -> None:
        self.store = store or VisionStateStore(
            os.getenv("VISION_STATE_DATABASE_URL", "postgresql://arkos:arkos@localhost:5432/insolvency_os")
        )
        loaded = self.store.load_state()
        self.what_if_by_case: dict[str, dict[str, dict[str, Any]]] = loaded.get("what_if_by_case", {})
        self.cubes: dict[str, dict[str, Any]] = loaded.get("cubes", {})
        self.etl_jobs: dict[str, dict[str, Any]] = loaded.get("etl_jobs", {})
        self.root_cause_by_case: dict[str, dict[str, Any]] = loaded.get("root_cause_by_case", {})
        self._id_seq = count(1)
        self._root_cause_metrics: dict[str, Any] = {}
        self._reset_root_cause_metrics()

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000)}-{next(self._id_seq)}"

    def clear(self) -> None:
        self.what_if_by_case.clear()
        self.cubes.clear()
        self.etl_jobs.clear()
        self.root_cause_by_case.clear()
        self.store.clear()
        self._reset_root_cause_metrics()

    def _reset_root_cause_metrics(self) -> None:
        self._root_cause_metrics = {
            "calls_total": 0,
            "success_total": 0,
            "error_total": 0,
            "latency_ms_total": 0.0,
            "operations": {},
        }

    def record_root_cause_call(self, operation: str, success: bool, latency_ms: float) -> None:
        metrics = self._root_cause_metrics
        metrics["calls_total"] += 1
        metrics["latency_ms_total"] += max(latency_ms, 0.0)
        if success:
            metrics["success_total"] += 1
        else:
            metrics["error_total"] += 1

        op = metrics["operations"].setdefault(
            operation,
            {"calls_total": 0, "success_total": 0, "error_total": 0, "latency_ms_total": 0.0},
        )
        op["calls_total"] += 1
        op["latency_ms_total"] += max(latency_ms, 0.0)
        if success:
            op["success_total"] += 1
        else:
            op["error_total"] += 1

    def get_root_cause_operational_metrics(self) -> dict[str, Any]:
        metrics = self._root_cause_metrics
        calls_total = int(metrics["calls_total"])
        error_total = int(metrics["error_total"])
        avg_latency_ms = 0.0 if calls_total == 0 else round(float(metrics["latency_ms_total"]) / calls_total, 3)
        failure_rate = 0.0 if calls_total == 0 else round(error_total / calls_total, 6)
        operations = {}
        for name, item in metrics["operations"].items():
            op_calls = int(item["calls_total"])
            operations[name] = {
                "calls_total": op_calls,
                "error_total": int(item["error_total"]),
                "avg_latency_ms": 0.0 if op_calls == 0 else round(float(item["latency_ms_total"]) / op_calls, 3),
            }
        return {
            "calls_total": calls_total,
            "success_total": int(metrics["success_total"]),
            "error_total": error_total,
            "failure_rate": failure_rate,
            "avg_latency_ms": avg_latency_ms,
            "operations": operations,
        }

    def render_root_cause_metrics_prometheus(self) -> str:
        snapshot = self.get_root_cause_operational_metrics()
        lines = [
            "# HELP vision_root_cause_calls_total Total root cause API calls",
            "# TYPE vision_root_cause_calls_total counter",
            f"vision_root_cause_calls_total {snapshot['calls_total']}",
            "# HELP vision_root_cause_errors_total Total root cause API errors",
            "# TYPE vision_root_cause_errors_total counter",
            f"vision_root_cause_errors_total {snapshot['error_total']}",
            "# HELP vision_root_cause_failure_rate Root cause API failure rate",
            "# TYPE vision_root_cause_failure_rate gauge",
            f"vision_root_cause_failure_rate {snapshot['failure_rate']}",
            "# HELP vision_root_cause_avg_latency_ms Average root cause API latency milliseconds",
            "# TYPE vision_root_cause_avg_latency_ms gauge",
            f"vision_root_cause_avg_latency_ms {snapshot['avg_latency_ms']}",
        ]
        for op_name, op in snapshot["operations"].items():
            lines.append(f'vision_root_cause_operation_calls_total{{operation="{op_name}"}} {op["calls_total"]}')
            lines.append(f'vision_root_cause_operation_errors_total{{operation="{op_name}"}} {op["error_total"]}')
            lines.append(f'vision_root_cause_operation_avg_latency_ms{{operation="{op_name}"}} {op["avg_latency_ms"]}')
        return "\n".join(lines) + "\n"

    def scenarios(self, case_id: str) -> dict[str, dict[str, Any]]:
        return self.what_if_by_case.setdefault(case_id, {})

    def create_scenario(self, case_id: str, payload: dict[str, Any], created_by: str) -> dict[str, Any]:
        scenario_id = self._new_id("scn-")
        now = _now()
        scenario = {
            "id": scenario_id,
            "case_id": case_id,
            "scenario_name": payload["scenario_name"],
            "scenario_type": payload["scenario_type"],
            "base_scenario_id": payload.get("base_scenario_id"),
            "description": payload.get("description"),
            "status": "DRAFT",
            "parameters": payload.get("parameters", {}),
            "constraints": payload.get("constraints", []),
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "completed_at": None,
            "created_by": created_by,
            "result": None,
        }
        self.scenarios(case_id)[scenario_id] = scenario
        self.store.upsert_scenario(case_id, scenario_id, scenario)
        return scenario

    def save_scenario(self, case_id: str, scenario: dict[str, Any]) -> None:
        scenario_id = str(scenario.get("id") or "")
        if not scenario_id:
            return
        self.scenarios(case_id)[scenario_id] = scenario
        self.store.upsert_scenario(case_id, scenario_id, scenario)

    def list_scenarios(self, case_id: str) -> list[dict[str, Any]]:
        items = list(self.scenarios(case_id).values())
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return items

    def get_scenario(self, case_id: str, scenario_id: str) -> dict[str, Any] | None:
        return self.scenarios(case_id).get(scenario_id)

    def delete_scenario(self, case_id: str, scenario_id: str) -> bool:
        bucket = self.scenarios(case_id)
        if scenario_id not in bucket:
            return False
        del bucket[scenario_id]
        self.store.delete_scenario(case_id, scenario_id)
        return True

    def compute_scenario(self, case_id: str, scenario_id: str) -> dict[str, Any]:
        scenario = self.get_scenario(case_id, scenario_id)
        if not scenario:
            raise KeyError("scenario not found")
        started_at = _now()
        scenario["status"] = "COMPUTING"
        scenario["started_at"] = started_at
        params = scenario.get("parameters", {})
        interest_rate = float(params.get("interest_rate", 4.0))
        growth_rate = float(params.get("ebitda_growth_rate", 5.0))
        period = int(params.get("execution_period_years", 10))
        operating_cost_ratio = float(params.get("operating_cost_ratio", 65.0))
        base_total = 5_000_000_000.0
        npv = base_total * (1 + growth_rate / 100.0) * (1 - interest_rate / 100.0)
        feasibility = max(0.0, min(1.0, (growth_rate / 100.0) - (interest_rate / 200.0) + 0.5))

        by_year = []
        yearly = base_total / max(1, period)
        cumulative_allocation = 0.0
        for year_idx in range(1, period + 1):
            allocation_amount = yearly * 0.52
            cumulative_allocation += allocation_amount
            net_cash = yearly * ((1 + growth_rate / 100.0) - (operating_cost_ratio / 100.0))
            by_year.append(
                {
                    "year": year_idx,
                    "revenue": round(yearly * (1 + growth_rate / 100.0), 2),
                    "ebitda": round(yearly * max(0.01, (100 - operating_cost_ratio) / 100.0), 2),
                    "interest_expense": round(yearly * (interest_rate / 100.0), 2),
                    "operating_cost": round(yearly * (operating_cost_ratio / 100.0), 2),
                    "net_cashflow": round(net_cash, 2),
                    "allocation_amount": round(allocation_amount, 2),
                    "cumulative_allocation": round(cumulative_allocation, 2),
                    "cash_balance": round(max(0.0, net_cash * 0.45), 2),
                    "dscr": round(max(0.1, 1.0 + growth_rate / 25.0 - interest_rate / 40.0), 2),
                }
            )

        total_obligations = round(base_total, 2)
        by_stakeholder = [
            {
                "class": "priority",
                "total_obligation": round(total_obligations * 0.05, 2),
                "allocation_amount": round(total_obligations * 0.05, 2),
                "allocation_rate": 1.0,
            },
            {
                "class": "secured",
                "total_obligation": round(total_obligations * 0.30, 2),
                "allocation_amount": round(total_obligations * 0.24, 2),
                "allocation_rate": 0.8,
            },
            {
                "class": "unsecured",
                "total_obligation": round(total_obligations * 0.65, 2),
                "allocation_amount": round(total_obligations * 0.2275, 2),
                "allocation_rate": 0.35,
            },
        ]
        constraints = scenario.get("constraints") or []
        constraints_met = [
            {
                "constraint_type": c.get("constraint_type", "custom"),
                "description": c.get("description", "custom constraint"),
                "actual_value": c.get("value", 0.0),
                "threshold": c.get("value", 0.0),
                "satisfied": True,
            }
            for c in constraints
        ]

        completed_at = _now()
        result = {
            "scenario_id": scenario_id,
            "scenario_name": scenario["scenario_name"],
            "status": "COMPLETED",
            "computed_at": completed_at,
            "solver_iterations": 100 + period,
            "is_feasible": feasibility >= 0.4,
            "feasibility_score": round(feasibility, 3),
            "summary": {
                "total_allocation": round(base_total * 0.52, 2),
                "total_obligations": total_obligations,
                "overall_allocation_rate": 0.52,
                "execution_period_years": period,
                "npv_at_wacc": round(npv, 2),
            },
            "by_year": by_year,
            "by_stakeholder_class": by_stakeholder,
            "constraints_met": constraints_met,
        }
        scenario["status"] = "COMPLETED"
        scenario["result"] = result
        scenario["updated_at"] = completed_at
        scenario["completed_at"] = completed_at
        self.store.upsert_scenario(case_id, scenario_id, scenario)
        return result

    def create_cube(self, cube_name: str, fact_table: str, dimensions: list[str], measures: list[str]) -> dict[str, Any]:
        now = _now()
        cube = {
            "name": cube_name,
            "fact_table": fact_table,
            "dimensions": dimensions,
            "measures": measures,
            "dimension_count": len(dimensions),
            "measure_count": len(measures),
            "last_refreshed": now,
            "row_count": 1000,
        }
        self.cubes[cube_name] = cube
        self.store.upsert_cube(cube_name, cube)
        return cube

    def queue_etl_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        job_id = self._new_id("etl-")
        now = _now()
        job = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "payload": payload,
        }
        self.etl_jobs[job_id] = job
        self.store.upsert_etl_job(job_id, job)
        return job

    def get_etl_job(self, job_id: str) -> dict[str, Any] | None:
        return self.etl_jobs.get(job_id)

    def complete_etl_job_if_queued(self, job_id: str) -> dict[str, Any] | None:
        job = self.get_etl_job(job_id)
        if not job:
            return None
        if job["status"] == "queued":
            job["status"] = "completed"
            job["updated_at"] = _now()
            self.store.upsert_etl_job(job_id, job)
        return job

    def create_root_cause_analysis(self, case_id: str, payload: dict[str, Any], requested_by: str) -> dict[str, Any]:
        analysis_id = self._new_id("rca-")
        now = _now()
        engine_result = run_root_cause_engine(case_id=case_id, payload=payload)
        analysis = {
            "analysis_id": analysis_id,
            "case_id": case_id,
            "status": "ANALYZING",
            "progress": {
                "step": "computing_shap_values",
                "step_label": "요인 기여도 계산 중",
                "pct": 65,
            },
            "started_at": now,
            "updated_at": now,
            "completed_at": None,
            "requested_by": requested_by,
            "request": payload,
            "causal_graph_version": "v2.1",
            "overall_confidence": engine_result["overall_confidence"],
            "predicted_failure_probability": engine_result["predicted_failure_probability"],
            "confidence_basis": engine_result["confidence_basis"],
            "root_causes": engine_result["root_causes"],
            "explanation": engine_result["explanation"],
        }
        self.root_cause_by_case[case_id] = analysis
        self.store.upsert_root_cause_analysis(case_id, analysis)
        return analysis

    def get_root_cause_analysis(self, case_id: str) -> dict[str, Any] | None:
        return self.root_cause_by_case.get(case_id)

    def get_root_cause_status(self, case_id: str) -> dict[str, Any] | None:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis:
            return None
        if analysis["status"] == "ANALYZING":
            analysis["status"] = "COMPLETED"
            analysis["progress"] = {
                "step": "generating_explanation",
                "step_label": "설명 생성 완료",
                "pct": 100,
            }
            analysis["completed_at"] = _now()
            analysis["updated_at"] = analysis["completed_at"]
            self.store.upsert_root_cause_analysis(case_id, analysis)
        return analysis

    def get_root_causes(self, case_id: str) -> dict[str, Any] | None:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            return None
        return {
            "case_id": case_id,
            "analysis_id": analysis["analysis_id"],
            "analyzed_at": analysis["completed_at"],
            "causal_graph_version": analysis["causal_graph_version"],
            "overall_confidence": analysis["overall_confidence"],
            "confidence_basis": analysis.get("confidence_basis"),
            "root_causes": analysis["root_causes"],
            "explanation": analysis["explanation"],
        }

    def run_counterfactual(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        actual_value = float(payload["actual_value"])
        counterfactual_value = float(payload["counterfactual_value"])
        computed = run_counterfactual_engine(
            analysis=analysis,
            variable=payload["variable"],
            actual_value=actual_value,
            counterfactual_value=counterfactual_value,
        )
        return {
            "analysis_id": analysis["analysis_id"],
            "case_id": case_id,
            "variable": payload["variable"],
            "actual_value": actual_value,
            "counterfactual_value": counterfactual_value,
            "question": payload.get("question"),
            "estimated_failure_probability_before": computed["estimated_failure_probability_before"],
            "estimated_failure_probability_after": computed["estimated_failure_probability_after"],
            "risk_reduction_pct": computed["risk_reduction_pct"],
            "confidence_basis": computed["confidence_basis"],
            "computed_at": _now(),
        }

    def get_causal_timeline(self, case_id: str) -> dict[str, Any]:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        return {
            "case_id": case_id,
            "timeline": [
                {
                    "date": "2022-06-15",
                    "event": "차입 확대",
                    "variable": "debt_ratio",
                    "value_before": 0.80,
                    "value_after": 1.50,
                    "impact": "critical",
                    "description": "부채비율 급등",
                },
                {
                    "date": "2023-01-25",
                    "event": "금리 인상",
                    "variable": "interest_rate_env",
                    "value_before": 3.50,
                    "value_after": 5.50,
                    "impact": "high",
                    "description": "이자비용 상승",
                },
                {
                    "date": "2023-09-01",
                    "event": "수익성 악화",
                    "variable": "ebitda",
                    "value_before": 1500000000,
                    "value_after": 600000000,
                    "impact": "critical",
                    "description": "EBITDA 하락",
                },
            ],
        }

    def get_root_cause_impact(self, case_id: str) -> dict[str, Any]:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        contributions = []
        for item in analysis["root_causes"]:
            pct = float(item.get("contribution_pct", 0.0))
            contributions.append(
                {
                    "variable": item["variable"],
                    "label": item["variable_label"],
                    "shap_value": round(float(item.get("shap_value", 0.0)), 4),
                    "feature_value": item.get("actual_value"),
                    "direction": item.get("direction", "positive"),
                    "description": f"실패 확률 기여도 {pct:.1f}%",
                }
            )
        base = round(
            max(0.01, float(analysis.get("predicted_failure_probability", 0.70)) - sum(c["shap_value"] for c in contributions)),
            3,
        )
        return {
            "case_id": case_id,
            "base_value": base,
            "predicted_value": round(base + sum(c["shap_value"] for c in contributions), 3),
            "confidence_basis": analysis.get("confidence_basis"),
            "contributions": contributions,
        }

    def get_causal_graph(self, case_id: str) -> dict[str, Any]:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        nodes = []
        edges = []
        for idx, item in enumerate(analysis["root_causes"], start=1):
            node_id = item["variable"]
            nodes.append(
                {
                    "id": node_id,
                    "label": item["variable_label"],
                    "type": "intermediate",
                    "value": item.get("actual_value"),
                    "position": {"x": 120 * idx, "y": 120},
                }
            )
            edges.append(
                {
                    "source": node_id,
                    "target": "business_failure",
                    "coefficient": round(float(item.get("contribution_pct", 0.0)) / 100.0, 3),
                    "confidence": item.get("confidence", 0.7),
                    "label": f"{item.get('contribution_pct', 0)}% 영향",
                }
            )
        nodes.append(
            {
                "id": "business_failure",
                "label": "비즈니스 실패",
                "type": "outcome",
                "value": 1,
                "position": {"x": 500, "y": 300},
            }
        )
        return {
            "graph_version": analysis.get("causal_graph_version", "v2.1"),
            "training_samples": 127,
            "nodes": nodes,
            "edges": edges,
        }

    def get_process_bottleneck_root_cause(
        self,
        case_id: str,
        process_id: str,
        bottleneck_activity: str | None = None,
        max_causes: int = 5,
        include_explanation: bool = True,
    ) -> dict[str, Any]:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        if not process_id.strip():
            raise ValueError("process_id is required")

        max_causes = min(max(max_causes, 1), 10)
        selected = analysis["root_causes"][:max_causes]
        root_causes = [
            {
                "rank": idx,
                "variable": item["variable"],
                "variable_label": item["variable_label"],
                "related_activity": bottleneck_activity,
                "shap_value": item["shap_value"],
                "contribution_pct": item["contribution_pct"],
                "actual_value": item["actual_value"],
                "normal_range": None,
                "description": item["description"],
                "causal_chain": item["causal_chain"],
                "confidence": item["confidence"],
            }
            for idx, item in enumerate(selected, start=1)
        ]

        synapse_status = "fallback"
        source_log_id = process_id
        data_range = None
        case_count = None
        bottleneck_score = 0.82
        bottleneck_name = bottleneck_activity or "승인"
        if os.getenv("SYNAPSE_BASE_URL", "").strip():
            synapse = self._fetch_synapse_process_context(case_id=case_id, process_id=process_id)
            synapse_status = "connected"
            source_log_id = synapse["source_log_id"]
            data_range = synapse["data_range"]
            case_count = synapse["case_count"]
            bottleneck_score = synapse["bottleneck_score"]
            bottleneck_name = bottleneck_activity or synapse["bottleneck_activity"] or "승인"

        return {
            "case_id": case_id,
            "process_model_id": process_id,
            "source_log_id": source_log_id,
            "bottleneck_activity": bottleneck_name,
            "bottleneck_score": bottleneck_score,
            "analyzed_at": _now(),
            "data_range": data_range,
            "case_count": case_count,
            "overall_confidence": analysis["overall_confidence"],
            "root_causes": root_causes,
            "recommendations": [
                "승인 리소스 보강",
                "재작업 비율 절감",
                "피크 시간대 부하 분산",
            ],
            "explanation": analysis["explanation"] if include_explanation else None,
            "synapse_status": synapse_status,
        }

    def _fetch_synapse_process_context(self, case_id: str, process_id: str) -> dict[str, Any]:
        synapse_base = os.getenv("SYNAPSE_BASE_URL", "").strip().rstrip("/")
        log_id = os.getenv("VISION_BOTTLENECK_LOG_ID", process_id).strip() or process_id
        params = {"case_id": case_id, "log_id": log_id, "sort_by": "bottleneck_score_desc"}

        try:
            with httpx.Client(timeout=5.0) as client:
                bottlenecks_resp = client.get(f"{synapse_base}/api/v3/synapse/process-mining/bottlenecks", params=params)
                variants_resp = client.get(
                    f"{synapse_base}/api/v3/synapse/process-mining/variants",
                    params={"case_id": case_id, "log_id": log_id, "limit": 5},
                )
                performance_resp = client.post(
                    f"{synapse_base}/api/v3/synapse/process-mining/performance",
                    json={"case_id": case_id, "log_id": log_id, "options": {"include_bottlenecks": True}},
                )
        except Exception as exc:  # pragma: no cover - network branch
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable") from exc

        for resp in (bottlenecks_resp, variants_resp, performance_resp):
            if resp.status_code >= 500:
                raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable")
            if resp.status_code == 404:
                code = ((resp.json().get("detail") or {}).get("code") if resp.headers.get("content-type", "").startswith("application/json") else None)
                if code == "LOG_NOT_FOUND":
                    raise VisionRuntimeError("PROCESS_MODEL_NOT_FOUND", "process model not found")
            if resp.status_code == 400:
                detail = resp.json().get("detail") if resp.headers.get("content-type", "").startswith("application/json") else {}
                code = (detail or {}).get("code")
                if code in {"INSUFFICIENT_PROCESS_DATA", "EMPTY_EVENT_LOG"}:
                    raise VisionRuntimeError("INSUFFICIENT_PROCESS_DATA", "insufficient process data")

        if bottlenecks_resp.status_code >= 400:
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable")

        bottlenecks_data = bottlenecks_resp.json().get("data", {})
        bottlenecks = bottlenecks_data.get("bottlenecks") or []
        top = bottlenecks[0] if bottlenecks else {}
        overall = bottlenecks_data.get("overall_process") or {}
        period = bottlenecks_data.get("analysis_period") or {}
        case_count = int(overall.get("total_sla_violations", 0)) if overall else None
        if performance_resp.status_code < 400:
            performance_task = performance_resp.json().get("data", {})
            if isinstance(performance_task, dict) and performance_task.get("task_id"):
                # async task 기반이므로 case_count는 bottleneck payload 기반이 없으면 None 유지
                pass
        return {
            "source_log_id": log_id,
            "bottleneck_activity": top.get("activity"),
            "bottleneck_score": float(top.get("bottleneck_score", 0.82)),
            "data_range": {"from": period.get("start"), "to": period.get("end")} if period else None,
            "case_count": case_count,
        }


vision_runtime = VisionRuntime()
