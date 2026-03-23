# Sprint 4 상세 구현서
## Ontology Synonym Expansion & Intent Confidence Runtime 구현 계획

- 작성일: 2026-03-23
- 대상 스프린트: Sprint 4
- 상위 문서:
  - `final_implementation_status_assessment_v2.md`
  - `sprint1_oracle_semantic_enforcement_detailed_plan.md`
  - `sprint2_quality_trust_policy_detailed_plan.md`
  - `sprint3_semantic_snapshot_consistency_detailed_plan.md`
- 대상 시스템:
  - Synapse (Ontology/Semantic Control Plane)
  - Oracle (NL2SQL/AI Consumer)
  - Canvas (운영/카탈로그 UI)
  - Weaver (선택적 품질/학습 피드백 공급자)
- 목표 한 줄 요약:
  - **“질문을 SQL로 바꾸기 전에, 질문을 온톨로지와 시멘틱 계약의 언어로 먼저 해석하는 runtime을 구축한다.”**

---

## 1. Sprint 4의 목표

Sprint 1이 Oracle의 생성 결과를 검증하고, Sprint 2가 품질 점수에 따라 응답 행동을 바꾸고, Sprint 3이 semantic snapshot 일관성을 보장했다면, Sprint 4는 그 이전 단계인 **질문 이해(question understanding)** 를 닫는 단계다.

현재 구조의 가장 큰 한계는 다음과 같다.

1. 사용자는 비즈니스 용어, 줄임말, 현업 별칭, 한국어/영어 혼용 표현을 사용한다.
2. Oracle은 일부 키워드 기반 intent 분류로 ContextPack을 고르지만, **온톨로지 동의어와 개념 변형을 충분히 활용하지 못한다.**
3. 같은 질문이라도 domain synonym, time alias, metric alias를 해석하지 못하면 LLM 프롬프트 품질이 크게 흔들린다.
4. intent confidence가 없으므로, 확신이 낮은 질문도 일반 흐름으로 통과해 품질이 나빠진다.
5. 결과적으로 Oracle은 계약을 잘 강제할 수는 있어도, **질문을 처음부터 올바른 semantic context에 놓는 능력은 아직 약하다.**

Sprint 4의 목표는 다음 5단계를 하나의 폐루프로 만드는 것이다.

1. 사용자 질문을 정규화한다.
2. 온톨로지 용어, 동의어, alias, 도메인 사전, 금지 표현을 활용해 semantic candidates를 추출한다.
3. intent classifier가 질문의 의도와 신뢰도(confidence)를 산출한다.
4. confidence와 semantic candidates를 기준으로 적절한 ContextPack/PromptPolicy/semantic release를 선택 또는 축소한다.
5. Oracle은 해석 근거를 메타데이터로 남기고, confidence가 낮거나 ambiguity가 높으면 안전한 fallback 경로를 탄다.

이번 스프린트가 끝나면 Oracle은 더 이상 “키워드 중심 질의 진입기”가 아니라, **“온톨로지 용어망과 확률적 의도 판정 위에서 질문을 의미적으로 정규화하는 AI consumer”** 로 바뀌어야 한다.

---

## 2. 이번 스프린트에서 반드시 닫아야 할 문제

### 2.1 synonym_map이 질문 확장에 실제로 쓰이지 않는 문제
온톨로지_terms와 용어 메타데이터가 있어도, 현재 질문 전처리에서 실질적으로 활용되지 않으면 저장만 해두고 소비하지 않는 상태가 된다.

### 2.2 metric alias / business alias 해석 실패 문제
예를 들어 사용자는 다음과 같이 질문할 수 있다.

- 고객 수 = 회원 수 = 활성 고객 = 유효 가입자
- 매출 = 실적 = 거래액 = 수익(부정확하지만 현업에서 혼용)
- 지난달 = 전월 = 지난 월 = previous month

이런 표현이 semantic entity/measure/dimension에 안정적으로 연결되지 않으면, LLM은 프롬프트 단계부터 흔들린다.

### 2.3 intent confidence 부재 문제
현재 키워드 기반 intent는 매칭 결과는 줄 수 있어도, **얼마나 확신하는지** 를 알려주지 못한다. 따라서 낮은 확신의 질문도 같은 강도로 일반 흐름에 태워 버린다.

