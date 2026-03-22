# Axiom — 핵심 요약 (v5.1)

## 1. 미션

온톨로지 기반 디지털 트윈 플랫폼 — Palantir Foundry와 유사한 시맨틱 레이어 아키텍처로 기업 데이터를 통합·분석·의사결정 지원

## 2. 기술 스택 (2026년 3월 기준)

- Frontend: React 19.2 + TypeScript 5.9 + Vite 7.3 + Tailwind CSS 4.2 + shadcn/ui (Radix UI)
- Backend: FastAPI (Python 3.12) × 6개 마이크로서비스
- State: Zustand 5.0 + TanStack Query 5.90 + TanStack Table 8.21
- Graph DB: Neo4j 5.18 (온톨로지 + 리니지 + BehaviorModel)
- 관계형 DB: PostgreSQL 16 (스키마: core, synapse, vision, weaver, oracle, olap, dw)
- Cache/Event Bus: Redis 7 (Streams + 캐싱 + Insight 잡 스토어)
- AI/LLM: LangChain + OpenAI GPT-4o (프로덕션) / Gemma-3-12B (로컬 개발)
- NL2SQL 엔진: SQLGlot AST 검증, Enum Cache, Sub-schema Context, LLM 품질 게이트, Value Mapping
- OLAP 엔진: Mondrian XML 파싱, 스타 스키마 SQL 생성, asyncpg 피벗 실행
- DMN 엔진: 결정 테이블 기반 규칙 실행 (FIRST/COLLECT/PRIORITY 정책)
- 관계 추론: LLM 기반 엔티티 관계 발견 + 레이어 규칙 폴백
- ETL: 파이프라인 정의/실행/이력 + Airflow DAG 생성/트리거
- 인과 분석: statsmodels (Granger/VAR), scipy, pandas, scikit-learn
- 시각화: Cytoscape (그래프), Konva (프로세스 디자이너), Recharts (차트), Monaco (코드 에디터), Mermaid.js (ERD)
- 협업: Yjs (CRDT), y-websocket, y-indexeddb
- 국제화: i18next (ko/en)
- Infra: Docker Compose (postgres:15432, redis:16379, neo4j:17687, core:9002, weaver:9001, oracle:9004, synapse:9003, vision:9100, olap-studio:9005, canvas:5174)
- 프로젝트 구조: `canvas/` (React SPA), `services/` (6개 마이크로서비스), `docs/` (기술 문서)

## 3. 서비스 아키텍처

### 6개 마이크로서비스 + 1 프론트엔드

| 서비스 | 포트 | 역할 |
|--------|------|------|
| **Core** | 8002 (→9002) | BPM 오케스트레이션, AI Agent, 인증/인가, 이벤트 소싱, 케이스 관리 |
| **Synapse** | 8003 (→9003) | 5계층 온톨로지, **시멘틱 계약 계층 (L2 Control Plane)**, L5 AI ContextPack, BehaviorModel, 프로세스 마이닝, 그래프 검색 |
| **Weaver** | 8001 (→9001) | 데이터 패브릭, 메타데이터 카탈로그, 데이터소스 통합, Insight 잡 스토어, **품질 수집 파이프라인** |
| **Oracle** | 8004 (→9004) | NL2SQL 엔진 (ReAct + HIL), SQLGlot AST 검증, 품질 게이트, Value Mapping, Enum Cache, 피드백 분석, **시멘틱 계약 컨텍스트 소비 (P3)** |
| **Vision** | 8000 (→9100) | OLAP 피벗, What-if DAG 시뮬레이션, 인과 분석 (Granger/VAR), 근본 원인 분석 (RCA) |
| **OLAP Studio** | 8000 (→9005) | 스타 스키마 OLAP 피벗, 큐브/Mondrian 관리, ETL 파이프라인, Airflow 연동, 데이터 리니지, AI 큐브 생성, 탐색형 NL2SQL |
| **Canvas** | 5173 (→5174) | React SPA — 온톨로지 5계층, NL2SQL 채팅 (HIL), OLAP, ERD, 피드백 대시보드, 프로세스 디자이너 |

