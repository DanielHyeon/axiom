# KAIR vs Axiom — 갭 분석 보고서 v2

> 작성일: 2026-03-20
> 목적: 온톨로지 기반 디지털 트윈 플랫폼(Axiom)과 레거시 현대화 + AI 데이터 분석 플랫폼(KAIR)의 기술·기능 갭을 식별하고, 상호 이식 기회를 도출한다.
> 참고: 기존 마이그레이션 문서 `services/oracle/docs/08_operations/migration-from-kair.md`

---

## 1. 프로젝트 정체성 비교

| 항목 | KAIR | Axiom |
|------|------|-------|
| **미션** | 레거시 코드 현대화 + AI 기반 데이터 분석 | 온톨로지 기반 디지털 트윈 (Palantir Foundry-like) |
| **핵심 가치** | 기존 시스템의 코드·데이터를 이해하고 변환 | 시맨틱 레이어로 기업 데이터를 통합·분석·의사결정 지원 |
| **온톨로지** | 5계층 (KPI/Measure/Driver/Process/Resource) | 4계층 (KPI/Measure/Process/Resource) |
| **데이터 접근** | MindsDB 페더레이션 + 직접 SQL | Weaver 데이터 패브릭 + 메타데이터 카탈로그 |
| **분석** | NL2SQL + 인과 분석 + What-if | NL2SQL + OLAP + What-if + RCA + 프로세스 마이닝 |
| **프로세스** | 코드 리니지 (AST→테이블 추적) | BPM 오케스트레이션 + BPMN 디자이너 + Saga |
| **이벤트** | 규칙 기반 모니터링 (기본) | CEP 엔진 + Redis Streams + Outbox 패턴 |
| **인증** | 미구현 | JWT + RBAC + 멀티테넌트 + RLS |

### 공통 DNA

두 프로젝트 모두 **"시맨틱 계층 위에서 AI가 데이터를 이해하고 질의한다"**는 동일한 철학을 공유한다:
- Neo4j 지식 그래프 중심
- NL2SQL ReAct 에이전트
- 온톨로지 기반 메타데이터 관리
- 벡터 임베딩 + 그래프 순회 하이브리드 검색

---

## 2. 기술 스택

```
                    KAIR                              Axiom
────────────────────────────────────────────────────────────────────
Frontend        Vue 3 + Pinia                  React 19 + Zustand + shadcn/ui
Build           Vite                            Vite 7
Graph Viz       Neo4j NVL + VueFlow            Cytoscape + Konva
Charts          Chart.js + ECharts             Recharts
Code Editor     Monaco                         Monaco
────────────────────────────────────────────────────────────────────
Backend         FastAPI + Spring Boot (GW)     FastAPI × 5 서비스
Gateway         Spring Boot (별도 서비스)       Core 서비스 내장
Task Queue      —                              Redis Streams (이벤트 버스)
Event Sourcing  —                              Transactional Outbox 패턴
────────────────────────────────────────────────────────────────────
Graph DB        Neo4j 5.23                     Neo4j 5.18
관계형 DB       PostgreSQL 16                  PostgreSQL 16
Cache           SQLite (LLM 캐시만)            Redis 7
Federation      MindsDB                        Weaver 직접 연결
────────────────────────────────────────────────────────────────────
LLM             Gemini + OpenAI (Cloud)        GPT-4o (Prod) / Gemma-3 (Dev)
Embedding       text-embedding-3-small (1536d) Gemma-3-12B (로컬)
RAG             HyDE + 5축 + 리랭킹            단일축 (5축 스캐폴드 존재)
────────────────────────────────────────────────────────────────────
Auth            없음                           JWT + RBAC + 멀티테넌트
Observability   기본 로깅                       structlog + 요청 ID + CEP
Process         코드 리니지 (AST)               BPM + BPMN + Saga + 프로세스 마이닝
Analytics       NL2SQL + 인과 분석              NL2SQL + OLAP + What-if + RCA
────────────────────────────────────────────────────────────────────
```