### 2.4 ambiguity를 관리하지 못하는 문제
질문이 여러 의미로 해석될 수 있어도, 현재는 어느 하나를 사실상 임의로 선택하거나, 너무 넓은 semantic context를 넣어 버릴 수 있다. 이 경우 hallucination과 wrong-join 유인이 커진다.

### 2.5 domain-specific vocabulary drift 문제
도메인 팀마다 같은 개념을 다른 용어로 쓰고, 시간이 지나며 용어가 바뀐다. 이를 ontological term lifecycle과 연결하지 않으면 질문 이해 품질이 빠르게 노후화된다.

### 2.6 Canvas에서 왜 특정 용어가 그렇게 해석됐는지 보이지 않는 문제
운영자와 semantic architect 입장에서는 “왜 이 질문이 이 intent로 분류됐고, 어떤 synonym이 적용됐는지” 를 볼 수 있어야 개선이 가능하다.

---

## 3. Sprint 4 비범위

이번 스프린트는 **질문 이해와 semantic expansion runtime** 에 집중한다. 아래 항목은 비범위로 둔다.

- 대규모 foundation model fine-tuning
- 검색엔진 수준의 general semantic retrieval 전체 교체
- 다국어 완전 지원 전체
- 음성 인식/ASR 파이프라인 개선
- 사용자별 개인화 intent model
- fully autonomous clarification dialogue engine
- ontology reasoning rule 전체 자동 생성

단, 이후 Sprint 5 이상에서 확장할 수 있도록 이벤트, feature logging, feedback loop는 열어 둔다.

---

## 4. 완료 기준

### 4.1 기능 완료 기준
- Oracle이 질문 처리 시작 시 ontology synonym expansion을 수행한다.
- expansion 결과가 semantic entities / measures / dimensions / time aliases / domain aliases에 매핑된다.
- intent classifier가 최소 7개 기존 intent에 대해 confidence score를 산출한다.
- low-confidence / ambiguous / out-of-ontology 질문에 대해 fallback 정책이 적용된다.
- ContextPack 선택이 단순 키워드가 아니라 intent confidence + semantic candidate set 기반으로 동작한다.
- Canvas에서 질문 해석 결과, confidence, 적용 synonym, rejected candidate를 확인할 수 있다.
- 모든 question understanding 결과가 trace/event/log로 남는다.

### 4.2 비기능 완료 기준
- 질의 전처리 + expansion + intent scoring 총 95p latency: **120ms 이하**
- ontology term hit ratio 측정 가능
- top-1 intent precision: **기존 대비 15% 이상 개선**
- ambiguity fallback false-positive rate: **10% 이하**
- 운영자가 synonym 변경 후 반영 상태를 snapshot/version 단위로 확인 가능

---

## 5. 목표 아키텍처

```text
[User Question]
   ↓
[Oracle Question Understanding Pipeline]
   ├─ Normalizer
   ├─ Token/phrase extractor
   ├─ Ontology Synonym Expander
   ├─ Semantic Candidate Resolver
   ├─ Intent Classifier + Confidence Scorer
   ├─ Ambiguity Resolver / Safety Router
   └─ ContextPack Selector
   ↓
[Semantic Request Envelope]
   ├─ pinned snapshot version
   ├─ resolved intent + confidence
   ├─ matched concepts/terms/measures/dimensions
   ├─ rejected candidates
   ├─ ambiguity flags
   └─ policy mode
   ↓
[Prompt Builder]
   ↓
[LLM]
   ↓
[Sprint 1 Validation]
   ↓
[Sprint 2 Quality Policy]
   ↓
[Response]
```

Sprint 4에서 추가되는 핵심은 **Semantic Request Envelope** 다. 이 envelope는 단순 raw user question이 아니라, 질문 해석 결과를 정형화한 실행 단위다. 이후 LLM, validation, quality policy는 이 envelope를 기준으로 동작한다.

---

## 6. 핵심 설계 원칙

### 6.1 질문을 먼저 온톨로지 언어로 바꾼다
LLM에게 바로 질문을 던지지 않는다. 먼저 사용자 표현을 ontology terms, canonical concepts, semantic entities로 정규화한다.

### 6.2 확신이 낮으면 context를 넓히지 말고 좁힌다
확신이 없을 때는 많은 계약을 넣어 “알아서 맞추게” 하지 않는다. 오히려 위험하다. confidence가 낮으면 safe fallback으로 전환한다.

### 6.3 해석은 explainable 해야 한다
어떤 token/phrase가 어떤 synonym rule에 의해 어떤 concept로 해석됐는지 남겨야 한다.

