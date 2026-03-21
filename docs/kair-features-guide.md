# KAIR 이식 기능 사용자 가이드

> KAIR robo-data-domain-layer에서 Axiom으로 이식된 7개 기능의 사용 안내

<!-- affects: vision, synapse, oracle, weaver -->
<!-- requires-update: docs/02_api/, docs/service-endpoints-ssot.md -->

## 이 문서가 답하는 질문

- KAIR에서 이식된 기능은 무엇이고, 각각 어떤 서비스에 속하는가?
- 각 기능의 API는 어떻게 호출하는가?
- 제한 사항과 주의점은 무엇인가?

---

## 1. What-if 시뮬레이션 위자드 (Vision)

### 개요

변수 간 인과관계를 탐색하고, 특정 변수를 변경했을 때 다른 변수에 미치는 영향을 시뮬레이션한다. 9단계 파이프라인으로 구성되어 있으며, 각 단계는 독립적으로 호출할 수 있다.

### 9단계 파이프라인

| 단계 | API | 설명 |
|------|-----|------|
| 1 | `POST /api/v1/vision/whatif-wizard/discover-edges` | 변수 간 상관/인과 엣지 탐색 |
| 2 | `POST /api/v1/vision/whatif-wizard/correlation-matrix` | 상관 행렬 히트맵 생성 |
| 3 | `POST /api/v1/vision/whatif-wizard/build-graph` | 엣지에서 DAG 구축 (사이클 자동 제거) |
| 4 | `POST /api/v1/vision/whatif-wizard/train` | 노드별 회귀 모델 학습 |
| 5 | `POST /api/v1/vision/whatif-wizard/validate` | 모델 백테스팅 (RMSE/MAE) |
| 6 | `POST /api/v1/vision/whatif-wizard/simulate` | What-if DAG 전파 시뮬레이션 |
| 7 | `POST /api/v1/vision/whatif-wizard/compare` | 다중 시나리오 비교 분석 |
| 8 | `POST /api/v1/vision/whatif-wizard/scenarios` | 시나리오 저장 |
| 9 | `GET /api/v1/vision/whatif-wizard/scenarios` | 시나리오 목록/복원 |

### 사용 예시

**일반적인 흐름:**

1. 시계열 데이터를 준비한다 (변수명 -> 값 배열 형태)
2. `discover-edges`로 변수 간 관계를 탐색한다 (Pearson 상관 + Granger 인과)
3. `build-graph`로 DAG를 구축한다 (사이클 자동 제거)
4. `train`으로 각 노드의 회귀 모델을 학습한다
5. `simulate`에 개입(intervention) 값을 전달하여 전파 결과를 확인한다
6. 여러 시나리오를 `compare`로 비교한다

**discover-edges 요청 예시:**

```json
{
  "variables": {
    "temperature": [22.1, 23.5, 24.0, 25.2, 26.1],
    "humidity": [45.0, 47.2, 50.1, 52.3, 55.0],
    "defect_rate": [0.02, 0.03, 0.04, 0.05, 0.06]
  },
  "methods": ["pearson", "granger"],
  "threshold": 0.3,
  "max_lag": 3
}
```

**simulate 요청 예시:**

```json
{
  "graph": { "nodes": [...], "edges": [...] },
  "models": { "defect_rate": { "coefficients": {...} } },
  "interventions": {
    "temperature": 30.0
  }
}
```

### 제한 사항

- 최대 50개 변수, 변수당 최대 10,000개 데이터 포인트
- scikit-learn 미설치 시 학습(train)/검증(validate) 단계는 건너뜀
- DAG 구축 시 사이클이 발견되면 가장 약한 엣지부터 자동 제거

---

## 2. 비즈니스 캘린더 (Vision)

### 개요

시계열 데이터에서 공휴일과 주말을 제거하여 순수 영업일 데이터만 분석한다. 시계열 분석의 노이즈를 줄이는 데 필수적이다.

### API

| API | 설명 |
|-----|------|
| `POST /api/v1/vision/calendar/filter` | 시계열에서 비영업일 제거 |
| `POST /api/v1/vision/calendar/business-days` | 기간 내 영업일 목록 반환 |
| `POST /api/v1/vision/calendar/aggregate` | 비영업일 데이터를 인접 영업일로 집계 |
| `GET /api/v1/vision/calendar/is-business-day/{date}` | 특정 날짜 영업일 여부 확인 |

### 공휴일 데이터

| 소스 | 설명 |
|------|------|
| 기본 내장 | 대한민국 2024-2027 법정 공휴일 |
| DB 확장 | `vision.holidays` 테이블에서 동적 로드 |
| 사용자 정의 | `holidays` 파라미터로 커스텀 공휴일 전달 |

