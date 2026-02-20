# Axiom Core - 시스템 개요

## 이 문서가 답하는 질문

- Axiom Core는 무엇이고, 왜 존재하는가?
- 시스템이 해결하는 핵심 문제는 무엇인가?
- 어떤 사용자가 이 시스템을 사용하는가?
- AI/LLM은 어디에, 왜 사용되는가?
- 주요 용어의 정의는 무엇인가?

<!-- affects: all modules -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

---

## 1. 프로젝트 개요

### 1.1 Axiom이란

Axiom은 **비즈니스 프로세스 인텔리전스**를 위한 AI 데이터 플랫폼이다. 의사결정권자, 프로세스 분석가, 이해관계자, 도메인 전문가가 엔터프라이즈 운영 전반에서 AI 기반 자동화와 의사결정 지원을 제공한다.

**핵심 비전**:

```
"비즈니스 프로세스의 비정형 데이터를 구조화하고,
 AI 에이전트가 프로세스를 자동 실행하며,
 사람은 판단과 의사결정에 집중한다."
```

### 1.2 Axiom Core의 역할

Axiom Core는 Axiom 플랫폼의 **중앙 신경계(Central Nervous System)**이다. 전체 6개 모듈(Core, Vision, Oracle, Synapse, Weaver, Canvas) 중 Core는 다음을 담당한다:

| 책임 영역 | 설명 |
|-----------|------|
| **인증/인가** | JWT 기반 인증, RBAC 권한 관리, 멀티테넌트 격리 |
| **API Gateway** | 모든 외부 요청의 단일 진입점, 라우팅, 속도 제한 |
| **서비스 오케스트레이션** | 모듈 간 동기/비동기 통신 조율 |
| **BPM 엔진** | 비즈니스 프로세스를 BPMN 기반으로 정의하고 자동 실행 |
| **에이전트 오케스트레이션** | LangGraph 기반 멀티에이전트 조율, HITL 중단점 관리 |
| **이벤트 버스** | Redis Streams 기반 Event Outbox 패턴으로 모듈 간 비동기 통신 |
| **Watch Agent** | CEP(Complex Event Processing) 기반 실시간 이벤트 감시/알림 |
| **Worker 관리** | OCR, 문서 추출, 문서 생성, 동기화, CEP 처리 워커 |
| **이벤트 로그 수집** | XES/CSV 파일 업로드, DB 연결을 통한 프로세스 마이닝용 이벤트 로그 수집 및 Synapse 라우팅 |

### 1.3 프로젝트 계보

Axiom Core는 K-AIR/Process-GPT 시스템(uengine-oss 조직의 18개 저장소)의 핵심 로직을 이식하여 구축한다.

```
K-AIR/Process-GPT (18개 저장소, Java+Python+Vue3)
        |
        | 로직 이식 + 프레임워크 교체
        v
Axiom Core (단일 FastAPI 서비스, Python)
```

**이식 대상 저장소 매핑**:

| K-AIR 저장소 | Core 내 위치 | 이식 범위 |
|-------------|-------------|----------|
| process-gpt-completion-main | `app/bpm/`, `app/orchestrator/` | BPM 엔진, Saga 보상, LLM 통합 |
| process-gpt-gs-main/gateway | `app/core/security.py` | JWT 인증 (Spring Boot -> FastAPI 재작성) |
| process-gpt-a2a-orch-main | `app/orchestrator/` | A2A -> LangGraph 멀티에이전트 전환 |
| process-gpt-agent-feedback-main | `app/orchestrator/agent_loop.py` | 3티어 지식 학습 루프 |
| process-gpt-crewai-action-main | `app/orchestrator/` | CrewAI -> LangGraph Tool 전환 |
| process-gpt-langchain-react-main | `app/orchestrator/` | ReAct + MCP 패턴 직접 활용 |
| process-gpt-memento-main | `app/workers/extract.py` | 문서 파싱 로직 참조 |
| process-gpt-bpmn-extractor-main | `app/bpm/extractor.py` | PDF -> BPMN 추출 파이프라인 |
| process-gpt-main | `db/`, `infra/` | DB 스키마, K8s 매니페스트 참조 |
| robo-data-text2sql-main (CEP 부분) | `app/workers/watch_cep.py` | SimpleCEP 이벤트 감지 엔진 |

---

## 2. 해결하는 문제

### 2.1 도메인 문제

엔터프라이즈 비즈니스 프로세스는 다음과 같은 근본적 어려움을 가진다:

| 문제 | 현재 상태 | Axiom의 해결 방식 |
|------|----------|-----------------|
| **비정형 데이터 과다** | 분석 보고서, 운영 문서, 계약서 등 수백 장의 PDF/HWP 문서를 수작업 처리 | OCR + GPT-4o Vision으로 자동 구조화, RAG 기반 즉시 검색 |
| **프로세스 복잡성** | 요청 접수 -> 데이터 등록 -> 분석 보고서 -> 이해관계자 리뷰 -> 최적화 시나리오의 다단계 절차를 수동 추적 | BPM 엔진이 프로세스를 BPMN으로 정의하고 자동 진행 |
| **기한 관리 실패** | 핵심 기한 도과 시 비즈니스 불이익 발생 | Watch Agent가 기한 7일/3일/1일 전 자동 알림 |
| **최적화 시나리오** | 다양한 시나리오를 수작업 Excel로 비교 | What-if 시뮬레이션으로 최적 시나리오 자동 추천 |
| **데이터 격리 미흡** | 프로젝트 간 데이터 혼재 위험 | RLS + ContextVar 기반 멀티테넌트로 완전 격리 |

### 2.2 기술 문제

| 문제 | K-AIR의 한계 | Axiom Core의 해결 |
|------|-------------|-----------------|
| **18개 저장소 분산** | 일관성 없는 인증, 중복 코드, 배포 복잡성 | 6개 모듈 모노레포로 통합, Core가 단일 인증/라우팅 |
| **Spring Boot + FastAPI 혼용** | Gateway가 Java, 서비스가 Python - 기술 스택 분리 | 전체 Python (FastAPI) 통일 |
| **CrewAI + A2A SDK 복잡성** | 에이전트 간 통신이 HTTP 폴링 기반, 디버깅 어려움 | LangGraph 단일 프레임워크로 에이전트 통합 |
| **메시지 큐 부재** | 서비스 간 직접 HTTP 호출, 장애 전파 위험 | Redis Streams Event Outbox로 비동기 decoupling |
| **테스트 커버리지 낮음** | 일부 모듈만 테스트 존재 | pytest 기반 체계적 테스트 (단위/통합/E2E) |

---

## 3. 사용자 유형

### 3.1 시스템 사용자

| 사용자 유형 | 역할 | Core 관련 기능 |
|------------|------|---------------|
| **프로세스 분석가(Analyst)** | 비즈니스 프로세스 관리자 | 케이스 관리, BPM 워크플로우 실행, 보고서 생성 승인 |
| **도메인 전문가(Expert)** | 이해관계자/대상 조직 대리인 | 데이터 등록/검증, 문서 검토, 최적화 시나리오 분석 |
| **의사결정권자(Decision Maker)** | 프로젝트 감독, 승인 결정 | 대시보드 모니터링, 보고서 검토, 기한 관리 |
| **이해관계자(Stakeholder)** | 프로세스 참여, 결과 수신 | 현황 조회, 리뷰 참여, 알림 수신 |
| **시스템 관리자(Admin)** | 플랫폼 운영, 테넌트 관리 | 테넌트 생성/관리, 사용자 관리, 시스템 모니터링 |

### 3.2 시스템 소비자 (Machine-to-Machine)

| 소비자 | 역할 | 통신 방식 |
|--------|------|----------|
| **Axiom Canvas** | 웹 프론트엔드 | REST API + WebSocket |
| **Axiom Vision** | 분석 엔진 | REST API (Core가 호출) |
| **Axiom Oracle** | NL2SQL 엔진 | REST API (Core가 호출) |
| **Axiom Synapse** | 온톨로지 엔진 + 프로세스 마이닝 | REST API (Core가 호출), 이벤트 로그 수집 라우팅 |
| **Axiom Weaver** | 데이터 패브릭 | REST API (Core가 호출) |
| **LLM 프로바이더** | OpenAI, Anthropic, Google | HTTPS API (Core가 호출) |

---

## 4. AI/LLM 사용 범위

### 4.1 Core 내 LLM 사용 포인트

| 기능 | LLM 모델 | 프레임워크 | 용도 |
|------|---------|-----------|------|
| **프로세스 정의 생성** | GPT-4o / Claude | LangChain | 자연어 -> BPMN 프로세스 정의 변환 |
| **에이전트 태스크 실행** | GPT-4o | LangGraph (ReAct) | 서비스/스크립트 태스크의 AI 자동 실행 |
| **피드백 -> 지식 학습** | GPT-4o | LangChain (ReAct 5단계) | 사용자 피드백 분석 -> Memory/DMN/Skill 자동 학습 |
| **문서 구조화** | GPT-4o Vision | LangChain | PDF/HWP 문서 -> 구조화된 데이터 추출 |
| **BPMN 추출** | GPT-4o | LangGraph | 업무 매뉴얼 PDF -> BPMN/DMN 자동 생성 |
| **MCP 도구 실행** | GPT-4o | LangGraph + MCP | 외부 도구(Skill, DMN, Mem0)를 에이전트가 호출 |
| **Saga 보상** | GPT-4o | LangGraph | 프로세스 실패 시 MCP 도구로 자동 롤백 판단 |

