# Axiom Core - 아키텍처 개요

## 이 문서가 답하는 질문

- Axiom Core의 전체 아키텍처는 어떤 구조인가?
- 논리적 계층과 물리적 배포는 어떻게 다른가?
- 서비스 경계는 왜 이렇게 나뉘어졌는가?
- 동기/비동기 통신은 어디에서 구분되는가?
- 장애가 발생하면 어떻게 격리되는가?

<!-- affects: all modules -->
<!-- requires-update: 00_overview/system-overview.md, 02_api/gateway-api.md -->

---

## 1. 전체 시스템 아키텍처

### 1.1 Axiom 6-모듈 아키텍처

```
+-------------------------------------------------------------------------+
|                         Axiom Canvas (React 18)                          |
|  +----------+ +----------+ +----------+ +----------+ +----------+       |
|  | Cases    | | Documents| | HITL     | | What-if  | | Watch    |       |
|  | 관리     | | 관리     | | 리뷰     | | 시뮬     | | 알림     |       |
|  +----------+ +----------+ +----------+ +----------+ +----------+       |
+---------------------------------|----------------------------------------+
                                  | HTTP / WebSocket
+---------------------------------v----------------------------------------+
|                         Axiom Core (FastAPI)                              |
|  +----------+ +----------+ +----------+ +----------+ +----------+       |
|  | API      | | BPM      | | Agent    | | Event    | | Watch    |       |
|  | Gateway  | | Engine   | | Orch.    | | Bus      | | Agent    |       |
|  +----------+ +----------+ +----------+ +----------+ +----------+       |
|       |            |            |             |            |              |
|  +----v----+ +-----v----+ +----v-----+ +-----v----+ +----v-----+       |
|  | Auth &  | | Process  | | LangGraph| | Redis    | | CEP      |       |
|  | Routing | | Exec.    | | Agents   | | Streams  | | Engine   |       |
|  +---------+ +----------+ +----------+ +----------+ +----------+       |
+------+------------+------------+------------+------------+-----------+---+
       |            |            |            |            |           |
  +----v----+ +-----v----+ +----v-----+ +----v-----+ +---v-------+  |
  | Vision  | | Oracle   | | Synapse  | | Weaver   | | Workers   |  |
  | 분석    | | NL2SQL   | | 온톨로지 | | 패브릭   | | OCR/추출  |  |
  +---------+ +----------+ +----------+ +----------+ +-----------+  |
       |            |            |            |            |          |
  +----v----+  +----v----+  +---v----+  +----v----+  +---v------+   |
  | Postgres|  | Neo4j 5 |  | Neo4j  |  | MindsDB |  | MinIO    |   |
  | pgvector|  | Vector  |  | Graph  |  | Multi-DB|  | (S3)     |   |
  +---------+  +---------+  +--------+  +---------+  +----------+   |
                                                                      |
  +-------------------------------------------------------------------v--+
  |                    PostgreSQL 15 (RLS) + Redis 7                       |
  +-----------------------------------------------------------------------+
```

### 1.2 Core 내부 논리적 계층

```
+-----------------------------------------------------------------+
| Presentation Layer (API 경계)                                     |
|  +------------------+ +------------------+ +------------------+  |
|  | REST Endpoints   | | WebSocket        | | SSE Streams      |  |
|  | (FastAPI Router) | | (알림/실시간)    | | (워커 진행률)    |  |
|  +--------+---------+ +--------+---------+ +--------+---------+  |
|           |                     |                     |           |
+-----------v---------------------v---------------------v-----------+
| Application Layer (비즈니스 로직 조율)                              |
|  +------------------+ +------------------+ +------------------+  |
|  | Process Service  | | Agent Service    | | Watch Service    |  |
|  | (BPM 실행 조율)  | | (에이전트 조율)  | | (CEP 조율)       |  |
|  +--------+---------+ +--------+---------+ +--------+---------+  |
|           |                     |                     |           |
+-----------v---------------------v---------------------v-----------+
| Domain Layer (핵심 도메인 로직)                                     |
|  +------------------+ +------------------+ +------------------+  |
|  | BPM Engine       | | LangGraph Flow   | | CEP Engine       |  |
|  | Saga Manager     | | Knowledge Loop   | | Alert Dispatcher |  |
|  | Process Def.     | | Tool Priority    | | Event Evaluator  |  |
|  +--------+---------+ +--------+---------+ +--------+---------+  |
|           |                     |                     |           |
+-----------v---------------------v---------------------v-----------+
| Infrastructure Layer (외부 시스템 접근)                              |
|  +----------+ +----------+ +----------+ +----------+ +----------+|
|  | DB Repo  | | Redis    | | LLM      | | MCP      | | External ||
|  | (SQLAlch)| | Client   | | Client   | | Client   | | Service  ||
|  +----------+ +----------+ +----------+ +----------+ +----------+|
+-----------------------------------------------------------------+
```

