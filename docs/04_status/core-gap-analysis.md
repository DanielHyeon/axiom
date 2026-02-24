# Core 설계 문서 대비 구현 갭 분석

> **기준**: `services/core/docs/` 문서 vs `services/core/app/` 실제 구현  
> **작성일**: 2026-02-22  
> **갱신**: 2026-02-22 — cases API·오케스트레이터 연동 반영: app/api/cases(목록·활동·문서 리뷰), LangGraph Oracle/Synapse 연동, SafeToolLoader MCP.

## 1. 문서 기준

- **설계 문서 위치**: `services/core/docs/`
  - `00_overview/system-overview.md` — Core 역할, 기술 스택, 경계
  - `01_architecture/architecture-overview.md` — 계층, 컴포넌트 매핑
  - `01_architecture/bpm-engine.md` — BPM 엔진, Saga, 추출기
  - `02_api/process-api.md`, `watch-api.md`, `agent-api.md`, `gateway-api.md`
  - `07_security/auth-model.md` — JWT, RBAC, 로그인/갱신
  - `03_backend/worker-system.md` — Worker 목록 및 구조
  - `06_data/event-outbox.md` — Event Outbox / Redis Streams

---

## 2. 갭 요약

| 영역 | 문서 기대 | 현재 구현 | 갭 |
|------|-----------|-----------|-----|
| **인증/인가** | JWT 발급·검증, RBAC, auth API | ✅ login/refresh, security.py, 보호 경로 Depends | **해소** (RBAC 데코레이터·속도 제한은 선택) |
| **API 경로** | auth, cases, process, agents, watches, users | auth, users, process, watch, agent, gateway, events, health, **cases** | **해소** (cases: app/api/cases/routes.py 구현) |
| **Domain 계층** | app/bpm/, app/orchestrator/ | app/bpm/(models, engine, saga, extractor 스텁), app/orchestrator/(langgraph_flow, agent_loop 스텁) | **해소** (추출기·연동은 예정) |
| **Workers** | sync, watch_cep, ocr, extract, generate, event_log | sync, watch_cep, event_log 구현 (CEP·Synapse 로직 스텁), ocr/extract/generate 예정 | **부분 해소** |
| **Process** | 정의 단건 조회 | GET /process/definitions/:id 구현 | **해소** |
| **사용자 API** | POST /api/v1/users, GET /users/me | GET /api/v1/users/me 구현 | **부분 해소** (목록·생성 추후) |
| **미들웨어** | JWT, 속도 제한, RBAC | JWT는 Depends로 적용 | **해소** (Rate limit 선택) |

---

## 3. 상세 갭

### 3.1 인증·인가 (07_security/auth-model.md, 02_api/gateway-api.md)

| 문서 내용 | 구현 여부 | 비고 |
|----------|----------|------|
| `POST /api/v1/auth/login` (이메일/비밀번호 → JWT) | ✅ | app/api/auth/routes.py |
| `POST /api/v1/auth/refresh` (Refresh Token → 새 토큰) | ✅ | 동일 |
| `app/core/security.py` (JWT 검증, get_current_user) | ✅ | 구현됨 |
| JWT 검증 (보호 경로) | ✅ | Depends(get_current_user) 로 process, watch, agent, gateway, events, users 적용 |
| RBAC 경로별 권한 | ⚠️ | require_permission 데코레이터 존재, 라우터별 적용은 선택 |
| Refresh Token 블랙리스트 (Redis) | ✅ | auth:refresh_blacklist, TTL 7일 |
| User·Tenant 모델 (로그인 시 검증) | ✅ | base_models.Tenant, User; login 시 활성 검사 |

**결과**: 인증·갱신·블랙리스트·보호 경로 적용 완료. 속도 제한 미들웨어는 미구현(선택).

---

### 3.2 API·라우팅 (01_architecture/architecture-overview.md, 02_api/gateway-api.md)