---

## 3. 서비스 아키텍처 매핑

| KAIR 서비스 | 역할 | Axiom 대응 | 관계 |
|-------------|------|-----------|------|
| `robo-data-text2sql` | NL→SQL + RAG + 모니터링 | `oracle` | **핵심 비교 대상** |
| `robo-data-domain-layer` | 5계층 온톨로지 + 인과 분석 + What-if | `synapse` + `vision` | **핵심 비교 대상** |
| `robo-data-fabric` | MindsDB 페더레이션 | `weaver` | 부분 대응 |
| `robo-data-analyzer` | 소스코드 분석 + 리니지 | — (Axiom은 코드 분석 불필요) | 도메인 차이 |
| `antlr-code-parser` | ANTLR AST 파싱 | — | 도메인 차이 |
| `process-gpt-gateway` | API 게이트웨이 | `core` (gateway 모듈) | 대응 |
| `robo-data-platform` | 인프라 오케스트레이션 | `docker-compose.yml` | 대응 |
| `robo-data-frontend` | Vue 3 SPA | `canvas` (React 19) | 프레임워크 상이 |
| — | — | `vision` | KAIR에 OLAP 피벗 없음 |
| — | — | `core` (BPM/Saga/CEP) | KAIR에 프로세스 엔진 없음 |

---

## 4. 핵심 역량 갭 분석

### 4.1 온톨로지 모델링

| 기능 | KAIR (`domain-layer`) | Axiom (`synapse`) | 분석 |
|------|----------------------|-------------------|------|
| **계층 구조** | 5계층: KPI → Measure → **Driver** → Process → Resource | 4계층: KPI → Measure → Process → Resource | KAIR에 **Driver 계층** 추가됨 — 인과 관계 명시적 분리 |
| **관계 타입** | 17종 (CAUSES, MEASURED_AS, INFLUENCES, LAGS, READS_FIELD, PREDICTS_FIELD 등) | 20+종 (HAS_MEASURE, DERIVES_FROM, IMPACTS, CAUSES 등) | Axiom이 더 다양하나, KAIR의 **LAGS(시차)**, **READS/PREDICTS_FIELD** 누락 |
| **인과 가중치** | `weight` (영향도) + `lag` (일 단위 시차) + `confidence` (0~1) | 관계에 가중치 없음 | 🔴 **Critical Gap** — 디지털 트윈의 핵심은 인과 강도·시차 |
| **행동 모델** | `OntologyBehaviorModel` — ML 모델 연결 (MindsDB/sklearn) + 피처 엔지니어링 | 없음 | 🔴 **Critical Gap** — 시뮬레이션 기반 |
| **BPMN 통합** | 노드에 `bpmnXml` 속성 | 별도 ProcessDefinition (Core 서비스) | Axiom이 더 분리된 설계 (장점) |
| **시계열 메타** | `timeColumn`, `timeGranularity`, `aggregationMethod` per node | 없음 | 🟠 High — OLAP 연동에 필요 |
| **HITL 검증** | 없음 | 구현됨 (검증 큐 + 품질 대시보드) | ✅ **Axiom 우위** |
| **OWL/RDF 내보내기** | 없음 | Turtle + JSON-LD 내보내기 | ✅ **Axiom 우위** |
| **스냅샷 버전관리** | 없음 | diff 추적 포함 버전관리 | ✅ **Axiom 우위** |

### 4.2 인과 분석 엔진

| 기능 | KAIR (`causal_analysis.py`, 575 LOC) | Axiom (`vision`) | 분석 |
|------|--------------------------------------|-------------------|------|
| **통계 검정** | VAR + Granger 인과성 + Pearson + ANOVA | 없음 (스텁) | 🔴 **Critical Gap** |
| **공선성 진단** | variance < 1e-10 / corr > 0.999 탐지 | 없음 | 🔴 Critical |
| **시차 탐지** | cross-correlation 스캔 (0..K 기간) | 없음 | 🔴 Critical |
| **신뢰도 합성** | `0.3*|pearson| + 0.2*lag + 0.2*granger + 0.3*stability` | 없음 | 🔴 Critical |
| **출력 형식** | `EdgeCandidate(source, target, lag, score, method, direction)` | — | 온톨로지 관계 자동 생성에 직접 활용 가능 |

