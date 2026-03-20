# P0-01: Causal Analysis Engine 이식 구현 계획

> **우선순위**: P0 (최우선)
> **소스**: KAIR `robo-data-domain-layer/app/services/causal_analysis.py` (575 LOC)
> **대상**: Axiom Vision 서비스
> **예상 소요**: 5-7일 (1인 기준)
> **작성일**: 2026-03-20

---

## 1. 현재 상태 분석

### 1.1 Axiom 관련 코드 현황

#### Vision 서비스 (`services/vision/`)

| 파일 | 역할 | 인과 분석 관련성 |
|------|------|-----------------|
| `app/api/root_cause.py` | 근본원인 분석 API (7개 엔드포인트) | **직접 관련** — 현재 하드코딩된 FeatureSpec 기반의 결정론적 엔진 사용. 실제 시계열 통계 분석 없음 |
| `app/services/root_cause_engine.py` | 근본원인 분석 엔진 (207 LOC) | **교체 대상** — `FEATURE_SPECS` 튜플에 5개 변수 하드코딩, seed 기반 의사난수로 actual_value 생성. 실제 데이터 분석 0% |
| `app/services/vision_runtime.py` | Vision 상태 관리 런타임 | **수정 필요** — `run_root_cause_engine()` 호출부, `root_cause_by_case` 저장소 |
| `app/api/what_if.py` | What-If 시나리오 API | 간접 관련 — 시나리오 결과에 인과 그래프 연결 가능 |
| `app/engines/scenario_solver.py` | scipy 기반 시나리오 솔버 | 간접 관련 — 인과 엣지 가중치를 솔버 입력으로 활용 가능 |

**핵심 문제점**: 현재 `root_cause_engine.py`는 **실제 인과 분석이 아닌 하드코딩된 시뮬레이션**이다. `_seed_from()` + `_unit()` 함수로 결정론적 의사 랜덤 값을 생성할 뿐, 시계열 데이터를 전혀 분석하지 않는다.

#### Synapse 서비스 (`services/synapse/`)

| 파일 | 역할 | 인과 분석 관련성 |
|------|------|-----------------|
| `app/services/ontology_service.py` | 온톨로지 CRUD (417 LOC) | **데이터 소스** — 노드/관계 저장소. `case_id` 기반 격리. 관계 타입에 CAUSES, DERIVED_FROM 등 이미 정의 |
| `app/api/ontology.py` | 온톨로지 REST API | 인과 분석 결과를 관계로 저장할 때 활용 |
| `app/services/metadata_graph_service.py` | Neo4j 메타데이터 CRUD | **데이터 소스** — 테이블/컬럼 매핑 정보 (concept mapping) |
| `app/services/impact_analysis_service.py` | BFS 영향도 분석 (220 LOC) | **연계 대상** — 인과 그래프 엣지로 BFS 수행. 현재 정적 관계만 탐색 |

#### KAIR 온톨로지 모델 (`app/models/ontology.py`)

이미 인과 분석에 필요한 필드가 정의되어 있다:

```python
class OntologyRelationship(BaseModel):
    weight: Optional[float] = None      # 영향도 가중치 (0.0 ~ 1.0)
    lag: Optional[int] = None            # 시간 지연 (일 단위)
    confidence: Optional[float] = None   # 관계 신뢰도 (0.0 ~ 1.0)

class OntologyRelationType(str, Enum):
    CAUSES = "CAUSES"                    # 인과 관계
    INFLUENCES = "INFLUENCES"            # 영향 관계
    LAGS = "LAGS"                        # 시간 지연

class EdgeCandidate(BaseModel):          # 인과 분석 결과 후보
    correlationPearson, correlationSpearman, lagCorrelation, grangerPValue 등
```

이 모델들은 **Axiom Synapse의 온톨로지 서비스에는 아직 반영되지 않았다**. Synapse의 `OntologyService`는 관계에 `type`과 `properties` dict만 저장하고, `weight/lag/confidence`를 1급 필드로 다루지 않는다.

### 1.2 의존성 현황

| 패키지 | Vision (`requirements.txt`) | Synapse (`requirements.txt`) |
|--------|:-:|:-:|
| `scipy` | `>=1.10,<2` | 없음 |
| `numpy` | `>=1.24,<3` | 없음 |
| `pandas` | 없음 | `==2.2.1` |
| `statsmodels` | 없음 | 없음 |

**KAIR 인과 분석 엔진이 필요로 하는 패키지**:
- `pandas` — DataFrame 조작
- `numpy` — 수치 연산
- `scipy.stats` — `pearsonr` (상관 분석)
- `statsmodels.tsa.stattools` — `grangercausalitytests` (Granger 인과 검정)
- `statsmodels.tsa.vector_ar.var_model` — `VAR` (벡터 자기회귀 모델)

---

## 2. KAIR 소스 분석

### 2.1 아키텍처 개요

```
CausalAnalysisService
 ├── analyze_causality()           # 진입점 (하이브리드 엔진 호출)
 │   └── analyze_causality_hybrid() # 핵심 로직
 │       ├── [1단계] relation_hints 기반 동학/분해 분류
 │       ├── [2단계] VAR 피팅 + Granger 검정 (동학형)
 │       ├── [3단계] VAR 실패 시 → _diagnose_collinearity()
 │       │   ├── 분해형 판정 → _decomposition_contribution_*()
 │       │   └── 비분해형 → 상관 분석 보강
 │       └── [4단계] 분해형 소스 별도 처리
 ├── fit_var_model()               # VAR 모델 단독 피팅
 ├── test_granger_causality()      # Granger 검정 단독 실행
 └── calculate_impact_scores()     # 엣지 목록 → 변수별 영향도 점수
```

### 2.2 알고리즘 상세

#### 하이브리드 라우팅 전략

```
입력: DataFrame + target_var + relation_hints
 │
 ├─ relation_hints에 "deterministic" 표시된 소스 → 분해형으로 분류
 ├─ 나머지 → VAR/Granger 시도
 │
 ├─ VAR 피팅 시도 (AIC 기반 최적 시차 선택)
 │   ├─ 성공 → 각 cause_var에 대해 grangercausalitytests
 │   │        ├─ p_value < 0.05 → CausalEdge(method='granger')
 │   │        └─ 유의하지 않은 변수 → Pearson 상관 보강
 │   │
 │   └─ 실패 (positive definite 에러 등)
 │       └─ _diagnose_collinearity() 진단
 │           ├─ 분해형 가능성 큼 → decomposition 라우팅
 │           └─ 비분해형 → Pearson 상관만 사용
 │
 ├─ deterministic_sources 별도 처리
 │   ├─ _decomposition_contribution_multiplicative() 시도
 │   └─ 실패 시 _decomposition_contribution_additive() 시도
 │
 └─ 결과가 비었으면 → 전체 cause_vars에 대해 분해형 최종 시도
```

