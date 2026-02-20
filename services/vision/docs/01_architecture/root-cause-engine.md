# See-Why 근본원인 분석 엔진 설계

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **Phase**: 4 (출시 후)
> **근거**: ADR-004 (DoWhy 선택), K-AIR "See-why 원인분석" 설계

---

## 이 문서가 답하는 질문

- See-Why 엔진은 어떤 구조로 인과 추론을 수행하는가?
- 인과 그래프는 어떻게 구축되는가?
- 케이스별 근본원인 추출은 어떤 알고리즘을 사용하는가?
- 반사실 시나리오(Counterfactual)는 어떻게 생성되는가?
- SHAP 기반 요인 기여도는 어떻게 계산되는가?
- LLM 기반 설명 서술문은 어떻게 생성되는가?
- 프로세스 병목의 근본원인은 어떻게 분석되는가? (Synapse 연동)

---

## 1. 엔진 개요

### 1.1 해결하는 비즈니스 문제

비즈니스 프로세스 인텔리전스에서 **"왜 이 조직이 실패했는가?"** 는 핵심적인 질문이다.

- **분석 보고서 작성**: 분석가는 근본 원인을 분석하여 의사결정권자에게 보고해야 한다
- **비즈니스 전략 근거**: 근본원인을 제거/완화하는 방향으로 전략을 수립해야 한다
- **이해관계자(Stakeholder) 설명**: 이해관계자에게 비즈니스 경위를 설명하고 합의를 구해야 한다
- **이상 징후 탐지**: 비정상적 경영/자산 변동 징후를 체계적으로 추적해야 한다

### 1.2 전제 조건

| 전제 조건 | 상태 | 설명 |
|----------|------|------|
| 과거 종결 사건 100건+ | 미확보 | ML 모델 학습을 위한 라벨링된 데이터 |
| 4계층 온톨로지 구축 | Phase 3.3 | 인과 변수 간 관계 정의의 기반 |
| Phase 2 현금흐름 데이터 | Phase 2 | 재무 시계열 데이터 |

---

## 2. 파이프라인

```
┌─ See-Why 근본원인 분석 파이프라인 ─────────────────────────────┐
│                                                                 │
│  1. 인과 그래프 구축 (Causal Graph Construction)                │
│  ├─ 입력: 과거 종결 사건 100건+ 관측 데이터                    │
│  ├─ PC Algorithm: 조건부 독립성 테스트 → 골격 구축             │
│  ├─ LiNGAM: 선형 비가우시안 비순환 모델 → 방향 결정           │
│  ├─ 도메인 전문가 검토: 인과 방향 보정 (HITL)                 │
│  └─ 출력: 인과 DAG (causal_graphs 테이블 저장)                │
│          │                                                      │
│          ▼                                                      │
│  2. 케이스별 근본원인 추출                                      │
│  ├─ 현재 사건 데이터 로드: 매출, 비용, 부채, 자산 시계열       │
│  ├─ 인과 그래프에서 역방향 탐색 (backward traversal)           │
│  │  ├─ 결과 노드: "사업 실패" 또는 "성과 미달"                │
│  │  ├─ 중간 노드: 부채비율 급증, EBITDA 하락, 현금 고갈        │
│  │  └─ 근본 노드: M&A 차입, 공급망 교란, 경기침체              │
│  ├─ 상위 3~5개 근본원인 도출 (인과 계수 기준)                 │
│  └─ 각 원인의 기여도 (%) 산출                                  │
│          │                                                      │
│          ▼                                                      │
│  3. DoWhy 인과 효과 추정                                       │
│  ├─ 처치(Treatment): 근본원인 변수 (예: 부채비율)              │
│  ├─ 결과(Outcome): 사업 실패 여부                              │
│  ├─ 추정 방법: 백도어 기준 (backdoor criterion)                │
│  ├─ 효과 크기: ATE (Average Treatment Effect)                  │
│  └─ 검증: Refutation tests (placebo, random common cause)      │
│          │                                                      │
│          ▼                                                      │
│  4. 반사실 시나리오 생성 (Counterfactual)                       │
│  ├─ "비용 구조를 20% 개선하면 수익성이 어떻게 변할까?"         │
│  ├─ DoWhy counterfactual estimation                            │
│  ├─ 민감도: 어떤 원인 변경이 가장 큰 영향?                     │
│  └─ 정량화: "비용 구조 20% 개선 시 실패 확률 35% 하락"        │
│          │                                                      │
│          ▼                                                      │
│  5. SHAP 기반 요인 기여도                                      │
│  ├─ SHAP (SHapley Additive exPlanations)                       │
│  ├─ 각 변수의 결과 기여도 산출                                  │
│  ├─ Force plot: 개별 사건의 요인별 기여                         │
│  └─ Summary plot: 전체 사건의 요인 중요도                       │
│          │                                                      │
│          ▼                                                      │
│  6. LLM 설명 생성                                               │
│  ├─ 인과 체인 + SHAP 값 → 구조화된 프롬프트                   │
│  ├─ GPT-4o → 서술적 설명문 생성 (한국어)                       │
│  ├─ "근본 원인 분석: 2022년 M&A로 인한 과도한 차입금이          │
│  │   부채비율을 150%까지 상승시켰으며, 이후 금리 인상으로       │
│  │   이자 비용이 급증하여 2023년 4분기 현금 고갈에 이르렀다."  │
│  └─ 분석 보고서 자동 작성과 연동                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 인과 그래프 구축

### 3.1 변수 정의 (비즈니스 도메인)

```python
# Causal variables for business domain
CAUSAL_VARIABLES = {
    # Root causes (exogenous)
    "market_condition": "경기 상황 (GDP 성장률)",
    "interest_rate_env": "금리 환경 (기준금리)",
    "industry_cycle": "업종 경기 (업종별 성장률)",
    "management_decision": "경영 의사결정 (M&A, 투자)",

    # Intermediate (endogenous)
    "revenue": "매출액",
    "ebitda": "EBITDA",
    "operating_cost": "영업비용",
    "debt_ratio": "부채비율",
    "interest_expense": "이자비용",
    "cash_balance": "현금잔고",
    "asset_value": "자산가치",
    "supply_chain_stability": "공급망 안정성",

    # Outcome
    "business_failure": "사업 실패",
}
```

### 3.2 PC Algorithm + LiNGAM

```python
from causallearn.search.ConstraintBased.PC import pc
from lingam import DirectLiNGAM
import numpy as np