### 4.2 LLM은 비결정적(Non-deterministic) 시스템이다

LLM 통합 시 핵심 원칙:

```
[결정] LLM 출력은 항상 검증한다.
[결정] 신뢰도 3단계 (99%+: 자동, 80%+: 확인, <80%: 수동)로 위험을 관리한다.
[결정] LLM 실패는 시스템 장애가 아닌 "에이전트 태스크 실패"로 처리한다.
[결정] 모든 LLM 호출에 타임아웃(30초)과 재시도(3회) 정책을 적용한다.
[결정] LLM 응답의 구조적 검증은 Pydantic Structured Output으로 강제한다.
```

자세한 내용은 [05_llm/llm-integration.md](../05_llm/llm-integration.md) 참조.

---

## 5. 기술 스택

### 5.1 Core 기술 스택 요약

| 분류 | 기술 | 버전 | 선택 근거 |
|------|------|------|----------|
| **Runtime** | Python | 3.12+ | AI/ML 생태계, FastAPI 호환 |
| **Web Framework** | FastAPI | 0.115+ | 비동기 지원, 타입 안전, OpenAPI 자동 생성 |
| **인증** | python-jose (JWT) | 3.3+ | Spring JJWT 대체, RS256/HS256 지원 |
| **ORM** | SQLAlchemy | 2.0+ | 비동기 지원, Alembic 마이그레이션 |
| **DB 드라이버** | asyncpg | 0.30+ | PostgreSQL 비동기 고성능 드라이버 |
| **LLM Framework** | LangChain + LangGraph | 0.3.x + 0.2.x | ReAct 패턴, 멀티에이전트, HITL |
| **에이전트 프로토콜** | MCP (FastMCP) | 1.9+ | 도구 격리, 보안 정책, 동적 로딩 |
| **메시지 큐** | Redis Streams | 7.0+ | Event Outbox, at-least-once 전달 보장 |
| **검색** | pgvector | 0.7+ | 벡터 유사도 검색 (문서 임베딩) |
| **그래프 DB** | Neo4j | 5.x | 관계 탐색, FK 그래프, 벡터 인덱스 |
| **모니터링** | OpenTelemetry + LangSmith | - | 분산 추적, LLM 호출 모니터링 |

### 5.2 이식 시 기술 전환 매트릭스

| 영역 | K-AIR (원본) | Axiom Core (전환 후) | 전환 전략 |
|------|-------------|---------------------|----------|
| API Gateway | Spring Boot + JJWT | FastAPI + python-jose | JWT 필터 로직 이식, 라우팅 규칙 YAML화 |
| DB 접근 | Supabase Client SDK | SQLAlchemy + asyncpg | RLS 정책 동일, 마이그레이션은 Alembic |
| 에이전트 | CrewAI + A2A SDK | LangGraph + LangChain | CrewAI Flow -> LangGraph 노드 전환 |
| 인증 | Keycloak + Supabase Auth | 자체 JWT + RBAC | Keycloak 토큰 구조 참조 |
| 메시지 큐 | (없음 - 직접 HTTP 호출) | Redis Streams | Axiom Event Outbox 패턴 신규 적용 |
| 멀티테넌트 | ContextVar (동일) | ContextVar (동일) | 그대로 활용 |

---

## 6. 시스템 경계

### 6.1 Core의 책임 범위

```
Core가 하는 것:
  + 인증/인가 (JWT 발급/검증, RBAC 평가)
  + API Gateway (요청 라우팅, 속도 제한, CORS)
  + BPM 엔진 (프로세스 정의/실행/보상)
  + 에이전트 오케스트레이션 (LangGraph 멀티에이전트)
  + Event Outbox (이벤트 발행, Redis Streams)
  + Watch Agent (CEP 룰 평가, 알림 발송)
  + Worker 관리 (OCR, 추출, 생성, 동기화, CEP)
  + MCP 도구 관리 (SafeToolLoader, 도구 우선순위)
  + 3티어 지식 학습 (Memory/DMN/Skills)
  + 이벤트 로그 수집 (XES/CSV 업로드, DB 연결, Synapse 라우팅)

Core가 하지 않는 것:
  - What-if 시뮬레이션 -> Axiom Vision
  - OLAP 피벗 분석 -> Axiom Vision
  - NL2SQL 변환 -> Axiom Oracle
  - 온톨로지/지식그래프 -> Axiom Synapse
  - 데이터 패브릭 -> Axiom Weaver
  - 웹 UI 렌더링 -> Axiom Canvas
```

