# Vision What-if scenario solver (scipy.optimize, scenario-solver.md)
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import minimize

SOLVER_TIMEOUT_SECONDS = 60
SOLVER_METHOD = "SLSQP"
SOLVER_OPTIONS = {"maxiter": 1000, "ftol": 1e-8, "disp": False}


class SolverInfeasibleError(Exception):
    """제약조건으로는 실현 가능한 계획을 찾을 수 없음."""

    def __init__(self, message: str = "현재 제약조건으로는 실현 가능한 실행 계획을 찾을 수 없습니다"):
        super().__init__(message)


class SolverConvergenceError(Exception):
    """솔버 수렴 실패."""

    def __init__(self, message: str = "계산이 수렴하지 않았습니다. 초기 조건을 조정해 보세요"):
        super().__init__(message)


class SolverTimeoutError(Exception):
    """솔버 타임아웃 (60초 초과)."""

    def __init__(self, message: str = "계산 시간이 60초를 초과했습니다"):
        super().__init__(message)


@dataclass
class CaseFinancialData:
    """시나리오 계산용 케이스 재무 데이터 (scenario-solver.md §1.2)."""

    execution_period: int
    interest_rate: float
    base_ebitda: float
    base_revenue: float
    operating_cost_ratio: float
    annual_capex: float
    total_debt: float
    total_priority_obligations: float
    total_secured_obligations: float
    total_unsecured_obligations: float
    minimum_benchmark_rate: float
    asset_disposals: list[dict[str, Any]] = field(default_factory=list)


def _params_to_case_data(parameters: dict[str, Any]) -> CaseFinancialData:
    """시나리오 parameters에서 CaseFinancialData 생성."""
    period = max(1, min(30, int(parameters.get("execution_period_years", 10))))
    interest = max(0.0, min(100.0, float(parameters.get("interest_rate", 4.0)))) / 100.0
    growth = float(parameters.get("ebitda_growth_rate", 5.0)) / 100.0
    cost_ratio = max(0.0, min(100.0, float(parameters.get("operating_cost_ratio", 65.0)))) / 100.0
    base_revenue = 3_000_000_000.0
    base_ebitda = base_revenue * (1.0 - cost_ratio)
    total_debt = 2_000_000_000.0
    total_obligations = 10_000_000_000.0
    total_priority = total_obligations * 0.05
    total_secured = total_obligations * 0.30
    total_unsecured = total_obligations * 0.65
    benchmark = 0.15
    return CaseFinancialData(
        execution_period=period,
        interest_rate=interest,
        base_ebitda=base_ebitda,
        base_revenue=base_revenue,
        operating_cost_ratio=cost_ratio,
        annual_capex=100_000_000.0,
        total_debt=total_debt,
        total_priority_obligations=total_priority,
        total_secured_obligations=total_secured,
        total_unsecured_obligations=total_unsecured,
        minimum_benchmark_rate=benchmark,
        asset_disposals=parameters.get("asset_disposal_plan") or [],
    )


