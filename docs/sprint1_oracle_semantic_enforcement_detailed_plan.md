# Sprint 1 상세 구현서
## Oracle Semantic Enforcement Runtime — Post-generation SQL 검증/차단 구현 계획

- 작성일: 2026-03-23
- 범위: Oracle 소비단의 시멘틱 계약 준수 사후 검증 폐루프 구축
- 상위 문서: `final_implementation_status_assessment_v2.md`
- 목표 상태: **정의 중심 Semantic Control Plane → 실행 강제형 Semantic Enforcement Runtime의 첫 단계 진입**

---

## 1. Sprint 1 목표

이번 스프린트의 목표는 단순합니다.

현재 Oracle은 Synapse의 시멘틱 계약과 ContextPack을 받아 LLM 프롬프트에 반영할 수는 있지만, **LLM이 최종적으로 생성한 SQL이 실제로 계약을 준수하는지 사후 검증하지 못합니다.** 이 상태에서는 시멘틱 계약이 권고 수준에 머무르며, 금지된 조인, 미승인 테이블, 잘못된 grain, 우회 필터가 실제 실행될 수 있습니다.

Sprint 1에서는 이를 끊어야 합니다.

즉 다음 4단계를 하나의 폐루프로 만듭니다.

1. Oracle이 질의 의도와 관련된 시멘틱 계약 스냅샷을 조회한다.
2. LLM이 SQL을 생성한다.
3. Oracle이 SQL AST를 파싱하여 계약 위반 여부를 사후 검증한다.
4. 위반 시 실행을 차단하고, 사용자와 개발자가 모두 이해할 수 있는 사유를 반환한다.

이번 스프린트가 끝나면 Oracle은 더 이상 “계약을 참고하는 NL2SQL”이 아니라, **“계약을 강제하는 NL2SQL 게이트웨이”**로 바뀌어야 합니다.

---

## 2. 이번 스프린트에서 반드시 닫아야 할 문제

### 2.1 금지 조인이 실행되는 문제
LLM이 fanout 위험이 높은 경로, 승인되지 않은 relationship, cross-domain 금지 경로를 써도 현재는 차단되지 않습니다.

### 2.2 미승인 테이블/뷰를 직접 참조하는 문제
ContextPack에 포함되지 않은 원시 테이블이나 관리되지 않는 뷰를 SQL이 직접 사용할 수 있습니다.

### 2.3 그레인 불일치 문제
일별 집계를 요구하는 계약인데 row-level fact와 dimension을 잘못 섞거나, 집계 단위가 다른 measure를 함께 사용해 결과가 왜곡될 수 있습니다.

### 2.4 Explainable rejection 부재
현재는 실패해도 왜 안 되는지 명확한 계약 근거를 주지 못해 사용자 경험과 운영성이 떨어집니다.

---

## 3. Sprint 1 비범위

이번 스프린트에서는 아래는 다루지 않습니다.

- 품질 점수 기반 응답 강등 정책 전체 구현
- 도메인 연합 승인 워크플로
- ML feature binding
- ontology synonym 기반 질문 확장
- semantic query runtime 전용 실행 엔진 전체
- SQL 자동 수정/자동 재작성 엔진

단, 다음 스프린트를 고려해 인터페이스는 미리 열어 둡니다.

---

## 4. 완료 기준

다음 항목이 모두 충족되면 Sprint 1 완료로 봅니다.

### 기능 완료 기준
- Oracle이 LLM 생성 SQL을 실행 전에 반드시 AST 기반으로 검증한다.
- 다음 4종 위반을 차단한다.
  - forbidden table/view reference
  - banned join path
  - grain mismatch
  - disallowed raw column / unmanaged identifier reference
- 위반 시 사용자용 메시지와 운영자용 상세 사유를 함께 반환한다.
- 정상 SQL은 semantic validation metadata와 함께 실행된다.
- 모든 검증 결과는 감사 로그/추적 이벤트로 남는다.

### 품질 완료 기준
- 정상/실패 분기 단위 테스트 30개 이상
- AST 파서 경계 케이스 테스트 15개 이상
- fanout/banned join 회귀 테스트 포함
- p95 검증 시간 150ms 이하
- false reject율 5% 이하를 목표로 초기 운영 시작

