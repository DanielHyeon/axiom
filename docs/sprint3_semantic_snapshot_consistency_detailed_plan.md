# Sprint 3 상세 구현서
## Semantic Snapshot Cache, Event-driven Invalidation, Version Pinning 구현 계획

- 작성일: 2026-03-23
- 대상 스프린트: Sprint 3
- 상위 문서:
  - Sprint 1 상세 구현서 — Oracle Semantic Enforcement
  - Sprint 2 상세 구현서 — Quality Trust Policy
- 대상 시스템:
  - Synapse (Ontology/Semantic Control Plane)
  - Oracle (NL2SQL/AI Consumer)
  - Weaver (품질 수집 및 일부 실행 지원)
  - Canvas (카탈로그/운영 UI)
- 목표 한 줄 요약:
  - **“의미 계약의 최신성”보다 “질문 단위의 일관성”을 우선 보장하는 semantic snapshot runtime을 구축한다.**

---

## 1. Sprint 3의 목표

Sprint 1이 계약 위반 차단을 만들고, Sprint 2가 품질 점수에 따른 응답 정책을 만들었다면, Sprint 3은 그 둘이 **항상 동일한 semantic context** 위에서 동작하도록 만드는 단계다.

현재 구조의 가장 큰 문제는 다음과 같다.

1. Oracle이 요청마다 Synapse를 조회하면 지연이 커지고 장애 전파가 발생한다.
2. 반대로 Oracle이 캐시를 쓰기 시작하면, 계약이 변경되어도 오래된 계약으로 질의가 생성될 수 있다.
3. 같은 사용자 질문 처리 중간에 release가 바뀌면, 생성 단계와 검증 단계가 서로 다른 버전을 사용할 위험이 있다.
4. Canvas, Oracle, Weaver가 각자 다른 시점의 semantic release를 보고 있으면 운영자가 시스템을 신뢰하기 어렵다.

따라서 Sprint 3의 핵심은 다음 4개다.

- **Semantic Snapshot Cache**: 소비자가 즉시 사용할 수 있는 사전 컴파일 snapshot 제공
- **Version Pinning**: 질문/세션/실행 단위로 semantic version 고정
- **Event-driven Invalidation**: release 변경 시 관련 snapshot만 정밀 무효화
- **Consistency Contract**: Oracle/Synapse/Canvas 간 semantic version 가시성 통일

---

## 2. 성공 기준

Sprint 3 완료 판정은 아래 기준을 만족해야 한다.

### 2.1 기능 기준
- Oracle이 Synapse live CRUD 응답에 직접 의존하지 않고 Redis snapshot cache를 우선 사용한다.
- 각 질의 요청은 단일 `semantic_snapshot_version`에 pinning 된다.
- 질의 생성, SQL 검증, 품질 정책 적용, 응답 포맷팅이 모두 동일 snapshot version을 사용한다.
- semantic release publish/rollback/archive 시 관련 snapshot invalidation event가 발행된다.
- Oracle은 event를 수신하여 cache를 정밀 무효화하거나 신규 snapshot prefetch를 수행한다.
- Canvas 운영 화면에서 현재 active release와 Oracle 적용 snapshot version을 확인할 수 있다.

### 2.2 비기능 기준
- Oracle 95p semantic context resolution latency: **150ms 이하**
- Redis cache hit ratio: **85% 이상**
- release publish 후 Oracle 반영 지연: **10초 이하**
- 동일 request 내부 version drift: **0건**
- 장애 시 fallback 규칙이 명확해야 하며, stale snapshot 사용 여부가 로그/응답 메타데이터에 드러나야 한다.

---

## 3. 핵심 아키텍처

```text
[Synapse Release Publish]
   └─ Semantic Compiler
      └─ Snapshot Builder
         ├─ PostgreSQL metadata
         ├─ Neo4j ontology bindings
         ├─ Quality aggregate refs
         └─ ContextPack materialization
              ↓
         [Snapshot Store]
         ├─ PostgreSQL (registry + manifest)
         └─ Redis (hot cache)
              ↓
         Transactional Outbox
              ↓
     semantic.snapshot.published
     semantic.snapshot.invalidated
     semantic.release.rolled_back
              ↓
          Event Bus / Poller
              ↓
            Oracle
         ├─ SnapshotResolver
         ├─ VersionPinManager
         ├─ QueryExecutionContext
         ├─ ContractEnforcer
         └─ TrustPolicyApplier
```