> **핵심:** 디지털 트윈의 "무엇이 무엇에 영향을 미치는가"를 **데이터 기반으로 자동 발견**하는 엔진.
> Axiom의 온톨로지가 수동 구축이라면, KAIR의 인과 분석은 **자동 발견 계층**을 제공한다.

### 4.3 What-if 시뮬레이션

| 기능 | KAIR (`simulation_engine.py`, 359 LOC) | Axiom (`vision/what_if`) | 분석 |
|------|---------------------------------------|--------------------------|------|
| **DAG 전파** | 20-wave 증분 전파 (수렴 조건: delta < 1e-6) | API 스텁 존재 | 🔴 Critical |
| **ML 모델 실행** | MindsDB 예측 → sklearn LGBM 폴백 → 베이스라인 폴백 | 구조 정의만 | 🔴 Critical |
| **개입 모델** | `Intervention(nodeId, field, value)` → 연쇄 효과 추적 | ScenarioSolver 정의됨 | 🟠 High — Axiom에 구조 있으나 엔진 미완 |
| **시나리오 비교** | trace별 delta 계산 | tornado 차트 UI 존재 | 🟡 Medium — UI는 Axiom 우위 |

### 4.4 NL2SQL RAG 파이프라인

> **참고:** Axiom `oracle` 서비스의 `graph_search.py`에 5축 검색 + RRF 퓨전 + FK hop 스캐폴드가 존재.
> 프로덕션 경로(`nl2sql_pipeline.py` → `synapse_acl.search_schema_context()`)는 단일축만 사용 중.

| 기능 | KAIR (`text2sql`) | Axiom (`oracle`) | 분석 |
|------|-------------------|-------------------|------|
| **멀티축 검색** | 5축 프로덕션 (semantic, syntactic, relational, historical, heuristic) | 스캐폴드 존재, 프로덕션 미연결 | 🟠 High — 연결 작업 |
| **HyDE** | 가상 SQL/테이블 설명 3~5개 생성 → 멀티 검색 | 인터페이스만 정의 | 🟠 High |
| **FK 그래프 순회** | 3-hop 이웃 확장 | 스캐폴드 존재 | 🟠 High |
| **컬럼 값 힌트** | `SELECT DISTINCT col LIMIT 100` 실행 + 캐시 | 미구현 | 🟠 High |
| **쿼리 히스토리 재활용** | 벡터 유사도로 과거 SQL 검색 | 히스토리 저장만 | 🟠 High |
| **품질 게이트** | N라운드 LLM 심사 | 스텁 (confidence=0.95 고정) | 🟠 High |
| **Value Mapping** | 자연어↔DB 값 자동 매핑 | 스텁 (하드코딩 패턴매칭) | 🟠 High |
| **멀티턴 대화** | `ConversationCapsule` (zlib 압축, 200턴) | 단일 세션 | 🟠 High |
| **Human-in-the-Loop** | `ask_user` → 프론트엔드 자동 전환 | 미구현 | 🟡 Medium |
| **온톨로지 컨텍스트** | 없음 | ✅ 3-tier 신뢰도 (Confirmed/Reference/Low) | **Axiom 우위** |
| **시각화 추천** | 없음 | ✅ `recommend_visualization()` 자동 추천 | **Axiom 우위** |
| **레이트 리밋** | 없음 | ✅ 30 ask/min, 10 react/min | **Axiom 우위** |
| **ACL 패턴** | Oracle이 Neo4j 직접 접근 | ✅ Synapse ACL 통한 간접 접근 (아키텍처 우위) | **Axiom 우위** |

### 4.5 데이터 패브릭 / 메타데이터

