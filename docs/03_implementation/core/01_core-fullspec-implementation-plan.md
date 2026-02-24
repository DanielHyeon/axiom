# Core Full 스펙 구현 계획 (미구현·스텁 항목)

> **근거**: [docs/05_backlog/future-backlog.md](../../future-implementation-backlog.md) (코드 기준), [docs/04_status/core-gap-analysis.md](../../core-docs-vs-implementation-gap.md)  
> **범위**: 현재 스텁이거나 파일이 없어 Full 스펙에 미달한 항목만. 설계 문서를 참조하여 단계별 구현 계획을 수립한다.  
> **작성일**: 2026-02-22  
> **구현 상태 (코드 기준 2026-02 검증)**: **Phase G·H·I·J·K·L·M·N 구현 완료.** H: langgraph_flow 멀티스텝 러너(route→intent별 노드→hitl→complete). K: extract_from_pdf 파일 검증·텍스트(pdfplumber 선택)·청킹·스텁 반환. L: ocr/extract/generate Workers 스켈레톤(axiom:workers 소비·ACK). M: POST/GET users(admin·user:manage·tenant 제한). N: RateLimitMiddleware·gateway-api §4 반영.

---

## 1. 목적

- Core의 **미구현** 또는 **스텁 상태**인 항목을 설계 문서(services/core/docs/)에 맞춰 Full 스펙으로 구현하기 위한 계획.
- Phase별 설계 문서 참조, 티켓, 선행 조건, 통과 기준을 명시.

---

## 2. 참조 설계 문서

| 문서 | 용도 |
|------|------|
| **01_architecture/bpm-engine.md** | BPM 엔진, Workitem 라이프사이클, **Saga 보상** (§5), **BPMN 추출** (§6), 병렬 분기 보상 (§5.5) |
| **01_architecture/agent-orchestration.md** | **LangGraph 10노드** 그래프, OrchestratorState, build_orchestrator_graph, HITL, 에이전트 실행 |
| **01_architecture/event-driven.md** | 이벤트 발행·구독, Watch/Worker 이벤트 타입 |
| **03_backend/worker-system.md** | **watch_cep** CEP·알림 (§3.2), **event_log** 파이프라인·Synapse (§3.6), **ocr/extract/generate** (§3.3–3.5) |
| **05_llm/mcp-integration.md** | MCP 클라이언트, SafeToolLoader, 도구 호출 (Saga 보상에서 사용) |
| **06_data/event-outbox.md** | Redis 스트림 키·Consumer Group·Sync 발행 포맷, event_type→스트림 라우팅 |
| **02_api/watch-api.md** | Watch 구독·알림·규칙, CEP 룰·채널 |
| **02_api/process-api.md** | Process 상태·Workitem, 보상 연동 |
| **99_decisions/ADR-005-saga-compensation.md** | Saga 보상 불변성, 병렬 분기 규칙 |

---

## 3. 갭 요약 (코드 기준)