핵심 원칙은 다음과 같다.

1. **Release와 Snapshot을 분리**한다.
   - release는 사람/거버넌스 관점의 승인 단위
   - snapshot은 runtime 소비 단위
2. **Snapshot은 immutable**이어야 한다.
   - publish 이후 내용 변경 금지
3. **질문 처리 중에는 version 고정**이 절대 깨지면 안 된다.
4. **최신 버전 자동 추적보다, 안전한 명시적 전환**이 우선이다.

---

## 4. Sprint 3 범위

### 포함
- Synapse snapshot builder/registry
- Redis hot cache
- Oracle snapshot resolver
- request-level version pinning
- release change event 수신 및 cache invalidation
- stale snapshot fallback 정책
- observability/logging/metrics
- Canvas 운영 가시화 최소 기능

### 제외
- domain federation namespace 전면 확장
- ML feature snapshot binding
- 다중 지역(active-active) 캐시 복제
- 완전한 streaming change propagation 플랫폼

---

## 5. 데이터 모델 설계

## 5.1 Synapse PostgreSQL 테이블

### 5.1.1 semantic_snapshots
```sql
CREATE TABLE semantic_snapshots (
    id UUID PRIMARY KEY,
    snapshot_version VARCHAR(64) NOT NULL UNIQUE,
    release_id UUID NOT NULL,
    release_version VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL, -- BUILDING, READY, ACTIVE, SUPERSEDED, INVALIDATED
    manifest_json JSONB NOT NULL,
    content_hash VARCHAR(128) NOT NULL,
    ontology_hash VARCHAR(128) NOT NULL,
    quality_hash VARCHAR(128) NOT NULL,
    context_hash VARCHAR(128) NOT NULL,
    built_at TIMESTAMP NOT NULL,
    activated_at TIMESTAMP,
    invalidated_at TIMESTAMP,
    invalidation_reason VARCHAR(100),
    created_by VARCHAR(100) NOT NULL
);
```

### 5.1.2 semantic_snapshot_artifacts
```sql
CREATE TABLE semantic_snapshot_artifacts (
    id UUID PRIMARY KEY,
    snapshot_id UUID NOT NULL REFERENCES semantic_snapshots(id),
    artifact_type VARCHAR(50) NOT NULL, -- CONTRACT_INDEX, JOIN_GRAPH, CONTEXT_PACKS, TRUST_THRESHOLDS, SYNONYM_MAP
    artifact_key VARCHAR(200) NOT NULL,
    artifact_json JSONB NOT NULL,
    artifact_hash VARCHAR(128) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    UNIQUE(snapshot_id, artifact_type, artifact_key)
);
```

### 5.1.3 semantic_runtime_bindings
```sql
CREATE TABLE semantic_runtime_bindings (
    id UUID PRIMARY KEY,
    consumer_name VARCHAR(50) NOT NULL, -- ORACLE, CANVAS, WEAVER
    consumer_instance_id VARCHAR(100) NOT NULL,
    bound_snapshot_version VARCHAR(64) NOT NULL,
    bound_release_version VARCHAR(64) NOT NULL,
    binding_mode VARCHAR(20) NOT NULL, -- AUTO, PINNED, STICKY, FALLBACK
    last_seen_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    UNIQUE(consumer_name, consumer_instance_id)
);
```

### 5.1.4 semantic_snapshot_leases
```sql
CREATE TABLE semantic_snapshot_leases (
    id UUID PRIMARY KEY,
    request_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(100),
    consumer_name VARCHAR(50) NOT NULL,
    snapshot_version VARCHAR(64) NOT NULL,
    acquired_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    released_at TIMESTAMP,
    status VARCHAR(20) NOT NULL, -- ACTIVE, RELEASED, EXPIRED
    UNIQUE(request_id, consumer_name)
);
```