| 기능 | KAIR (`fabric` + `text2sql`) | Axiom (`weaver`) | 분석 |
|------|------------------------------|-------------------|------|
| **데이터소스 통합** | MindsDB 페더레이션 (MySQL 프로토콜) | 직접 연결 (PG/MySQL/Oracle) + 스키마 인트로스펙션 | ✅ Axiom 우위 — 더 유연 |
| **메타데이터 카탈로그** | Neo4j에 `:DataSource`/`:Schema`/`:Table` 저장 | PostgreSQL 기반 + 글로서리 + 태깅 시스템 | ✅ Axiom 우위 — 거버넌스 |
| **스냅샷 버전관리** | 없음 | v1→v2 diff 추적 | ✅ Axiom 우위 |
| **ERD 시각화** | Mermaid ERD 자동 생성 | 미구현 | 🟡 Medium |
| **FK 수동 추가** | REST API + UI | Synapse schema_edit | ✅ 유사 |
| **Enum 캐시 추출** | 컬럼 값 자동 추출 + 캐시 | 스텁 존재 | 🟠 High |
| **유사 쿼리 검색** | 벡터 기반 `cache/similar-query` | 미구현 | 🟡 Medium |
| **피드백 통계** | 별점 + 코멘트 + 통계 | 기본 피드백 API | 🟡 Medium |
| **보안** | ⚠️ Neo4j에 비밀번호 평문 저장 | ✅ 환경변수 + 서비스 토큰 | **Axiom 우위** |

### 4.6 SQL 안전성

| 기능 | KAIR | Axiom | 분석 |
|------|------|-------|------|
| **SELECT-only** | ✅ | ✅ | 동등 |
| **LIMIT 자동 삽입** | ✅ | ✅ | 동등 |
| **SQLGlot AST 검증** | ✅ (구조적) | 문자열 기반 | 🟠 High |
| **Join depth 제한** | 10단계 | 미구현 | 🟡 Medium |
| **Subquery depth 제한** | 10단계 | 미구현 | 🟡 Medium |
| **멀티스테이트먼트 차단** | ✅ | ✅ | 동등 |

### 4.7 프로세스 인텔리전스

| 기능 | KAIR | Axiom | 분석 |
|------|------|-------|------|
| **프로세스 마이닝** | 없음 | Alpha/Heuristic/Inductive 마이너 (pm4py) | ✅ **Axiom 우위** |
| **BPM 오케스트레이션** | 없음 | WorkItem 라이프사이클 + Saga 보상 | ✅ **Axiom 우위** |
| **BPMN 디자이너** | 없음 | Konva 기반 비주얼 에디터 | ✅ **Axiom 우위** |
| **코드 리니지** | ✅ AST→테이블 추적 (6단계 파이프라인) | 없음 | KAIR 고유 (도메인 차이) |
| **이벤트 소싱** | 없음 | Outbox + Redis Streams + CEP | ✅ **Axiom 우위** |
| **Watch/모니터링** | 규칙 CRUD + 수동 실행 | CEP 엔진 + 에스컬레이션 정책 + 멀티채널 | ✅ **Axiom 우위** |

---

## 5. 종합 성숙도 비교

