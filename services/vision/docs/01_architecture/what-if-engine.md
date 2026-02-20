# What-if 시뮬레이션 엔진 상세 설계

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **Phase**: 3.2
> **근거**: ADR-001 (scipy.optimize 선택), 00_overview/system-overview.md

---

## 이 문서가 답하는 질문

- What-if 시뮬레이션은 어떤 구조로 동작하는가?
- 시나리오 솔버의 입력/출력/제약조건은 무엇인가?
- 의존성 그래프 연산은 어떻게 수행되는가?
- 결과 비교(토네이도 차트, 전환점 분석)는 어떻게 구현되는가?
- 프론트엔드 시나리오 빌더와의 데이터 흐름은?
- 프로세스 시간축 시뮬레이션은 어떻게 Synapse 데이터를 활용하는가?

---

## 1. 엔진 개요

### 1.1 해결하는 비즈니스 문제

비즈니스 전략 수립 시 프로세스 분석가는 다양한 운영 시나리오를 비교해야 한다.

- "8년 계획과 12년 계획 중 어떤 것이 이해관계자 만족도가 높을까?"
- "금리가 1% 오르면 수익 계획이 유지되는가?"
- "주요 자산을 매각하면 KPI가 어떻게 변하는가?"

현재는 이 계산을 수작업(엑셀)으로 하며, 시나리오가 3개만 되어도 수일이 소요된다.

### 1.2 파이프라인

```
┌─ What-if 시뮬레이션 파이프라인 ────────────────────────────────┐
│                                                                 │
│  1. 시나리오 정의                                               │
│  ├─ 기본 시나리오 (현재 가정)                                   │
│  ├─ 낙관 시나리오 (+10% EBITDA, 낮은 WACC)                     │
│  ├─ 비관 시나리오 (-15% EBITDA, 금리 상승)                     │
│  ├─ 스트레스 테스트 (자산 급매, 조기 집행)                      │
│  └─ 사용자 정의 시나리오 (UI 슬라이더)                          │
│          │                                                      │
│          ▼                                                      │
│  2. 제약조건 정의                                               │
│  ├─ 정책 제약: 최소 성과율 >= 최소 성과 기준                    │
│  ├─ 운영 제약: 대상 조직 운영자금 >= 최소 유지액               │
│  ├─ 시간 제약: 실행 기간 <= 최대 연한                          │
│  └─ 재무 제약: DSCR >= 1.0, 부채비율 <= 목표치                 │
│          │                                                      │
│          ▼                                                      │
│  3. 의존성 그래프 연산                                          │
│  ├─ 변수 간 영향 관계 매핑 (금리 → 이자비용 → 현금흐름)       │
│  ├─ 파라미터 변경 시 연쇄 재계산                                │
│  └─ 위상 정렬(Topological Sort)로 계산 순서 결정               │
│          │                                                      │
│          ▼                                                      │
│  4. 다중 시나리오 솔버 (scipy.optimize)                         │
│  ├─ 각 시나리오별 제약 충족 여부 판정                           │
│  ├─ 목적함수: 이해관계자 성과율 최대화                          │
│  ├─ minimize(method='SLSQP') 또는 linprog                      │
│  └─ 시나리오당 연도별 현금흐름 산출                             │
│          │                                                      │
│          ▼                                                      │
│  5. 결과 비교 및 시각화                                         │
│  ├─ 시나리오별: 실현가능성 점수, 총 집행액, 계획 기간           │
│  ├─ 비교표: 시나리오 | 1차년도CF | 10차년도CF | 이해관계자별 성과│
│  ├─ 토네이도 차트 (각 파라미터 민감도)                          │
│  └─ 전환점 분석 ("성장률 몇 %에서 계획 실패하는가?")            │
│          │                                                      │
│          ▼                                                      │
│  6. 의사결정 지원                                               │
│  ├─ 최적 시나리오 추천 (실현가능성 + 이해관계자 만족도 최대화)  │
│  ├─ 전환점 식별 (어느 시점에서 계획이 실패하는가?)              │
│  └─ 시나리오 비교 보고서 PDF 내보내기                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 데이터 모델

### 2.1 시나리오 상태 머신

```
DRAFT → READY → COMPUTING → COMPLETED
                    │              │
                    ▼              ▼
                 FAILED        ARCHIVED