## 5.2 Redis 키 설계

### 5.2.1 Hot snapshot key
```text
semantic:snapshot:{snapshot_version}
```
값: 전체 runtime snapshot JSON 압축본
TTL: 기본 24시간, active snapshot은 갱신형 유지

### 5.2.2 Active pointer key
```text
semantic:active:{consumer_name}:{domain_scope}
```
예:
- `semantic:active:oracle:global`
- `semantic:active:oracle:sales`

값:
```json
{
  "snapshot_version": "ss_2026_03_23_001",
  "release_version": "r2026.03.23.1",
  "activated_at": "2026-03-23T11:20:00Z",
  "content_hash": "..."
}
```

### 5.2.3 Request pin key
```text
semantic:pin:{consumer_name}:{request_id}
```
TTL: 30분

### 5.2.4 Invalidation marker key
```text
semantic:invalidated:{snapshot_version}
```
TTL: 24시간

---

## 6. Snapshot 내용 구조

Oracle이 매 요청마다 여러 API를 합성하지 않도록 snapshot은 runtime 친화적으로 materialize 되어야 한다.

```json
{
  "snapshotVersion": "ss_2026_03_23_001",
  "releaseVersion": "r2026.03.23.1",
  "builtAt": "2026-03-23T11:20:00Z",
  "scope": {
    "domains": ["global", "sales", "finance"]
  },
  "contracts": {
    "entities": [...],
    "measures": [...],
    "dimensions": [...],
    "joins": [...],
    "grains": [...]
  },
  "ontology": {
    "conceptBindings": [...],
    "synonymMap": {...},
    "termExpansions": {...}
  },
  "quality": {
    "trustPolicies": [...],
    "entityScores": {...},
    "measureScores": {...}
  },
  "ai": {
    "contextPacks": {...},
    "promptPolicies": [...],
    "allowedTables": [...],
    "bannedJoins": [...]
  },
  "manifest": {
    "contentHash": "...",
    "ontologyHash": "...",
    "qualityHash": "...",
    "contextHash": "..."
  }
}
```

설계 원칙:
- Oracle이 질의 시점에 필요한 것은 모두 snapshot 내부에 있어야 한다.
- snapshot 하나만 읽으면 Prompt 구성, AST 검증, 신뢰 등급 결정이 가능해야 한다.
- runtime에서 추가 질의가 필요한 구조를 최대한 제거한다.

---

## 7. Synapse 구현 설계

## 7.1 주요 클래스

### 7.1.1 SnapshotBuilder
역할:
- active release 기준 metadata 로드
- compiler 결과, ontology bindings, quality aggregate, context packs 통합
- immutable snapshot document 생성

메서드:
```java
public interface SnapshotBuilder {
    SemanticSnapshot buildFromRelease(UUID releaseId);
}
```

### 7.1.2 SnapshotArtifactAssembler
역할:
- snapshot 내부 artifact 단위 materialization
- entity/measure index, banned join set, synonym expansion map 생성

### 7.1.3 SnapshotRegistryService
역할:
- snapshot 등록
- active snapshot 전환
- supersede/invalidate 처리
- consumer binding 조회

주요 메서드:
```java
SemanticSnapshot register(SemanticSnapshot snapshot);
void activate(String snapshotVersion);
void invalidate(String snapshotVersion, String reason);
Optional<SemanticSnapshot> findActiveForConsumer(String consumerName, String scope);
```

### 7.1.4 SnapshotPublisher
역할:
- Redis hot cache populate
- outbox event 기록
- prewarm 대상 consumer 통지 메타 생성

---

## 7.2 Synapse API 설계

### 7.2.1 Snapshot 조회 API
```http
GET /api/synapse/runtime/snapshots/active?consumer=ORACLE&scope=global
```
응답:
```json
{
  "snapshotVersion": "ss_2026_03_23_001",
  "releaseVersion": "r2026.03.23.1",
  "status": "ACTIVE",
  "manifest": {...}
}
```