async def build_causal_graph(
    training_data: np.ndarray,
    variable_names: list[str],
    alpha: float = 0.05
) -> CausalGraph:
    """
    Step 1: PC Algorithm - discover skeleton (undirected edges)
    Step 2: LiNGAM - orient edges (determine causal direction)
    """
    # Step 1: PC Algorithm
    pc_result = pc(
        data=training_data,
        alpha=alpha,
        indep_test="fisherz",
        stable=True
    )
    skeleton = pc_result.G  # Undirected graph

    # Step 2: LiNGAM for edge orientation
    model = DirectLiNGAM()
    model.fit(training_data)
    causal_order = model.causal_order_
    adjacency_matrix = model.adjacency_matrix_

    # Build causal graph
    graph = CausalGraph(
        variables=variable_names,
        edges=[],
        adjacency_matrix=adjacency_matrix
    )

    for i in range(len(variable_names)):
        for j in range(len(variable_names)):
            if abs(adjacency_matrix[i][j]) > 0.01:  # Threshold
                graph.edges.append(CausalEdge(
                    cause=variable_names[j],
                    effect=variable_names[i],
                    coefficient=float(adjacency_matrix[i][j]),
                    confidence=compute_edge_confidence(pc_result, i, j)
                ))

    return graph
```

### 3.3 DoWhy 인과 효과 추정

```python
import dowhy
from dowhy import CausalModel

async def estimate_causal_effect(
    data: pd.DataFrame,
    treatment: str,        # "debt_ratio"
    outcome: str,          # "business_failure"
    graph_dot: str,        # DOT format causal graph
    min_confidence: float = 0.70
) -> CausalEffectResult:
    """
    Estimate causal effect of treatment on outcome using DoWhy.
    """
    model = CausalModel(
        data=data,
        treatment=treatment,
        outcome=outcome,
        graph=graph_dot
    )

    # Identify causal effect
    identified = model.identify_effect(proceed_when_unidentifiable=True)

    # Estimate using backdoor criterion
    estimate = model.estimate_effect(
        identified,
        method_name="backdoor.propensity_score_matching"
    )

    # Refutation tests
    refutation_placebo = model.refute_estimate(
        identified, estimate,
        method_name="placebo_treatment_refuter"
    )
    refutation_random = model.refute_estimate(
        identified, estimate,
        method_name="random_common_cause"
    )

    return CausalEffectResult(
        treatment=treatment,
        outcome=outcome,
        ate=float(estimate.value),
        confidence_interval=estimate.get_confidence_intervals(),
        refutation_passed=(
            refutation_placebo.new_effect < 0.05 and
            refutation_random.new_effect < estimate.value * 1.1
        ),
        confidence=compute_confidence(estimate, refutation_placebo, refutation_random)
    )
