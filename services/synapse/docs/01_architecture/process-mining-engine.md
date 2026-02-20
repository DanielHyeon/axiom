# Process Mining Engine 아키텍처

## 이 문서가 답하는 질문

- Process Mining Engine의 전체 구조와 각 구성요소의 책임은?
- pm4py를 어떻게 통합하였으며, 어떤 알고리즘을 지원하는가?
- EventStorming 모델을 Conformance Checking의 참조 모델로 어떻게 사용하는가?
- Variant Analysis와 Bottleneck Detection은 어떻게 동작하는가?
- Vision(시간축 What-if)과 Canvas(시각화)와의 통합은 어떻게 이루어지는가?

<!-- affects: backend, api, frontend, data -->
<!-- requires-update: 02_api/process-mining-api.md, 03_backend/process-discovery.md, 03_backend/conformance-checker.md, 03_backend/temporal-analysis.md -->

---

## 1. 설계 배경

### 1.1 왜 Process Mining Engine이 필요한가?

Axiom Synapse는 4계층 온톨로지로 비즈니스 프로세스의 **구조**를 표현한다. 그러나 구조만으로는 다음 질문에 답할 수 없다:

| 질문 | 구조(온톨로지)만으로 | Process Mining으로 |
|------|-------------------|-------------------|
| "이 프로세스의 병목은 어디인가?" | 불가 | 활동별 소요시간 분석으로 식별 |
| "설계한 프로세스와 실제 실행이 얼마나 다른가?" | 불가 | Conformance Checking으로 정량화 |
| "프로세스가 실제로 몇 가지 경로로 실행되는가?" | 불가 | Variant Analysis로 식별 |
| "SLA를 위반하는 케이스의 공통점은?" | 불가 | 시간축 분석 + 속성 상관 분석 |
| "프로세스가 점점 느려지고 있는가?" | 불가 | 시계열 추세 분석 |

Process Mining Engine은 **온톨로지(구조) + 이벤트 로그(실행 데이터) + 시간축(시간)**을 결합하여, 비즈니스 프로세스의 실제 동작을 분석한다.

### 1.2 EventStorming과의 관계

EventStorming으로 설계된 프로세스 모델(As-Is 또는 To-Be)은 Process Mining의 **참조 모델(Reference Model)**로 활용된다.

```
┌──────────────────────────────┐     ┌──────────────────────────────┐
│  설계된 프로세스                │     │  실행된 프로세스                │
│  (EventStorming Model)        │     │  (Event Log)                 │
│                               │     │                              │
│  Command → Event → Policy    │     │  case_001: A → B → C → D    │
│  Actor, Aggregate, Rule      │     │  case_002: A → C → B → D    │
│                               │     │  case_003: A → B → D        │
└──────────────┬───────────────┘     └──────────────┬───────────────┘
               │                                     │
               └──────────┬──────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  Conformance Checking │
              │  fitness=0.85         │
              │  precision=0.92       │
              │  generalization=0.88  │
              └──────────────────────┘
```

---