### 7.2.2 Snapshot 전문 조회 API
```http
GET /api/synapse/runtime/snapshots/{snapshotVersion}
```
용도:
- Oracle cache miss 시 fetch
- Canvas 운영 점검

### 7.2.3 Consumer binding heartbeat API
```http
POST /api/synapse/runtime/consumers/bindings/heartbeat
```
요청:
```json
{
  "consumerName": "ORACLE",
  "consumerInstanceId": "oracle-pod-2",
  "boundSnapshotVersion": "ss_2026_03_23_001",
  "bindingMode": "AUTO"
}
```

### 7.2.4 Snapshot prewarm API
```http
POST /api/synapse/runtime/snapshots/{snapshotVersion}/prewarm
```
용도:
- publish 직후 Oracle/Canvas에 사전 적재 유도

---

## 8. Outbox/Event 설계

## 8.1 이벤트 타입

### 8.1.1 semantic.snapshot.published
```json
{
  "eventType": "semantic.snapshot.published",
  "snapshotVersion": "ss_2026_03_23_001",
  "releaseVersion": "r2026.03.23.1",
  "scope": ["global"],
  "contentHash": "...",
  "publishedAt": "2026-03-23T11:20:00Z"
}
```

### 8.1.2 semantic.snapshot.invalidated
```json
{
  "eventType": "semantic.snapshot.invalidated",
  "snapshotVersion": "ss_2026_03_23_000",
  "reason": "RELEASE_SUPERSEDED",
  "invalidatedAt": "2026-03-23T11:21:05Z"
}
```

### 8.1.3 semantic.release.rolled_back
```json
{
  "eventType": "semantic.release.rolled_back",
  "fromSnapshotVersion": "ss_2026_03_23_001",
  "toSnapshotVersion": "ss_2026_03_22_005",
  "reason": "VALIDATION_FAILURE",
  "rolledBackAt": "2026-03-23T11:27:00Z"
}
```

### 8.1.4 semantic.snapshot.prewarm.requested
```json
{
  "eventType": "semantic.snapshot.prewarm.requested",
  "snapshotVersion": "ss_2026_03_23_001",
  "targetConsumers": ["ORACLE", "CANVAS"]
}
```

## 8.2 이벤트 전파 방식

1차 구현은 단순하고 안정적으로 간다.

- Synapse Transactional Outbox에 이벤트 적재
- poller가 event bus 또는 Oracle polling endpoint로 전달
- Oracle은 최소 5~10초 주기 poll + push event 수신 혼합 가능

즉 Sprint 3의 목표는 “가장 현대적인 메시징 플랫폼”이 아니라 **일관성 있는 반영**이다.

---

## 9. Oracle 구현 설계

## 9.1 주요 클래스

### 9.1.1 SemanticSnapshotResolver
역할:
- request 시작 시 snapshot 결정
- pinning 우선 적용
- Redis → local cache → Synapse fallback 순으로 조회

```java
public interface SemanticSnapshotResolver {
    ResolvedSemanticSnapshot resolve(QueryRequestContext context);
}
```

우선순위:
1. request pin 존재 시 해당 version 사용
2. session pin 존재 시 사용
3. active pointer 조회
4. Redis hot snapshot 로드
5. miss 시 Synapse API fetch 후 Redis populate

### 9.1.2 VersionPinManager
역할:
- request_id 단위 snapshot version 고정
- 생성/검증/응답 전 구간 동일 version 보장

메서드:
```java
String pinForRequest(String requestId, String snapshotVersion);
Optional<String> getPinnedVersion(String requestId);
void releasePin(String requestId);
```

### 9.1.3 SemanticRuntimeContextFactory
역할:
- snapshot을 Oracle 내부 실행 컨텍스트로 변환
- prompt input, AST policy, trust policy를 하나의 context로 결합

### 9.1.4 SnapshotInvalidationListener
역할:
- outbox 전달 이벤트 수신
- local cache 제거
- active pointer 갱신
- prewarm 트리거