---

## 2. 논리적 아키텍처 상세

### 2.1 계층별 책임

| 계층 | 책임 | 금지 사항 |
|------|------|----------|
| **Presentation** | HTTP 요청 수신, 요청 유효성 검증, 응답 직렬화 | DB 직접 접근, 비즈니스 로직 포함 |
| **Application** | 유스케이스 조율, 트랜잭션 경계 관리, 이벤트 발행 | 도메인 로직 구현, 인프라 의존 |
| **Domain** | 핵심 비즈니스 규칙, 상태 전이, 불변조건 검증 | 외부 서비스 호출, DB 접근 |
| **Infrastructure** | DB 접근, 외부 API 호출, 메시지 발행/소비 | 비즈니스 로직 포함 |

### 2.2 주요 컴포넌트별 계층 매핑

```python
# Presentation Layer - app/api/
app/api/auth/          # JWT 인증 엔드포인트
app/api/cases/         # 케이스 CRUD
app/api/process/       # BPM 실행 API
app/api/agents/        # 에이전트 관리 API
app/api/watches/       # Watch 구독/알림 API

# Application Layer - app/services/
app/services/process_service.py    # BPM 실행 조율
app/services/agent_service.py      # 에이전트 실행 조율
app/services/watch_service.py      # CEP 룰 관리/알림 조율
app/services/document_service.py   # 문서 처리 조율

# Domain Layer - app/bpm/, app/orchestrator/
app/bpm/engine.py                  # BPM 엔진 코어
app/bpm/saga.py                    # Saga 보상 트랜잭션
app/bpm/extractor.py               # BPMN 추출기
app/orchestrator/langgraph_flow.py # 9노드 LangGraph 오케스트레이터
app/orchestrator/agent_loop.py     # 에이전트 지식 학습 루프

# Infrastructure Layer - app/core/, app/workers/
app/core/config.py                 # 환경 설정
app/core/security.py               # JWT + RBAC
app/core/middleware.py             # 멀티테넌트 ContextVar
app/core/database.py               # SQLAlchemy 세션
app/core/redis_client.py           # Redis 연결
app/workers/                       # 비동기 워커들
```

---

## 3. 서비스 경계 근거

### 3.1 왜 6개 모듈인가

K-AIR의 18개 저장소가 6개 Axiom 모듈로 통합된 근거:

| 결정 | 근거 |
|------|------|
| **Core로 통합** (12개 저장소 -> 1개) | 인증, Gateway, BPM, 에이전트는 모두 요청 흐름의 같은 경로에 있다. 분리 시 네트워크 홉 증가, 트랜잭션 관리 복잡도 상승. |
| **Vision 분리** | 분석 엔진(What-if, OLAP, 근본원인)은 Core의 요청-응답 흐름과 독립적인 무거운 계산이다. 별도 스케일링이 필요하다. |
| **Oracle 분리** | NL2SQL은 Neo4j 기반 5축 벡터 검색이라는 독자적 데이터 파이프라인을 가진다. Core와 다른 메모리/CPU 프로파일. |
| **Synapse 분리** | 온톨로지와 지식그래프는 Neo4j 중심의 독립적 도메인이다. 변경 주기가 Core와 다르다. |
| **Weaver 분리** | 데이터 패브릭(MindsDB 연동)은 외부 DB 연결이라는 보안 경계가 다르다. |
| **Canvas 분리** | 프론트엔드는 백엔드와 기술 스택, 배포 주기, 빌드 파이프라인이 다르다. |

### 3.2 Core 내부 경계

Core 내에서도 명확한 하위 경계가 존재한다:

```
Core 내부 경계:
  [Gateway 영역]     인증, 라우팅, CORS, 속도 제한
       |
  [BPM 영역]         프로세스 정의, 실행, Saga 보상
       |
  [Agent 영역]       LangGraph 오케스트레이션, MCP 도구, 지식 학습
       |
  [Event 영역]       Event Outbox, Redis Streams 발행/소비
       |
  [Watch 영역]       CEP 룰 평가, 알림 생성/발송
       |
  [Worker 영역]      OCR, 추출, 생성, 동기화, CEP (비동기 프로세서)
```

