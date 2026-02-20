# Process Discovery 구현 상세

## 이 문서가 답하는 질문

- pm4py의 각 Process Discovery 알고리즘은 어떻게 구현하는가?
- Alpha Miner, Heuristic Miner, Inductive Miner의 차이와 선택 기준은?
- Petri Net에서 BPMN으로의 변환은 어떻게 하는가?
- 발견된 모델을 Neo4j에 어떻게 저장하는가?

<!-- affects: api, data -->
<!-- requires-update: 02_api/process-mining-api.md, 06_data/neo4j-schema.md -->

---

## 1. 알고리즘 개요

### 1.1 알고리즘 선택 가이드

| 알고리즘 | 적합한 로그 | 장점 | 단점 | 사용 시나리오 |
|---------|-----------|------|------|-------------|
| **Alpha Miner** | 노이즈 없는 완전한 로그 | 단순, 빠름 | 노이즈에 취약, 루프/비가시 작업 처리 제한 | 학습/검증 목적, 깨끗한 시뮬레이션 로그 |
| **Heuristic Miner** | 실제 비즈니스 로그 (노이즈 있음) | 노이즈 내성, 빈도 기반 필터링 | 사운드 보장 안됨 | 실제 이벤트 로그 탐색적 분석 |
| **Inductive Miner** | 모든 유형의 로그 | 사운드 모델 보장, BPMN 변환 최적 | 과도하게 일반화할 수 있음 | BPMN 생성, Conformance Checking 참조 모델 |

### 1.2 알고리즘 자동 추천

```python
def recommend_algorithm(log_stats: EventLogStatistics) -> str:
    """
    Recommend mining algorithm based on log characteristics.
    """
    # Rule 1: Very clean log (low variant diversity) → Alpha
    if log_stats.variant_count / log_stats.case_count < 0.05:
        return "alpha"

    # Rule 2: Need sound model (for conformance) → Inductive
    if log_stats.purpose == "conformance_reference":
        return "inductive"

    # Rule 3: Default for real business logs → Heuristic
    return "heuristic"
```

---

## 2. Alpha Miner 구현

### 2.1 알고리즘 원리

Alpha Miner는 이벤트 로그에서 직접적인 순서 관계(directly-follows)를 분석하여 Petri Net을 생성한다.

- **Directly-follows**: a > b (a 직후에 b 발생)
- **Causality**: a → b (a가 b를 야기)
- **Parallel**: a || b (a와 b가 병렬)
- **Choice**: a # b (a와 b가 상호 배타)

### 2.2 pm4py 구현

```python
import pm4py

async def discover_with_alpha(df: pd.DataFrame) -> DiscoveryResult:
    """
    Alpha Miner: basic process discovery.
    Best for structured, noise-free logs.
    """
    net, initial_marking, final_marking = pm4py.discover_petri_net_alpha(df)

    # Calculate model statistics
    stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
    }

    return DiscoveryResult(
        algorithm="alpha",
        petri_net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        statistics=stats
    )
```

### 2.3 Alpha Miner 제한사항

| 제한 | 설명 | 대안 |
|------|------|------|
| 노이즈 미처리 | 빈도 1회의 예외 경로도 모델에 포함 | Heuristic Miner 사용 |
| 길이 2 루프 미지원 | a→b→a 패턴 인식 불가 | Inductive Miner 사용 |
| 비가시 작업 미생성 | skip/silent transition 미지원 | Inductive Miner 사용 |

---

## 3. Heuristic Miner 구현

### 3.1 알고리즘 원리

Heuristic Miner는 빈도(frequency)와 의존도(dependency)를 기반으로 관계를 결정한다. 노이즈가 있는 실제 비즈니스 로그에 적합하다.

- **Dependency measure**: |a > b| - |b > a| / (|a > b| + |b > a| + 1)
- dependency_threshold 이상인 관계만 모델에 포함

### 3.2 pm4py 구현

```python
import pm4py

async def discover_with_heuristic(
    df: pd.DataFrame,
    dependency_threshold: float = 0.5,
) -> DiscoveryResult:
    """
    Heuristic Miner: noise-tolerant process discovery.
    Best for real business logs with noise.

    Parameters:
    - dependency_threshold (0.0-1.0): higher = stricter filtering
      0.3 = very permissive (includes rare paths)
      0.5 = balanced (default)
      0.8 = strict (only frequent paths)
    """
    net, initial_marking, final_marking = pm4py.discover_petri_net_heuristics(
        df,
        dependency_threshold=dependency_threshold,
    )

    stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
        "dependency_threshold": dependency_threshold,
    }

    return DiscoveryResult(
        algorithm="heuristic",
        petri_net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        statistics=stats
    )
```

### 3.3 dependency_threshold 튜닝 가이드

| threshold | 결과 | 권장 시나리오 |
|-----------|------|-------------|
| 0.1 - 0.3 | 거의 모든 경로 포함, 복잡한 모델 | 탐색적 분석, 예외 경로 발견 |
| 0.4 - 0.6 | 주요 경로 + 빈번한 변종 | **기본 분석 (권장)** |
| 0.7 - 0.9 | 주요 경로만, 단순한 모델 | 핵심 프로세스 파악, 보고용 |

---

## 4. Inductive Miner 구현

### 4.1 알고리즘 원리