### 9.1.5 SemanticSnapshotLocalCache
역할:
- pod 내부 Caffeine/LRU 캐시
- Redis 장애 시 2차 방어막

---

## 9.2 Oracle 요청 처리 흐름

```text
[User Question]
   ↓
RequestContext 생성 (request_id 발급)
   ↓
SemanticSnapshotResolver.resolve()
   ↓
VersionPinManager.pin(request_id, snapshotVersion)
   ↓
Intent 분류 / ContextPack 선택
   ↓
Prompt 생성
   ↓
LLM SQL 생성
   ↓
AST 계약 검증 (동일 snapshot 사용)
   ↓
TrustPolicy 평가 (동일 snapshot 사용)
   ↓
응답 생성 + snapshotVersion 메타 포함
   ↓
Pin 해제 또는 TTL 만료
```

핵심은 **resolve를 한 번만 하고, 그 뒤에는 모든 단계가 pinned snapshot을 재사용**하는 것이다.

---

## 10. 버전 고정 규칙

## 10.1 Pinning 단위

### request-level pinning
- 기본값
- 단일 질문/단일 SQL 생성 흐름에 적용
- 가장 중요

### session-level sticky pinning
- 선택 적용
- 대화형 세션에서 여러 후속 질문을 같은 semantic version으로 유지하고 싶을 때 사용
- 예: “이전 결과와 같은 기준으로 다시 계산해줘” 같은 대화

### manual pinning
- 운영/디버깅용
- 특정 `snapshotVersion`을 강제로 사용

## 10.2 규칙
- request 시작 후 active snapshot이 바뀌어도 해당 request는 기존 pinned version 유지
- invalidate 이벤트가 와도 **이미 실행 중인 request**는 hard-fail 하지 않고 pinned snapshot으로 마무리
- 단, pinned snapshot이 `SECURITY_REVOKED`나 `CRITICAL_POLICY_VIOLATION`으로 invalidate된 경우는 즉시 차단 가능

## 10.3 응답 메타데이터
Oracle 응답에는 아래가 포함되어야 한다.

```json
{
  "semantic": {
    "snapshotVersion": "ss_2026_03_23_001",
    "releaseVersion": "r2026.03.23.1",
    "bindingMode": "AUTO",
    "consistency": "PINNED",
    "stale": false
  }
}
```

---

## 11. 캐시 정책

## 11.1 다단 캐시 구조

### Level 1: Local pod cache
- 매우 빠름
- 작은 크기 (예: 20~50 snapshots)
- Redis 장애 시 fallback

### Level 2: Redis hot cache
- 기본 조회 대상
- active snapshot 및 최근 snapshot 보관

### Level 3: Synapse snapshot registry
- 최종 원본
- miss 시 fetch

## 11.2 Prewarm 정책
- release publish 직후 active snapshot을 Redis에 적재
- Oracle 각 pod가 event 수신 시 snapshot fetch
- 첫 사용자 요청 전에 warm 상태 유도

## 11.3 TTL 정책
- active snapshot: TTL 연장형
- superseded snapshot: 24시간 유지
- invalidated snapshot: marker 유지, payload 제거 가능
- rolled-back old stable snapshot: 48시간 유지 가능

---

## 12. 무효화 정책

## 12.1 invalidate 원인
- RELEASE_SUPERSEDED
- QUALITY_POLICY_CHANGED
- ONTOLOGY_BINDING_CHANGED
- ACCESS_POLICY_CHANGED
- SECURITY_REVOKED
- MANUAL_ADMIN_ACTION

## 12.2 무효화 수준

### soft invalidation
- 신규 request부터 사용 금지
- 실행 중 request는 계속 허용

### hard invalidation
- 신규 request 즉시 금지
- 실행 중 request도 차단 가능
- 보안/정책 오류 시만 사용

## 12.3 Oracle 동작
- soft invalidation: active pointer 재조회, 신규 request부터 새 snapshot 사용
- hard invalidation: local pin 검사 후 차단 가능성 평가, 필요 시 사용자에게 재시도 안내

---