이 경계는 Python 패키지 경계로 구현되며, 하위 영역 간 직접 import는 허용하되, **순환 의존은 금지**한다.

---

## 4. 동기/비동기 경계

### 4.1 통신 패턴 결정 기준

| 조건 | 패턴 | 예시 |
|------|------|------|
| 결과가 즉시 필요 | **동기 (REST)** | 케이스 조회, 인증 |
| 처리 시간 > 5초 | **비동기 (Worker)** | OCR, 문서 추출, LLM 호출 |
| 다른 모듈에 알림 필요 | **이벤트 (Redis Streams)** | 케이스 상태 변경, 문서 생성 완료 |
| 클라이언트에 실시간 푸시 | **SSE / WebSocket** | 알림, 워커 진행률 |
| 장기 실행 에이전트 태스크 | **비동기 + 폴링** | LangGraph 에이전트 실행 |

### 4.2 동기 호출 경로

```
Canvas --> Core API Gateway --> Core Service Layer --> DB/Redis
  |                                    |
  |                                    +--> Vision API (HTTP)
  |                                    +--> Oracle API (HTTP)
  |                                    +--> Synapse API (HTTP)
  |                                    +--> Weaver API (HTTP)
  |
  <-- JSON Response (< 500ms 목표) ---
```

### 4.3 비동기 호출 경로

```
Canvas --> Core API (작업 생성)
  |           |
  |           +--> event_outbox 테이블에 이벤트 INSERT (같은 트랜잭션)
  |           |
  |           <-- 202 Accepted (작업 ID 반환) ---
  |
  |   [Worker: sync_worker]
  |           |
  |           +--> event_outbox 폴링 (5초 간격)
  |           +--> Redis Streams에 이벤트 PUBLISH
  |           +--> event_outbox 상태 업데이트 (PUBLISHED)
  |
  |   [Worker: watch_cep_worker]
  |           |
  |           +--> Redis Streams 소비 (XREADGROUP)
  |           +--> CEP 룰 평가
  |           +--> 알림 생성 + 발송
  |
  <-- SSE/WebSocket (알림) ---
```

---

## 5. 장애 격리

### 5.1 격리 포인트

| 격리 포인트 | 격리 방법 | 장애 시 영향 |
|------------|----------|------------|
| **LLM 프로바이더 장애** | 타임아웃(30초) + 재시도(3회) + 폴백 | 에이전트 태스크만 실패, BPM 수동 모드로 전환 |
| **Vision/Oracle/Synapse 장애** | Circuit Breaker (5회 실패 시 차단) | 해당 기능만 비가용, Core CRUD 정상 |
| **Redis 장애** | 로컬 큐 폴백 + 재연결 | 이벤트 발행 지연, 알림 지연 (데이터 유실 없음) |
| **Worker 장애** | 프로세스 재시작 (systemd/k8s) | 비동기 작업 지연, 재시작 후 미처리 작업 재개 |
| **DB 장애** | Connection Pool 재연결 + Read Replica 폴백 | 전체 서비스 영향 (최대 위험) |
| **개별 테넌트 데이터 오류** | RLS + ContextVar 격리 | 해당 테넌트만 영향, 다른 테넌트 정상 |

> **상세 참조**: Circuit Breaker 상태 전이, 서비스 쌍별 설정, Fallback 매트릭스, DLQ, K8s Probe 등 전체 복원력 패턴은 [resilience-patterns.md](./resilience-patterns.md)를 참조한다.

### 5.2 장애 전파 방지 원칙

```
[결정] Core -> 외부 모듈 호출 시 반드시 타임아웃을 설정한다 (기본 30초).
[결정] Worker는 개별 태스크 실패 시 해당 태스크만 재시도하고, Worker 자체는 계속 실행한다.
[결정] LLM 호출 실패는 "에이전트 태스크 실패"로 처리하며, BPM은 수동 모드로 전환한다.
[결정] Event Outbox는 at-least-once 보장이므로, 소비자는 멱등성(idempotency)을 보장해야 한다.
```

---

## 6. 데이터 흐름

### 6.1 요청 처리 흐름 (동기)