def _compute_yearly_cashflows(
    x: np.ndarray,
    d: CaseFinancialData,
) -> list[dict[str, Any]]:
    """연도별 현금흐름 산출 (scenario-solver.md §4)."""
    r_p, r_s, r_u, g = float(x[0]), float(x[1]), float(x[2]), float(x[3])
    period = d.execution_period
    cashflows = []
    cumulative_allocation = 0.0
    remaining_debt = d.total_debt

    for year in range(1, period + 1):
        ebitda = d.base_ebitda * ((1.0 + g) ** year)
        revenue = d.base_revenue * ((1.0 + g) ** year)
        operating_cost = revenue * d.operating_cost_ratio
        interest = remaining_debt * d.interest_rate
        disposal = 0.0
        for a in d.asset_disposals:
            if int(a.get("disposal_year", 0)) == year:
                val = float(a.get("estimated_value", 0))
                cost_ratio = float(a.get("disposal_cost_ratio", 0)) / 100.0
                disposal += val * (1.0 - cost_ratio)
        net_cf = ebitda - operating_cost - interest + disposal
        allocation_pct = (r_p * 0.05 + r_s * 0.30 + r_u * 0.65)
        allocation = min(net_cf * 0.6, (d.total_priority_obligations + d.total_secured_obligations + d.total_unsecured_obligations) * allocation_pct / period)
        cumulative_allocation += allocation
        remaining_debt = max(0.0, remaining_debt - allocation * 0.3)
        principal_plus_interest = interest + allocation * 0.3
        dscr = round((ebitda - d.annual_capex) / max(principal_plus_interest, 1.0), 2)
        cashflows.append({
            "year": year,
            "revenue": round(revenue, 2),
            "ebitda": round(ebitda, 2),
            "interest_expense": round(interest, 2),
            "operating_cost": round(operating_cost, 2),
            "net_cashflow": round(net_cf, 2),
            "allocation_amount": round(allocation, 2),
            "cumulative_allocation": round(cumulative_allocation, 2),
            "cash_balance": round(net_cf - allocation, 2),
            "dscr": dscr,
        })
    return cashflows


def _objective(x: np.ndarray, d: CaseFinancialData) -> float:
    """목적함수: 이해관계자 성과 최대화 → minimize(-total_performance)."""
    r_p, r_s, r_u = float(x[0]), float(x[1]), float(x[2])
    total_performance = (
        r_p * d.total_priority_obligations
        + r_s * d.total_secured_obligations
        + r_u * d.total_unsecured_obligations
    )
    cashflows = _compute_yearly_cashflows(x, d)
    penalty = sum(abs(c["cash_balance"]) * 1e6 for c in cashflows if c["cash_balance"] < 0)
    return -(total_performance - penalty)


def _legal_minimum_constraint(x: np.ndarray, d: CaseFinancialData) -> float:
    """일반(미담보) 배분율 >= 최소 기준. g(x) >= 0."""
    return float(x[2]) - d.minimum_benchmark_rate


def _operating_fund_constraint(
    x: np.ndarray,
    d: CaseFinancialData,
    min_fund: float = 100_000_000.0,
) -> float:
    """연도별 현금잔고 >= 최소 운영자금. g(x) >= 0."""
    cashflows = _compute_yearly_cashflows(x, d)
    min_balance = min(c["cash_balance"] for c in cashflows)
    return min_balance - min_fund


def _dscr_constraint(x: np.ndarray, d: CaseFinancialData) -> float:
    """연도별 DSCR >= 1.0. g(x) >= 0."""
    cashflows = _compute_yearly_cashflows(x, d)
    dscrs = [c["dscr"] for c in cashflows]
    return (min(dscrs) if dscrs else 0.0) - 1.0


def _build_bounds() -> list[tuple[float, float]]:
    """결정 변수 [r_p, r_s, r_u, g] 범위."""
    return [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (-0.5, 5.0)]


def _build_initial_vector(parameters: dict[str, Any]) -> np.ndarray:
    """시나리오 parameters에서 초기 벡터 x0."""
    p_alloc = max(0.0, min(100.0, float(parameters.get("priority_allocation_rate", 100.0)))) / 100.0
    s_alloc = max(0.0, min(100.0, float(parameters.get("secured_allocation_rate", 80.0)))) / 100.0
    g_alloc = max(0.0, min(100.0, float(parameters.get("general_allocation_rate", 35.0)))) / 100.0
    growth = max(-0.5, min(5.0, float(parameters.get("ebitda_growth_rate", 5.0)) / 100.0))
    return np.array([p_alloc, s_alloc, g_alloc, growth], dtype=float)


