# Core ↔ 프론트엔드(Canvas) 구현 연동 현황

> **기준**: `services/core` 제공 API vs `apps/canvas/src` 호출 구현  
> **작성일**: 2026-02-22  
> **갱신**: 2026-02-22 — Process 전부, Users/me, Agent/MCP API 클라이언트 및 설정 페이지 연동 완료.

---

## 1. 결론

**Core 제공 API에 대응하는 Canvas API 클라이언트 및 호출부 구현이 완료되었습니다.**  
Auth·Watch·Health·Process(목록/생성/단건/실행 전부)·Users/me·Agent·MCP·Completion·Chat·Knowledge 연동 완료. (실제 프로세스 실행/에이전트 UI에서의 사용은 각 feature에서 위 API를 호출하면 됨.)

---

## 2. Core API별 연동 여부

### 2.1 인증·헬스 (공개)

| Core API | Canvas 연동 | 비고 |
|----------|-------------|------|
| `POST /api/v1/auth/login` | ✅ | `LoginPage` → authStore.login, 토큰·user 저장 |
| `POST /api/v1/auth/refresh` | ✅ | `authStore.refreshAccessToken`, 401 시 재시도 |
| `GET /api/v1/health/*` | ✅ | `settingsApi`(ready), `health.ts`(live) |

### 2.2 Process API (보호)

| Core API | Canvas 연동 | 비고 |
|----------|-------------|------|
| `GET /api/v1/process/definitions` | ✅ | `processApi.listProcessDefinitions` |
| `POST /api/v1/process/definitions` | ✅ | `processApi.createProcessDefinition` |
| `GET /api/v1/process/definitions/{id}` | ✅ | `processApi.getProcessDefinition` |
| `POST /api/v1/process/initiate` | ✅ | `processApi.initiateProcess` |
| `POST /api/v1/process/submit` | ✅ | `processApi.submitWorkitem` |
| `POST /api/v1/process/role-binding` | ✅ | `processApi.roleBinding` |
| `GET /api/v1/process/{proc_inst_id}/status` | ✅ | `processApi.getProcessStatus` |
| `GET /api/v1/process/{proc_inst_id}/workitems` | ✅ | `processApi.getWorkitems` |
| `GET /api/v1/process/feedback/{workitem_id}` | ✅ | `processApi.getProcessFeedback` |
| `POST /api/v1/process/rework` | ✅ | `processApi.reworkWorkitem` |
| `POST /api/v1/process/approve-hitl` | ✅ | `processApi.approveHitl` |

→ **Process API 전부 연동 완료.**

### 2.3 Watch API (보호)

| Core API | Canvas 연동 | 비고 |
|----------|-------------|------|
| `GET /api/v1/watches/alerts` | ✅ | `watch.ts` getAlerts |
| `PUT /api/v1/watches/alerts/{id}/acknowledge` | ✅ | acknowledgeAlert |
| `PUT /api/v1/watches/alerts/read-all` | ✅ | markAllAlertsRead |
| `GET/POST/PUT/DELETE /api/v1/watches/rules` | ✅ | rules CRUD |
| `GET /api/v1/watches/stream` (SSE) | ✅ | `wsManager.ts` EventSource, token 쿼리 |

→ **Watch는 전부 연동됨.**

### 2.4 Users API (보호)

| Core API | Canvas 연동 | 비고 |
|----------|-------------|------|
| `GET /api/v1/users/me` | ✅ | `usersApi.getCurrentUser`, 설정 > 사용자 페이지 마운트 시 호출·authStore 동기화 |

→ **Users/me 연동 완료.**

### 2.5 Agent / MCP API (보호)

| Core API | Canvas 연동 | 비고 |
|----------|-------------|------|
| `POST /api/v1/agents/feedback` | ✅ | `agentApi.submitAgentFeedback` |
| `GET /api/v1/agents/feedback/{workitem_id}` | ✅ | `agentApi.getAgentFeedback` |
| `POST /api/v1/mcp/config` | ✅ | `agentApi.configureMcp` |
| `GET /api/v1/mcp/tools` | ✅ | `agentApi.listMcpTools` |
| `POST /api/v1/mcp/execute-tool` | ✅ | `agentApi.executeMcpTool` |
| `POST /api/v1/completion/complete` | ✅ | `agentApi.completionComplete` |
| `POST /api/v1/completion/vision-complete` | ✅ | `agentApi.completionVisionComplete` |
| `POST /api/v1/agents/chat` | ✅ | `agentApi.agentChat` (stream=false) |
| `GET /api/v1/agents/knowledge` | ✅ | `agentApi.listKnowledge` |
| `DELETE /api/v1/agents/knowledge/{id}` | ✅ | `agentApi.deleteKnowledge` |

→ **Agent/MCP/Completion/Chat/Knowledge API 클라이언트 연동 완료.**

### 2.6 Gateway / Events

- Core는 `/api/v1/gateway/**`, `/api/v1/events/**` 등 프록시/이벤트 라우트 제공.
- Canvas는 Vision/Oracle/Synapse/Weaver 등을 각 feature에서 해당 서비스 URL로 호출하는 구조. Core Gateway 경로 직접 호출 여부는 feature별로 상이.

---

## 3. 구현 완료 요약

| 영역 | 상태 | 비고 |
|------|------|------|
| Process | ✅ | `processApi.ts` — 정의 목록/생성/단건, initiate, submit, roleBinding, status, workitems, feedback, rework, approveHitl |
| Users | ✅ | `usersApi.ts` — getCurrentUser; 설정 > 사용자 페이지에서 마운트 시 호출 |
| Agent/MCP | ✅ | `agentApi.ts` — feedback, mcp config/tools/execute, completion, chat, knowledge |

프로세스 실행·에이전트 채팅 등 **화면/플로우**에서는 위 API를 import해 호출하면 됨. (스트리밍 채팅은 `stream: true` 시 EventSource 등 별도 처리 필요.)

---

## 4. 파일 위치

- `apps/canvas/src/lib/api/processApi.ts` — Process 전부
- `apps/canvas/src/lib/api/usersApi.ts` — GET /users/me
- `apps/canvas/src/lib/api/agentApi.ts` — Agent, MCP, Completion, Chat, Knowledge
- `apps/canvas/src/pages/settings/SettingsUsersPage.tsx` — 마운트 시 getCurrentUser() 호출

---

## 5. 참조

- Core API 스펙: `services/core/docs/02_api/` (process-api, watch-api, gateway-api), `07_security/auth-model.md`
- 사용자 API 책임: `docs/04_status/settings-users-api-status.md`
- 프론트 설계 대비 갭: `docs/04_status/frontend-gap-analysis.md`
