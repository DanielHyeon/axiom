# Conformance Checker 구현 상세

## 이 문서가 답하는 질문

- Token-based replay Conformance Checking은 어떻게 구현하는가?
- fitness, precision, generalization, simplicity 메트릭의 의미와 계산 방식은?
- EventStorming 모델을 참조 모델로 사용하는 변환 과정은?
- 편차(deviation) 리포트는 어떻게 생성하는가?
- Canvas에서 편차를 시각적으로 하이라이트하는 방식은?

<!-- affects: api, frontend, data -->
<!-- requires-update: 02_api/process-mining-api.md, 01_architecture/process-mining-engine.md -->

---

## 1. Conformance Checking 개요

### 1.1 목적

"설계된 프로세스"(EventStorming 모델)와 "실제 실행"(이벤트 로그)의 차이를 정량적으로 측정한다.

```
설계된 프로세스 (As-Designed):
  주문접수 → 결제확인 → 재고확인 → 출하지시 → 배송완료

실제 실행 (As-Executed):
  case_001: 주문접수 → 결제확인 → 재고확인 → 출하지시 → 배송완료  (적합)
  case_002: 주문접수 → 결제확인 → 출하지시 → 배송완료              (재고확인 누락)
  case_003: 주문접수 → 결제확인 → 재고확인 → 반품처리 → 환불      (설계에 없는 경로)
```

### 1.2 4대 메트릭

| 메트릭 | 질문 | 높을수록 | 낮으면 |
|--------|------|---------|--------|
| **Fitness** | "로그의 행동을 모델이 재현할 수 있는가?" | 모든 실행이 설계를 따름 | 설계에 없는 실행이 많음 |
| **Precision** | "모델이 허용하는 행동 중 실제로 발생하는가?" | 모델이 정확히 실행을 반영 | 모델이 너무 느슨함 |
| **Generalization** | "미래의 새 케이스도 모델로 설명 가능한가?" | 모델이 일반적임 | 모델이 과적합됨 |
| **Simplicity** | "모델이 얼마나 단순한가?" | 이해하기 쉬움 | 모델이 과도하게 복잡 |

---

## 2. Token-based Replay 구현

### 2.1 알고리즘 원리

Token-based replay는 Petri Net 위에서 이벤트 로그의 각 trace를 재생(replay)한다.

1. 초기 마킹에 토큰을 배치
2. trace의 각 이벤트에 대해:
   - 해당 transition이 활성화(enabled)되었으면 → 정상 소비/생성
   - 활성화되지 않았으면 → **missing token** 추가 (편차 발생)
3. 최종 마킹에 도달했는지 확인
   - 남은 토큰이 있으면 → **remaining token** (편차 발생)

### 2.2 pm4py 구현

```python
import pm4py

async def check_conformance(
    df: pd.DataFrame,
    reference_net: PetriNet,
    initial_marking: Marking,
    final_marking: Marking,
    include_case_diagnostics: bool = True,
    max_diagnostics_cases: int = 100
) -> ConformanceResult:
    """
    Token-based replay conformance checking.
    Compares event log against reference model (from EventStorming).
    """
    # 1. Token-based replay (per-case diagnostics)
    replayed_traces = pm4py.conformance_diagnostics_token_based_replay(
        df, reference_net, initial_marking, final_marking
    )

    # 2. Calculate aggregate fitness
    fitness_result = pm4py.fitness_token_based_replay(
        df, reference_net, initial_marking, final_marking
    )
    fitness = fitness_result['average_trace_fitness']

    # 3. Calculate precision
    precision = pm4py.precision_token_based_replay(
        df, reference_net, initial_marking, final_marking
    )

    # 4. Calculate generalization
    generalization = pm4py.generalization_tbr(
        df, reference_net, initial_marking, final_marking
    )

    # 5. Calculate simplicity
    simplicity = pm4py.simplicity_arc_degree(reference_net)

    # 6. Build per-case diagnostics
    case_diagnostics = []
    if include_case_diagnostics:
        for i, trace_result in enumerate(replayed_traces[:max_diagnostics_cases]):
            case_diagnostics.append(CaseDiagnostic(
                is_fit=trace_result['trace_is_fit'],
                trace_fitness=trace_result['trace_fitness'],
                missing_tokens=trace_result['missing_tokens'],
                remaining_tokens=trace_result['remaining_tokens'],
                consumed_tokens=trace_result['consumed_tokens'],
                produced_tokens=trace_result['produced_tokens'],
            ))

    return ConformanceResult(
        fitness=fitness,
        precision=precision,
        generalization=generalization,
        simplicity=simplicity,
        total_cases=len(replayed_traces),
        conformant_cases=sum(1 for t in replayed_traces if t['trace_is_fit']),
        case_diagnostics=case_diagnostics
    )
```

