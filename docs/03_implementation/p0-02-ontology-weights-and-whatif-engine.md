# P0-02: 온톨로지 관계 가중치 + What-if DAG 전파 엔진

> **작성일**: 2026-03-20
> **소스**: KAIR `robo-data-domain-layer` (검증 완료 프로덕션 코드)
> **대상**: Axiom `services/synapse` + `services/vision`
> **의존성**: Neo4j 5.18, PostgreSQL 16, Redis (기존 인프라 활용)

---

## 1. 현재 상태 분석

### 1.1 Axiom Synapse 온톨로지 관계 스키마 (현재)

**파일**: `services/synapse/app/services/ontology_service.py`

현재 관계(relation) 데이터 모델은 **최소 스키마**로 구현되어 있다:

```python
# _normalize_relation() 에서 생성되는 relation dict
{
    "id": "rel-{uuid}",
    "case_id": str,
    "source_id": str,
    "target_id": str,
    "type": str,          # RELATED_TO, CAUSES 등 (safe_graph_name 검증)
    "properties": dict,   # 자유 형식 속성 (updated_at, tenant_id 자동 삽입)
}
```

**부재 항목**:
- `weight` (영향도 가중치) -- 없음
- `lag` (시간 지연) -- 없음
- `confidence` (관계 신뢰도) -- 없음
- `sourceLayer` / `targetLayer` -- 없음
- `fromField` / `toField` (필드 수준 연결) -- 없음

**Neo4j 동기화** (`_sync_relation_to_neo4j`):
- MERGE 방식으로 `(a)-[r:{rel_type} {id: $relation_id}]->(b)` 생성
- `SET r += $properties`로 속성 전체 교체
- 관계별 속성은 `properties` dict에 flat하게 저장됨
- 관계 타입이 동적으로 결정됨 (`_safe_graph_name` 검증)

**API 엔드포인트** (`services/synapse/app/api/ontology.py`):
- `POST /api/v3/synapse/ontology/relations` -- payload는 `dict[str, Any]` (타입 검증 없음)
- `DELETE /api/v3/synapse/ontology/relations/{relation_id}`
- 관계 수정(PUT) 엔드포인트 없음
- 관계 가중치 관련 엔드포인트 전무

### 1.2 Vision What-if API (현재)

**파일**: `services/vision/app/api/what_if.py`

현재 What-if는 **보험 시나리오 솔버** 전용으로 구현되어 있다:

| 엔드포인트 | 용도 |
|---|---|
| `POST /api/v3/cases/{case_id}/what-if` | 시나리오 CRUD (BASELINE/OPTIMISTIC/PESSIMISTIC/STRESS/CUSTOM) |
| `POST /{scenario_id}/compute` | scipy 기반 솔버 실행 (202 비동기) |
| `GET /{scenario_id}/status` | 폴링 |
| `GET /{scenario_id}/result` | 결과 조회 |
| `POST /{scenario_id}/sensitivity` | 단일 파라미터 민감도 (단순 수식) |
| `POST /{scenario_id}/breakeven` | 손익분기점 (단순 수식) |
| `POST /process-simulation` | 프로세스 시간축 시뮬레이션 (Synapse 병목 데이터 활용) |

**핵심 문제**:
- 온톨로지 DAG 기반 전파 로직 없음
- 시나리오 솔버(`scenario_solver.py`)는 보험 도메인 전용 (NPV, 배당률 등)
- 온톨로지 노드 간 인과관계 기반 시뮬레이션 기능 전무
- ML 모델 연동 구조 없음

### 1.3 기존 의존성 매핑

| 컴포넌트 | Axiom 현재 | KAIR 소스 |
|---|---|---|
| 온톨로지 모델 | in-memory dict + Neo4j | Pydantic + Neo4j SchemaStore |
| 관계 속성 | `{type, properties}` | `{weight, lag, confidence, fromField, toField, ...}` |
| What-if 엔진 | scipy 솔버 (도메인 전용) | DAG 증분 전파 엔진 + MindsDB + Fallback |
| BehaviorModel | 없음 | `OntologyBehaviorModel` + `READS_FIELD`/`PREDICTS_FIELD` |
| 상관/인과 분석 | 없음 | `CorrelationEngine` + `CausalAnalysisService` |
| 모델 검증 | 없음 | `ModelValidator` (walk-forward 백테스팅) |

---

## 2. KAIR 소스 분석

### 2.1 OntologyRelationship 속성 상세

**파일**: `KAIR/robo-data-domain-layer/app/models/ontology.py` (L124-141)

```python
class OntologyRelationship(BaseModel):
    id: str
    source: str
    target: str
    type: str                           # 16가지 관계 타입 (OntologyRelationType enum)
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    # Multi-Layer 전용 필드
    weight: Optional[float] = None      # 영향도 가중치 (0.0 ~ 1.0)
    lag: Optional[int] = None           # 시간 지연 (일 단위)
    confidence: Optional[float] = None  # 관계 신뢰도 (0.0 ~ 1.0)
    sourceLayer: Optional[str] = None   # KPI / Measure / Driver / Process / Resource
    targetLayer: Optional[str] = None
    fromField: Optional[str] = None     # FK 기반 cascading filter 연결
    toField: Optional[str] = None
```

**관계 타입 분류** (`OntologyRelationType` enum):
- **인과/영향**: CAUSES, INFLUENCES, PRODUCES, MEASURED_AS
- **구조**: CONTAINS, BELONGS_TO, OPERATES
- **행동**: READS_FIELD, PREDICTS_FIELD, HAS_BEHAVIOR
- **추적**: TRACEABLE_TO, UPDATED_BY, PREDICTED_BY, LAGS