```

---

## 4. 반사실 시나리오

### 4.1 반사실 질의 구조

```python
class CounterfactualRequest(BaseModel):
    case_id: UUID
    variable: str           # "debt_ratio"
    actual_value: Decimal    # 0.60 (60%)
    counterfactual_value: Decimal  # 0.40 (40%)
    question: str | None     # "비용 구조를 개선했다면 실패를 피할 수 있었는가?"

class CounterfactualResult(BaseModel):
    case_id: UUID
    variable: str
    actual_value: Decimal
    counterfactual_value: Decimal
    actual_outcome: str               # "사업 실패"
    counterfactual_outcome: str       # "실패 회피 가능성 65%"
    probability_change: Decimal       # -0.35 (35% 감소)
    explanation: str                  # LLM 생성 서술문
    confidence: Decimal               # 0.78
```

---

## 5. SHAP 값 계산

```python
import shap

async def compute_shap_values(
    case_id: UUID,
    model,              # Trained causal/ML model
    case_features: np.ndarray,
    background_data: np.ndarray
) -> SHAPResult:
    """
    Compute SHAP values for a specific case to explain
    which factors contributed most to the outcome.
    """
    explainer = shap.Explainer(model, background_data)
    shap_values = explainer(case_features)

    contributions = []
    for i, var_name in enumerate(CAUSAL_VARIABLES.keys()):
        contributions.append(SHAPContribution(
            variable=var_name,
            variable_label=CAUSAL_VARIABLES[var_name],
            shap_value=float(shap_values.values[0][i]),
            feature_value=float(case_features[0][i]),
            direction="positive" if shap_values.values[0][i] > 0 else "negative"
        ))

    # Sort by absolute SHAP value
    contributions.sort(key=lambda c: abs(c.shap_value), reverse=True)

    return SHAPResult(
        case_id=case_id,
        base_value=float(shap_values.base_values[0]),
        contributions=contributions,
        top_factors=contributions[:5]  # Top 5
    )