---

## 5. 목표 아키텍처

```text
User Question
   ↓
Oracle Intent Resolver
   ↓
Oracle Semantic Context Loader
   ↓
LLM SQL Generation
   ↓
Oracle Post-generation Semantic Validator
   ├─ SQL Parser / AST Builder
   ├─ Identifier Resolver
   ├─ Join Path Checker
   ├─ Grain Checker
   ├─ Policy Checker
   └─ Rejection Message Builder
   ↓
[PASS] Query Execute
[FAIL] Block + Explain
```

핵심은 **검증기가 실행 직전의 최종 게이트**가 되어야 한다는 점입니다.

---

## 6. 서비스 경계

### 6.1 Synapse 책임
Synapse는 여전히 정의의 원천입니다.

- SemanticEntity
- Measure
- Dimension
- JoinContract
- GrainContract
- QualityContract
- Release
- ContextPack
- PromptPolicy

그리고 Oracle이 검증에 필요한 **immutable semantic snapshot**을 조회할 수 있게 제공해야 합니다.

### 6.2 Oracle 책임
Oracle은 소비와 집행의 책임을 집니다.

- 질문 의도 분류
- ContextPack 선택
- LLM SQL 생성
- 사후 검증
- 실행 허용/차단
- explainable rejection 생성
- 검증 결과 관찰성/로그 기록

### 6.3 Weaver 책임
Sprint 1에서는 직접 관여 범위를 최소화합니다.

- 기존 품질 수집 유지
- 향후 semantic validation outcome을 품질 점수와 연결할 여지 확보

---

## 7. 핵심 설계 원칙

### 7.1 검증은 문자열 비교가 아니라 AST 기준으로 한다
정규식 기반 차단은 우회가 쉽고, alias/subquery/CTE를 제대로 처리하지 못합니다.

### 7.2 계약은 release snapshot 기준으로 고정한다
질의 중간에 계약이 바뀌어도 같은 요청에서는 같은 버전을 사용해야 합니다.

### 7.3 차단 사유는 계약 ID와 함께 설명 가능해야 한다
“실패”가 아니라 “왜 실패했는지, 어느 정책에 걸렸는지”를 제공해야 합니다.

### 7.4 Fail-closed를 기본으로 하되 운영 초기에는 정책별 예외를 둔다
고위험 항목은 즉시 차단, 저위험 항목은 경고 허용 등 점진 롤아웃이 필요합니다.

---

## 8. 데이터 계약 추가/보완

Sprint 1은 새 테이블을 많이 추가하지 않습니다. 다만 Oracle이 효율적으로 검증할 수 있도록 Synapse가 아래 snapshot 응답을 제공해야 합니다.

### 8.1 새 API 응답 모델: SemanticValidationSnapshot

```json
{
  "release_id": "rel_2026_03_23_sales_v12",
  "version": 12,
  "domain_id": "sales",
  "entities": [
    {
      "entity_key": "sales.order",
      "physical_targets": ["mart_sales.orders", "vw_orders_semantic"],
      "allowed_columns": ["order_id", "customer_id", "order_date", "amount"],
      "default_grain": "order"
    }
  ],
  "measures": [
    {
      "measure_key": "gross_revenue",
      "entity_key": "sales.order",
      "expression_template": "SUM(amount)",
      "grain_key": "order",
      "aggregation": "SUM"
    }
  ],
  "dimensions": [
    {
      "dimension_key": "order_date",
      "entity_key": "sales.order",
      "column_name": "order_date",
      "grain_key": "day"
    }
  ],
  "joins": [
    {
      "join_key": "order_to_customer",
      "left_entity": "sales.order",
      "right_entity": "sales.customer",
      "join_type": "many_to_one",
      "left_columns": ["customer_id"],
      "right_columns": ["customer_id"],
      "status": "approved",
      "fanout_risk": "low",
      "is_banned": false
    }
  ],
  "banned_paths": [
    ["sales.order", "finance.payment", "hr.employee"]
  ],
  "grain_rules": [
    {
      "rule_key": "daily_revenue_requires_day_grouping",
      "measure_key": "gross_revenue",
      "required_dimensions": ["order_date"],
      "forbidden_dimensions": ["customer_email"]
    }
  ],
  "policy": {
    "disallow_raw_tables": true,
    "disallow_unmanaged_columns": true,
    "disallow_select_star": true
  }
}
```