```
1. Canvas에서 HTTP 요청 전송
2. FastAPI 미들웨어 체인:
   a. CORS 검증
   b. JWT 토큰 검증 (core/security.py)
   c. ContextVar 테넌트 설정 (core/middleware.py - X-Forwarded-Host)
   d. 요청 로깅
3. Router 핸들러 실행
4. Service Layer에서 비즈니스 로직 조율
5. Domain Layer에서 핵심 규칙 적용
6. Infrastructure Layer에서 DB/Redis/외부 API 접근
7. 응답 반환
```

### 6.2 BPM 프로세스 실행 흐름

```
1. POST /process/initiate (프로세스 시작)
2. ProcessService.initiate():
   a. ProcessDefinition 로드 (proc_def 테이블)
   b. ProcessInstance 생성 (bpm_proc_inst)
   c. 첫 Activity의 Workitem 생성 (bpm_work_item, status=TODO)
   d. 역할 바인딩 (사용자/에이전트 할당)
   e. event_outbox에 PROCESS_STARTED 이벤트 INSERT

3. Workitem 실행 루프:
   a. agentMode 확인
      - AUTONOMOUS: LangGraph 에이전트 자동 실행
      - SUPERVISED: AI 실행 결과 -> HITL 승인 대기
      - MANUAL: 사용자가 직접 완료
   b. POST /process/submit (워크아이템 제출)
   c. 게이트웨이 평가 (분기 조건)
   d. 다음 Activity의 Workitem 생성
   e. event_outbox에 WORKITEM_COMPLETED 이벤트 INSERT

4. 프로세스 완료:
   a. ProcessInstance.status = COMPLETED
   b. event_outbox에 PROCESS_COMPLETED 이벤트 INSERT
```

---

## 7. 확장성(Scalability) 설계

### 7.1 수평 확장 포인트

| 컴포넌트 | 확장 전략 | 제약 사항 |
|---------|----------|----------|
| **Core API** | Stateless - 로드밸런서 뒤에 N개 인스턴스 | ContextVar는 요청 스코프이므로 문제없음 |
| **Workers** | 독립 프로세스 - 개별 스케일링 | Redis Consumer Group으로 작업 분배 |
| **Redis** | Redis Cluster (파티셔닝) | 순서 보장은 스트림 키 단위 |
| **PostgreSQL** | Read Replica + Connection Pooling | 쓰기는 단일 마스터 |

### 7.2 성능 병목 예측

| 병목 지점 | 원인 | 대응 |
|----------|------|------|
| LLM API 호출 | 네트워크 지연 + 토큰 생성 시간 | 비동기 처리 + 스트리밍 + 캐싱 |
| DB 연결 풀 고갈 | 동시 요청 과다 | asyncpg 풀 크기 조정 (기본 20, 최대 100) |
| Worker 처리 지연 | OCR/문서 추출의 CPU/메모리 소비 | Worker 별도 인스턴스, 자원 제한 설정 |
| Event Outbox 폴링 | 5초 간격 폴링의 지연 | 폴링 간격 조정 또는 LISTEN/NOTIFY 활용 |

---

## 8. 재평가 조건

이 아키텍처는 다음 조건에서 재평가해야 한다:

| 조건 | 재평가 대상 | 근거 |
|------|-----------|------|
| 동시 테넌트 100개 초과 | ContextVar 멀티테넌트 -> 물리적 DB 분리 검토 | 단일 DB RLS의 성능 한계 |
| LLM 호출 100 req/min 초과 | LLM 호출 큐잉 + 프로바이더 분산 | API 레이트 리밋 |
| Core API 인스턴스 10개 초과 | Core 내부 영역 분리 (BPM/Agent를 별도 서비스로) | 배포 복잡도 |
| Worker 처리량 부족 | Celery 등 전용 태스크 큐 도입 | 현재 Redis Streams 기반 자체 구현의 한계 |

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| [01_architecture/resilience-patterns.md](./resilience-patterns.md) | Circuit Breaker, Retry, Fallback, DLQ, K8s Probe 등 전체 복원력 패턴 상세 |

---

## 근거

- K-AIR 역설계 보고서 섹션 2 (시스템 아키텍처), 섹션 4.10 (Axiom 모듈 정의)
- ADR-001: FastAPI 선택 (Spring Boot 대체)
- ADR-003: ContextVar 멀티테넌트
- ADR-004: Redis Streams 이벤트 버스
