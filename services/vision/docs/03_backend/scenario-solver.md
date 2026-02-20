# scipy 기반 시나리오 솔버 상세

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 3.2
> **근거**: ADR-001 (scipy.optimize 선택), 01_architecture/what-if-engine.md

---

## 이 문서가 답하는 질문

- 시나리오 솔버의 수학적 모델은 무엇인가?
- scipy.optimize의 어떤 메서드를 사용하며 왜인가?
- 목적함수와 제약조건은 어떻게 정의되는가?
- 의존성 그래프는 어떻게 구현되는가?
- 솔버 실패 시 어떻게 처리하는가?

---

## 1. 수학적 모델

### 1.1 최적화 문제 정의

```
최소화: -f(x)  (총 이해관계자 성과율의 음수 → 최대화)

Subject to:
  g_1(x) >= 0  (정책 최소 성과율 제약)
  g_2(x) >= 0  (운영자금 제약)
  g_3(x) >= 0  (DSCR 제약)
  h_1(x) = 0   (현금흐름 균형 등식)
  x_lower <= x <= x_upper  (파라미터 범위)
```

### 1.2 결정 변수 벡터 (x)

```python
# Decision variable vector structure
# x = [r_p, r_s, r_u, g, a_1, a_2, ..., a_n]
#
# r_p: priority obligation allocation rate (0.0 ~ 1.0)
# r_s: secured obligation allocation rate (0.0 ~ 1.0)
# r_u: unsecured obligation allocation rate (0.0 ~ 1.0)
# g:   EBITDA growth rate assumption (-0.5 ~ 5.0)
# a_i: asset disposal decision for asset i (0 or 1)

VARIABLE_INDICES = {
    "priority_rate": 0,
    "secured_rate": 1,
    "unsecured_rate": 2,
    "growth_rate": 3,
    # Dynamic: asset disposal flags start at index 4
}
```

### 1.3 목적함수

```python
def objective_function(x: np.ndarray, case_data: CaseFinancialData) -> float:
    """
    Objective: Maximize total stakeholder performance
    We negate because scipy minimizes.

    total_performance = priority_allocation + secured_allocation + unsecured_allocation
    """
    r_p, r_s, r_u = x[0], x[1], x[2]

    priority_allocation = r_p * case_data.total_priority_obligations
    secured_allocation = r_s * case_data.total_secured_obligations
    unsecured_allocation = r_u * case_data.total_unsecured_obligations

    total_performance = priority_allocation + secured_allocation + unsecured_allocation

    # Penalty for infeasible cash flow
    cashflows = compute_yearly_cashflows(x, case_data)
    negative_cf_penalty = sum(
        abs(cf) * 1e6 for cf in cashflows if cf < 0
    )

    return -(total_performance - negative_cf_penalty)
```

---

## 2. 제약조건 구현

### 2.1 법적 제약

```python
def legal_minimum_constraint(x: np.ndarray, case_data: CaseFinancialData) -> float:
    """
    Unsecured obligation rate must be >= minimum benchmark rate.
    Returns >= 0 when satisfied.
    """
    r_u = x[2]
    benchmark_rate = case_data.minimum_benchmark_rate  # From case data
    return r_u - benchmark_rate  # Must be >= 0
```

### 2.2 운영자금 제약

```python
def operating_fund_constraint(
    x: np.ndarray,
    case_data: CaseFinancialData,
    min_fund: int = 100_000_000  # 1억원
) -> float:
    """
    Cash balance at any year must be >= minimum operating fund.
    Returns >= 0 when satisfied (minimum cash balance - threshold).
    """
    cashflows = compute_yearly_cashflows(x, case_data)
    min_balance = min(cashflows)
    return min_balance - min_fund
```

### 2.3 DSCR 제약

```python
def dscr_constraint(x: np.ndarray, case_data: CaseFinancialData) -> float:
    """
    Debt Service Coverage Ratio must be >= 1.0 at every year.
    DSCR = (EBITDA - CapEx) / (Interest + Principal Repayment)
    """
    g = x[3]  # Growth rate
    dscr_values = []

    for year in range(1, case_data.execution_period + 1):
        ebitda = case_data.base_ebitda * (1 + g) ** year
        capex = case_data.annual_capex
        interest = compute_interest(x, case_data, year)
        principal = compute_principal_payment(x, case_data, year)

        if (interest + principal) > 0:
            dscr = (ebitda - capex) / (interest + principal)
            dscr_values.append(dscr)

    return min(dscr_values) - 1.0  # Must be >= 0
```