| 영역 | 현재 상태 (코드) | Full 스펙 (설계 문서) |
|------|------------------|------------------------|
| **Saga** | **구현됨**: 역순 조회·보상 단계 생성·실행, _execute_compensation(MCP), _update_process_status, _publish_event(SAGA_COMPENSATION_COMPLETED). 보상 실패 알림은 로깅. | bpm-engine.md §5.3: 완료 Activity 역순 조회 → 보상 단계 생성 → MCP 실행 → 프로세스 TERMINATED, 이벤트 발행 |
| **BPMN 추출기** | **구현됨(최소)**: extract_from_pdf 파일 검증·pdfplumber 텍스트·청킹·스텁 process_definition/bpmn_xml. LLM Entity/BPMN/DMN 연동은 추후. | bpm-engine.md §6: PDF→텍스트→청킹→EntityExtractor→BPMNGenerator→DMNGenerator→HITL |
| **LangGraph** | **구현됨**: route_intent→process_exec/document_proc/query_data/mining→hitl_check→complete 멀티스텝 러너. query_data는 Oracle POST /text2sql/ask 연동, mining은 state에 case_id·log_id 있을 때 Synapse POST /api/v3/synapse/process-mining/discover 연동. URL·계약: docs/02_api/service-endpoints-ssot.md §2.1. | agent-orchestration.md §2: 10노드 StateGraph, route→process_exec/document_proc/query_data/agent_tools/rag/nl2sql/mining→hitl→complete |
| **agent_loop** | **구현됨**: graph.ainvoke 호출, SUBMITTED/DONE 반환. HITL 시 needs_human_review. | bpm-engine.md §4.3, agent-orchestration: Workitem 실행, HITL 대기, 지식 반영 |
| **MCP/tool_loader** | **구현됨**: app/orchestrator/mcp_client.py, execute_mcp_tool(MCP_BASE_URL·httpx). SafeToolLoader/테넌트 격리는 선택. | mcp-integration.md, agent-orchestration: MCP 클라이언트, SafeToolLoader, Saga _execute_compensation에서 execute_mcp_tool 호출 |
| **watch_cep** | **구현됨**: CEP 룰 평가(_evaluate_rule), WatchService.create_alert, idempotency 24h, _send_alert_channels(인앱=DB; 이메일/SMS/Slack 어댑터 미구현 시 로깅). | worker-system.md §3.2: CEP 룰 평가, 알림 생성/발송(인앱·이메일·SMS·Slack), 중복 방지·에스컬레이션 |
| **event_log** | **구현됨**: MinIO 다운로드, validate_xes/validate_csv, Synapse ingest(multipart), _report_progress·_publish_completion·_report_failure. | worker-system.md §3.6: MinIO 다운로드→형식 검증→청킹→Synapse REST 전달→진행률 발행→PROCESS_LOG_INGESTED |
| **ocr / extract / generate** | **구현됨(스켈레톤)**: app/workers/ocr.py, extract.py, generate.py. axiom:workers 소비·ACK·event_type 라우팅. 파이프라인(MinIO·Vision·LLM) 연동은 추후. | worker-system.md §3.3–3.5: axiom:workers 소비, 파이프라인 구현 |
| **users API** | **구현됨**: GET /me, POST /users(생성), GET /users(목록). admin 또는 user:manage·tenant 제한. | settings-users-api-status, watch-api: POST /users, GET /users 목록, admin (선택) |
| **속도 제한** | **구현됨**: app/core/rate_limiter.py, RateLimitMiddleware. 경로별 limit/window(login 10/분, agents 20/분, 기본 100/분). | gateway-api.md: IP/User 기반 (선택) |
| **app/api/cases/** | **구현됨**: GET /api/v1/cases(목록·tenant·status·페이징), GET /api/v1/cases/activities, POST .../review. core_case, core_case_activity, core_document_review. | gateway-api §2.1, Canvas Phase A/D 연동 |

---

## 4. Phase 개요

| Phase | 목표 | 설계 문서 | 선행 | 상태 |
|-------|------|-----------|------|------|
| **G** | Saga 보상 Full 구현 | bpm-engine.md §5, ADR-005 | Process API·WorkItem DB 안정 | 완료 |
| **H** | Orchestrator + MCP | agent-orchestration.md, mcp-integration.md, bpm-engine §4.3 | G(선택), Agent API 존재 | 완료 |
| **I** | watch_cep CEP·알림 로직 | worker-system.md §3.2, watch-api.md, event-outbox.md | - | 완료 |
| **J** | event_log MinIO·Synapse | worker-system.md §3.6, event-outbox.md | Synapse ingest API 확정 | 완료 |
| **K** | BPMN 추출기 (선택) | bpm-engine.md §6 | 우선순위 낮으면 "예정" 유지 | 완료(최소) |
| **L** | ocr / extract / generate Worker (선택) | worker-system.md §3.3–3.5 | MinIO·DB·Vision 연동 정책 확정 | 완료(스켈레톤) |
| **M** | Users API 확장 (선택) | settings-users-api-status, watch-api | B1 결정: Core 담당 시 | 완료 |
| **N** | (선택) 속도 제한·문서 | gateway-api.md | - | 완료 |

---

## 5. Phase G: Saga 보상 Full 구현

**목표**: app/bpm/saga.py의 trigger_compensation을 설계대로 동작하도록 구현. 완료 Activity 역순 조회 → 보상 단계 생성 → 실행 → 프로세스 상태·이벤트 반영.

### 5.1 참조 설계

- **bpm-engine.md** §5.2–5.3: 보상 흐름, SagaManager 구현 예시 (_get_completed_activities, _execute_compensation, _notify_compensation_failure, _update_process_status, _publish_event).
- **bpm-engine.md** §5.5: 병렬 분기 보상 (Phase 1 취소 → Phase 2 완료 분기 보상 → Phase 3 분기 이전 역순).
- **ADR-005-saga-compensation.md**: 병렬 분기 불변성, CANCELLED/COMPENSATED 처리.
- **mcp-integration.md**: _execute_compensation에서 MCP 도구 호출 (execute_mcp_tool).

### 5.2 선행 조건

- Process API·WorkItem·ProcessDefinition·RoleBinding 등 DB/서비스가 안정 동작.
- (선택) MCP 클라이언트 또는 보상 액션을 위한 내부 서비스 호출 경로 존재.

### 5.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| G1 | 완료 Activity 역순 조회 | proc_inst_id, up_to=failed_activity_id 기준으로 완료된 Activity 목록 조회. process_service 또는 WorkItem/정의 조합. | saga.py _get_completed_activities |
| G2 | 보상 단계 생성·실행 | CompensationStep 생성(activity.compensation, compensation_data). _execute_compensation에서 MCP 또는 내부 서비스 호출. | saga.py _execute_compensation, execute_mcp_tool 연동 또는 스텁 대체 |
| G3 | 보상 실패 알림 | _notify_compensation_failure 구현 (Watch 알림 또는 이벤트 발행). | saga.py _notify_compensation_failure |
| G4 | 프로세스 상태·이벤트 | TERMINATED 등 상태 업데이트, SAGA_COMPENSATION_COMPLETED 이벤트 발행(EventPublisher). | saga.py, process_service 연동 |
| G5 | 병렬 분기 보상 (선택) | _group_by_parallel, _handle_parallel_compensation, _cancel_workitem. bpm-engine §5.5. | saga.py 확장 |

### 5.4 통과 기준 (Gate G)

- trigger_compensation 호출 시 완료된 Activity가 있으면 보상 단계가 생성·실행되며, status가 STUB가 아닌 EXECUTED/FAILED 등으로 반환된다.
- 프로세스 인스턴스 상태가 TERMINATED로 갱신되고, 이벤트가 Outbox에 기록된다(선택 시 Redis까지 발행).

---

## 6. Phase H: Orchestrator + MCP

**목표**: LangGraph 10노드 그래프 구현, agent_loop와 연동, MCP/tool_loader 도입.

### 6.1 참조 설계

- **agent-orchestration.md** §2.1–2.2: 10노드 그래프(route, process_exec, document_proc, query_data, agent_tools, rag_search, nl2sql, process_mining_analysis, hitl_check, complete), OrchestratorState, build_orchestrator_graph.
- **bpm-engine.md** §4.3: execute_workitem_with_agent, build_agent_for_activity, load_tools_for_activity, HITL 시 SUBMITTED·save_workitem_draft.
- **mcp-integration.md**: MCP 클라이언트, SafeToolLoader, 테넌트별 도구 격리.

### 6.2 선행 조건

- Agent API(agent/routes.py) 존재. (선택) Phase G로 Saga 연동 시 에이전트 실패 시 trigger_compensation 호출 가능.

### 6.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| H1 | MCP 클라이언트·tool_loader | mcp-integration.md에 따른 MCP 클라이언트 모듈. SafeToolLoader(차단 목록·테넌트 격리). app/orchestrator/tool_loader.py 또는 mcp_client.py. | app/orchestrator/ 또는 app/llm/ |
| H2 | LangGraph StateGraph 빌드 | OrchestratorState, 10노드 등록, 조건부 엣지, interrupt_before(hitl_check). agent-orchestration §2.2 코드 예시 참고. | langgraph_flow.py build_orchestrator_graph |
| H3 | 노드 함수 스텁→실연동 | route_intent, execute_bpm_activity, process_document, query_data, execute_agent_tools, perform_rag_search, call_oracle_service, execute_process_mining, check_human_review, finalize_result. query_data: Oracle POST /text2sql/ask(body: question, datasource_id, options). mining: Synapse POST /api/v3/synapse/process-mining/discover(case_id, log_id 필수). SSOT: docs/02_api/service-endpoints-ssot.md §2.1. | langgraph_flow.py 노드 구현 |
| H4 | agent_loop 연동 | run_agent_loop에서 build_orchestrator_graph().ainvoke 호출, Workitem 상태 업데이트(IN_PROGRESS→SUBMITTED/DONE), HITL 시 대기. | agent_loop.py |
| H5 | process_service에서 에이전트 실행 경로 | SUPERVISED/AUTONOMOUS Activity에 대해 orchestrator 실행 호출, 실패 시 Saga trigger_compensation 호출. | process_service 또는 별도 agent_executor |

### 6.4 통과 기준 (Gate H)

- build_orchestrator_graph()가 None이 아닌 컴파일된 StateGraph(또는 Runnable)를 반환한다.
- run_agent_loop()가 실제 그래프 1회 실행 후 결과를 반환하며, STUB 메시지가 아니다.
- (선택) Workitem 제출 시 에이전트 모드에 따라 LangGraph가 실행된다.

---

## 7. Phase I: watch_cep CEP·알림 로직

**목표**: watch_cep Worker의 _handle_message를 CEP 룰 평가·알림 생성·발송까지 구현.

### 7.1 참조 설계

- **worker-system.md** §3.2: axiom:watches 소비, CEP 룰 평가, 알림(인앱·이메일·SMS·Slack), 중복 방지(idempotency_key, 24h TTL), CRITICAL 1시간 미확인 에스컬레이션, 실패 시 3회 재시도·FAILED 기록.
- **event-outbox.md** §2.2: axiom:watches 메시지 필드(event_type, aggregate_id, payload 등).
- **watch-api.md**: 구독·룰·알림 CRUD, SSE 스트림. 알림 생성 시 WatchAlert 모델·DB 및 SSE 푸시.

### 7.2 선행 조건

- WatchRule·WatchAlert·WatchSubscription 모델·API 존재. Redis axiom:watches 스트림에 이벤트가 Sync Worker에 의해 발행됨.

### 7.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| I1 | CEP 룰 평가 | payload 기반 event_type·aggregate_id로 해당 구독·룰 매칭. worker-system §3.2 룰 타입(deadline, threshold, pattern). | watch_cep.py _evaluate_rules |
| I2 | 알림 생성·DB 저장 | WatchAlert 레코드 생성, idempotency_key로 24시간 중복 방지. severity·channels 결정. | watch_cep.py, watch_service 또는 DB 직접 |
| I3 | 알림 발송 채널 | 인앱(SSE는 기존 /watches/stream), 이메일/SMS/Slack 등 외부 발송(서비스 또는 큐). 실패 시 3회 재시도 후 FAILED. | watch_cep.py _send_alert |
| I4 | CRITICAL 에스컬레이션 (선택) | 1시간 미확인 시 에스컬레이션 이벤트 발행 또는 상위 알림 생성. | watch_cep.py 또는 별도 스케줄러 |

### 7.4 통과 기준 (Gate I)

- axiom:watches에 WATCH_* 이벤트가 들어왔을 때 _handle_message가 CEP 룰을 평가하고, 조건 충족 시 알림이 DB에 생성되며 인앱(SSE) 또는 지정 채널로 전달된다.
- Worker docstring의 “CEP·알림 로직은 추후 구현”이 제거된 상태로 동작한다.

---

## 8. Phase J: event_log MinIO·Synapse

**목표**: event_log Worker의 _process_event_log_request를 MinIO 다운로드→파싱/검증→청킹→Synapse 전달→진행률 발행까지 구현.

### 8.1 참조 설계

- **worker-system.md** §3.6: 파이프라인(MinIO 스트리밍 다운로드, 형식 판별 XES/CSV, 검증, 10_000 이벤트 청킹, Synapse REST /api/v1/event-logs/ingest, 진행률 Redis axiom:process_mining, PROCESS_LOG_INGESTED 발행). XESStreamParser, CSVStreamParser, case 경계 보장.
- **event-outbox.md**: axiom:workers 메시지 포맷, WORKER_EVENT_LOG_REQUEST payload(file_path, format, estimated_total 등).

### 8.2 선행 조건

- Synapse 쪽 event-logs/ingest API(또는 동등) 스펙 확정. MinIO 설정·payload 내 file_path 규약 확정.

### 8.3 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| J1 | MinIO 스트리밍 다운로드 | payload.file_path로 MinIO에서 스트리밍 다운로드. | event_log.py _download_from_minio |
| J2 | XES/CSV 파서·검증 | worker-system §3.6 예시: validate, parse_chunks. case 경계 보장. | event_log.py 또는 parsers/ 서브모듈 |
| J3 | Synapse ingest 연동 | 청크별 POST Synapse, event_log_id·chunk_index·events. | event_log.py _send_chunk_to_synapse |
| J4 | 진행률·완료 이벤트 | Redis axiom:process_mining에 MINING_PROGRESS, PROCESS_LOG_INGESTED 발행. | event_log.py _report_progress, _publish_completion |

### 8.4 통과 기준 (Gate J)

- WORKER_EVENT_LOG_REQUEST 메시지 수신 시 MinIO에서 파일을 받아 파싱·검증 후 Synapse로 청크 전달되며, 진행률/완료 이벤트가 발행된다.
- Worker docstring의 “MinIO·Synapse 전달은 추후 구현”이 제거된 상태로 동작한다.

---

## 9. Phase K: BPMN 추출기 (선택)

**목표**: app/bpm/extractor.py를 bpm-engine.md §6 파이프라인에 맞게 구현. 우선순위 낮으면 “예정” 문서만 정리.

### 9.1 참조 설계

- **bpm-engine.md** §6.1–6.2: PDF→텍스트(pdfplumber)→청킹(800 토큰)→EntityExtractor(GPT-4o)→BPMNGenerator→DMNGenerator→HITL 검토→ProcessDefinition JSON + BPMN XML.

### 9.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| K1 | 텍스트 추출·청킹 | pdf_path → pdfplumber 텍스트 → 800 토큰 청킹. | extractor.py |
| K2 | EntityExtractor·BPMN/DMN 생성 | GPT-4o Structured Output으로 엔티티 추출, BPMN/DMN XML 생성. | extractor.py 또는 별도 모듈 |
| K3 | extract_from_pdf API 노출 | Process 정의 생성 API 또는 내부 호출. HITL 검토(신뢰도<80% 수동 검토) 연동은 선택. | extractor.py, process 또는 gateway 연동 |

### 9.3 통과 기준 (Gate K)

- extract_from_pdf(pdf_path) 호출 시 NotImplementedError 없이 ProcessDefinition·BPMN XML(및 선택 DMN)이 반환된다.

---

## 10. Phase L: ocr / extract / generate Worker (선택)

**목표**: worker-system.md §3.3–3.5에 따른 Worker 파일 추가 및 axiom:workers 소비·처리. 리소스에 따라 구현 또는 “예정” 문서 유지.

### 10.1 참조 설계

- **worker-system.md** §3.3 OCR: WORKER_OCR_REQUEST → MinIO 다운로드 → Textract/GPT-4o Vision → DB documents 업데이트 → WORKER_OCR_COMPLETED.
- **worker-system.md** §3.4 Extract: WORKER_EXTRACT_REQUEST → OCR 텍스트 로드 → 청킹 → GPT-4o Structured Output → pgvector·DB → WORKER_EXTRACT_COMPLETED.
- **worker-system.md** §3.5 Generate: WORKER_GENERATE_REQUEST → LLM·템플릿 렌더링 → MinIO 저장 → WORKER_GENERATE_COMPLETED.
- **event-outbox.md**: axiom:workers, event_type 라우팅.

### 10.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| L1 | ocr Worker | workers/ocr.py, BaseWorker 상속, axiom:workers 소비, WORKER_OCR_REQUEST 처리. | workers/ocr.py |
| L2 | extract Worker | workers/extract.py, WORKER_EXTRACT_REQUEST, 청킹·구조화·pgvector. | workers/extract.py |
| L3 | generate Worker | workers/generate.py, WORKER_GENERATE_REQUEST, LLM·템플릿·MinIO. | workers/generate.py |

### 10.3 통과 기준 (Gate L)

- 각 Worker가 해당 event_type 메시지를 소비·처리하고, 출력(DB/MinIO) 및 완료 이벤트가 설계와 일치한다. 미구현 시 worker-system.md에 “예정” 유지.

---

## 11. Phase M: Users API 확장 (선택)

**목표**: GET /users/me 외 POST /users, GET /users 목록, (선택) admin 사용자 관리. 설계·정책에 따라 Core 담당 시에만 진행.

### 11.1 참조 설계

- **docs/04_status/settings-users-api-status.md**: POST /users(생성), GET /users(목록), Watch 구독 시드·admin API.
- **watch-api.md**: 사용자 생성 시 구독 시드 연동.

### 11.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| M1 | POST /api/v1/users | 사용자 생성, 비밀번호 해시, Tenant 연결. (선택) Watch 기본 구독 시드. | users/routes.py |
| M2 | GET /api/v1/users | 목록·필터·페이징. JWT 권한(admin 또는 본인 tenant). | users/routes.py |
| M3 | admin/users (선택) | GET/POST/PATCH admin 전용 경로. | users/routes.py 또는 admin/ |

### 11.4 통과 기준 (Gate M)

- 결정된 Users API가 설계 문서와 일치하게 동작한다.

---

## 12. Phase N: (선택) 속도 제한·문서

**목표**: gateway-api.md에 따른 속도 제한 미들웨어. 적용 시 IP/User 기반 제한, 429 응답.

### 12.1 참조 설계

- **02_api/gateway-api.md**: 보호 경로, 속도 제한 미들웨어 “미구현(선택)” 명시.

### 12.2 티켓

| ID | 제목 | 설명 | 산출 |
|----|------|------|------|
| N1 | Rate limit 미들웨어 | slowapi 또는 동등, 경로별 제한(예: /auth/login 5/분). | app/core/ 또는 middleware |
| N2 | 문서 갱신 | gateway-api.md “속도 제한 미들웨어” Implemented 또는 유지. | gateway-api.md |

---

## 13. 권장 실행 순서

1. **Phase I (watch_cep)** 또는 **Phase J (event_log)** — Worker 스텁 제거가 즉시 가치가 있을 때.
2. **Phase G (Saga)** — Process 안정 후 보상 트랜잭션이 필요할 때.
3. **Phase H (Orchestrator + MCP)** — 에이전트 자동 실행·HITL이 핵심일 때.
4. **Phase K, L** — 리소스·우선순위에 따라 구현 또는 “예정” 문서 유지.
5. **Phase M, N** — 정책 확정 후 (Users 확장, Rate limit).

---

## 14. 문서 갱신

- 각 Phase 완료 시 **core-docs-vs-implementation-gap.md** 해당 행을 “해소”로 갱신.
- **worker-system.md** Worker 목록의 “예정”/“스텁” 표기를 구현 상태에 맞게 수정.
- **future-implementation-backlog.md** Core 섹션을 코드 재검증 후 갱신.