#### _diagnose_collinearity() — 공선성/종속성 진단

| 진단 항목 | 조건 | 의미 |
|-----------|------|------|
| `near_constant_cols` | `var < 1e-10` | 거의 상수인 열 존재 |
| `high_corr_pairs` | `abs(corr) >= 0.999` | 거의 동일한 열 쌍 존재 |
| `multiplicative_fit_r2` | `>= 0.99` | `target ≈ product(causes)` 관계 성립 |
| `is_likely_deterministic` | 위 3개 중 하나라도 True | 분해형 라우팅 신호 |

곱셈 근사 검정: `log(target) ~ sum(log(causes))` OLS 피팅 후 R-squared 계산

#### _decomposition_contribution_multiplicative() — 곱셈 분해

```
log(target) = sum(log(source_i))
Δlog(target) = sum(Δlog(source_i))
기여도 = |Δlog(source_i)| / |Δlog(target)|
```

#### _decomposition_contribution_additive() — 덧셈 분해

```
target = sum(source_i)
Δtarget = sum(Δsource_i)
기여도 = |Δsource_i| / |Δtarget|
```

### 2.3 CausalEdge 출력 스키마

```python
@dataclass
class CausalEdge:
    source: str          # 원인 변수명
    target: str          # 결과 변수명
    method: str          # 'granger' | 'correlation' | 'var' | 'decomposition'
    strength: float      # 관계 강도 0~1
    p_value: float       # 통계적 유의성
    lag: int = 0         # 시차 (Granger에서만 >0)
    direction: str       # 'positive' | 'negative'
```

### 2.4 생성자 파라미터

```python
CausalAnalysisService(
    significance_level=0.05,  # Granger p-value 유의수준
    min_correlation=0.3,      # Pearson 최소 상관계수
    max_lag=2,                # VAR 최대 시차
)
```

### 2.5 입력 데이터 요구사항

- **최소 행 수**: `max_lag * 2 + 10` (기본값 max_lag=2이면 14행)
- **컬럼**: 숫자형만 사용 (`select_dtypes(include=[np.number])`)
- **NaN 처리**: `dropna()` (행 기준)
- **relation_hints**: `Dict[Tuple[str,str], str]` — `(source_node_id, target_node_id) -> "dynamic" | "deterministic"`

---

## 3. 아키텍처 결정

### 3.1 배치 위치: Vision 서비스

**결정: Vision 서비스 내에 배치한다.**

#### 근거

| 기준 | Vision | Synapse |
|------|--------|---------|
| **기존 인과 분석 코드** | `root_cause_engine.py`, `root_cause.py` API 7개 이미 존재 | 없음 |
| **scipy/numpy 의존성** | 이미 `requirements.txt`에 포함 | 없음 |
| **분석 엔진 패턴** | What-If 솔버, OLAP 피벗 엔진 등 계산 집약적 서비스가 모여 있음 | CRUD + 그래프 탐색 중심 |
| **데이터 흐름** | Vision이 Synapse에서 온톨로지 데이터를 가져와 분석 후 결과 반환 | Synapse는 저장소 역할 |
| **서비스 역할** | "분석/계산" | "저장/탐색" |

**데이터 흐름 아키텍처**:

```
[Canvas Frontend]
    │
    ├── POST /api/v3/cases/{case_id}/causal-analysis
    │       ↓
    │   [Vision Service]
    │       │
    │       ├── (1) Synapse API → 온톨로지 노드/관계 조회
    │       ├── (2) Weaver API → 시계열 데이터 조회 (SQL 실행)
    │       ├── (3) CausalAnalysisEngine.analyze() 실행
    │       ├── (4) 결과를 Vision 상태 저장소에 캐시
    │       └── (5) Synapse API → 인과 관계 엣지 저장 (weight/lag/confidence)
    │
    └── GET /api/v3/cases/{case_id}/causal-graph
            ↓
        [Vision Service] → 캐시된 결과 반환
```

### 3.2 모듈 구조

```
services/vision/app/
 ├── engines/
 │   └── causal_analysis_engine.py    # [신규] KAIR 엔진 이식 (핵심)
 ├── services/
 │   ├── root_cause_engine.py         # [수정] 하드코딩 → 실제 인과 엔진 호출
 │   ├── causal_data_fetcher.py       # [신규] Synapse/Weaver에서 데이터 수집
 │   └── vision_runtime.py            # [수정] 인과 분석 상태 관리 추가
 └── api/
     └── root_cause.py                # [수정] 인과 분석 전용 엔드포인트 추가
```

### 3.3 Neo4j 관계 속성 확장

현재 Synapse `OntologyService._normalize_relation()`은 관계를 `properties` dict에 임의 키-값으로 저장한다. 인과 분석 결과의 `weight`, `lag`, `confidence`는 이 `properties` dict 안에 저장하면 스키마 변경 없이 즉시 사용 가능하다.

```python
# 인과 분석 결과 저장 시 properties 예시
{
    "type": "CAUSES",
    "properties": {
        "weight": 0.85,           # 인과 강도
        "lag": 2,                 # 시차 (일)
        "confidence": 0.95,       # p-value 기반 신뢰도
        "method": "granger",      # 분석 방법
        "direction": "positive",  # 방향
        "analyzed_at": "2026-03-20T09:00:00Z",
        "engine_version": "1.0.0"
    }
}
```

**Neo4j 인덱스 추가** (Synapse `Neo4jBootstrap`):

```cypher
CREATE INDEX idx_rel_causes_weight IF NOT EXISTS
FOR ()-[r:CAUSES]-() ON (r.weight)
```

---

## 4. 구현 단계

### Step 1: 인과 분석 엔진 코어 이식

- **What**: KAIR `CausalAnalysisService`를 Axiom Vision에 이식
- **Where**: `services/vision/app/engines/causal_analysis_engine.py` (신규 생성)
- **Complexity**: High
- **Dependencies**: 없음 (독립 모듈)

#### 파일 구조