---

## 9. Oracle 내부 모듈 설계

## 9.1 패키지 구조 제안

```text
oracle/
  semantic/
    application/
      semantic_validation_service.py
      semantic_snapshot_service.py
      rejection_message_service.py
    domain/
      models.py
      rules.py
      violations.py
    infrastructure/
      synapse_client.py
      cache.py
      sql_parser.py
      ast_resolver.py
      query_fingerprint.py
    interfaces/
      dto.py
      api_models.py
    tests/
      test_validation_service.py
      test_join_checker.py
      test_grain_checker.py
      test_identifier_resolver.py
```

---

## 9.2 핵심 클래스 설계

### SemanticSnapshotService
역할:
- Synapse에서 release 기준 validation snapshot 조회
- Redis/local cache에서 snapshot 재사용
- 질의 시작 시 snapshot version pinning

주요 메서드:

```python
class SemanticSnapshotService:
    async def get_snapshot(
        self,
        domain_id: str,
        intent: str,
        release_id: str | None = None
    ) -> SemanticValidationSnapshot:
        ...
```

### SqlAstParser
역할:
- SQL 문자열을 AST로 변환
- dialect 차이를 최소화한 canonical AST 제공

주요 메서드:

```python
class SqlAstParser:
    def parse(self, sql: str) -> ParsedSqlAst:
        ...
```

권장 구현:
- Python이면 `sqlglot` 우선
- 복잡한 dialect가 많다면 Java 쪽에 이미 parser가 있으면 sidecar 또는 service wrapper 검토

### AstIdentifierResolver
역할:
- AST에서 실제 사용된 테이블, 뷰, 컬럼, alias, CTE, join path 추출
- subquery/CTE/alias를 physical reference로 정규화

```python
class AstIdentifierResolver:
    def resolve(self, ast: ParsedSqlAst) -> ResolvedQueryShape:
        ...
```

### SemanticPolicyChecker
역할:
- raw table 사용 금지
- unmanaged column 사용 금지
- select * 금지
- 허용되지 않은 function 사용 금지(선택)

### JoinPathChecker
역할:
- AST에서 도출한 join edge를 snapshot의 approved join과 비교
- banned join / unknown join / high fanout 금지

### GrainChecker
역할:
- measure와 dimension 조합이 계약 grain과 충돌하는지 검사
- aggregate와 group by 일관성 확인

### SemanticValidationService
역할:
- 전체 검증 오케스트레이션

```python
class SemanticValidationService:
    async def validate_sql(
        self,
        sql: str,
        snapshot: SemanticValidationSnapshot,
        request_context: ValidationRequestContext
    ) -> SemanticValidationResult:
        ...
```

### RejectionMessageService
역할:
- violation list를 사용자용/운영자용 메시지로 변환
- 계약 ID, 엔티티, 조인 경로, 허용 대안을 포함

---

## 10. 핵심 DTO

### 10.1 ValidationRequestContext

```python
@dataclass
class ValidationRequestContext:
    request_id: str
    user_id: str
    tenant_id: str
    domain_id: str
    intent: str
    release_id: str
    original_question: str
    llm_model: str
    generated_at: datetime
```

### 10.2 SemanticValidationResult

```python
@dataclass
class SemanticValidationResult:
    passed: bool
    release_id: str
    snapshot_version: int
    violations: list[SemanticViolation]
    warnings: list[SemanticWarning]
    resolved_entities: list[str]
    resolved_measures: list[str]
    resolved_dimensions: list[str]
    validation_latency_ms: int
    query_fingerprint: str
```

### 10.3 SemanticViolation

```python
@dataclass
class SemanticViolation:
    code: str
    severity: str
    rule_id: str | None
    message: str
    user_message: str
    evidence: dict
    suggested_fix: str | None
```

