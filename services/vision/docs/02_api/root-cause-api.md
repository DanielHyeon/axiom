# 근본원인 분석 API (Phase 4)

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **Phase**: 4 (출시 후)
> **근거**: 01_architecture/root-cause-engine.md, ADR-004

---

## 이 문서가 답하는 질문

- 근본원인 분석을 요청하는 API는?
- 분석 결과(근본원인, 인과 타임라인)를 조회하는 방법은?
- 반사실 시나리오를 실행하는 API는?
- 민감도 분석(어떤 원인이 가장 영향이 큰가)을 조회하는 방법은?
- 프로세스 병목의 근본원인을 분석하는 API는?

---

## 기본 정보

| 항목 | 값 |
|------|-----|
| **Base URL** | `/api/v3/cases/{case_id}` |
| **인증** | Bearer JWT |
| **권한** | VIEWER 이상 (분석 조회), TRUSTEE 이상 (분석 실행) |
| **비동기 처리** | 분석 실행은 비동기 (1~2분 소요) |

### 외부 의존성

§8 프로세스 병목 근본원인 분석은 Synapse 프로세스 마이닝 서비스에 의존한다.

| Synapse 엔드포인트 | 용도 | 호출 시점 |
|-------------------|------|----------|
| `GET /api/v3/synapse/process-mining/bottlenecks` | 병목 탐지 결과 조회 | process-bottleneck 요청 시 |
| `GET /api/v3/synapse/process-mining/variants` | 프로세스 변형 데이터 조회 | 인과 변수 구성 시 |
| `POST /api/v3/synapse/process-mining/performance` | 시간축 성능 분석 데이터 | 병목 시계열 분석 시 |

- **Synapse 불가 시**: 502 `SYNAPSE_UNAVAILABLE` 반환. 프로세스 병목 외 재무 근본원인 분석(§1~§7)은 Synapse 독립적으로 정상 동작한다.
- **API 스펙**: Synapse [process-mining-api.md](../../../synapse/docs/02_api/process-mining-api.md) 참조.

---

## 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| POST | `/root-cause-analysis` | 근본원인 분석 실행 (비동기) |
| GET | `/root-cause-analysis/status` | 분석 상태 조회 |
| GET | `/root-causes` | 근본원인 목록 조회 |
| GET | `/causal-timeline` | 인과 타임라인 조회 |
| POST | `/counterfactual` | 반사실 시나리오 실행 |
| GET | `/root-cause-impact` | 요인 영향도 (SHAP) 조회 |
| GET | `/causal-graph` | 인과 그래프 조회 |
| GET | `/root-cause/process-bottleneck` | 프로세스 병목 근본원인 분석 |

---

## 1. 근본원인 분석 실행

### POST `/api/v3/cases/{case_id}/root-cause-analysis`

비동기로 근본원인 분석을 실행한다. 인과 그래프 모델 기반 역추적 + SHAP 계산 + LLM 설명 생성을 수행한다.

#### Request