```

| 상태 | 설명 | 전이 조건 |
|------|------|----------|
| DRAFT | 시나리오 생성, 파라미터 편집 중 | 사용자 생성 시 |
| READY | 파라미터 확정, 계산 대기 | 필수 파라미터 충족 시 |
| COMPUTING | 솔버 실행 중 | compute 요청 시 |
| COMPLETED | 계산 완료, 결과 조회 가능 | 솔버 정상 종료 시 |
| FAILED | 계산 실패 | 타임아웃, 제약 불만족 등 |
| ARCHIVED | 보관 (더 이상 수정 불가) | 사용자 아카이브 시 |

### 2.2 시나리오 데이터 구조

```python
# Pydantic Schema: ScenarioCreate
class ScenarioCreate(BaseModel):
    scenario_name: str                    # "10년 실행 낙관 시나리오"
    scenario_type: ScenarioType           # BASELINE | OPTIMISTIC | PESSIMISTIC | STRESS | CUSTOM
    base_scenario_id: UUID | None = None  # 복사 원본 (없으면 케이스 현재값 기반)
    description: str | None = None

# Pydantic Schema: ScenarioParameters
class ScenarioParameters(BaseModel):
    execution_period_years: int           # 실행 기간 (연)
    interest_rate: Decimal                # 적용 금리 (%)
    ebitda_growth_rate: Decimal           # EBITDA 성장률 (%)
    asset_disposal_plan: list[AssetDisposal] | None  # 자산 매각 계획
    operating_cost_ratio: Decimal         # 운영비 비율 (%)
    discount_rate: Decimal                # 할인율 (WACC)
    priority_allocation_rate: Decimal     # 우선 배분율 (%)
    secured_allocation_rate: Decimal      # 담보 배분율 (%)
    general_allocation_rate: Decimal      # 일반 배분율 (%)
    custom_overrides: dict[str, Any] | None  # 추가 커스텀 파라미터

class AssetDisposal(BaseModel):
    asset_id: UUID
    disposal_year: int                    # 매각 예정 연차
    estimated_value: int                  # 예상 매각가 (원)
    disposal_cost_ratio: Decimal          # 매각 비용 비율 (%)
```

### 2.3 제약조건 정의

```python
class Constraint(BaseModel):
    constraint_type: ConstraintType
    parameter_path: str                   # "allocation.general_rate"
    operator: str                         # ">=", "<=", "==", "between"
    value: Decimal | list[Decimal]
    description: str                      # "일반 배분율 >= 최소 성과 기준"
    is_hard: bool = True                  # True: 반드시 충족, False: 가급적 충족

class ConstraintType(str, Enum):
    POLICY_MINIMUM = "policy_minimum"     # 정책 최소 성과율
    OPERATING_FUND = "operating_fund"     # 운영자금 확보
    TIME_LIMIT = "time_limit"            # 실행 기간 제한
    DSCR = "dscr"                         # Debt Service Coverage Ratio
    DEBT_RATIO = "debt_ratio"             # 부채비율 목표
    CUSTOM = "custom"                     # 사용자 정의
```

---

## 3. 시나리오 솔버 상세

### 3.1 의존성 그래프

파라미터 변경이 결과에 미치는 영향을 위상 정렬(DAG)로 계산한다.

```
금리 변동 ──→ 이자 비용 ──→ 연간 현금흐름 ──→ 집행 가능액
                                    ↑                    │
EBITDA 성장률 ──→ 매출 예측 ────────┘                    │
                                                          ▼
자산 매각 ──→ 일시 현금 유입 ──→ 누적 현금흐름 ──→ 성과율
                                                          │
운영비 비율 ──→ 운영 비용 ──→ 순현금흐름 ────────────────┘
```

```python
# Dependency graph definition
DEPENDENCY_GRAPH = {
    "interest_expense": ["interest_rate", "total_debt"],
    "revenue_forecast": ["ebitda_growth_rate", "base_revenue"],
    "annual_cashflow": ["revenue_forecast", "interest_expense", "operating_cost"],
    "operating_cost": ["operating_cost_ratio", "revenue_forecast"],
    "disposal_proceeds": ["asset_disposal_plan"],
    "cumulative_cashflow": ["annual_cashflow", "disposal_proceeds"],
    "allocation_capacity": ["cumulative_cashflow", "operating_fund_reserve"],
    "performance_rate": ["allocation_capacity", "total_obligations"],
}
```

### 3.2 솔버 실행

```python
from scipy.optimize import minimize, LinearConstraint
import numpy as np