## 2. 엔진 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Process Mining Engine                             │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Input Layer                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │ │
│  │  │ EventStorming │  │ Event Log    │  │ DB Table Binding     │  │ │
│  │  │ Model Parser  │  │ Ingester     │  │ (source_table,       │  │ │
│  │  │ (JSON→Graph)  │  │ (XES/CSV/DB) │  │  timestamp_column)   │  │ │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │ │
│  └─────────┼─────────────────┼──────────────────────┼──────────────┘ │
│            │                 │                      │                 │
│  ┌─────────▼─────────────────▼──────────────────────▼──────────────┐ │
│  │  Processing Layer (pm4py)                                        │ │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌────────────────┐  │ │
│  │  │ Process        │  │ Conformance      │  │ Temporal        │  │ │
│  │  │ Discovery      │  │ Checker          │  │ Analysis        │  │ │
│  │  │                │  │                  │  │                 │  │ │
│  │  │ Alpha Miner    │  │ Token Replay     │  │ Duration Stats  │  │ │
│  │  │ Heuristic Miner│  │ fitness/precis./ │  │ Waiting Time    │  │ │
│  │  │ Inductive Miner│  │ generalization   │  │ SLA Violation   │  │ │
│  │  │                │  │                  │  │ Bottleneck Score│  │ │
│  │  │ Petri Net      │  │ Deviation Report │  │ Trend Analysis  │  │ │
│  │  │ BPMN Export    │  │                  │  │                 │  │ │
│  │  └────────────────┘  └──────────────────┘  └────────────────┘  │ │
│  │                                                                  │ │
│  │  ┌────────────────┐  ┌──────────────────┐                      │ │
│  │  │ Variant        │  │ Organizational   │                      │ │
│  │  │ Analyzer       │  │ Mining           │                      │ │
│  │  │                │  │                  │                      │ │
│  │  │ Variant Stats  │  │ Resource Profile │                      │ │
│  │  │ Deviation Det. │  │ Workload Anal.   │                      │ │
│  │  │ Case Filtering │  │ Social Network   │                      │ │
│  │  └────────────────┘  └──────────────────┘                      │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│            │                                                          │
│  ┌─────────▼────────────────────────────────────────────────────────┐ │
│  │  Output Layer                                                     │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │ │
│  │  │ Neo4j Graph   │  │ PostgreSQL   │  │ API Response         │  │ │
│  │  │ (Process Model│  │ (Results,    │  │ (JSON, BPMN XML,     │  │ │
│  │  │  + Temporal)  │  │  Variants,   │  │  Petri Net, Stats)  │  │ │
│  │  │              │  │  Conformance) │  │                     │  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 구성요소 책임

| 구성요소 | 책임 | 입력 | 출력 |
|---------|------|------|------|
| **Event Log Ingester** | 이벤트 로그 수집/변환 | CSV, XES, DB 테이블 | pm4py EventLog DataFrame |
| **Process Discovery** | 프로세스 모델 자동 발견 | EventLog DataFrame | Petri Net, BPMN |
| **Conformance Checker** | 설계 vs 실행 적합성 검사 | 참조모델 + EventLog | fitness/precision/generalization |
| **Temporal Analysis** | 시간축 분석, 병목/SLA | EventLog DataFrame | 활동별 통계, 병목 점수, SLA 리포트 |
| **Variant Analyzer** | 프로세스 변종 분석 | EventLog DataFrame | 변종 목록, 빈도, 편차 |
| **Organizational Mining** | 조직/리소스 분석 | EventLog DataFrame | 리소스 프로파일, 작업부하 |

---

## 3. pm4py 통합 설계

### 3.1 pm4py 선택 근거

pm4py는 Python 네이티브 Process Mining 라이브러리로, 다음 이유로 선택하였다 (ADR-005 참조):

- FastAPI 스택과 동일한 Python 기반으로 별도 프로세스/서비스 불필요
- Alpha/Heuristic/Inductive Miner 3가지 핵심 알고리즘 내장
- Token-based replay Conformance Checking 내장
- BPMN 자동 생성 기능 (`pm4py.discover_bpmn_inductive()`)
- 오픈소스 + 학술/산업 양쪽에서 검증됨

### 3.2 핵심 알고리즘

#### Process Discovery 알고리즘

| 알고리즘 | 특성 | 적합한 상황 | pm4py 함수 |
|---------|------|-----------|-----------|
| **Alpha Miner** | 기본 알고리즘, 정확한 로그 필요 | 노이즈 없는 구조화된 로그 | `pm4py.discover_petri_net_alpha()` |
| **Heuristic Miner** | 노이즈 내성, 빈도 기반 | 실제 비즈니스 로그 (노이즈 있음) | `pm4py.discover_petri_net_heuristics()` |
| **Inductive Miner** | 사운드 모델 보장 | BPMN 생성, 적합성 검사 참조 | `pm4py.discover_petri_net_inductive()` |

#### Conformance Checking 메트릭