### 6.4 ontology lifecycle과 runtime을 연결한다
deprecated term, blocked term, experimental alias는 runtime에서 실제로 다르게 처리되어야 한다.

### 6.5 LLM 분류를 도입하더라도 rule-based skeleton을 유지한다
완전 블랙박스 intent classifier로 치환하지 않는다. ontological term hit, rule match, explicit signals를 함께 사용한 hybrid 구조로 간다.

---

## 7. 데이터 모델 설계

Sprint 4에서는 완전히 새로운 거대 스키마보다, 기존 ontology/semantic 테이블 위에 runtime 친화적인 보조 구조를 추가한다.

### 7.1 기존 테이블 재사용
- `ontology_concepts`
- `ontology_terms`
- `semantic_entities`
- `semantic_measures`
- `semantic_dimensions`
- `semantic_releases`
- `context_packs`
- `prompt_policies`

### 7.2 신규 테이블 제안

#### 7.2.1 `ontology_term_alias_groups`
용도: 여러 alias를 하나의 canonical term cluster로 묶는다.

```sql
create table ontology_term_alias_groups (
  id uuid primary key,
  tenant_id uuid not null,
  domain_id uuid not null,
  canonical_term_id uuid not null,
  group_name varchar(200) not null,
  language_code varchar(16) not null default 'ko',
  status varchar(32) not null default 'ACTIVE',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

#### 7.2.2 `ontology_term_expansion_rules`
용도: exact, normalized, regex, token-set, time alias, acronym 규칙 정의.

```sql
create table ontology_term_expansion_rules (
  id uuid primary key,
  tenant_id uuid not null,
  domain_id uuid not null,
  alias_group_id uuid not null references ontology_term_alias_groups(id),
  rule_type varchar(32) not null,
  match_pattern text not null,
  normalized_pattern text,
  boost numeric(5,2) not null default 1.0,
  priority int not null default 100,
  status varchar(32) not null default 'ACTIVE',
  effective_from timestamptz,
  effective_to timestamptz,
  created_at timestamptz not null default now()
);
```

#### 7.2.3 `intent_models`
용도: intent classifier 버전/구성 관리.

```sql
create table intent_models (
  id uuid primary key,
  tenant_id uuid not null,
  model_key varchar(100) not null,
  model_version varchar(64) not null,
  model_type varchar(32) not null,
  status varchar(32) not null default 'ACTIVE',
  config_json jsonb not null,
  created_at timestamptz not null default now()
);
```

#### 7.2.4 `intent_inference_logs`
용도: 분류 결과, confidence, feature, fallback 추적.

```sql
create table intent_inference_logs (
  id uuid primary key,
  tenant_id uuid not null,
  request_id varchar(100) not null,
  snapshot_version varchar(100) not null,
  user_question text not null,
  normalized_question text not null,
  top_intent varchar(64),
  confidence numeric(5,2),
  ambiguity_score numeric(5,2),
  fallback_mode varchar(32),
  feature_json jsonb not null,
  candidate_json jsonb not null,
  created_at timestamptz not null default now()
);
```

#### 7.2.5 `semantic_question_feedback`
용도: 운영자가 오분류/미매핑을 교정하고 학습 재료를 남김.

```sql
create table semantic_question_feedback (
  id uuid primary key,
  tenant_id uuid not null,
  request_id varchar(100) not null,
  issue_type varchar(32) not null,
  expected_intent varchar(64),
  expected_concept_id uuid,
  expected_measure_id uuid,
  feedback_note text,
  resolved boolean not null default false,
  created_by uuid,
  created_at timestamptz not null default now()
);
```

---

## 8. Oracle 내부 컴포넌트 설계

### 8.1 `QuestionNormalizer`
책임:
- 소문자/대문자 정규화
- 공백/구두점 정리
- 한영 혼용 정규화
- 날짜 표현 정규화 (예: 지난달 → relative_time:last_month)
- 숫자/단위 보정 (예: 억, %, 건)

입력:
- raw question

출력:
- normalized question
- tokens
- phrases
- time hints

### 8.2 `OntologySynonymExpander`
책임:
- ontology term 및 expansion rule 조회
- token/phrase 기반 candidate concept 매핑
- synonym hit score 계산
- deprecated/blocked term 처리

출력:
- matched term list
- canonical concept candidates
- alias evidence
- rejected rules

### 8.3 `SemanticCandidateResolver`
책임:
- concept → entity/measure/dimension/time contract 후보 연결
- domain boundary 고려
- cross-domain ambiguity 계산
- top-k candidate set 생성

출력:
- `ResolvedSemanticCandidates`

### 8.4 `IntentClassifier`
책임:
- hybrid 분류 수행
- rule-based explicit signal + lightweight ML/LLM score 결합
- intent confidence와 ambiguity score 산출

권장 intent 예시:
- METRIC_LOOKUP
- TREND_ANALYSIS
- SLICE_AND_DICE
- COMPARISON
- EXPLANATION
- QUALITY_STATUS
- GOVERNANCE_DISCOVERY
- UNKNOWN

### 8.5 `AmbiguityRouter`
책임:
- low-confidence, multi-domain, conflicting measure 해석 시 fallback 경로 결정
- 안전 정책 적용

fallback mode 예시:
- `SAFE_NARROW_CONTEXT`
- `ASK_FOR_CLARIFICATION` (UI 지원 시)
- `REFERENCE_ONLY`
- `BLOCK_AND_EXPLAIN`

### 8.6 `SemanticContextSelector`
책임:
- resolved intent와 candidates에 맞는 ContextPack 선택
- PromptPolicy set 결정
- quality/trust tier 영향 반영
- pinned snapshot version과 결합

---

## 9. Hybrid Intent Classifier 설계

Sprint 4에서는 완전한 대형 모델 분류 대신 **Hybrid Intent Classifier** 를 권장한다.

### 9.1 입력 feature
- explicit keyword match
- ontology term hit count
- matched measure/entity count
- time expression presence
- comparison markers (`vs`, `대비`, `비교`)
- aggregation markers (`합계`, `평균`, `추이`)
- governance markers (`정의`, `품질`, `소유자`, `라인리지`)
- question length
- previous turn intent (선택)
- LLM mini-classifier score (선택)

### 9.2 판정 구조
1. explicit deterministic rules 우선
2. rule score가 약하면 logistic/lightweight classifier 적용
3. tie 또는 ambiguity 시 mini-LLM re-ranker 사용 가능
4. 최종 top-3 intent와 confidence distribution 생성

### 9.3 confidence 산식 예시

```text
confidence =
  0.35 * explicit_rule_score +
  0.25 * ontology_match_score +
  0.20 * semantic_candidate_consistency +
  0.10 * classifier_probability +
  0.10 * conversation_context_alignment
