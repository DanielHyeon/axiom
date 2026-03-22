# Sprint 2 상세 구현서
## Quality-aware Semantic Response Grading — 품질 점수 기반 신뢰도 정책 엔진 구현 계획

- 작성일: 2026-03-23
- 범위: Semantic Quality Score를 Oracle/Canvas 소비 동작으로 연결하는 정책 엔진 구축
- 상위 문서: `final_implementation_status_assessment_v2.md`
- 연계 문서: `sprint1_oracle_semantic_enforcement_detailed_plan.md`
- 목표 상태: **측정 중심 Quality Framework → 행동 연결형 Quality Trust Runtime**

---

## 1. Sprint 2 목표

Sprint 2의 핵심은 단순합니다.

현재 시스템은 freshness, completeness, uniqueness를 수집하고 QualityContract도 보유하고 있지만, **품질 점수가 실제 소비 계층의 행동을 바꾸지 못합니다.** 즉 점수는 존재하지만, Oracle은 평소와 같은 어조로 응답하고, Canvas는 강한 경고 없이 동일하게 결과를 보여주며, 운영자는 임계치 기반 통제 없이 낮은 품질의 의미 계약을 계속 노출할 수 있습니다.

Sprint 2에서는 이 단절을 끊습니다.

이번 스프린트에서 다음 5단계를 하나의 폐루프로 완성합니다.

1. Weaver가 품질 차원별 원시 측정값을 수집한다.
2. Synapse가 release 기준의 정규화 점수와 총합 score를 계산한다.
3. 정책 엔진이 score와 hard-fail 차원을 기준으로 trust tier를 결정한다.
4. Oracle과 Canvas가 trust tier에 따라 응답 톤, 배지, 경고, 차단 동작을 다르게 수행한다.
5. 모든 품질 판정과 소비 결과를 감사 로그 및 이벤트로 남긴다.

이번 스프린트가 끝나면 품질 점수는 단순 메타데이터가 아니라, **사용자 경험과 실행 정책을 바꾸는 1급 제어 신호**가 되어야 합니다.

---

## 2. 이번 스프린트에서 반드시 닫아야 할 문제

### 2.1 낮은 점수여도 Oracle이 정상 답변처럼 보이는 문제
현재 score가 낮아도 Oracle이 일반 응답과 같은 톤으로 결과를 제시할 수 있습니다. 이 상태에서는 품질 엔진이 사용자 신뢰에 실질적으로 기여하지 못합니다.

### 2.2 품질 차원 수집과 정책 행동이 분리된 문제
차원별 측정은 일부 존재하지만, 임계치 판정, 등급화, 차단/강등/주의 배지 같은 정책 행동이 연결되어 있지 않습니다.

### 2.3 release마다 어떤 품질 상태로 노출되는지 추적하기 어려운 문제
같은 semantic release라도 시간에 따라 품질 점수가 달라질 수 있는데, 현재는 어떤 시점에 어떤 등급으로 노출됐는지 운영 추적이 약합니다.

### 2.4 hard-fail 차원이 총점에 묻히는 문제
예를 들어 referential integrity가 붕괴되거나 lineage completeness가 사실상 0에 가까워도, 단순 가중 평균만 사용하면 총점이 상대적으로 높게 보일 수 있습니다.

### 2.5 Canvas와 Oracle의 품질 표현이 일관되지 않은 문제
같은 release를 소비해도 한쪽은 경고를 보이고 다른 쪽은 평상시처럼 보이면, semantic layer의 신뢰 모델이 제품 전반에서 깨집니다.

---

## 3. Sprint 2 비범위

이번 스프린트는 품질 정책 엔진과 소비 계층 행동 연결에 집중합니다. 아래 항목은 비범위로 둡니다.

- 9개 차원의 완전 구현 전부 마무리
- incident health의 외부 관측 시스템 완전 연동
- ML feature source binding
- 도메인별 품질 승인 워크플로 전체 구현
- 품질 이슈 자동 수정 엔진
- 자연어 응답 자동 재작성의 고도화

다만 이후 스프린트에서 확장할 수 있도록 인터페이스와 이벤트는 열어 둡니다.