### 서비스 간 통신
- Redis Streams 이벤트 버스
- Transactional Outbox 패턴 (EventOutbox 테이블 + Relay Worker)
- 서비스 토큰 기반 내부 인증 (예: Oracle→Weaver insight 연동)
- OLAP Studio Outbox 패턴 (olap.outbox_events + OlapRelayWorker)

## 4. 핵심 도메인 모델

### Core 도메인
```
Tenant → User (역할: admin, manager, attorney, analyst, engineer, staff, viewer)
Tenant → Case → CaseActivity (케이스 라이프사이클)
ProcessDefinition → ProcessInstance → WorkItem (BPM)
WatchRule → WatchAlert (실시간 모니터링)
EventOutbox (이벤트 소싱)
```

### Synapse 온톨로지 (Neo4j 5계층)
```
KPI Layer:      OEE, Throughput Rate, Defect Rate, Downtime
  ↑ DERIVED_FROM
Driver Layer:   환율변동, 수요변동, 유가변동 (인과 분석 결과 자동 생성)
  ↑ CAUSES / INFLUENCES
Measure Layer:  Availability, Performance, Quality, Cycle Time, MTBF
  ↑ OBSERVED_IN
Process Layer:  Assembly, Inspection, Packaging, Maintenance
  ↑ USES / SUPPORTS
Resource Layer: Machines, Robots, Operators, Materials, Sensors
```
관계 타입: `DERIVED_FROM`, `OBSERVED_IN`, `PRECEDES`, `SUPPORTS`, `USES`, `CAUSES`, `INFLUENCES`, `RELATED_TO`
관계 속성: `weight` (0.0~1.0), `lag` (일), `confidence` (0.0~1.0), `method`, `direction`
BehaviorModel: `:OntologyBehavior:Model` 멀티레이블 + `READS_FIELD` / `PREDICTS_FIELD` 링크

### Synapse 시멘틱 계약 계층 (L2 Control Plane + L5 AI Context)
```
L3 온톨로지 거버넌스:
  OntologyConcept (status: draft→review→approved→deprecated, owner_team, steward, sensitivity)
  OntologyTerm (surface_form, language, term_type: primary/synonym/alias/abbreviation/legacy)

L2 시멘틱 계약:
  SemanticEntity → SemanticMeasure (sql_expression, measure_type, additive_type)
  SemanticEntity → SemanticDimension (sql_expression, value_type, hierarchy_path)
  SemanticEntity → GrainContract (grain_key_set, time_grain, duplicate_resolution_rule)
  JoinContract (left/right entity, join_condition, allowed_for_ai, fanout_risk_score)
  QualityContract (target_type/id, freshness_sla, completeness/uniqueness threshold)
  SemanticRelease (version, review_status, deployed_at)

L5 AI 컨텍스트:
  ContextPack (intent_type별 프리셋: kpi_query, root_cause, trend, comparison 등)
  PromptPolicy (rule_type: must_use_metric, must_avoid_raw_table 등)

Semantic Compiler: 계약 검증 + SQL 뷰 템플릿 생성
이벤트: SEMANTIC_MEASURE_PUBLISHED, SEMANTIC_ENTITY_PUBLISHED, JOIN_CONTRACT_CREATED 등 5종
```
API: `/api/v3/synapse/semantic/*` (48 엔드포인트)

### Synapse 확장 도메인
```
DMN DecisionTable → DecisionRule → 조건 평가 (ast.literal_eval 안전 실행)
RelationInference: LLM 기반 엔티티 관계 추론 + 레이어 규칙 폴백
```