### 6.2 모듈 간 통신

```
Canvas ----HTTP/WS----> Core ----HTTP----> Vision / Oracle / Synapse / Weaver
  |                       |
  | (이벤트 로그 업로드)   +--publish--> [Redis Streams: event_outbox]
  +--multipart/form--->   |                  |
     XES/CSV 파일         |                  +--consume--> Vision (이벤트 반응)
                          |                  +--consume--> Synapse (온톨로지 갱신)
                          |
                          +--publish--> [Redis Streams: watch_events]
                          |                  |
                          |                  +--consume--> Canvas (SSE 알림)
                          |
                          +--publish--> [Redis Streams: process_mining_events]
                          |                  |
                          |                  +--consume--> Synapse (프로세스 마이닝)
                          |                  +--consume--> Canvas (마이닝 결과 실시간 전달)
                          |
                          +--route---> [이벤트 로그 파이프라인]
                                        Core(EventLogWorker) -> Synapse(pm4py)
                                        파싱/검증/청킹 -> 프로세스 발견/적합성 검사
```

### 6.3 금지 패턴

```
[금지] Oracle -> Core DB 직접 쿼리 (반드시 API 경유)
[금지] Vision -> Synapse import (REST API 호출만 허용)
[금지] Canvas -> DB 직접 접근 (반드시 Core API 경유)
[금지] Core -> 다른 모듈의 내부 import (REST API만 사용)
[금지] Worker에서 Controller 계층 직접 호출 (서비스 계층만 사용)
```

---

## 7. 용어집(Glossary)

### 7.1 도메인 용어

| 용어 | 정의 | 영문 |
|------|------|------|
| **비즈니스 프로세스** | 조직의 목표를 달성하기 위한 구조화된 활동의 집합 | Business Process |
| **프로세스 최적화** | 비즈니스 프로세스의 효율성과 효과성을 개선하는 활동 | Process Optimization |
| **프로세스 분석가** | 비즈니스 프로세스의 분석과 관리를 담당하는 책임자 | Process Analyst |
| **이해관계자** | 프로세스의 결과에 이해관계를 가진 참여자 | Stakeholder |
| **대상 조직** | 프로세스 분석 및 최적화의 대상이 되는 조직 | Target Organization |
| **데이터 등록** | 이해관계자가 프로세스에서 필요한 데이터를 등록하는 행위 | Data Registration |
| **최적화 시나리오** | 프로세스 개선을 위한 다양한 방법과 일정을 정한 계획 | Optimization Scenario |
| **자산 가치 평가** | 대상 조직의 자산을 현재 시점에서 평가한 가치 | Asset Valuation |
| **이해관계자 리뷰** | 이해관계자들이 모여 최적화 시나리오 등을 검토하는 회의 | Stakeholder Review |
| **분석 보고서** | 프로세스 분석가가 작성하는 현황 및 원인 분석 보고서 | Analysis Report |

### 7.2 기술 용어