---

## 4. 완료 기준

다음 항목이 모두 충족되면 Sprint 2 완료로 봅니다.

### 기능 완료 기준
- Synapse가 release 기준 품질 스냅샷과 trust tier를 계산한다.
- Oracle이 질의 실행 전/후 release 품질 등급을 반영해 응답 동작을 바꾼다.
- Canvas가 동일한 trust tier를 사용해 일관된 품질 배지와 경고를 표시한다.
- score, trust tier, hard-fail reason, dimension breakdown이 모두 조회 가능하다.
- score < 임계치일 때 강등 또는 차단 정책이 실제 적용된다.
- 품질 판정 변경이 이벤트로 발행되고 캐시 무효화에 활용된다.

### 품질 완료 기준
- trust tier 판정 단위 테스트 25개 이상
- score 계산/정규화 테스트 20개 이상
- Oracle 응답 강등/차단 분기 테스트 20개 이상
- Canvas 뱃지 및 경고 렌더링 테스트 10개 이상
- 품질 정책 오판(false downgrade)율 5% 이하 목표
- 정책 적용 후 사용자 응답의 tier 일관성 99% 이상

---

## 5. 목표 아키텍처

```text
Weaver Quality Collectors
   ↓
Raw Dimension Metrics
   ↓
Synapse Quality Aggregator
   ├─ normalize dimension scores
   ├─ apply weights
   ├─ hard-fail checks
   ├─ compute total score
   └─ decide trust tier
   ↓
SemanticQualitySnapshot (release-bound)
   ├─ Oracle Trust Policy Adapter
   │    ├─ allow
   │    ├─ warn
   │    ├─ degrade
   │    └─ block
   └─ Canvas Trust Badge Adapter
        ├─ green
        ├─ amber
        ├─ red
        └─ blocked
```

Sprint 2의 본질은 **품질 수집기와 사용자 응답 사이에 Trust Policy Runtime을 끼워 넣는 것**입니다.

---

## 6. 서비스 경계

### 6.1 Weaver 책임
Weaver는 품질 원천 측정의 책임을 집니다.

- freshness 측정
- completeness 측정
- uniqueness 측정
- validity 측정의 최소 구현
- referential integrity 측정의 최소 구현
- lineage completeness 계산에 필요한 lineage metadata 공급
- dimension score raw payload 발행

Weaver는 정책 결정을 하지 않습니다. 측정과 전달만 담당합니다.

### 6.2 Synapse 책임
Synapse는 품질 평가와 정책 결정의 원천입니다.

- 차원별 점수 정규화
- 가중치 적용
- hard-fail 차원 판정
- trust tier 결정
- release-bound quality snapshot 저장
- quality policy CRUD/배포
- Oracle/Canvas에 일관된 snapshot API 제공

### 6.3 Oracle 책임
Oracle은 신뢰 등급에 따른 응답 동작을 수행합니다.

- score/tier 조회
- SQL 실행 허용/강등/차단 결정 반영
- 응답 상단 신뢰 안내문 출력
- score가 낮을 때 보수적 문장 템플릿 사용
- 감사 로그 기록

### 6.4 Canvas 책임
Canvas는 사람이 시각적으로 상태를 이해할 수 있게 만듭니다.

- semantic catalog에 품질 배지 표시
- dimension breakdown 노출
- release 상태와 trust tier 병행 표시
- 차단 상태 시 배포/사용 경고 강조

---

## 7. 핵심 설계 원칙

### 7.1 총점만 보지 않고 hard-fail 차원을 별도로 본다
품질은 단순 평균이 아닙니다. referential integrity나 lineage completeness 같은 차원은 일정 기준 미만이면 총점과 무관하게 강등 또는 차단해야 합니다.

### 7.2 품질은 release-bound snapshot으로 고정한다
Oracle과 Canvas는 같은 질의/같은 화면에서 동일한 quality snapshot을 봐야 합니다. 질의 중간에 값이 바뀌어도 한 요청에서는 동일 snapshot을 사용합니다.

