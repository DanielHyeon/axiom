# 온톨로지-시멘틱 레이어 통합 의미론적 계층 구현 계획서

## 1. 문서 목적

이 계획서는 첨부 문서가 강조한 다섯 가지 핵심 축,

1. 지표 정의와 계산 로직의 중앙화
2. API 기반 단일 진실 공급
3. Metrics as Code 방식의 형상관리
4. 데이터 품질 점수 기반 신뢰 확보
5. 도메인 연합 구조와 ML/AI 컨텍스트 연결

을 실제 구현 가능한 아키텍처와 운영 절차로 내리는 데 목적이 있다.

핵심 결론은 단순하다. **온톨로지는 의미를 정의하는 층**이고, **시멘틱 레이어는 그 의미를 실행 가능한 계약과 API로 바꾸는 층**이다. 따라서 둘은 분리해서 생각하면 안 되고, 다음과 같은 상하 결합 구조로 설계해야 한다.

- 온톨로지: 개념, 용어, 동의어, 관계, 제약, 정책, 시간 의미, 단위, 책임 주체 정의
- 시멘틱 레이어: 엔터티, 측정값, 차원, 그레인, 조인 규칙, 계산식, 품질, 버전, 제공 API 정의
- AI 컨텍스트 레이어: 온톨로지 + 시멘틱 메타데이터 + 품질 + 정책을 LLM/에이전트용 문맥으로 패키징

---

## 2. 첨부 문서로부터 끌어온 설계 원칙

첨부 문서는 시멘틱 레이어를 단순 BI 보조 기능이 아니라, 비즈니스 로직을 중앙 서버로 끌어올리고 모든 시스템이 API로 재사용하는 핵심 인프라로 봐야 한다고 설명한다. 또 “한 번 정의하고 어디서나 사용”하기 위해 지표를 코드로 선언하고, 코드 리뷰와 승인 절차를 거쳐 관리해야 한다고 강조한다. 더 나아가 지표 품질 점수, 도메인별 연합 구조, ML 피처 재사용, LLM용 컨텍스트 제공까지 확장해야 한다는 흐름을 제시한다. fileciteturn3file3 fileciteturn3file2 fileciteturn1file1 fileciteturn1file0 fileciteturn3file4

이 문서의 메시지를 구현 관점으로 번역하면 다음과 같다.

- 원시 스키마 중심이 아니라 **의미 중심 모델**을 먼저 고정해야 한다.
- 의미는 문서로만 두면 무너진다. **실행 가능한 계약**으로 내려야 한다.
- 중앙집중만 하면 병목이 된다. **표준은 중앙, 정의는 도메인 분산**이 맞다.
- AI는 raw schema를 보면 실패한다. **온톨로지 + 시멘틱 메타데이터 + 품질 + 정책**을 함께 봐야 한다.

---

## 3. 목표 상태 아키텍처

## 3.1 목표 문장

“기업의 비즈니스 의미를 온톨로지 그래프로 정의하고, 이를 시멘틱 계약으로 컴파일하여, BI/앱/ML/LLM이 동일한 의미 체계와 동일한 계산 로직을 API로 소비하도록 만든다.”

## 3.2 6계층 의미론적 계층 구조

### L0. Physical Data Layer
- 원천 DB, CDC, 로그, 이벤트, 외부 API, 파일
- 테이블/컬럼/파티션/스키마/배치 스케줄
- 이 층은 의미를 설명하지 않는다. 저장과 수집만 담당한다.

### L1. Canonical Data Product Layer
- 정제된 사실 테이블, 차원 테이블, 데이터 마트, 피처 소스
- SCD, snapshot, time spine, surrogate key 정리
- BI/ML 공통으로 쓸 수 있는 안정화된 물리적 기반

### L2. Semantic Contract Layer
- semantic_entity
- semantic_measure
- semantic_dimension
- semantic_segment
- join_contract
- grain_contract
- time_contract
- access_policy
- quality_contract

이 층이 “실행 가능한 시멘틱 레이어”다.