| 용어 | 정의 |
|------|------|
| **BPM (Business Process Management)** | 비즈니스 프로세스를 모델링, 실행, 모니터링하는 관리 체계 |
| **BPMN (Business Process Model and Notation)** | BPM을 위한 그래픽 표기법 표준 |
| **DMN (Decision Model and Notation)** | 의사결정 규칙을 표현하는 표준 (Decision Table 등) |
| **Saga** | 마이크로서비스 환경에서 분산 트랜잭션을 보상 트랜잭션으로 관리하는 패턴 |
| **Workitem** | BPM 엔진에서 사용자/에이전트에게 할당된 개별 작업 단위 |
| **LangGraph** | LangChain 기반의 순환 가능한 에이전트 워크플로우 프레임워크 |
| **MCP (Model Context Protocol)** | LLM 에이전트가 외부 도구를 호출하기 위한 표준 프로토콜 |
| **ReAct** | Reasoning + Acting 패턴. LLM이 추론하고 도구를 호출하는 루프 |
| **HITL (Human-in-the-Loop)** | AI 실행 중 사람이 개입하여 검증/승인하는 패턴 |
| **CEP (Complex Event Processing)** | 이벤트 스트림에서 복합 패턴을 감지하는 기술 |
| **Event Outbox** | DB 트랜잭션과 이벤트 발행의 원자성을 보장하는 패턴 |
| **RLS (Row Level Security)** | PostgreSQL의 행 수준 보안 정책 |
| **ContextVar** | Python의 컨텍스트 지역 변수 (비동기 환경에서 요청별 격리) |
| **SSE (Server-Sent Events)** | 서버에서 클라이언트로 단방향 실시간 데이터를 전송하는 프로토콜 |
| **프로세스 마이닝 (Process Mining)** | 이벤트 로그 데이터에서 실제 프로세스를 자동 발견, 적합성 검사, 병목 분석하는 기술 |
| **XES (eXtensible Event Stream)** | 프로세스 마이닝을 위한 IEEE 표준 이벤트 로그 형식 |
| **이벤트 로그 (Event Log)** | Case ID, Activity, Timestamp로 구성된 프로세스 실행 기록 데이터 |
| **pgvector** | PostgreSQL 확장으로, 벡터 유사도 검색을 지원 |
| **Mem0** | AI 에이전트의 장기 기억을 관리하는 벡터 기반 메모리 시스템 |
| **SafeToolLoader** | MCP 도구를 보안 정책에 따라 동적으로 로드하는 컴포넌트 |
| **A2A (Agent-to-Agent)** | 에이전트 간 통신을 위한 프로토콜 (Axiom에서는 LangGraph로 대체) |

### 7.3 프로세스 상태 용어

| 상태 | 의미 | 적용 대상 |
|------|------|----------|
| `RUNNING` | 프로세스 실행 중 | ProcessInstance |
| `COMPLETED` | 정상 완료 | ProcessInstance |
| `TERMINATED` | 외부에 의해 중단 | ProcessInstance |
| `SUSPENDED` | 일시 정지 | ProcessInstance |
| `TODO` | 아직 시작되지 않은 작업 | Workitem |
| `IN_PROGRESS` | 진행 중인 작업 | Workitem |
| `SUBMITTED` | 제출 완료, 검토 대기 | Workitem |
| `DONE` | 완료된 작업 | Workitem |
| `AUTONOMOUS` | AI 자동 실행 모드 | AgentMode |
| `SUPERVISED` | AI 실행 + 사람 확인 | AgentMode |
| `MANUAL` | 사람이 직접 처리 | AgentMode |
| `INGESTING` | 이벤트 로그 수집 중 | EventLog |
| `MINING` | 프로세스 마이닝 분석 중 | EventLog |
| `MINED` | 프로세스 마이닝 완료 | EventLog |

---

## 8. 규모 및 성능 목표

| 항목 | 목표 값 | 근거 |
|------|---------|------|
| 동시 사건(Case) 수 | 1,000+ | 중대형 컨설팅 조직 기준 |
| 테넌트 수 | 50+ | 분석 조직/컨설팅 조직 단위 |
| API 응답 시간 (P95) | < 500ms | 일반 CRUD 기준 |
| LLM 응답 시간 (P95) | < 30s | GPT-4o 기준, 타임아웃 적용 |
| 문서 처리 처리량 | 100 문서/시간 | Worker 스케일링 기준 |
| 이벤트 처리 지연 | < 5s | Watch Agent CEP 기준 |
| 가용성 | 99.5% | 비즈니스 시간 기준 |

---

## 9. 관련 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| 아키텍처 개요 | [01_architecture/architecture-overview.md](../01_architecture/architecture-overview.md) | 논리적/물리적 아키텍처 |
| BPM 엔진 설계 | [01_architecture/bpm-engine.md](../01_architecture/bpm-engine.md) | 프로세스 정의/실행/보상 상세 |
| API Gateway | [02_api/gateway-api.md](../02_api/gateway-api.md) | 라우팅 규칙, 타임아웃 |
| 보안 모델 | [07_security/auth-model.md](../07_security/auth-model.md) | JWT, RBAC, 멀티테넌트 |
| K-AIR 역설계 보고서 | [research/k-air-reverse-engineering-analysis.md](../../../../research/k-air-reverse-engineering-analysis.md) | 원본 시스템 분석 |

---

## 근거

- K-AIR 역설계 분석 보고서 v2.0 (2026-02-19)
- ADR-001: FastAPI 선택 ([99_decisions/ADR-001-fastapi-over-spring.md](../99_decisions/ADR-001-fastapi-over-spring.md))
- ADR-002: LangGraph 선택 ([99_decisions/ADR-002-langgraph-over-crewai.md](../99_decisions/ADR-002-langgraph-over-crewai.md))