### 7.3 응답 동작은 trust tier 테이블에 의해 결정한다
비즈니스 로직 곳곳에 if-else를 흩뿌리지 말고, 정책 테이블을 중앙에서 관리합니다.

### 7.4 차원별 측정과 정책 등급은 분리한다
측정은 Weaver, 판정은 Synapse가 맡아야 정책 교체와 도메인별 조정이 쉬워집니다.

### 7.5 사용자에게는 간단히, 운영자에게는 상세히 보여준다
사용자는 “신뢰 가능/주의 필요/참고용/차단” 정도만 보면 충분합니다. 운영자는 차원별 점수와 hard-fail 이유까지 봐야 합니다.

---

## 8. Trust Tier 모델

Sprint 2에서는 4단계 trust tier를 도입합니다.

| Tier | 코드 | 의미 | Oracle 동작 | Canvas 동작 |
|---|---|---|---|---|
| T1 | TRUSTED | 신뢰 가능 | 일반 응답 | 초록 배지 |
| T2 | CAUTION | 주의 필요 | 경고 포함 응답 | 노랑 배지 + 경고 |
| T3 | REFERENCE_ONLY | 참고용 | 강등 응답, 보수적 문장 | 주황/빨강 배지 + 상세 경고 |
| T4 | BLOCKED | 사용 차단 | 실행 차단 또는 결과 노출 차단 | 차단 배지 |

### 8.1 Tier 기본 임계치
기본 임계치는 전역 정책으로 시작합니다.

- T1 TRUSTED: score >= 85 이고 hard-fail 없음
- T2 CAUTION: 70 <= score < 85 이고 hard-fail 없음
- T3 REFERENCE_ONLY: 50 <= score < 70 또는 soft-fail 존재
- T4 BLOCKED: score < 50 또는 hard-fail 존재

### 8.2 Hard-fail 조건
아래는 점수와 무관하게 T4로 즉시 강등할 수 있습니다.

- referential_integrity < 40
- lineage_completeness < 30
- validity < 35
- release 상태가 deprecated/suspended
- 최근 24시간 내 critical incident 연동 플래그 true

### 8.3 Soft-fail 조건
아래는 총점과 별도로 T3 이상 강등 조건으로 사용합니다.

- freshness < 50
- completeness < 60
- uniqueness < 70
- test_coverage < 50

---

## 9. 품질 점수 모델

### 9.1 차원 정의
Sprint 2에서 공식 지원하는 차원은 다음 9개입니다.

1. freshness
2. completeness
3. uniqueness
4. validity
5. referential_integrity
6. lineage_completeness
7. test_coverage
8. incident_health
9. policy_compliance

현재 완전 측정이 없는 차원은 최소 구현 또는 placeholder 측정으로 시작합니다.

### 9.2 가중치 기본안

| 차원 | 기본 가중치 |
|---|---:|
| freshness | 0.15 |
| completeness | 0.15 |
| uniqueness | 0.10 |
| validity | 0.10 |
| referential_integrity | 0.10 |
| lineage_completeness | 0.10 |
| test_coverage | 0.10 |
| incident_health | 0.10 |
| policy_compliance | 0.10 |
|
| 총합 | 1.00 |

### 9.3 점수 계산식

정규화 점수는 0~100 범위로 계산합니다.

```text
dimension_score = normalize(raw_metric, dimension_rule)
weighted_score = Σ(dimension_score × weight)
penalty = hard_fail_penalty + soft_fail_penalty
final_score = max(0, min(100, weighted_score - penalty))
```

### 9.4 Penalty 규칙
초기 버전에서는 복잡한 비선형 모델보다 단순 규칙 기반 penalty를 사용합니다.

- soft-fail 1개당 5점 차감
- soft-fail 2개 이상이면 추가 5점 차감
- hard-fail은 final tier를 T4로 고정하고 final_score는 참고값으로만 저장

---

## 10. 데이터 모델 추가/보완

Sprint 2에서는 기존 `quality_contracts`를 유지하되, 소비 계층과 판정 추적을 위해 아래 테이블을 추가합니다.

### 10.1 semantic_quality_snapshots
release 단위 품질 스냅샷 저장