| 역량 | KAIR | Axiom | 리더 |
|------|------|-------|------|
| **온톨로지 모델 풍부도** | ⭐⭐⭐⭐⭐ (5계층 + 가중치 + 시차 + 행동모델) | ⭐⭐⭐⭐ (4계층 + HITL + 버전관리 + OWL) | KAIR (모델링) / Axiom (거버넌스) |
| **인과 분석** | ⭐⭐⭐⭐⭐ (VAR + Granger, 575 LOC) | ⭐ (스텁) | **KAIR** |
| **What-if 시뮬레이션** | ⭐⭐⭐⭐ (DAG 전파 + ML 폴백) | ⭐⭐ (구조만) | **KAIR** |
| **NL2SQL RAG** | ⭐⭐⭐⭐⭐ (5축 + HyDE + 품질게이트) | ⭐⭐⭐ (단일축 + 온톨로지 컨텍스트) | **KAIR** (검색) / Axiom (시맨틱) |
| **데이터 패브릭** | ⭐⭐⭐ (MindsDB 단일 경로) | ⭐⭐⭐⭐⭐ (멀티소스 + 카탈로그 + 글로서리) | **Axiom** |
| **프로세스 관리** | ⭐ (없음) | ⭐⭐⭐⭐⭐ (BPM + BPMN + Saga + 마이닝) | **Axiom** |
| **이벤트/실시간** | ⭐⭐ (규칙 기반) | ⭐⭐⭐⭐⭐ (CEP + Outbox + Streams) | **Axiom** |
| **보안/거버넌스** | ⭐ (미구현) | ⭐⭐⭐⭐⭐ (JWT + RBAC + RLS + 멀티테넌트) | **Axiom** |
| **프론트엔드 완성도** | ⭐⭐⭐⭐ (그래프 + 스키마 + 채팅) | ⭐⭐⭐⭐ (라우트 완비, 일부 UI 미완) | 동등 |

---

## 6. 이식 권장 항목 (우선순위별)

### 🔴 P0 — 디지털 트윈 핵심 역량 확보 (즉시)

디지털 트윈의 본질은 **"실제 시스템의 인과 관계를 모델링하고 시뮬레이션하는 것"**이다.
Axiom에 온톨로지 구조는 있으나, **인과 분석 엔진**과 **시뮬레이션 엔진**이 없으면 "그래프 뷰어"에 불과하다.

| # | 항목 | 기대 효과 | 예상 공수 | 대상 서비스 | KAIR 소스 참조 |
|---|------|----------|----------|-----------|---------------|
| 1 | **인과 분석 엔진 이식** | 온톨로지 관계를 데이터 기반으로 자동 발견 | ~8일 | `synapse` 또는 `vision` | `causal_analysis.py` (575 LOC) |
| 2 | **온톨로지 관계에 가중치·시차 추가** | CAUSES(weight=0.7, lag=3d) 같은 정량적 인과 표현 | ~3일 | `synapse` | `ontology.py` (관계 모델) |
| 3 | **What-if DAG 전파 엔진 이식** | "X를 10% 올리면 Y는 얼마나 변하나" 시뮬레이션 | ~7일 | `vision` | `simulation_engine.py` (359 LOC) |
| 4 | **행동 모델(BehaviorModel) 연동** | 온톨로지 노드에 ML 예측 모델 바인딩 | ~5일 | `synapse` + `vision` | `OntologyBehaviorModel` + `ModelFieldLink` |
| 5 | **시계열 메타데이터 추가** | 노드별 `timeColumn`, `granularity`, `aggregation` | ~2일 | `synapse` | `OntologyType` 속성 |

### 🟠 P1 — NL2SQL 고도화 (1~2 스프린트)

> Axiom에 스캐폴드가 이미 존재하는 항목이 많아, "신규 구현"이 아닌 **"활성화 + KAIR 로직 참조"** 수준.

| # | 항목 | 기대 효과 | 예상 공수 | 대상 | KAIR 참조 |
|---|------|----------|----------|------|-----------|
| 6 | **SQLGlot AST 검증 도입** | SQL 안전성 구조적 강화 | ~2일 | `oracle` | `app/core/` |
| 7 | **서브스키마 추출** | LLM 토큰 절약 + 노이즈 감소 | ~3일 | `oracle` | `build_sql_context` 출력 조립 |
| 8 | **Enum 캐시 활성화** | 필터 값 자동완성 + 쿼리 정확도 | ~2일 | `oracle` | `column_value_hints_flow.py` |
| 9 | **멀티축 RAG 프로덕션 연결** | 검색 정확도 대폭 향상 (스캐폴드→실연결) | ~8일 | `oracle` | `build_sql_context_parts/` |
| 10 | **HyDE 검색** | 의미론적 검색 품질 개선 | ~5일 | `oracle` | `hyde_flow.py` |
| 11 | **FK 그래프 순회 활성화** | 조인 컨텍스트 자동 확장 | ~4일 | `oracle` | `neo4j.py:_neo4j_fetch_fk_neighbors` |
| 12 | **품질 게이트 활성화** | 잘못된 SQL 배포 방지 (스텁→LLM 심사) | ~3일 | `oracle` | 후처리 파이프라인 |
| 13 | **Value Mapping 활성화** | 자연어↔DB 값 자동 변환 | ~5일 | `oracle` | Value Mapping 캐시 |

