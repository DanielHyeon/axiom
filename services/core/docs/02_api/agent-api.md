# Axiom Core - 에이전트 API

> 구현 상태 태그: `Partial (In-memory-backed)`
> 기준일: 2026-02-21
> 최신 근거: `docs/full-spec-gap-analysis-2026-02-22.md`

## 이 문서가 답하는 질문

- 에이전트 관련 API(피드백, MCP, 도구 관리)는 어떻게 사용하는가?
- 피드백이 3티어 지식 저장소에 어떻게 반영되는가?
- MCP 도구를 동적으로 관리하는 API는 무엇인가?

<!-- affects: frontend, llm -->
<!-- requires-update: 05_llm/agent-architecture.md, 05_llm/mcp-integration.md -->

---

## 1. 엔드포인트 목록

| Method | Path | 설명 | 타임아웃 | 상태 | 근거(구현/티켓) |
|--------|------|------|---------|------|------------------|
| POST | `/api/v1/agents/chat` | 에이전트 채팅 메시지 전송 | 120s | Partial | `services/core/app/api/agent/routes.py` |
| POST | `/api/v1/agents/feedback` | 사용자 피드백 제출 | 60s | Partial | `services/core/app/api/agent/routes.py` |
| GET | `/api/v1/agents/feedback/{workitem_id}` | 피드백 상태 조회 | 10s | Partial | `services/core/app/api/agent/routes.py` |
| POST | `/api/v1/completion/complete` | LLM 완성 (범용) | 120s | Partial | `services/core/app/api/agent/routes.py` |
| POST | `/api/v1/completion/vision-complete` | 비전 모델 완성 | 120s | Partial | `services/core/app/api/agent/routes.py` |
| POST | `/api/v1/mcp/config` | MCP 서버 설정 | 30s | Partial | `services/core/app/api/agent/routes.py` |
| GET | `/api/v1/mcp/tools` | 사용 가능한 MCP 도구 목록 | 10s | Partial | `services/core/app/api/agent/routes.py` |
| POST | `/api/v1/mcp/execute-tool` | MCP 도구 실행 | 60s | Partial | `services/core/app/api/agent/routes.py` |
| GET | `/api/v1/agents/knowledge` | 학습된 지식 조회 (Memory/DMN/Skill) | 10s | Partial | `services/core/app/api/agent/routes.py` |
| DELETE | `/api/v1/agents/knowledge/{id}` | 학습된 지식 삭제 | 10s | Partial | `services/core/app/api/agent/routes.py` |

---

## 2. 주요 엔드포인트 상세

### 2.1 POST /api/v1/agents/feedback

사용자 피드백을 제출하면 ReAct 5단계를 거쳐 3티어 지식 저장소에 자동 학습된다.

#### 요청

```json
{
  "workitem_id": "uuid (required) - 피드백 대상 워크아이템",
  "feedback_type": "correction | suggestion | approval",
  "content": "string (required) - 피드백 내용. 예: '이 데이터는 핵심 데이터가 아니라 일반 데이터입니다'",
  "corrected_output": {
    "field_name": "data_type",
    "original_value": "핵심 데이터",
    "corrected_value": "일반 데이터"
  },
  "priority": "low | medium | high"
}
```

유효성 규칙:
- `feedback_type=correction`이면 `corrected_output`은 필수다.
- `priority=high` 충돌 피드백은 자동 반영하지 않고 `422 KNOWLEDGE_CONFLICT_HIGH`를 반환한다.
- `priority=high` 충돌 피드백도 이력은 저장되며, `GET /api/v1/agents/feedback/{workitem_id}`에서 `status=NEEDS_REVIEW`로 조회된다.

#### 응답 (202 Accepted)

```json
{
  "feedback_id": "uuid",
  "status": "PROCESSING",
  "estimated_completion": "2026-02-19T10:00:30Z",
  "message": "피드백을 분석하여 지식에 반영합니다."
}
```

#### 피드백 처리 결과 조회

```
GET /api/v1/agents/feedback/{workitem_id}
```

```json
{
  "feedback_id": "uuid",
  "status": "COMPLETED",
  "analysis": {
    "conflict_level": "LOW",
    "operation": "UPDATE",
    "confidence": 0.85
  },
  "committed_to": [
    {
      "type": "MEMORY",
      "action": "UPDATE",
      "content_preview": "KPI 영향이 없는 데이터는 일반 데이터로 분류..."
    },
    {
      "type": "DMN_RULE",
      "action": "UPDATE",
      "rule_name": "데이터분류규칙",
      "changed_rows": 1
    }
  ]
}
```