```sql
CREATE TABLE semantic_quality_snapshots (
  snapshot_id            UUID PRIMARY KEY,
  release_id             UUID NOT NULL,
  domain_id              VARCHAR(100) NOT NULL,
  entity_key             VARCHAR(255),
  final_score            NUMERIC(5,2) NOT NULL,
  trust_tier             VARCHAR(32) NOT NULL,
  has_hard_fail          BOOLEAN NOT NULL DEFAULT FALSE,
  hard_fail_codes        JSONB NOT NULL DEFAULT '[]'::jsonb,
  soft_fail_codes        JSONB NOT NULL DEFAULT '[]'::jsonb,
  dimension_breakdown    JSONB NOT NULL,
  source_window_start    TIMESTAMP,
  source_window_end      TIMESTAMP,
  calculated_at          TIMESTAMP NOT NULL,
  expires_at             TIMESTAMP,
  is_latest              BOOLEAN NOT NULL DEFAULT TRUE,
  created_by             VARCHAR(100) DEFAULT 'system'
);

CREATE INDEX idx_quality_snapshots_release_latest
  ON semantic_quality_snapshots(release_id, is_latest);
```

### 10.2 semantic_quality_policies
trust tier 임계치와 hard-fail 규칙 저장

```sql
CREATE TABLE semantic_quality_policies (
  policy_id              UUID PRIMARY KEY,
  policy_name            VARCHAR(200) NOT NULL,
  scope_type             VARCHAR(50) NOT NULL,
  scope_key              VARCHAR(255),
  weights_json           JSONB NOT NULL,
  thresholds_json        JSONB NOT NULL,
  hard_fail_rules_json   JSONB NOT NULL,
  soft_fail_rules_json   JSONB NOT NULL,
  response_actions_json  JSONB NOT NULL,
  status                 VARCHAR(32) NOT NULL DEFAULT 'draft',
  version                INTEGER NOT NULL,
  created_at             TIMESTAMP NOT NULL,
  updated_at             TIMESTAMP NOT NULL,
  approved_at            TIMESTAMP,
  approved_by            VARCHAR(100)
);
```

### 10.3 semantic_quality_decisions
실제 Oracle/Canvas 소비 시 어떤 정책이 적용됐는지 기록

```sql
CREATE TABLE semantic_quality_decisions (
  decision_id            UUID PRIMARY KEY,
  request_id             VARCHAR(100) NOT NULL,
  consumer_type          VARCHAR(32) NOT NULL,
  release_id             UUID NOT NULL,
  snapshot_id            UUID NOT NULL,
  trust_tier             VARCHAR(32) NOT NULL,
  action_taken           VARCHAR(64) NOT NULL,
  rationale_json         JSONB NOT NULL,
  created_at             TIMESTAMP NOT NULL
);
```

### 10.4 기존 quality_contracts 보완 필드

```sql
ALTER TABLE quality_contracts
  ADD COLUMN IF NOT EXISTS scoring_method VARCHAR(50) DEFAULT 'weighted_sum',
  ADD COLUMN IF NOT EXISTS hard_fail_dimensions JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS policy_id UUID;
```

---

## 11. 최소 구현이 필요한 추가 품질 차원

Sprint 2에서 9개 전부를 완벽하게 만들 필요는 없습니다. 그러나 최소한 아래 3개는 계산 가능해야 합니다.

### 11.1 validity
컬럼 타입/도메인/허용 범위/NULL 불가 조건 위반 비율 기준으로 계산합니다.

예시:

```text
validity = 100 - (invalid_rows / inspected_rows) × 100
```

초기 구현은 semantic entity별 critical column subset에 대해서만 수행합니다.

### 11.2 referential_integrity
승인된 JoinContract의 FK-like 관계를 기준으로 orphan ratio를 계산합니다.

```text
referential_integrity = 100 - (orphan_count / inspected_rows) × 100
```

초기 구현은 high-value join 10개 내외만 대상으로 수행합니다.

### 11.3 lineage_completeness
entity/measure/dimension이 lineage graph에서 upstream/downstream 연결을 얼마나 갖고 있는지로 계산합니다.

