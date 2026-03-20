# Axiom Core - 서비스 내부 구조

## 이 문서가 답하는 질문

- Core 서비스의 디렉토리 레이아웃은 어떻게 구성되는가?
- 각 패키지의 책임과 의존 방향은 무엇인가?
- 코드 리뷰 시 어떤 규칙을 적용하는가?

<!-- affects: backend -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

---

## 1. 디렉토리 레이아웃

> **최종 검증일**: 2026-03-21 — 실제 코드베이스 기준 (`services/core/app/`)

```
services/core/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI 앱 진입점, 미들웨어·라우터 등록
│   │
│   ├── api/                             # [Presentation Layer] REST 엔드포인트 (직접 구현)
│   │   ├── __init__.py
│   │   ├── health.py                    # 헬스체크 (startup, live, ready, metrics)
│   │   ├── auth/routes.py               # 인증 (login, refresh) — 공개 경로
│   │   ├── users/routes.py              # 사용자 관리 (GET /me, POST, GET 목록)
│   │   ├── events/routes.py             # 이벤트 Outbox 관리 (sync run-once, backlog, retry, DLQ)
│   │   ├── admin/event_routes.py        # DLQ 관리 API (dead-letter CRUD, 파이프라인 메트릭)
│   │   └── gateway/routes.py            # Synapse 프록시 게이트웨이 (event-logs, process-mining,
│   │                                    #   extraction, schema-edit, graph, ontology — 약 50개 엔드포인트)
│   │
│   ├── modules/                         # [모듈별 Bounded Context] DDD 기반 패키지 분리
│   │   ├── agent/                       # 에이전트 모듈
│   │   │   ├── api/routes.py            # /agents/*, /mcp/*, /completion/* 엔드포인트
│   │   │   ├── application/
│   │   │   │   └── agent_service.py     # AgentService (피드백, MCP, 채팅, 지식 관리)
│   │   │   └── infrastructure/
│   │   │       └── state/agent_state_store.py  # 에이전트 상태 영속화
│   │   │
│   │   ├── case/                        # 케이스 모듈
│   │   │   └── api/routes.py            # /cases 목록·활동·통계·추이·문서리뷰 엔드포인트
│   │   │
│   │   ├── process/                     # BPM 프로세스 모듈 (DDD Aggregate 구조)
│   │   │   ├── api/routes.py            # /process/* 엔드포인트
│   │   │   ├── application/             # Application Services
│   │   │   │   ├── definition_service.py
│   │   │   │   ├── process_instance_service.py
│   │   │   │   ├── workitem_lifecycle_service.py
│   │   │   │   ├── role_binding_service.py
│   │   │   │   └── process_service_facade.py   # 하위 호환용 파사드
│   │   │   ├── domain/                  # Domain Layer (순수 비즈니스 규칙)
│   │   │   │   ├── aggregates/work_item.py    # WorkItem Aggregate Root (상태 머신)
│   │   │   │   ├── events.py                   # 도메인 이벤트 정의
│   │   │   │   ├── errors.py                   # 도메인 에러
│   │   │   │   └── repositories/work_item_repository.py  # 리포지토리 인터페이스
│   │   │   └── infrastructure/          # Infrastructure 구현
│   │   │       ├── bpm/                 # BPM 엔진 (models, engine, saga, extractor)
│   │   │       ├── event_store.py       # 이벤트 저장소
│   │   │       ├── mappers/             # 도메인 ↔ ORM 매퍼
│   │   │       └── repositories/        # SQLAlchemy 리포지토리 구현
│   │   │
│   │   └── watch/                       # Watch 모듈
│   │       ├── api/routes.py            # /watches/* 엔드포인트 (구독, 알림, 룰, 스케줄러, SSE)
│   │       ├── application/
│   │       │   └── watch_service.py     # WatchService (구독·알림·룰 CRUD, CEP 룰 검증)
│   │       └── infrastructure/
│   │           └── watch_cep.py         # WatchCepWorker 구현
│   │
│   ├── orchestrator/                    # [Domain Layer] 에이전트 오케스트레이션
│   │   ├── langgraph_flow.py            # _CompiledOrchestrator (4노드 의도 분류 흐름)
│   │   ├── agent_loop.py               # run_agent_loop (오케스트레이터 1회 실행)
│   │   ├── tool_loader.py              # SafeToolLoader (BLOCKED_TOOLS 차단 목록 기반)
│   │   └── mcp_client.py               # MCP 도구 실행 클라이언트 (httpx 기반)
│   │
│   ├── workers/                         # [Infrastructure Layer] 비동기 워커
│   │   ├── base.py                      # BaseWorker (재시도, 멱등성 래퍼)
│   │   ├── sync.py                      # SyncWorker — Outbox → Redis Streams (MAX_RETRY=3, DLQ)
│   │   ├── watch_cep.py                 # WatchCepWorker 하위호환 shim
│   │   ├── policy_executor.py           # PolicyExecutorWorker — Neo4j Policy 매칭 → POLICY_COMMAND 발행
│   │   ├── event_log.py                 # EventLogWorker — 이벤트 로그 파싱 (미구현 스텁)
│   │   ├── event_log_parsers.py         # XES/CSV 파서 (미구현 스텁)
│   │   ├── ocr.py                       # OCR 워커 (미구현 스텁)
│   │   ├── extract.py                   # 문서 추출 워커 (미구현 스텁)
│   │   └── generate.py                  # 문서 생성 워커 (미구현 스텁)
│   │
│   ├── infrastructure/external/         # [Infrastructure Layer] 외부 BC 접근
│   │   └── synapse_acl.py               # SynapseACL — Anti-Corruption Layer (Core→Synapse)
│   │
│   ├── core/                            # [Infrastructure Layer] 공통 인프라
│   │   ├── config.py                    # Settings (pydantic-settings 기반)
│   │   ├── security.py                  # JWT 인증 (PyJWT) + RBAC (ROLE_PERMISSIONS)
│   │   ├── middleware.py                # TenantMiddleware + RequestIdMiddleware (ASGI 미들웨어)
│   │   ├── database.py                  # SQLAlchemy async 엔진·세션·Base (스키마: "core")
│   │   ├── redis_client.py              # Redis 싱글턴 (redis.asyncio)
│   │   ├── events.py                    # EventPublisher — Outbox 테이블 INSERT
│   │   ├── event_contract_registry.py   # EventContract 등록·검증 (9개 이벤트)
│   │   ├── rate_limiter.py              # RateLimitMiddleware + check() 의존성
│   │   ├── resilience.py                # CircuitBreaker (3상태: CLOSED/OPEN/HALF_OPEN)
│   │   ├── observability.py             # MetricsRegistry (Prometheus 텍스트 렌더링)
│   │   ├── self_verification.py         # SelfVerificationHarness (20% 샘플링)
│   │   └── logging.py                   # JSONContextFormatter (구조화 로깅)
│   │
│   ├── models/                          # [Infrastructure Layer] SQLAlchemy ORM 모델
│   │   └── base_models.py               # 모든 모델 정의 (Tenant, User, Case, CaseActivity,
│   │                                    #   EventOutbox, WorkItem, ProcessDefinition,
│   │                                    #   ProcessRoleBinding, WatchSubscription, WatchRule,
│   │                                    #   WatchAlert, EventDeadLetter, SagaExecutionLog,
│   │                                    #   DocumentReview — 총 14개 테이블)
│   │
│   ├── shared/                          # 공유 모듈 (auth, config, event_bus, middleware shim)
│   │   └── event_bus/bus.py             # 이벤트 버스 유틸리티
│   │
│   ├── services/                        # [레거시] 하위 호환 서비스 모듈
│   │   ├── agent_service.py             # → modules/agent으로 위임
│   │   ├── process_service.py           # → modules/process로 위임
│   │   ├── watch_service.py             # → modules/watch로 위임
│   │   └── synapse_gateway_service.py   # → infrastructure/external/synapse_acl로 위임
│   │
│   ├── llm/agent.py                     # LLM 에이전트 유틸리티 (미구현 스텁)
│   │
│   ├── bpm/                             # [레거시] BPM 모델/엔진 (→ modules/process에 복제)
│   │   ├── models.py, engine.py, saga.py, extractor.py
│   │
│   ├── domain/                          # [레거시] 도메인 모델 (→ modules/process/domain에 복제)
│   │   ├── aggregates/work_item.py, events.py, errors.py, repositories/
│   │
│   └── scripts/load_test.py             # 부하 테스트 스크립트
│
├── tests/                               # pytest 테스트
├── docs/                                # 기술 문서 (현재 파일 위치)
├── pyproject.toml                       # Python 프로젝트 설정
├── requirements.txt                     # 의존성 목록
├── pytest.ini                           # pytest 설정
└── Dockerfile                           # 컨테이너 빌드
```

