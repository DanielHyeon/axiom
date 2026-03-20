# Oracle 모듈 시스템 개요

## 이 문서가 답하는 질문

- Oracle 모듈은 무엇이고, Axiom 플랫폼에서 어떤 역할을 하는가?
- NL2SQL 파이프라인은 어떤 흐름으로 동작하는가?
- 비즈니스 프로세스 인텔리전스에서 Oracle이 해결하는 문제는 무엇인가?
- Oracle은 어떤 기술 스택 위에 구축되는가?

<!-- affects: 01_architecture, 02_api, 05_llm -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

---

## 1. Oracle이란

**Axiom Oracle**은 "질문에 데이터의 언어로 답하는 영매(Oracle)" 모듈이다.

사용자가 자연어로 던진 질문을 SQL로 변환하고, 데이터베이스에서 실행한 결과를 사람이 이해할 수 있는 형태로 되돌려주는 **NL2SQL(Natural Language to SQL) 엔진**이다.

### 1.1 핵심 정체성

| 속성 | 설명 |
|------|------|
| 이름 | Axiom Oracle |
| 은유 | "데이터의 영매" - 사람의 말을 데이터의 언어(SQL)로 통역 |
| 도메인 | 비즈니스 프로세스 인텔리전스 |
| 핵심 기능 | 자연어 -> SQL 변환, ReAct 추론 (HIL), SQL 안전성 검증, 이벤트 감시 (Core Watch 프록시), 피드백 분석 |
| 버전 | 2.0.0 (FastAPI title: "Axiom Oracle") |
| 출자 | K-AIR `robo-data-text2sql-main` 기반 — 전면 재구현 완료 |

### 1.2 Axiom 플랫폼 내 위치