```python
# services/vision/app/engines/causal_analysis_engine.py

"""
인과 분석 엔진 (Hybrid Engine)
KAIR로부터 이식 — VAR/Granger + 분해형 하이브리드 인과 분석

관계 타입별 맞는 판정기를 붙이는 하이브리드 인과 분석:
- 동학(시차)형: VAR/Granger
- 분해(정의)형: 로그 분해/기여도 (decomposition)
- VAR 실패(positive definite 등) → 진단 후 분해형 라우팅 또는 전처리 재시도
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.vector_ar.var_model import VAR

warnings.filterwarnings("ignore", category=FutureWarning)
logger = logging.getLogger(__name__)

# 분해형 관계 타입 상수
DETERMINISTIC_RELATION_TYPES: frozenset[str] = frozenset({
    "FORMULA", "DERIVED_FROM", "AGGREGATES", "AGGREGATE", "COMPOSED_OF",
})


@dataclass(frozen=True)
class CausalEdge:
    """발견된 인과관계 엣지"""
    source: str           # 원인 변수 (node_id:field 또는 컬럼명)
    target: str           # 결과 변수
    method: str           # 'granger' | 'correlation' | 'decomposition'
    strength: float       # 관계 강도 (0~1)
    p_value: float        # 통계적 유의성
    lag: int = 0          # 시차 (Granger용)
    direction: str = "positive"  # 'positive' | 'negative'

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "method": self.method,
            "strength": round(self.strength, 4),
            "p_value": round(self.p_value, 6),
            "lag": self.lag,
            "direction": self.direction,
        }


def diagnose_collinearity(
    data: pd.DataFrame,
    target_var: str,
    cause_vars: list[str],
    near_constant_threshold: float = 1e-10,
    high_corr_threshold: float = 0.999,
) -> dict[str, Any]:
    """공선성/종속성 진단 — VAR 실패 시 분해형 라우팅 판단 근거"""
    # ... (KAIR 로직 그대로 이식)


def _decomposition_multiplicative(...) -> list[CausalEdge]: ...
def _decomposition_additive(...) -> list[CausalEdge]: ...


class CausalAnalysisEngine:
    """
    하이브리드 인과 분석 엔진.

    사용법:
        engine = CausalAnalysisEngine(significance_level=0.05, max_lag=2)
        edges = engine.analyze(data=df, target_var="kpi_oee")
        scores = engine.calculate_impact_scores(edges)
    """

    def __init__(
        self,
        significance_level: float = 0.05,
        min_correlation: float = 0.3,
        max_lag: int = 2,
    ) -> None: ...

    def analyze(
        self,
        data: pd.DataFrame,
        target_var: str,
        max_lag: int | None = None,
        relation_hints: dict[tuple[str, str], str] | None = None,
    ) -> list[CausalEdge]:
        """핵심 진입점 — 하이브리드 인과 분석 실행"""
        ...

    def fit_var_model(self, data: pd.DataFrame, max_lag: int | None = None) -> Any:
        """VAR 모델 단독 피팅"""
        ...

    def test_granger_causality(
        self, var_results: Any, cause_var: str, effect_var: str
    ) -> dict[str, Any]:
        """Granger 인과 검정 단독 실행"""
        ...

    def calculate_impact_scores(self, edges: list[CausalEdge]) -> dict[str, float]:
        """엣지 목록 → 변수별 영향도 점수 (0~1 정규화)"""
        ...
```

#### 이식 시 변경 사항 (KAIR 대비)

1. **`@dataclass` → `@dataclass(frozen=True)`**: 불변 객체로 변경 (스레드 안전)
2. **클래스명**: `CausalAnalysisService` → `CausalAnalysisEngine` (서비스가 아닌 엔진)
3. **메서드명**: `analyze_causality` → `analyze` (간결화)
4. **타입 힌트**: `Dict`, `List` → `dict`, `list` (Python 3.10+ 스타일)
5. **로거**: `logging` 유지 (Vision은 `structlog` 대신 `logging` 사용)
6. **헬퍼 함수**: 모듈 수준 → 모듈 수준 유지 (변경 없음)

#### 검증 방법

```bash
cd services/vision
python -c "
from app.engines.causal_analysis_engine import CausalAnalysisEngine, CausalEdge
import pandas as pd, numpy as np

np.random.seed(42)
n = 100
x = np.random.randn(n).cumsum()
y = 0.7 * np.roll(x, 2) + 0.3 * np.random.randn(n)
df = pd.DataFrame({'x': x, 'y': y})

engine = CausalAnalysisEngine()
edges = engine.analyze(df, target_var='y')
for e in edges:
    print(e.to_dict())
assert len(edges) > 0, '인과 엣지가 발견되어야 함'
print('OK: 엔진 코어 이식 검증 통과')
"
```

---

### Step 2: 데이터 수집기 구현

- **What**: Synapse/Weaver에서 시계열 데이터를 수집하여 DataFrame으로 변환
- **Where**: `services/vision/app/services/causal_data_fetcher.py` (신규 생성)
- **Complexity**: Medium
- **Dependencies**: Step 1

#### 파일 구조

```python
# services/vision/app/services/causal_data_fetcher.py

"""
인과 분석용 데이터 수집기.

역할:
1. Synapse → 온톨로지 노드/관계 조회 (case_id 기준)
2. Weaver → 바인딩된 데이터소스에서 시계열 데이터 조회
3. DataFrame 조립 + relation_hints 생성
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

# 서비스 URL (환경변수에서)
SYNAPSE_URL = "http://synapse:8002"  # docker-compose 기준
WEAVER_URL = "http://weaver:8001"    # docker-compose 기준


@dataclass
class CausalAnalysisInput:
    """인과 분석 엔진 입력 데이터 패키지"""
    data: pd.DataFrame                           # 시계열 데이터 (컬럼 = node_id:field)
    target_var: str                               # 타겟 변수명
    relation_hints: dict[tuple[str, str], str]    # (source, target) → "dynamic"|"deterministic"
    node_metadata: dict[str, dict[str, Any]]      # node_id → {name, layer, dataSource, ...}


class CausalDataFetcher:
    """Synapse/Weaver에서 인과 분석용 데이터를 수집"""

    def __init__(
        self,
        synapse_url: str = SYNAPSE_URL,
        weaver_url: str = WEAVER_URL,
        timeout: float = 30.0,
    ) -> None:
        self._synapse_url = synapse_url.rstrip("/")
        self._weaver_url = weaver_url.rstrip("/")
        self._timeout = timeout

    async def fetch(
        self,
        case_id: str,
        target_node_id: str,
        target_field: str,
        tenant_id: str,
        max_neighbors: int = 20,
    ) -> CausalAnalysisInput:
        """
        인과 분석에 필요한 데이터를 수집하여 CausalAnalysisInput으로 반환.

        흐름:
        1. Synapse에서 target 노드의 이웃 조회 (관계 포함)
        2. 각 노드의 dataSource 확인
        3. Weaver를 통해 각 dataSource에서 시계열 데이터 조회
        4. DataFrame 조립 + relation_hints 매핑
        """
        ...

    async def _get_ontology_neighbors(
        self, case_id: str, node_id: str, limit: int
    ) -> dict[str, Any]:
        """Synapse /api/v3/synapse/ontology/nodes/{node_id}/neighbors 호출"""
        ...

    async def _get_ontology_nodes(
        self, case_id: str
    ) -> list[dict[str, Any]]:
        """Synapse /api/v3/synapse/ontology/cases/{case_id}/ontology 호출"""
        ...

    async def _query_timeseries(
        self, datasource: str, table: str, columns: list[str],
        time_column: str, tenant_id: str,
    ) -> pd.DataFrame:
        """Weaver SQL 실행 API를 통해 시계열 데이터 조회"""
        ...

    @staticmethod
    def _build_relation_hints(
        relations: list[dict[str, Any]],
    ) -> dict[tuple[str, str], str]:
        """
        온톨로지 관계 타입을 relation_hints로 변환.
        FORMULA, DERIVED_FROM, AGGREGATES → "deterministic"
        그 외 → "dynamic"
        """
        from app.engines.causal_analysis_engine import DETERMINISTIC_RELATION_TYPES
        hints = {}
        for rel in relations:
            rel_type = (rel.get("type") or "").upper()
            source_id = rel.get("source_id") or rel.get("source")
            target_id = rel.get("target_id") or rel.get("target")
            if source_id and target_id:
                hint_type = "deterministic" if rel_type in DETERMINISTIC_RELATION_TYPES else "dynamic"
                hints[(source_id, target_id)] = hint_type
        return hints
```