### 2.4 제약조건 빌더

```python
from scipy.optimize import NonlinearConstraint

def build_scipy_constraints(
    constraints: list[Constraint],
    case_data: CaseFinancialData
) -> list[dict]:
    """
    Convert domain constraints to scipy format.
    """
    scipy_constraints = []

    for c in constraints:
        if c.constraint_type == ConstraintType.LEGAL_MINIMUM:
            scipy_constraints.append({
                'type': 'ineq',
                'fun': lambda x: legal_minimum_constraint(x, case_data)
            })
        elif c.constraint_type == ConstraintType.OPERATING_FUND:
            scipy_constraints.append({
                'type': 'ineq',
                'fun': lambda x, min_v=c.value: operating_fund_constraint(
                    x, case_data, int(min_v)
                )
            })
        elif c.constraint_type == ConstraintType.DSCR:
            scipy_constraints.append({
                'type': 'ineq',
                'fun': lambda x: dscr_constraint(x, case_data)
            })

    return scipy_constraints
```

---

## 3. 의존성 그래프 구현

### 3.1 DAG 정의

```python
from collections import defaultdict
from graphlib import TopologicalSorter

class DependencyGraph:
    """
    Manages parameter dependencies for cascading recomputation.

    When interest_rate changes:
    interest_rate → interest_expense → annual_cashflow → allocation_capacity → allocation_rate
    """

    EDGES = {
        "interest_expense": {"interest_rate", "total_debt"},
        "revenue_forecast": {"ebitda_growth_rate", "base_revenue"},
        "operating_cost": {"operating_cost_ratio", "revenue_forecast"},
        "annual_cashflow": {"revenue_forecast", "interest_expense", "operating_cost"},
        "disposal_proceeds": {"asset_disposal_plan"},
        "cumulative_cashflow": {"annual_cashflow", "disposal_proceeds"},
        "operating_fund_reserve": {"operating_cost", "minimum_fund_ratio"},
        "allocation_capacity": {"cumulative_cashflow", "operating_fund_reserve"},
        "allocation_rate": {"allocation_capacity", "total_obligations"},
        "feasibility_score": {"allocation_rate", "dscr", "constraint_violations"},
    }

    def __init__(self):
        self.sorter = TopologicalSorter(self.EDGES)
        self.computation_order = list(self.sorter.static_order())

    def get_affected_nodes(self, changed_param: str) -> list[str]:
        """
        Return all nodes that need recomputation when a parameter changes.
        """
        affected = set()
        queue = [changed_param]

        reverse_edges = defaultdict(set)
        for node, deps in self.EDGES.items():
            for dep in deps:
                reverse_edges[dep].add(node)

        while queue:
            current = queue.pop(0)
            for dependent in reverse_edges.get(current, set()):
                if dependent not in affected:
                    affected.add(dependent)
                    queue.append(dependent)

        # Return in topological order
        return [n for n in self.computation_order if n in affected]
```

### 3.2 연쇄 재계산

```python
async def recompute_cascade(
    scenario: Scenario,
    changed_params: dict[str, Any],
    case_data: CaseFinancialData
) -> dict[str, Any]:
    """
    When parameters change, recompute all dependent values
    in topological order.
    """
    graph = DependencyGraph()
    computed = {**scenario.current_values, **changed_params}

    for param_name, new_value in changed_params.items():
        affected = graph.get_affected_nodes(param_name)

        for node in affected:
            computed[node] = COMPUTE_FUNCTIONS[node](computed, case_data)

    return computed

# Computation functions registry
COMPUTE_FUNCTIONS = {
    "interest_expense": lambda v, d: v["total_debt"] * v["interest_rate"] / 100,
    "revenue_forecast": lambda v, d: d.base_revenue * (1 + v["ebitda_growth_rate"] / 100),
    "operating_cost": lambda v, d: v["revenue_forecast"] * v["operating_cost_ratio"] / 100,
    "annual_cashflow": lambda v, d: v["revenue_forecast"] - v["operating_cost"] - v["interest_expense"],
    # ... more
}
```

---

## 4. 연도별 현금흐름 산출