```json
{
  "analysis_depth": "full",
  "max_root_causes": 5,
  "include_counterfactuals": true,
  "include_explanation": true,
  "language": "ko"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `analysis_depth` | enum | N | `quick` (역추적만), `full` (SHAP + 반사실 포함) 기본 full |
| `max_root_causes` | integer | N | 반환할 최대 근본원인 수 (기본 5, 최대 10) |
| `include_counterfactuals` | boolean | N | 반사실 분석 포함 여부 (기본 true) |
| `include_explanation` | boolean | N | LLM 설명문 생성 여부 (기본 true) |
| `language` | string | N | 설명문 언어 (ko, en) 기본 ko |

#### Response (202 Accepted)

```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440030",
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ANALYZING",
  "estimated_duration_seconds": 90,
  "poll_url": "/api/v3/cases/{case_id}/root-cause-analysis/status"
}
```

---

## 2. 분석 상태 조회

### GET `/api/v3/cases/{case_id}/root-cause-analysis/status`

#### Response (200 OK)

```json
{
  "analysis_id": "550e8400-e29b-41d4-a716-446655440030",
  "status": "ANALYZING",
  "progress": {
    "step": "computing_shap_values",
    "step_label": "요인 기여도 계산 중",
    "pct": 65
  },
  "started_at": "2026-02-19T11:00:00Z",
  "elapsed_seconds": 58
}
```

가능한 status: `PENDING`, `ANALYZING`, `COMPLETED`, `FAILED`

진행 단계:
1. `loading_data` - 사건 데이터 로드
2. `loading_causal_graph` - 인과 그래프 로드
3. `backward_traversal` - 역추적 수행
4. `computing_shap_values` - SHAP 값 계산
5. `counterfactual_analysis` - 반사실 분석
6. `generating_explanation` - LLM 설명 생성

---

## 3. 근본원인 목록 조회

### GET `/api/v3/cases/{case_id}/root-causes`

분석 완료 후 근본원인 목록을 조회한다.

#### Response (200 OK)

```json
{
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "analysis_id": "550e8400-e29b-41d4-a716-446655440030",
  "analyzed_at": "2026-02-19T11:01:30Z",
  "causal_graph_version": "v2.1",
  "overall_confidence": 0.82,
  "root_causes": [
    {
      "rank": 1,
      "variable": "debt_ratio",
      "variable_label": "부채비율",
      "shap_value": 0.35,
      "contribution_pct": 35.0,
      "actual_value": 1.50,
      "critical_threshold": 1.00,
      "description": "부채비율 150%로 업종 평균 80% 대비 과도",
      "causal_chain": [
        "2022년 M&A 인수자금 차입 500억원",
        "부채비율 80% → 150% 급등",
        "이자비용 연 50억원 증가",
        "현금흐름 악화"
      ],
      "confidence": 0.89
    },
    {
      "rank": 2,
      "variable": "ebitda",
      "variable_label": "EBITDA",
      "shap_value": 0.28,
      "contribution_pct": 28.0,
      "actual_value": 600000000,
      "critical_threshold": 1500000000,
      "description": "EBITDA 6억원으로 이자비용 대비 부족",
      "causal_chain": [
        "공급망 교란으로 원가 상승",
        "매출 성장률 -5% (업종 평균 +3%)",
        "EBITDA 마진 2% (업종 평균 8%)"
      ],
      "confidence": 0.85
    },
    {
      "rank": 3,
      "variable": "interest_rate_env",
      "variable_label": "금리 환경",
      "shap_value": 0.18,
      "contribution_pct": 18.0,
      "actual_value": 5.5,
      "critical_threshold": null,
      "description": "기준금리 3.5% → 5.5% 상승으로 이자부담 가중",
      "causal_chain": [
        "2023년 기준금리 인상",
        "변동금리 차입금 이자비용 40% 증가"
      ],
      "confidence": 0.78
    }
  ],
  "explanation": "ABC 주식회사의 비즈니스 실패는 2022년 M&A 인수자금 차입으로 인한 과도한 부채비율(150%)이 가장 주된 원인입니다(기여도 35%). 이에 더하여 공급망 교란으로 인한 EBITDA 하락(기여도 28%)과 2023년 금리 인상(기여도 18%)이 복합적으로 작용하여, 2024년 1분기 현금 고갈에 이르렀습니다. 반사실 분석 결과, 부채비율이 100% 이하로 유지되었다면 실패 확률이 42% 감소했을 것으로 추정됩니다."
}
```

---

## 4. 인과 타임라인

### GET `/api/v3/cases/{case_id}/causal-timeline`

시간 순서대로 인과 관계 이벤트를 조회한다.

#### Response (200 OK)

```json
{
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "timeline": [
    {
      "date": "2022-06-15",
      "event": "M&A 인수자금 차입",
      "variable": "debt_ratio",
      "value_before": 0.80,
      "value_after": 1.50,
      "impact": "critical",
      "description": "500억원 차입으로 부채비율 급등"
    },
    {
      "date": "2023-01-25",
      "event": "기준금리 인상",
      "variable": "interest_rate_env",
      "value_before": 3.50,
      "value_after": 5.50,
      "impact": "high",
      "description": "이자비용 40% 증가"
    },
    {
      "date": "2023-09-01",
      "event": "공급망 교란",
      "variable": "ebitda",
      "value_before": 1500000000,
      "value_after": 600000000,
      "impact": "critical",
      "description": "원가 상승으로 EBITDA 60% 감소"
    },
    {
      "date": "2024-01-15",
      "event": "현금 고갈",
      "variable": "cash_balance",
      "value_before": 200000000,
      "value_after": -50000000,
      "impact": "terminal",
      "description": "운영자금 부족, 비즈니스 지속 불가 상태 진입"
    }
  ]
}
```

---

## 5. 반사실 시나리오

### POST `/api/v3/cases/{case_id}/counterfactual`

#### Request

```json
{
  "variable": "debt_ratio",
  "actual_value": 1.50,
  "counterfactual_value": 0.80,
  "question": "부채비율이 80%였다면 실패를 피할 수 있었는가?"
}
```

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|:----:|:--------:|------|
| `variable` | string | Y | N | 변경할 변수명 |
| `actual_value` | decimal | Y | N | 실제 값 |
| `counterfactual_value` | decimal | Y | N | 반사실 값 |
| `question` | string | N | Y | 자연어 질문 (LLM 설명 생성에 활용) |

#### Response (200 OK)

```json
{
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "variable": "debt_ratio",
  "actual_value": 1.50,
  "counterfactual_value": 0.80,
  "actual_outcome": "실패 (확률 95%)",
  "counterfactual_outcome": "실패 회피 가능 (확률 53%)",
  "probability_change": -0.42,
  "probability_change_label": "실패 확률 42% 감소",
  "explanation": "부채비율이 150%가 아닌 80%였다면, 연간 이자비용이 약 25억원 감소하여 현금흐름이 양(+)으로 유지되었을 가능성이 높습니다. 다만, EBITDA 하락이 동시에 발생했으므로 실패 회피는 확정적이지 않으며, 추가적인 비용 절감이 필요했을 것입니다.",
  "confidence": 0.78,
  "caveats": [
    "반사실 분석은 다른 변수가 동일하다는 가정 하에 수행됨",
    "실제로는 부채비율 변화가 다른 변수에도 영향을 미칠 수 있음"
  ]
}
```

---

## 6. 요인 영향도 (SHAP) 조회

### GET `/api/v3/cases/{case_id}/root-cause-impact`

#### Response (200 OK)

```json
{
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "base_value": 0.50,
  "base_label": "평균 실패 확률 50%",
  "predicted_value": 0.95,
  "predicted_label": "이 사건 실패 확률 95%",
  "contributions": [
    {
      "variable": "debt_ratio",
      "label": "부채비율",
      "shap_value": 0.18,
      "feature_value": 1.50,
      "direction": "positive",
      "description": "실패 확률을 18%p 증가시킴"
    },
    {
      "variable": "ebitda",
      "label": "EBITDA",
      "shap_value": 0.14,
      "feature_value": 600000000,
      "direction": "positive",
      "description": "실패 확률을 14%p 증가시킴"
    },
    {
      "variable": "interest_rate_env",
      "label": "금리 환경",
      "shap_value": 0.08,
      "feature_value": 5.5,
      "direction": "positive",
      "description": "실패 확률을 8%p 증가시킴"
    }
  ],
  "visualization_data": {
    "force_plot": { },
    "summary_plot": { }
  }
}
```

---

## 7. 인과 그래프 조회

### GET `/api/v3/cases/{case_id}/causal-graph`

프론트엔드 React Flow 시각화를 위한 인과 그래프 데이터.

#### Response (200 OK)

```json
{
  "graph_version": "v2.1",
  "training_samples": 127,
  "nodes": [
    {
      "id": "debt_ratio",
      "label": "부채비율",
      "type": "intermediate",
      "value": 1.50,
      "position": {"x": 200, "y": 100}
    },
    {
      "id": "business_failure",
      "label": "비즈니스 실패",
      "type": "outcome",
      "value": 1,
      "position": {"x": 400, "y": 200}
    }
  ],
  "edges": [
    {
      "source": "debt_ratio",
      "target": "interest_expense",
      "coefficient": 0.72,
      "confidence": 0.89,
      "label": "72% 영향"
    },
    {
      "source": "interest_expense",
      "target": "cash_balance",
      "coefficient": -0.65,
      "confidence": 0.85,
      "label": "-65% 영향"
    }
  ]
}
```

---

## 8. 프로세스 병목 근본원인 분석

### GET `/api/v3/cases/{case_id}/root-cause/process-bottleneck`

Synapse 프로세스 마이닝 병목 데이터를 기반으로 프로세스 병목의 근본원인을 인과 분석한다. Synapse에서 병목 탐지 결과와 프로세스 변형 데이터를 수신하여 DoWhy 인과 그래프로 분석한다.

#### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|:----:|------|
| `process_id` | UUID | Y | Synapse 프로세스 모델 ID |
| `bottleneck_activity` | string | N | 특정 병목 활동 지정. 없으면 Synapse에서 자동 탐지된 최고 병목 사용 |
| `max_causes` | integer | N | 반환할 최대 근본원인 수 (기본 5, 최대 10) |
| `include_explanation` | boolean | N | LLM 설명문 포함 여부 (기본 true) |

#### Request 예시

```
GET /api/v3/cases/{case_id}/root-cause/process-bottleneck?process_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