### 2.2 OntologyBehaviorModel (What-if 시뮬레이션용)

**파일**: `KAIR/robo-data-domain-layer/app/models/ontology.py` (L274-327)

```
OntologyType   --[READS_FIELD]-->   OntologyBehavior:Model   --[PREDICTS_FIELD]-->   OntologyType
(데이터 엔티티)                     (ML 예측 모델)                                    (예측 대상)
```

**핵심 구조**:
- `OntologyBehaviorModel`: Neo4j에서 `:OntologyBehavior:Model` 멀티레이블 노드
  - `mindsdbModel`: MindsDB 모델 이름
  - `modelType`: 엔진 (lightgbm, regression, xgboost)
  - `status`: pending | training | trained | failed | disabled
  - `metrics`: JSON 문자열 (rmse, r2, mape)
  - `featureViewSQL`: 학습 데이터 생성 SQL
- `ModelFieldLink`: READS_FIELD / PREDICTS_FIELD 관계 데이터
  - READS_FIELD: `lag`, `featureName`, `importance`, `correlationScore`, `grangerPValue`
  - PREDICTS_FIELD: `confidence`

### 2.3 SimulationEngine DAG 전파 알고리즘 상세

**파일**: `KAIR/robo-data-domain-layer/app/services/whatif/simulation_engine.py`

#### 알고리즘 (증분 전파 루프)

```
1. intervention으로 변경된 변수 수집 → changed_vars = {"nodeId::field": value}
2. WHILE changed_vars 존재 AND wave < 20:
   a. 변경된 변수를 READS_FIELD로 읽는 모델 찾기 (역인덱스: field_to_models)
   b. 이미 실행된 모델 제외 (executed_models set → DAG 순환 방지)
   c. 각 모델 실행:
      - 모델의 최대 lag → effective_day = wave + max_lag
      - 입력값 구성: state[key] 또는 baseline[key] 사용
      - 예측 실행: MindsDB(1순위) → FallbackPredictor(2순위) → baseline 유지(3순위)
      - state[output_key] = predicted
      - delta = predicted - baseline_value
      - |delta| > 1e-6 이면 new_changed_vars에 추가 (다음 wave 전파)
   d. executed_models |= models_to_run
   e. changed_vars = new_changed_vars
   f. wave += 1
3. 결과 조립: traces, timeline(day별), final_state, deltas
```

#### 핵심 데이터 구조

- **InterventionSpec**: `{node_id, field, value, description}`
- **SimulationTrace**: `{model_id, model_name, inputs, output_field, baseline_value, predicted_value, delta, pct_change, wave, effective_day, triggered_by}`
- **SimulationResult**: `{scenario_name, interventions, traces, timeline, final_state, baseline_state, deltas, propagation_waves}`
- **model_graph**: `{models: [...], reads: [...], predicts: [...]}`

#### 수렴 조건
1. `max_waves = 20` (무한 루프 방지)
2. 모든 모델 출력의 delta가 `1e-6` 이하일 때 (변화 없음)
3. 실행 가능한 새 모델이 없을 때

### 2.4 ML 모델 폴백 전략

**KAIR 3단계 폴백**:

| 순서 | 엔진 | 조건 | 파일 |
|---|---|---|---|
| 1 | MindsDB | `status=="trained" && mindsdbModel 존재` | `mindsdb_model_factory.py` |
| 2 | FallbackPredictor (sklearn) | MindsDB 실패/미사용 | `mindsdb_model_factory.py` (FallbackPredictor) |
| 3 | Baseline 유지 | 모두 실패 | `simulation_engine.py` L263-265 |

**FallbackPredictor 상세**:
- 데이터 충분(>=20 rows, >=2 features) → `RandomForestRegressor(n_estimators=50, max_depth=5)`
- 그 외 → `LinearRegression`
- featureName ↔ df_column 매핑 (name_to_idx)으로 입력 정합성 보장

### 2.5 CorrelationEngine + CausalAnalysisService

**CorrelationEngine** (`correlation_engine.py`):
- Pearson + Spearman 동시 계산
- Lag 상관 스캔 (k=0..K, 최대 6)
- Granger 인과 검정 (statsmodels)
- 부분상관 (controls 통제)
- 시간적 안정성 (temporal_stability): N개 세그먼트 분할 → 부호 일관성 x 크기 안정성
- **robust_corr** = min(|Pearson|, |Spearman|) -- 이상치 견고
- **composite_score** = 0.3 * robust_corr + 0.2 * lag_corr + 0.2 * granger_sig + 0.3 * stability

**CausalAnalysisService** (`causal_analysis.py`):
- VAR(Vector Auto-Regression) 모델 피팅
- Granger 인과 검정
- 실패 시 진단: 공선성 체크 → 분해형(decomposition) 라우팅
- 곱셈 분해 + 덧셈 분해 (기여도 산출)

---

## 3. Part A: 관계 가중치 구현

### Step A-1: Neo4j 관계 속성 확장 스키마

**변경 파일**: `services/synapse/app/services/ontology_service.py`

**Neo4j 관계 속성 추가**:

```
(source_node)-[r:CAUSES {
    id: "rel-xxx",
    weight: 0.75,           # 영향도 가중치 (0.0 ~ 1.0)
    lag: 3,                 # 시간 지연 (일 단위, 0 = 동시점)
    confidence: 0.88,       # 관계 신뢰도 (0.0 ~ 1.0)
    source_layer: "Driver", # 소스 노드 레이어
    target_layer: "KPI",    # 타겟 노드 레이어
    from_field: "cost_idx", # 소스 필드 (선택)
    to_field: "defect_rate",# 타겟 필드 (선택)
    method: "granger",      # 발견 방법 (granger/correlation/decomposition/manual)
    direction: "positive",  # positive / negative
    updated_at: "2026-03-20T...",
    tenant_id: "xxx"
}]->(target_node)
```

**구현 사항**:

1. `_normalize_relation()` 메서드 확장:
   - `weight`, `lag`, `confidence` 최상위 키로 추출
   - `source_layer`, `target_layer`, `from_field`, `to_field` 추출
   - `method`, `direction` 추출
   - 모두 `properties` dict 안에 저장 (Neo4j SET r += $properties 호환)
   - 유효성 검증: weight/confidence는 0.0~1.0 범위, lag >= 0

2. `_sync_relation_to_neo4j()` 변경 없음 (이미 `SET r += $properties` 패턴)

3. 새 메서드 추가:
   - `update_relation(tenant_id, relation_id, payload)` -- 기존 관계의 속성 수정
   - `get_case_relations(case_id, filters)` -- 가중치/신뢰도 기반 필터링
   - `bulk_update_relations(tenant_id, case_id, updates)` -- 상관 분석 결과 일괄 반영

**복잡도**: Medium

### Step A-2: Synapse ontology_service.py 수정

**파일**: `services/synapse/app/services/ontology_service.py`

#### A-2a: _normalize_relation 확장

```python
def _normalize_relation(self, tenant_id: str, payload: dict[str, Any], relation_id: str | None = None) -> dict[str, Any]:
    # ... 기존 코드 유지 ...
    properties = payload.get("properties") if isinstance(payload.get("properties"), dict) else {}

    # 가중치/지연/신뢰도 추출 (최상위 키 또는 properties 내부)
    weight = payload.get("weight") or properties.get("weight")
    lag = payload.get("lag") or properties.get("lag")
    confidence = payload.get("confidence") or properties.get("confidence")
    source_layer = payload.get("source_layer") or properties.get("source_layer")
    target_layer = payload.get("target_layer") or properties.get("target_layer")
    from_field = payload.get("from_field") or properties.get("from_field")
    to_field = payload.get("to_field") or properties.get("to_field")
    method = payload.get("method") or properties.get("method")
    direction = payload.get("direction") or properties.get("direction")

    # 유효성 검증
    if weight is not None:
        weight = max(0.0, min(1.0, float(weight)))
        properties["weight"] = weight
    if lag is not None:
        properties["lag"] = max(0, int(lag))
    if confidence is not None:
        confidence = max(0.0, min(1.0, float(confidence)))
        properties["confidence"] = confidence
    if source_layer:
        properties["source_layer"] = str(source_layer)
    if target_layer:
        properties["target_layer"] = str(target_layer)
    if from_field:
        properties["from_field"] = str(from_field)
    if to_field:
        properties["to_field"] = str(to_field)
    if method:
        properties["method"] = str(method)
    if direction and direction in ("positive", "negative"):
        properties["direction"] = direction

    # ... 나머지 기존 코드 ...
```

#### A-2b: update_relation 메서드 신규

```python
async def update_relation(self, tenant_id: str, relation_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """기존 관계의 속성(weight, lag, confidence 등)을 수정"""
    case_id = self._relation_case_index.get(relation_id)
    if not case_id:
        raise KeyError("relation not found")
    current = self._relations(case_id).get(relation_id)
    if not current:
        raise KeyError("relation not found")

    # 속성 머지
    merged_properties = {**current.get("properties", {})}
    for key in ("weight", "lag", "confidence", "source_layer", "target_layer",
                "from_field", "to_field", "method", "direction"):
        if key in payload:
            merged_properties[key] = payload[key]
    if isinstance(payload.get("properties"), dict):
        merged_properties.update(payload["properties"])
    merged_properties["updated_at"] = _iso_now()

    current["properties"] = merged_properties
    if "type" in payload:
        current["type"] = _safe_graph_name(str(payload["type"]), current["type"])

    await self._sync_relation_to_neo4j(case_id=case_id, rel=current)
    return current
```

#### A-2c: bulk_update_relations 메서드 신규

```python
async def bulk_update_relations(
    self, tenant_id: str, case_id: str,
    updates: list[dict[str, Any]]
) -> dict[str, Any]:
    """상관 분석 결과를 관계에 일괄 반영 (EdgeCandidate → relation properties)"""
    updated = 0
    created = 0
    for item in updates:
        source_id = str(item.get("source_id", "")).strip()
        target_id = str(item.get("target_id", "")).strip()
        rel_type = item.get("type", "CAUSES")

        # 기존 관계 찾기 (source, target, type 일치)
        existing_rel = None
        for rel in self._relations(case_id).values():
            if (rel["source_id"] == source_id and
                rel["target_id"] == target_id and
                rel["type"] == rel_type):
                existing_rel = rel
                break

        if existing_rel:
            # 업데이트
            await self.update_relation(tenant_id, existing_rel["id"], item)
            updated += 1
        else:
            # 새로 생성
            item["case_id"] = case_id
            item["source_id"] = source_id
            item["target_id"] = target_id
            await self.create_relation(tenant_id=tenant_id, payload=item)
            created += 1

    return {"updated": updated, "created": created, "total": updated + created}
```

**복잡도**: Medium

### Step A-3: API 엔드포인트 수정

**파일**: `services/synapse/app/api/ontology.py`

