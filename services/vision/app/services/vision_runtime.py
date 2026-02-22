from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
import os
from typing import Any

from app.services.vision_state_store import VisionStateStore

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000)}-{next(self._id_seq)}"

    def clear(self) -> None:
        self.what_if_by_case.clear()
        self.cubes.clear()
        self.etl_jobs.clear()
        self.root_cause_by_case.clear()
        self.store.clear()

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
        max_root_causes = min(max(int(payload.get("max_root_causes", 5)), 1), 10)
        root_cause_templates = [
            {
                "rank": 1,
                "variable": "debt_ratio",
                "variable_label": "부채비율",
                "shap_value": 0.35,
                "contribution_pct": 35.0,
                "actual_value": 1.50,
                "critical_threshold": 1.00,
                "description": "부채비율이 임계치를 상회해 현금흐름 압박이 발생했습니다.",
                "causal_chain": ["차입 증가", "이자비용 상승", "현금흐름 악화"],
                "confidence": 0.89,
            },
            {
                "rank": 2,
                "variable": "ebitda",
                "variable_label": "EBITDA",
                "shap_value": 0.28,
                "contribution_pct": 28.0,
                "actual_value": 600000000,
                "critical_threshold": 1500000000,
                "description": "EBITDA 저하가 상환여력 부족으로 연결되었습니다.",
                "causal_chain": ["원가 상승", "마진 축소", "현금부족"],
                "confidence": 0.85,
            },
            {
                "rank": 3,
                "variable": "interest_rate_env",
                "variable_label": "금리 환경",
                "shap_value": 0.18,
                "contribution_pct": 18.0,
                "actual_value": 5.5,
                "critical_threshold": None,
                "description": "외부 금리 상승이 이자비용 증가를 유발했습니다.",
                "causal_chain": ["기준금리 상승", "변동금리 부담 증가"],
                "confidence": 0.78,
            },
        ][:max_root_causes]
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
            "overall_confidence": 0.82,
            "root_causes": root_cause_templates,
            "explanation": "핵심 근본원인은 부채비율 상승, EBITDA 저하, 금리환경 악화의 결합입니다.",
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
            "root_causes": analysis["root_causes"],
            "explanation": analysis["explanation"],
        }

    def run_counterfactual(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        analysis = self.get_root_cause_analysis(case_id)
        if not analysis or analysis["status"] != "COMPLETED":
            raise KeyError("root cause analysis not ready")
        actual_value = float(payload["actual_value"])
        counterfactual_value = float(payload["counterfactual_value"])
        if actual_value == 0:
            delta_pct = 0.0
        else:
            delta_pct = ((actual_value - counterfactual_value) / abs(actual_value)) * 100.0
        failure_probability_before = 0.78
        impact = max(0.0, min(0.6, delta_pct / 200.0))
        failure_probability_after = round(max(0.01, failure_probability_before - impact), 3)
        return {
            "analysis_id": analysis["analysis_id"],
            "case_id": case_id,
            "variable": payload["variable"],
            "actual_value": actual_value,
            "counterfactual_value": counterfactual_value,
            "question": payload.get("question"),
            "estimated_failure_probability_before": failure_probability_before,
            "estimated_failure_probability_after": failure_probability_after,
            "risk_reduction_pct": round((failure_probability_before - failure_probability_after) * 100.0, 2),
            "computed_at": _now(),
        }


vision_runtime = VisionRuntime()