---

## 3. EventStorming → Petri Net 변환

### 3.1 변환 규칙

EventStorming 모델의 Command→Event 체인을 Petri Net으로 변환하여 Conformance Checking의 참조 모델로 사용한다.

| EventStorming | Petri Net | 설명 |
|--------------|----------|------|
| Command | Transition (visible) | 활동 = 발화 가능한 전이 |
| Event | Place | 상태 = 토큰이 존재하는 장소 |
| Event→Event 순서 | Arc (Place→Transition→Place) | 흐름 관계 |
| Policy(XOR 분기) | Place + 다중 Transition | 선택 분기 |
| 병렬 처리 | AND-split/join (추가 Place) | 병렬 실행 |

### 3.2 변환 구현

```python
from pm4py.objects.petri_net.obj import PetriNet, Marking
from pm4py.objects.petri_net.utils import petri_utils

async def eventstorming_to_petri_net(
    events: list[BusinessEventNode],
    actions: list[BusinessActionNode],
    rules: list[BusinessRuleNode],
    relations: list[dict]
) -> tuple[PetriNet, Marking, Marking]:
    """
    Convert EventStorming model to Petri Net for conformance checking.
    """
    net = PetriNet("eventstorming_reference")
    im = Marking()
    fm = Marking()

    places = {}  # event_id -> Place
    transitions = {}  # action_id -> Transition

    # Create start place
    start = PetriNet.Place("start")
    net.places.add(start)
    im[start] = 1

    # Create transitions for each Command/Action
    for action in actions:
        t = PetriNet.Transition(action.id, action.name)
        net.transitions.add(t)
        transitions[action.id] = t

    # Create places for each Event
    for event in events:
        p = PetriNet.Place(event.id)
        net.places.add(p)
        places[event.id] = p

    # Connect based on relations
    for rel in relations:
        if rel['type'] == 'PRODUCES':  # Action → Event
            action_t = transitions.get(rel['source_id'])
            event_p = places.get(rel['target_id'])
            if action_t and event_p:
                petri_utils.add_arc_from_to(action_t, event_p, net)

        elif rel['type'] == 'FOLLOWED_BY':  # Event → next Action
            event_p = places.get(rel['source_id'])
            # Find the action that follows
            next_action_t = transitions.get(rel['target_id'])
            if event_p and next_action_t:
                petri_utils.add_arc_from_to(event_p, next_action_t, net)

    # Connect start to first action
    first_action = transitions.get(actions[0].id) if actions else None
    if first_action:
        petri_utils.add_arc_from_to(start, first_action, net)

    # Set final marking (last event place)
    last_event = places.get(events[-1].id) if events else None
    if last_event:
        fm[last_event] = 1

    return net, im, fm
```

---

## 4. 편차 리포트 생성

### 4.1 편차 유형

| 편차 유형 | Token Replay 지표 | 설명 | 예시 |
|----------|------------------|------|------|
| **Skipped Activity** | missing_tokens > 0 | 설계된 활동이 실행되지 않음 | "재고 확인"을 건너뜀 |
| **Unexpected Activity** | remaining_tokens > 0 | 설계에 없는 활동이 실행됨 | "반품 처리"가 추가됨 |
| **Wrong Order** | missing + remaining | 활동 순서가 설계와 다름 | "출하 지시"가 "재고 확인" 전에 실행 |
| **Loop** | repeated transitions | 동일 활동이 반복됨 | "결제 확인"이 2번 실행 |

### 4.2 편차 리포트 구현