```

### 9.4 ambiguity score 예시

```text
ambiguity =
  1 - (top1_confidence - top2_confidence) * candidate_coherence_factor
```

### 9.5 정책 임계치
- confidence >= 0.80: trusted intent
- 0.60 <= confidence < 0.80: guarded intent
- 0.40 <= confidence < 0.60: narrow-context fallback
- confidence < 0.40: unknown / clarification / block

---

## 10. Ontology Synonym Expansion 규칙 체계

### 10.1 rule type
- `EXACT`
- `NORMALIZED_EXACT`
- `TOKEN_SET`
- `REGEX`
- `TIME_ALIAS`
- `ACRONYM`
- `TRANSLITERATION`
- `ABBREVIATION`
- `NEGATIVE_RULE` (금지/오해 방지)

### 10.2 예시

#### 활성 고객
- 활성 고객
- active customer
- 유효 고객
- 최근 활동 고객
- 지난 30일 활동 회원

#### 거래액
- gmv
- 거래액
- 총 거래 금액
- gross merchandise value

#### 지난달
- 전월
- 지난달
- previous month
- last month

### 10.3 negative rule 예시
- “수익”을 무조건 revenue로 매핑하지 않음
- 특정 도메인에서는 “고객”이 `account` 가 아니라 `insured_party` 일 수 있음

### 10.4 expansion 결과 구조

```json
{
  "phrase": "지난달 활성 고객",
  "matches": [
    {
      "term": "활성 고객",
      "concept_id": "concept_customer_active",
      "evidence": ["NORMALIZED_EXACT", "TOKEN_SET"],
      "score": 0.91
    },
    {
      "term": "지난달",
      "concept_id": "concept_time_last_month",
      "evidence": ["TIME_ALIAS"],
      "score": 0.97
    }
  ],
  "rejected": [
    {
      "term": "고객",
      "reason": "too_generic_lower_priority"
    }
  ]
}
```

---

## 11. Semantic Request Envelope 설계

Sprint 4 이후 Oracle의 핵심 입력 구조를 아래처럼 바꾼다.

```json
{
  "request_id": "req-20260323-001",
  "snapshot_version": "semrel-2026.03.23-15",
  "raw_question": "지난달 활성 고객 수를 채널별로 보여줘",
  "normalized_question": "relative_time:last_month active_customer count by channel",
  "intent": {
    "top1": "SLICE_AND_DICE",
    "confidence": 0.86,
    "topk": [
      {"intent": "SLICE_AND_DICE", "score": 0.86},
      {"intent": "TREND_ANALYSIS", "score": 0.21}
    ],
    "ambiguity_score": 0.12
  },
  "semantic_candidates": {
    "concepts": ["concept_customer_active", "concept_time_last_month", "concept_channel"],
    "measures": ["measure_active_customer_count"],
    "dimensions": ["dimension_channel"],
    "domains": ["customer"]
  },
  "applied_rules": ["TIME_ALIAS:last_month", "TERM:active_customer"],
  "fallback_mode": "NONE",
  "policy_mode": "TRUSTED_CONTEXT"
}
```

이 envelope는 PromptBuilder, Validator, QualityPolicy, AuditLog가 공통으로 사용한다.

---

## 12. Synapse API 설계

### 12.1 질문 해석용 snapshot 조회 API
`GET /api/synapse/runtime/snapshots/{version}/question-understanding`

응답:
- ontology term dictionary
- alias group
- expansion rules
- intent model config
- deprecated/blocked term set
- domain boundary hints
- context pack routing map

### 12.2 질문 해석 진단 API
`POST /api/synapse/runtime/question/diagnose`

용도:
- 운영자가 특정 질문이 어떻게 해석되는지 확인
- Canvas의 디버그/품질 개선 화면에서 사용

요청 예시:
```json
{
  "tenantId": "...",
  "snapshotVersion": "semrel-2026.03.23-15",
  "question": "지난달 회원 실적 보여줘"
}
```

응답 예시:
```json
{
  "normalizedQuestion": "relative_time:last_month member performance show",
  "intent": {"top1": "METRIC_LOOKUP", "confidence": 0.58},
  "matches": [...],
  "ambiguities": [...],
  "recommendedFallback": "SAFE_NARROW_CONTEXT"
}
```

### 12.3 feedback 등록 API
`POST /api/synapse/runtime/question-feedback`

용도:
- 오분류, 누락 synonym, 잘못된 canonical mapping 신고

### 12.4 alias rule CRUD API
- `POST /api/synapse/ontology/alias-groups`
- `POST /api/synapse/ontology/expansion-rules`
- `PATCH /api/synapse/ontology/expansion-rules/{id}`
- `POST /api/synapse/ontology/expansion-rules/{id}/activate`
- `POST /api/synapse/ontology/expansion-rules/{id}/deprecate`

---

## 13. Oracle API / 내부 DTO 설계

### 13.1 `QuestionUnderstandingResult`

```python
@dataclass
class QuestionUnderstandingResult:
    request_id: str
    snapshot_version: str
    raw_question: str
    normalized_question: str
    top_intent: str
    confidence: float
    ambiguity_score: float
    fallback_mode: str
    matched_concepts: list[str]
    matched_measures: list[str]
    matched_dimensions: list[str]
    applied_rules: list[str]
    rejected_candidates: list[dict]
    diagnostics: dict
