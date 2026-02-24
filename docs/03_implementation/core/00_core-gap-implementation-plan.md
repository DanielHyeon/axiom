# Core 설계 문서 갭 해소 구현 계획

> **근거 문서**: [docs/04_status/core-gap-analysis.md](../../core-docs-vs-implementation-gap.md)  
> **작성일**: 2026-02-22

## 1. 목적

- `services/core/docs/` 설계 문서와 `services/core/app/` 현재 구현 간 갭을 단계적으로 해소하기 위한 구현 계획.
- Phase별 작업 패키지, 티켓, 선행 조건, 통과 기준을 정의한다.

## 2. 참조 문서

| 문서 | 용도 |
|------|------|
| docs/04_status/core-gap-analysis.md | 갭 분석 원본 |
| services/core/docs/07_security/auth-model.md | 인증·RBAC 스펙 |
| services/core/docs/02_api/gateway-api.md | 라우팅·공개 경로·미들웨어 |
| services/core/docs/01_architecture/architecture-overview.md | 계층·컴포넌트 |
| services/core/docs/03_backend/worker-system.md | Worker 목록 |
| services/core/docs/01_architecture/bpm-engine.md | BPM·Saga·추출기 |

## 3. Phase 개요

| Phase | 목표 | 산출 요약 | 선행 |
|-------|------|-----------|------|
| **A** | 인증·인가 | auth API, JWT 검증, RBAC 기반 | - |
| **B** | 사용자·케이스 범위 | User/Tenant 모델·API 또는 “Core 외부” 결정 | A |
| **C** | Process·API 보완 | 정의 단건 조회, 보호 경로 JWT 적용 | A |
| **D** | Domain 계층 (선택) | app/bpm/, app/orchestrator/ 구조·엔진/Saga/추출기 | C |
| **E** | Workers 확장 | watch_cep, event_log 등 문서 대비 Worker | A, C |
| **F** | 문서·운영 정합성 | 구현 상태 태그, 미들웨어·경로 문서 반영 | A~E |

---

## 4. Phase A: 인증·인가

**목표**: auth-model.md·gateway-api.md에 따른 로그인/refresh, JWT 검증, (선택) RBAC 적용.

### 4.1 선행 조건

- 없음.