async def solve_scenario(
    scenario: Scenario,
    case_data: CaseFinancialData,
    constraints: list[Constraint],
    timeout: int = 60
) -> ScenarioResult:
    """
    Solve a single scenario using constrained optimization.

    Objective: Maximize total stakeholder performance rate
    Subject to: Policy, operational, and financial constraints
    """
    # 1. Build initial parameter vector
    x0 = build_initial_vector(scenario.parameters, case_data)

    # 2. Build constraint matrices from Constraint objects
    scipy_constraints = []
    for c in constraints:
        if c.is_hard:
            scipy_constraints.append(
                build_scipy_constraint(c, case_data)
            )

    # 3. Define bounds for each parameter
    bounds = build_parameter_bounds(scenario.parameters)

    # 4. Define objective function (negative because scipy minimizes)
    def objective(x):
        cashflows = compute_cashflows(x, case_data)
        total_performance = sum(cashflows.allocation_by_year)
        return -total_performance  # Negate for minimization

    # 5. Run optimizer with timeout
    result = await asyncio.wait_for(
        asyncio.to_thread(
            minimize,
            objective,
            x0,
            method='SLSQP',
            bounds=bounds,
            constraints=scipy_constraints,
            options={'maxiter': 1000, 'ftol': 1e-8}
        ),
        timeout=timeout
    )

    # 6. Build result
    if result.success:
        return build_scenario_result(result, scenario, case_data)
    else:
        raise SolverFailedError(f"Solver did not converge: {result.message}")
```

### 3.3 민감도 분석 (토네이도 차트 데이터)

```python
async def compute_sensitivity(
    scenario_id: UUID,
    parameters_to_vary: list[str],
    variation_pct: Decimal = Decimal("0.10")  # +/- 10%
) -> SensitivityResult:
    """
    For each parameter, compute impact of +/- variation on key metrics.
    Returns data for tornado chart visualization.
    """
    baseline = await get_scenario_result(scenario_id)
    sensitivities = []

    for param in parameters_to_vary:
        base_value = getattr(baseline.parameters, param)

        # High scenario (+10%)
        high_params = baseline.parameters.copy()
        setattr(high_params, param, base_value * (1 + variation_pct))
        high_result = await solve_with_params(high_params)

        # Low scenario (-10%)
        low_params = baseline.parameters.copy()
        setattr(low_params, param, base_value * (1 - variation_pct))
        low_result = await solve_with_params(low_params)

        sensitivities.append(SensitivityItem(
            parameter=param,
            base_value=base_value,
            high_value=high_result.total_performance,
            low_value=low_result.total_performance,
            impact=abs(high_result.total_performance - low_result.total_performance),
        ))

    # Sort by impact descending (for tornado chart ordering)
    sensitivities.sort(key=lambda s: s.impact, reverse=True)
    return SensitivityResult(items=sensitivities)
```

### 3.4 전환점 분석 (Breakeven Analysis)

```python
async def find_breakeven(
    scenario_id: UUID,
    parameter: str,
    threshold_metric: str = "is_feasible",
    search_range: tuple[Decimal, Decimal] = (Decimal("-0.50"), Decimal("0.50"))
) -> BreakevenResult:
    """
    Binary search to find the parameter value where the plan
    transitions from feasible to infeasible.

    Example: "At what EBITDA growth rate does the plan fail?"
    """
    low, high = search_range
    precision = Decimal("0.001")  # 0.1% precision

    while (high - low) > precision:
        mid = (low + high) / 2
        test_params = build_params_with_override(scenario_id, parameter, mid)
        result = await solve_with_params(test_params)

        if result.is_feasible:
            low = mid  # Plan still works, push further
        else:
            high = mid  # Plan fails, come back

    return BreakevenResult(
        parameter=parameter,
        breakeven_value=mid,
        description=f"{parameter}이(가) {mid:.1%}일 때 계획이 전환됨",
    )
