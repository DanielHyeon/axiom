# K-AIR text2sql -> Oracle 이식 가이드

> 상태: 레거시 이식 참고 문서 (Axiom 현재 저장소 표준은 PostgreSQL)

## 이 문서가 답하는 질문

- K-AIR에서 Axiom Oracle로 이식할 때 어떤 단계를 거쳐야 하는가?
- 어떤 파일을 그대로 이식하고, 어떤 파일을 수정해야 하는가?
- 도메인 변경(범용 -> 비즈니스 프로세스 인텔리전스) 시 어떤 부분을 수정해야 하는가?
- 이식 후 검증은 어떻게 하는가?

<!-- affects: 모든 문서 -->

---

## 1. 이식 개요

### 1.1 원본과 대상

| 항목 | K-AIR 원본 | Axiom Oracle |
|------|-----------|-------------|
| 저장소 | `robo-data-text2sql-main` | `services/oracle` |
| 도메인 | 범용 | 비즈니스 프로세스 인텔리전스 |
| 프레임워크 | FastAPI | FastAPI (동일) |
| LLM | OpenAI/Google/호환 | OpenAI 중심 (호환 유지) |
| 그래프 DB | Neo4j 5 | Neo4j 5 (동일) |
| Target DB | MySQL + PostgreSQL | PostgreSQL 중심 |
| 이력 저장 | SQLite | PostgreSQL |
| 인증 | Supabase + Keycloak | Core 통합 인증 |
| 이벤트 | SimpleCEP (내장) | Core Watch (외부) |

### 1.2 이식 완성도 평가

K-AIR `robo-data-text2sql-main`의 구현 완성도는 **95%**로, 대부분의 코어 기능이 동작 가능한 수준이다.

---

## 2. 이식 단계

> 기준일: 2026-02-21
> 아래 Phase 2~8 표는 원안 계획이며, 실제 상태는 "2.0 현재 구현 현황"을 우선 기준으로 본다.

### 2.0 현재 구현 현황 (코드 기준)

| Phase | 상태 | 근거 |
|------|------|------|
| Phase 1 (구조 셋업) | 부분 완료 | `app/main.py`, `app/core/config.py`, `requirements.txt` 존재. `Dockerfile`/compose는 미확인 |
| Phase 2 (코어 모듈) | 부분 완료 | `sql_guard.py`, `sql_exec.py`, `graph_search.py`, `llm_factory.py` 구현. 일부 모듈은 mock/미구현 |
| Phase 3 (파이프라인 분리) | 완료 | `pipelines/nl2sql_pipeline.py`, `pipelines/react_agent.py` 구현 |
| Phase 4 (API 라우터) | 부분 완료 | `api/text2sql.py`, `api/feedback.py` 구현, `meta/events/history` 라우터 미구현 |
| Phase 5 (데이터 계층) | 부분 완료 | `core/synapse_client.py`, `core/query_history.py` 존재하나 mock 기반 |
| Phase 6 (도메인 적응) | 부분 완료 | `core/value_mapping.py`/`sql_guard.py` 반영, 도메인 데이터 세트 고도화 미완 |
| Phase 7 (인증/보안) | 부분 완료 | `core/auth.py`, `core/security.py` 존재. 실서비스 JWT/DB 계정 분리 미완 |
| Phase 8 (테스트/검증) | 부분 완료 | `tests/unit/` 존재. 통합/성능 검증은 별도 진행 필요 |

### Phase 1: 구조 셋업 (1~2일)

| 단계 | 작업 | 상태 |
|------|------|------|
| 1.1 | 디렉터리 구조 생성 (routers/core/pipelines/models) | 완료 |
| 1.2 | pyproject.toml 작성 (의존성 정의) | 부분 완료 (`requirements.txt` 사용) |
| 1.3 | config.py 작성 (환경 변수 관리) | 완료 |
| 1.4 | Dockerfile / docker-compose.yml 작성 | 미착수 |
| 1.5 | 기본 main.py (FastAPI 앱 뼈대) | 완료 |

### Phase 2: 코어 모듈 이식 (3~5일)

