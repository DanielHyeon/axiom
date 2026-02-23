from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from itertools import count
import os
from typing import Any

import httpx

# ETL: 허용 MV 목록 (etl-pipeline.md 기준). REFRESH MATERIALIZED VIEW CONCURRENTLY만 허용.
ALLOWED_MV_VIEWS = frozenset({
    "mv_business_fact",
    "mv_cashflow_fact",
    "dim_case_type",
    "dim_org",
    "dim_time",
    "dim_stakeholder_type",
})

from app.engines.scenario_solver import (
    SolverConvergenceError,
    SolverInfeasibleError,
    SolverTimeoutError,
    solve_scenario_result,
    SOLVER_TIMEOUT_SECONDS,
)
from app.services.root_cause_engine import run_counterfactual_engine, run_root_cause_engine
from app.services.vision_state_store import VisionStateStore

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VisionRuntimeError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class PivotQueryTimeoutError(Exception):
    """피벗 쿼리 30초 타임아웃 (504 QUERY_TIMEOUT)."""


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

    def set_scenario_computing(self, case_id: str, scenario_id: str) -> None:
        """비동기 compute 시작 시 상태만 COMPUTING으로 설정 (202 반환 후 백그라운드에서 솔버 실행)."""
        scenario = self.get_scenario(case_id, scenario_id)
        if not scenario:
            raise KeyError("scenario not found")
        scenario["status"] = "COMPUTING"
        scenario["started_at"] = _now()
        scenario["failure_reason"] = None
        self.store.upsert_scenario(case_id, scenario_id, scenario)

    def set_scenario_failed(self, case_id: str, scenario_id: str, reason: str) -> None:
        """솔버 타임아웃/실패 시 상태를 FAILED로 설정."""
        scenario = self.get_scenario(case_id, scenario_id)
        if not scenario:
            return
        scenario["status"] = "FAILED"
        scenario["completed_at"] = _now()
        scenario["failure_reason"] = reason
        scenario["result"] = None
        self.store.upsert_scenario(case_id, scenario_id, scenario)

    def run_scenario_solver(self, case_id: str, scenario_id: str) -> dict[str, Any] | None:
        """
        scipy 기반 솔버 실행 (동기). 스레드에서 호출하며 60초 타임아웃 적용.
        성공 시 결과 저장 후 반환, 실패 시 FAILED 저장 후 예외 또는 None.
        """
        scenario = self.get_scenario(case_id, scenario_id)
        if not scenario:
            raise KeyError("scenario not found")
        completed_at = _now()
        params = scenario.get("parameters", {})
        constraints = scenario.get("constraints") or []
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(
                    solve_scenario_result,
                    scenario_id,
                    scenario["scenario_name"],
                    params,
                    constraints,
                    completed_at,
                )
                result = future.result(timeout=SOLVER_TIMEOUT_SECONDS + 5)
        except SolverInfeasibleError as e:
            self.set_scenario_failed(case_id, scenario_id, str(e))
            return None
        except SolverConvergenceError as e:
            self.set_scenario_failed(case_id, scenario_id, str(e))
            return None
        except SolverTimeoutError as e:
            self.set_scenario_failed(case_id, scenario_id, str(e))
            return None
        except Exception as e:
            self.set_scenario_failed(case_id, scenario_id, str(e))
            return None
        scenario["status"] = "COMPLETED"
        scenario["result"] = result
        scenario["updated_at"] = completed_at
        scenario["completed_at"] = completed_at
        scenario["failure_reason"] = None
        self.store.upsert_scenario(case_id, scenario_id, scenario)
        return result

    def create_cube(
        self,
        cube_name: str,
        fact_table: str,
        dimensions: list[str],
        measures: list[str],
        dimension_details: list[dict[str, Any]] | None = None,
        measure_details: list[dict[str, Any]] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
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
        if dimension_details is not None:
            cube["dimension_details"] = dimension_details
        if measure_details is not None:
            cube["measure_details"] = measure_details
        cube.update(extra)
        self.cubes[cube_name] = cube
        self.store.upsert_cube(cube_name, cube)
        return cube

    def execute_pivot_query(
        self,
        sql: str,
        params: list[Any],
        timeout_seconds: int = 30,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """
        피벗용 읽기 전용 SQL 실행. (rows, column_names) 반환.
        PostgreSQL이 아니거나 실패 시 빈 결과. 타임아웃 시 PivotQueryTimeoutError.
        """
        if not getattr(self.store, "_is_postgres", False):
            return [], []
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            return [], []
        try:
            conn = psycopg2.connect(self.store.database_url)
            conn.set_session(readonly=True)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (timeout_seconds * 1000,))
            cur.execute(sql, params)
            rows = cur.fetchall()
            column_names = list(rows[0].keys()) if rows else []
            conn.close()
            return [dict(r) for r in rows], column_names
        except Exception as e:
            err_msg = str(e).lower()
            if "timeout" in err_msg or "canceled" in err_msg or "statement_timeout" in err_msg:
                raise PivotQueryTimeoutError() from e
            return [], []

    def _is_etl_running(self) -> bool:
        """진행 중인 ETL 작업이 있으면 True (RUNNING 상태)."""
        return any(
            j.get("status") == "RUNNING"
            for j in self.etl_jobs.values()
        )

    def queue_etl_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        sync_type = str(payload.get("sync_type") or "full").lower()
        target_views = list(payload.get("target_views") or ["mv_business_fact"])
        force = bool(payload.get("force"))
        if not force and self._is_etl_running():
            raise VisionRuntimeError("ETL_IN_PROGRESS", "데이터 동기화가 진행 중입니다")

        job_id = self._new_id("etl-")
        now = _now()
        job = {
            "job_id": job_id,
            "status": "queued",
            "sync_type": sync_type,
            "target_views": target_views,
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
        if job.get("status") == "queued":
            job["status"] = "completed"
            job["updated_at"] = _now()
            self.store.upsert_etl_job(job_id, job)
        return job

    def run_etl_refresh_sync(self, job_id: str) -> None:
        """
        ETL 동기화 실행 (동기). 백그라운드 스레드에서 호출.
        target_views에 대해 REFRESH MATERIALIZED VIEW [CONCURRENTLY] 실행 후
        job 상태를 RUNNING → COMPLETED/FAILED, duration_seconds, rows_affected 반영.
        """
        job = self.get_etl_job(job_id)
        if not job or job.get("status") != "queued":
            return
        now = _now()
        job["status"] = "RUNNING"
        job["started_at"] = now
        job["updated_at"] = now
        self.store.upsert_etl_job(job_id, job)

        target_views = job.get("target_views") or ["mv_business_fact"]
        views_to_refresh = [v for v in target_views if v in ALLOWED_MV_VIEWS]
        start_monotonic = time.monotonic()
        rows_affected: dict[str, int] = {}

        try:
            if self.store._is_postgres and views_to_refresh:
                psycopg2, _ = self.store._import_psycopg2()
                conn = psycopg2.connect(self.store.database_url)
                try:
                    # REFRESH MATERIALIZED VIEW CONCURRENTLY cannot run inside a transaction block
                    conn.autocommit = True
                    cur = conn.cursor()
                    for view in views_to_refresh:
                        try:
                            cur.execute(f'REFRESH MATERIALIZED VIEW CONCURRENTLY "{view}"')
                        except Exception:
                            try:
                                cur.execute(f'REFRESH MATERIALIZED VIEW "{view}"')
                            except Exception as e:
                                raise e
                    # pg_stat_user_tables에서 대략 행 수 (갱신 후)
                    cur.execute(
                        "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname = ANY(%s)",
                        (list(views_to_refresh),),
                    )
                    for row in cur.fetchall():
                        rows_affected[str(row[0])] = int(row[1] or 0)
                finally:
                    conn.close()
            # SQLite 또는 views_to_refresh 빈 경우: no-op
            elapsed = time.monotonic() - start_monotonic
            job["status"] = "COMPLETED"
            job["completed_at"] = _now()
            job["duration_seconds"] = round(elapsed, 2)
            job["rows_affected"] = rows_affected
            job["updated_at"] = _now()
        except Exception as e:
            job["status"] = "FAILED"
            job["completed_at"] = _now()
            job["duration_seconds"] = round(time.monotonic() - start_monotonic, 2)
            job["error_message"] = str(e)
            job["rows_affected"] = {}
            job["updated_at"] = _now()
        self.store.upsert_etl_job(job_id, job)

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

    def run_process_simulation(
        self,
        case_id: str,
        process_model_id: str,
        scenario_name: str,
        description: str | None,
        parameter_changes: list[dict[str, Any]],
        sla_threshold_seconds: int | None,
    ) -> dict[str, Any]:
        """
        프로세스 시간축 시뮬레이션 (what-if-api.md §10).
        Synapse performance/bottlenecks/variants 호출 후 parameter_changes 적용,
        original_cycle_time, simulated_cycle_time, by_activity, bottleneck_shift 반환.
        Synapse 연결 실패 시 VisionRuntimeError(SYNAPSE_UNAVAILABLE) 발생.
        """
        if not os.getenv("SYNAPSE_BASE_URL", "").strip():
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable")
        try:
            ctx = self._fetch_synapse_process_context(case_id, process_model_id)
        except VisionRuntimeError:
            raise
        except Exception as exc:
            raise VisionRuntimeError("SYNAPSE_UNAVAILABLE", "process mining service unavailable") from exc

        # 활동별 기본 소요시간 (Synapse에서 상세 미제공 시 사용)
        default_activities = ["접수", "승인", "검토", "배송"]
        default_durations = [3600, 14400, 28800, 86400]
        activity_durations = dict(zip(default_activities, default_durations))
        bottlenecks_data = {}
        try:
            synapse_base = os.getenv("SYNAPSE_BASE_URL", "").strip().rstrip("/")
            log_id = process_model_id
            with httpx.Client(timeout=10.0) as client:
                bn_resp = client.get(
                    f"{synapse_base}/api/v3/synapse/process-mining/bottlenecks",
                    params={"case_id": case_id, "log_id": log_id},
                )
                if bn_resp.status_code == 200:
                    bottlenecks_data = bn_resp.json().get("data", {}) or {}
                    for b in bottlenecks_data.get("bottlenecks") or []:
                        act = b.get("activity")
                        if act and "avg_duration" in b:
                            activity_durations[act] = int(b.get("avg_duration", 86400))
        except Exception:
            pass

        original_bottleneck = ctx.get("bottleneck_activity") or (default_activities[1] if len(default_activities) > 1 else "승인")
        simulated_durations = dict(activity_durations)
        for ch in parameter_changes:
            act = (ch.get("activity") or "").strip()
            if not act or act not in simulated_durations:
                continue
            change_type = (ch.get("change_type") or "").strip().lower()
            if change_type == "duration" and ch.get("duration_change") is not None:
                new_d = simulated_durations[act] + int(ch["duration_change"])
                simulated_durations[act] = max(0, new_d)
            elif change_type == "resource" and ch.get("resource_change") is not None:
                factor = max(0.1, float(ch["resource_change"]))
                simulated_durations[act] = max(0, int(simulated_durations[act] / factor))
            # routing: 변형 빈도 변경은 여기서 스텁 처리

        original_cycle_time = sum(activity_durations.values())
        simulated_cycle_time = sum(simulated_durations.values())
        cycle_time_change = simulated_cycle_time - original_cycle_time
        cycle_time_change_pct = round((cycle_time_change / max(original_cycle_time, 1)) * 100, 1) if original_cycle_time else 0
        hours = abs(cycle_time_change) // 3600
        cycle_time_change_label = f"전체 주기 시간 {hours}시간 {'단축' if cycle_time_change <= 0 else '증가'}"

        by_activity = []
        for name in activity_durations:
            orig = activity_durations[name]
            sim = simulated_durations.get(name, orig)
            by_activity.append({
                "activity": name,
                "original_duration": orig,
                "simulated_duration": sim,
                "change": sim - orig,
                "is_on_critical_path": True,
            })

        simulated_bottleneck = max(simulated_durations, key=lambda a: simulated_durations[a])
        bottleneck_shift = None
        if original_bottleneck != simulated_bottleneck:
            bottleneck_shift = {
                "original": original_bottleneck,
                "new": simulated_bottleneck,
                "description": f"병목이 '{original_bottleneck}'에서 '{simulated_bottleneck}'(으)로 이동.",
            }

        sla_orig = 0.15
        sla_sim = max(0.0, sla_orig + (cycle_time_change_pct / 100.0) * 0.5)
        affected_kpis = [
            {"kpi": "avg_cycle_time", "kpi_label": "평균 주기 시간", "original": original_cycle_time, "simulated": simulated_cycle_time, "change_pct": cycle_time_change_pct},
            {"kpi": "sla_violation_rate", "kpi_label": "SLA 위반율", "original": sla_orig, "simulated": round(sla_sim, 2), "change_pct": round((sla_sim - sla_orig) / max(sla_orig, 0.01) * 100, 1)},
        ]
        critical_path = {"original": list(activity_durations), "simulated": list(simulated_durations)}

        simulation_id = self._new_id("sim-")
        return {
            "simulation_id": simulation_id,
            "process_model_id": process_model_id,
            "scenario_name": scenario_name,
            "computed_at": _now(),
            "original_cycle_time": original_cycle_time,
            "simulated_cycle_time": simulated_cycle_time,
            "cycle_time_change": cycle_time_change,
            "cycle_time_change_pct": cycle_time_change_pct,
            "cycle_time_change_label": cycle_time_change_label,
            "bottleneck_shift": bottleneck_shift,
            "affected_kpis": affected_kpis,
            "by_activity": by_activity,
            "critical_path": critical_path,
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