#### 검증 방법

- 단위 테스트: `httpx.AsyncClient` 모킹으로 Synapse/Weaver 응답 시뮬레이션
- 통합 테스트: 데모 온톨로지 (`case_id=00000000-0000-4000-a000-000000000100`)에 대해 실행

---

### Step 3: Vision Runtime 통합

- **What**: `VisionRuntime`에 인과 분석 워크플로우 추가
- **Where**: `services/vision/app/services/vision_runtime.py` (수정)
- **Complexity**: Medium
- **Dependencies**: Step 1, Step 2

#### 변경 내용

```python
# vision_runtime.py에 추가할 내용

from app.engines.causal_analysis_engine import CausalAnalysisEngine, CausalEdge
from app.services.causal_data_fetcher import CausalDataFetcher

class VisionRuntime:
    def __init__(self, ...):
        # 기존 코드 유지
        ...
        # 인과 분석 엔진 + 데이터 수집기 초기화
        self.causal_engine = CausalAnalysisEngine(
            significance_level=float(os.getenv("CAUSAL_SIGNIFICANCE_LEVEL", "0.05")),
            min_correlation=float(os.getenv("CAUSAL_MIN_CORRELATION", "0.3")),
            max_lag=int(os.getenv("CAUSAL_MAX_LAG", "2")),
        )
        self.causal_fetcher = CausalDataFetcher(
            synapse_url=os.getenv("SYNAPSE_URL", "http://synapse:8002"),
            weaver_url=os.getenv("WEAVER_URL", "http://weaver:8001"),
        )
        self.causal_results_by_case: dict[str, dict[str, Any]] = loaded.get("causal_results_by_case", {})

    # ── 인과 분석 API ── #

    async def run_causal_analysis(
        self,
        case_id: str,
        target_node_id: str,
        target_field: str,
        tenant_id: str,
        requested_by: str,
        max_lag: int | None = None,
    ) -> dict[str, Any]:
        """
        인과 분석 실행 (비동기 + 캐싱).

        흐름:
        1. CausalDataFetcher로 데이터 수집
        2. CausalAnalysisEngine.analyze() 실행 (CPU 집약적 → asyncio.to_thread)
        3. 결과 캐싱 + Synapse에 인과 관계 엣지 저장
        """
        analysis_id = self._new_id("causal-")
        causal_state = {
            "analysis_id": analysis_id,
            "case_id": case_id,
            "target_node_id": target_node_id,
            "target_field": target_field,
            "status": "RUNNING",
            "started_at": _now(),
            "completed_at": None,
            "requested_by": requested_by,
            "edges": [],
            "impact_scores": {},
            "metadata": {},
        }
        self.causal_results_by_case.setdefault(case_id, {})[analysis_id] = causal_state
        # 실제 분석은 백그라운드 스레드에서 실행
        return causal_state

    def _execute_causal_analysis(
        self,
        case_id: str,
        analysis_id: str,
        causal_input: "CausalAnalysisInput",
        max_lag: int | None,
    ) -> None:
        """동기 실행 — asyncio.to_thread에서 호출"""
        engine = self.causal_engine
        edges = engine.analyze(
            data=causal_input.data,
            target_var=causal_input.target_var,
            max_lag=max_lag,
            relation_hints=causal_input.relation_hints,
        )
        impact_scores = engine.calculate_impact_scores(edges)
        # 결과 저장
        state = self.causal_results_by_case.get(case_id, {}).get(analysis_id)
        if state:
            state["status"] = "COMPLETED"
            state["completed_at"] = _now()
            state["edges"] = [e.to_dict() for e in edges]
            state["impact_scores"] = impact_scores

    def get_causal_analysis(self, case_id: str, analysis_id: str) -> dict[str, Any] | None:
        return self.causal_results_by_case.get(case_id, {}).get(analysis_id)

    def list_causal_analyses(self, case_id: str) -> list[dict[str, Any]]:
        return list(self.causal_results_by_case.get(case_id, {}).values())

    def get_latest_causal_edges(self, case_id: str) -> list[dict[str, Any]]:
        """최신 완료된 인과 분석의 엣지 목록 반환"""
        analyses = self.list_causal_analyses(case_id)
        completed = [a for a in analyses if a["status"] == "COMPLETED"]
        if not completed:
            return []
        latest = max(completed, key=lambda a: a.get("completed_at", ""))
        return latest.get("edges", [])
```

---

### Step 4: REST API 엔드포인트 추가

- **What**: 인과 분석 전용 엔드포인트 추가
- **Where**: `services/vision/app/api/causal.py` (신규 생성) + `services/vision/app/main.py` (수정)
- **Complexity**: Medium
- **Dependencies**: Step 3

#### 신규 파일: `services/vision/app/api/causal.py`