| 단계 | K-AIR 원본 | Axiom 대상 | 수정 사항 |
|------|-----------|-----------|----------|
| 2.1 | `core/embedding.py` (55줄) | `core/embedding.py` | 프로바이더 추상화 |
| 2.2 | `core/llm_factory.py` (213줄) | `core/llm_factory.py` | 설정 방식 변경 |
| 2.3 | `core/graph_search.py` (352줄) | `core/graph_search.py` | datasource_id 체계 변경 |
| 2.4 | `core/prompt.py` (112줄) | `core/prompt.py` | 비즈니스 도메인 규칙 추가 |
| 2.5 | `core/sql_guard.py` (153줄) | `core/sql_guard.py` | 화이트리스트 추가 |
| 2.6 | `core/sql_exec.py` (380줄) | `core/sql_exec.py` | MySQL 의존 축소 |
| 2.7 | `core/viz.py` (297줄) | `core/viz.py` | 그대로 이식 |
| 2.8 | `core/cache_postprocess.py` (1977줄) | `core/cache_postprocess.py` | Neo4j 쿼리 호환 검증 |
| 2.9 | `core/enum_cache_bootstrap.py` (513줄) | `core/enum_cache_bootstrap.py` | datasource 체계 변경 |

### Phase 3: 파이프라인 분리 (2~3일)

| 단계 | 작업 | 설명 |
|------|------|------|
| 3.1 | `routers/ask.py`에서 파이프라인 추출 | NL2SQL 8단계 파이프라인 독립 모듈화 |
| 3.2 | ReAct 파이프라인 분리 | 6단계 ReAct 루프 독립 모듈화 |
| 3.3 | 파이프라인-코어 간 인터페이스 정의 | `SchemaSearchResult`, `GuardResult` 등 모델 |

### Phase 4: API 라우터 이식 (2~3일)

| 단계 | K-AIR 원본 | Axiom 대상 | 수정 사항 |
|------|-----------|-----------|----------|
| 4.1 | `routers/ask.py` | `routers/ask.py` | 파이프라인 위임으로 경량화 |
| 4.2 | `routers/meta.py` | `routers/meta.py` | 페이지네이션 표준화 |
| 4.3 | `routers/feedback.py` | `routers/feedback.py` | Synapse Graph API 통합 |
| 4.4 | `models/history.py` | `routers/history.py` | SQLite -> PostgreSQL |
| 4.5 | `routers/events.py` | `routers/events.py` | Core Watch 이관 준비 |

### Phase 5: 데이터 계층 이식 (2~3일)

| 단계 | 작업 | 설명 |
|------|------|------|
| 5.1 | Synapse 백엔드 그래프 스키마 연동 | 벡터 인덱스/일반 인덱스는 Synapse bootstrap로 관리 |
| 5.2 | PostgreSQL 이력 스키마 생성 | oracle.query_history, oracle.query_feedback |
| 5.3 | Repository 패턴 구현 | synapse_repo.py, history_repo.py |

### Phase 6: 도메인 적응 (3~5일)

| 단계 | 작업 | 설명 |
|------|------|------|
| 6.1 | 프롬프트 도메인 규칙 수정 | 범용 -> 비즈니스 프로세스 인텔리전스 |
| 6.2 | 값 매핑 초기 데이터 구축 | 조직명, 프로세스유형, 상태 등 |
| 6.3 | 테스트 질문 데이터 구축 | 비즈니스 도메인 NL2SQL 테스트 셋 |
| 6.4 | SQL Guard 화이트리스트 설정 | 비즈니스 DB 테이블 목록 |

### Phase 7: 인증/보안 통합 (2~3일)

| 단계 | 작업 | 설명 |
|------|------|------|
| 7.1 | Core 인증 미들웨어 통합 | JWT 검증, 사용자 정보 추출 |
| 7.2 | DB 읽기 전용 계정 설정 | oracle_reader 계정 생성 |
| 7.3 | 감사 로깅 구현 | 구조화 로깅 설정 |

### Phase 8: 테스트 및 검증 (3~5일)

| 단계 | 작업 | 설명 |
|------|------|------|
| 8.1 | 단위 테스트 작성 | SQL Guard, 그래프 검색, 임베딩 |
| 8.2 | 통합 테스트 작성 | NL2SQL 파이프라인 E2E |
| 8.3 | 비즈니스 도메인 테스트 | 도메인 질문 20개+ 수동 검증 |
| 8.4 | 성능 테스트 | 응답 시간, 동시 요청 처리 |

---

## 3. 파일별 이식 상세

### 3.1 그대로 이식 (수정 최소)

| 파일 | 줄 수 | 이유 |
|------|-------|------|
| `core/viz.py` | 297 | 도메인 무관한 범용 로직 |
| `core/embedding.py` | 55 | 임베딩 API 호출만 |
| `core/sql_guard.py` | 153 | 화이트리스트 추가만 필요 |