Inductive Miner는 분할 정복(divide-and-conquer) 전략으로 프로세스 트리를 생성한 후 Petri Net으로 변환한다. **사운드 모델을 보장**하므로 Conformance Checking의 참조 모델로 적합하다.

- noise_threshold로 노이즈 필터링 (Inductive Miner infrequent)
- 항상 사운드(sound) 모델을 생성 (교착 없음, 종료 보장)

### 4.2 pm4py 구현

```python
import pm4py

async def discover_with_inductive(
    df: pd.DataFrame,
    noise_threshold: float = 0.2,
) -> DiscoveryResult:
    """
    Inductive Miner: guaranteed sound model.
    Best for BPMN generation and conformance checking reference.

    Parameters:
    - noise_threshold (0.0-1.0): percentage of traces to filter as noise
      0.0 = no filtering (all traces included)
      0.2 = filter bottom 20% infrequent traces (default)
      0.5 = aggressive filtering
    """
    net, initial_marking, final_marking = pm4py.discover_petri_net_inductive(
        df,
        noise_threshold=noise_threshold,
    )

    stats = {
        "places": len(net.places),
        "transitions": len(net.transitions),
        "arcs": len(net.arcs),
        "noise_threshold": noise_threshold,
        "is_sound": True,  # Inductive Miner guarantees soundness
    }

    return DiscoveryResult(
        algorithm="inductive",
        petri_net=net,
        initial_marking=initial_marking,
        final_marking=final_marking,
        statistics=stats
    )
```

---

## 5. Petri Net → BPMN 변환

### 5.1 pm4py BPMN 생성

```python
import pm4py

async def generate_bpmn(df: pd.DataFrame) -> str:
    """
    Generate BPMN model directly from event log.
    Uses Inductive Miner internally.
    Returns BPMN 2.0 XML string.
    """
    bpmn_model = pm4py.discover_bpmn_inductive(df)

    # Export to XML string
    from pm4py.objects.bpmn.exporter import exporter as bpmn_exporter
    import tempfile, os

    with tempfile.NamedTemporaryFile(suffix='.bpmn', delete=False) as f:
        bpmn_exporter.apply(bpmn_model, f.name)
        with open(f.name, 'r') as xml_file:
            bpmn_xml = xml_file.read()
        os.unlink(f.name)

    return bpmn_xml
```

### 5.2 Petri Net → BPMN 변환 규칙

| Petri Net 요소 | BPMN 요소 | 설명 |
|---------------|----------|------|
| Transition (visible) | Task | 활동 노드 |
| Transition (silent) | - | BPMN에서 제거 또는 Gateway로 변환 |
| Place (branching) | Exclusive Gateway (XOR) | 선택 분기 |
| Parallel structure | Parallel Gateway (AND) | 병렬 실행 |
| Start place | Start Event | 프로세스 시작 |
| End place | End Event | 프로세스 종료 |

---

## 6. Neo4j 모델 저장

발견된 프로세스 모델을 Neo4j에 저장하여 온톨로지와 통합 탐색할 수 있게 한다.

```python
async def store_discovered_model_in_neo4j(
    neo4j: Neo4jClient,
    case_id: str,
    result: DiscoveryResult,
    log_id: str
):
    """
    Store discovered process model as graph nodes/relations in Neo4j.
    Each transition becomes a BusinessEvent:Process node.
    Arcs become FOLLOWED_BY relations.
    """
    async with neo4j.session() as session:
        for transition in result.petri_net.transitions:
            if transition.label:  # Skip silent transitions
                await session.run("""
                    MERGE (e:BusinessEvent:Process {
                        case_id: $case_id,
                        name: $name,
                        source: 'discovered'
                    })
                    ON CREATE SET
                        e.id = randomUUID(),
                        e.type = 'BusinessEvent',
                        e.discovery_algorithm = $algorithm,
                        e.log_id = $log_id,
                        e.created_at = datetime()
                    """,
                    case_id=case_id,
                    name=transition.label,
                    algorithm=result.algorithm,
                    log_id=log_id
                )

        # Create FOLLOWED_BY relations with statistics
        for activity_pair, stats in result.transition_stats.items():
            await session.run("""
                MATCH (a:BusinessEvent:Process {case_id: $case_id, name: $from_name})
                MATCH (b:BusinessEvent:Process {case_id: $case_id, name: $to_name})
                MERGE (a)-[r:FOLLOWED_BY]->(b)
                SET r.case_count = $case_count,
                    r.avg_duration = $avg_duration,
                    r.probability = $probability
                """,
                case_id=case_id,
                from_name=activity_pair[0],
                to_name=activity_pair[1],
                case_count=stats.case_count,
                avg_duration=stats.avg_duration,
                probability=stats.probability
            )
```

---

## 금지 규칙

- Process Mining Layer 외부에서 pm4py를 직접 호출하지 않는다
- Discovery 결과를 Graph Layer를 거치지 않고 Neo4j에 직접 저장하지 않는다
- 100만 이벤트 초과 로그를 동기 처리하지 않는다

## 필수 규칙

- 모든 Discovery 결과에 사용된 알고리즘과 파라미터를 기록한다
- 비동기 작업으로 실행하고 task_id를 즉시 반환한다
- 결과를 PostgreSQL(conformance_results)과 Neo4j(프로세스 모델)에 모두 저장한다

---

## 근거 문서

- `01_architecture/process-mining-engine.md` (엔진 아키텍처)
- `02_api/process-mining-api.md` (API 명세)
- ADR-005: pm4py 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