권장 violation code:
- `UNAPPROVED_TABLE_REFERENCE`
- `UNMANAGED_COLUMN_REFERENCE`
- `SELECT_STAR_DISALLOWED`
- `BANNED_JOIN_PATH`
- `UNKNOWN_JOIN_PATH`
- `HIGH_FANOUT_JOIN_BLOCKED`
- `GRAIN_MISMATCH`
- `MISSING_REQUIRED_DIMENSION`
- `FORBIDDEN_DIMENSION_FOR_MEASURE`

---

## 11. 검증 규칙 상세

## 11.1 Rule A — Unapproved Table Reference

### 목적
관리되지 않은 raw table, ad-hoc view, shadow table 사용 차단

### 검사 방식
- AST의 FROM/JOIN 대상 추출
- physical target을 snapshot.entities.physical_targets와 비교
- CTE alias는 실제 base relation로 resolve

### 차단 조건
- snapshot에 없는 physical relation 참조
- 관리 상태가 retired/inactive인 relation 참조

### 예시
허용:
```sql
SELECT SUM(amount)
FROM mart_sales.orders
```

차단:
```sql
SELECT SUM(amount)
FROM raw.orders_dump_202603
```

### user_message 예시
"승인되지 않은 원시 테이블 `raw.orders_dump_202603` 이 사용되어 실행할 수 없습니다. 승인된 시멘틱 엔터티 `sales.order` 를 통해 조회해 주세요."

---

## 11.2 Rule B — Banned Join Path

### 목적
금지된 cross-domain 조인과 fanout 위험 경로 차단

### 검사 방식
- AST join tree를 edge list로 추출
- 각 edge를 approved join set과 비교
- path 단위 banned_paths와도 비교

### 차단 조건
- `is_banned = true`
- approved join set에 없음
- fanout_risk = high 이고 policy상 block

### 예시
차단:
```sql
SELECT o.order_id, e.employee_name
FROM mart_sales.orders o
JOIN finance.payments p ON o.order_id = p.order_id
JOIN hr.employee e ON p.approver_id = e.employee_id
```

### 운영자 상세 메시지 예시
- path: `sales.order -> finance.payment -> hr.employee`
- reason: `BANNED_CROSS_DOMAIN_PATH`
- rule_id: `join_policy_2026_03_17_01`

---

## 11.3 Rule C — Grain Mismatch

### 목적
다른 grain의 데이터가 섞이면서 수치가 왜곡되는 문제 차단

### 검사 방식
- measure가 속한 entity/grain 식별
- select, aggregate, group by, dimension 컬럼 분석
- measure별 required/forbidden dimension 규칙 검사

### 차단 조건
- measure가 day grain을 요구하는데 group by에 day 계열이 없음
- order grain measure와 line_item grain dimension이 무제한 혼합
- distinct 없이 many-side join 이후 sum 수행

### 예시
차단:
```sql
SELECT customer_email, SUM(amount)
FROM mart_sales.orders o
JOIN mart_sales.order_items i ON o.order_id = i.order_id
GROUP BY customer_email
```

사유:
- `gross_revenue`는 order grain 측정치
- `order_items` join으로 many-side fanout 발생
- distinct protection 또는 approved aggregate bridge 없음

---

## 11.4 Rule D — Unmanaged Column / Select Star

### 목적
계약 바깥 컬럼 노출, 우발적 PII 노출, schema drift 영향 차단

### 검사 방식
- select list와 filter/order/group expressions에서 column 추출
- snapshot.allowed_columns와 비교
- `SELECT *` 직접 금지

### 차단 조건
- 허용 컬럼 목록 외의 참조
- wildcard projection

---

## 12. AST 처리 로직 상세

## 12.1 파싱 도구
권장: `sqlglot`

이유:
- Python 기반 Oracle 서비스에 붙이기 쉬움
- dialect 변환/AST 탐색이 안정적
- alias, CTE, subquery 순회가 비교적 수월

## 12.2 처리 순서

```text
SQL string
  → Parse
  → Normalize
  → Resolve CTE / alias
  → Extract relations
  → Extract join edges
  → Extract projected columns
  → Extract group/order/filter columns
  → Map to semantic entities
  → Validate rules
```

## 12.3 정규화 규칙
- identifier는 lower-case canonical form으로 정규화
- schema 미지정 시 default schema resolve
- quoted identifier는 quote 제거 후 canonical form 유지
- alias는 scope 단위로 매핑
- CTE는 base relation lineage 보존