특정 활동 지정:
```
GET /api/v3/cases/{case_id}/root-cause/process-bottleneck?process_id=a1b2c3d4-...&bottleneck_activity=재고확인
```

#### Response (200 OK)

```json
{
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "process_model_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "bottleneck_activity": "재고확인",
  "bottleneck_score": 0.87,
  "analyzed_at": "2026-02-20T10:30:00Z",
  "data_range": {
    "from": "2025-12-01T00:00:00Z",
    "to": "2026-02-20T00:00:00Z",
    "case_count": 1247
  },
  "overall_confidence": 0.82,
  "root_causes": [
    {
      "rank": 1,
      "variable": "queue_wait_time",
      "variable_label": "승인 대기열 대기시간",
      "related_activity": "승인",
      "shap_value": 0.42,
      "contribution_pct": 42.0,
      "actual_value": "평균 4.2시간",
      "normal_range": "1~2시간",
      "description": "승인 단계 대기시간이 평균 4.2시간으로, 정상 범위(1~2시간)의 2배 이상이며 전체 병목의 42% 기여",
      "causal_chain": [
        "승인 담당자 2명→1명 감소 (2025-12-15)",
        "승인 대기열 대기시간 2.1배 증가",
        "후속 재고확인 시작 평균 4시간 지연",
        "전체 주기시간 35% 증가"
      ],
      "confidence": 0.88
    },
    {
      "rank": 2,
      "variable": "rework_rate",
      "variable_label": "검수 재작업 비율",
      "related_activity": "검수",
      "shap_value": 0.28,
      "contribution_pct": 28.0,
      "actual_value": "15%",
      "normal_range": "3~5%",
      "description": "검수 단계 재작업 비율 15%로 정상 범위(3~5%)의 3배, 추가 처리시간 발생",
      "causal_chain": [
        "입력 데이터 품질 저하 (오류율 12% 증가)",
        "검수 불합격 → 재작업 루프 발생",
        "케이스당 평균 1.3회 재작업"
      ],
      "confidence": 0.81
    },
    {
      "rank": 3,
      "variable": "input_volume",
      "variable_label": "시간당 입력 건수",
      "related_activity": null,
      "shap_value": 0.15,
      "contribution_pct": 15.0,
      "actual_value": "시간당 45건",
      "normal_range": "시간당 25~35건",
      "description": "입력량 증가로 전반적인 대기열 길이 증가",
      "causal_chain": [
        "분기말 입력량 30% 증가",
        "전체 대기열 길이 평균 40% 증가"
      ],
      "confidence": 0.74
    }
  ],
  "recommendations": [
    "승인 담당자 추가 배치 (1명→2명) 시 대기시간 50% 감소 예상",
    "검수 기준 명확화 및 입력 데이터 사전 검증으로 재작업 비율 감소",
    "피크 시간대(14:00~17:00) 자원 추가 배치 검토"
  ],
  "explanation": "재고확인 단계의 병목은 상류 활동인 승인 단계의 대기시간 증가가 가장 주된 원인입니다(기여도 42%). 2025년 12월 승인 담당자가 2명에서 1명으로 감소한 이후, 승인 대기열 대기시간이 평균 4.2시간으로 정상 범위(1~2시간)의 2배 이상 증가했습니다. 이로 인해 후속 재고확인 단계의 시작이 지연되고 있습니다. 또한 검수 단계의 재작업 비율(15%)이 정상(3~5%) 대비 3배 높아 추가적인 처리 부하를 발생시키고 있으며(기여도 28%), 분기말 입력량 증가(시간당 45건)도 전반적인 대기열 증가에 기여하고 있습니다(기여도 15%).",
  "causal_graph": {
    "nodes": [
      {"id": "resource_availability", "label": "승인 담당자 가용성", "type": "root_cause"},
      {"id": "queue_wait_time", "label": "승인 대기시간", "type": "intermediate"},
      {"id": "rework_rate", "label": "재작업 비율", "type": "intermediate"},
      {"id": "bottleneck", "label": "재고확인 병목", "type": "outcome"}
    ],
    "edges": [
      {"source": "resource_availability", "target": "queue_wait_time", "coefficient": 0.72},
      {"source": "queue_wait_time", "target": "bottleneck", "coefficient": 0.65},
      {"source": "rework_rate", "target": "bottleneck", "coefficient": 0.45}
    ]
  }
}
```