```python
async def generate_deviation_report(
    replayed_traces: list[dict],
    df: pd.DataFrame,
    reference_events: list[str]
) -> DeviationReport:
    """
    Generate detailed deviation report from replay results.
    """
    non_conformant = []
    skipped_stats = defaultdict(int)
    unexpected_stats = defaultdict(int)

    for i, trace_result in enumerate(replayed_traces):
        if not trace_result['trace_is_fit']:
            case_id = df.iloc[trace_result['activated_transitions_indexes'][0]]['case:concept:name']
            trace_activities = get_case_activities(df, case_id)

            deviations = []

            # Detect skipped activities
            for ref_event in reference_events:
                if ref_event not in trace_activities:
                    deviations.append(Deviation(
                        type="skipped_activity",
                        expected=ref_event,
                        actual=None,
                        description=f"'{ref_event}' 활동이 누락됨"
                    ))
                    skipped_stats[ref_event] += 1

            # Detect unexpected activities
            for actual_event in trace_activities:
                if actual_event not in reference_events:
                    deviations.append(Deviation(
                        type="unexpected_activity",
                        expected=None,
                        actual=actual_event,
                        description=f"설계에 없는 '{actual_event}' 활동이 발생"
                    ))
                    unexpected_stats[actual_event] += 1

            non_conformant.append(CaseDeviation(
                case_id=case_id,
                trace=trace_activities,
                deviations=deviations,
                trace_fitness=trace_result['trace_fitness']
            ))

    return DeviationReport(
        non_conformant_cases=non_conformant,
        skipped_statistics=dict(skipped_stats),
        unexpected_statistics=dict(unexpected_stats),
        total_deviations=sum(len(c.deviations) for c in non_conformant)
    )
```

---

## 5. Canvas 시각적 편차 하이라이트

Conformance Checking 결과를 Canvas의 EventStorming 디자이너에서 시각적으로 표현한다.

### 5.1 시각화 규칙

| 편차 유형 | 색상/스타일 | Canvas 표현 |
|----------|-----------|------------|
| 적합 (conformant) | 녹색 실선 | 정상 경로 |
| 활동 누락 (skipped) | 빨간색 점선 | 해당 Event 노드에 경고 아이콘 |
| 예상 외 활동 (unexpected) | 주황색 점선 | 새로운 Event 노드가 추가로 표시 |
| 순서 오류 (wrong order) | 노란색 점선 | 화살표 방향에 경고 표시 |

### 5.2 Canvas 연동 데이터 형식

```json
{
  "type": "conformance_overlay",
  "model_id": "es-model-uuid-001",
  "highlights": [
    {
      "node_id": "event-uuid-재고확인",
      "type": "skipped_activity",
      "severity": "high",
      "skip_count": 120,
      "skip_rate": 0.096,
      "color": "#FF4444",
      "style": "dashed",
      "tooltip": "120건 (9.6%)에서 '재고 확인'이 누락됨"
    },
    {
      "node_id": null,
      "type": "unexpected_activity",
      "activity_name": "반품 처리",
      "position_after": "event-uuid-결제확인",
      "occurrence_count": 23,
      "color": "#FF8800",
      "style": "dashed",
      "tooltip": "설계에 없는 '반품 처리' 23건 발견"
    }
  ],
  "overall_fitness": 0.85,
  "overall_conformance_rate": 0.85
}
```

---

## 6. 메트릭 해석 가이드

### 6.1 임계값 기준

| 메트릭 | 양호 (Green) | 주의 (Yellow) | 위험 (Red) |
|--------|-------------|-------------|-----------|
| Fitness | >= 0.90 | 0.75 - 0.89 | < 0.75 |
| Precision | >= 0.85 | 0.70 - 0.84 | < 0.70 |
| Generalization | >= 0.80 | 0.65 - 0.79 | < 0.65 |

### 6.2 결과 해석 시나리오

| 시나리오 | Fitness | Precision | 해석 |
|---------|---------|-----------|------|
| 높음/높음 | 0.95 | 0.93 | 설계와 실행이 잘 일치. 이상적 |
| 높음/낮음 | 0.95 | 0.50 | 실행은 설계를 따르지만, 모델이 너무 느슨 |
| 낮음/높음 | 0.60 | 0.90 | 실행이 설계를 많이 벗어나지만, 모델 자체는 정확 |
| 낮음/낮음 | 0.50 | 0.40 | 설계와 실행 모두 재검토 필요 |

---

## 금지 규칙

- Conformance Checking을 동기 API로 실행하지 않는다 (항상 비동기)
- EventStorming 모델 없이 참조 모델을 임의로 생성하지 않는다
- fitness 0.5 미만인 결과에서 세부 편차를 무시하지 않는다

## 필수 규칙

- 모든 Conformance 결과에 사용된 참조 모델 ID와 이벤트 로그 ID를 기록한다
- 결과를 PostgreSQL conformance_results 테이블에 저장한다
- Canvas 오버레이 데이터를 표준 형식으로 반환한다

---

## 근거 문서

- `01_architecture/process-mining-engine.md` (엔진 아키텍처)
- `02_api/process-mining-api.md` (API 명세)
- `03_backend/process-discovery.md` (Process Discovery - Petri Net 생성)
- ADR-005: pm4py 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