```

### 13.2 `IntentDecision`

```python
@dataclass
class IntentDecision:
    top1: str
    topk: list[dict]
    confidence: float
    ambiguity_score: float
    model_version: str
    rule_hits: list[str]
```

### 13.3 `FallbackDecision`

```python
@dataclass
class FallbackDecision:
    mode: str
    reason_code: str
    safe_context_pack_ids: list[str]
    allow_generation: bool
    response_tone: str
```

---

## 14. Fallback / Safety Policy 설계

Sprint 4는 질문 이해 실패를 “조용히 무시”하지 않는다. 명시적으로 다룬다.

### 14.1 fallback mode 정의

#### `NONE`
- high confidence
- ambiguity 낮음
- 안전한 semantic candidate 확보

#### `SAFE_NARROW_CONTEXT`
- confidence가 애매함
- top domain은 추정 가능
- 관련 context pack만 최소 범위로 주입
- broad cross-domain join 힌트 제거

#### `REFERENCE_ONLY`
- 개념은 일부 알겠지만 실행성 있는 measure/dimension 해석이 부족
- 정의/설명 중심 응답으로 강등

#### `ASK_FOR_CLARIFICATION`
- UI가 지원하면 선택
- “회원”이 사용자/고객/보험계약자 중 무엇인지 확인

#### `BLOCK_AND_EXPLAIN`
- 금지 용어, 미승인 도메인, 위험 ambiguity
- 생성 자체 차단

### 14.2 routing 기준
- confidence < 0.40 → `REFERENCE_ONLY` or `BLOCK_AND_EXPLAIN`
- ambiguity > 0.60 → `SAFE_NARROW_CONTEXT` or `ASK_FOR_CLARIFICATION`
- blocked term hit → `BLOCK_AND_EXPLAIN`
- deprecated term hit → 허용 가능하나 warning metadata 첨부

---

## 15. Canvas 운영 UI 설계

Sprint 4에서 Canvas에는 최소 3개 화면이 추가되어야 한다.

### 15.1 Question Interpretation Inspector
표시 항목:
- 원문 질문
- normalized question
- matched terms
- canonical concept
- selected intent/confidence
- rejected candidate
- fallback mode
- snapshot version

### 15.2 Alias Rule Workbench
기능:
- alias group 생성/수정
- expansion rule 우선순위 조정
- deprecated term 관리
- negative rule 등록
- 테스트 질문으로 즉시 시뮬레이션

### 15.3 Intent Quality Dashboard
지표:
- top intents volume
- low-confidence rate
- fallback mode 분포
- unresolved synonym rate
- 운영자 feedback 처리율

---

## 16. 이벤트 설계

### 16.1 발행 이벤트
- `ontology.term.alias_group.created`
- `ontology.term.expansion_rule.activated`
- `ontology.term.expansion_rule.deprecated`
- `semantic.intent_model.updated`
- `oracle.question_understanding.logged`
- `oracle.question_understanding.feedback_created`

### 16.2 소비 목적
- Oracle cache invalidation
- Canvas 대시보드 갱신
- 분석용 피처 저장
- drift 모니터링

---

## 17. 로그/관측성 설계

### 17.1 반드시 남겨야 할 로그
- request_id
- snapshot_version
- raw_question
- normalized_question
- matched_term_count
- top_intent
- confidence
- ambiguity_score
- fallback_mode
- allowed_generation
- post-generation validation result id 연결

### 17.2 핵심 운영 지표
- synonym hit rate
- canonical concept resolution rate
- low-confidence rate
- ambiguity rate
- fallback invocation rate
- feedback-to-fix lead time
- deprecated term usage count

### 17.3 알람
- low-confidence rate 급증
- unresolved term rate 급증
- 특정 도메인 alias match failure 급증
- intent drift by model version

---

## 18. 구현 순서 (4주 기준)

### Week 1 — 데이터/사전/규칙 기반 구축
목표:
- alias group / expansion rule 스키마 추가
- Synapse snapshot에 question understanding dictionary 포함
- Oracle normalizer / expander 기본 구현

산출물:
- DB migration
- `QuestionNormalizer`
- `OntologySynonymExpander`
- seed rules (핵심 30~50개)

### Week 2 — semantic candidate / intent confidence 구현
목표:
- candidate resolver 구현
- hybrid intent classifier 구현
- confidence / ambiguity scoring 도입

산출물:
- `SemanticCandidateResolver`
- `IntentClassifier`
- `IntentDecision`
- rule-based + lightweight model 결합

### Week 3 — fallback / prompt integration / Canvas 진단 화면
목표:
- fallback router 구현
- semantic request envelope 적용
- Canvas inspector 화면 구현

산출물:
- `AmbiguityRouter`
- `SemanticContextSelector`
- Canvas Question Interpretation Inspector
- Oracle prompt builder integration

### Week 4 — feedback loop / observability / hardening
목표:
- feedback API 및 운영 대시보드 추가
- 성능 최적화
- 회귀 테스트 및 drift monitor 추가

산출물:
- `semantic_question_feedback`
- Intent Quality Dashboard
- metrics/alerts
- 운영 가이드

---

## 19. 테스트 전략

### 19.1 단위 테스트
- normalization 케이스 40개 이상
- synonym expansion rule 테스트 60개 이상
- deprecated/blocked term 테스트 15개 이상
- intent confidence 판정 테스트 30개 이상
- fallback decision 테스트 20개 이상

### 19.2 통합 테스트
- question → envelope → prompt builder 전체 흐름
- snapshot version pinning 연동
- low confidence 시 safe_narrow_context 진입 여부
- blocked term hit 시 generation 차단 여부

### 19.3 회귀 테스트 데이터셋
도메인별 golden set 구축:
- customer
- sales
- insurance
- operations
- governance

각 세트에 다음 포함:
- 정상 synonym
- 중의적 질문
- deprecated term 질문
- 금지 표현
- time alias 혼합 질문

### 19.4 오프라인 품질 기준
- top1 intent accuracy
- top3 recall
- concept resolution precision
- ambiguous question safe routing precision
- false clarification rate

---

## 20. 위험과 대응책

### 20.1 synonym rule 과적합 위험
문제:
- 특정 현업 표현에만 맞춘 규칙이 전체 정확도를 떨어뜨릴 수 있음

대응:
- domain namespace 분리
- negative rule 지원
- golden set 회귀 테스트 필수화

### 20.2 LLM mini-classifier 도입 시 지연 증가 위험
대응:
- rule/feature 기반 1차 판정 우선
- mini-classifier는 tie-breaker로 제한
- timeout 시 deterministic fallback

### 20.3 alias 스파게티화 위험
대응:
- alias group 구조 사용
- canonical owner 지정
- deprecated lifecycle 강제

### 20.4 너무 많은 clarification 유도 위험
대응:
- UI 지원 전까지 `SAFE_NARROW_CONTEXT` 우선
- confidence/ambiguity threshold 운영 튜닝

### 20.5 운영자가 이유를 모르는 자동 해석 위험
대응:
- Canvas Inspector와 diagnostics를 기본 제공
- explainability metadata를 로그/응답에 항상 포함

---

## 21. 완료 후 기대 효과

Sprint 4가 끝나면 기대 효과는 명확하다.

### 21.1 Oracle 질문 이해 품질 상승
같은 semantic contract를 가지고도, 질문 해석이 좋아지면 prompt 품질과 SQL 품질이 동시에 올라간다.

### 21.2 불필요한 broad context 주입 감소
무작정 많은 계약을 주입하는 대신, 좁고 맞는 context를 선택하게 된다.

### 21.3 synonym drift를 운영적으로 관리 가능
도메인 용어 변화가 runtime에 반영되는 체계가 생긴다.

### 21.4 low-confidence 상황에서 더 안전한 응답
질문 해석이 불확실할 때 무리하게 생성하지 않고, reference-only 또는 narrow-context로 전환할 수 있다.

### 21.5 향후 도메인 연합과 ML 통합의 기반 확보
feedback, inference log, intent model registry가 생기면 이후 Sprint 5/6에서 federated governance와 ML feature integration으로 확장하기 쉬워진다.

---

## 22. Sprint 4 최종 판정 기준

다음 질문에 모두 “예”라고 답할 수 있어야 Sprint 4를 완료로 본다.

1. Oracle은 ontology synonym을 실제 질문 확장에 사용하고 있는가?
2. intent는 confidence와 ambiguity score를 함께 반환하는가?
3. low-confidence 질문은 안전한 fallback 경로를 타는가?
4. ContextPack 선택은 question understanding 결과에 의해 좁혀지는가?
5. 운영자는 Canvas에서 왜 그렇게 해석되었는지 볼 수 있는가?
6. synonym/intent drift를 로그와 피드백으로 개선할 수 있는가?

이 6개가 닫히면 Sprint 4는 단순 편의 기능이 아니라, **Ontology-driven Semantic Layer의 질문 이해 runtime** 을 완성하는 단계가 된다.

---

## 23. 다음 Sprint와의 연결

Sprint 4가 끝난 뒤에는 다음 두 방향으로 자연스럽게 이어진다.

### 23.1 Sprint 5 — 도메인 연합 확장
- domain namespace 정책
- domain steward 승인 워크플로
- alias ownership / approval delegation
- federated release governance

### 23.2 Sprint 6 — ML / Feature 통합
- question understanding logs를 학습 피처로 사용
- intent/confidence calibration
- feedback 기반 semi-supervised tuning
- semantic routing feature store 연계

즉 Sprint 4는 단순 NLP 개선이 아니라, **질문 → 의미 해석 → 안전한 실행 → 피드백 학습** 으로 이어지는 전체 semantic runtime의 전처리 계층을 완성하는 핵심 단계다.