---

### 2.2 POST /api/v1/mcp/config

테넌트별 MCP 서버 설정을 관리한다.

#### 요청

```json
{
  "servers": [
    {
      "name": "string (required) - 서버 이름",
      "url": "string (required) - MCP 서버 URL",
      "auth": {
        "type": "bearer | api_key | none",
        "token": "string (auth.type이 bearer/api_key일 때 required)"
      },
      "enabled": true,
      "tool_filter": ["allowed_tool_1", "allowed_tool_2"]
    }
  ]
}
```

#### 응답 (200 OK)

```json
{
  "tenant_id": "uuid",
  "servers_count": 2,
  "total_tools_available": 15,
  "servers": [
    {
      "name": "axiom-skills",
      "url": "http://mcp-skills:8080",
      "status": "CONNECTED",
      "tools_count": 8
    }
  ]
}
```

---

### 2.3 POST /api/v1/mcp/execute-tool

MCP 도구를 직접 실행한다 (에이전트를 통하지 않고 직접 호출).

#### 요청

```json
{
  "tool_name": "string (required)",
  "parameters": {},
  "server_name": "string (optional) - 특정 서버 지정. null이면 자동 선택"
}
```

#### 응답 (200 OK)

```json
{
  "tool_name": "calculate_optimization_rate",
  "server": "axiom-skills",
  "result": { ... },
  "execution_time_ms": 234,
  "cached": false
}
```

---

### 2.4 POST /api/v1/agents/chat

에이전트에게 메시지를 보내고 응답을 받는다. 스트리밍 응답을 지원한다.

#### 요청

```json
{
  "message": "string (required)",
  "context": {
    "case_id": "uuid (optional)",
    "proc_inst_id": "uuid (optional)",
    "workitem_id": "uuid (optional)"
  },
  "stream": true,
  "agent_config": {
    "model": "gpt-4o (optional, default)",
    "temperature": 0.0,
    "max_tokens": 4096
  }
}
```

#### 응답 (SSE 스트리밍, stream=true)

```
data: {"type": "thinking", "content": "데이터 등록 현황을 분석합니다..."}

data: {"type": "tool_call", "tool": "search_records", "input": {"case_id": "..."}}

data: {"type": "tool_result", "tool": "search_records", "output": {"count": 15}}

data: {"type": "response", "content": "해당 프로젝트에 15건의 데이터가 등록되어 있습니다."}

data: {"type": "done", "total_tokens": 1234, "model": "gpt-4o"}
```

#### 응답 (JSON, stream=false)

```json
{
  "response": "해당 프로젝트에 15건의 데이터가 등록되어 있습니다.",
  "tools_used": ["search_records"],
  "confidence": 0.95,
  "sources": [
    {"type": "database", "query": "SELECT count(*) FROM records WHERE case_id = ..."}
  ],
  "usage": {
    "model": "gpt-4o",
    "prompt_tokens": 800,
    "completion_tokens": 434
  }
}
```

---

## 3. 에러 코드

| HTTP | 코드 | 설명 |
|------|------|------|
| 400 | INVALID_FEEDBACK | 피드백 내용이 비어있거나 형식이 잘못됨 |
| 404 | MCP_SERVER_NOT_FOUND | 지정한 MCP 서버를 찾을 수 없음 |
| 404 | MCP_TOOL_NOT_FOUND | 지정한 MCP 도구를 찾을 수 없음 |
| 408 | AGENT_TIMEOUT | 에이전트 응답 시간 초과 (120초) |
| 422 | KNOWLEDGE_CONFLICT_HIGH | 고충돌 수준 - 사람 개입 필요 |
| 502 | LLM_PROVIDER_ERROR | LLM 프로바이더 오류 |
| 503 | MCP_SERVER_UNAVAILABLE | MCP 서버 연결 불가 |

---

## 근거

- K-AIR 역설계 보고서 섹션 8 (에이전트 시스템), 섹션 15.3 (completion API)
- process-gpt-completion-main (multi-agent, mcp 라우터)
- process-gpt-agent-feedback-main (FeedbackProcessor)
- 01_architecture/agent-orchestration.md
