# Axiom Core - 서비스 내부 구조

## 이 문서가 답하는 질문

- Core 서비스의 디렉토리 레이아웃은 어떻게 구성되는가?
- 각 패키지의 책임과 의존 방향은 무엇인가?
- 코드 리뷰 시 어떤 규칙을 적용하는가?

<!-- affects: backend -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

---

## 1. 디렉토리 레이아웃

```
services/core/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI 앱 진입점, 미들웨어 등록
│   │
│   ├── api/                             # [Presentation Layer] REST 엔드포인트
│   │   ├── __init__.py
│   │   ├── auth/                        # 인증 (login, refresh, logout)
│   │   │   ├── router.py
│   │   │   └── schemas.py              # Pydantic 요청/응답 스키마
│   │   ├── cases/                       # 케이스 CRUD
│   │   │   ├── router.py
│   │   │   └── schemas.py
│   │   ├── process/                     # BPM 프로세스 실행
│   │   │   ├── router.py
│   │   │   └── schemas.py
│   │   ├── agents/                      # 에이전트 채팅, 피드백
│   │   │   ├── router.py
│   │   │   └── schemas.py
│   │   ├── watches/                     # Watch 구독, 알림
│   │   │   ├── router.py
│   │   │   └── schemas.py
│   │   ├── documents/                   # 문서 관리
│   │   │   ├── router.py
│   │   │   └── schemas.py
│   │   ├── completion/                  # LLM 완성
│   │   │   ├── router.py
│   │   │   └── schemas.py
│   │   └── mcp/                         # MCP 도구 관리
│   │       ├── router.py
│   │       └── schemas.py
│   │
│   ├── services/                        # [Application Layer] 비즈니스 로직 조율
│   │   ├── __init__.py
│   │   ├── process_service.py           # BPM 실행 조율
│   │   ├── agent_service.py             # 에이전트 실행 조율
│   │   ├── watch_service.py             # CEP 룰 관리, 알림 조율
│   │   ├── document_service.py          # 문서 처리 조율
│   │   ├── case_service.py              # 케이스 관리 조율
│   │   └── completion_service.py        # LLM 완성 조율
│   │
│   ├── bpm/                             # [Domain Layer] BPM 엔진
│   │   ├── __init__.py
│   │   ├── models.py                    # ProcessDefinition, Activity 등 Pydantic 모델
│   │   ├── engine.py                    # BPM 실행 엔진 (K-AIR process_engine.py 이식)
│   │   ├── saga.py                      # Saga 보상 트랜잭션 (compensation_handler.py 이식)
│   │   └── extractor.py                 # PDF -> BPMN 추출 (bpmn-extractor 이식)
│   │
│   ├── orchestrator/                    # [Domain Layer] 에이전트 오케스트레이션
│   │   ├── __init__.py
│   │   ├── langgraph_flow.py            # 9-노드 LangGraph 오케스트레이터
│   │   ├── agent_loop.py               # 에이전트 지식 학습 루프 (agent-feedback 이식)
│   │   ├── tool_loader.py              # SafeToolLoader (agent-utils 이식)
│   │   ├── conflict_analyzer.py        # 충돌 분석기 (agent-feedback 이식)
│   │   └── mcp_client.py              # MCP 프로토콜 클라이언트
│   │
│   ├── workers/                         # [Infrastructure Layer] 비동기 워커
│   │   ├── __init__.py
│   │   ├── ocr.py                       # OCR 워커 (Textract + GPT-4o Vision)
│   │   ├── extract.py                   # 문서 추출 워커 (memento 이식)
│   │   ├── generate.py                  # 문서 생성 워커
│   │   ├── sync.py                      # Event Outbox -> Redis Streams
│   │   └── watch_cep.py               # CEP 이벤트 처리 (text2sql/simple_cep 이식)
│   │
│   ├── core/                            # [Infrastructure Layer] 공통 인프라
│   │   ├── __init__.py
│   │   ├── config.py                    # 환경 설정 (Pydantic Settings)
│   │   ├── security.py                  # JWT 인증 + RBAC (gs-main 이식)
│   │   ├── middleware.py               # ContextVar 멀티테넌트, 요청 로깅
│   │   ├── database.py                  # SQLAlchemy 비동기 세션
│   │   ├── redis_client.py             # Redis 연결 관리
│   │   ├── event_publisher.py          # Event Outbox 퍼블리셔
│   │   ├── rate_limiter.py             # 속도 제한
│   │   ├── exceptions.py              # 커스텀 예외
│   │   └── logging.py                  # 구조화 로깅 (JSON)
│   │
│   └── models/                          # [Infrastructure Layer] SQLAlchemy ORM 모델
│       ├── __init__.py
│       ├── case.py                      # 케이스 모델
│       ├── process.py                   # 프로세스 인스턴스, 워크아이템
│       ├── user.py                      # 사용자, 테넌트
│       ├── document.py                  # 문서 모델
│       ├── watch.py                     # 구독, 알림 모델
│       ├── event_outbox.py             # Event Outbox 모델
│       └── base.py                      # Base 모델 (공통 필드)
│
├── tests/                               # 테스트
│   ├── unit/                            # 단위 테스트
│   │   ├── test_bpm_engine.py
│   │   ├── test_saga.py
│   │   └── test_tool_loader.py
│   ├── integration/                     # 통합 테스트
│   │   ├── test_process_api.py
│   │   ├── test_agent_api.py
│   │   └── test_watch_api.py
│   └── conftest.py                      # pytest 설정, 픽스처
│
├── docs/                                # 기술 문서 (현재 파일 위치)
├── pyproject.toml                       # Python 프로젝트 설정
└── Dockerfile                           # 컨테이너 빌드
```

---

## 2. 의존 방향 규칙

```
api/ --> services/ --> bpm/ | orchestrator/
                  |
                  +--> models/
                  |
                  +--> core/

workers/ --> services/ --> bpm/ | orchestrator/
                     |
                     +--> core/
```

### 2.1 허용되는 의존 방향

| 소스 | 대상 | 허용 |
|------|------|------|
| api/ | services/ | O |
| api/ | core/ (Depends) | O |
| services/ | bpm/, orchestrator/ | O |
| services/ | models/ | O |
| services/ | core/ | O |
| bpm/ | models/ (읽기만) | O |
| orchestrator/ | core/ (LLM 클라이언트) | O |
| workers/ | services/ | O |
| workers/ | core/ | O |

### 2.2 금지되는 의존 방향

| 소스 | 대상 | 금지 사유 |
|------|------|----------|
| api/ | models/ (직접) | Service Layer를 우회하면 트랜잭션 관리 불가 |
| api/ | bpm/ (직접) | Service Layer의 조율 없이 도메인 직접 접근 금지 |
| bpm/ | api/ | 순환 의존 |
| core/ | services/ | 순환 의존 |
| workers/ | api/ | Worker는 Service Layer를 통해서만 접근 |

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