### 4.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| A1 | User·Tenant 모델 및 마이그레이션 | Core DB에 users, tenants(또는 tenant_config) 테이블 추가. 비밀번호 해시(bcrypt), 활성 플래그, tenant_id FK. | models, Alembic migration |
| A2 | app/core/security.py 추가 | JWT 발급/검증(HS256 또는 RS256), get_current_user(Depends), payload에서 tenant_id/role/permissions/case_roles 추출. | security.py |
| A3 | POST /api/v1/auth/login | 이메일/비밀번호 검증, User/Tenant 활성 확인, Access/Refresh 토큰 발급. 응답: access_token, refresh_token, expires_in. | app/api/auth/routes.py |
| A4 | POST /api/v1/auth/refresh | refresh_token 검증, 블랙리스트 확인(Redis), Token Rotation 후 새 쌍 발급. | auth/routes.py |
| A5 | Refresh 토큰 블랙리스트 (Redis) | 로그아웃/갱신 시 기존 refresh를 Redis에 TTL=7일로 저장, refresh 시 블랙리스트 조회. | security 또는 auth_service |
| A6 | JWT 미들웨어 또는 Depends 적용 | 보호 경로에 get_current_user 적용. 공개 경로: /api/v1/auth/login, /api/v1/auth/refresh, /api/v1/health/*. | main.py 또는 라우터별 Depends |
| A7 | (선택) RBAC 경로별 권한 | gateway-api 권한 매트릭스에 따라 require_permission 데코레이터 또는 미들웨어. admin은 모든 권한 통과. | security.py, 라우터 적용 |

### 4.3 통과 기준 (Gate A)

- POST /api/v1/auth/login 으로 유효 자격증으로 Access/Refresh 토큰 수신.
- POST /api/v1/auth/refresh 로 새 토큰 쌍 수신; 만료/블랙리스트 refresh는 401.
- 보호 경로에 Authorization 없거나 유효하지 않으면 401.
- (선택) 권한 부족 시 403.

### 4.4 연계

- 07_security-implementation-plan, 02_api-implementation-plan 과 연동.

---

## 5. Phase B: 사용자·케이스 범위

**목표**: Core가 사용자/케이스 CRUD를 직접 담당할지 결정하고, 담당 시 최소 API·모델 구현.

### 5.1 선행 조건

- Phase A 완료 (로그인/refresh 동작).

### 5.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| B1 | 사용자·케이스 책임 결정 | Core 내 구현 vs 외부 Gateway/IdP 정책 확정. 결정 결과를 docs/04_status/settings-users-api-status.md 및 본 계획에 반영. | 결정 문서/ADR |
| B2 | GET /api/v1/users/me (Core 담당 시) | get_current_user 기반으로 현재 사용자 정보 반환. auth-model payload와 동일 필드. | app/api/users/ 또는 auth 확장 |
| B3 | POST /api/v1/users (Core 담당 시) | 사용자 생성, Watch 역할별 기본 구독 시드(watch-api.md). | users routes, watch_service 연동 |
| B4 | app/api/cases/ (Core 담당 시) | 케이스 CRUD가 Core 책임이면 cases 라우터·서비스·모델 추가. 외부면 “Proxy만” 문서화. | cases/ 또는 문서 갱신 |

### 5.3 통과 기준 (Gate B)

- 책임 결정이 문서화됨.
- Core 담당으로 결정된 항목만 구현되고, 나머지는 “외부 담당”으로 문서 정리.

### 5.4 연계

- docs/04_status/settings-users-api-status.md, admin-dashboard.md (API 경로).

---

## 6. Phase C: Process·API 보완 및 보호 경로 정합성

**목표**: Process 정의 단건 조회 추가, 기존 보호 경로에 JWT 적용, (선택) 속도 제한.

### 6.1 선행 조건

- Phase A 완료.

### 6.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| C1 | GET /api/v1/process/definitions/:id | proc_def_id로 단건 조회. 응답: proc_def_id, name, version, type, source, definition, bpmn_xml 등. 404 when not found. | process/routes.py, process_service |
| C2 | 보호 경로 JWT 적용 | process, watch, agent, gateway(보호 구간) 라우터에 get_current_user(또는 동등) Depends 적용. tenant_id는 JWT에서 취득·ContextVar와 일치 검증. | 각 api/*/routes.py |
| C3 | (선택) 속도 제한 미들웨어 | gateway-api.md의 경로별 제한(예: /auth/login 10 req/min). Redis 또는 in-memory 카운터. | middleware |
| C4 | (선택) Circuit Breaker 문서·적용 검토 | resilience.py와 gateway 프록시 라우트 매핑. 문서와 실제 적용 여부 정합성 확인. | 문서 또는 코드 |

### 6.3 통과 기준 (Gate C)

- GET /api/v1/process/definitions/:id 로 정의 단건 조회 가능.
- 인증 필요한 경로는 토큰 없이 401.
- (선택) 속도 제한 초과 시 429.

### 6.4 연계

- 02_api-implementation-plan (Process API), Canvas processApi (단건 조회 클라이언트).

---

## 7. Phase D: Domain 계층 (BPM·Orchestrator) — 선택

**목표**: 설계 문서대로 app/bpm/, app/orchestrator/ 도입 여부 결정 후, 도입 시 최소 구조·엔진/Saga/추출기 배치.

### 7.1 선행 조건

- Phase C 완료. (Process API가 안정된 상태에서 리팩터.)