#### A-3a: 관계 수정 엔드포인트 추가

```python
@router.put("/relations/{relation_id}")
async def update_relation(relation_id: str, request: Request, payload: dict[str, Any]):
    try:
        data = await ontology_service.update_relation(
            tenant_id=_tenant(request), relation_id=relation_id, payload=payload or {}
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}
```

#### A-3b: 관계 일괄 업데이트 엔드포인트

```python
@router.post("/cases/{case_id}/relations/bulk-update")
async def bulk_update_relations(case_id: str, request: Request, payload: dict[str, Any]):
    """상관/인과 분석 결과를 관계에 일괄 반영"""
    updates = payload.get("updates", [])
    if not isinstance(updates, list):
        raise HTTPException(status_code=400, detail="updates must be a list")
    try:
        data = await ontology_service.bulk_update_relations(
            tenant_id=_tenant(request), case_id=case_id, updates=updates
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}
```

#### A-3c: 기존 GET 응답에 가중치 필드 포함

현재 `get_case_ontology`가 반환하는 `relations` 내 각 관계의 `properties`에 이미 weight/lag/confidence가 포함되므로, **응답 스키마 변경은 불필요**. 단, 프론트엔드가 쉽게 접근할 수 있도록 필터링 파라미터 추가:

```python
@router.get("/cases/{case_id}/ontology")
async def get_case_ontology(
    case_id: str,
    layer: str = "all",
    include_relations: bool = True,
    verified_only: bool = False,
    min_weight: float | None = None,      # 신규: 최소 가중치 필터
    min_confidence: float | None = None,  # 신규: 최소 신뢰도 필터
    limit: int = 500,
    offset: int = 0,
):
```

**복잡도**: Low

### Step A-4: 프론트엔드 영향 범위

**Canvas 프론트엔드** (참고 -- 별도 구현 계획 필요):

| 영역 | 변경 내용 |
|---|---|
| 온톨로지 그래프 뷰어 | 엣지 두께 = weight, 색상 = confidence, 점선/실선 = lag 유무 |
| 관계 편집 패널 | weight(0~1 슬라이더), lag(숫자 입력), confidence(0~1 슬라이더) 필드 추가 |
| 관계 타입 셀렉터 | CAUSES, INFLUENCES 등 Multi-Layer 관계 타입 추가 |
| 필터 패널 | min_weight, min_confidence 슬라이더 필터 |
| API 호출 | `PUT /relations/{id}` 연동, `POST /relations/bulk-update` 연동 |

---

## 4. Part B: What-if DAG 전파 엔진 구현

### Step B-1: 디렉토리 구조 설계

```
services/vision/app/
  engines/
    scenario_solver.py          # 기존 (보험 도메인 전용, 유지)
    whatif_simulation.py        # 신규: DAG 증분 전파 엔진
    whatif_models.py            # 신규: InterventionSpec, SimulationTrace, SimulationResult
    whatif_fallback.py          # 신규: FallbackPredictor (sklearn 기반)
  api/
    what_if.py                  # 기존 (보험 시나리오, 유지)
    what_if_dag.py              # 신규: 온톨로지 DAG What-if API
  services/
    vision_runtime.py           # 기존 (확장)
```

**복잡도**: Low (디렉토리 생성만)

### Step B-2: 데이터 모델 (whatif_models.py)

**신규 파일**: `services/vision/app/engines/whatif_models.py`

KAIR의 `simulation_engine.py`에서 dataclass를 이식:

```python
@dataclass
class InterventionSpec:
    """개입 정의 — 사용자가 "이 변수를 이 값으로 변경하면?" 지정"""
    node_id: str        # 온톨로지 노드 ID
    field: str          # 필드명
    value: float        # 개입 값
    description: str = ""

@dataclass
class SimulationTrace:
    """단일 모델 실행 트레이스"""
    model_id: str
    model_name: str
    inputs: Dict[str, float]
    output_field: str          # "nodeId::fieldName"
    baseline_value: float
    predicted_value: float
    delta: float
    pct_change: float
    wave: int = 0              # 전파 단계 (0 = 직접 영향)
    effective_day: int = 0     # lag 반영된 실제 Day
    triggered_by: List[str] = field(default_factory=list)

@dataclass
class SimulationResult:
    """시뮬레이션 전체 결과"""
    scenario_name: str
    interventions: List[InterventionSpec]
    traces: List[SimulationTrace]
    timeline: Dict[int, List[Dict]]   # day -> [traces]
    final_state: Dict[str, float]
    baseline_state: Dict[str, float]
    deltas: Dict[str, float]
    executed_at: str
    propagation_waves: int

    def to_dict(self) -> Dict[str, Any]: ...  # KAIR과 동일 직렬화
```

**복잡도**: Low

### Step B-3: DAG 전파 엔진 (whatif_simulation.py)

**신규 파일**: `services/vision/app/engines/whatif_simulation.py`

KAIR의 `WhatIfSimulationEngine`을 거의 그대로 이식하되, Axiom 환경에 맞게 조정:

#### 핵심 변경점 (KAIR → Axiom)

| 항목 | KAIR | Axiom |
|---|---|---|
| MindsDB 연동 | `MindsDBModelFactory.predict()` | **Phase 1에서 제외** (FallbackPredictor만 사용) |
| 모델 그래프 소스 | Neo4j SchemaStore | Synapse API 호출 (HTTP) |
| baseline 데이터 | FeatureViewBuilder (direct-sql) | Weaver/Oracle 쿼리 결과 또는 Synapse 캐시 |
| 설정 | `settings.MINDSDB_HOST` | 환경변수 `WHATIF_MAX_WAVES`, `WHATIF_CONVERGENCE_THRESHOLD` |