```

---

## 6. LLM 인과 설명 생성

### 6.1 프롬프트 구조

```python
CAUSAL_EXPLANATION_PROMPT = """
당신은 기업 비즈니스 프로세스 전문 분석가입니다.

아래 인과 분석 결과를 바탕으로, 이 조직의 비즈니스 실패 원인을 서술적으로 설명해 주세요.
분석 보고서에 사용될 수 있는 수준의 전문적이고 객관적인 문체를 사용하세요.

## 분석 대상
- 회사명: {company_name}
- 사건번호: {case_number}
- 분석 기준일: {declaration_date}

## 근본원인 (SHAP 기여도 순)
{root_causes_formatted}

## 인과 체인
{causal_chain_formatted}

## 반사실 시나리오
{counterfactual_formatted}

## 작성 요구사항
1. 시간 순서대로 인과 관계를 서술하세요.
2. 각 원인의 기여도를 수치로 명시하세요.
3. 반사실 분석 결과를 근거로 제시하세요.
4. 300~500자 분량으로 작성하세요.
5. 추측이나 가정은 명확히 표시하세요.
"""
```

---

## 7. 프로세스 병목 인과 분석

### 7.1 해결하는 비즈니스 문제

Synapse 프로세스 마이닝 엔진이 병목 탐지 결과와 프로세스 변형 데이터를 제공함에 따라, See-Why 엔진은 **프로세스 병목의 근본원인을 인과적으로 분석**할 수 있다.

- "왜 배송 프로세스가 느려지고 있는가?" → "재고확인 단계에서 승인 대기 시간이 원인"
- "왜 특정 프로세스 변형이 SLA를 위반하는가?"
- "어떤 활동 조합이 전체 처리 시간을 악화시키는가?"

### 7.2 데이터 소스: Synapse 병목 데이터

| Synapse API | 데이터 | See-Why 사용 목적 |
|-------------|--------|------------------|
| `GET /api/v1/process-models/{id}/bottlenecks` | 병목 활동, 대기시간, 빈도 | 인과 그래프의 관측 데이터로 활용 |
| `GET /api/v1/process-models/{id}/variants` | 변형별 경로, 소요시간, 결과 | 인과 변수(프로세스 변형 피처) |
| `GET /api/v1/process-models/{id}/statistics` | 활동별 통계 시계열 | 시간에 따른 변화 패턴 추적 |

### 7.3 인과 변수 확장: 프로세스 도메인

```python
# Causal variables for process domain (extension of CAUSAL_VARIABLES)
PROCESS_CAUSAL_VARIABLES = {
    # Root causes (exogenous) - process specific
    "resource_availability": "자원 가용성 (인력, 시스템)",
    "input_volume": "입력 건수 (시간당 요청량)",
    "process_complexity": "프로세스 복잡도 (분기 수, 활동 수)",

    # Intermediate (endogenous) - process specific
    "queue_wait_time": "대기열 대기시간",
    "handoff_delay": "핸드오프 지연시간 (담당자 간 전달)",
    "rework_rate": "재작업 비율",
    "variant_deviation_rate": "표준 경로 이탈 비율",
    "batch_accumulation_time": "배치 누적 대기시간",

    # Outcome
    "activity_bottleneck": "활동 병목 발생",
    "sla_violation": "SLA 위반",
    "cycle_time_increase": "주기 시간 증가",
}
```

### 7.4 파이프라인: Synapse 병목 데이터 → DoWhy 인과 그래프

```
┌─ 프로세스 병목 인과 분석 파이프라인 ────────────────────────────┐
│                                                                 │
│  1. Synapse 병목 데이터 수집                                    │
│  ├─ 프로세스 모델별 병목 활동 목록                              │
│  ├─ 활동별 대기시간/처리시간 시계열                             │
│  ├─ 프로세스 변형별 경로 및 소요시간                            │
│  └─ 자원 배분 현황 (인력, 시스템 부하)                          │
│          │                                                      │
│          ▼                                                      │
│  2. 인과 피처 구성                                              │
│  ├─ 프로세스 변형 데이터 → 인과 피처 변환                      │
│  │  ├─ 변형별: 경로 길이, 분기 수, 재작업 유무                 │
│  │  ├─ 활동별: 대기시간 비율, 처리시간 비율                    │
│  │  └─ 시간별: 시간대, 요일, 월 효과                           │
│  ├─ Synapse 병목 점수를 결과 변수(outcome)로 설정              │
│  └─ 관측 데이터 테이블 구성                                     │
│          │                                                      │
│          ▼                                                      │
│  3. DoWhy 인과 추론 (기존 파이프라인 재사용)                    │
│  ├─ PC Algorithm + LiNGAM → 인과 그래프 구축                  │
│  ├─ 처치(Treatment): 의심되는 원인 활동/변수                   │
│  ├─ 결과(Outcome): 병목 발생 또는 SLA 위반                    │
│  ├─ DoWhy 인과 효과 추정                                       │
│  └─ Refutation tests 검증                                      │
│          │                                                      │
│          ▼                                                      │
│  4. 인과 체인 도출                                              │
│  ├─ 역추적: 병목 활동 → 중간 원인 → 근본 원인                │
│  ├─ 예시: "배송 지연" ← "재고확인 대기" ← "승인 대기시간 증가"│
│  │        ← "승인 담당자 부족" (근본원인)                      │
│  ├─ 각 원인의 인과 계수 및 기여도 산출                          │
│  └─ SHAP 값으로 요인 기여도 정량화                              │
│          │                                                      │
│          ▼                                                      │
│  5. LLM 설명 생성                                               │
│  ├─ 프로세스 병목 전용 프롬프트 템플릿 사용                     │
│  └─ "왜 X 프로세스가 느려지고 있는가?"에 대한 서술적 답변     │
└─────────────────────────────────────────────────────────────────┘
```

### 7.5 결과 구조

```python
class ProcessBottleneckCausalResult(BaseModel):
    process_model_id: UUID
    bottleneck_activity: str                 # "재고확인"
    analyzed_at: datetime
    overall_confidence: float                # 0.82

    root_causes: list[ProcessRootCause]
    causal_chain: list[CausalChainStep]
    explanation: str                          # LLM 생성 서술문
    recommendations: list[str]               # 개선 권고사항

class ProcessRootCause(BaseModel):
    rank: int
    variable: str                            # "queue_wait_time"
    variable_label: str                      # "승인 대기열 대기시간"
    activity: str | None                     # "승인" (특정 활동과 연관된 경우)
    shap_value: float
    contribution_pct: float
    description: str                         # "승인 단계 대기시간이 평균 4시간으로 전체 병목의 45% 기여"
    confidence: float

class CausalChainStep(BaseModel):
    step: int
    cause: str                               # "승인 담당자 2명→1명 감소"
    effect: str                              # "승인 대기열 대기시간 2배 증가"
    coefficient: float                       # 0.72