### 🟡 P2 — 사용자 경험 & 운영 (중기)

| # | 항목 | 기대 효과 | 예상 공수 | 대상 | KAIR 참조 |
|---|------|----------|----------|------|-----------|
| 14 | **멀티턴 대화 컨텍스트** | 연속 질문 문맥 유지 (⚠️ KAIR 토큰은 비서명 — JWT 보안 유지 필수) | ~5일 | `oracle` | `conversation_capsule.py` |
| 15 | **쿼리 자동 벡터화 + 클러스터링** | 유사 질문 캐시 히트율 향상 | ~5일 | `oracle` | Neo4j `:Query` 노드 |
| 16 | **ERD 시각화** | 스키마 이해도 향상 (Mermaid 기반) | ~3일 | `canvas` | ERDiagram.vue |
| 17 | **피드백 통계 대시보드** | NL2SQL 품질 모니터링 | ~3일 | `canvas` + `oracle` | 피드백 API |
| 18 | **Human-in-the-Loop** | 모호한 질문 시 사용자 확인 (Vue→React 재작성 필요) | ~8일 | `oracle` + `canvas` | `ReactInput.vue` |
| 19 | **Driver 계층 추가** | 5계층 온톨로지로 확장 (Measure↔Process 사이) | ~4일 | `synapse` | `OntologyType.label` |
| 20 | **LLM 리랭킹 + PRF** | 최종 컨텍스트 품질 개선 | ~6일 | `oracle` | 리랭킹 로직 |

---

## 7. 권장 실행 계획

| Phase | 기간 | 내용 | 예상 공수 | 목표 |
|-------|------|------|----------|------|
| **Phase 1** | 2~3주 | P0: 인과 분석 + 관계 가중치 + What-if 엔진 + 행동 모델 | ~25일 | **디지털 트윈 핵심 역량 확보** |
| **Phase 2** | 1~2주 | P1 전반: SQLGlot + 서브스키마 + Enum + 멀티축 RAG | ~20일 | NL2SQL 정확도 도약 |
| **Phase 3** | 2~3주 | P1 후반: HyDE + FK순회 + 품질게이트 + Value Mapping | ~17일 | RAG 파이프라인 완성 |
| **Phase 4** | 2~3주 | P2: 멀티턴 + 벡터화 + ERD + HIL + Driver 계층 | ~34일 | UX/운영 고도화 |

**총 예상: 7~11주**

### 검증 전략

| Phase | 검증 기준 |
|-------|----------|
| **Phase 1** | 인과 분석 → 시드 온톨로지에서 자동 발견한 관계가 수동 정의와 80%+ 일치 |
| **Phase 1** | What-if → 시드 데이터에서 KPI 변동 시뮬레이션 결과가 실측과 ±15% 이내 |
| **Phase 2** | Golden Query Set 50개 — NL2SQL 정답률 Phase 전/후 비교 |
| **Phase 2** | LLM 평균 컨텍스트 토큰 수 30%+ 감소 (서브스키마 효과) |
| **Phase 3** | Value Mapping 적용 후 "서울" → "SEL" 같은 변환 자동 성공률 90%+ |
| **Phase 4** | 멀티턴 대화 3턴 이상 문맥 유지 성공률 80%+ |

---

## 8. KAIR 핵심 소스 참조 경로