#### 알고리즘 (KAIR 동일, 20-wave, 수렴 조건)

```python
class WhatIfDAGEngine:
    """온톨로지 DAG 기반 증분 전파 What-if 시뮬레이션 엔진"""

    MAX_WAVES = 20
    CONVERGENCE_THRESHOLD = 1e-6

    def __init__(self, fallback_predictor=None):
        self.fallback = fallback_predictor

    async def run_simulation(
        self,
        model_graph: Dict[str, Any],
        interventions: List[InterventionSpec],
        baseline_data: Dict[str, float],
        scenario_name: str = "Scenario",
    ) -> SimulationResult:
        # 1. 인덱스 구축
        model_inputs, model_output, field_to_models, model_map = self._build_indices(model_graph)

        # 2. 상태 초기화 + 개입값 적용
        state = dict(baseline_data)
        changed_vars = {}
        for intervention in interventions:
            key = f"{intervention.node_id}::{intervention.field}"
            state[key] = intervention.value
            changed_vars[key] = intervention.value

        # 3. 증분 전파 루프
        executed_models = set()
        all_traces = []
        timeline = defaultdict(list)
        wave = 0

        while changed_vars and wave < self.MAX_WAVES:
            models_to_run, trigger_map = self._find_affected_models(
                changed_vars, field_to_models, executed_models
            )
            if not models_to_run:
                break

            new_changed_vars = {}
            for model_id in models_to_run:
                trace = await self._execute_model(
                    model_id, model_map, model_inputs, model_output,
                    state, baseline_data, wave, trigger_map
                )
                if trace:
                    all_traces.append(trace)
                    timeline[trace.effective_day].append(trace_to_dict(trace))
                    if abs(trace.delta) > self.CONVERGENCE_THRESHOLD:
                        new_changed_vars[trace.output_field] = trace.predicted_value

            executed_models |= models_to_run
            changed_vars = new_changed_vars
            wave += 1

        # 4. 결과 조립
        return SimulationResult(...)

    async def _execute_model(self, model_id, ...):
        """단일 모델 실행: FallbackPredictor → baseline 유지"""
        # disabled 모델 건너뜀
        # 입력값 구성 (state에서)
        # FallbackPredictor.predict() 호출
        # 실패 시 baseline 유지
        # SimulationTrace 반환

    async def compare_scenarios(self, model_graph, scenarios, baseline_data):
        """여러 시나리오 비교 실행"""
```

**복잡도**: High

### Step B-4: FallbackPredictor (whatif_fallback.py)

**신규 파일**: `services/vision/app/engines/whatif_fallback.py`

KAIR의 `FallbackPredictor` 이식:

```python
class FallbackPredictor:
    """sklearn 기반 간이 예측기 (MindsDB 미사용 시 대체)"""

    def __init__(self):
        self._models: Dict[str, Any] = {}

    def train(self, model_name, df, target_col, feature_cols, feature_name_map=None):
        """
        데이터 충분(>=20, >=2 features) → RandomForestRegressor
        그 외 → LinearRegression
        """

    def predict(self, model_name, input_data: Dict[str, float]) -> Optional[float]:
        """featureName → index 매핑으로 예측"""
```

**의존성**: `scikit-learn` (requirements.txt에 추가)

**복잡도**: Medium

### Step B-5: 모델 그래프 로딩 (Synapse 연동)

**Vision → Synapse API 호출**로 모델 그래프를 로딩해야 한다.

#### 신규: Synapse에 BehaviorModel 관련 API 추가

**파일**: `services/synapse/app/api/ontology.py`에 추가

```python
# -- BehaviorModel CRUD --

@router.get("/cases/{case_id}/behavior-models")
async def list_behavior_models(case_id: str):
    """해당 case의 모든 OntologyBehavior:Model 노드 + READS/PREDICTS 링크 조회"""

@router.post("/cases/{case_id}/behavior-models")
async def create_behavior_model(case_id: str, request: Request, payload: dict[str, Any]):
    """OntologyBehavior:Model 노드 생성 + READS/PREDICTS 링크 생성"""

@router.put("/behavior-models/{model_id}")
async def update_behavior_model(model_id: str, request: Request, payload: dict[str, Any]):
    """모델 상태/메트릭 업데이트 (학습 완료 시)"""

@router.delete("/behavior-models/{model_id}")
async def delete_behavior_model(model_id: str):
    """모델 + 연결된 READS/PREDICTS 링크 모두 삭제"""

@router.get("/cases/{case_id}/model-graph")
async def get_model_graph(case_id: str):
    """시뮬레이션용 모델 DAG 구조 반환 (models + reads + predicts)"""
```

#### OntologyService에 BehaviorModel 메서드 추가

**파일**: `services/synapse/app/services/ontology_service.py`

```python
async def create_behavior_model(self, case_id: str, payload: dict) -> dict:
    """OntologyBehavior:Model 노드를 Neo4j에 생성"""
    # :OntologyBehavior:Model 멀티레이블로 MERGE

async def get_model_graph(self, case_id: str) -> dict:
    """
    Neo4j에서 모델 DAG를 로드하여 시뮬레이션 구조로 변환.
    Returns:
        {
            "models": [{id, name, status, mindsdbModel, ...}],
            "reads": [{modelId, sourceNodeId, field, lag, featureName}],
            "predicts": [{modelId, targetNodeId, field, confidence}],
        }
    """
    # MATCH (m:OntologyBehavior:Model {case_id: $case_id})
    # OPTIONAL MATCH (src)-[r:READS_FIELD]->(m)
    # OPTIONAL MATCH (m)-[p:PREDICTS_FIELD]->(tgt)
    # RETURN ...
```