### L3. Ontology Layer
- 비즈니스 개념(고객, 주문, 계약, 활성 사용자, 실효 계약, 만기 갱신율)
- 상하위 분류(is-a)
- 관계(part-of, owned-by, affects, derived-from, equivalent-to)
- 동의어/약어/용어 충돌 해소
- 업무 규칙(예: 활성 고객은 최근 90일 이내 거래가 있는 고객)
- 시간/단위/관점 규칙(주문일 기준인지 결제일 기준인지, 금액 통화 기준 등)

### L4. Reasoning & Governance Layer
- 의미 충돌 탐지
- 조인 위험 탐지
- metric drift 탐지
- 정책 위반 탐지
- 변경 영향도 분석
- 승인 워크플로우

### L5. AI Context Layer
- LLM prompt context pack
- SQL generation guardrail
- entity/metric retrieval
- synonym expansion
- join rule constraint
- quality-aware answer synthesis

---

## 4. 왜 온톨로지와 시멘틱 레이어를 분리하되 결합해야 하는가

온톨로지만 있으면 실행이 안 된다. “고객”이 무엇인지 정의돼도 어떤 테이블에서 어떤 필드로 계산할지 연결되지 않는다. 반대로 시멘틱 레이어만 있으면 계산은 되지만 의미 충돌을 설명하지 못한다. 예를 들어 고객, 회원, 사용자, 계정, 가입자 같은 말이 부서마다 다르게 쓰이면 지표는 정의돼 있어도 조직은 계속 싸운다.

따라서 구조는 아래가 맞다.

- 온톨로지 = 의미의 원천
- 시멘틱 레이어 = 계산의 표준 실행체
- AI 컨텍스트 = 의미 + 계산 + 품질 + 정책의 조합 산출물

즉, **온톨로지가 시멘틱 레이어를 지배하고, 시멘틱 레이어가 애플리케이션/AI를 지배하는 구조**가 되어야 한다.

---

## 5. 핵심 메타모델 설계

## 5.1 온톨로지 메타모델

### OntologyConcept
- concept_id
- domain_id
- name_ko
- name_en
- description
- business_definition
- status(draft, review, approved, deprecated)
- owner_team
- steward_user
- sensitivity_level
- default_time_semantics
- default_unit
- created_at, updated_at, version

### OntologyTerm
- term_id
- concept_id
- surface_form
- language
- term_type(primary, synonym, alias, abbreviation, legacy)
- confidence

### OntologyRelation
- relation_id
- subject_concept_id
- predicate_type(is_a, part_of, relates_to, derives_from, equivalent_to, owned_by, constrained_by)
- object_concept_id
- cardinality
- directionality
- effective_from, effective_to

### OntologyRule
- rule_id
- concept_id
- rule_type(definition, eligibility, exclusion, time_window, policy)
- rule_expression
- expression_lang(sql, jsonlogic, python, dsl)
- severity

### OntologyPolicy
- policy_id
- concept_id
- policy_type(access, pii, retention, residency, aggregation)
- policy_expression

## 5.2 시멘틱 레이어 메타모델

### SemanticEntity
- entity_id
- bound_concept_id
- physical_source_ref
- entity_type(fact, dimension, bridge, aggregate, feature_source)
- grain_definition
- primary_key_spec
- surrogate_key_spec
- default_filters
- freshness_sla

### SemanticMeasure
- measure_id
- bound_concept_id
- entity_id
- name
- description
- measure_type(sum, count, distinct_count, ratio, rate, avg, percentile, derived)
- sql_expression
- filter_expression
- numerator_measure_id
- denominator_measure_id
- additive_type(additive, semi_additive, non_additive)
- default_aggregation_window
- owner_team
- lifecycle_state

### SemanticDimension
- dimension_id
- bound_concept_id
- entity_id
- name
- sql_expression
- value_type
- hierarchy_path
- conformed_dimension_group
- null_handling_rule

### JoinContract
- join_id
- left_entity_id
- right_entity_id
- join_type
- join_condition
- relationship_type(1:1, 1:N, N:1, N:N)
- allowed_for_ai
- fanout_risk_score
- bridge_strategy