> **참고**: `app/bpm/`, `app/domain/`, `app/services/` 경로는 레거시 하위 호환 코드이다. 신규 코드는 반드시 `app/modules/<domain>/` 패턴을 따라야 한다.

---

## 2. 의존 방향 규칙

> **실제 구현 기준** (2026-03-21 검증): `modules/` 패키지 내에서 Hexagonal Architecture 의존 방향을 따른다.

```
modules/<domain>/api/routes.py
    → modules/<domain>/application/*_service.py   (Application Layer)
        → modules/<domain>/domain/aggregates/     (Domain Layer — 순수 비즈니스 규칙)
        → modules/<domain>/infrastructure/        (Repository 구현, 외부 연동)
            → core/                               (DB, Redis, config)
            → models/base_models.py               (ORM 모델)

workers/ → core/ (DB, Redis, config)
         → models/base_models.py

orchestrator/ → core/config (설정), models/ (WorkItem 조회)
```

### 2.1 허용되는 의존 방향

| 소스 | 대상 | 허용 |
|------|------|------|
| modules/*/api/ | modules/*/application/ | O |
| modules/*/api/ | core/ (Depends) | O |
| modules/*/application/ | modules/*/domain/ | O |
| modules/*/application/ | modules/*/infrastructure/ | O |
| modules/*/infrastructure/ | core/, models/ | O |
| modules/*/domain/ | (순수 Python만 — 외부 의존 없음) | O |
| orchestrator/ | core/, models/ | O |
| workers/ | core/, models/ | O |
| api/gateway/ | infrastructure/external/ (SynapseACL) | O |

### 2.2 금지되는 의존 방향

| 소스 | 대상 | 금지 사유 |
|------|------|----------|
| modules/*/api/ | models/ (직접) | Application Service를 우회하면 트랜잭션 관리 불가 |
| modules/*/domain/ | core/, models/ | 도메인 계층은 인프라 의존 금지 (Hexagonal Architecture) |
| core/ | modules/ | 순환 의존 |
| workers/ | modules/*/api/ | Worker는 Service Layer나 core를 통해서만 접근 |
| modules/A/ | modules/B/ (직접) | 모듈 간 직접 의존 금지 — 이벤트 버스 사용 |

