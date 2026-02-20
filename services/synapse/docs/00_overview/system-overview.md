# Axiom Synapse - 시스템 개요

## 이 문서가 답하는 질문

- Axiom Synapse는 무엇이며 어떤 문제를 해결하는가?
- 비즈니스 프로세스 인텔리전스에서 온톨로지가 왜 필요한가?
- Synapse가 다른 Axiom 모듈과 어떻게 연동되는가?
- 4계층 온톨로지 구조란 무엇인가?
- Process Mining Engine은 무엇이며, EventStorming과 어떻게 통합되는가?

<!-- affects: all -->
<!-- requires-update: 01_architecture/architecture-overview.md, 01_architecture/process-mining-engine.md -->

---

## 1. Synapse 한줄 정의

> **"데이터 간 연결고리를 잇는 지능 신경망"**

Axiom Synapse는 비즈니스 프로세스 데이터를 **4계층 온톨로지(Resource - Process - Measure - KPI)** 로 구조화하고, 비정형 문서에서 자동으로 개체와 관계를 추출하여 **지식그래프**를 구축하며, **Process Mining Engine**으로 설계된 프로세스와 실제 실행 간의 차이를 분석하는 모듈이다.

---

## 2. 해결하는 문제

### 2.1 비즈니스 프로세스 인텔리전스의 데이터 단절 문제

| 문제 | 설명 | Synapse 해결 방식 |
|------|------|-------------------|
| **데이터 사일로** | 이해관계자 목록, 자산 평가서, 의사결정 문서가 각기 다른 형태로 존재 | 온톨로지 통합 그래프로 연결 |
| **관계 추적 불가** | "이 리소스가 어떤 프로세스에 할당되어 있는가?" 질의 불가 | Neo4j 그래프 경로 탐색 |
| **비정형 문서 사장** | 비즈니스 문서, 계약서, 보고서 등의 핵심 정보가 텍스트에 묻힘 | GPT-4o 기반 자동 추출 |
| **KPI 근거 부재** | 프로세스 효율성, 비용 절감률 등의 산출 근거를 역추적할 수 없음 | 4계층 온톨로지 역방향 탐색 |
| **프로세스 병목 미식별** | 어떤 프로세스 단계가 병목인지, SLA를 위반하는지 파악 불가 | Process Mining Engine 시간축 분석 |
| **설계-실행 괴리** | EventStorming으로 설계한 프로세스와 실제 실행의 차이를 추적할 수 없음 | Conformance Checking (적합성 검사) |
| **프로세스 변종 관리 부재** | 동일 프로세스가 실제로 몇 가지 경로로 실행되는지 알 수 없음 | Variant Analysis (변종 분석) |

### 2.2 누가 사용하는가

| 역할 | 사용 시나리오 | 접근 방식 |
|------|-------------|----------|
| **프로세스 분석가** | 프로젝트 전체 관계도 파악, 이해관계자 구조 탐색 | 온톨로지 브라우저 UI |
| **비즈니스 프로세스 설계자** | EventStorming 캔버스에서 프로세스 모델링, 시간축 분석, 병목 탐지 | Canvas 프로세스 디자이너 |
| **의사결정권자** | KPI 기반 현황 모니터링, 프로세스 적합성 현황 확인 | KPI 대시보드 + Conformance 리포트 |
| **이해관계자(Stakeholder)** | 자신의 관련 프로세스 및 리소스 관계 추적 | 제한적 그래프 뷰 |
| **데이터 분석가** | 비정형 문서에서 구조화 데이터 추출, 이벤트 로그 분석 | 추출 API + HITL 검토 + Process Mining API |
| **Axiom Oracle** | 자연어 질의 시 온톨로지 컨텍스트 활용 | Synapse REST API |
| **Axiom Vision** | 근본원인 분석 시 인과 그래프 참조, 시간축 What-if 시뮬레이션 | Synapse REST API |

---

## 3. 4계층 온톨로지 개요

비즈니스 프로세스 인텔리전스의 모든 데이터를 4개 계층으로 분류한다.