```python
# services/vision/app/api/causal.py

"""인과 분석 API 엔드포인트"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.services.vision_runtime import vision_runtime

router = APIRouter(
    prefix="/api/v3/cases/{case_id}/causal",
    tags=["Causal Analysis"],
)


async def get_current_user(
    authorization: str = Header("mock_token", alias="Authorization"),
) -> CurrentUser:
    return auth_service.verify_token(authorization)


# ── 요청/응답 스키마 ── #

class CausalAnalysisRequest(BaseModel):
    """인과 분석 실행 요청"""
    target_node_id: str = Field(..., min_length=1, description="타겟 노드 ID (예: 'kpi-oee')")
    target_field: str = Field(..., min_length=1, description="타겟 필드명 (예: 'value')")
    max_lag: int | None = Field(default=None, ge=1, le=10, description="VAR 최대 시차")
    significance_level: float | None = Field(default=None, ge=0.001, le=0.1)

class CausalAnalysisResponse(BaseModel):
    analysis_id: str
    case_id: str
    status: str
    estimated_duration_seconds: int = 30
    poll_url: str

class CausalEdgeResponse(BaseModel):
    source: str
    target: str
    method: str  # granger | correlation | decomposition
    strength: float
    p_value: float
    lag: int
    direction: str  # positive | negative

class CausalGraphResponse(BaseModel):
    case_id: str
    analysis_id: str
    edges: list[CausalEdgeResponse]
    impact_scores: dict[str, float]
    node_metadata: dict[str, Any]
    completed_at: str | None


# ── 엔드포인트 ── #

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def run_causal_analysis(
    case_id: str,
    payload: CausalAnalysisRequest,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """
    인과 분석 실행 (비동기).

    타겟 노드/필드에 대해 VAR + Granger + 분해형 하이브리드 인과 분석을 실행한다.
    202 반환 후 백그라운드에서 실행, poll_url로 상태 확인.
    """
    auth_service.requires_role(user, ["admin", "staff"])
    result = await vision_runtime.run_causal_analysis(
        case_id=case_id,
        target_node_id=payload.target_node_id,
        target_field=payload.target_field,
        tenant_id=str(user.tenant_id) if hasattr(user, "tenant_id") else "default",
        requested_by=str(user.user_id),
        max_lag=payload.max_lag,
    )
    return {
        "analysis_id": result["analysis_id"],
        "case_id": case_id,
        "status": result["status"],
        "estimated_duration_seconds": 30,
        "poll_url": f"/api/v3/cases/{case_id}/causal/{result['analysis_id']}/status",
    }


@router.get("/{analysis_id}/status")
async def get_causal_status(
    case_id: str,
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 분석 진행 상태 조회"""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    result = vision_runtime.get_causal_analysis(case_id, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="analysis not found")
    return {
        "analysis_id": analysis_id,
        "status": result["status"],
        "started_at": result.get("started_at"),
        "completed_at": result.get("completed_at"),
    }


@router.get("/{analysis_id}/edges")
async def get_causal_edges(
    case_id: str,
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 분석 결과 엣지 목록 조회"""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    result = vision_runtime.get_causal_analysis(case_id, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="analysis not found")
    if result["status"] != "COMPLETED":
        raise HTTPException(status_code=409, detail="analysis not completed")
    return {
        "case_id": case_id,
        "analysis_id": analysis_id,
        "edges": result["edges"],
        "impact_scores": result["impact_scores"],
        "total_edges": len(result["edges"]),
    }


@router.get("/{analysis_id}/graph")
async def get_causal_graph(
    case_id: str,
    analysis_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 그래프 시각화용 데이터 (노드 + 엣지 + 메타데이터)"""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    result = vision_runtime.get_causal_analysis(case_id, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="analysis not found")
    if result["status"] != "COMPLETED":
        raise HTTPException(status_code=409, detail="analysis not completed")
    return {
        "case_id": case_id,
        "analysis_id": analysis_id,
        "edges": result["edges"],
        "impact_scores": result["impact_scores"],
        "metadata": result.get("metadata", {}),
        "completed_at": result.get("completed_at"),
    }


@router.get("/latest")
async def get_latest_causal_analysis(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """최신 완료된 인과 분석 결과 조회"""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    analyses = vision_runtime.list_causal_analyses(case_id)
    completed = [a for a in analyses if a["status"] == "COMPLETED"]
    if not completed:
        raise HTTPException(status_code=404, detail="no completed analysis found")
    latest = max(completed, key=lambda a: a.get("completed_at", ""))
    return latest


@router.get("")
async def list_causal_analyses(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """인과 분석 이력 목록 조회"""
    auth_service.requires_role(user, ["admin", "staff", "viewer"])
    analyses = vision_runtime.list_causal_analyses(case_id)
    return {"data": analyses, "total": len(analyses)}
```

#### main.py 수정

```python
# services/vision/app/main.py 에 추가
from app.api.causal import router as causal_router
# ...
app.include_router(causal_router)
```

#### API 요약

| Method | 경로 | 설명 | 상태 코드 |
|--------|------|------|-----------|
| `POST` | `/api/v3/cases/{case_id}/causal` | 인과 분석 실행 | 202 |
| `GET` | `/api/v3/cases/{case_id}/causal/{id}/status` | 진행 상태 | 200 |
| `GET` | `/api/v3/cases/{case_id}/causal/{id}/edges` | 엣지 목록 | 200/409 |
| `GET` | `/api/v3/cases/{case_id}/causal/{id}/graph` | 그래프 데이터 | 200/409 |
| `GET` | `/api/v3/cases/{case_id}/causal/latest` | 최신 결과 | 200/404 |
| `GET` | `/api/v3/cases/{case_id}/causal` | 분석 이력 | 200 |

---

### Step 5: root_cause_engine.py 업그레이드

- **What**: 하드코딩된 FeatureSpec 엔진을 실제 인과 분석 엔진과 연결
- **Where**: `services/vision/app/services/root_cause_engine.py` (수정)
- **Complexity**: Medium
- **Dependencies**: Step 3

#### 변경 전략

**하위 호환성 유지**: 기존 `run_root_cause_engine()` 함수 시그니처는 유지하되, 내부에서 인과 분석 결과가 있으면 그것을 우선 사용한다.