### 집계 방법

| 방법 | 설명 |
|------|------|
| mean | 비영업일 값의 평균을 다음 영업일에 합산 |
| sum | 비영업일 값의 합계를 다음 영업일에 합산 |
| last | 비영업일 마지막 값을 다음 영업일에 할당 |
| first | 비영업일 첫 값을 다음 영업일에 할당 |
| max | 비영업일 최대값을 다음 영업일에 할당 |
| min | 비영업일 최소값을 다음 영업일에 할당 |

### 사용 예시

```json
{
  "start_date": "2026-01-01",
  "end_date": "2026-01-31",
  "timeseries": {
    "2026-01-01": 100,
    "2026-01-02": 110,
    "2026-01-03": 95,
    "2026-01-04": 80,
    "2026-01-05": 120
  },
  "country": "KR",
  "aggregate_method": "mean"
}
```

---

## 3. DMN 규칙 엔진 (Synapse)

### 개요

비헤이비어 기반 의사결정 로직을 결정 테이블(Decision Table)로 정의하고 실행한다. 코드 배포 없이 비즈니스 규칙을 변경할 수 있다.

### API

| API | 설명 |
|-----|------|
| `POST /api/v3/synapse/dmn/execute` | 결정 테이블 실행 |

### 적중 정책 (Hit Policy)

| 정책 | 동작 |
|------|------|
| FIRST | 첫 번째 매칭 규칙만 반환 (순서 중요) |
| COLLECT | 모든 매칭 규칙을 배열로 수집 |
| PRIORITY | 우선순위 정렬 후 첫 번째 반환 |

### 조건 연산자

| 연산자 | 예시 | 설명 |
|--------|------|------|
| `==` | `== "VIP"` | 동등 비교 |
| `!=` | `!= "Normal"` | 부등 비교 |
| `>` | `> 100` | 초과 |
| `>=` | `>= 1000000` | 이상 |
| `<` | `< 50` | 미만 |
| `<=` | `<= 99` | 이하 |
| `in [...]` | `in ["A", "B"]` | 포함 |
| `not in [...]` | `not in ["C"]` | 미포함 |
| `-` | `-` | 와일드카드 (모든 값 매칭) |

### 사용 예시

```json
{
  "table": {
    "name": "고객등급판정",
    "hit_policy": "FIRST",
    "inputs": [
      {"name": "purchase_amount", "type": "number"}
    ],
    "outputs": [
      {"name": "grade", "type": "string"},
      {"name": "discount_rate", "type": "number"}
    ],
    "rules": [
      {
        "conditions": {"purchase_amount": ">= 1000000"},
        "outputs": {"grade": "VIP", "discount_rate": 0.15}
      },
      {
        "conditions": {"purchase_amount": ">= 500000"},
        "outputs": {"grade": "Gold", "discount_rate": 0.10}
      },
      {
        "conditions": {"purchase_amount": ">= 100000"},
        "outputs": {"grade": "Silver", "discount_rate": 0.05}
      },
      {
        "conditions": {"purchase_amount": "-"},
        "outputs": {"grade": "Normal", "discount_rate": 0}
      }
    ]
  },
  "context": {"purchase_amount": 750000}
}
```

**응답:**

```json
{
  "results": [
    {"grade": "Gold", "discount_rate": 0.10}
  ],
  "matched_count": 1,
  "hit_policy": "FIRST"
}
```

### 금지 사항

- `eval()` 함수는 절대 사용하지 않는다 (보안). 내부적으로 `ast.literal_eval`만 허용한다.
- 조건 표현식에 임의 Python 코드를 삽입할 수 없다.

---

## 4. 관계 추론 엔진 (Synapse)

### 개요

온톨로지 엔티티 간의 의미적 관계를 자동으로 발견한다. LLM 기반 추론과 규칙 기반 폴백 두 가지 전략을 사용한다.

### API

| API | 설명 |
|-----|------|
| `POST /api/v3/synapse/dmn/infer-relation` | 2개 엔티티 간 관계 추론 |
| `POST /api/v3/synapse/dmn/infer-relations-batch` | 엔티티 목록 일괄 추론 (최대 20개) |

### 추론 방식

**1단계 -- LLM 기반 (OpenAI API 키 존재 시)**

- 두 엔티티의 이름, 설명, 레이어 정보를 LLM에 전달
- 자연어 이해 기반으로 관계 타입, 방향, 신뢰도를 판단
- 레이트 리밋: 15회/분

**2단계 -- 규칙 기반 폴백 (API 키 부재 시)**