---

## 13. Synapse API 추가/보완

## 13.1 GET /api/synapse/semantic/releases/{releaseId}/validation-snapshot

### 목적
Oracle이 검증에 필요한 immutable snapshot 조회

### 응답
- entities
- measures
- dimensions
- joins
- banned_paths
- grain_rules
- policy
- version/hash

## 13.2 POST /api/synapse/semantic/validate/simulate

### 목적
운영 전 테스트와 UI 시뮬레이션 지원

### 요청
```json
{
  "release_id": "rel_2026_03_23_sales_v12",
  "sql": "SELECT ..."
}
```

### 응답
```json
{
  "passed": false,
  "violations": [...],
  "warnings": [...]
}
```

이 엔드포인트는 Oracle runtime이 아니라, 카탈로그 UI와 QA 팀의 사전 검증용입니다.

---

## 14. Oracle API 변경

## 14.1 기존 chat/query 응답에 validation metadata 추가

### 성공 시 응답 예시
```json
{
  "status": "ok",
  "answer": "...",
  "sql": "SELECT ...",
  "semantic_validation": {
    "passed": true,
    "release_id": "rel_2026_03_23_sales_v12",
    "snapshot_version": 12,
    "warnings": [],
    "latency_ms": 82
  }
}
```

### 차단 시 응답 예시
```json
{
  "status": "blocked",
  "reason": "semantic_policy_violation",
  "message": "승인되지 않은 조인 경로가 포함되어 실행할 수 없습니다.",
  "semantic_validation": {
    "passed": false,
    "violations": [
      {
        "code": "BANNED_JOIN_PATH",
        "user_message": "주문과 직원 정보를 직접 연결하는 경로는 승인되지 않았습니다.",
        "suggested_fix": "승인된 고객 기준 집계 질의로 다시 요청해 주세요."
      }
    ]
  }
}
```

---

## 15. 예외 메시지 설계

## 15.1 사용자용 메시지 원칙
- 계약 용어 중심으로 설명
- raw 테이블명만 던지지 말고 승인된 개념명을 함께 제시
- 내부 정책 세부값을 과도하게 노출하지 않음
- 수정 방향을 한 줄로 안내

## 15.2 운영자용 메시지 원칙
- rule_id, entity, join path, offending identifiers, fingerprint 포함
- snapshot version 포함
- parser stage/resolve stage/validation stage 구분

## 15.3 메시지 템플릿 예시

### BANNED_JOIN_PATH
사용자용:
- "요청된 분석에 승인되지 않은 조인 경로가 포함되어 실행할 수 없습니다. 승인된 도메인 경로 안에서 다시 질문해 주세요."

운영자용:
- "Blocked by rule join_policy_2026_03_17_01. Path `sales.order -> finance.payment -> hr.employee` is banned under release `rel_2026_03_23_sales_v12`."

### GRAIN_MISMATCH
사용자용:
- "요청된 집계 단위와 사용된 상세 데이터의 단위가 맞지 않아 결과가 왜곡될 수 있으므로 실행하지 않았습니다."

운영자용:
- "Measure `gross_revenue` at grain `order` joined with relation `order_items` at grain `line_item` without approved bridge or deduplication pattern."

---

## 16. 실행 흐름 상세

## 16.1 요청 처리 순서

1. 사용자 질문 수신
2. 의도 분류
3. ContextPack / release 선택
4. Synapse snapshot 조회 및 request scope pinning
5. LLM SQL 생성
6. AST parse
7. identifier resolve
8. policy/join/grain validation
9. 실패 시 block 응답 반환
10. 성공 시 실행 + validation metadata 첨부
11. validation result event 기록

## 16.2 request scope version pinning
동일 요청 내에서는 snapshot version을 고정해야 합니다.

```python
request.semantic_release_id = snapshot.release_id
request.semantic_snapshot_version = snapshot.version
```

재시도나 후속 로깅도 이 버전을 기준으로 기록합니다.

---

## 17. 이벤트/관찰성 설계

## 17.1 신규 이벤트 타입