### GrainContract
- grain_id
- entity_id
- grain_key_set
- time_grain
- uniqueness_test
- duplicate_resolution_rule

### QualityContract
- quality_contract_id
- target_type(entity, measure, dimension)
- target_id
- freshness_sla_minutes
- completeness_threshold
- uniqueness_threshold
- referential_integrity_threshold
- owner_presence_required
- lineage_required

### SemanticRelease
- release_id
- semantic_object_type
- semantic_object_id
- version
- git_commit_sha
- review_status
- reviewer
- deployed_at

## 5.3 AI 컨텍스트 메타모델

### ContextPack
- context_pack_id
- domain_id
- intent_type(kpi_query, root_cause, trend, comparison, forecast_support, narrative)
- included_concepts
- included_measures
- included_dimensions
- allowed_joins
- banned_joins
- synonym_map
- temporal_rules
- answer_guardrails
- quality_gate_policy

### PromptPolicy
- prompt_policy_id
- context_pack_id
- rule_type(must_use_metric, must_cite_quality, must_avoid_raw_table, must_confirm_timegrain)
- rule_text

---

## 6. 저장소 및 기술 스택 권장안

## 6.1 저장소 이원화

### A. 그래프 저장소
온톨로지와 의미 관계는 그래프가 적합하다.
- Neo4j 또는 RDF triplestore
- 사용 목적: 개념 관계 탐색, 동의어 해석, 영향도 분석, AI 컨텍스트 추출

### B. 관계형 메타스토어
시멘틱 계약과 배포 상태는 관계형이 적합하다.
- PostgreSQL
- 사용 목적: 계약 버전, 배포 상태, 품질 점수, API 서빙 인덱스

### C. Git 리포지토리
Metrics as Code / Semantics as Code 저장
- YAML + SQL + tests + policy files
- PR 리뷰, 변경 이력, 승인

## 6.2 실행 엔진
- dbt 또는 SQL compiler: 물리 SQL 생성
- FastAPI/Spring Boot: semantic query API
- Redis: metadata cache / query plan cache
- OpenLineage + Marquez or custom lineage store
- Great Expectations or custom quality runner
- Vector store(optional): AI 검색용 context embedding

---

## 7. 권장 리포지토리 구조

```text
semantic-platform/
  ontology/
    domains/
      sales/
        concepts.yaml
        relations.yaml
        terms.yaml
        rules.yaml
      customer/
      finance/
  semantic/
    entities/
    measures/
    dimensions/
    joins/
    policies/
    quality/
  marts/
    dbt_models/
    snapshots/
    tests/
  ai/
    context_packs/
    prompt_policies/
    join_guardrails/
  schemas/
    ontology.schema.json
    semantic_measure.schema.json
  services/
    registry/
    compiler/
    query-api/
    quality-engine/
    context-service/
  docs/
    glossary/
    change_logs/
```

---

## 8. 예시 정의 방식

## 8.1 온톨로지 개념 예시

```yaml
concept_id: customer.active_customer
name_ko: 활성 고객
description: 최근 90일 이내 유효 거래가 있는 고객
owner_team: growth-analytics
default_time_semantics: transaction_date
default_unit: person
terms:
  - 활성고객
  - active customer
  - engaged customer
rules:
  - type: eligibility
    expression_lang: jsonlogic
    expression:
      and:
        - ">=": [{"var": "valid_transaction_count_90d"}, 1]
        - "==": [{"var": "customer_status"}, "ACTIVE"]
```

## 8.2 시멘틱 지표 예시

```yaml
measure_id: sales.monthly_active_customers
bound_concept_id: customer.active_customer
entity_id: mart_customer_activity_daily
measure_type: distinct_count
sql_expression: customer_id
filter_expression: valid_transaction_count_90d >= 1 and customer_status = 'ACTIVE'
additive_type: non_additive
owner_team: growth-analytics
quality_contract_id: qc.sales.monthly_active_customers
```

## 8.3 AI 컨텍스트 팩 예시

