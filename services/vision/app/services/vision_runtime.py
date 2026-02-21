from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VisionRuntime:
    def __init__(self) -> None:
        self.what_if_by_case: dict[str, dict[str, dict[str, Any]]] = {}
        self.cubes: dict[str, dict[str, Any]] = {}
        self.etl_jobs: dict[str, dict[str, Any]] = {}
        self._id_seq = count(1)

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000)}-{next(self._id_seq)}"

    def clear(self) -> None:
        self.what_if_by_case.clear()
        self.cubes.clear()
        self.etl_jobs.clear()

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
        return scenario

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
        return cube


vision_runtime = VisionRuntime()