#### 응답 필드 상세

| 필드 | 타입 | Nullable | 설명 |
|------|------|:--------:|------|
| `bottleneck_activity` | string | N | 분석 대상 병목 활동명 |
| `bottleneck_score` | decimal | N | Synapse 병목 점수 (0.0~1.0) |
| `data_range` | object | N | 분석에 사용된 데이터 범위 |
| `data_range.case_count` | integer | N | 분석 대상 케이스 수 |
| `root_causes` | array | N | 근본원인 목록 (기여도 내림차순) |
| `root_causes[].related_activity` | string | Y | 관련 활동명. 특정 활동과 무관한 원인은 null |
| `root_causes[].normal_range` | string | Y | 정상 범위 참고값 |
| `recommendations` | array | N | 개선 권고사항 목록 |
| `explanation` | string | Y | LLM 생성 서술문 (include_explanation=false면 null) |
| `causal_graph` | object | N | 인과 그래프 시각화 데이터 (React Flow 용) |

---

## 에러 코드

| HTTP | 코드 | 의미 | 사용자 표시 |
|:----:|------|------|-----------|
| 400 | `INSUFFICIENT_DATA` | 분석 대상 데이터 부족 | "분석에 필요한 재무 데이터가 부족합니다" |
| 404 | `CAUSAL_MODEL_NOT_FOUND` | 인과 모델이 학습되지 않음 | "인과 분석 모델이 아직 준비되지 않았습니다" |
| 404 | `ANALYSIS_NOT_FOUND` | 분석 결과 없음 | "분석을 먼저 실행해 주세요" |
| 409 | `ANALYSIS_IN_PROGRESS` | 이미 분석 중 | "분석이 이미 진행 중입니다" |
| 504 | `ANALYSIS_TIMEOUT` | 분석 타임아웃 | "분석 시간이 초과되었습니다" |
| 404 | `PROCESS_MODEL_NOT_FOUND` | Synapse 프로세스 모델 없음 | "프로세스 모델을 찾을 수 없습니다" |
| 400 | `INSUFFICIENT_PROCESS_DATA` | 프로세스 데이터 부족 (케이스 50건 미만) | "프로세스 분석에 필요한 데이터가 부족합니다 (최소 50건 필요)" |
| 502 | `SYNAPSE_UNAVAILABLE` | Synapse 서비스 연결 실패 | "프로세스 마이닝 서비스에 연결할 수 없습니다" |

<!-- affects: 04_frontend, 05_llm/causal-explanation.md, 00_overview/system-overview.md -->
<!-- requires-update: 01_architecture/root-cause-engine.md, 04_frontend/root-cause-ui.md -->