```yaml
context_pack_id: cp.exec.kpi.active_customer
intent_type: trend
included_concepts:
  - customer.active_customer
included_measures:
  - sales.monthly_active_customers
included_dimensions:
  - dim_calendar.month
  - dim_channel.channel_group
allowed_joins:
  - mart_customer_activity_daily -> dim_calendar
  - mart_customer_activity_daily -> dim_channel
banned_joins:
  - mart_customer_activity_daily -> raw_event_log
answer_guardrails:
  - 항상 transaction_date 기준으로 설명할 것
  - 데이터 품질 점수가 80 미만이면 경고를 먼저 제시할 것
```

---

## 9. 시스템 구성도

```text
[Source Systems]
   -> [Ingestion/CDC]
   -> [Warehouse/Lakehouse]
   -> [Canonical Data Products]
   -> [Semantic Compiler]
        <- [Ontology Graph]
        <- [Semantic Contracts in Git]
        <- [Policies]
        <- [Quality Contracts]
   -> [Semantic Registry/Postgres]
   -> [Query API / Metrics API / Feature API / Context API]
      -> BI Tools
      -> Operational Apps
      -> ML Feature Jobs
      -> LLM Agents / Text2SQL / Insight Copilot
```

---

## 10. 핵심 서비스 설계

## 10.1 Ontology Registry Service
역할:
- 개념 CRUD
- 용어 동의어 관리
- 관계 정의
- 영향도 조회
- 의미 충돌 탐지

주요 API:
- POST /ontology/concepts
- GET /ontology/concepts/{id}
- POST /ontology/relations
- GET /ontology/search?q=
- GET /ontology/impact/{conceptId}

## 10.2 Semantic Registry Service
역할:
- 엔터티/지표/차원 계약 등록
- 온톨로지 binding 검증
- 버전 관리
- publish/deprecate

주요 API:
- POST /semantic/entities
- POST /semantic/measures
- POST /semantic/dimensions
- POST /semantic/publish
- GET /semantic/catalog

## 10.3 Semantic Compiler
역할:
- YAML 계약을 검증
- ontology binding 확인
- join fanout 검사
- SQL 템플릿 생성
- query plan metadata 생성

출력물:
- executable SQL view/model
- registry rows
- lineage edges
- AI context fragments

## 10.4 Query API
역할:
- measure query 실행
- dimension slice 지원
- timegrain/group by/filter 처리
- quality score 동봉 응답

예시:
- POST /query/metrics
- POST /query/explain
- GET /query/catalog/measures/{id}

## 10.5 Quality Engine
역할:
- freshness/completeness/uniqueness/owner/lineage 검사
- metric quality score 계산
- score history 저장
- 경고 이벤트 발행

## 10.6 Context Service for AI
역할:
- 질의 의도 분류
- 관련 concept/measure retrieval
- synonym 확장
- join constraint 제공
- prompt context pack 생성

예시:
- POST /ai/context/resolve
- POST /ai/query/guard
- GET /ai/context/pack/{id}

---

## 11. 데이터 품질 점수 설계

첨부 문서가 말한 “신뢰가 없으면 거대한 수식 모음집”이라는 경고는 구현에서 품질 점수를 1급 객체로 만들어야 한다는 뜻이다. fileciteturn1file1

## 11.1 품질 점수 항목
- Freshness: SLA 내 적재 여부
- Completeness: null/missing 비율
- Validity: 도메인 값 적합성
- Uniqueness: grain 위반 여부
- Referential Integrity: FK/semantic relation 충족 여부
- Owner Coverage: steward 지정 여부
- Lineage Completeness: upstream/downstream 추적 가능 여부
- Test Coverage: semantic tests 존재 여부
- Incident Health: 최근 장애 횟수

## 11.2 점수 공식 예시

```text
quality_score =
  0.20 * freshness +
  0.15 * completeness +
  0.10 * validity +
  0.10 * uniqueness +
  0.10 * referential_integrity +
  0.10 * owner_coverage +
  0.10 * lineage_completeness +
  0.05 * test_coverage +
  0.10 * incident_health
```

## 11.3 서빙 원칙
- 모든 metric query 응답에 quality_score 포함
- score < 80이면 경고 배지
- score < 60이면 AI 답변에서 “참고용”으로 강등
- score < 40이면 자동 차단 또는 human review 강제