| 문서 상 경로/구성 | 구현 여부 | 비고 |
|-------------------|----------|------|
| `app/api/auth/` | ✅ | app/api/auth/routes.py (login, refresh) |
| `app/api/users/` | ✅ | app/api/users/routes.py (GET /me) |
| `app/api/cases/` (Core 자체 케이스·활동·문서 리뷰) | ✅ | app/api/cases/routes.py: GET /cases, GET /cases/activities, POST /cases/:caseId/documents/:docId/review. core_case, core_case_activity, core_document_review |
| `app/api/process/` | ✅ | process/routes.py 존재 |
| `app/api/agents/` | ✅ | agent/routes.py 존재 |
| `app/api/watches/` | ✅ | watch/routes.py 존재 |
| 공개 경로: /auth/login, /auth/refresh, /health | ⚠️ | /health/* 만 구현 (health/startup, live, ready, metrics) |
| 속도 제한 미들웨어 (IP/User 기반) | ❌ | 없음 |
| Circuit Breaker (프록시별) | ⚠️ | resilience.py 존재하나, gateway 라우트에 적용 여부·문서 정합성 확인 필요 |

---

### 3.3 Domain 계층 (01_architecture, 01_architecture/bpm-engine.md)

| 문서 상 구성 | 구현 여부 | 비고 |
|--------------|----------|------|
| `app/bpm/` | ✅ | Phase D에서 생성 |
| `app/bpm/models.py` (Pydantic 프로세스 모델) | ✅ | ActivityType, AgentMode, ProcessDefinitionModel 등 |
| `app/bpm/engine.py` (BPM 실행 엔진) | ✅ | get_initial_activity, get_next_activities_after; process_service 위임 |
| `app/bpm/saga.py` (Saga 보상) | ✅ | SagaManager 스텁 (trigger_compensation 반환만) |
| `app/bpm/extractor.py` (PDF→BPMN/DMN) | ⚠️ | 스텁, "예정" 문서화 |
| `app/orchestrator/` | ✅ | Phase D에서 생성 |
| `app/orchestrator/langgraph_flow.py` (10노드 LangGraph) | ✅ | 구현됨. query_data→Oracle /text2sql/ask, mining→Synapse /process-mining/discover. SSOT §2.1 |
| `app/orchestrator/agent_loop.py` (지식 학습 루프) | ✅ | 구현됨 (graph.ainvoke, HITL, db·workitem 연동) |
| `app/orchestrator/tool_loader.py`, MCP 클라이언트 등 | ✅ | SafeToolLoader·agent_service.list_mcp_tools 연동 구현 |

**결과**: BPM “엔진”·Saga·BPMN 추출·LangGraph 오케스트레이터는 문서만 있고, BPM 엔진·Saga(스텁)·orchestrator·tool_loader 구현 완료. Oracle/Synapse 노드 연동. process_service는 bpm/engine 위임. 추출기·연동은 예정.

---

### 3.4 Worker (03_backend/worker-system.md)

| 문서 상 Worker | 파일 | 구현 여부 |
|----------------|------|----------|
| sync | workers/sync.py | ✅ (event_outbox → Redis Streams 폴링) |
| watch_cep | workers/watch_cep.py | ✅ (axiom:watches 소비·ACK, CEP·알림 로직 스텁) |
| ocr | workers/ocr.py | ❌ 예정 |
| extract | workers/extract.py | ❌ 예정 |
| generate | workers/generate.py | ❌ 예정 |
| event_log | workers/event_log.py | ✅ (axiom:workers 소비·ACK, Synapse 연동 스텁) |

**결과**: sync, watch_cep, event_log 구현. ocr, extract, generate는 예정.

---

### 3.5 Process API·데이터 (02_api/process-api.md, BPM 설계)

| 문서/기대 | 구현 여부 | 비고 |
|-----------|----------|------|
| GET /api/v1/process/definitions | ✅ | 목록 (cursor, limit, sort) |
| POST /api/v1/process/definitions | ✅ | 생성 (name, source, bpmn_xml 등) |
| GET /api/v1/process/definitions/:id | ✅ | ProcessService.get_definition, GET /definitions/{proc_def_id} |
| POST /initiate, /submit, /role-binding, /rework, /approve-hitl | ✅ | 구현됨 |
| GET /process/{proc_inst_id}/status, /workitems | ✅ | 구현됨 |
| GET /process/feedback/{workitem_id} | ✅ | 구현됨 |
| ProcessInstance 전용 테이블 | ❌ | 없음. 상태는 WorkItem 집약으로 유도 |
| Event Outbox에 PROCESS_* 이벤트 INSERT | ✅ | process_service에서 EventPublisher 사용 |
| Saga 보상 호출 | ⚠️ | app/bpm/saga.py 스텁 (trigger_compensation 반환만) |

---

### 3.6 Event Outbox·Redis (06_data/event-outbox.md)

| 문서 내용 | 구현 여부 | 비고 |
|----------|----------|------|
| event_outbox 테이블 | ✅ | base_models.EventOutbox |
| EventPublisher.publish() (같은 트랜잭션에 INSERT) | ✅ | core/events.py |
| sync Worker가 PENDING → Redis 발행 | ✅ | workers/sync.py |
| Redis Streams Consumer Group (watch_cep, event_log) | ✅ | workers/watch_cep.py, workers/event_log.py |
| axiom:events, axiom:watches, axiom:workers 스트림 구독 | ✅ | event-outbox.md §2.2 Sync 발행 포맷 문서화, watch_cep/event_log 소비 |

---

### 3.7 Watch·Agent API

| 항목 | 구현 여부 |
|------|----------|
| Watch 구독/알림/규칙 CRUD, SSE 스트림 | ✅ (watch/routes.py) |
| Agent feedback, MCP config/tools/execute, completion, chat, knowledge | ✅ (agent/routes.py). 문서는 “Partial” 표기 |

---

### 3.8 사용자·케이스 (문서 다수 참조)

| API/기능 | 구현 여부 |
|----------|----------|
| POST /api/v1/users (watch-api.md: 사용자 생성 시 구독 시드) | ❌ (추후 확장) |
| GET /api/v1/users/me | ✅ app/api/users/routes.py |
| Core 자체 케이스·활동·문서 리뷰 (app/api/cases/) | ✅ GET /cases, /cases/activities, POST .../review (core_case, core_case_activity, core_document_review) |
| User·Tenant 모델/테이블 (Core DB) | ✅ base_models.Tenant, User |

---

## 4. 구현된 것 정리

- **라우터**: health, process, watch, agent, gateway, events, **cases**
- **미들웨어**: CORS, RequestIdMiddleware, TenantMiddleware (X-Tenant-Id / X-Forwarded-Host)
- **Process**: 정의 목록/생성, initiate/submit/role-binding/status/workitems/feedback/rework/approve-hitl (JWT 검증 없이 tenant_id만 사용)
- **Watch**: 구독·알림·규칙 CRUD, SSE 스트림
- **Agent**: feedback, MCP, completion, chat, knowledge (인메모리/파일 기반 등)
- **Gateway**: 이벤트 로그, 프로세스 마이닝, 추출, 온톨로지, 그래프, 스키마 편집 등 Synapse/외부 프록시
- **Event Outbox**: EventOutbox 모델, EventPublisher, sync Worker로 PENDING → Redis 발행
- **DB 모델**: EventOutbox, WorkItem, ProcessDefinition, ProcessRoleBinding, WatchSubscription, WatchRule, WatchAlert, **Case, CaseActivity, DocumentReview** (core_case, core_case_activity, core_document_review)

---

## 5. 권장 조치 (우선순위 예시)

1. **인증**: `app/core/security.py` 및 `app/api/auth/` 추가 — 로그인/refresh, JWT 검증, get_current_user. (또는 Gateway에서 처리한다면 문서를 “Core 외부”로 정리.)
2. **보호 구간**: 인증 필요한 경로에 JWT Depends 적용 및 RBAC(경로별 권한) 정합성 확인.
3. **사용자/케이스**: Core에서 담당할지 결정 후, `/api/v1/users`, `/api/v1/users/me`, `/api/v1/cases/**` 중 구현할 항목만 문서와 맞춤.
4. **Process**: 정의 단건 조회 `GET /api/v1/process/definitions/:id` 필요 시 추가.
5. **Domain 분리**: BPM 엔진·Saga·추출기·LangGraph를 도입할 계획이면 `app/bpm/`, `app/orchestrator/` 구조를 문서대로 생성하고 process_service는 이 계층을 호출하도록 리팩터.
6. **Workers**: watch_cep·event_log 구현 완료(소비·ACK, CEP/Synapse 스텁). ocr, extract, generate는 문서 예정 유지. 문서 상 Worker 구현 또는 문서를 “예정”으로 조정.
7. **문서 갱신**: “구현 상태” 태그 및 경로 테이블을 위 구현 상태에 맞게 수정 (auth, cases, users, workers 등).

---

## 6. 참조 문서

- `services/core/docs/00_overview/system-overview.md`
- `services/core/docs/01_architecture/architecture-overview.md`
- `services/core/docs/07_security/auth-model.md`
- `services/core/docs/02_api/gateway-api.md`
- `services/core/docs/03_backend/worker-system.md`
- `docs/04_status/settings-users-api-status.md` (사용자 API 연동 현황)