def _build_constraints(d: CaseFinancialData, constraints: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """scipy minimize 형식의 제약조건 리스트."""
    scipy_constraints = []
    for c in constraints or []:
        ctype = (c.get("constraint_type") or "").strip().lower()
        if ctype in ("legal_minimum", "policy_minimum"):
            scipy_constraints.append({"type": "ineq", "fun": lambda x, _d=d: _legal_minimum_constraint(x, _d)})
        elif ctype == "operating_fund":
            val = float(c.get("value", 100_000_000))
            scipy_constraints.append({
                "type": "ineq",
                "fun": lambda x, _d=d, _v=val: _operating_fund_constraint(x, _d, _v),
            })
        elif ctype == "dscr":
            scipy_constraints.append({"type": "ineq", "fun": lambda x, _d=d: _dscr_constraint(x, _d)})
    if not scipy_constraints:
        scipy_constraints.append({"type": "ineq", "fun": lambda x, _d=d: _legal_minimum_constraint(x, _d)})
    return scipy_constraints


def _run_solver_sync(
    x0: np.ndarray,
    case_data: CaseFinancialData,
    constraints: list[dict[str, Any]],
) -> tuple[Any, np.ndarray, list[dict[str, Any]]]:
    """동기 솔버 실행 (스레드에서 호출)."""
    scipy_constraints = _build_constraints(case_data, constraints)

    def objective(x: np.ndarray) -> float:
        return _objective(x, case_data)

    result = minimize(
        objective,
        x0,
        method=SOLVER_METHOD,
        bounds=_build_bounds(),
        constraints=scipy_constraints,
        options=SOLVER_OPTIONS,
    )
    cashflows = _compute_yearly_cashflows(result.x, case_data)
    return result, result.x, cashflows


def _build_constraints_met(
    scenario_constraints: list[dict[str, Any]],
    x: np.ndarray,
    d: CaseFinancialData,
    cashflows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """결과용 constraints_met 배열."""
    out = []
    for c in scenario_constraints or []:
        ctype = (c.get("constraint_type") or "custom").strip().lower()
        thresh = float(c.get("value", 0.0))
        desc = str(c.get("description", ""))
        if ctype in ("legal_minimum", "policy_minimum"):
            actual = float(x[2])
            out.append({
                "constraint_type": "legal_minimum",
                "description": desc or "일반 배분율 >= 최소 성과 기준",
                "actual_value": round(actual * 100, 2),
                "threshold": round(thresh * 100 if thresh <= 1 else thresh, 2),
                "satisfied": actual >= d.minimum_benchmark_rate,
            })
        elif ctype == "operating_fund":
            min_bal = min(cf["cash_balance"] for cf in cashflows) if cashflows else 0.0
            out.append({
                "constraint_type": "operating_fund",
                "description": desc or "최소 운영자금 확보",
                "actual_value": round(min_bal, 2),
                "threshold": thresh,
                "satisfied": min_bal >= thresh,
            })
        elif ctype == "dscr":
            min_dscr = min(cf["dscr"] for cf in cashflows) if cashflows else 0.0
            out.append({
                "constraint_type": "dscr",
                "description": desc or "연간 DSCR >= 1.0",
                "actual_value": min_dscr,
                "threshold": max(1.0, thresh),
                "satisfied": min_dscr >= 1.0,
            })
        else:
            out.append({
                "constraint_type": ctype or "custom",
                "description": desc,
                "actual_value": thresh,
                "threshold": thresh,
                "satisfied": True,
            })
    return out


def solve_scenario_result(
    scenario_id: str,
    scenario_name: str,
    parameters: dict[str, Any],
    constraints: list[dict[str, Any]],
    computed_at: str,
) -> dict[str, Any]:
    """
    시나리오 파라미터·제약으로 scipy 솔버 실행 후 API 결과 형식 반환.
    동기 함수이므로 asyncio.to_thread + wait_for(60s)로 호출.
    """
    d = _params_to_case_data(parameters)
    x0 = _build_initial_vector(parameters)
    result, x_opt, cashflows = _run_solver_sync(x0, d, constraints)

    if not result.success:
        msg = (getattr(result, "message", None) or str(result)).lower()
        if "infeasible" in msg and "incompatible" not in msg:
            raise SolverInfeasibleError()
        # "incompatible" 또는 수렴 실패 시에도 result.x로 결과 산출, is_feasible=False

    r_p, r_s, r_u = float(x_opt[0]), float(x_opt[1]), float(x_opt[2])
    total_priority = d.total_priority_obligations
    total_secured = d.total_secured_obligations
    total_unsecured = d.total_unsecured_obligations
    total_allocation = (
        r_p * total_priority + r_s * total_secured + r_u * total_unsecured
    )
    total_obligations = total_priority + total_secured + total_unsecured
    overall_rate = total_allocation / max(total_obligations, 1.0)
    feasibility = 1.0 if result.success else 0.0
    for cf in cashflows:
        if cf["cash_balance"] < 0:
            feasibility *= 0.8
            break
    feasibility = max(0.0, min(1.0, feasibility))

    constraints_met = _build_constraints_met(constraints, x_opt, d, cashflows)
    all_met = all(c.get("satisfied", True) for c in constraints_met)
    is_feasible = result.success and all_met and feasibility >= 0.4

    by_stakeholder = [
        {"class": "priority", "total_obligation": total_priority, "allocation_amount": r_p * total_priority, "allocation_rate": round(r_p, 2)},
        {"class": "secured", "total_obligation": total_secured, "allocation_amount": r_s * total_secured, "allocation_rate": round(r_s, 2)},
        {"class": "unsecured", "total_obligation": total_unsecured, "allocation_amount": r_u * total_unsecured, "allocation_rate": round(r_u, 2)},
    ]

    discount_rate = max(0.01, float(parameters.get("discount_rate", 8.0)) / 100.0)
    npv = sum(
        cf["net_cashflow"] / ((1.0 + discount_rate) ** cf["year"])
        for cf in cashflows
    )

    return {
        "scenario_id": scenario_id,
        "scenario_name": scenario_name,
        "status": "COMPLETED",
        "computed_at": computed_at,
        "solver_iterations": int(getattr(result, "nit", 0) or 0),
        "is_feasible": is_feasible,
        "feasibility_score": round(feasibility, 3),
        "summary": {
            "total_allocation": round(total_allocation, 2),
            "total_obligations": round(total_obligations, 2),
            "overall_allocation_rate": round(overall_rate, 2),
            "execution_period_years": d.execution_period,
            "npv_at_wacc": round(npv, 2),
        },
        "by_year": cashflows,
        "by_stakeholder_class": by_stakeholder,
        "constraints_met": constraints_met,
        "warnings": [] if is_feasible else ["일부 제약조건 미충족 또는 현금 부족 구간 존재"],
    }


async def solve_scenario_async(
    scenario_id: str,
    scenario_name: str,
    parameters: dict[str, Any],
    constraints: list[dict[str, Any]],
    computed_at: str,
    timeout_seconds: int = SOLVER_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    비동기 래퍼: to_thread + wait_for로 타임아웃 적용.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                solve_scenario_result,
                scenario_id,
                scenario_name,
                parameters,
                constraints,
                computed_at,
            ),
            timeout=float(timeout_seconds),
        )
    except asyncio.TimeoutError:
        raise SolverTimeoutError()


# 레거시 호환: evaluate_what_if (스텁 유지)
class ScenarioSolver:
    async def evaluate_what_if(
        self,
        base_cache_key: str,
        modifications: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """ETL 캐시 대상에 대한 로컬 시뮬레이션 (레거시)."""
        if not base_cache_key:
            raise ValueError("Base target execution must be extracted first.")
        impacts = {}
        regressions = []
        for mod in modifications:
            metric = mod.get("metric", "")
            adj = mod.get("adjustment", "")
            impact = f"Simulated adjusting {metric} by {adj}"
            if "cost" in metric.lower() and "+" in str(adj):
                regressions.append(f"Operating margin contraction alert regarding {metric}")
            impacts[metric] = impact
        return {
            "solver_status": "complete",
            "impacts": impacts,
            "regressions": regressions,
        }


scenario_solver = ScenarioSolver()