```
┌─────────────────────────────────────────────────────────────────┐
│                      Axiom AI Data Platform                     │
│              비즈니스 프로세스 인텔리전스 플랫폼                  │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │   Vision   │  │   Oracle   │  │  Synapse   │  │  Weaver   │ │
│  │  문서 처리  │  │  NL2SQL    │  │ 에이전트   │  │ 데이터    │ │
│  │  OCR/분석  │  │  ReAct     │  │ 오케스트라 │  │ 패브릭    │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬─────┘ │
│        │               │               │               │        │
│  ┌─────┴───────────────┴───────────────┴───────────────┴─────┐ │
│  │                    Core (공통 인프라)                       │ │
│  │          인증 / 이벤트 버스 / 감시(Watch) / 로깅           │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              데이터 레이어                                  │ │
│  │   PostgreSQL  |  Neo4j  |  Redis  |  Vector Store          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Oracle이 해결하는 문제

**비즈니스 데이터 접근 장벽**:

1. **전문 용어 장벽**: "프로세스 성공률" 같은 질문을 SQL로 작성하려면 DB 스키마와 비즈니스 용어를 모두 알아야 함
2. **복잡한 조인**: 비즈니스 데이터는 다수의 테이블에 분산되어 있어 FK 관계 파악이 필수
3. **안전성 요구**: 민감한 비즈니스 데이터에 대한 무분별한 쿼리 실행 방지 필요
4. **반복 질문**: 유사한 질문이 반복되지만 매번 SQL을 새로 작성하는 비효율

**Oracle의 해결 방식**:

| 문제 | 해결 방식 |
|------|----------|
| 전문 용어 | 5축 벡터 검색으로 자연어-DB 스키마 의미 매핑 |
| 복잡한 조인 | Synapse API가 제공하는 FK 그래프에서 최대 3홉 경로 자동 탐색 |
| 안전성 | SQL Guard (SELECT-only, LIMIT 강제, 서브쿼리 깊이 제한) |
| 반복 질문 | 품질 게이트 통과 쿼리를 Synapse 백엔드 그래프 캐시에 반영 후 벡터 검색으로 재활용 |

---

## 2. NL2SQL 파이프라인 요약

Oracle의 핵심은 **10단계 NL2SQL 파이프라인**이다.

```
사용자 질문 (자연어)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. 임베딩 생성                                               │
│    자연어 질문 → 벡터 (MockLLM 1536차원 / OpenAI 등)        │
├─────────────────────────────────────────────────────────────┤
│ 2. 그래프 검색 + 스키마 카탈로그 + 온톨로지 컨텍스트 (O3)    │
│    Synapse ACL 경유 → 관련 테이블, 컬럼, 값 매핑, 캐시 쿼리 │
├─────────────────────────────────────────────────────────────┤
│ 2.5. Value Mapping (#13 P1-2)                               │
│    자연어 값 → DB 값 매핑 (3단계: 캐시 → DB Probe → 검증)   │
├─────────────────────────────────────────────────────────────┤
│ 3. 스키마 포맷팅                                             │
│    추출된 테이블/컬럼 → CREATE TABLE DDL 형태로 정규화       │
├─────────────────────────────────────────────────────────────┤
│ 4. SQL 생성 (LLM Factory — MockLLM 스마트 모드)             │
│    프롬프트: 스키마 + 질문 + 값 매핑 + 온톨로지 → SQL 출력  │
├─────────────────────────────────────────────────────────────┤
│ 4.5. SQL 리터럴 검증 (#13 P1-2)                             │
│    WHERE 절의 값이 실제 DB 값과 일치하는지 확인              │
├─────────────────────────────────────────────────────────────┤
│ 5. SQL 검증 (SQLGlot AST 기반 SQL Guard)                    │
│    AST 파싱, 멀티스테이트먼트 차단, 금지 노드 검출,          │
│    JOIN/서브쿼리 깊이 제한, 화이트리스트 테이블 검증         │
├─────────────────────────────────────────────────────────────┤
│ 6. SQL 실행 (4모드: direct_pg / weaver / hybrid / mock)     │
│    타임아웃 15초, 최대 10,000행, psycopg2 readonly          │
├─────────────────────────────────────────────────────────────┤
│ 7. 시각화 추천                                               │
│    결과 컬럼 역할 추론 → 차트 유형 자동 추천                 │
│    (line/bar/pie/scatter/kpi_card/table)                     │
├─────────────────────────────────────────────────────────────┤
│ 8. 결과 요약 (LLM 요약)                                     │
│    쿼리 결과를 한 문장으로 요약                              │
├─────────────────────────────────────────────────────────────┤
│ 9. 품질 게이트 + 캐시 저장 + Value Mapping 학습 (비동기)    │
│    N-라운드 LLM 심사 → APPROVE(>=0.80)/PENDING/REJECT       │
│    APPROVE 시 Neo4j 캐시 저장 + Value Mapping 학습          │
├─────────────────────────────────────────────────────────────┤
│ 10. Insight 로그 포워딩 (비동기, fire-and-forget)            │
│    Oracle → Weaver /api/insight/logs (P1-B)                 │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
응답 (SQL + 데이터 + 시각화 추천 + 요약 + 메타데이터)
```

---

## 3. 기술 스택

### 3.1 핵심 기술 (현재 구현 기준)

| 계층 | 기술 | 용도 |
|------|------|------|
| LLM | MockLLM (스마트 모드) | SQL 생성, 품질 심사 — 프로덕션 시 GPT-4o로 교체 가능 |
| LLM 추상화 | LLMFactory + LLMClientWithRetry | 프로바이더 팩토리 + 3회 재시도 래퍼 |
| SQL 파서 | SQLGlot (AST 기반) | SQL 구문 분석, 금지 노드 검출, LIMIT 자동 삽입 |
| 품질 심사 | QualityJudge (N-라운드) | Pydantic strict 모델, fail-closed, semantic mismatch 검증 |
| 웹 프레임워크 | FastAPI 2.0.0 | 비동기 API 서버, Lifespan 패턴 |
| DB 드라이버 | psycopg2 (동기, asyncio.to_thread 래핑) | PostgreSQL 직접 실행 (readonly) |
| SQL 실행 | 4모드 (direct/hybrid/weaver/mock) | ORACLE_SQL_EXECUTION_MODE 환경변수로 설정 |
| 외부 연동 | httpx (비동기) | Synapse ACL, Weaver ACL, Core Watch 프록시 |
| 인증 | python-jose (JWT HS256) | Core 발급 JWT 검증, 역할 기반 권한 |
| 로깅 | structlog | 구조화 로깅 |
| Value Mapping | 인메모리 LRU 캐시 + DB Probe | 자연어 → DB 값 매핑 (최대 5000건) |
| Enum 캐시 | information_schema 스캔 | 서비스 시작 시 저카디널리티 컬럼 캐싱 |

### 3.2 현재 소스 구성 (구현 완료)

| 파일 | 역할 |
|------|------|
| `app/api/text2sql.py` | /ask, /react, /direct-sql, /history 엔드포인트 |
| `app/api/feedback.py` | 피드백 제출 + 목록 조회 |
| `app/api/feedback_stats.py` | 피드백 통계 대시보드 (summary/trend/failures/by-datasource/top-failed) |
| `app/api/meta.py` | 메타데이터 탐색 (tables/columns/datasources/description 수정) |
| `app/api/events.py` | 이벤트 룰 CRUD + 스케줄러 + SSE 알림 (Core Watch 프록시) |
| `app/api/health.py` | /health, /health/ready 프로브 |
| `app/pipelines/nl2sql_pipeline.py` | 10단계 Ask 파이프라인 |
| `app/pipelines/react_agent.py` | 6단계 ReAct 에이전트 (HIL 지원) |
| `app/pipelines/cache_postprocess.py` | 품질 게이트 + 캐시 저장 |
| `app/pipelines/enum_cache_bootstrap.py` | Enum 캐시 부트스트랩 (서비스 시작 시) |
| `app/core/llm_factory.py` | LLM 팩토리 (MockLLM 스마트 모드 + 재시도) |
| `app/core/sql_guard.py` | SQLGlot AST 기반 SQL 안전성 검증 |
| `app/core/sql_exec.py` | SQL 실행 (4모드: direct_pg/weaver/hybrid/mock) |
| `app/core/quality_judge.py` | LLM 기반 N-라운드 품질 심사기 |
| `app/core/value_mapping.py` | 자연어 → DB 값 매핑 3단계 파이프라인 |
| `app/core/visualize.py` | 시각화 추천 (컬럼 역할 추론 기반) |
| `app/core/schema_context.py` | 서브스키마 컨텍스트 (DDL 축소) |
| `app/core/graph_search.py` | RRF 기반 검색 + PRF (현재 모의 데이터) |
| `app/core/query_history.py` | PostgreSQL 쿼리 이력 저장소 (인메모리 폴백) |
| `app/core/feedback_analytics.py` | asyncpg 기반 피드백 통계 집계 |
| `app/core/auth.py` | JWT 검증 (Core 동일 비밀키) |
| `app/core/rate_limit.py` | 인메모리 Rate Limiter |
| `app/core/security.py` | 역할별 행 제한 + PII 마스킹 |
| `app/infrastructure/acl/synapse_acl.py` | Anti-Corruption Layer: Synapse BC |
| `app/infrastructure/acl/weaver_acl.py` | Anti-Corruption Layer: Weaver BC |

---

## 4. 사용자 유형과 사용 시나리오

### 4.1 사용자 역할

| 역할 | Oracle 사용 방식 |
|------|-----------------|
| **비즈니스 분석가** | "이 프로젝트의 총 수익은?" 같은 자연어 질의 |
| **운영 담당자** | 프로세스 통계 조회, 기간별 추이 분석 |
| **데이터 분석가** | 직접 SQL 실행, 시각화 결과 활용 |
| **시스템 관리자** | 메타데이터 관리, 피드백 기반 품질 개선 |
| **AI/LLM 시스템** | ReAct 에이전트를 통한 다단계 추론 |

### 4.2 주요 사용 시나리오

**시나리오 1: 단순 조회**
```
사용자: "2024년 매출 성장률이 가장 높은 사업부는?"
Oracle: SQL 생성 → 실행 → "2024년 매출 성장률이 가장 높은 사업부는 디지털사업부(32%)입니다."
        + 사업부별 성장률 bar chart 추천
```

**시나리오 2: 복합 추론 (ReAct)**
```
사용자: "작년 대비 프로세스 성공률이 가장 많이 변동한 조직 TOP 5는?"
Oracle: [ReAct 에이전트]
  → Think: 2024년과 2023년 프로세스 성공률을 조직별로 비교해야 함
  → Act: 2024년 조직별 성공률 SQL 실행
  → Observe: 결과 확인
  → Act: 2023년 조직별 성공률 SQL 실행
  → Observe: 결과 확인
  → Think: 변동률 계산 후 TOP 5 추출
  → Answer: 결과 + 비교 차트
```

**시나리오 3: 이벤트 감시**
```
관리자: "프로세스 마일스톤 기한 3일 전 알림 룰 등록"
Oracle: 이벤트 룰 등록 → 주기적 SQL 실행 → 조건 충족 시 알림 발생
```

---

## 5. 용어 사전

| 용어 | 설명 |
|------|------|
| **NL2SQL** | Natural Language to SQL. 자연어를 SQL 쿼리로 변환하는 기술 |
| **ReAct** | Reasoning + Acting. LLM이 사고(Think)와 행동(Act)을 반복하며 문제를 해결하는 패턴 |
| **5축 벡터 검색** | question, HyDE, regex, intent, PRF(Pseudo Relevance Feedback) 5가지 축으로 벡터 유사도 검색 |
| **SQL Guard** | SQL 안전성 검증기. DML 차단, JOIN 깊이 제한, 서브쿼리 깊이 제한 등 |
| **SQLGlot** | SQL 파서/트랜스파일러. SQL 구문 분석과 방언 변환 수행 |
| **FK 3홉** | Foreign Key 관계를 최대 3단계까지 그래프 탐색하여 관련 테이블 발견 |
| **품질 게이트** | 생성된 SQL/매핑을 LLM이 N회 심사하여 신뢰도 기준 이상만 캐시에 영속화 |
| **CEP** | Complex Event Processing. 이벤트 스트림에서 복합 패턴을 감지하는 기술 |
| **HyDE** | Hypothetical Document Embedding. 질문에 대한 가상 답변을 생성한 후 그 임베딩으로 검색하는 기법 |
| **PRF** | Pseudo Relevance Feedback. 초기 검색 결과를 기반으로 쿼리를 보강하는 기법 |
| **값 매핑** | 자연어 값("본사")과 DB 실제 값("HQ_001") 사이의 매핑 |
| **비즈니스 프로세스** | 조직이 목표를 달성하기 위해 수행하는 일련의 활동 흐름 |
| **프로세스 인텔리전스** | 비즈니스 프로세스 데이터를 분석하여 인사이트를 도출하고 미래를 예측하는 기술 |
| **디지털 트윈** | 비즈니스 프로세스의 디지털 복제본을 통해 시뮬레이션 및 예측을 수행하는 기술 |

---

## 6. K-AIR 출자 현황

### 6.1 이식 범위

| 원본 (K-AIR) | 대상 (Axiom Oracle) | 이식 방식 |
|-------------|--------------------|-----------|
| `robo-data-text2sql-main` | `services/oracle` | 전면 이식 후 비즈니스 도메인 적응 |
| NL2SQL 파이프라인 | 동일 구조 유지 | 5축 벡터 검색 + ReAct 그대로 |
| SQL Guard | 동일 구조 유지 | 비즈니스 도메인 화이트리스트 추가 |
| 이벤트/CEP | Core Watch로 이관 | SimpleCEP → Core 공통 모듈로 분리 |
| Neo4j 스키마 | 확장 | 비즈니스 프로세스 도메인 노드/관계 추가 |

### 6.2 변경 사항

| 항목 | K-AIR 원본 | Axiom Oracle |
|------|-----------|-------------|
| 도메인 | 범용 | 비즈니스 프로세스 인텔리전스 |
| DB 타겟 | MySQL + PostgreSQL | PostgreSQL 중심 |
| 인증 | Keycloak + Supabase | Core 통합 인증 |
| 이벤트 | SimpleCEP (내장) | Core Watch (외부 모듈) |
| 이력 저장 | SQLite | PostgreSQL |
| 멀티테넌트 | X-Forwarded-Host | Core 테넌트 관리 |

---

## 관련 문서

- [01_architecture/architecture-overview.md](../01_architecture/architecture-overview.md): 전체 아키텍처
- [01_architecture/nl2sql-pipeline.md](../01_architecture/nl2sql-pipeline.md): NL2SQL 파이프라인 상세
- [02_api/text2sql-api.md](../02_api/text2sql-api.md): API 스펙
- [05_llm/react-agent.md](../05_llm/react-agent.md): ReAct 에이전트
- [99_decisions/ADR-001-langchain-sql.md](../99_decisions/ADR-001-langchain-sql.md): LangChain 선택 배경