### Weaver 메타데이터
```
Datasource → Schema → Table → Column (스키마 인트로스펙션)
MetadataCatalog (글로서리, 비즈니스 용어)
InsightJob (Redis 캐시 기반 비동기 분석 잡)
QualityScore (freshness/completeness/uniqueness 자동 수집 + 가중 점수)
```

### OLAP Studio 도메인
```
DataSource → Model → Dimension/Fact/Join (스타 스키마)
Model → Cube → CubeDimension/CubeMeasure (큐브 정의)
Cube → MondrianDocument (XML 스키마)
ETLPipeline → ETLRun → ETLRunStep (파이프라인 실행)
PivotView (저장된 피벗 레이아웃)
QueryHistory (질의 이력)
LineageEntity → LineageEdge (데이터 흐름 추적)
AIGeneration (AI 생성 이력)
OutboxEvent (이벤트 발행)
```

### Vision 확장 도메인
```
WhatIfWizard: EdgeCandidate → SimulationNode → WhatIfScenario (9단계 시뮬레이션)
BusinessCalendar: 공휴일 DB + 영업일 필터링 + 시계열 집계
ScenarioStore: Redis 기반 시나리오 영속화
```

## 5. 프론트엔드 라우트 구조

```
/dashboard                   — 케이스 대시보드 + 활동 타임라인
/cases/{id}/documents        — 문서 관리
/analysis/olap               — OLAP 피벗 분석
/analysis/nl2sql             — 자연어 쿼리 빌더 (채팅 UI + HIL)
/analysis/insight            — KPI 임팩트 분석 (3패널: KPI→Driver→Root Cause)
/analysis/olap-studio        — OLAP Studio 피벗 분석 (드래그앤드롭)
/data/ontology               — 온톨로지 5계층 그래프 브라우저 (Cytoscape)
/data/datasources            — 데이터 패브릭 메타데이터 + ERD (Mermaid.js)
/data/sources                — OLAP 데이터소스 관리
/data/etl                    — ETL 파이프라인 관리
/data/cubes                  — 큐브/Mondrian 관리
/data/semantic-catalog       — 시멘틱 카탈로그 (개념/엔티티/지표/차원/조인/그레인 6탭 브라우저)
/data/lineage                — 데이터 리니지 시각화
/process-designer            — BPM 워크플로 디자이너 (Konva)
/watch                       — 알림 규칙 & 이벤트 모니터링
/settings/feedback           — 피드백 통계 대시보드 (admin)
/settings/*                  — 시스템 설정
```

피처 슬라이스 패턴: `features/<name>/{api,components,hooks,store,types,utils}/`
OLAP Studio 피처 슬라이스: `features/olap-studio/{api,components,hooks,pages}/`
시멘틱 카탈로그 피처 슬라이스: `features/semantic-catalog/{api,components,hooks,types}/`

## 6. 시맨틱 레이어 철학

- 레거시 시스템에 대한 **읽기 전용** 접근
- AI 친화적 시맨틱 계층 (글로서리, 온톨로지, 메타데이터)
- 4대 정보 소스: 운영 DB, 레거시 코드, 공식 문서, 산업 표준
- "Golden Question" 방법론 — 목적 주도형 데이터 모델링

### Option B' 아키텍처 (v5.1)

- **Control Plane (Synapse)**: 시멘틱 계약 정의·승인·배포 메타데이터 관리
- **Data Plane (Weaver)**: 쿼리 실행, 품질 수집, 캐시 — 후속 runtime 분리 가능
- **Consumer (Oracle)**: raw schema 대신 시멘틱 계약 컨텍스트를 LLM에 주입 (fallback 유지)
- 온톨로지 = 의미의 원천, 시멘틱 레이어 = 계산의 표준 실행체, AI Context = 의미+계산+품질 조합

### 6계층 의미론적 계층 구조