## 13. 장애 및 fallback 설계

## 13.1 Redis 장애
동작 순서:
1. local cache 사용
2. local miss 시 Synapse fetch
3. fetch 성공 시 local cache만 populate
4. 응답 메타에 `cacheMode=DEGRADED` 표시

## 13.2 Synapse 장애
- pinned snapshot이 있으면 계속 사용
- active snapshot local cache가 있으면 stale 허용 범위 내에서 사용
- 없으면 semantic-safe mode 진입

semantic-safe mode 정책:
- raw schema wide-open 질의 금지
- 사전 승인된 low-risk query template만 허용하거나 요청 차단
- 사용자에게 “의미 기준 최신 동기화 불가” 메시지 제공

## 13.3 Event 지연
- Oracle은 주기적으로 active pointer를 polling 하여 eventual consistency 보완
- event loss가 발생해도 polling이 복구 수단이 된다

---

## 14. 보안 및 무결성

- snapshot payload에는 secret/credential 포함 금지
- snapshot content hash 검증 수행
- Oracle이 수신한 snapshot의 hash와 Synapse manifest 비교 가능해야 함
- tampered snapshot 방지를 위해 manifest signature 또는 최소 HMAC 고려
- manual pinning은 운영 권한 필요

---

## 15. Canvas 운영 기능

Sprint 3에서는 Canvas에 최소 3가지만 추가한다.

### 15.1 Runtime Version Panel
표시 항목:
- active release version
- active snapshot version
- Oracle bound snapshot version (인스턴스별)
- last heartbeat
- stale 여부

### 15.2 Invalidation Timeline
- publish / invalidate / rollback 이벤트 타임라인
- 원인 코드 및 영향 consumer 표시

### 15.3 Force Rebind 액션
- 운영자가 특정 consumer에 snapshot prewarm/rebind 요청 가능

---

## 16. API/DTO 초안

## 16.1 Oracle ↔ Synapse snapshot fetch 응답
```json
{
  "snapshotVersion": "ss_2026_03_23_001",
  "releaseVersion": "r2026.03.23.1",
  "status": "ACTIVE",
  "stale": false,
  "manifest": {
    "contentHash": "abc",
    "ontologyHash": "def",
    "qualityHash": "ghi",
    "contextHash": "jkl"
  },
  "payload": {
    "contracts": {...},
    "ontology": {...},
    "quality": {...},
    "ai": {...}
  }
}
```

## 16.2 Oracle 내부 QueryExecutionContext
```java
public record QueryExecutionContext(
    String requestId,
    String sessionId,
    String snapshotVersion,
    String releaseVersion,
    SemanticRuntimeSnapshot snapshot,
    BindingMode bindingMode,
    boolean stale,
    CacheMode cacheMode
) {}
```

---

## 17. 테스트 전략

## 17.1 단위 테스트
- SnapshotBuilder가 동일 입력에서 동일 hash 생성
- Resolver 우선순위 테스트 (pin > local > redis > synapse)
- invalidation reason별 처리 분기 테스트
- TTL 만료 후 fallback 동작 테스트

## 17.2 통합 테스트
- release publish → Redis populate → Oracle prewarm
- request 시작 후 release 변경 → 동일 request는 drift 없이 완료
- invalidate event 수신 후 신규 request가 새 snapshot 사용
- Redis 장애 시 local cache fallback
- Synapse 장애 시 stale snapshot safe mode

## 17.3 회귀 테스트
- Sprint 1의 AST enforcement가 pinned snapshot으로 동일 결과 유지
- Sprint 2 trust policy가 pinned snapshot score 기준으로 동작

## 17.4 카오스/복원 테스트
- outbox event 지연 30초 주입
- Redis flushall 시나리오
- Oracle pod 재기동 후 rebind recovery

---

## 18. 관측성(Observability)

## 18.1 메트릭
- `semantic_snapshot_resolve_latency_ms`
- `semantic_snapshot_cache_hit_total{layer=local|redis|synapse}`
- `semantic_snapshot_invalidation_total{reason=...}`
- `semantic_version_drift_total`
- `semantic_binding_stale_total`
- `semantic_safe_mode_total`