```python
def compute_yearly_cashflows(
    x: np.ndarray,
    case_data: CaseFinancialData
) -> list[YearlyCashflow]:
    """
    Compute year-by-year cashflow projection for a scenario.
    """
    g = x[3]  # EBITDA growth rate
    period = case_data.execution_period
    cashflows = []

    cumulative_allocation = 0
    remaining_debt = case_data.total_debt

    for year in range(1, period + 1):
        # Revenue & EBITDA
        ebitda = case_data.base_ebitda * (1 + g) ** year
        revenue = case_data.base_revenue * (1 + g) ** year

        # Costs
        operating_cost = revenue * case_data.operating_cost_ratio
        interest = remaining_debt * case_data.interest_rate

        # Asset disposal (if scheduled this year)
        disposal = sum(
            a.estimated_value * (1 - a.disposal_cost_ratio)
            for a in case_data.asset_disposals
            if a.disposal_year == year
        )

        # Net cashflow
        net_cf = ebitda - operating_cost - interest + disposal

        # Repayment allocation
        allocation = compute_year_allocation(x, net_cf, year, case_data)
        cumulative_allocation += allocation
        remaining_debt -= allocation

        cashflows.append(YearlyCashflow(
            year=year,
            revenue=int(revenue),
            ebitda=int(ebitda),
            interest_expense=int(interest),
            operating_cost=int(operating_cost),
            disposal_proceeds=int(disposal),
            net_cashflow=int(net_cf),
            allocation_amount=int(allocation),
            cumulative_allocation=int(cumulative_allocation),
            cash_balance=int(net_cf - allocation),
            dscr=round((ebitda - case_data.annual_capex) / max(interest + allocation, 1), 2),
        ))

    return cashflows
```

---

## 5. 솔버 설정 및 실패 처리

### 5.1 솔버 설정

```python
SOLVER_CONFIG = {
    "method": "SLSQP",           # Sequential Least Squares Programming
    "options": {
        "maxiter": 1000,         # Maximum iterations
        "ftol": 1e-8,            # Function tolerance
        "disp": False,           # No verbose output
    },
    "timeout": 60,               # Seconds
}

# Alternative for linear problems
LINEAR_SOLVER_CONFIG = {
    "method": "linprog",         # For purely linear constraints
    "options": {
        "maxiter": 500,
    }
}
```

### 5.2 실패 사유 매핑

| scipy 결과 | Vision 에러 | 사용자 메시지 |
|-----------|------------|-------------|
| `result.success = False, "Inequality constraints incompatible"` | `SolverInfeasibleError` | "현재 제약조건으로는 실현 가능한 계획을 찾을 수 없습니다" |
| `result.success = False, "Iteration limit reached"` | `SolverConvergenceError` | "계산이 수렴하지 않았습니다. 초기 조건을 조정해 보세요" |
| `asyncio.TimeoutError` | `SolverTimeoutError` | "계산 시간이 60초를 초과했습니다" |
| `result.success = True, 하지만 음수 CF` | Warning | "계획은 수립 가능하나, N년차에 현금 부족이 예상됩니다" |

### 5.3 재시도 전략

```python
async def solve_with_retry(
    scenario: Scenario,
    case_data: CaseFinancialData,
    max_retries: int = 2
) -> ScenarioResult:
    """
    Retry with relaxed constraints if initial solve fails.
    """
    for attempt in range(max_retries + 1):
        try:
            return await solve_scenario(scenario, case_data)
        except SolverInfeasibleError:
            if attempt < max_retries:
                # Relax soft constraints
                scenario.constraints = [
                    c for c in scenario.constraints if c.is_hard
                ]
                logger.warning(
                    "solver_retry",
                    attempt=attempt + 1,
                    relaxed_constraints=True
                )
            else:
                raise
```

---

## 결정 사항 (Decisions)

- SLSQP 메서드 사용 (비선형 제약 지원, 중소 규모 문제에 적합)
- 최대 반복 1000회, 함수 허용 오차 1e-8
- 소프트 제약 완화 후 재시도 (최대 2회)

## 금지 사항 (Forbidden)

- 제약 없이 솔버 실행
- 동기 컨텍스트에서 솔버 호출 (반드시 asyncio.to_thread)
- 솔버 결과의 직접 수정 (재계산만 허용)

<!-- affects: 02_api/what-if-api.md, 06_data/database-schema.md -->
