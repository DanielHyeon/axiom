# 관계 추출 + 온톨로지 매핑

## 이 문서가 답하는 질문

- NER로 추출한 개체 간 관계를 어떻게 식별하는가?
- 추출된 관계를 4계층 온톨로지에 어떻게 매핑하는가?
- LLM 관계 추출과 규칙 기반 매핑의 역할 분담은?
- 관계 추출의 한계와 HITL 보완 전략은?

<!-- affects: backend, data -->
<!-- requires-update: 06_data/ontology-model.md -->

---

## 1. 관계 추출 개요

### 1.1 2단계 파이프라인

```
NER 결과 (개체 리스트)
       │
       ▼
 ┌──────────────┐     ┌──────────────────┐
 │ LLM 관계 추출 │────▶│ 규칙 기반 온톨로지 │
 │ (GPT-4o)     │     │ 매핑             │
 └──────────────┘     └──────────────────┘
       │                       │
       ▼                       ▼
 추출된 관계               4계층 노드 + 관계
 (domain relations)        (ontology relations)
```

### 1.2 역할 분담

| 단계 | 엔진 | 역할 | 비결정적 여부 |
|------|------|------|-------------|
| 관계 추출 | GPT-4o (LLM) | 텍스트에서 개체 간 관계 식별 | 비결정적 (확률적) |
| 온톨로지 매핑 | 규칙 기반 (Python) | 추출된 관계 -> 4계층 온톨로지 변환 | 결정적 (규칙) |

**설계 근거**: 관계 추출은 자연어 이해가 필요하므로 LLM을 사용하지만, 온톨로지 매핑은 명확한 규칙으로 처리한다. 이렇게 분리함으로써 LLM의 비결정성이 온톨로지 구조에 영향을 주지 않는다.

---

## 2. LLM 관계 추출

### 2.1 추출 관계 유형

| 관계 | 의미 | 주체 유형 | 객체 유형 |
|------|------|----------|----------|
| `INITIATED_PROCESS` | 프로세스 개시 | COMPANY | PROCESS_STEP |
| `ASSIGNED_TO` | 리소스 배정 | COMPANY/PERSON | METRIC |
| `OWNS_ASSET` | 자산 소유 | COMPANY | ASSET_TYPE |
| `HAS_CONTRACT_WITH` | 계약 관계 | COMPANY | COMPANY |
| `SUPPLIES_TO` | 공급 관계 | COMPANY | COMPANY |
| `APPOINTED_AS` | 직위 임명 | PERSON | PROCESS_STEP |
| `DECIDED` | 의사결정 | DEPARTMENT | PROCESS_STEP |
| `MEASURED_AS` | 지표 측정 | PROCESS_STEP | METRIC |
| `IMPROVED_BY` | 지표 개선 | METRIC | PROCESS_STEP |
| `ALLOCATED_TO` | 금액 배분 | AMOUNT | COMPANY/PROCESS_STEP |
| `VALUED_AT` | 가액 평가 | ASSET_TYPE | AMOUNT |
| `OCCURRED_ON` | 일자 발생 | PROCESS_STEP | DATE |

### 2.2 관계 추출 프롬프트

```
시스템 프롬프트:

당신은 한국 비즈니스 문서에서 개체 간 관계를 추출하는 전문가입니다.

추출 규칙:
1. 반드시 원문에 근거가 있는 관계만 추출합니다
2. 추론이나 상식에 의한 관계는 추출하지 않습니다
3. 하나의 문장에서 여러 관계가 추출될 수 있습니다
4. 동일 관계의 반복은 가장 신뢰도 높은 것만 남깁니다

예시:
텍스트: "대상 조직 XYZ 주식회사는 2024년 1월 15일 프로세스 분석을 개시하였다."
관계:
- (XYZ 주식회사, INITIATED_PROCESS, 프로세스 분석) confidence=0.97
- (프로세스 분석, OCCURRED_ON, 2024-01-15) confidence=0.99

텍스트: "국민은행과의 공급 계약 금액 40억원은 본사 건물 담보로 설정되어 있다."
관계:
- (공급 계약 40억원, HAS_CONTRACT_WITH, 국민은행) confidence=0.95
```

### 2.3 관계 추출 전략

#### 엔터티 페어 전략

큰 개체 집합에서 모든 쌍을 검사하면 O(n^2) 비용이 발생한다. 이를 최적화하기 위해:

```python
async def extract_relations_smart(
    self, text: str, entities: list[dict]
) -> list[dict]:
    """
    Smart relation extraction:
    1. Group entities by proximity in text
    2. Extract relations only for nearby entity pairs
    3. Cross-group relations only for high-salience entities
    """
    # Sort entities by position
    sorted_entities = sorted(entities, key=lambda e: e.get("span_start", 0))

    # Create overlapping windows of entities
    windows = self._create_entity_windows(sorted_entities, window_size=5)

    all_relations = []
    for window in windows:
        relations = await self.extract_relations(text, window)
        all_relations.extend(relations.get("relations", []))

    # Deduplicate
    return self._deduplicate_relations(all_relations)
```

---

## 3. 규칙 기반 온톨로지 매핑

### 3.1 매핑 규칙 테이블

```python
# app/extraction/ontology_mapper.py

ENTITY_TO_ONTOLOGY_MAP = {
    # entity_type -> (ontology_layer, default_label)
    "COMPANY": ("resource", "Company:Resource"),
    "PERSON": ("resource", "Employee:Resource"),  # or separate Person node
    "DEPARTMENT": (None, None),  # Departments are metadata, not ontology nodes
    "AMOUNT": (None, None),  # Amounts are properties, not standalone nodes
    "DATE": (None, None),    # Dates are properties
    "ASSET_TYPE": ("resource", "Asset:Resource"),
    "PROCESS_STEP": ("process", None),  # Subtype determined by process name
    "METRIC": ("measure", None),        # Subtype determined by metric type
    "CONTRACT": ("resource", "Contract:Resource"),
    "FINANCIAL_METRIC": ("resource", "Financial:Resource"),
    "REGULATION": (None, None),  # Regulatory refs are metadata
}

RELATION_TO_ONTOLOGY_MAP = {
    # (predicate, subject_layer, object_layer) -> ontology_relation_type
    ("INITIATED_PROCESS", "resource", "process"): "PARTICIPATES_IN",
    ("ASSIGNED_TO", "resource", "process"): "PARTICIPATES_IN",
    ("OWNS_ASSET", "resource", "resource"): "OWNS",
    ("HAS_CONTRACT_WITH", "resource", "resource"): "HAS_CONTRACT_WITH",
    ("SUPPLIES_TO", "resource", "resource"): "SUPPLIES_TO",
    ("MEASURED_AS", "process", "measure"): "PRODUCES",
    ("IMPROVED_BY", "process", "measure"): "PRODUCES",
    ("ALLOCATED_TO", "measure", "resource"): "ALLOCATED_TO",
}
```

### 3.2 프로세스 유형 자동 분류

```python
PROCESS_TYPE_MAP = {
    # Korean text patterns -> Process subtype
    "데이터 수집": "DataCollection",
    "정보 수집": "DataCollection",
    "프로세스 분석": "ProcessAnalysis",
    "현황 분석": "ProcessAnalysis",
    "최적화": "Optimization",
    "개선": "Optimization",
    "실행": "Execution",
    "구현": "Execution",
    "검토": "Review",
    "성과 평가": "Review",
    "모니터링": "Monitoring",
    "감시": "Monitoring",
}

def classify_process(text: str) -> str:
    """
    Classify a process text into a Process subtype.
    Uses longest match first for accuracy.
    """
    normalized = text.strip().replace(" ", "")
    sorted_patterns = sorted(PROCESS_TYPE_MAP.keys(), key=len, reverse=True)
    for pattern in sorted_patterns:
        if pattern.replace(" ", "") in normalized:
            return PROCESS_TYPE_MAP[pattern]
    return "Process"  # Generic fallback
```

### 3.3 지표 유형 자동 분류

```python
METRIC_TYPE_MAP = {
    "매출": "Revenue",
    "비용": "Cost",
    "영업이익": "OperatingProfit",
    "처리량": "Throughput",
    "사이클 타임": "CycleTime",
    "ROI": "ROI",
    "고객 만족도": "CustomerSatisfaction",
}
```

### 3.4 매핑 실행