| 역량 | 파일 | LOC | 재사용성 |
|------|------|-----|---------|
| **인과 분석 엔진** | `KAIR/robo-data-domain-layer/services/causal_analysis.py` | 575 | ✅ 직접 이식 (scipy/statsmodels 의존) |
| **What-if 시뮬레이션** | `KAIR/robo-data-domain-layer/services/whatif/simulation_engine.py` | 359 | ✅ 직접 이식 (DAG 전파 알고리즘) |
| **5계층 온톨로지 모델** | `KAIR/robo-data-domain-layer/app/models/ontology.py` | 366 | ✅ 스키마 참조 (Axiom 4계층 확장) |
| **5축 RAG 검색** | `KAIR/robo-data-text2sql/app/react/tools/build_sql_context_parts/` | ~2000 | ⚠️ 부분 이식 (Axiom ACL 패턴 유지) |
| **HyDE 검색** | `KAIR/robo-data-text2sql/app/react/tools/build_sql_context_parts/hyde_flow.py` | ~150 | ✅ 로직 이식 |
| **대화 캡슐** | `KAIR/robo-data-text2sql/app/react/conversation_capsule.py` | 300+ | ⚠️ 보안 주의 (비서명 토큰) |
| **컬럼 값 힌트** | `KAIR/robo-data-text2sql/app/react/tools/build_sql_context_parts/column_value_hints_flow.py` | ~100 | ✅ 직접 이식 |
| **Neo4j 스키마** | `KAIR/robo-data-text2sql/app/core/neo4j_bootstrap.py` | 231 | ✅ 제약조건/벡터인덱스 참조 |

## 9. Axiom 수정 대상 파일

| 역량 | 대상 파일 | 작업 유형 |
|------|----------|----------|
| **인과 분석** | `services/synapse/app/services/` (신규) 또는 `services/vision/app/` (신규) | KAIR 이식 |
| **관계 가중치** | `services/synapse/app/services/ontology_service.py` | 속성 확장 |
| **What-if 엔진** | `services/vision/app/api/what_if.py` | 스텁→실구현 |
| **행동 모델** | `services/synapse/app/services/ontology_service.py` + Neo4j 스키마 | 신규 모델 |
| **시계열 메타** | `services/synapse/app/services/ontology_service.py` | 속성 추가 |
| **RAG 파이프라인** | `services/oracle/app/pipelines/nl2sql_pipeline.py` | 프로덕션 경로 변경 |
| **멀티축 검색** | `services/oracle/app/core/graph_search.py` | 스캐폴드→실구현 |
| **SQLGlot** | `services/oracle/app/core/` | 가드 교체 |
| **Value Mapping** | `services/oracle/app/core/value_mapping.py` | 스텁→실구현 |
| **품질 게이트** | `services/oracle/app/pipelines/cache_postprocess.py` | 스텁→LLM 심사 |
| **Enum 캐시** | `services/oracle/app/pipelines/enum_cache_bootstrap.py` | 스텁→실구현 |
| **마이그레이션 문서** | `services/oracle/docs/08_operations/migration-from-kair.md` | 참조·병행 갱신 |

---

## 10. 결론

### 전략적 판단

1. **Axiom의 플랫폼 인프라는 이미 엔터프라이즈급**이다 — 보안, 이벤트 소싱, BPM, 데이터 패브릭, 프로세스 마이닝 등 KAIR에 없는 역량이 풍부하다.

2. **KAIR에서 가져와야 할 것은 "디지털 트윈의 두뇌"**다 — 인과 분석 엔진(VAR+Granger), What-if DAG 전파, 행동 모델 바인딩. 이것 없이는 온톨로지가 정적 그래프에 머문다.

3. **NL2SQL RAG는 "활성화" 수준**이다 — Axiom에 이미 스캐폴드(5축, FK hop, value mapping, 품질 게이트)가 있으므로, KAIR 로직을 참조하여 프로덕션 연결하면 된다.

4. **Phase 1이 가장 중요**하다 — 인과 분석 + What-if가 도입되면 Axiom은 "데이터 뷰어"에서 "디지털 트윈"으로 질적 전환을 이룬다.