```

---

## 4. 시나리오 비교

### 4.1 비교 테이블 구조

```json
{
  "comparison": {
    "scenarios": [
      {
        "id": "uuid-1",
        "name": "8년 낙관",
        "feasibility_score": 0.85,
        "total_allocation": 5200000000,
        "execution_period_years": 8,
        "by_year": [
          {"year": 1, "cashflow": 650000000, "allocation": 520000000},
          {"year": 2, "cashflow": 690000000, "allocation": 552000000}
        ],
        "by_stakeholder_class": [
          {"class": "secured", "rate": 0.95, "amount": 2850000000},
          {"class": "general", "rate": 0.35, "amount": 2100000000},
          {"class": "priority", "rate": 1.00, "amount": 250000000}
        ]
      }
    ],
    "recommendation": {
      "best_scenario_id": "uuid-1",
      "reason": "실현가능성 85%로 가장 높으며, 일반 배분율 35%로 정책 최소 충족"
    },
    "tornado_chart_data": { },
    "breakeven_points": [ ]
  }
}
```

---

## 5. 프로세스 시간축 시뮬레이션

### 5.1 해결하는 비즈니스 문제

Synapse 프로세스 마이닝 엔진이 시간축(temporal) 데이터와 프로세스 의존 그래프를 제공함에 따라, Vision은 **프로세스 활동 단위의 What-if 시뮬레이션**을 지원한다.

- "승인 프로세스를 4시간→2시간으로 단축하면 전체 주기 시간은?"
- "검토 인력을 2배로 늘리면 병목이 해소되는가?"
- "SLA 기준을 24시간→12시간으로 강화하면 위반율이 어떻게 변하는가?"

### 5.2 데이터 소스: Synapse Process Mining API (pm4py 기반)

Vision은 Synapse로부터 다음 데이터를 REST API로 수신한다.

| Synapse API | 데이터 | Vision 사용 목적 |
|-------------|--------|-----------------|
| `GET /api/v1/process-models/{id}` | 프로세스 모델 (활동 목록, 의존 그래프) | 시간 변경의 연쇄 영향 계산 |
| `GET /api/v1/process-models/{id}/statistics` | 활동별 소요시간 통계 (avg, p50, p95) | 시뮬레이션 기준값 |
| `GET /api/v1/process-models/{id}/bottlenecks` | 병목 활동 및 대기시간 | 시뮬레이션 우선순위 식별 |
| `GET /api/v1/process-models/{id}/variants` | 프로세스 변형별 경로 및 빈도 | 변형별 영향 분석 |

### 5.3 시나리오 타입: ProcessTemporalScenario

```python
class ProcessTemporalScenario(BaseModel):
    """Process Mining 기반 시간축 시뮬레이션 시나리오"""
    scenario_name: str                          # "승인 시간 단축 시나리오"
    scenario_type: Literal["PROCESS_TEMPORAL"]   # 고정값
    process_model_id: UUID                       # Synapse 프로세스 모델 ID
    description: str | None = None

    parameter_changes: list[ProcessParameterChange]
    sla_threshold: timedelta | None = None       # SLA 기준 변경 시

class ProcessParameterChange(BaseModel):
    """개별 활동의 파라미터 변경"""
    activity: str                   # "승인" | "검토" | "배송"
    change_type: ProcessChangeType  # DURATION | RESOURCE | ROUTING
    duration_change: int | None = None      # seconds (-7200 = 2시간 단축)
    resource_change: float | None = None    # 배율 (2.0 = 2배 증가)
    routing_probability: float | None = None # 라우팅 확률 변경 (0.0~1.0)

class ProcessChangeType(str, Enum):
    DURATION = "duration"       # 활동 소요시간 변경
    RESOURCE = "resource"       # 자원 배분 변경 (인력, 설비 등)
    ROUTING = "routing"         # 프로세스 분기 확률 변경