```python
class OntologyMapper:
    """
    Maps extracted entities and relations to 4-layer ontology nodes.
    This is a rule-based (deterministic) mapper.
    """

    async def map_extraction_to_ontology(
        self,
        entities: list[dict],
        relations: list[dict],
        case_id: str
    ) -> OntologyMappingResult:
        """
        Convert extracted entities/relations to ontology node/relation specs.

        Returns:
            OntologyMappingResult with:
            - nodes: list of ontology node specs
            - relations: list of ontology relation specs
            - unmapped: entities that could not be mapped
            - low_confidence: entities below HITL threshold
        """
        nodes = []
        ontology_relations = []
        unmapped = []
        low_confidence = []

        for entity in entities:
            mapping = self._map_entity(entity)
            if mapping is None:
                unmapped.append(entity)
            elif mapping["confidence"] < self.hitl_threshold:
                low_confidence.append({**entity, "mapping": mapping})
            else:
                nodes.append(mapping)

        for relation in relations:
            ont_rel = self._map_relation(relation, nodes)
            if ont_rel:
                ontology_relations.append(ont_rel)

        return OntologyMappingResult(
            nodes=nodes,
            relations=ontology_relations,
            unmapped=unmapped,
            low_confidence=low_confidence
        )
```

---

## 4. 관계 충돌 해결

### 4.1 충돌 유형

| 충돌 | 예시 | 해결 |
|------|------|------|
| **중복 관계** | 같은 두 개체 간 동일 관계 2개 | 높은 confidence 유지 |
| **모순 관계** | "지표 상승" + "지표 하락" 동시 | 양쪽 모두 유지 (시점이 다를 수 있음) |
| **순환 관계** | A->B->C->A | 온톨로지 계층 방향 규칙으로 차단 |

### 4.2 계층 방향 규칙 검증

```python
VALID_RELATION_DIRECTIONS = {
    "PARTICIPATES_IN": ("resource", "process"),
    "PRODUCES": ("process", "measure"),
    "CONTRIBUTES_TO": [("resource", "measure"), ("measure", "kpi")],
    "DEPENDS_ON": ("kpi", "measure"),
    "INFLUENCES": ("process", "kpi"),
}

def validate_relation_direction(
    relation_type: str, source_layer: str, target_layer: str
) -> bool:
    valid = VALID_RELATION_DIRECTIONS.get(relation_type)
    if valid is None:
        return True  # No restriction for auxiliary relations
    if isinstance(valid, list):
        return (source_layer, target_layer) in valid
    return (source_layer, target_layer) == valid
```

---

## 5. HITL 보완 전략

### 5.1 관계 추출이 어려운 경우

| 상황 | 대응 |
|------|------|
| 두 개체가 먼 위치에 있음 | 윈도우 검색 -> 누락 가능, HITL |
| 암묵적 관계 | "회사 자산은 50억원 상당이다" -> OWNS_ASSET 암시, HITL |
| 부정적 관계 | "지표는 달성되지 않았다" -> IMPROVED_BY 부정, 부정어 처리 필요 |
| 조건부 관계 | "승인 시 실행한다" -> 미래/조건, confidence 하향 |

### 5.2 관계 제안 (HITL 지원)

매핑되지 않은 개체에 대해 가능한 관계를 제안한다.

```python
def suggest_relations(self, unmapped_entity: dict, existing_nodes: list[dict]) -> list[dict]:
    """
    Suggest potential relations for an unmapped entity.
    Used in HITL review UI to assist human reviewer.
    """
    suggestions = []
    entity_layer = ENTITY_TO_ONTOLOGY_MAP.get(unmapped_entity["entity_type"], (None,))[0]

    for node in existing_nodes:
        node_layer = node["layer"]
        for rel_type, (src, tgt) in VALID_RELATION_DIRECTIONS.items():
            if isinstance((src, tgt), tuple):
                if (entity_layer, node_layer) == (src, tgt):
                    suggestions.append({
                        "relation_type": rel_type,
                        "target_node": node,
                        "direction": "outgoing"
                    })
                elif (node_layer, entity_layer) == (src, tgt):
                    suggestions.append({
                        "relation_type": rel_type,
                        "target_node": node,
                        "direction": "incoming"
                    })

    return suggestions
```

---

## 금지 규칙

- LLM으로 온톨로지 매핑을 수행하지 않는다 (규칙 기반만 사용)
- 계층 방향 규칙을 위반하는 관계를 생성하지 않는다
- evidence 없이 관계를 추출하지 않는다

## 필수 규칙

- 모든 추출된 관계에 evidence (근거 문장)를 포함한다
- 온톨로지 매핑 시 계층 방향 규칙을 검증한다
- 매핑 불가 개체는 unmapped로 분류하여 HITL에 전달한다

---

## 근거 문서

- `05_llm/structured-output.md` (Structured Output 설정)
- `05_llm/entity-extraction.md` (NER 상세)
- `01_architecture/ontology-4layer.md` (4계층 온톨로지)
- `01_architecture/extraction-pipeline.md` (파이프라인 전체)