```python
# root_cause_engine.py 수정 개요

def run_root_cause_engine(
    case_id: str,
    payload: dict[str, Any],
    causal_edges: list[dict[str, Any]] | None = None,  # 신규 파라미터
) -> dict[str, Any]:
    """
    근본원인 분석 엔진.

    causal_edges가 주어지면 실제 인과 분석 결과 기반으로 근본원인 산출.
    없으면 기존 FeatureSpec 기반 결정론적 엔진 사용 (하위 호환).
    """
    if causal_edges:
        return _root_cause_from_causal_edges(case_id, payload, causal_edges)
    # 기존 로직 (FEATURE_SPECS 기반)
    return _root_cause_legacy(case_id, payload)


def _root_cause_from_causal_edges(
    case_id: str,
    payload: dict[str, Any],
    causal_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    인과 분석 엣지 기반 근본원인 랭킹.

    각 엣지의 strength, p_value, method를 조합하여
    impact_score를 계산하고 순위를 매긴다.
    """
    max_root_causes = min(max(int(payload.get("max_root_causes", 5)), 1), 10)

    # 엣지별 impact 계산
    scored = []
    for edge in causal_edges:
        strength = float(edge.get("strength", 0.0))
        p_value = float(edge.get("p_value", 1.0))
        confidence = 1.0 - p_value
        impact = strength * confidence

        # method 가중치: granger > decomposition > correlation
        method_weight = {"granger": 1.2, "decomposition": 1.0, "correlation": 0.8}
        weight = method_weight.get(edge.get("method", ""), 0.8)

        scored.append({
            "variable": edge["source"],
            "variable_label": edge["source"],
            "shap_value": round(impact * weight, 4),
            "contribution_pct": 0.0,  # 아래에서 계산
            "actual_value": strength,
            "critical_threshold": None,
            "description": f"{edge['source']} → {edge['target']} ({edge.get('method', 'unknown')})",
            "causal_chain": [edge["source"], edge.get("method", ""), edge["target"]],
            "confidence": round(confidence, 3),
            "direction": edge.get("direction", "positive"),
            "lag": edge.get("lag", 0),
            "method": edge.get("method", "unknown"),
        })

    scored.sort(key=lambda x: x["shap_value"], reverse=True)
    selected = scored[:max_root_causes]

    # contribution_pct 계산
    total_shap = sum(item["shap_value"] for item in selected) or 1.0
    root_causes = []
    for rank, item in enumerate(selected, 1):
        item["rank"] = rank
        item["contribution_pct"] = round((item["shap_value"] / total_shap) * 100.0, 2)
        root_causes.append(item)

    return {
        "root_causes": root_causes,
        "overall_confidence": round(
            sum(item["confidence"] for item in root_causes) / max(len(root_causes), 1), 3
        ),
        "analysis_method": "causal_analysis_engine",
        "explanation": "VAR/Granger + 분해형 하이브리드 인과 분석 기반 근본원인 산출",
    }
```

---

### Step 6: Synapse 인과 관계 저장 연동

- **What**: 인과 분석 결과를 Synapse 온톨로지에 CAUSES 관계로 저장
- **Where**: `services/vision/app/services/causal_data_fetcher.py` (확장) + Synapse 관계 API 활용
- **Complexity**: Low
- **Dependencies**: Step 2, Step 4

```python
# causal_data_fetcher.py에 추가

async def save_causal_edges_to_synapse(
    self,
    case_id: str,
    edges: list[dict[str, Any]],
    tenant_id: str,
    analysis_id: str,
) -> int:
    """
    인과 분석 결과 엣지를 Synapse에 CAUSES 관계로 저장.

    기존 CAUSES 관계가 있으면 properties만 업데이트.
    """
    saved_count = 0
    async with httpx.AsyncClient(timeout=self._timeout) as client:
        for edge in edges:
            payload = {
                "case_id": case_id,
                "source_id": edge["source"],
                "target_id": edge["target"],
                "type": "CAUSES",
                "properties": {
                    "weight": edge["strength"],
                    "lag": edge["lag"],
                    "confidence": round(1.0 - edge["p_value"], 4),
                    "method": edge["method"],
                    "direction": edge["direction"],
                    "analysis_id": analysis_id,
                    "analyzed_at": _now(),
                    "engine_version": "1.0.0",
                },
            }
            try:
                resp = await client.post(
                    f"{self._synapse_url}/api/v3/synapse/ontology/relations",
                    json=payload,
                    headers={"X-Tenant-Id": tenant_id},
                )
                if resp.status_code in (200, 201):
                    saved_count += 1
            except Exception as e:
                logger.warning("인과 관계 저장 실패: %s → %s: %s", edge["source"], edge["target"], e)
    return saved_count
```

---

### Step 7: requirements.txt 업데이트

- **What**: 필요한 Python 패키지 추가
- **Where**: `services/vision/requirements.txt` (수정)
- **Complexity**: Low
- **Dependencies**: 없음

#### 추가할 패키지

```
# services/vision/requirements.txt 에 추가
pandas>=2.0,<3
statsmodels>=0.14,<1
```

**이미 존재하는 패키지** (변경 불필요):
- `numpy>=1.24,<3` -- 이미 존재
- `scipy>=1.10,<2` -- 이미 존재

**패키지 버전 근거**:
- `pandas>=2.0,<3`: Synapse에서 `pandas==2.2.1` 사용 중이므로 호환 범위 설정
- `statsmodels>=0.14,<1`: VAR + grangercausalitytests 필요. 0.14는 Python 3.10+ 지원

---

### Step 8: 테스트 작성

- **What**: 엔진 단위 테스트 + API 통합 테스트
- **Where**: `services/vision/tests/unit/test_causal_analysis_engine.py` (신규), `services/vision/tests/unit/test_causal_api.py` (신규)
- **Complexity**: Medium
- **Dependencies**: Step 1, Step 4

#### 테스트 파일 구조

```
services/vision/tests/unit/
 ├── test_causal_analysis_engine.py   # 엔진 단위 테스트
 ├── test_causal_data_fetcher.py      # 데이터 수집기 테스트
 └── test_causal_api.py               # API 통합 테스트
```

#### test_causal_analysis_engine.py 주요 테스트 시나리오