```

### 7.6 사용 예시

**질문**: "왜 배송 프로세스가 느려지고 있는가?"

**결과**:
```json
{
  "process_model_id": "a1b2c3d4-...",
  "bottleneck_activity": "재고확인",
  "overall_confidence": 0.82,
  "root_causes": [
    {
      "rank": 1,
      "variable": "queue_wait_time",
      "variable_label": "승인 대기열 대기시간",
      "activity": "승인",
      "shap_value": 0.42,
      "contribution_pct": 42.0,
      "description": "승인 단계 대기시간이 평균 4시간으로 전체 병목의 42% 기여",
      "confidence": 0.88
    },
    {
      "rank": 2,
      "variable": "rework_rate",
      "variable_label": "재작업 비율",
      "activity": "검수",
      "shap_value": 0.28,
      "contribution_pct": 28.0,
      "description": "검수 단계 재작업 비율 15%로 추가 처리시간 발생",
      "confidence": 0.81
    }
  ],
  "causal_chain": [
    {"step": 1, "cause": "승인 담당자 1명 감소 (2명→1명)", "effect": "승인 대기열 대기시간 2배 증가", "coefficient": 0.72},
    {"step": 2, "cause": "승인 대기시간 증가", "effect": "재고확인 시작 지연", "coefficient": 0.65},
    {"step": 3, "cause": "재고확인 지연", "effect": "배송 프로세스 전체 주기시간 35% 증가", "coefficient": 0.58}
  ],
  "explanation": "배송 프로세스의 지연은 승인 단계의 대기시간 증가가 가장 주된 원인입니다(기여도 42%). 승인 담당자가 2명에서 1명으로 감소하면서 대기열 대기시간이 2배로 증가했고, 이로 인해 후속 재고확인 단계의 시작이 평균 4시간 지연되고 있습니다. 또한 검수 단계의 재작업 비율 15%가 추가적인 처리시간을 발생시키고 있습니다(기여도 28%).",
  "recommendations": [
    "승인 담당자 추가 배치 (1명→2명) 시 병목 해소 예상",
    "검수 기준 명확화로 재작업 비율 감소 가능"
  ]
}
```

---

## 8. 프론트엔드 시각화

| 시각화 | 라이브러리 | 용도 |
|--------|----------|------|
| 인과 DAG | React Flow | 노드-엣지 인과 그래프 (엣지 강도 표시) |
| SHAP Force Plot | Recharts (커스텀) | 개별 사건의 요인별 기여도 |
| 인과 타임라인 | Recharts LineChart | 시계열로 인과 체인 표시 |
| 반사실 비교 | Recharts BarChart | 실제 vs 반사실 결과 비교 |

---

## 결정 사항 (Decisions)

- DoWhy 라이브러리로 인과 추론 (ADR-004)
- PC Algorithm + LiNGAM 조합으로 인과 그래프 구축
- 인과 연결 보고 최소 신뢰도 0.70
- SHAP으로 요인 기여도 설명
- 프로세스 병목 인과 분석은 Synapse 병목 데이터를 입력으로 받아 DoWhy 파이프라인을 재사용 (별도 엔진 아님)
- 프로세스 변형(variant) 데이터를 인과 피처로 변환하여 DoWhy에 공급

## 금지 사항 (Forbidden)

- 학습 데이터 100건 미만에서 인과 그래프 구축 (통계적 신뢰도 부족)
- 인과 관계를 상관관계로 대체하여 보고
- LLM 설명에서 근거 없는 인과 주장 (hallucination 방지)
- Synapse 병목 데이터 없이 프로세스 병목 인과 분석 실행 (Synapse 연동 필수)

## 필수 사항 (Required)

- 인과 효과 추정 시 Refutation test 통과 필수
- 신뢰도 0.70 미만 인과 연결은 "참고용"으로 표시
- 도메인 전문가 HITL 검토 후 최종 인과 그래프 확정
- 모든 분석에 분석 일시, 사용 데이터 범위, 신뢰도 명시
- 프로세스 병목 분석 시 Synapse 데이터의 시간 범위와 케이스 수를 결과에 명시

## 미결정 사항 (Open Questions)

- 학습 데이터 확보 전략 (공개 비즈니스 사건 데이터 활용 가능 여부)
- 인과 그래프 버전 관리 방안 (데이터 축적 시 재학습 주기)
- HITL 검토 워크플로우 상세 (누가, 어떤 기준으로 검토하는가)

<!-- affects: 02_api/root-cause-api.md, 05_llm/causal-explanation.md, 06_data/database-schema.md, 00_overview/system-overview.md -->
<!-- requires-update: 02_api/root-cause-api.md, 00_overview/system-overview.md -->