```

### 5.4 시뮬레이션 파이프라인

```
┌─ 프로세스 시간축 시뮬레이션 파이프라인 ──────────────────────────┐
│                                                                 │
│  1. Synapse에서 프로세스 모델 로드                              │
│  ├─ 활동 의존 그래프 (DAG)                                     │
│  ├─ 활동별 소요시간 분포 (avg, p50, p95, std)                  │
│  └─ 현재 병목 정보                                              │
│          │                                                      │
│          ▼                                                      │
│  2. 파라미터 변경 적용                                          │
│  ├─ 활동 소요시간 오버라이드                                    │
│  ├─ 자원 변경 → 대기시간 재계산 (큐잉 이론)                   │
│  └─ 라우팅 변경 → 변형별 빈도 재분배                           │
│          │                                                      │
│          ▼                                                      │
│  3. 의존 그래프 기반 연쇄 재계산                                │
│  ├─ 위상 정렬로 계산 순서 결정                                  │
│  ├─ 병렬 활동: max(변경된 활동들) → 구간 소요시간              │
│  ├─ 순차 활동: sum(변경된 활동들) → 구간 소요시간              │
│  └─ 전체 주기 시간 = 임계 경로(Critical Path) 재계산           │
│          │                                                      │
│          ▼                                                      │
│  4. 결과 산출                                                   │
│  ├─ original_cycle_time vs simulated_cycle_time                │
│  ├─ 병목 이동 감지 (bottleneck_shift)                          │
│  ├─ 변형별 주기 시간 변화                                      │
│  ├─ SLA 위반율 변화 예측                                       │
│  └─ 영향받는 KPI 목록                                          │
│          │                                                      │
│          ▼                                                      │
│  5. 시각화 데이터 생성                                          │
│  ├─ 프로세스 맵 (변경 전/후 비교)                              │
│  ├─ 활동별 시간 변화 워터폴 차트                               │
│  └─ 병목 이동 하이라이트                                       │
└─────────────────────────────────────────────────────────────────┘
```

### 5.5 핵심 연산: 임계 경로 재계산

```python
from collections import defaultdict
from typing import Any

async def simulate_process_temporal(
    process_model: ProcessModel,        # Synapse에서 로드
    parameter_changes: list[ProcessParameterChange],
    sla_threshold: timedelta | None = None
) -> ProcessSimulationResult:
    """
    Process dependency graph에서 parameter_changes를 적용하고
    전체 주기 시간을 재계산한다.

    핵심: Synapse 프로세스 의존 그래프(DAG)를 사용하여
    활동 시간 변경의 연쇄 영향(cascade)을 정확히 계산.
    """
    # 1. Build modified activity durations
    durations = {a.name: a.avg_duration for a in process_model.activities}
    for change in parameter_changes:
        if change.change_type == ProcessChangeType.DURATION:
            durations[change.activity] += change.duration_change
        elif change.change_type == ProcessChangeType.RESOURCE:
            # Resource change affects queue wait time (M/M/c model)
            activity = process_model.get_activity(change.activity)
            new_wait = compute_queue_wait(
                arrival_rate=activity.arrival_rate,
                service_rate=activity.service_rate,
                servers=int(activity.current_resources * change.resource_change)
            )
            durations[change.activity] = activity.processing_time + new_wait

    # 2. Compute critical path with modified durations
    original_critical_path = compute_critical_path(
        process_model.dependency_graph,
        {a.name: a.avg_duration for a in process_model.activities}
    )
    simulated_critical_path = compute_critical_path(
        process_model.dependency_graph,
        durations
    )

    # 3. Detect bottleneck shift
    original_bottleneck = identify_bottleneck(original_critical_path)
    simulated_bottleneck = identify_bottleneck(simulated_critical_path)
    bottleneck_shift = None
    if original_bottleneck != simulated_bottleneck:
        bottleneck_shift = BottleneckShift(
            original=original_bottleneck,
            new=simulated_bottleneck,
            description=f"병목이 '{original_bottleneck}'에서 '{simulated_bottleneck}'(으)로 이동"
        )

    # 4. Compute affected KPIs
    affected_kpis = compute_affected_kpis(
        original_cycle_time=original_critical_path.total_time,
        simulated_cycle_time=simulated_critical_path.total_time,
        sla_threshold=sla_threshold,
        process_model=process_model
    )

    return ProcessSimulationResult(
        original_cycle_time=original_critical_path.total_time,
        simulated_cycle_time=simulated_critical_path.total_time,
        cycle_time_change=simulated_critical_path.total_time - original_critical_path.total_time,
        bottleneck_shift=bottleneck_shift,
        affected_kpis=affected_kpis,
        by_activity=[
            ActivityTimeChange(
                activity=name,
                original_duration=process_model.get_activity(name).avg_duration,
                simulated_duration=durations[name],
            )
            for name in durations
        ],
    )