```python
"""인과 분석 엔진 단위 테스트"""

import numpy as np
import pandas as pd
import pytest

from app.engines.causal_analysis_engine import (
    CausalAnalysisEngine,
    CausalEdge,
    DETERMINISTIC_RELATION_TYPES,
    diagnose_collinearity,
)


class TestCausalAnalysisEngine:
    """CausalAnalysisEngine 테스트"""

    @pytest.fixture
    def engine(self):
        return CausalAnalysisEngine(significance_level=0.05, min_correlation=0.3, max_lag=2)

    @pytest.fixture
    def simple_causal_data(self):
        """명확한 인과 관계: x → y (lag=2)"""
        np.random.seed(42)
        n = 200
        x = np.random.randn(n).cumsum()
        y = np.zeros(n)
        for i in range(2, n):
            y[i] = 0.7 * x[i - 2] + 0.3 * np.random.randn()
        return pd.DataFrame({"x": x, "y": y})

    @pytest.fixture
    def multiplicative_data(self):
        """곱셈 분해 관계: target = a * b"""
        np.random.seed(42)
        n = 100
        a = np.random.uniform(1, 10, n)
        b = np.random.uniform(1, 5, n)
        target = a * b
        return pd.DataFrame({"a": a, "b": b, "target": target})

    @pytest.fixture
    def additive_data(self):
        """덧셈 분해 관계: target = a + b + c"""
        np.random.seed(42)
        n = 100
        a = np.random.uniform(10, 50, n)
        b = np.random.uniform(5, 30, n)
        c = np.random.uniform(1, 10, n)
        target = a + b + c
        return pd.DataFrame({"a": a, "b": b, "c": c, "target": target})

    def test_granger_causality_detection(self, engine, simple_causal_data):
        """Granger 인과 관계가 올바르게 감지되는지 검증"""
        edges = engine.analyze(simple_causal_data, target_var="y")
        assert len(edges) > 0
        granger_edges = [e for e in edges if e.method == "granger"]
        assert len(granger_edges) > 0
        assert granger_edges[0].source == "x"
        assert granger_edges[0].target == "y"
        assert granger_edges[0].lag > 0

    def test_multiplicative_decomposition(self, engine, multiplicative_data):
        """곱셈 분해 관계 탐지 검증"""
        hints = {("a", "target"): "deterministic", ("b", "target"): "deterministic"}
        edges = engine.analyze(
            multiplicative_data, target_var="target", relation_hints=hints
        )
        assert len(edges) >= 2
        decomp = [e for e in edges if e.method == "decomposition"]
        assert len(decomp) >= 2

    def test_additive_decomposition(self, engine, additive_data):
        """덧셈 분해 관계 탐지 검증"""
        hints = {
            ("a", "target"): "deterministic",
            ("b", "target"): "deterministic",
            ("c", "target"): "deterministic",
        }
        edges = engine.analyze(
            additive_data, target_var="target", relation_hints=hints
        )
        assert len(edges) >= 3

    def test_impact_scores(self, engine, simple_causal_data):
        """영향도 점수 정규화 검증"""
        edges = engine.analyze(simple_causal_data, target_var="y")
        scores = engine.calculate_impact_scores(edges)
        assert all(0.0 <= v <= 1.0 for v in scores.values())
        if scores:
            assert max(scores.values()) == 1.0  # 정규화 확인

    def test_insufficient_data(self, engine):
        """데이터 부족 시 경고 발생 검증"""
        df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
        with pytest.warns(UserWarning, match="데이터가 충분하지 않습니다"):
            edges = engine.analyze(df, target_var="y")

    def test_no_numeric_target(self, engine):
        """타겟 변수가 숫자형이 아닐 때 에러"""
        df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
        with pytest.raises(ValueError, match="타겟 변수"):
            engine.analyze(df, target_var="y")

    def test_var_failure_fallback(self, engine):
        """VAR 실패 시 상관/분해형 폴백 검증"""
        np.random.seed(42)
        n = 50
        x = np.random.randn(n)
        y = x + 1e-12 * np.random.randn(n)  # 거의 동일 → positive definite 실패
        df = pd.DataFrame({"x": x, "y": y})
        edges = engine.analyze(df, target_var="y")
        # VAR 실패해도 상관 또는 분해형으로 엣지가 나와야 함
        assert len(edges) > 0

    def test_edge_to_dict(self):
        """CausalEdge.to_dict() 직렬화 검증"""
        edge = CausalEdge(
            source="x", target="y", method="granger",
            strength=0.85, p_value=0.001, lag=2, direction="positive"
        )
        d = edge.to_dict()
        assert d["source"] == "x"
        assert d["strength"] == 0.85
        assert d["p_value"] == 0.001


class TestDiagnoseCollinearity:
    """공선성 진단 함수 테스트"""

    def test_near_constant_detection(self):
        df = pd.DataFrame({"target": [1.0, 1.0, 1.0, 1.0], "cause": [2, 3, 4, 5]})
        result = diagnose_collinearity(df, "target", ["cause"])
        assert "target" in result["near_constant_cols"]

    def test_high_correlation_detection(self):
        n = 100
        x = np.arange(n, dtype=float)
        df = pd.DataFrame({"target": x, "cause": x * 1.0000001})
        result = diagnose_collinearity(df, "target", ["cause"])
        assert len(result["high_corr_pairs"]) > 0

    def test_multiplicative_fit(self):
        np.random.seed(42)
        a = np.random.uniform(1, 10, 100)
        b = np.random.uniform(1, 5, 100)
        df = pd.DataFrame({"a": a, "b": b, "target": a * b})
        result = diagnose_collinearity(df, "target", ["a", "b"])
        assert result["multiplicative_fit_r2"] > 0.95
        assert result["is_likely_deterministic"] is True
```

---

## 5. 파일 변경 요약

### 신규 생성 파일

| 파일 경로 | 역할 | 예상 LOC |
|-----------|------|----------|
| `services/vision/app/engines/causal_analysis_engine.py` | 인과 분석 엔진 코어 | ~400 |
| `services/vision/app/services/causal_data_fetcher.py` | 데이터 수집기 | ~200 |
| `services/vision/app/api/causal.py` | REST API 엔드포인트 | ~180 |
| `services/vision/tests/unit/test_causal_analysis_engine.py` | 엔진 단위 테스트 | ~250 |
| `services/vision/tests/unit/test_causal_data_fetcher.py` | 수집기 테스트 | ~120 |
| `services/vision/tests/unit/test_causal_api.py` | API 통합 테스트 | ~150 |

### 수정 파일

| 파일 경로 | 변경 내용 |
|-----------|-----------|
| `services/vision/app/main.py` | `causal_router` import + `app.include_router(causal_router)` 추가 |
| `services/vision/app/services/vision_runtime.py` | `CausalAnalysisEngine`, `CausalDataFetcher` 초기화 + 인과 분석 메서드 5개 추가 |
| `services/vision/app/services/root_cause_engine.py` | `causal_edges` 파라미터 추가 + `_root_cause_from_causal_edges()` 함수 추가 (기존 함수 유지) |
| `services/vision/requirements.txt` | `pandas>=2.0,<3`, `statsmodels>=0.14,<1` 추가 |

---

## 6. 테스트 전략

### 6.1 단위 테스트 (Step 8에서 상세 설명)

| 테스트 범위 | 시나리오 | 우선순위 |
|------------|---------|---------|
| Granger 인과 감지 | 시차 있는 인과 관계 DataFrame 생성 → 엣지 감지 확인 | P0 |
| 곱셈 분해 | `target = a * b` 데이터 → decomposition 엣지 확인 | P0 |
| 덧셈 분해 | `target = a + b + c` 데이터 → decomposition 엣지 확인 | P0 |
| VAR 실패 폴백 | 공선성 높은 데이터 → 상관/분해형 폴백 | P0 |
| 공선성 진단 | 상수열, 고상관 쌍, 곱셈 근사 감지 | P1 |
| 영향도 점수 | 엣지 → 정규화된 점수 (0~1) | P1 |
| 데이터 부족 경고 | 14행 미만 DataFrame → UserWarning | P1 |
| 빈 결과 폴백 | Granger 유의하지 않을 때 → 분해형 최종 시도 | P1 |

### 6.2 통합 테스트 (시드 온톨로지 기반)