```
┌─────────────────────────────────────────────────────────────┐
│  KPI 계층        전략적 성과 지표                             │
│  예: 프로세스 효율성 85%, 비용 절감률 20%                    │
├─────────────────────────────────────────────────────────────┤
│  Measure 계층    프로세스 실행에서 파생된 정량 지표            │
│  예: 매출 500억, 비용 200억, 영업이익 50억                   │
├─────────────────────────────────────────────────────────────┤
│  Process 계층    비즈니스 프로세스 절차                       │
│  예: 데이터 수집 → 프로세스 분석 → 최적화 → 실행             │
├─────────────────────────────────────────────────────────────┤
│  Resource 계층   물리적 자원, 관계자, 자산                    │
│  예: 기업 A (매출 500억, 직원 1,000명)                       │
└─────────────────────────────────────────────────────────────┘

흐름: Resource ─참여→ Process ─산출→ Measure ─기여→ KPI
```

### 3.1 계층별 노드 유형

| 계층 | 노드 유형 | 설명 |
|------|----------|------|
| **Resource** | Company, Asset, Employee, CashReserve, Inventory, Financial, Contract | 프로젝트의 물리적 구성요소 |
| **Process** | DataCollection, ProcessAnalysis, Optimization, Execution, Review | 비즈니스 프로세스 단계 |
| **Measure** | Revenue, Cost, OperatingProfit, Throughput, CycleTime | 정량 측정값 |
| **KPI** | ProcessEfficiency, CostReduction, ROI, CustomerSatisfaction | 전략 성과 지표 |

### 3.2 핵심 관계

| 관계 | 방향 | 의미 |
|------|------|------|
| `PARTICIPATES_IN` | Resource → Process | 자원이 프로세스에 참여 |
| `PRODUCES` | Process → Measure | 프로세스가 측정값을 산출 |
| `CONTRIBUTES_TO` | Measure → KPI | 측정값이 KPI에 기여 |
| `DEPENDS_ON` | KPI → Measure | KPI가 측정값에 의존 |
| `INFLUENCES` | Process → KPI | 프로세스가 KPI에 영향 |

---

## 4. 핵심 기능

### 4.1 지식그래프 관리

- Neo4j 5 기반 그래프 데이터베이스
- 기존 K-AIR text2sql의 Table/Column/Query/ValueMapping 노드 이식
- 4계층 온톨로지 확장 노드 추가
- FK 관계 기반 그래프 경로 탐색 (최대 3홉)

### 4.2 벡터 유사도 검색

- Neo4j 벡터 인덱스 (table_vector, column_vector, query_vector)
- pgvector 연동을 통한 하이브리드 검색
- Oracle 모듈의 Text2SQL 파이프라인에 검색 결과 제공

### 4.3 비정형 문서 온톨로지 추출

- 문서 수집 → 텍스트 추출/청킹 → NER → 관계 추출 → 온톨로지 매핑
- GPT-4o Structured Output 기반 개체/관계 추출
- 신뢰도 점수 (0.0-1.0) 기반 HITL (Human-in-the-Loop) 검토
- 0.75 미만 신뢰도 필드에 대해 인간 확인 요청

### 4.4 스키마 편집

- 테이블/컬럼 설명 편집 API
- FK 관계 수동 관리
- Oracle Text2SQL의 정확도 향상을 위한 메타데이터 보강

### 4.5 Process Mining Engine

EventStorming 기반 프로세스 설계와 실제 이벤트 로그를 연결하여, 프로세스 발견/적합성 검사/병목 탐지를 수행하는 엔진이다.

#### 4.5.1 시간축 (Temporal Layer)

- Event 노드에 시간 속성 부여: `timestamp`, `duration`, `sla_threshold`, `expected_duration`, `actual_avg_duration`
- SLA 위반율 자동 계산 및 시계열 추적
- 프로세스 실행 시간의 추세 분석 (점점 느려지는지/빨라지는지)

#### 4.5.2 측정값 바인딩 (Measure Binding)

- Event 체인에서 Measure 노드를 자동 산출
- 4계층 온톨로지의 Measure/KPI 계층과 직접 연결
- 예시: `{출하됨}` ──produces──> `[배송완료율: 95.2%]`

#### 4.5.3 이벤트 로그 연결 (Event Log Binding)