---

## 12. 도메인 연합 구조 설계

첨부 문서는 중앙집권만으로는 병목이 생기며, 도메인별 독립성과 공통 표준의 결합이 필요하다고 말한다. fileciteturn1file0

권장 구조는 아래와 같다.

### 중앙 플랫폼 팀이 책임질 것
- 메타모델 표준
- schema lint 규칙
- 배포 파이프라인
- 품질 엔진
- query API 공통 런타임
- 권한/감사/버전 표준
- ontology relation core taxonomy

### 각 도메인 팀이 책임질 것
- 도메인 개념 정의
- 도메인 지표/차원 정의
- 데이터 품질 임계치
- owner/steward 지정
- AI context pack 도메인 튜닝

### 절대 중앙화하지 말아야 할 것
- 모든 지표 정의 권한
- 도메인별 실험 지표 생성 속도
- 도메인 용어의 상세 의미 결정권

---

## 13. AI/LLM 연결 방식

첨부 문서는 AI가 raw 테이블/컬럼만 보고서는 실패하고, 동의어·품질·유효 기간·조인 규칙 같은 컨텍스트가 필요하다고 강조한다. fileciteturn3file4

이를 구현으로 바꾸면 LLM은 직접 DB를 보게 하면 안 된다. 다음 4단계로 제한한다.

### 1단계: 의도 해석
- KPI 조회
- 비교
- 원인 분석
- 세그먼트 분석
- 예외/이상 탐지

### 2단계: 의미 해석
- 사용자 발화에서 ontology concept 검색
- synonym/alias 정규화
- metric 후보 추출

### 3단계: 안전한 질의 계획 생성
- 허용 join만 사용
- 허용된 semantic entities만 사용
- time semantics 자동 결정
- 품질 점수/권한/민감도 검사

### 4단계: 응답 생성
- 결과 + 품질 경고 + 사용한 정의 + 시간 기준 + 해석 제한 포함

즉 LLM은 SQL 생성기가 아니라, **시멘틱 레이어 소비자**가 되어야 한다.

---

## 14. 권한/거버넌스 설계

### 역할
- Semantic Architect: 메타모델/플랫폼 총괄
- Ontology Steward: 개념/용어/정의 관리
- Domain Data Owner: 도메인 데이터 책임자
- Metric Maintainer: 지표 코드 유지보수
- AI Policy Owner: AI 가드레일/민감도 정책 관리
- Reviewer: PR 승인자

### 승인 흐름
1. Draft 생성
2. 자동 lint / test / quality simulation
3. ontology binding review
4. domain owner review
5. publish 승인
6. production deployment
7. release note 자동 생성

### 감사 항목
- 누가 정의를 바꿨는가
- 어떤 근거 문서/이슈를 참조했는가
- 어떤 downstream metric/AI answer에 영향이 있는가
- 품질 점수 변화는 얼마인가

---

## 15. 구현 로드맵

## Phase 0. 준비 진단 (2~3주)
목표:
- 현재 KPI 정의 문서, BI 수식, SQL 스프롤, 용어사전, 데이터마트 현황 파악

수행:
- 상위 30개 KPI inventory 수집
- 동의어/충돌 용어 목록 작성
- 부서별 다른 정의 발견
- raw-to-report lineage 샘플 수집

산출물:
- KPI 충돌 보고서
- 용어 충돌 맵
- 후보 ontology domain 목록
- quick win 대상 10개 지표

완료 기준:
- 동일 이름 다른 정의 지표 목록 확정
- 우선 구축 도메인 2개 선정

## Phase 1. 온톨로지 코어 구축 (3~5주)
목표:
- 개념, 용어, 관계, 규칙의 최소 코어 구축

수행:
- concept taxonomy 설계
- synonym dictionary 구축
- 시간 의미 사전 정의
- 민감도/정책 태그 설계
- 그래프 저장소 구축

산출물:
- ontology graph v1
- concept CRUD API
- relation explorer UI 초안