| 소스 레이어 | 타겟 레이어 | 추론 관계 |
|-------------|-------------|-----------|
| KPI | Measure | DERIVED_FROM |
| Measure | Process | OBSERVED_IN |
| Process | Resource | USES |
| Resource | Process | SUPPORTS |
| Driver | KPI | INFLUENCES |
| Driver | Measure | CAUSES |

### 사용 예시

```json
{
  "source": {
    "name": "OEE",
    "layer": "KPI",
    "description": "Overall Equipment Effectiveness"
  },
  "target": {
    "name": "Availability",
    "layer": "Measure",
    "description": "Equipment uptime ratio"
  }
}
```

**응답:**

```json
{
  "relation_type": "DERIVED_FROM",
  "confidence": 0.92,
  "method": "llm",
  "direction": "source_to_target",
  "reasoning": "OEE is calculated from Availability, Performance, and Quality metrics"
}
```

---

## 5. LLM 시맨틱 캐시 (Oracle)

### 개요

동일하거나 유사한 LLM 프롬프트의 응답을 캐싱하여 API 호출 비용과 응답 지연을 줄인다.

### 2단계 캐싱 전략

```
[새 프롬프트 입력]
    |
    v
[Phase 1] SHA-256 해시 비교 ── 정확 매칭
    |                            |
    | miss                       | hit -> 즉시 반환 (< 1ms)
    v
[Phase 2] 코사인 유사도 비교 ── 시맨틱 매칭
    |                            |
    | 유사도 < 0.92              | 유사도 >= 0.92 -> 캐시 반환
    v
[LLM API 호출] -> 응답 저장 후 반환
```

### API

| API | 설명 |
|-----|------|
| `GET /api/v2/oracle/cache/metrics` | 캐시 적중률 통계 (hit_count, miss_count, hit_rate) |

### 테넌트 격리

- Redis 키 형식: `axiom:{tenant_id}:semantic_cache:{hash}`
- 교차 테넌트 캐시 공유는 불가능하다
- 각 테넌트별 독립적인 캐시 공간을 사용한다

### 결정 사항

- 유사도 임계값을 0.92로 설정한 이유: 0.90 미만에서는 의미가 달라지는 쿼리가 매칭되는 사례가 발견됨. 0.95 이상에서는 캐시 적중률이 지나치게 낮음.

---

## 6. 자동 데이터소스 바인딩 (Weaver)

### 개요

온톨로지 엔티티를 실제 DB 테이블/컬럼에 자동으로 매핑한다. 수작업 매핑의 부담을 줄이고, 시맨틱 레이어와 물리 데이터의 연결을 자동화한다.

### API

| API | 설명 |
|-----|------|
| `POST /api/v2/weaver/auto-binding/bind` | 자동 바인딩 실행 |

### 2단계 매칭 전략

**Phase 1 -- 이름 기반 매칭 (LLM 호출 없음)**

| 매칭 방법 | 점수 | 예시 |
|-----------|------|------|
| 정확 매칭 | 1.0 | `temperature` == `temperature` |
| 부분 매칭 | 0.7 | `avg_temperature` contains `temperature` |
| 한영 변환 | 0.6 | `수온` -> `temperature` (사전 기반) |
| 컬럼 매칭 | 0.5 | 테이블 내 컬럼명 부분 일치 |

**Phase 2 -- LLM 시맨틱 매칭 (Phase 1에서 unbound인 것만)**

- OpenAI에 엔티티 설명 + 후보 컬럼 목록 전달
- 시맨틱 유사도 기반 매칭 (0.0~1.0 점수)

### 한국어-영어 도메인 용어 매핑 (내장 사전)

| 한국어 | 영어 |
|--------|------|
| 탁도 | turbidity |
| 잔류염소 | chlorine |
| 수온 | temperature |
| 유량 | flow_rate |
| 수압 | pressure |
| pH | ph |
| 전도도 | conductivity |
| 용존산소 | dissolved_oxygen |

### 바인딩 상태

| 상태 | 점수 범위 | 의미 |
|------|-----------|------|
| bound | 0.7 이상 | 자동 매칭 성공, 바로 사용 가능 |
| partial | 0.3 ~ 0.7 | 매칭 후보 존재, 사용자 확인 권장 |
| unbound | 0.3 미만 | 매칭 실패, 수동 매핑 필요 |

### 사용 예시

```json
{
  "entities": [
    {"name": "수온", "layer": "Measure", "description": "원수 수온"},
    {"name": "탁도", "layer": "Measure", "description": "정수 탁도"},
    {"name": "OEE", "layer": "KPI", "description": "설비종합효율"}
  ],
  "datasource_id": "ds-001",
  "use_llm": true
}
```