| 메트릭 | 의미 | 범위 | 해석 |
|--------|------|------|------|
| **Fitness** | 로그의 행위를 모델이 얼마나 재현할 수 있는가 | 0.0-1.0 | 1.0 = 모든 케이스가 모델을 따름 |
| **Precision** | 모델이 허용하는 행위 중 실제로 발생하는 비율 | 0.0-1.0 | 1.0 = 모델이 불필요한 행위를 허용하지 않음 |
| **Generalization** | 모델이 미래의 새로운 케이스를 얼마나 일반화할 수 있는가 | 0.0-1.0 | 1.0 = 완전히 일반화됨 |
| **Simplicity** | 모델의 복잡도 (노드/엣지 수) | 0.0-1.0 | 1.0 = 가장 단순 |

### 3.3 EventStorming 모델을 참조 모델로 사용

EventStorming 캔버스에서 설계된 Command→Event 체인을 Petri Net으로 변환하여 Conformance Checking의 참조 모델로 사용한다.

```python
# EventStorming model to Petri Net conversion (pseudo-code)
def eventstorming_to_petri_net(events: list[BusinessEvent]) -> PetriNet:
    """
    Convert EventStorming event chain to Petri Net for conformance checking.

    EventStorming Command→Event chain maps to:
    - Command → Transition (activity)
    - Event → Place (state)
    - Policy → Silent transition (automatic routing)
    """
    net = PetriNet("eventstorming_model")
    im = Marking()  # initial marking
    fm = Marking()  # final marking

    prev_place = add_place(net, "start")
    im[prev_place] = 1

    for event in events:
        # Command → Transition
        transition = add_transition(net, event.action_name)
        add_arc(net, prev_place, transition)

        # Event → Place
        place = add_place(net, event.name)
        add_arc(net, transition, place)
        prev_place = place

    fm[prev_place] = 1
    return net, im, fm
```

---

## 4. 데이터 파이프라인

### 4.1 이벤트 로그 인제스트 파이프라인

```
[소스]                    [변환]                     [저장]
CSV 파일 ──────▶                              ──▶ PostgreSQL
XES 파일 ──────▶  pm4py.format_dataframe()    ──▶ event_log_entries
DB 테이블 ─────▶  (case_id, activity,         ──▶ process_instances
                    timestamp 컬럼 매핑)        ──▶ process_variants
```

### 4.2 pm4py DataFrame 표준 형식

```python
import pm4py

# pm4py requires specific column names
df = pm4py.format_dataframe(
    df,
    case_id='order_id',           # process instance identifier
    activity_key='event_type',     # activity name
    timestamp_key='event_time'     # event timestamp
)

# Result DataFrame columns:
# case:concept:name  - case identifier
# concept:name       - activity name
# time:timestamp     - event timestamp
# (+ any additional columns as attributes)
```

### 4.3 Process Discovery 파이프라인

```
EventLog (DataFrame)
    │
    ├─ Algorithm Selection (Alpha / Heuristic / Inductive)
    │
    ▼ pm4py.discover_petri_net_*()
    │
    ├─ Petri Net Model
    │    │
    │    ├─ pm4py.convert_to_bpmn() → BPMN XML (Canvas 시각화)
    │    │
    │    └─ Neo4j 저장 (프로세스 모델 노드/관계)
    │
    └─ Statistics
         ├─ Activity frequency
         ├─ Transition frequency
         └─ Path statistics
```

### 4.4 Conformance Checking 파이프라인

```
Reference Model                    Event Log
(EventStorming Petri Net)          (pm4py DataFrame)
    │                                   │
    └──────────┬────────────────────────┘
               │
               ▼ pm4py.conformance_diagnostics_token_based_replay()
               │
               ├─ Per-case diagnostics
               │    ├─ is_fit: Boolean
               │    ├─ missing_tokens: List
               │    ├─ remaining_tokens: List
               │    └─ trace_fitness: Float
               │
               ├─ Aggregate metrics
               │    ├─ fitness: Float (0.0-1.0)
               │    ├─ precision: Float
               │    ├─ generalization: Float
               │    └─ simplicity: Float
               │
               └─ Deviation report
                    ├─ Non-conformant cases
                    ├─ Deviation points (which activity, where)
                    └─ Canvas visual highlighting
```