Synapse `main.py`에 이미 시드된 데모 온톨로지 사용:
- **case_id**: `00000000-0000-4000-a000-000000000100`
- **노드**: KPI 4개 (OEE, Throughput, Defect Rate, Downtime) + Measure 5개 + Process 5개 + Resource 5개
- **관계**: DERIVED_FROM (KPI←Measure), OBSERVED_IN (Measure←Process), USES (Process←Resource)

```python
# 통합 테스트 시나리오
async def test_causal_analysis_e2e():
    """
    1. POST /causal — 인과 분석 실행 (target: kpi-oee, field: value)
    2. GET /causal/{id}/status — RUNNING → COMPLETED 폴링
    3. GET /causal/{id}/edges — 엣지 목록 확인
       - msr-availability → kpi-oee (DERIVED_FROM → decomposition)
       - msr-performance → kpi-oee (DERIVED_FROM → decomposition)
       - msr-quality → kpi-oee (DERIVED_FROM → decomposition)
    4. GET /causal/{id}/graph — 그래프 데이터 확인
    5. Synapse /ontology/relations에 CAUSES 관계 저장 확인
    """
```

### 6.3 성능 테스트

| 시나리오 | 데이터 규모 | 목표 |
|---------|------------|------|
| 소규모 | 5 변수 x 100행 | < 2초 |
| 중규모 | 20 변수 x 1,000행 | < 10초 |
| 대규모 | 50 변수 x 10,000행 | < 30초 (타임아웃) |

---

## 7. 위험 요소

### 7.1 기술적 위험

| 위험 | 영향 | 확률 | 완화 전략 |
|------|------|------|-----------|
| **statsmodels 의존성 크기** | Docker 이미지 500MB+ 증가 가능 | 높음 | multi-stage build에서 `--no-cache-dir` + 불필요 모듈 제외. Alpine 대신 slim 이미지 사용 |
| **VAR positive definite 에러** | 공선성 높은 실제 데이터에서 빈번 발생 | 높음 | KAIR의 `_diagnose_collinearity()` 진단 + 분해형 폴백이 이미 대응. 추가로 데이터 전처리 (표준화) 적용 |
| **Weaver 시계열 쿼리 타임아웃** | 대규모 테이블 조회 시 30초 초과 | 중간 | `LIMIT` + `time_column` 기반 최근 N행만 조회. 타임아웃 설정 |
| **Synapse 온톨로지 메모리 캐시** | 노드/관계가 인메모리 dict에만 있음 (Neo4j 동기화 지연) | 낮음 | `_sync_relation_to_neo4j`가 이미 비동기 동기화 수행. 인과 관계 저장 시 Neo4j 직접 저장 확인 |
| **데이터 부족** | 시계열 14행 미만이면 VAR 불가 | 중간 | 경고 발생 + 상관/분해형만으로 분석 진행 (graceful degradation) |

### 7.2 이식 시 주의 사항

1. **KAIR `CausalAnalysisService` vs Axiom 명명 규칙**
   - KAIR: `CausalAnalysisService` (서비스)
   - Axiom Vision: `CausalAnalysisEngine` (엔진) — Vision은 `engines/` 디렉토리에 계산 로직을 배치하는 패턴을 따름 (`scenario_solver.py`, `pivot_engine.py`, `etl_pipeline.py`)

2. **`analyze_causality()` → `analyze()`**
   - KAIR에서는 `analyze_causality()`가 `analyze_causality_hybrid()`를 호출하는 래퍼였음
   - Axiom에서는 `analyze()` 하나로 통합 (불필요한 간접 호출 제거)

3. **동기 vs 비동기**
   - KAIR: 동기 함수 (`def analyze_causality()`)
   - Axiom: 엔진 자체는 동기 유지, `VisionRuntime`에서 `asyncio.to_thread()`로 감싸서 비동기 처리
   - 이유: `numpy/scipy/statsmodels`는 CPU 바운드이므로 async 의미 없음

4. **`relation_hints` 생성**
   - KAIR: 외부에서 직접 hints를 넘김
   - Axiom: `CausalDataFetcher._build_relation_hints()`가 Synapse 온톨로지 관계 타입으로부터 자동 생성

5. **에러 처리 강화**
   - KAIR: `except Exception: continue` 패턴 다수 → 조용한 실패
   - Axiom: 동일 패턴 유지하되, `logger.warning()`으로 모든 실패를 기록. 구조화된 로그 (`structlog` 대신 `logging` — Vision 패턴 따름)

6. **`_col_to_node_id()` 네이밍 컨벤션**
   - KAIR: `node_id:field` 형식 (콜론 구분)
   - Axiom: Synapse 노드 ID + properties 딕셔너리 기반이므로, `{node_id}:{field}` 형식을 컬럼명으로 사용하는 것이 자연스러움
   - `CausalDataFetcher`에서 DataFrame 컬럼명을 `{node_id}:{field}` 형식으로 생성

### 7.3 기존 기능 영향 분석

| 기존 기능 | 영향 | 조치 |
|-----------|------|------|
| `POST /root-cause-analysis` | 하위 호환 유지 | `causal_edges` 파라미터 optional, 없으면 기존 로직 |
| `GET /causal-graph` (기존) | 충돌 없음 | 기존은 `root_cause.py`의 `/causal-graph`, 신규는 `/causal/{id}/graph` |
| `root_cause_engine.run_root_cause_engine()` | 시그니처 확장 | optional 파라미터 추가, 기존 호출 코드 변경 불필요 |
| `vision_runtime.py` | 저장소 확장 | `causal_results_by_case` 딕셔너리 추가, 기존 필드 변경 없음 |
| What-If 시나리오 | 간접 이익 | 향후 시나리오 솔버에 인과 엣지 가중치 입력 가능 (이번 스코프 밖) |

---

## 8. 구현 순서 및 일정

| 순서 | Step | 예상 소요 | 병렬 가능 |
|:----:|:----:|:---------:|:---------:|
| 1 | Step 7: requirements.txt | 0.5시간 | - |
| 2 | Step 1: 엔진 코어 이식 | 1일 | - |
| 3 | Step 8a: 엔진 단위 테스트 | 0.5일 | Step 2와 병렬 가능 |
| 4 | Step 2: 데이터 수집기 | 1일 | - |
| 5 | Step 3: Vision Runtime 통합 | 0.5일 | - |
| 6 | Step 4: REST API | 0.5일 | - |
| 7 | Step 5: root_cause_engine 업그레이드 | 0.5일 | Step 6과 병렬 가능 |
| 8 | Step 6: Synapse 연동 | 0.5일 | Step 5와 병렬 가능 |
| 9 | Step 8b: 통합 테스트 | 1일 | - |
| 10 | 리뷰 + 버그 수정 | 1일 | - |
| **합계** | | **~6일** | |