- L0 Physical Data (Weaver 인트로스펙션)
- L1 Canonical Data Product (OLAP Studio 스타 스키마)
- L2 Semantic Contract (Synapse: entity/measure/dimension/join/grain/quality)
- L3 Ontology (Synapse: Neo4j 5계층 + 개념 거버넌스 + 용어 사전)
- L4 Reasoning & Governance (Semantic Compiler 검증 + publish 승인 워크플로)
- L5 AI Context (ContextPack + PromptPolicy → Oracle NL2SQL 소비)

## 7. 인증 & 권한

- JWT: Access 15분 + Refresh 7일 (HS256)
- 역할: admin, manager, attorney, analyst, engineer, staff, viewer
- 멀티테넌트: `X-Tenant-Id` 헤더 + TenantMiddleware
- RLS (Row-Level Security): Insight 쿼리 시 세션 기반 데이터 격리
- 레이트 리밋: 엔드포인트별 세밀한 제한 (Oracle: 30 ask/min, 10 react/min)
- OLAP Studio 레이트 리밋: AI 생성 10/min, NL2SQL 20/min, 피벗 60/min, Airflow 5/min
- Synapse 레이트 리밋: 관계 추론 15/min
- RBAC Capability: datasource:read/write, etl:run/edit, cube:publish, pivot:save, lineage:read, ai:use, nl2sql:use

## 8. 필수 개발 규칙

- TDD (pytest 우선)
- 작은 단위 커밋 + PR 필수
- Git Worktree 적극 활용
- 초등학생도 이해할 수 있게 코드 구현시 한글로 주석을 달것
- API 호출은 /api 폴더에서만
- 디버그 및 버그 찾기시 근본적인 원인을 파악하고 근본적인 해결책을 제시
- 코드 구현시 다하지도 않고 다했다고 거짓말 하지 않음
- 문서 작성 및 코드 작성 후 반드시 리뷰 agent 통해 리뷰하고 검증 받을것
- 반드시 구현 후 code-reviewer agent로 리뷰 검증하고 수정 후 근거 제시 할것

## 9. 빠른 시작

```bash
docker-compose up -d

# 개발 서버
cd canvas && npm run dev     # Canvas UI: http://localhost:5173
cd services/core && uvicorn app.main:app --port 8002
cd services/weaver && uvicorn app.main:app --port 8001
cd services/oracle && uvicorn app.main:app --port 8004
cd services/synapse && uvicorn app.main:app --port 8003
cd services/vision && uvicorn app.main:app --port 8000
cd services/olap-studio && uvicorn app.main:app --port 8000  # → 9005

# 기본 계정: admin@local.axiom / admin (SEED_DEV_USER=1)
```

## 10. 핵심 설정값

```
DATABASE_URL=postgresql+asyncpg://arkos:arkos@postgres-db:5432/insolvency_os
JWT_SECRET_KEY=axiom-dev-secret-key-do-not-use-in-production
NEO4J_URI=bolt://neo4j-db:7687
REDIS_URL=redis://redis-bus:6379
WEAVER_INSIGHT_SERVICE_TOKEN=axiom-insight-svc-token-dev
SEED_DEV_USER=1

# OLAP Studio
OPENAI_API_KEY=             # AI 큐브 생성, NL2SQL (선택)
AIRFLOW_BASE_URL=           # Airflow 연동 (선택)
DW_SCHEMA=dw                # 데이터 웨어하우스 스키마 접두사
```

## 11. 신규 기능 요약 (v5.0)

### Schema Canvas G1-G8
- G1: FK 가시성 토글 (DDL/User/Fabric 소스별)
- G2: CardinalityModal 관계 편집 모달
- G3: 스키마 편집 API 연동 (useSchemaEdit)
- G4: column_pairs 구조 (복수 FK 매핑)
- G5: 실시간 캔버스 업데이트 (useCanvasPolling)
- G6: 시맨틱 벡터 검색 (useSemanticSearch)
- G7: 논리명/물리명 토글 (useDisplayMode)
- G8: 테이블 데이터 프리뷰 (DataPreviewPanel)