---

## 5. 외부 모듈 통합

### 5.1 Axiom Vision 통합 (시간축 What-if)

Vision 모듈이 근본원인 분석 시 시간축 데이터를 활용할 수 있도록 REST API를 제공한다.

| Vision 요청 | Synapse 응답 | 용도 |
|------------|-------------|------|
| "프로세스 X의 병목 분석" | 활동별 소요시간 통계 + 병목 점수 | 근본원인 식별 |
| "SLA 위반 케이스 패턴" | 위반 케이스의 공통 경로/속성 | 패턴 분석 |
| "시간축 추세" | 기간별 프로세스 소요시간 변화 | 추세 예측 |

### 5.2 Axiom Canvas 통합 (시각화)

Canvas의 EventStorming 디자이너에서 Process Mining 결과를 시각화한다.

| Canvas 기능 | Synapse 데이터 | 시각화 |
|------------|--------------|--------|
| 프로세스 맵 | Discovered Petri Net / BPMN | 프로세스 흐름도 |
| 병목 하이라이트 | 활동별 병목 점수 | 빨간색(병목)→초록색(원활) 색상 |
| 적합성 오버레이 | Conformance 결과 | 편차 경로 점선 표시 |
| 변종 비교 | Variant 목록 | 변종별 경로 병렬 표시 |
| 시간축 히트맵 | 활동별 소요시간 분포 | 히트맵 색상 오버레이 |

---

## 6. 성능 고려사항

| 시나리오 | 이벤트 수 | 예상 처리 시간 | 병목 |
|---------|----------|-------------|------|
| 소규모 로그 | ~10,000 | < 5초 | 없음 |
| 중규모 로그 | ~100,000 | 10-30초 | pm4py 알고리즘 |
| 대규모 로그 | ~1,000,000 | 1-5분 | 메모리 + pm4py |
| 초대규모 로그 | > 1,000,000 | 비동기 필수 | 샘플링 또는 분할 처리 |

### 대용량 처리 전략

- 100,000 이벤트 초과 시 비동기 작업으로 전환
- 1,000,000 이벤트 초과 시 랜덤 샘플링 (case 단위) 또는 시간 범위 분할
- Process Discovery 결과는 캐싱 (동일 로그에 대해 재실행 방지)
- Conformance Checking은 case 단위 병렬 처리 가능

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| pm4py 채택 | Python 네이티브, 학술/산업 검증, FastAPI 스택 호환 (ADR-005) |
| EventStorming을 참조 모델로 | 기존 프로세스 설계 자산 활용, 별도 BPMN 도구 불필요 |
| PostgreSQL에 이벤트 로그 저장 | 대용량 시계열 데이터, 트랜잭션 일관성 |
| Neo4j에 프로세스 모델 저장 | 그래프 구조의 프로세스 모델, 온톨로지 통합 탐색 |
| 비동기 처리 (대용량 로그) | pm4py 알고리즘 실행 시간이 수 분 소요 가능 |

## 재검토 조건

- pm4py 성능이 100만 이벤트 이상에서 한계를 보일 때
- Celonis SDK 등 상용 도구와의 통합이 필요할 때
- 실시간 스트리밍 Process Mining 요구가 발생할 때
- BPMN 2.0 완전 호환이 필요할 때

---

## 근거 문서

- ADR-005: pm4py Process Mining 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
- `01_architecture/ontology-4layer.md` (4계층 온톨로지 + EventStorming 매핑)
- `06_data/neo4j-schema.md` (Process Mining 확장 노드)
- `06_data/event-log-schema.md` (이벤트 로그 PostgreSQL 스키마)
- `03_backend/process-discovery.md` (Process Discovery 구현 상세)
- `03_backend/conformance-checker.md` (Conformance Checker 구현 상세)
- `03_backend/temporal-analysis.md` (시간축 분석 구현 상세)