```text
lineage_completeness =
  (documented_upstream_edges + documented_transforms + downstream_consumers)
  / expected_lineage_nodes × 100
```

초기에는 정확한 전체 계보 대신 다음 기준으로 시작합니다.

- upstream source 존재 여부
- transformation step 등록 여부
- owner 지정 여부
- downstream consumer 등록 여부

즉 metadata completeness 기반의 최소 버전으로 도입하고, 이후 실제 lineage 파이프라인과 연결합니다.

---

## 12. Synapse 품질 집계기 설계

### 12.1 핵심 클래스 구조

```text
QualityAggregationService
 ├─ QualityMetricIngestService
 ├─ QualityNormalizationService
 ├─ QualityPenaltyService
 ├─ TrustTierDecisionService
 ├─ QualitySnapshotRepository
 └─ QualityDecisionEventPublisher
```

### 12.2 클래스 책임

#### QualityMetricIngestService
- Weaver raw payload 수신
- 차원별 raw metric 저장/캐시
- 동일 release/entity 최신값 취합

#### QualityNormalizationService
- 차원별 normalize 규칙 적용
- 0~100 score 변환
- dimension breakdown 생성

#### QualityPenaltyService
- soft-fail/hard-fail 판정
- penalty 계산

#### TrustTierDecisionService
- score + fail state를 바탕으로 tier 결정
- response action 결정

#### QualityDecisionEventPublisher
- snapshot 생성/변경 이벤트 발행
- Oracle/Canvas 캐시 무효화 이벤트 발행

---

## 13. API 설계

### 13.1 Weaver → Synapse 수집 API

#### POST `/api/synapse/quality/metrics/ingest`

```json
{
  "release_id": "rel_sales_v12",
  "domain_id": "sales",
  "entity_key": "sales.order",
  "window_start": "2026-03-23T00:00:00Z",
  "window_end": "2026-03-23T00:15:00Z",
  "dimensions": [
    {"dimension": "freshness", "raw_value": 4, "unit": "minutes_lag"},
    {"dimension": "completeness", "raw_value": 0.982, "unit": "ratio"},
    {"dimension": "uniqueness", "raw_value": 0.997, "unit": "ratio"},
    {"dimension": "validity", "raw_value": 0.975, "unit": "ratio"},
    {"dimension": "referential_integrity", "raw_value": 0.991, "unit": "ratio"},
    {"dimension": "lineage_completeness", "raw_value": 0.75, "unit": "ratio"}
  ]
}
```

응답:

```json
{
  "accepted": true,
  "queued_for_aggregation": true,
  "release_id": "rel_sales_v12"
}
```

### 13.2 품질 스냅샷 조회 API

#### GET `/api/synapse/quality/snapshots/{releaseId}`

```json
{
  "release_id": "rel_sales_v12",
  "snapshot_id": "qs_123",
  "final_score": 78.40,
  "trust_tier": "CAUTION",
  "has_hard_fail": false,
  "hard_fail_codes": [],
  "soft_fail_codes": ["LOW_LINEAGE_COMPLETENESS"],
  "dimension_breakdown": {
    "freshness": 95,
    "completeness": 92,
    "uniqueness": 99,
    "validity": 97,
    "referential_integrity": 99,
    "lineage_completeness": 55,
    "test_coverage": 60,
    "incident_health": 85,
    "policy_compliance": 90
  },
  "actions": {
    "oracle": "warn",
    "canvas_badge": "amber",
    "allow_execution": true
  },
  "calculated_at": "2026-03-23T01:15:00Z"
}
```

### 13.3 정책 CRUD API

- `POST /api/synapse/quality/policies`
- `PUT /api/synapse/quality/policies/{policyId}`
- `POST /api/synapse/quality/policies/{policyId}/approve`
- `POST /api/synapse/quality/policies/{policyId}/publish`
- `GET /api/synapse/quality/policies/active?scope=domain:sales`

### 13.4 Oracle 소비 API

#### GET `/api/synapse/quality/runtime/release/{releaseId}`