완료 기준:
- 핵심 개념 100개 정의
- synonym 300개 정규화
- 상위 30개 KPI가 ontology concept에 연결 가능

## Phase 2. 시멘틱 계약 및 compiler 구축 (4~6주)
목표:
- YAML 기반 Semantics as Code 정착

수행:
- semantic entity/measure/dimension 스키마 확정
- schema validator 구현
- ontology binding validator 구현
- SQL compile pipeline 구현
- Git PR 템플릿/CI 구축

산출물:
- semantic contract repo
- compiler v1
- semantic registry DB schema

완료 기준:
- 상위 20개 KPI가 코드로 선언되고 배포 가능
- PR 리뷰 기반 승인 파이프라인 동작

## Phase 3. Query API 및 카탈로그 구축 (3~4주)
목표:
- BI/앱/내부 서비스가 공통 API로 metric 조회

수행:
- metrics query API
- explain API
- semantic catalog UI
- dimension slicing, filter grammar
- caching 전략 적용

산출물:
- /query/metrics
- /semantic/catalog
- catalog search UI

완료 기준:
- 기존 대시보드 2개 이상이 raw SQL 대신 semantic API 사용

## Phase 4. 품질 엔진 및 신뢰 레이어 구축 (3~4주)
목표:
- metric/entity quality score 가동

수행:
- freshness/completeness tests
- owner coverage 검사
- lineage completeness 점검
- quality scoring job
- alert/event 발행

산출물:
- quality score table
- score dashboard
- alert webhook/slack integration

완료 기준:
- 모든 운영 KPI에 quality score 노출
- 저품질 지표 자동 경고 동작

## Phase 5. 도메인 연합 확장 (4~8주)
목표:
- 중앙 표준 + 도메인 자율 구조 정착

수행:
- domain namespace 정책
- domain approval workflow 분리
- conformed dimensions 정의
- shared ontology core 유지

산출물:
- sales, customer, finance 등 3~5개 도메인 온보딩
- domain steward 운영 가이드

완료 기준:
- 중앙 플랫폼 팀 승인 없이 도메인 내부 지표의 draft 생성 가능
- conformed dimensions 충돌률 감소

## Phase 6. ML/Feature 통합 (3~5주)
목표:
- BI와 ML이 같은 의미 체계를 공유

수행:
- feature source binding
- online/offline feature parity 규칙 설계
- feature registry 연계
- training dataset assembly API 제공

산출물:
- feature semantic contracts
- training query templates

완료 기준:
- 1개 모델 이상이 semantic feature API 사용
- BI metric와 ML feature 정의 불일치 이슈 감소

## Phase 7. LLM/AI Context 서비스 구축 (4~6주)
목표:
- LLM이 raw DB가 아니라 semantic context를 소비하도록 전환

수행:
- concept retrieval
- context pack builder
- join guardrail service
- answer provenance formatter
- quality-aware response policy

산출물:
- /ai/context/resolve
- /ai/query/guard
- context pack registry

완료 기준:
- Text2SQL/Insight Agent가 raw schema 직접 접근하지 않음
- hallucination rate, invalid join rate 유의미 감소

---

## 16. 데이터베이스 스키마 초안

```sql
create table ontology_concepts (
  concept_id varchar primary key,
  domain_id varchar not null,
  name_ko varchar not null,
  name_en varchar,
  description text,
  business_definition text,
  status varchar not null,
  owner_team varchar,
  steward_user varchar,
  sensitivity_level varchar,
  default_time_semantics varchar,
  default_unit varchar,
  version int not null,
  created_at timestamp not null,
  updated_at timestamp not null
);

create table ontology_terms (
  term_id bigserial primary key,
  concept_id varchar not null references ontology_concepts(concept_id),
  surface_form varchar not null,
  language varchar not null,
  term_type varchar not null,
  confidence numeric(5,2)
);

create table semantic_measures (
  measure_id varchar primary key,
  bound_concept_id varchar references ontology_concepts(concept_id),
  entity_id varchar not null,
  name varchar not null,
  description text,
  measure_type varchar not null,
  sql_expression text not null,
  filter_expression text,
  additive_type varchar,
  owner_team varchar,
  lifecycle_state varchar not null,
  current_version int not null,
  quality_contract_id varchar
);

create table semantic_quality_scores (
  target_type varchar not null,
  target_id varchar not null,
  score numeric(5,2) not null,
  freshness_score numeric(5,2),
  completeness_score numeric(5,2),
  uniqueness_score numeric(5,2),
  owner_score numeric(5,2),
  lineage_score numeric(5,2),
  calculated_at timestamp not null,
  primary key (target_type, target_id, calculated_at)
);
```