### semantic.validation.passed
```json
{
  "event_type": "semantic.validation.passed",
  "request_id": "req_123",
  "tenant_id": "t1",
  "domain_id": "sales",
  "release_id": "rel_2026_03_23_sales_v12",
  "snapshot_version": 12,
  "query_fingerprint": "...",
  "latency_ms": 82,
  "generated_sql_hash": "..."
}
```

### semantic.validation.blocked
```json
{
  "event_type": "semantic.validation.blocked",
  "request_id": "req_124",
  "tenant_id": "t1",
  "domain_id": "sales",
  "release_id": "rel_2026_03_23_sales_v12",
  "snapshot_version": 12,
  "violations": ["BANNED_JOIN_PATH", "UNMANAGED_COLUMN_REFERENCE"],
  "query_fingerprint": "...",
  "latency_ms": 95
}
```

## 17.2 대시보드 지표
- validation pass rate
- validation block rate
- top violation codes
- top blocked join paths
- false reject override count
- avg validation latency

---

## 18. Redis 캐시 최소 설계

Sprint 1의 주목표는 검증기지만, snapshot 조회 비용이 커질 수 있으므로 최소 캐시는 같이 넣는 것이 좋습니다.

### cache key
`semantic:snapshot:{tenant_id}:{domain_id}:{release_id}`

### cache value
- serialized snapshot
- version
- hash
- loaded_at

### TTL
- 기본 5분
- release 고정 질의는 longer TTL 가능

### 주의
정식 이벤트 기반 무효화는 다음 스프린트에서 강화하되, Sprint 1에서도 수동 invalidate endpoint 정도는 두는 것이 좋습니다.

---

## 19. 롤아웃 전략

## 19.1 단계 1 — Shadow Mode
- 검증은 수행하되 차단하지 않음
- violations를 로그와 메트릭으로만 수집
- false reject 패턴 식별

## 19.2 단계 2 — High-risk Block Only
즉시 차단 규칙:
- banned join
- unknown raw table
- select *
- unmanaged column referencing PII candidate

## 19.3 단계 3 — Full Enforcement
- grain mismatch 차단
- unknown join 차단
- policy severity별 block/warn 세분화

---

## 20. 테스트 전략

## 20.1 단위 테스트
대상:
- parser wrapper
- identifier resolver
- join checker
- grain checker
- rejection builder

예시 케이스:
- alias + join + subquery
- nested CTE
- select star
- same table self join
- line_item fanout
- approved one-to-many bridge exception

## 20.2 계약 기반 테스트
입력:
- validation snapshot fixture
- SQL fixture

출력:
- expected pass/fail
- expected violation code
- expected offending entity/path

## 20.3 회귀 테스트 세트
실제 과거 실패 패턴을 별도 corpus로 보관합니다.

권장 파일 구조:
```text
tests/fixtures/semantic_validation/
  approved/
  banned_join/
  grain_mismatch/
  raw_table/
  unmanaged_column/
```

## 20.4 성능 테스트
목표:
- 단일 SQL 검증 평균 50ms 이하
- p95 150ms 이하

측정 포인트:
- parse latency
- resolve latency
- rules latency
- total validation latency

---

## 21. 구현 순서

## Week 1
- Synapse validation snapshot API 정의
- Oracle DTO/models 추가
- sqlglot parser wrapper 도입
- identifier resolver 구현

## Week 2
- policy checker 구현
- join path checker 구현
- banned/unknown path 규칙 추가
- user/operator rejection builder 구현

## Week 3
- grain checker 구현
- Oracle 실행 플로우에 validation hook 연결
- shadow mode 로깅/이벤트 추가
- 단위 테스트/fixture 작성

## Week 4
- high-risk block 활성화
- Canvas QA 시뮬레이션 endpoint 연결
- 메트릭 대시보드 구성
- 운영 튜닝 및 false reject 예외 정리

---

## 22. 권장 코드 스켈레톤