- 각 Event 노드에 실제 데이터 소스 바인딩 (테이블, 컬럼, 필터 조건)
- XES/CSV 이벤트 로그 인제스트 지원
- `case_id_column`으로 프로세스 인스턴스 식별
- "설계된 프로세스"(EventStorming 모델)와 "실행된 프로세스"(이벤트 로그)의 브릿지

#### 4.5.4 프로세스 마이닝 알고리즘 (pm4py)

- **Process Discovery**: Alpha Miner, Heuristic Miner (노이즈 내성), Inductive Miner (사운드 보장)
- **Conformance Checking**: Token-based replay, fitness/precision/generalization 메트릭
- **Variant Analysis**: 프로세스 변종 통계, 편차 탐지
- **Bottleneck Detection**: 활동별 소요시간 분석, 대기시간 분석
- **BPMN Export**: Inductive Miner 기반 BPMN 모델 생성
- **Organizational Mining**: 리소스 프로파일, 작업부하 분석, 소셜 네트워크

---

## 5. 기술 스택

| 기술 | 버전 | 용도 |
|------|------|------|
| **Neo4j** | 5.x | 그래프 데이터베이스, 벡터 인덱스 |
| **pgvector** | - | PostgreSQL 벡터 확장 (하이브리드 검색) |
| **GPT-4o** | Structured Output | NER, 관계 추출, 온톨로지 매핑 |
| **FastAPI** | 0.100+ | REST API 서버 |
| **Python** | 3.11+ | 서비스 구현 언어 |
| **Redis Streams** | 7.x | 비동기 이벤트 수신 (Core → Synapse) |
| **pm4py** | 2.7+ | Process Mining 엔진 (Alpha/Heuristic/Inductive Miner, Conformance Checking, BPMN Export) |

---

## 6. Axiom 내 위치

```
┌─────────────────────────────────────────────────────────────┐
│  Axiom Canvas (React 프론트엔드)                               │
│    ├─ 온톨로지 브라우저 (← Synapse API)                        │
│    └─ 프로세스 디자이너 (EventStorming Canvas + Process Mining) │
├─────────────────────────────────────────────────────────────┤
│  Axiom Core (오케스트레이션)                                    │
│    ├─ HTTP → Synapse (동기 호출)                               │
│    └─ Redis Streams → Synapse (비동기 이벤트)                  │
├──────────┬──────────┬────────────────┬──────────┬───────────┤
│  Vision  │  Oracle  │    Synapse     │  Weaver  │           │
│  (분석)  │  (NL2SQL)│ (온톨로지 +    │ (패브릭) │           │
│          │          │  Process Mining)│          │           │
├──────────┴──────────┴────────────────┴──────────┴───────────┤
│  PostgreSQL 15 (RLS)  │  Neo4j 5 (그래프+벡터)  │ Redis     │
│  + 이벤트 로그 저장    │  + 프로세스 그래프       │           │
└─────────────────────────────────────────────────────────────┘
```

### 6.1 모듈 간 의존 관계

| 호출 방향 | 방식 | 용도 |
|----------|------|------|
| Core → Synapse | REST API | 온톨로지 CRUD, 추출 작업 요청, Process Mining 작업 요청 |
| Core → Synapse | Redis Streams | 프로젝트 데이터 변경 이벤트 → 온톨로지 자동 갱신 |
| Oracle → Synapse | REST API | NL2SQL 시 테이블/컬럼 메타데이터 조회, 그래프 경로 탐색 |
| Vision → Synapse | REST API | 근본원인 분석 시 인과 그래프 데이터 조회, 시간축 What-if 시뮬레이션 |
| Canvas → Synapse | Core 경유 | 온톨로지 브라우저 UI, EventStorming 캔버스 데이터, Process Mining 결과 시각화 |

### 6.2 금지 패턴

- Oracle → Synapse의 Neo4j 직접 쿼리 (반드시 Synapse API 경유)
- Vision → Synapse import (REST API 호출만 허용)
- Canvas → Synapse 직접 호출 (반드시 Core 경유)

---

## 7. K-AIR 이식 범위

### 7.1 이식 대상 (robo-data-text2sql-main)

| 원본 파일 | Synapse 대상 | 상태 |
|----------|-------------|------|
| `app/core/neo4j_bootstrap.py` | `synapse/app/graph/neo4j_bootstrap.py` | Phase 2 이식 |
| `app/core/graph_search.py` | `synapse/app/graph/graph_search.py` | Phase 2 이식 |