> **참고**: `app/api/cases/routes.py`는 `Case`, `CaseActivity` 모델을 직접 조회하는 예외 패턴이 존재한다. 이는 단순 조회 전용이기 때문이며, 쓰기 작업은 반드시 Application Service를 경유해야 한다.

---

## 3. 코드 리뷰 기준

### 3.1 필수 검사 항목

```
[필수] 새 API 엔드포인트는 반드시 schemas.py에 Pydantic 모델을 정의한다.
[필수] DB 접근은 반드시 Service Layer를 통해서만 한다.
[필수] 모든 외부 호출(LLM, MCP, 다른 모듈)에 타임아웃을 설정한다.
[필수] Event Outbox 이벤트 발행은 비즈니스 로직과 같은 트랜잭션에서 한다.
[필수] 새 Worker 추가 시 멱등성(idempotency) 보장을 확인한다.
[필수] 환경 변수는 core/config.py의 Settings 클래스에 정의한다.
```

### 3.2 금지 패턴

```
[금지] Router 핸들러에서 직접 SQLAlchemy 세션 생성 (Service에 위임)
[금지] Worker에서 HTTP 응답 반환 (Worker는 백그라운드 프로세스)
[금지] core/ 패키지에서 비즈니스 로직 구현
[금지] 하드코딩된 설정 값 (config.py 또는 환경 변수 사용)
[금지] except Exception: pass (예외 무시 금지)
[금지] 테스트 없는 새 기능 머지
```

---

## 근거

- K-AIR 역설계 보고서 섹션 4.11.2 (Axiom 모노레포 디렉토리 구조)
- 01_architecture/architecture-overview.md (논리적 계층 정의)