**복잡도**: High

### Step B-6: What-if DAG API 엔드포인트

**신규 파일**: `services/vision/app/api/what_if_dag.py`

```python
router = APIRouter(prefix="/api/v3/cases/{case_id}/whatif-dag", tags=["What-If DAG"])

# ── 시뮬레이션 실행 ──

@router.post("/simulate")
async def run_dag_simulation(case_id: str, payload: SimulateRequest):
    """
    온톨로지 DAG 기반 What-if 시뮬레이션 실행.

    요청:
    {
        "scenario_name": "원가 인상 시나리오",
        "interventions": [
            {"nodeId": "node_costs", "field": "cost_index", "value": 150, "description": "원가 50% 인상"}
        ],
        "snapshot_date": "2026-03-15"  // 선택: 베이스라인 시점
    }

    응답:
    {
        "success": true,
        "scenario_name": "원가 인상 시나리오",
        "interventions": [...],
        "traces": [
            {
                "model_id": "model_defect_rate_abc123",
                "model_name": "불량률 예측",
                "output_field": "node_quality::defect_rate",
                "baseline_value": 3.2,
                "predicted_value": 4.8,
                "delta": 1.6,
                "pct_change": 50.0,
                "wave": 0,
                "effective_day": 0,
                "triggered_by": ["node_costs::cost_index"]
            },
            ...
        ],
        "timeline": {
            "0": [...],   // Day 0 변화
            "3": [...],   // Day +3 변화 (lag=3인 모델)
            "5": [...]    // Day +5 변화 (2차 연쇄)
        },
        "final_state": {"node_quality::defect_rate": 4.8, ...},
        "baseline_state": {"node_quality::defect_rate": 3.2, ...},
        "deltas": {"node_quality::defect_rate": 1.6, ...},
        "propagation_waves": 3
    }
    """

@router.post("/compare-scenarios")
async def compare_dag_scenarios(case_id: str, payload: CompareRequest):
    """여러 시나리오를 동시 실행하고 delta 비교"""

# ── 스냅샷 (베이스라인) ──

@router.get("/snapshot")
async def get_baseline_snapshot(case_id: str, date: str | None = None):
    """현재 또는 특정 시점의 모든 온톨로지 변수 값 조회"""

# ── 모델 상태 ──

@router.get("/models")
async def list_simulation_models(case_id: str):
    """시뮬레이션에 사용 가능한 모델 목록 + 상태"""
```

**main.py 등록**:

```python
from app.api.what_if_dag import router as what_if_dag_router
app.include_router(what_if_dag_router)
```

**복잡도**: Medium

### Step B-7: Vision → Synapse 클라이언트

**신규 파일**: `services/vision/app/clients/synapse_client.py`

```python
class SynapseClient:
    """Synapse API 클라이언트 (모델 그래프, 온톨로지 데이터 조회)"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("SYNAPSE_BASE_URL", "")

    async def get_model_graph(self, case_id: str) -> Dict[str, Any]:
        """GET /api/v3/synapse/ontology/cases/{case_id}/model-graph"""

    async def get_ontology_snapshot(self, case_id: str) -> Dict[str, float]:
        """온톨로지 노드의 현재 값 스냅샷 (baseline_data 구성용)"""

    async def get_case_ontology(self, case_id: str) -> Dict[str, Any]:
        """GET /api/v3/synapse/ontology/cases/{case_id}/ontology"""
```

**복잡도**: Low

---

## 5. Part C: BehaviorModel 바인딩

### Step C-1: 온톨로지 노드 ↔ ML 모델 연결 스키마

**Neo4j 그래프 패턴**:

```
(:OntologyNode {case_id, node_id, name: "원가 지수"})
    -[:READS_FIELD {field: "cost_index", lag: 0, featureName: "cost_index"}]->
(:OntologyBehavior:Model {case_id, model_id, name: "불량률 예측", status: "trained"})
    -[:PREDICTS_FIELD {field: "defect_rate", confidence: 0.85}]->
(:OntologyNode {case_id, node_id, name: "품질 지표"})
```

**OntologyBehavior:Model 노드 속성**:

```
{
    case_id: str,
    model_id: str,
    name: str,              # "불량률 예측"
    behavior_type: "Model",
    status: str,            # pending | training | trained | failed | disabled
    model_type: str,        # "RandomForest" | "LinearRegression" | "GradientBoosting"
    metrics_json: str,      # '{"rmse": 2.3, "r2": 0.89, "mape": 4.2}'
    trained_at: str,
    version: int,
    feature_view_sql: str,  # 학습 데이터 생성 SQL (재현용)
    train_data_rows: int,
    algorithm: str,         # "GradientBoosting(enriched) + ExpandingWindowCV (4 folds)"
}
```

**READS_FIELD 관계 속성**:

```
{
    field: str,              # 소스 노드의 필드명
    lag: int,                # 시간 지연 (0 = 동시점)
    feature_name: str,       # 모델 내부 피처명 (lag>0이면 "field_lag3")
    importance: float,       # 피처 중요도 (학습 후)
    correlation_score: float,# 상관계수
    granger_p_value: float,  # Granger 인과 p-value
}
```

**PREDICTS_FIELD 관계 속성**:

```
{
    field: str,              # 타겟 노드의 필드명
    confidence: float,       # R2 기반 예측 신뢰도
}
```

**복잡도**: Medium

### Step C-2: 시계열 메타데이터 추가

**OntologyService의 노드 속성 확장**:

현재 Axiom의 `_normalize_node()`에서 `properties` dict에 자유롭게 속성을 넣을 수 있으므로, 별도 스키마 변경 없이 아래 속성을 properties에 포함:

```python
properties = {
    # ... 기존 속성 ...
    "time_column": "sales_date",       # 시간축 필드명
    "time_granularity": "day",         # minute | hour | day | week | month | year
    "aggregation_method": "sum",       # mean | sum | last | first | max | min
    "data_source": "postgres.public.daily_sales",  # 바인딩된 테이블
    "unit": "KRW",                     # 측정 단위
    "formula": "revenue - cost",       # 계산 공식 (KPI/Measure용)
    "target_value": 95.0,              # 목표값 (KPI용)
}
```

**KAIR 호환 메타데이터 필드**:

| 필드 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `time_column` | string | 시간축 필드명 | "sales_date", "metric_date" |
| `time_granularity` | string | 시간 단위 | "minute", "hour", "day", "week", "month", "year" |
| `aggregation_method` | string | 집계 방식 | "mean", "sum", "last", "first", "max", "min" |
| `data_source` | string | 바인딩된 테이블 (FQN) | "postgres.public.daily_sales" |
| `unit` | string | 측정 단위 | "%", "KRW", "count" |
| `formula` | string | 계산 공식 (Measure/KPI) | "revenue - cost" |
| `target_value` | float | 목표값 (KPI) | 95.0 |
| `thresholds` | JSON | 임계값 | {"warning": 80, "critical": 90} |

**구현**: 노드 생성/수정 API에서 이 필드들을 `properties`에 저장. FeatureViewBuilder 이식 시 이 메타데이터를 활용하여 시간 컬럼 자동 감지, 집계 방식 결정 등에 사용.

**복잡도**: Low

---

## 6. 의존성 및 구현 순서

### 6.1 구현 의존성 DAG

```
A-1 (Neo4j 스키마 확장)
  └─> A-2 (ontology_service 수정)
        └─> A-3 (API 엔드포인트)
              └─> A-4 (프론트엔드 -- 별도 계획)

C-1 (BehaviorModel Neo4j 스키마)
  └─> C-2 (시계열 메타데이터)
        └─> B-5 (Synapse BehaviorModel API)
              └─> B-7 (Vision → Synapse 클라이언트)
                    └─> B-3 (DAG 전파 엔진)
                          └─> B-6 (What-if DAG API)

B-1 (디렉토리 구조)
B-2 (데이터 모델)
B-4 (FallbackPredictor)
  └─> B-3 (DAG 전파 엔진)
```

### 6.2 권장 구현 순서

| 단계 | 스텝 | 예상 시간 | 설명 |
|---|---|---|---|
| 1 | A-1 + A-2 | 4h | Neo4j 관계 속성 확장 + ontology_service 수정 |
| 2 | A-3 | 2h | API 엔드포인트 추가/수정 |
| 3 | C-1 + C-2 | 3h | BehaviorModel 스키마 + 시계열 메타데이터 |
| 4 | B-5 | 6h | Synapse BehaviorModel CRUD + model-graph API |
| 5 | B-1 + B-2 | 1h | 디렉토리 구조 + 데이터 모델 |
| 6 | B-4 | 3h | FallbackPredictor 이식 |
| 7 | B-3 | 8h | DAG 전파 엔진 이식 (핵심) |
| 8 | B-7 | 2h | Synapse 클라이언트 |
| 9 | B-6 | 4h | What-if DAG API 엔드포인트 |
| 10 | 통합 테스트 | 4h | E2E 시뮬레이션 테스트 |
| **합계** | | **~37h** | |

---

## 7. 테스트 계획

### 7.1 단위 테스트

| 대상 | 테스트 항목 | 파일 |
|---|---|---|
| `_normalize_relation` | weight/lag/confidence 범위 검증, 기본값, None 처리 | `tests/synapse/test_ontology_relation_weights.py` |
| `update_relation` | 속성 머지, 존재하지 않는 관계 404, 유효성 | `tests/synapse/test_ontology_relation_crud.py` |
| `bulk_update_relations` | 일괄 생성/업데이트, 빈 목록, 잘못된 node_id | `tests/synapse/test_ontology_bulk.py` |
| `InterventionSpec` | 데이터 직렬화/역직렬화 | `tests/vision/test_whatif_models.py` |
| `WhatIfDAGEngine` | 단일 개입 전파, 다중 개입, 순환 방지 (20 wave), 수렴 | `tests/vision/test_whatif_dag_engine.py` |
| `FallbackPredictor` | train/predict, featureName 매핑, 모델 미존재 | `tests/vision/test_whatif_fallback.py` |
| `SimulationResult.to_dict` | JSON 직렬화, NaN/inf 처리 | `tests/vision/test_whatif_models.py` |

### 7.2 통합 테스트

| 시나리오 | 설명 |
|---|---|
| E2E 단일 개입 | 노드 3개 + 관계 2개 + 모델 2개 → 개입 1개 → 전파 결과 검증 |
| E2E 다중 개입 | 동시에 2개 변수 개입 → 2개 모델 독립 실행 → 합류점 검증 |
| E2E lag 전파 | lag=3 관계 → timeline[3]에 결과 기록 검증 |
| E2E 시나리오 비교 | 2개 시나리오 비교 → comparison dict 검증 |
| E2E Synapse 연동 | Vision → Synapse model-graph API → 시뮬레이션 실행 |
| 비정상: 모델 없음 | model_graph.models = [] → 빈 결과 반환 |
| 비정상: 순환 | A→B→C→A → max_waves=20에서 종료 |