**응답:**

```json
{
  "bindings": [
    {
      "entity": "수온",
      "status": "bound",
      "score": 0.95,
      "table": "sensor_readings",
      "column": "temperature",
      "method": "korean_english_dict"
    },
    {
      "entity": "탁도",
      "status": "bound",
      "score": 0.90,
      "table": "water_quality",
      "column": "turbidity",
      "method": "korean_english_dict"
    },
    {
      "entity": "OEE",
      "status": "partial",
      "score": 0.55,
      "table": "production_metrics",
      "column": "overall_efficiency",
      "method": "llm_semantic"
    }
  ],
  "summary": {
    "total": 3,
    "bound": 2,
    "partial": 1,
    "unbound": 0
  }
}
```

---

## 7. 시나리오 저장/비교 (Vision)

### 개요

What-if 시뮬레이션 결과를 저장하고, 여러 시나리오를 비교 분석한다. Redis 기반으로 30일 TTL이 적용된다.

### API

| API | 설명 |
|-----|------|
| `POST /scenarios` | 시나리오 저장 (30일 TTL) |
| `GET /scenarios` | 시나리오 목록 조회 |
| `GET /scenarios/{id}` | 시나리오 상세 조회 |
| `DELETE /scenarios/{id}` | 시나리오 삭제 |

### 비교 분석

`POST /api/v1/vision/whatif-wizard/compare` API에 2개 이상의 시나리오를 전달하면:

- 변수별 `delta` (절대 차이)와 `delta_pct` (백분율 차이) 계산
- 최대 영향 변수 자동 식별
- 시나리오 간 순위 정렬

### 사용 예시

**시나리오 저장:**

```json
{
  "name": "온도 30도 시나리오",
  "description": "공장 온도를 30도로 올렸을 때 불량률 변화",
  "interventions": {"temperature": 30.0},
  "results": {
    "defect_rate": 0.08,
    "humidity": 58.2
  },
  "graph_id": "graph-abc-123"
}
```

**시나리오 비교:**

```json
{
  "scenarios": [
    {
      "name": "기본",
      "results": {"defect_rate": 0.03, "output": 1000}
    },
    {
      "name": "온도 30도",
      "results": {"defect_rate": 0.08, "output": 920}
    },
    {
      "name": "온도 35도",
      "results": {"defect_rate": 0.15, "output": 850}
    }
  ]
}
```

**비교 응답:**

```json
{
  "comparison": [
    {
      "variable": "defect_rate",
      "baseline": 0.03,
      "scenarios": [
        {"name": "온도 30도", "value": 0.08, "delta": 0.05, "delta_pct": 166.7},
        {"name": "온도 35도", "value": 0.15, "delta": 0.12, "delta_pct": 400.0}
      ]
    },
    {
      "variable": "output",
      "baseline": 1000,
      "scenarios": [
        {"name": "온도 30도", "value": 920, "delta": -80, "delta_pct": -8.0},
        {"name": "온도 35도", "value": 850, "delta": -150, "delta_pct": -15.0}
      ]
    }
  ],
  "most_impacted_variable": "defect_rate",
  "max_delta_pct": 400.0
}
```

### 제한 사항

- 시나리오 TTL: 30일 (Redis EXPIRE)
- 테넌트별 격리: Redis 키에 tenant_id 포함
- 비교 시 최소 2개, 최대 10개 시나리오

---

## 기능별 서비스 매핑 요약

| 기능 | 서비스 | 주요 API 접두사 |
|------|--------|----------------|
| What-if 시뮬레이션 위자드 | Vision (:9100) | `/whatif-wizard/` |
| 비즈니스 캘린더 | Vision (:9100) | `/calendar/` |
| DMN 규칙 엔진 | Synapse (:9003) | `/dmn/` |
| 관계 추론 엔진 | Synapse (:9003) | `/dmn/` |
| LLM 시맨틱 캐시 | Oracle (:9004) | `/cache/` |
| 자동 데이터소스 바인딩 | Weaver (:9001) | `/auto-binding/` |
| 시나리오 저장/비교 | Vision (:9100) | `/scenarios/` |

---

## 재평가 조건

이 문서는 다음 상황에서 업데이트가 필요하다:

- KAIR에서 추가 기능이 이식될 때
- 기존 기능의 API 스펙이 변경될 때
- 새로운 적중 정책이나 매칭 전략이 추가될 때
- 캐시 임계값이나 TTL 값이 변경될 때

<!-- 마지막 업데이트: 2026-03-22 -->
<!-- 근거: KAIR robo-data-domain-layer 이식 코드 + Vision/Synapse/Oracle/Weaver 서비스 코드 검증 -->