### OLAP Studio (신규 서비스)
- 스타 스키마 모델 관리 (Dimension/Fact/Join)
- Mondrian XML import/export/검증
- 큐브 CRUD + 검증 + 게시 워크플로
- 드래그앤드롭 피벗 분석 (PivotBuilder + ResultGrid)
- ETL 파이프라인 CRUD + 실행 + 이력
- Airflow DAG 생성/트리거/상태 조회
- 데이터 리니지 그래프 (Mermaid flowchart)
- AI 큐브/DDL 생성 (OpenAI)
- 탐색형 NL2SQL (4단계 파이프라인)
- Outbox 이벤트 발행 + Redis Relay Worker
- Vision/Synapse/Weaver 연계 클라이언트

### KAIR 도메인 이식
- What-if 시뮬레이션 위자드 9단계 (엣지 탐색 → DAG → 학습 → 시뮬레이션 → 비교)
- 비즈니스 캘린더 (공휴일 DB + 영업일 필터 + 시계열 집계)
- 시나리오 저장/비교/재실행 (Redis)
- DMN 규칙 엔진 (결정 테이블 + 3가지 적중 정책)
- LLM 관계 추론 엔진 (+ 레이어 규칙 폴백)
- LLM 시맨틱 캐시 (해시 + 임베딩 유사도 2단계)
- 자동 데이터소스 바인딩 (이름 + LLM 시맨틱 2단계)

### 온톨로지-시멘틱 계약 계층 (v5.1)

- L2 시멘틱 계약 7개 테이블 (ontology_concepts, ontology_terms, semantic_entities, semantic_measures, semantic_dimensions, join_contracts, grain_contracts, quality_contracts, semantic_releases)
- L5 AI ContextPack + PromptPolicy (의도별 LLM 프리셋: kpi_query, root_cause, trend, comparison 등)
- Semantic Compiler: 계약 검증 + SQL 뷰 템플릿 생성 (binding 검증, fanout 위험, ratio 검증)
- Oracle NL2SQL 시멘틱 컨텍스트 소비: raw schema → approved 계약 기반 프롬프트 전환 (graceful fallback)
- Oracle 의도 분류기: 키워드 기반 intent → ContextPack 자동 매칭
- Weaver 품질 수집 파이프라인: freshness/completeness/uniqueness 자동 측정 (15분 주기 BackgroundWorker)
- Weaver Insight 응답에 quality_context 자동 포함
- Canvas 시멘틱 카탈로그 UI: 6탭 브라우저 (/data/semantic-catalog) + 상태 전이 + 컴파일 + 배포
- Canvas NL2SQL 품질 경고 배지: 시멘틱 계약 사용 여부 + 품질 경고 + 의도 분류 표시
- 보안: SQL fragment validation (DDL/코멘트 차단), RBAC (ai-context analyst 이상), 프롬프트 주입 방어
- Transactional Outbox 이벤트 5종 (SEMANTIC_MEASURE_PUBLISHED 등)
- 테스트: 33 passed (Synapse semantic contract API)

### 운영 안정화
- 슬라이딩 윈도우 레이트 리밋 (테넌트별)
- structlog JSON 구조화 로깅
- 표준 API 응답 래퍼 + 전역 에러 핸들러
- CI/CD GitHub Actions (OLAP Studio + Canvas)
- OpenTelemetry 선택적 계측 + 요청 메트릭 미들웨어

## 12. 세션 이어하기 (Session Continuity)

- "Prompt is too long" 전에 `save-session.sh` 실행 (또는 VSCode: Ctrl+Shift+P → Tasks: Run Task → 세션 저장)
- 저장 위치: `.ai-context/session-summary.md`
- 새 세션 시작 시 `.ai-context/session-summary.md` 파일이 존재하면, 해당 파일을 읽고 이전 작업 컨텍스트를 파악한 후 이어서 진행할 것
- 세션 복구 후 작업이 완료되면 해당 파일의 "수동 메모" 섹션을 비워둘 것