### 7.3 성능 테스트

| 항목 | 기준 |
|---|---|
| 100 노드, 200 관계 시뮬레이션 | < 5초 |
| 20 wave 전파 | < 10초 |
| 동시 5개 시나리오 비교 | < 30초 |

---

## 8. 위험 요소

### 8.1 기술적 위험

| 위험 | 영향도 | 완화 전략 |
|---|---|---|
| **Neo4j 동적 관계 타입** | High | Synapse의 `_sync_relation_to_neo4j`는 f-string으로 관계 타입 삽입. 16가지 타입이 추가되면 Neo4j 인덱스 전략 필요. 초기에는 CAUSES/INFLUENCES만 지원하고 점진 확장. |
| **in-memory 캐시 정합성** | High | `OntologyService`는 `_case_nodes`/`_case_relations` dict를 in-memory로 유지. 서버 재시작 시 데이터 유실. **해결**: Neo4j를 SSOT로 사용하고, 시작 시 `get_case_ontology` 호출로 로드하는 lazy loading 패턴 도입 검토. |
| **sklearn 의존성** | Medium | Vision 서비스에 `scikit-learn` 추가. Docker 이미지 크기 증가 (~100MB). requirements.txt에 명시적 버전 고정 필요. |
| **Synapse → Vision 순환 의존** | Medium | Vision이 Synapse를 호출하고, 현재 docker-compose에서 Vision이 Synapse에 의존. 방향은 Vision → Synapse 단방향이므로 순환은 없으나, Synapse 장애 시 What-if 전체 불가. **해결**: model_graph 캐싱 (Redis, TTL=5분). |
| **FallbackPredictor 정확도** | Medium | sklearn 모델은 MindsDB 대비 정확도가 낮을 수 있음. **해결**: 모델 metrics(R2, RMSE)를 UI에 표시하여 사용자가 신뢰도 판단 가능하게. |
| **대규모 그래프 성능** | Low | 20 wave x 100 모델 = 최대 2000회 예측. FallbackPredictor는 numpy 기반으로 단일 예측 < 1ms. 전체 < 5초 목표 달성 가능. |

### 8.2 기능적 위험

| 위험 | 완화 전략 |
|---|---|
| 기존 보험 What-if와 충돌 | 별도 라우터(`/whatif-dag`)로 분리. 기존 `/what-if`는 그대로 유지. |
| 프론트엔드 호환성 | Canvas 프론트엔드의 온톨로지 뷰어가 새 속성(weight/lag/confidence)을 무시하면 기존 동작 유지. 점진적 UI 업데이트. |
| 데이터 마이그레이션 | 기존 관계에 weight/lag/confidence 없음 → 기본값 `None` → 필터링 시 `None`은 "가중치 미설정"으로 표시. 마이그레이션 불필요. |

### 8.3 Phase 2 확장 고려사항 (본 계획 범위 밖)

| 항목 | 설명 |
|---|---|
| CorrelationEngine 이식 | 온톨로지 노드 데이터에서 자동 상관/인과 분석 → EdgeCandidate 생성 |
| ModelGraphBuilder 이식 | EdgeCandidate에서 자동 모델 DAG 구성 |
| ModelValidator 이식 | walk-forward 백테스팅 |
| FeatureViewBuilder 이식 | 온톨로지 노드 dataSource에서 시계열 DataFrame 자동 생성 |
| MindsDB 연동 | 프로덕션 ML 모델 학습/예측 |
| Watch Agent 연동 | 시나리오 프로필 저장 → 주기적 자동 재실행 |

---

## 부록: 파일별 변경 요약

### 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `services/synapse/app/services/ontology_service.py` | `_normalize_relation` 확장, `update_relation`/`bulk_update_relations`/`create_behavior_model`/`get_model_graph` 추가 |
| `services/synapse/app/api/ontology.py` | `PUT /relations/{id}`, `POST /relations/bulk-update`, BehaviorModel CRUD 5개 엔드포인트 추가 |
| `services/vision/app/main.py` | `what_if_dag_router` 등록 |
| `services/vision/requirements.txt` | `scikit-learn>=1.4.0` 추가 |
| `docker-compose.yml` | 변경 없음 (기존 인프라 활용) |

### 신규 파일

| 파일 | 설명 |
|---|---|
| `services/vision/app/engines/whatif_models.py` | InterventionSpec, SimulationTrace, SimulationResult |
| `services/vision/app/engines/whatif_simulation.py` | WhatIfDAGEngine (증분 전파 엔진) |
| `services/vision/app/engines/whatif_fallback.py` | FallbackPredictor (sklearn 기반) |
| `services/vision/app/api/what_if_dag.py` | DAG What-if API 라우터 |
| `services/vision/app/clients/synapse_client.py` | Synapse API 클라이언트 |
| `tests/synapse/test_ontology_relation_weights.py` | 관계 가중치 단위 테스트 |
| `tests/synapse/test_ontology_bulk.py` | 일괄 업데이트 테스트 |
| `tests/vision/test_whatif_dag_engine.py` | DAG 전파 엔진 단위/통합 테스트 |
| `tests/vision/test_whatif_fallback.py` | FallbackPredictor 테스트 |
| `tests/vision/test_whatif_models.py` | 데이터 모델 직렬화 테스트 |