```

### 5.6 사용 예시

**질문**: "승인 프로세스를 4시간→2시간으로 단축하면 전체 주기 시간은?"

```json
{
  "scenario_name": "승인 시간 단축 시나리오",
  "scenario_type": "PROCESS_TEMPORAL",
  "process_model_id": "a1b2c3d4-...",
  "parameter_changes": [
    {
      "activity": "승인",
      "change_type": "duration",
      "duration_change": -7200
    }
  ]
}
```

**결과 예시**:

```json
{
  "original_cycle_time": 259200,
  "simulated_cycle_time": 252000,
  "cycle_time_change": -7200,
  "cycle_time_change_label": "전체 주기 시간 2시간 단축 (3일 → 2일 22시간)",
  "bottleneck_shift": null,
  "affected_kpis": [
    {"kpi": "avg_cycle_time", "original": 259200, "simulated": 252000, "change_pct": -2.8},
    {"kpi": "sla_violation_rate", "original": 0.15, "simulated": 0.12, "change_pct": -20.0}
  ]
}
```

---

## 6. 프론트엔드 연동

### 5.1 시나리오 빌더 UI 데이터 흐름

```
┌─ Canvas (React) ────────────────────────────────────────────┐
│                                                              │
│  1. 시나리오 생성 (POST /what-if/create)                    │
│     → 시나리오 카드 추가                                    │
│                                                              │
│  2. 파라미터 슬라이더 조작                                   │
│     → PUT /what-if/{id} (autosave, debounce 500ms)          │
│                                                              │
│  3. "계산" 버튼 클릭                                        │
│     → POST /what-if/{id}/compute                            │
│     → 폴링: GET /what-if/{id}/status (2초 간격)             │
│     → 완료 시: GET /what-if/{id}/result                     │
│                                                              │
│  4. "비교" 탭 전환                                          │
│     → GET /what-if/compare?ids=uuid1,uuid2,uuid3            │
│     → 비교표 + 토네이도 차트 + 전환점 렌더링                │
│                                                              │
│  시각화 라이브러리: Recharts                                 │
│  ├─ BarChart: 시나리오별 배분액 비교                        │
│  ├─ TornadoChart: 민감도 분석 (커스텀 컴포넌트)             │
│  ├─ LineChart: 연도별 현금흐름 추이                         │
│  └─ RadarChart: 시나리오 종합 점수 비교                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 결정 사항 (Decisions)

- scipy.optimize 사용 (ADR-001 참조)
- 비동기 계산 + 폴링 패턴 (WebSocket 대신 HTTP 폴링)
- 시나리오당 최대 30년 실행 기간 지원
- 프로세스 시간축 시뮬레이션은 Synapse Process Mining API에서 프로세스 모델/의존 그래프를 수신하여 Vision 내에서 시간 재계산 수행 (Synapse에서 시뮬레이션을 실행하지 않음)
- 임계 경로(Critical Path) 기반으로 전체 주기 시간 영향 계산

## 금지 사항 (Forbidden)

- 동기 요청에서 솔버 직접 실행 (반드시 비동기)
- 제약조건 없이 솔버 실행 (무한 탐색 위험)
- 시나리오 결과의 직접 수정 (재계산만 허용)

## 필수 사항 (Required)

- 모든 솔버 실행에 타임아웃 설정 (기본 60초)
- 실패 시 사유를 사용자에게 명확히 전달
- 시나리오 파라미터 변경 시 이전 결과 무효화 (status → DRAFT)
- 프로세스 시뮬레이션 시 Synapse 프로세스 모델 유효성 검증 (모델 존재, 활동 존재 확인)
- duration_change 적용 후 활동 소요시간이 음수가 되지 않도록 검증

<!-- affects: 02_api/what-if-api.md, 03_backend/scenario-solver.md, 06_data/database-schema.md, 00_overview/system-overview.md -->
<!-- requires-update: 02_api/what-if-api.md, 06_data/database-schema.md -->