Oracle용 경량 응답입니다.

```json
{
  "release_id": "rel_sales_v12",
  "snapshot_id": "qs_123",
  "final_score": 78.40,
  "trust_tier": "CAUTION",
  "allow_execution": true,
  "response_mode": "warn",
  "user_banner": "이 결과는 일부 품질 주의가 필요한 시맨틱 계약을 기반으로 합니다.",
  "developer_reasons": ["LOW_LINEAGE_COMPLETENESS"]
}
```

---

## 14. Oracle 응답 정책 상세 설계

### 14.1 Oracle 처리 흐름

```text
Resolve semantic release
  ↓
Fetch quality runtime snapshot
  ↓
If BLOCKED → stop before result presentation
Else execute / or continue with validated result
  ↓
Apply response mode template
  ↓
Attach trust banner + metadata
  ↓
Log quality decision
```

### 14.2 ResponseMode 정의

| ResponseMode | 설명 |
|---|---|
| normal | 일반 응답 |
| warn | 결과 제공 + 품질 주의 문구 |
| degrade | 결과 제공 + 참고용 강등 + 더 보수적 표현 |
| block | 결과 제공 차단 또는 실행 차단 |

### 14.3 Oracle 응답 문구 템플릿

#### TRUSTED
- “현재 승인된 시맨틱 계약 기준으로 결과를 제공합니다.”

#### CAUTION
- “결과는 제공되지만 일부 품질 신호가 낮아 해석 시 주의가 필요합니다.”

#### REFERENCE_ONLY
- “이 결과는 참고용입니다. 일부 품질 지표가 기준 미만이므로 운영 의사결정에는 추가 검증이 필요합니다.”

#### BLOCKED
- “현재 이 시맨틱 계약은 품질 기준을 충족하지 않아 결과 제공이 제한됩니다.”

### 14.4 Oracle 내부 클래스 초안

```text
OracleQualityRuntimeClient
OracleTrustPolicyEvaluator
OracleResponseModeResolver
OracleTrustBannerBuilder
OracleQualityDecisionLogger
```

#### OracleTrustPolicyEvaluator
입력:
- release_id
- snapshot
- enforcement result (Sprint 1 결과)

출력:
- allow_execution
- response_mode
- user_banner
- developer_reasons

### 14.5 Sprint 1과의 연결 규칙
품질 정책은 시맨틱 계약 검증 이후 적용합니다.

1. Sprint 1 검증 실패 → 즉시 차단
2. Sprint 1 검증 통과 + 품질 BLOCKED → 결과 차단 또는 결과 노출 차단
3. Sprint 1 검증 통과 + 품질 REFERENCE_ONLY → 결과 허용, 강등 응답
4. Sprint 1 검증 통과 + 품질 CAUTION/TRUSTED → 결과 허용

즉 **정합성 검증이 먼저, 품질 신뢰도 판정이 다음**입니다.

---

## 15. Canvas UI 설계

### 15.1 표시 위치
- 시맨틱 카탈로그 release 헤더
- measure/entity 상세 패널
- NL2SQL 결과 패널 상단
- 배포 승인 화면

### 15.2 배지 규칙

| Tier | Badge | 표현 |
|---|---|---|
| TRUSTED | green | 신뢰 가능 |
| CAUTION | amber | 주의 필요 |
| REFERENCE_ONLY | orange/red | 참고용 |
| BLOCKED | dark red | 사용 차단 |

### 15.3 상세 패널 정보
- 총점
- 차원별 막대 또는 리스트
- hard-fail 여부
- soft-fail 사유
- 계산 시각
- 적용 policy 버전

### 15.4 배포 흐름 연결
release를 publish하려 할 때 현재 trust tier가 T3 이하라면 다음을 보여줍니다.

- CAUTION: 경고 모달 후 진행 가능
- REFERENCE_ONLY: 추가 승인 필요
- BLOCKED: publish 차단 또는 관리자 override 필요

---

## 16. 이벤트 계약

### 16.1 새 이벤트 타입

