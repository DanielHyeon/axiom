# Axiom — 핵심 요약 (v4.0)

## 1. 미션

온톨로지 기반 디지털 트윈 플랫폼 — Palantir Foundry와 유사한 시맨틱 레이어 아키텍처로 기업 데이터를 통합·분석·의사결정 지원

## 2. 기술 스택 (2026년 3월 기준)

- Frontend: React 19.2 + TypeScript 5.9 + Vite 7.3 + Tailwind CSS 4.2 + shadcn/ui (Radix UI)
- Backend: FastAPI (Python 3.12) × 5개 마이크로서비스
- State: Zustand 5.0 + TanStack Query 5.90 + TanStack Table 8.21
- Graph DB: Neo4j 5.18 (온톨로지 + 리니지 + BehaviorModel)
- 관계형 DB: PostgreSQL 15 (스키마: core, synapse, vision, weaver, oracle)
- Cache/Event Bus: Redis 7 (Streams + 캐싱 + Insight 잡 스토어)
- AI/LLM: LangChain + OpenAI GPT-4o (프로덕션) / Gemma-3-12B (로컬 개발)
- NL2SQL 엔진: SQLGlot AST 검증, Enum Cache, Sub-schema Context, LLM 품질 게이트, Value Mapping
- 인과 분석: statsmodels (Granger/VAR), scipy, pandas, scikit-learn
- 시각화: Cytoscape (그래프), Konva (프로세스 디자이너), Recharts (차트), Monaco (코드 에디터), Mermaid.js (ERD)
- 협업: Yjs (CRDT), y-websocket, y-indexeddb
- 국제화: i18next (ko/en)
- Infra: Docker Compose (postgres:15432, redis:16379, neo4j:17687, core:9002, weaver:9001, oracle:9004, synapse:9003, vision:9100, canvas:5174)
- 프로젝트 구조: `canvas/` (React SPA), `services/` (5개 마이크로서비스), `docs/` (기술 문서)

## 3. 서비스 아키텍처

### 5개 마이크로서비스 + 1 프론트엔드

| 서비스 | 포트 | 역할 |
|--------|------|------|
| **Core** | 8002 (→9002) | BPM 오케스트레이션, AI Agent, 인증/인가, 이벤트 소싱, 케이스 관리 |
| **Synapse** | 8003 (→9003) | 5계층 온톨로지 (KPI/Driver/Measure/Process/Resource), BehaviorModel, 프로세스 마이닝, 그래프 검색 |
| **Weaver** | 8001 (→9001) | 데이터 패브릭, 메타데이터 카탈로그, 데이터소스 통합, Insight 잡 스토어 |
| **Oracle** | 8004 (→9004) | NL2SQL 엔진 (ReAct + HIL), SQLGlot AST 검증, 품질 게이트, Value Mapping, Enum Cache, 피드백 분석 |
| **Vision** | 8000 (→9100) | OLAP 피벗, What-if DAG 시뮬레이션, 인과 분석 (Granger/VAR), 근본 원인 분석 (RCA) |
| **Canvas** | 5173 (→5174) | React SPA — 온톨로지 5계층, NL2SQL 채팅 (HIL), OLAP, ERD, 피드백 대시보드, 프로세스 디자이너 |

### 서비스 간 통신
- Redis Streams 이벤트 버스
- Transactional Outbox 패턴 (EventOutbox 테이블 + Relay Worker)
- 서비스 토큰 기반 내부 인증 (예: Oracle→Weaver insight 연동)

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

### Weaver 메타데이터
```
Datasource → Schema → Table → Column (스키마 인트로스펙션)
MetadataCatalog (글로서리, 비즈니스 용어)
InsightJob (Redis 캐시 기반 비동기 분석 잡)
```

## 5. 프론트엔드 라우트 구조

```
/dashboard                   — 케이스 대시보드 + 활동 타임라인
/cases/{id}/documents        — 문서 관리
/analysis/olap               — OLAP 피벗 분석
/analysis/nl2sql             — 자연어 쿼리 빌더 (채팅 UI + HIL)
/analysis/insight            — KPI 임팩트 분석 (3패널: KPI→Driver→Root Cause)
/data/ontology               — 온톨로지 5계층 그래프 브라우저 (Cytoscape)
/data/datasources            — 데이터 패브릭 메타데이터 + ERD (Mermaid.js)
/process-designer            — BPM 워크플로 디자이너 (Konva)
/watch                       — 알림 규칙 & 이벤트 모니터링
/settings/feedback           — 피드백 통계 대시보드 (admin)
/settings/*                  — 시스템 설정
```

피처 슬라이스 패턴: `features/<name>/{api,components,hooks,store,types,utils}/`

## 6. 시맨틱 레이어 철학

- 레거시 시스템에 대한 **읽기 전용** 접근
- AI 친화적 시맨틱 계층 (글로서리, 온톨로지, 메타데이터)
- 4대 정보 소스: 운영 DB, 레거시 코드, 공식 문서, 산업 표준
- "Golden Question" 방법론 — 목적 주도형 데이터 모델링

## 7. 인증 & 권한

- JWT: Access 15분 + Refresh 7일 (HS256)
- 역할: admin, manager, attorney, analyst, engineer, staff, viewer
- 멀티테넌트: `X-Tenant-Id` 헤더 + TenantMiddleware
- RLS (Row-Level Security): Insight 쿼리 시 세션 기반 데이터 격리
- 레이트 리밋: 엔드포인트별 세밀한 제한 (Oracle: 30 ask/min, 10 react/min)

## 8. 필수 개발 규칙

- TDD (pytest 우선)
- 작은 단위 커밋 + PR 필수
- Git Worktree 적극 활용
- 초등학생도 이해할 수 있게 코드 구현시 한글로 주석을 달것
- API 호출은 /api 폴더에서만
- 디버그 및 버그 찾기시 근본적인 원인을 파악하고 근본적인 해결책을 제시
- 코드 구현시 다하지도 않고 다했다고 거짓말 하지 않음
- 문서 작성 및 코드 작성 후 반드시 리뷰 agent 통해 리뷰하고 검증 받을것
- 반드시 구현 후 근거 제시 할것

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
```

## 11. 세션 이어하기 (Session Continuity)

- "Prompt is too long" 전에 `save-session.sh` 실행 (또는 VSCode: Ctrl+Shift+P → Tasks: Run Task → 세션 저장)
- 저장 위치: `.ai-context/session-summary.md`
- 새 세션 시작 시 `.ai-context/session-summary.md` 파일이 존재하면, 해당 파일을 읽고 이전 작업 컨텍스트를 파악한 후 이어서 진행할 것
- 세션 복구 후 작업이 완료되면 해당 파일의 "수동 메모" 섹션을 비워둘 것