## 18.2 로그 필드
- request_id
- session_id
- snapshot_version
- release_version
- binding_mode
- cache_mode
- stale
- invalidation_reason

## 18.3 알림
- Oracle heartbeat 미수신 5분 이상
- active pointer와 bound snapshot version 불일치 비율 임계치 초과
- version drift 1건 이상 즉시 알림

---

## 19. 구현 순서 (4주)

## Week 1 — Snapshot 모델과 Synapse registry
- `semantic_snapshots`, `semantic_snapshot_artifacts`, `semantic_runtime_bindings`, `semantic_snapshot_leases` 테이블 추가
- SnapshotBuilder / Registry 구현
- active snapshot 조회 API 구현
- Redis key 설계 및 populate 로직 구현

산출물:
- snapshot 생성/조회 가능
- 수동 active 전환 가능

## Week 2 — Oracle resolver와 version pinning
- SemanticSnapshotResolver 구현
- VersionPinManager 구현
- QueryExecutionContext 확장
- local cache + Redis 연동
- 응답 메타데이터에 snapshot version 노출

산출물:
- request-level version pinning 작동
- 95% 요청이 live Synapse 호출 없이 해결

## Week 3 — Event invalidation과 prewarm
- outbox 이벤트 4종 연결
- Oracle invalidation listener 구현
- prewarm flow 구현
- heartbeat/binding visibility 추가

산출물:
- publish/rollback/invalidate 반영 자동화
- Canvas에서 runtime binding 가시화

## Week 4 — 장애 대응/운영 안정화
- Redis/Synapse 장애 fallback 구현
- semantic-safe mode 구현
- stale/invalid 상태 정책 정교화
- 카오스 테스트/성능 튜닝

산출물:
- 장애 상황에서도 예측 가능한 동작 보장
- 운영 대시보드/경보 연결

---

## 20. 완료 정의 (Definition of Done)

아래를 모두 만족하면 Sprint 3 완료로 본다.

1. Oracle이 기본적으로 Redis/local cache 기반 snapshot resolution을 사용한다.
2. request-level version pinning이 생성→검증→응답 전 구간에서 유지된다.
3. publish/invalidate/rollback 이벤트가 Oracle cache에 자동 반영된다.
4. active snapshot과 Oracle bound snapshot이 Canvas에서 관찰 가능하다.
5. version drift가 통합 테스트에서 0건이다.
6. Redis 또는 Synapse 장애 시 fallback/safe mode 동작이 검증된다.

---

## 21. Sprint 3 이후 연결점

Sprint 3가 끝나면 시스템은 다음 상태에 도달한다.

- Sprint 1: 계약 위반 차단
- Sprint 2: 품질 기반 응답 제어
- Sprint 3: semantic version 일관성 보장

즉 이 시점부터 Oracle은 단순히 “semantic context를 참고하는 시스템”이 아니라,
**고정된 semantic snapshot 위에서 계약 검증과 신뢰 정책을 일관되게 집행하는 runtime**가 된다.

이후 Sprint 4에서는 다음을 연결하는 것이 자연스럽다.

- ontology synonym expansion 실사용
- intent confidence 기반 context selection 개선
- domain namespace 별 active snapshot 분리
- session-level sticky pinning 고도화

---

## 22. 최종 요약

Sprint 3의 본질은 캐시를 다는 것이 아니다.

진짜 목표는 아래를 보장하는 것이다.

- 같은 질문은 같은 semantic version 위에서 끝난다.
- release가 바뀌어도 실행 중 요청은 흔들리지 않는다.
- 새 계약은 예측 가능하게 반영되고, 오래된 계약은 안전하게 폐기된다.
- 운영자는 지금 Oracle이 어떤 의미 기준으로 답하고 있는지 볼 수 있다.

따라서 Sprint 3는 성능 최적화 스프린트가 아니라,
**Semantic Runtime의 일관성과 운영 신뢰성을 닫는 스프린트**로 정의하는 것이 맞다.