#### `semantic.quality.snapshot.created`
```json
{
  "event_type": "semantic.quality.snapshot.created",
  "release_id": "rel_sales_v12",
  "snapshot_id": "qs_123",
  "trust_tier": "CAUTION",
  "final_score": 78.40,
  "calculated_at": "2026-03-23T01:15:00Z"
}
```

#### `semantic.quality.snapshot.changed`
```json
{
  "event_type": "semantic.quality.snapshot.changed",
  "release_id": "rel_sales_v12",
  "previous_tier": "TRUSTED",
  "current_tier": "REFERENCE_ONLY",
  "reason_codes": ["LOW_FRESHNESS", "LOW_LINEAGE_COMPLETENESS"]
}
```

#### `semantic.quality.policy.published`
```json
{
  "event_type": "semantic.quality.policy.published",
  "policy_id": "qp_42",
  "scope_type": "domain",
  "scope_key": "sales",
  "version": 3
}
```

### 16.2 이벤트 수신자
- Oracle: 캐시 무효화, tier 변경 즉시 반영
- Canvas: 최신 배지 재조회
- Weaver: 품질 이슈 분석 참고
- Audit pipeline: 변경 이력 저장

---

## 17. 캐시 설계

### 17.1 캐시 대상
- release별 최신 quality runtime snapshot
- active quality policy

### 17.2 Redis 키 예시

```text
semantic:quality:runtime:{release_id}
semantic:quality:policy:{scope_type}:{scope_key}
```

### 17.3 캐시 TTL
- runtime snapshot: 5분
- active policy: 10분

TTL보다 중요한 것은 이벤트 기반 무효화입니다.

### 17.4 무효화 규칙
- quality snapshot created/changed 이벤트 수신 시 release 키 삭제
- quality policy published 이벤트 수신 시 policy 키 삭제

---

## 18. 운영 정책

### 18.1 초기 롤아웃 모드
초기 1주일은 observe mode를 권장합니다.

- Oracle: 실제 차단 대신 배너만 표시
- Canvas: 모든 tier 표시
- 로그: trust decision 전량 기록

### 18.2 점진적 강제 모드
2주차부터 아래 순서로 강화합니다.

1. BLOCKED만 실제 차단
2. REFERENCE_ONLY 강등 문구 적용
3. 배포 승인 시 낮은 tier 경고/차단 적용

### 18.3 Override 정책
관리자 또는 Semantic Architect만 일시적 override 가능하게 합니다.

Override에는 반드시 아래가 포함돼야 합니다.
- override 사유
- 적용 기간
- 책임자
- 만료 시각

---

## 19. 테스트 전략

### 19.1 단위 테스트
- normalize 규칙 테스트
- weighted score 계산 테스트
- hard-fail precedence 테스트
- trust tier 분기 테스트
- Oracle response mode 분기 테스트

### 19.2 통합 테스트
- Weaver raw metric ingest → snapshot 생성
- snapshot 변경 → Oracle 재조회
- BLOCKED tier → Oracle 차단
- REFERENCE_ONLY tier → Oracle 강등 응답
- Canvas badge 일관성 확인

### 19.3 회귀 테스트
- 점수 높지만 referential integrity 낮은 경우 차단 확인
- 점수 경계값 49/50/69/70/84/85 처리 확인
- policy version 변경 시 snapshot 재평가 확인

### 19.4 성능 테스트
- snapshot 조회 p95 50ms 이하
- Oracle trust policy 적용 오버헤드 p95 20ms 이하
- ingest → snapshot 생성 지연 30초 이하 목표

---

## 20. 보안 및 감사

### 20.1 보안
- 품질 정책 수정/배포는 세분화된 역할만 허용
- quality decision API는 내부 서비스 호출 우선
- override는 강한 감사 로그 필수

### 20.2 감사 로그 필드
- request_id
- release_id
- snapshot_id
- trust_tier
- action_taken
- user_id 또는 service_id
- reason_codes
- policy_version
- timestamp

---

## 21. 구현 순서 (4주 계획)

### Week 1 — Synapse 품질 집계 코어
- `semantic_quality_snapshots`, `semantic_quality_policies`, `semantic_quality_decisions` 생성
- QualityAggregationService 구현
- normalize/score/tier 계산 로직 구현
- quality runtime 조회 API 구현