### 7.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| D1 | Domain 계층 도입 여부 결정 | 현재 process_service 단일 레이어로 유지 vs bpm/orchestrator 분리. K-AIR 이식 범위·리소스 고려. | 결정 문서 |
| D2 | app/bpm/ 구조 생성 | bpm/models.py(Pydantic), bpm/engine.py(실행 코어), bpm/saga.py(보상). process_service는 이 계층 호출로 위임. | app/bpm/* |
| D3 | app/orchestrator/ 구조 생성 | langgraph_flow.py(9노드), agent_loop.py(지식 학습), tool_loader 또는 MCP 클라이언트. agent_service와 연동. | app/orchestrator/* |
| D4 | BPMN 추출기 (추가 범위) | app/bpm/extractor.py — PDF→엔티티→BPMN/DMN. 우선순위 낮으면 “예정” 문서화. | extractor 또는 문서 |

### 7.3 통과 기준 (Gate D)

- 도입 시: process_service가 bpm 엔진/서비스를 호출하고, 기존 Process API 동작 유지.
- 미도입 시: 문서에 “현재 단일 서비스 레이어 유지” 명시.

### 7.4 연계

- 01_architecture-implementation-plan, 05_llm-implementation-plan.

---

## 8. Phase E: Workers 확장

**목표**: worker-system.md 대비 누락 Worker 구현 또는 “예정” 문서 정리.

### 8.1 선행 조건

- Phase A(인증)·Phase C(Process/이벤트) 완료 권장. Redis Streams 소비 시 스트림 키·포맷 확정 필요.

### 8.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| E1 | Redis Streams 키·포맷 확정 | axiom:events, axiom:watches, axiom:workers 스트림과 sync Worker 발행 포맷을 event-outbox.md와 일치시키고 문서화. | 문서 + sync.py 검증 |
| E2 | watch_cep Worker | axiom:watches 소비, CEP 룰 평가, 알림 생성·발송(WatchAlert 등). Consumer Group. | workers/watch_cep.py |
| E3 | event_log Worker | 이벤트 로그 파이프라인(axiom:workers 또는 전용 스트림) 소비, 파싱/검증 후 Synapse 전달. | workers/event_log.py |
| E4 | ocr / extract / generate Worker (우선순위 낮음) | 문서 상 ocr, extract, generate Worker. 리소스에 따라 구현 또는 “예정” 문서화. | workers/* 또는 문서 |

### 8.3 통과 기준 (Gate E)

- watch_cep·event_log 중 구현한 Worker가 Redis에서 메시지 소비·처리 가능.
- 미구현 Worker는 worker-system.md에 “예정” 표기.

### 8.4 연계

- 03_backend-implementation-plan, 06_data (event-outbox).

---

## 9. Phase F: 문서·운영 정합성

**목표**: 갭 해소 결과를 설계 문서와 구현 상태에 반영.

### 9.1 선행 조건

- Phase A~E 중 수행한 Phase 완료.

### 9.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| F1 | 02_api 문서 구현 상태 태그 갱신 | process-api, watch-api, agent-api, gateway-api의 “Implemented”/“Partial” 표를 실제 구현과 일치시킴. auth, users, cases 경로 반영. | services/core/docs/02_api/*.md |
| F2 | 07_security/auth-model.md 상태 | Core 내 구현 완료 시 “Implemented” 및 실제 경로·설정 반영. 외부 담당 시 “Core 외부” 명시. | auth-model.md |
| F3 | 01_architecture 경로 매핑 갱신 | app/api/auth/, app/api/cases/ 유무, app/bpm/, app/orchestrator/ 유무에 맞게 architecture-overview.md 수정. | architecture-overview.md |
| F4 | worker-system.md Worker 목록 | 구현된 Worker만 “Implemented”, 나머지 “예정” 또는 제거. | worker-system.md |
| F5 | core-docs-vs-implementation-gap.md 갱신 | 해소된 갭은 “해소 완료”로 표시, 잔여 갭과 다음 단계 권장 조치만 유지. | docs/04_status/core-gap-analysis.md |

### 9.3 통과 기준 (Gate F)

- 위 문서들이 현재 코드·라우트·Worker 목록과 불일치 없음.
- 갭 문서가 “갱신일 + 잔여 갭” 구조로 유지됨.

---

## 10. 의존성 요약

```
Phase A (인증) ──┬──> Phase B (사용자/케이스)
                ├──> Phase C (Process·API 보완)
                └──> Phase E (Workers, 일부)
Phase C ────────> Phase D (Domain, 선택)
Phase A,C ──────> Phase E
Phase A~E ──────> Phase F (문서)
```

## 11. 권장 실행 순서

1. **Phase A** 전부 (A1~A7 중 A7은 선택).
2. **Phase C** (C1, C2 필수; C3, C4 선택).
3. **Phase B** (B1 결정 후 B2~B4 중 해당 항목만).
4. **Phase F** (F1~F5) — Phase A·B·C 완료 후 1차 문서 정리.
5. **Phase D** — Domain 분리 도입 시에만.
6. **Phase E** — E1→E2→E3, E4는 우선순위 낮음.
7. **Phase F** 최종 — D·E 반영 후 갭 문서·아키텍처 문서 재갱신.

## 12. 추적성

| 계획 문서 | 연계 Phase |
|----------|------------|
| docs/03_implementation/core/07_security-implementation-plan.md | A, B |
| docs/03_implementation/core/02_api-implementation-plan.md | A, B, C, F |
| docs/03_implementation/core/03_backend-implementation-plan.md | D, E |
| docs/03_implementation/core/01_architecture-implementation-plan.md | D, F |
| docs/04_status/core-gap-analysis.md | F (갱신) |