### 3.2 중간 수정 필요

| 파일 | 줄 수 | 수정 범위 |
|------|-------|----------|
| `core/llm_factory.py` | 213 | 설정 로드 방식 변경 |
| `core/graph_search.py` | 352 | datasource_id 체계, Cypher 쿼리 미세 조정 |
| `core/prompt.py` | 112 | 도메인 규칙 교체 |
| `core/sql_exec.py` | 380 | MySQL 코드 비활성화, PostgreSQL 집중 |
| `core/enum_cache_bootstrap.py` | 513 | datasource 체계 변경 |

### 3.3 대폭 수정/재작성

| 파일 | 줄 수 | 수정 범위 |
|------|-------|----------|
| `core/cache_postprocess.py` | 1,977 | 품질 게이트 로직 검증, Neo4j 쿼리 호환 |
| `routers/ask.py` | - | 파이프라인 분리로 구조 변경 |
| `routers/events.py` | - | Core Watch 이관 준비 |
| `models/history.py` | - | SQLite -> PostgreSQL 전환 |

### 3.4 새로 작성

| 파일 | 설명 |
|------|------|
| `pipelines/nl2sql_pipeline.py` | Ask 파이프라인 오케스트레이터 |
| `pipelines/react_pipeline.py` | ReAct 파이프라인 오케스트레이터 |
| `repositories/synapse_repo.py` | Synapse Graph/Meta API 접근 추상화 |
| `repositories/history_repo.py` | 이력 데이터 접근 추상화 |
| `config.py` | Pydantic Settings 기반 설정 |

---

## 4. 도메인 변경 체크리스트

| 항목 | K-AIR 원본 | 비즈니스 프로세스 인텔리전스 (Axiom) | 수정 위치 |
|------|-------------|----------------|----------|
| 프롬프트 도메인 규칙 | 수질/계측/시설물 | 프로세스/KPI/조직 | `core/prompt.py` |
| Enum 값 사전 | 수질기준, 시설유형 | 프로세스유형, 상태코드 | `enum_cache_bootstrap.py` |
| 값 매핑 초기 데이터 | 정수장명, 관측소명 | 조직명, 지표명 | Neo4j seed 스크립트 |
| 테스트 질문 셋 | "수질 기준 초과 시설은?" | "매출 성장률이 가장 높은 사업부는?" | 테스트 데이터 |
| DDL 주석 언어 | 범용 용어 | 비즈니스 프로세스 용어 | 메타데이터 설명 |

---

## 5. 이식 검증

### 5.1 기능 검증 체크리스트

| 기능 | 검증 방법 | 합격 기준 |
|------|----------|----------|
| NL2SQL Ask | 비즈니스 도메인 질문 20개 테스트 | 80% 이상 정확 SQL 생성 |
| ReAct | 복합 질문 5개 테스트 | 3단계 이내 정답 도달 |
| SQL Guard | 위험 SQL 10개 차단 테스트 | 100% 차단 |
| 캐시 | 동일 질문 재질의 | 캐시 히트 확인 |
| 시각화 | 결과별 차트 추천 확인 | 적절한 차트 유형 |
| 피드백 | 피드백 제출 -> 캐시 반영 | confidence 변경 확인 |
| 이력 | 쿼리 이력 조회 | 페이지네이션 동작 |

### 5.2 성능 검증

| 항목 | 기준 |
|------|------|
| Ask 응답 시간 | p95 < 5초 |
| ReAct 첫 응답 | < 3초 |
| 동시 요청 | 10개 동시 처리 |
| Neo4j 벡터 검색 | < 200ms |
| SQL 실행 | < 30초 (타임아웃) |

---

## 6. 리스크와 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| cache_postprocess.py 복잡도 | 이식 시 버그 가능성 | 단위 테스트 철저히 작성 |
| 도메인 용어 불일치 | NL2SQL 정확도 저하 | 비즈니스 도메인 전문가 용어 검토 |
| Neo4j 버전 차이 | Cypher 쿼리 비호환 | Neo4j 5.x 기능만 사용 |
| OpenAI API 변경 | LLM 호출 실패 | LLM Factory 추상화로 격리 |

---

## 관련 문서

- [00_overview/system-overview.md](../00_overview/system-overview.md): Oracle 개요
- [03_backend/service-structure.md](../03_backend/service-structure.md): 서비스 구조
- [08_operations/deployment.md](./deployment.md): 배포 절차