```python
class SemanticValidationService:
    def __init__(
        self,
        parser: SqlAstParser,
        resolver: AstIdentifierResolver,
        policy_checker: SemanticPolicyChecker,
        join_checker: JoinPathChecker,
        grain_checker: GrainChecker,
        rejection_builder: RejectionMessageService,
    ):
        self.parser = parser
        self.resolver = resolver
        self.policy_checker = policy_checker
        self.join_checker = join_checker
        self.grain_checker = grain_checker
        self.rejection_builder = rejection_builder

    async def validate_sql(self, sql: str, snapshot, ctx) -> SemanticValidationResult:
        ast = self.parser.parse(sql)
        shape = self.resolver.resolve(ast)

        violations = []
        warnings = []

        violations.extend(self.policy_checker.check(shape, snapshot))
        violations.extend(self.join_checker.check(shape, snapshot))
        violations.extend(self.grain_checker.check(shape, snapshot))

        passed = len([v for v in violations if v.severity == "BLOCK"]) == 0

        return SemanticValidationResult(
            passed=passed,
            release_id=snapshot.release_id,
            snapshot_version=snapshot.version,
            violations=self.rejection_builder.build(violations),
            warnings=warnings,
            resolved_entities=shape.entities,
            resolved_measures=shape.measures,
            resolved_dimensions=shape.dimensions,
            validation_latency_ms=0,
            query_fingerprint=shape.fingerprint,
        )
```

---

## 23. 위험요소와 대응

## 23.1 False Reject 증가
원인:
- parser/alias resolve 불완전
- approved join 정의 누락

대응:
- shadow mode 선행
- violation override registry 임시 운영
- blocked SQL corpus 기반 회귀 개선

## 23.2 Snapshot 누락/불일치
원인:
- release 배포 후 Oracle 반영 지연

대응:
- request scope pinning
- snapshot hash 검증
- manual invalidate endpoint

## 23.3 복잡 SQL 파싱 실패
원인:
- dialect 특수 문법, vendor-specific function

대응:
- parser failure는 기본 block이 아니라 controlled degrade 정책 적용
- 파싱 실패 시 “검증 불가” reason 반환 후 safe-mode 차단 또는 재생성 요청

---

## 24. Sprint 1 산출물 목록

### 코드
- Oracle semantic validation module
- Synapse validation snapshot API
- validation event publishing
- Redis snapshot cache

### 테스트
- validator unit tests
- SQL fixture corpus
- shadow mode metrics dashboard

### 문서
- violation code catalog
- 운영 runbook
- false reject triage guide
- QA 시뮬레이션 가이드

---

## 25. Sprint 1 종료 후 기대 효과

이 스프린트가 끝나면 다음 변화가 생깁니다.

### 사용자 관점
- 잘못된 SQL이 조용히 실행되는 대신, 차단과 이유 설명을 받게 됩니다.
- AI 응답의 신뢰 경계가 분명해집니다.

### 플랫폼 관점
- 시멘틱 계약이 권고가 아니라 실행 정책으로 승격됩니다.
- banned join과 raw table 사용 같은 고위험 사고를 사전에 막을 수 있습니다.

### 아키텍처 관점
- Axiom은 단순 ontology registry나 semantic catalog를 넘어서, **실행 강제형 의미 계층의 첫 번째 완결 루프**를 갖게 됩니다.

---

## 26. 다음 스프린트 연결 포인트

Sprint 2는 아래를 바로 이어서 붙이면 됩니다.

- 품질 점수 기반 응답 강등/차단 정책
- snapshot 이벤트 무효화 자동화
- synonym expansion + intent confidence
- partial auto-rewrite suggestion

즉 Sprint 1은 “막을 수 있는가”를 증명하고, Sprint 2는 “얼마나 신뢰할 수 있는가”를 강화하는 단계입니다.

---

## 27. 최종 판단

지금 Axiom에서 가장 먼저 필요한 것은 시멘틱 정의를 더 많이 만드는 일이 아니라, **이미 만들어진 정의를 Oracle 실행 경로에서 실제로 강제하는 일**입니다.

따라서 Sprint 1의 최우선 구현 범위를

- Post-generation SQL AST 검증
- banned join / raw table / unmanaged column / grain mismatch 차단
- explainable rejection
- snapshot version pinning

으로 잡는 것은 타당하며, 이 순서가 현재 시스템을 가장 빠르게 “보여주는 시맨틱 레이어”에서 “실제로 통제하는 시맨틱 레이어”로 옮기는 경로입니다.