---

## 17. 이벤트 계약 초안

- OntologyConceptCreated
- OntologyConceptUpdated
- OntologyBindingValidated
- SemanticMeasurePublished
- SemanticMeasureDeprecated
- QualityScoreUpdated
- QualityThresholdBreached
- ContextPackGenerated
- SemanticReleaseDeployed

예시:

```json
{
  "eventType": "SemanticMeasurePublished",
  "measureId": "sales.monthly_active_customers",
  "version": 3,
  "boundConceptId": "customer.active_customer",
  "ownerTeam": "growth-analytics",
  "gitCommitSha": "abc123",
  "publishedAt": "2026-03-22T10:00:00Z"
}
```

---

## 18. 테스트 전략

### 정적 테스트
- schema validation
- ontology binding validation
- forbidden raw table reference 검출
- duplicate name / synonym collision 검출

### 의미 테스트
- grain uniqueness test
- semantic join cardinality test
- metric reconciliation test
- cross-dashboard consistency test

### 품질 테스트
- freshness
- completeness
- validity
- SLA breach simulation

### AI 테스트
- synonym interpretation accuracy
- invalid join prevention rate
- wrong metric selection rate
- answer provenance completeness

---

## 19. 운영 KPI

- semantic API 사용률
- raw SQL 직접 사용 비율 감소율
- KPI 정의 충돌 건수
- metric publish lead time
- quality score 평균/하위 10% 개선율
- invalid join 발생 건수
- AI hallucination metric rate
- BI/ML 정의 불일치 건수

---

## 20. 실패 패턴과 방지책

### 실패 패턴 1: 용어사전만 만들고 실행 계층이 없음
방지:
- 모든 approved concept는 최소 1개 semantic binding 필요

### 실패 패턴 2: 중앙팀만 모든 정의 권한 보유
방지:
- 플랫폼은 표준만, 도메인은 정의 책임

### 실패 패턴 3: 품질 점수가 없거나 화면에 안 보임
방지:
- query response에 quality 필수 포함

### 실패 패턴 4: AI가 raw schema를 우회 접근
방지:
- AI service account의 DB 권한 차단
- semantic query endpoint만 허용

### 실패 패턴 5: 온톨로지와 시멘틱 레이어가 따로 놈
방지:
- publish 시 ontology binding 필수
- deprecated concept 연결 객체 자동 경고

---

## 21. 최종 권고안

가장 좋은 설계는 **“Ontology-driven Semantic Layer”**다.

즉,

1. 온톨로지에서 비즈니스 개념과 관계를 먼저 정의하고,
2. 각 개념을 시멘틱 엔터티/지표/차원 계약에 바인딩하고,
3. 이 계약을 코드로 관리하며,
4. 품질 점수를 모든 객체에 부여하고,
5. 도메인별 연합 구조로 확장하고,
6. 마지막으로 LLM/AI는 raw DB가 아니라 context pack과 semantic API만 보게 하는 구조가 가장 바람직하다.

이 방식은 첨부 문서가 말한 “중앙화된 단일 진실”, “코드로 관리되는 지표”, “품질에 기반한 신뢰”, “도메인 연합”, “ML/AI 연결”을 한 번에 수용하는 유일하게 현실적인 구조다. fileciteturn3file3 fileciteturn3file2 fileciteturn1file1 fileciteturn1file0 fileciteturn3file4

핵심 한 줄로 요약하면,

**시멘틱 레이어는 계산의 표준이고, 온톨로지는 의미의 표준이며, AI는 이 둘이 결합된 문맥 위에서만 제대로 작동한다.**