### Week 2 — Weaver 최소 차원 확장
- validity 최소 수집기 구현
- referential integrity 최소 수집기 구현
- lineage completeness metadata 기반 계산기 구현
- ingest payload와 aggregation 연결

### Week 3 — Oracle/Canvas 소비 연결
- OracleQualityRuntimeClient 구현
- OracleResponseModeResolver 구현
- user banner/degraded response 연결
- Canvas 배지/상세 패널 연결

### Week 4 — 이벤트/캐시/강제 모드
- quality snapshot changed 이벤트 발행/수신
- Redis 캐시/무효화 연결
- observe mode → partial enforce mode 전환
- 통합 회귀 테스트 및 운영 대시보드 점검

---

## 22. 산출물 체크리스트

### 백엔드
- [ ] DB migration 3개
- [ ] QualityAggregationService
- [ ] TrustTierDecisionService
- [ ] quality ingest/runtime/policy API
- [ ] 이벤트 발행/수신
- [ ] Redis 캐시

### Oracle
- [ ] Quality runtime client
- [ ] response mode evaluator
- [ ] trust banner builder
- [ ] degraded response template
- [ ] quality decision audit log

### Canvas
- [ ] trust badge component
- [ ] dimension breakdown panel
- [ ] release header integration
- [ ] publish warning modal

### QA/운영
- [ ] score/tier 테스트 세트
- [ ] observe mode 로그 검증
- [ ] rollback toggle 준비

---

## 23. 예상 리스크와 대응

### 23.1 과도한 차단 리스크
초기 임계치가 너무 공격적이면 정상 release까지 차단될 수 있습니다.

대응:
- observe mode 선행
- override 제공
- hard-fail 차원 최소화

### 23.2 측정값 신뢰도 자체가 낮은 리스크
새 차원(특히 lineage completeness)의 초기 계산이 거칠 수 있습니다.

대응:
- dimension별 신뢰도 메타 추가
- 초기에는 soft-fail 위주 적용
- 샘플 검증 루틴 운영

### 23.3 Oracle/Canvas 표현 불일치 리스크
서로 다른 API나 캐시를 쓰면 tier가 어긋날 수 있습니다.

대응:
- 동일 snapshot API 사용
- event-driven invalidation 강제
- request/response에 snapshot_id 포함

### 23.4 운영자 피로도 증가 리스크
경고가 너무 많으면 배지가 무시됩니다.

대응:
- 4단계 tier 단순화 유지
- 사용자용 메시지는 1줄로 제한
- 운영자 상세 화면에서만 breakdown 전체 노출

---

## 24. Sprint 2 종료 시 기대 상태

Sprint 2가 끝나면 다음 상태가 되어야 합니다.

- 품질 점수는 더 이상 장식용 메타데이터가 아니다.
- Oracle은 같은 semantic release라도 신뢰 등급에 따라 다른 행동을 한다.
- Canvas는 배포/조회/탐색 전 영역에서 일관된 품질 배지를 보여준다.
- release 품질 상태는 시점별 snapshot으로 추적 가능하다.
- hard-fail 차원은 총점에 묻히지 않고 실제 차단 규칙으로 동작한다.

즉 시스템은 **“정확성 검증(Sprint 1) + 신뢰도 정책(Sprint 2)”**의 두 축을 갖추게 됩니다.

---

## 25. Sprint 3 연결 포인트

Sprint 3에서는 품질 정책이 장기적으로 안정적으로 동작하도록 다음을 이어서 진행합니다.

- 계약 변경/품질 변경 이벤트와 Redis semantic snapshot 캐시의 완전 연결
- version pinning
- synonym-aware context expansion과 품질/정합성 정책의 동시 적용
- domain-specific quality policy override

Sprint 2의 핵심은 다음 한 문장으로 요약됩니다.

**“품질 점수는 계산으로 끝나는 것이 아니라, Oracle과 Canvas의 동작을 바꾸는 정책 신호가 되어야 한다.”**