### 7.2 신규 개발

| 기능 | 대상 파일 | 일정 |
|------|----------|------|
| 4계층 온톨로지 | `synapse/app/graph/ontology_schema.py` | Phase 3.3 (20일) |
| 자동 인제스트 | `synapse/app/graph/ontology_ingest.py` | Phase 3.3 |
| NER 추출 | `synapse/app/extraction/ner_extractor.py` | Phase 3.4 (18일) |
| 관계 추출 | `synapse/app/extraction/relation_extractor.py` | Phase 3.4 |
| 온톨로지 매핑 | `synapse/app/extraction/ontology_mapper.py` | Phase 3.4 |

---

## 8. 용어 사전

| 용어 | 정의 |
|------|------|
| **온톨로지 (Ontology)** | 도메인 내 개체와 그 관계를 형식적으로 정의한 지식 체계 |
| **4계층 온톨로지** | Resource → Process → Measure → KPI 의 계층적 지식 구조 |
| **지식그래프 (Knowledge Graph)** | 개체(노드)와 관계(엣지)로 구성된 그래프 형태의 지식 표현 |
| **NER (Named Entity Recognition)** | 텍스트에서 고유명사, 금액, 일자 등 개체명을 자동 인식하는 기술 |
| **HITL (Human-in-the-Loop)** | AI 추출 결과를 인간이 검토/승인하는 품질 보증 프로세스 |
| **FK (Foreign Key)** | 데이터베이스 테이블 간 참조 관계 |
| **청킹 (Chunking)** | 긴 문서를 처리 가능한 크기(토큰 단위)로 분할하는 과정 |
| **Structured Output** | LLM이 사전 정의된 JSON 스키마에 맞춰 출력을 생성하는 기능 |
| **벡터 인덱스** | 임베딩 벡터의 유사도 검색을 위한 인덱스 (cosine similarity) |
| **그래프 경로 탐색** | 노드 간 관계를 따라 연결된 경로를 찾는 탐색 알고리즘 |
| **인제스트 (Ingest)** | 외부 데이터를 시스템 내부 형식으로 변환하여 저장하는 과정 |
| **EventStorming** | 도메인 이벤트를 중심으로 비즈니스 프로세스를 설계하는 협업 모델링 기법 (Command → Event → Policy) |
| **Process Mining** | 이벤트 로그에서 실제 프로세스 모델을 발견하고, 설계 모델과의 적합성을 검증하는 분석 기법 |
| **pm4py** | Python 기반 오픈소스 Process Mining 라이브러리 (Process Discovery, Conformance Checking, BPMN Export) |
| **Conformance Checking** | 설계된 프로세스 모델과 실제 이벤트 로그 간의 적합성을 검증하는 분석 (fitness, precision, generalization) |
| **Petri Net** | 프로세스 모델을 표현하는 수학적 형식 모델 (Place, Transition, Arc로 구성) |
| **BPMN** | Business Process Model and Notation. 프로세스를 시각적으로 표현하는 국제 표준 표기법 |
| **XES** | eXtensible Event Stream. 이벤트 로그의 IEEE 표준 XML 형식 |
| **이벤트 로그 (Event Log)** | 프로세스 실행 기록. case_id(인스턴스), activity(활동), timestamp(시각)의 3요소로 구성 |
| **프로세스 변종 (Variant)** | 동일 프로세스의 서로 다른 실행 경로. 활동 순서의 고유한 조합 |
| **SLA (Service Level Agreement)** | 서비스 수준 협약. 프로세스 단계별 최대 허용 소요시간 |

---

## 근거 문서

- K-AIR 역설계 분석 보고서 v2.0 섹션 4.7.2, 4.7.3
- ADR-001: Neo4j 5 선택 근거 (`99_decisions/ADR-001-neo4j-graph.md`)
- ADR-002: 4계층 온톨로지 설계 결정 (`99_decisions/ADR-002-4layer-ontology.md`)
- ADR-003: GPT-4o Structured Output 선택 (`99_decisions/ADR-003-gpt4o-extraction.md`)
- ADR-005: pm4py Process Mining 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
- `01_architecture/process-mining-engine.md` (Process Mining Engine 아키텍처)
