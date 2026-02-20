# K-AIR / Process-GPT 시스템 역설계 분석 보고서 (v2.0)

> **분석일**: 2026-02-19
> **분석 범위**: 소스코드 18개 저장소 + WorkFlowy 문서
> **출처**: `/media/daniel/E/AXIPIENT/projects/k-air/` (소스코드), WorkFlowy (설계 문서)
> **프로젝트**: K-AIR (엔터프라이즈 AI 데이터 플랫폼) + Process-GPT (범용 AI BPM 플랫폼)
> **조직**: uengine-oss

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [모듈 구성 (18개 저장소)](#3-모듈-구성-18개-저장소)
4. [**계획 vs 실제 구현 갭 분석**](#4-계획-vs-실제-구현-갭-분석)
5. [핵심 기술 스택](#5-핵심-기술-스택)
6. [데이터 아키텍처](#6-데이터-아키텍처)
7. [AI/LLM 아키텍처](#7-aillm-아키텍처)
8. [에이전트 시스템](#8-에이전트-시스템)
9. [프로세스 엔진 (BPM)](#9-프로세스-엔진-bpm)
10. [데이터 플랫폼 (K-AIR 고유)](#10-데이터-플랫폼-k-air-고유)
11. [프론트엔드 아키텍처](#11-프론트엔드-아키텍처)
12. [인프라 및 배포](#12-인프라-및-배포)
13. [설계 의사결정 분석](#13-설계-의사결정-분석)
14. [Axiom 적용 시사점](#14-axiom-적용-시사점)
15. [부록: 모듈별 상세 API 명세](#15-부록-모듈별-상세-api-명세)

---

## 1. 프로젝트 개요

### 1.1 두 개의 제품군

소스코드 분석 결과, K-AIR 폴더는 실제로 **두 개의 밀접한 제품군**으로 구성된다:

| 제품군 | 접두어 | 저장소 수 | 목적 |
|--------|--------|----------|------|
| **K-AIR** | `robo-data-*` | 2개 | 엔터프라이즈 데이터허브 → AI Ready 플랫폼 |
| **Process-GPT** | `process-gpt-*` | 14개 | 범용 AI 기반 비즈니스 프로세스 자동화 |
| **도메인 도구** | 기타 | 2개 | 코드 파싱, 이벤트 스토밍 |

두 제품군은 **공통 인프라**(Supabase, Neo4j, LLM)를 공유하며, K-AIR는 Process-GPT 플랫폼 위에 엔터프라이즈 도메인을 얹는 구조이다.

### 1.2 핵심 비전

```
Process-GPT: "자연언어로 비즈니스 프로세스를 정의하고, AI 에이전트가 자동 실행"
K-AIR:       "엔터프라이즈 데이터허브를 온톨로지 기반 AI Ready 플랫폼으로 전환"
```

### 1.3 규모

| 항목 | 값 |
|------|-----|
| 총 저장소 | 18개 |
| 추정 총 LOC | 100,000+ |
| 주요 언어 | Python (~60%), TypeScript/Vue (~30%), Java (~10%) |
| 마이크로서비스 | 10+ 독립 서비스 |
| API 엔드포인트 | 150+ |
| LLM 통합 포인트 | 20+ |

---

## 2. 시스템 아키텍처

### 2.1 전체 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         사용자 인터페이스 레이어                         │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │ process-gpt-vue3 │  │ robo-data-fabric │  │ eventstorming-tool   │  │
│  │ (SpikeAdmin)     │  │ /frontend        │  │ (Yjs + Konva)        │  │
│  │ Vue3 + Vuetify   │  │ Vue3 + Tailwind  │  │ Vue3 + Konva         │  │
│  │ BPMN/DMN/Chat    │  │ DataSource 관리  │  │ 실시간 협업 모델링    │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────┬───────────┘  │
│           │                      │                        │              │
│  ┌────────┴─────────┐  ┌────────┴─────────────┐         │              │
│  │ react-voice-agent│  │ data-platform-olap   │         │              │
│  │ (WebSocket 음성) │  │ (피벗 분석 UI)        │         │              │
│  └────────┬─────────┘  └────────┬─────────────┘         │              │
└───────────┼──────────────────────┼───────────────────────┼──────────────┘
            │                      │                        │
┌───────────┼──────────────────────┼───────────────────────┼──────────────┐
│           ▼                      ▼                        ▼              │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │              API Gateway (Spring Boot + JWT)                       │ │
│  │              process-gpt-gs-main/gateway                           │ │
│  │              - JWT 검증 (Supabase Auth)                           │ │
│  │              - X-Forwarded-Host → 멀티테넌트 라우팅               │ │
│  └──────┬──────────┬──────────┬──────────┬──────────┬────────────────┘ │
│         │          │          │          │          │                   │
│    ┌────▼────┐ ┌───▼───┐ ┌───▼───┐ ┌───▼────┐ ┌───▼────┐            │
│    │Complete │ │Memento│ │Fabric │ │Text2SQL│ │BPMN    │            │
│    │Service  │ │Service│ │Service│ │Service │ │Extract │            │
│    │(BPM코어)│ │(문서) │ │(데이터)│ │(NL2SQL)│ │(PDF→)  │            │
│    └──┬──────┘ └───┬───┘ └───┬───┘ └───┬────┘ └───┬────┘            │
│       │            │         │         │           │                   │
│  ┌────▼────────────▼─────────▼─────────▼───────────▼──────────────┐   │
│  │                    에이전트 레이어                                │   │
│  │  ┌───────────────┐  ┌──────────────┐  ┌──────────────────────┐ │   │
│  │  │ crewai-action │  │ deep-research│  │ agent-feedback       │ │   │
│  │  │ (CrewAI 실행) │  │ (보고서 생성)│  │ (피드백→지식 학습)   │ │   │
│  │  └───────┬───────┘  └──────┬───────┘  └──────────┬───────────┘ │   │
│  │          │                  │                      │             │   │
│  │  ┌───────▼──────────────────▼──────────────────────▼──────────┐ │   │
│  │  │              agent-utils (공유 도구 라이브러리)              │ │   │
│  │  │  DMN Tool | A2A Client | Safe Tool Loader | Event Logger  │ │   │
│  │  └──────────────────────────────────────────────────────────┘ │   │
│  │                                                                │   │
│  │  ┌──────────────────┐  ┌─────────────────────┐               │   │
│  │  │ a2a-orch         │  │ langchain-react      │               │   │
│  │  │ (A2A 오케스트라) │  │ (LangChain+MCP)      │               │   │
│  │  └──────────────────┘  └─────────────────────┘               │   │
│  └────────────────────────────────────────────────────────────────┘   │
│                                                                       │
│                        도메인 도구 레이어                              │
│  ┌───────────────────────┐                                           │
│  │ antlr-code-parser     │                                           │
│  │ (Java/PL-SQL 파싱)    │                                           │
│  └───────────────────────┘                                           │
└───────────────────────────────────────────────────────────────────────┘
            │            │            │            │
┌───────────▼────────────▼────────────▼────────────▼────────────────────┐
│                        데이터 레이어                                   │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐ │
│  │ Supabase     │  │ Neo4j 5      │  │ MindsDB      │  │ Redis    │ │
│  │ (PostgreSQL) │  │ (Graph +     │  │ (Data Fabric │  │ (Cache)  │ │
│  │ + pgvector   │  │  Vector      │  │  + ML)       │  │          │ │
│  │ + Auth       │  │  Index)      │  │              │  │          │ │
│  │ + Realtime   │  │              │  │              │  │          │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘ │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │                    외부 AI 서비스                                 │ │
│  │  OpenAI GPT-4o | Google Gemini | Anthropic Claude | Ollama      │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 K-AIR 수직적 4계층 아키텍처 (엔터프라이즈 데이터 도메인)

```
┌──────────────────────────────────────────────────────────────┐
│  다이나믹 레이어 (data-platform-olap)                        │
│  - OLAP 피벗 분석 (Mondrian XML + Star Schema)               │
│  - Text2SQL (LangGraph 워크플로우)                           │
│  - ETL (Apache Airflow DAGs)                                 │
│  - What-if 시뮬레이션 (미구현)                               │
├──────────────────────────────────────────────────────────────┤
│  도메인 레이어 (robo-data-text2sql + Neo4j)                  │
│  - 온톨로지 기반 지식그래프 (Neo4j 5)                        │
│  - 멀티축 벡터 검색 (question/hyde/regex/intent/PRF)         │
│  - ReAct 에이전트 (다단계 추론 SQL 생성)                     │
│  - FK 그래프 경로 탐색 (최대 3홉)                            │
├──────────────────────────────────────────────────────────────┤
│  데이터 패브릭 (robo-data-fabric)                            │
│  - MindsDB 통합 (다중 DB 추상화)                             │
│  - 메타데이터 추출 어댑터 (PostgreSQL, MySQL, Oracle)        │
│  - Neo4j 기반 DataSource/Schema/Table/Column 그래프          │
│  - SSE 스트리밍 진행률                                       │
├──────────────────────────────────────────────────────────────┤
│  피지컬 레이어 (대상 DB들)                                   │
│  - 계측 DB (IoT 센서 → Kafka)                                │
│  - 전사 DB (ETL 적재)                                        │
│  - PostgreSQL, MySQL 등                                      │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 온톨로지 4계층 구조 (엔터프라이즈 매핑)

```
┌─────────────────────────────────────────────────────┐
│  KPI 레이어       : 전사 경영전략 (BSC 연계)         │
├─────────────────────────────────────────────────────┤
│  메저 레이어      : 데이터 기반 업무평가 지표         │
├─────────────────────────────────────────────────────┤
│  프로세스 레이어  : 현장업무 흐름 및 지침             │
├─────────────────────────────────────────────────────┤
│  리소스 레이어    : 물리적 시스템, 인력, 자원         │
└─────────────────────────────────────────────────────┘

관계: Resource ──참여──▶ Process ──측정──▶ Measure ──달성──▶ KPI
      DataSource ──매핑──▶ Resource (피지컬↔도메인 자동연결)
```

---

## 3. 모듈 구성 (18개 저장소)

### 3.1 전체 모듈 맵

| # | 저장소명 | 유형 | 언어 | 역할 | 계층 |
|---|---------|------|------|------|------|
| 1 | **process-gpt-main** | 오케스트레이션 | YAML/SQL | K8s 배포 + DB 스키마 | 인프라 |
| 2 | **process-gpt-gs-main** | Gateway+Frontend | Java/Vue3 | API Gateway + 메인 SPA | 프레젠테이션 |
| 3 | **process-gpt-vue3-main** | Frontend | Vue3/TS | SpikeAdmin (BPMN/DMN/Chat) | 프레젠테이션 |
| 4 | **process-gpt-completion-main** | Backend Core | Python | BPM 엔진 + LLM 통합 | 비즈니스 로직 |
| 5 | **process-gpt-memento-main** | Backend | Python | 문서 처리 + RAG Q&A | 비즈니스 로직 |
| 6 | **process-gpt-agent-feedback-main** | Agent | Python | 피드백 → 지식 학습 | 에이전트 |
| 7 | **process-gpt-agent-utils-main** | Library | Python | 공유 CrewAI 도구 | 에이전트 |
| 8 | **process-gpt-crewai-action-main** | Agent | Python | CrewAI 액션 실행 (A2A) | 에이전트 |
| 9 | **process-gpt-crewai-deep-research-main** | Agent | Python | 멀티포맷 보고서 생성 | 에이전트 |
| 10 | **process-gpt-langchain-react-main** | Agent | Python | LangChain ReAct + MCP | 에이전트 |
| 11 | **process-gpt-a2a-orch-main** | Orchestrator | Python | A2A 프로토콜 오케스트레이션 | 에이전트 |
| 12 | **process-gpt-bpmn-extractor-main** | Worker | Python | PDF → BPMN/DMN/Skill 추출 | 워커 |
| 13 | **process-gpt-react-voice-agent-main** | Agent | Python | 음성 AI 에이전트 (WebSocket) | 에이전트 |
| 14 | **robo-data-fabric-main** | Backend | Python/Vue3 | 데이터 패브릭 (MindsDB) | 데이터 |
| 15 | **robo-data-text2sql-main** | Backend | Python | Text2SQL (Neo4j RAG) | 데이터 |
| 16 | **data-platform-olap-main** | Backend+Frontend | Python/Vue3 | OLAP 피벗 분석 | 데이터 |
| 17 | **antlr-code-parser-main** | Worker | Java | 다중 언어 코드 AST 파싱 | 도구 |
| 18 | **eventstorming-tool-vite-main** | Tool | JS/Vue3 | 이벤트스토밍 + 역공학 | 도구 |

### 3.2 모듈 간 의존 관계

```
process-gpt-main (K8s 오케스트레이션)
    │
    ├─▶ process-gpt-gs-main/gateway (API Gateway - Spring Boot)
    │       │
    │       ├─▶ process-gpt-completion-main (BPM 코어)
    │       │       ├── LLM 클라이언트 (OpenAI/Anthropic/Google/Ollama)
    │       │       ├── BPMN 실행 엔진
    │       │       ├── Saga 보상 트랜잭션
    │       │       ├── MCP 도구 관리
    │       │       └── Mem0 에이전트 통합
    │       │
    │       ├─▶ process-gpt-memento-main (문서 처리)
    │       │       ├── PDF/DOCX/PPTX/HWP 파싱
    │       │       ├── OpenAI Vision (이미지 분석)
    │       │       ├── Supabase Vector Store
    │       │       └── RAG 체인 (Q&A)
    │       │
    │       ├─▶ process-gpt-crewai-action-main (액션 실행)
    │       │       ├── A2A SDK 폴링 (5초)
    │       │       ├── 동적 Crew 생성
    │       │       └──uses──▶ process-gpt-agent-utils-main
    │       │
    │       ├─▶ process-gpt-crewai-deep-research-main (보고서)
    │       │       ├── CrewAI Flow (상태 머신)
    │       │       ├── 5개 Crew (계획/매칭/리포트/슬라이드/텍스트)
    │       │       └──uses──▶ process-gpt-agent-utils-main
    │       │
    │       ├─▶ process-gpt-agent-feedback-main (피드백 학습)
    │       │       ├── ReAct 에이전트 (5단계 추론)
    │       │       ├── 3가지 지식 저장소 (Memory/DMN/Skill)
    │       │       └── 충돌 분석 + 머지 전략
    │       │
    │       ├─▶ process-gpt-react-voice-agent-main (음성)
    │       │       ├── OpenAI Realtime GPT-4o (WebSocket)
    │       │       └── LangChain 도구 호출
    │       │
    │       └─▶ process-gpt-a2a-orch-main (A2A 오케스트레이션)
    │               ├── 동기/비동기 실행 모드
    │               └── 웹훅 리시버 (별도 Pod)
    │
    ├─▶ process-gpt-gs-main/frontend (메인 SPA)
    │       └── process-gpt-vue3-main (SpikeAdmin) 과 동일 기반
    │
    ├─▶ robo-data-fabric-main (데이터 패브릭)
    │       ├── MindsDB HTTP API 클라이언트
    │       ├── 메타데이터 추출 어댑터 (PostgreSQL/MySQL/Oracle)
    │       └── Neo4j 메타데이터 그래프
    │
    ├─▶ robo-data-text2sql-main (NL2SQL)
    │       ├── Neo4j 멀티축 벡터 검색
    │       ├── ReAct 컨트롤러 (다단계 추론)
    │       ├── SQL Guard (안전장치)
    │       ├── 이벤트 룰 / CEP 엔진
    │       └── 감시 에이전트
    │
    └─▶ data-platform-olap-main (OLAP)
            ├── Mondrian XML 파서
            ├── LangGraph Text2SQL 워크플로우
            └── Apache Airflow ETL DAGs
```

### 3.3 계층별 분류

```
┌─ 프레젠테이션 (3개) ────────────────────────────────────────┐
│  process-gpt-vue3-main    : 35개 AI 생성기, BPMN/DMN, Chat  │
│  process-gpt-gs-main      : Vue3 SPA + Spring Boot Gateway  │
│  eventstorming-tool-vite  : Yjs CRDT 실시간 협업 모델링     │
└──────────────────────────────────────────────────────────────┘

┌─ 비즈니스 로직 (3개) ───────────────────────────────────────┐
│  process-gpt-completion   : BPM 엔진 + LLM + Saga 보상      │
│  process-gpt-memento      : 문서 처리 + RAG + 다국어 포맷    │
│  process-gpt-bpmn-extract : PDF → BPMN/DMN 자동 추출         │
└──────────────────────────────────────────────────────────────┘

┌─ 에이전트 (6개) ────────────────────────────────────────────┐
│  crewai-action            : A2A 기반 CrewAI 액션 실행        │
│  crewai-deep-research     : 멀티포맷 보고서 (Flow 상태머신)  │
│  agent-feedback           : 피드백 → 지식 자동 학습          │
│  agent-utils              : 공유 도구 라이브러리             │
│  langchain-react          : LangChain ReAct + MCP 9개 도구   │
│  a2a-orch                 : Agent-to-Agent 오케스트레이션    │
│  react-voice-agent        : 음성 AI (GPT-4o Realtime)        │
└──────────────────────────────────────────────────────────────┘

┌─ 데이터 플랫폼 (3개) ──────────────────────────────────────┐
│  robo-data-fabric         : MindsDB + 메타데이터 추출        │
│  robo-data-text2sql       : Neo4j RAG + ReAct SQL 생성       │
│  data-platform-olap       : Mondrian OLAP + LangGraph        │
└──────────────────────────────────────────────────────────────┘

┌─ 인프라/도구 (3개) ─────────────────────────────────────────┐
│  process-gpt-main         : K8s 배포 매니페스트 + DB 스키마  │
│  antlr-code-parser        : Java/PL-SQL/PostgreSQL AST 파싱  │
│  eventstorming-tool-vite  : 코드 역공학 + DDD 설계 도구      │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. 계획 vs 실제 구현 갭 분석

> **검증 방법**: WorkFlowy 설계 문서의 6개 K-AIR 모듈을 GitHub (uengine-oss 조직, 50+ 저장소 전수 조사) 및 소스코드 폴더와 대조

### 4.1 K-AIR 원래 설계 (WorkFlowy 기준: 6개 마이크로서비스)

```
┌─────────────────────────────────────────────────────────────────┐
│  WorkFlowy 설계 문서에 명시된 6개 robo-data-* 모듈              │
│                                                                 │
│  1. robo-data-platform      → 플랫폼 코어 (인증/오케스트레이션)│
│  2. robo-data-analyzer      → 분석 엔진 (What-if, OLAP)        │
│  3. robo-data-text2sql      → 자연어→SQL 변환 (LLM)            │
│  4. robo-data-domain-layer  → 온톨로지/지식그래프               │
│  5. robo-data-fabric        → 데이터 패브릭 (MindsDB)          │
│  6. robo-data-frontend      → 웹 프론트엔드                    │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 실제 구현 현황 (GitHub + 소스코드 검증)

| # | 계획된 모듈 | GitHub 존재 | 소스코드 | 상태 |
|---|-----------|:-----------:|:--------:|------|
| 1 | robo-data-platform | ❌ | ❌ | **미생성** - 저장소 자체가 없음 |
| 2 | robo-data-analyzer | ❌ | ❌ | **미생성** - 저장소 자체가 없음 |
| 3 | robo-data-text2sql | ✅ public | ✅ | **구현됨** - 가장 성숙한 모듈 (24개 코어 모듈, 12개 라우터) |
| 4 | robo-data-domain-layer | ❌ | ❌ | **미생성** - 저장소 자체가 없음 |
| 5 | robo-data-fabric | ✅ public, fork | ✅ | **구현됨** - 메타데이터 추출 + MindsDB 연동 |
| 6 | robo-data-frontend | ❌ | ❌ | **미생성** - 저장소 자체가 없음 |

> **결론**: 6개 중 **2개만 구현**, 4개는 저장소조차 생성되지 않았다.

### 4.3 미구현 모듈의 기능 흡수 맵

4개 미구현 모듈의 기능이 어디로 흡수되었는지 소스코드 근거와 함께 분석:

#### 4.3.1 robo-data-platform (플랫폼 코어) → 3개 모듈로 분산

```
계획: robo-data-platform
  ├─ 인증 (Keycloak)
  ├─ API Gateway
  └─ 서비스 오케스트레이션

실제 흡수:
  ├─▶ process-gpt-gs-main/gateway (Spring Boot)
  │     근거: ForwardHostHeaderFilter.java
  │     - JWT 토큰 검증 (쿠키에서 access_token 추출)
  │     - JJWT 0.9.1로 서명 검증 (HS256)
  │     - X-Forwarded-Host → 멀티테넌트 라우팅
  │     - 보호 경로: /completion/*, /autonomous/*, /memento/*, /agent/*, /mcp/*
  │
  ├─▶ process-gpt-completion-main/main.py
  │     근거: DBConfigMiddleware
  │     - X-Forwarded-Host로 테넌트 결정
  │     - ContextVar 기반 멀티테넌트 DB 격리
  │     - 10개 라우트 모듈 등록 (프로세스/채팅/MCP/에이전트 등)
  │
  └─▶ process-gpt-vue3-main (Keycloak-js 24.0.2)
        근거: package.json의 keycloak-js 의존성
        - 프론트엔드에서 Keycloak SSO 직접 통합
        - @casl/vue로 권한 관리 (RBAC)
```

#### 4.3.2 robo-data-analyzer (분석 엔진) → 2개 모듈로 분산

```
계획: robo-data-analyzer
  ├─ What-if 시뮬레이션
  ├─ OLAP 분석
  └─ 이벤트 감지 에이전트

실제 흡수:
  ├─▶ data-platform-olap-main
  │     근거: backend/app/services/sql_generator.py, xml_parser.py
  │     - Mondrian XML 파서 → 큐브 메타데이터
  │     - 피벗 쿼리 SQL 생성기
  │     - LangGraph Text2SQL 워크플로우 (langgraph_workflow/text2sql.py)
  │     - Apache Airflow ETL DAGs (데이터 분석)
  │     - 드릴다운/드릴업 지원
  │
  └─▶ robo-data-text2sql-main
        근거: app/routers/events.py (46KB), app/core/simple_cep.py
        - 이벤트 룰 CRUD (/events/rules/*)
        - 스케줄러 시작/중지 (/events/scheduler/*)
        - SimpleCEP 엔진 (이벤트 감지)
        - SSE 알람 스트림 (/events/stream/alarms)
        - 감시 에이전트 (/watch-agent/*)
        ⚠️ What-if 시뮬레이션은 미구현 (WorkFlowy TODO에서도 "범위 외")
```

#### 4.3.3 robo-data-domain-layer (온톨로지) → text2sql Neo4j에 흡수

```
계획: robo-data-domain-layer
  ├─ Schema 모델링
  ├─ 온톨로지 추출
  └─ See-why 원인분석

실제 흡수:
  └─▶ robo-data-text2sql-main (Neo4j 그래프)
        근거: app/core/neo4j_bootstrap.py, graph_search.py
        - Neo4j 노드: Table, Column, Query, ValueMapping
        - 벡터 인덱스: table_vector, column_vector, query_vector
        - FK 그래프 관계: (:Column)-[:FK_TO]->(:Column)
        - 스키마 편집 API: /schema-edit/tables/*/description
        - 유효성 관리: text_to_sql_is_valid 플래그

        ⚠️ 그러나 원래 계획의 핵심 기능 일부 누락:
        - 4계층 온톨로지 (Resource→Process→Measure→KPI) → 미구현
        - 비정형 문서 → 온톨로지 추출 → 미구현
        - See-why 원인분석 → 미구현 (WorkFlowy에서도 "데모수준")
```

#### 4.3.4 robo-data-frontend (웹 UI) → fabric 내부로 흡수

```
계획: robo-data-frontend (독립 저장소)

실제 흡수:
  └─▶ robo-data-fabric-main/frontend/ (Vue 3 + Tailwind)
        근거: frontend/package.json, frontend/src/views/
        - Dashboard.vue: 대시보드
        - DataSources.vue: 데이터소스 관리
        - QueryEditor.vue: SQL 에디터 (Monaco)
        - MaterializedTables.vue: 물리화 테이블
        - MindsDBObjects.vue: Models/Jobs/KB 관리
        - Pinia 상태 관리 (datasources, query 스토어)
        - Axios HTTP 클라이언트 → FastAPI 백엔드
```

### 4.4 갭 요약 매트릭스

| 계획된 기능 | 구현 상태 | 구현 위치 | 완성도 |
|------------|:---------:|----------|:------:|
| 인증 (Keycloak SSO) | ✅ | gs-main/gateway + vue3 | 80% |
| API Gateway | ✅ | gs-main/gateway (Spring Boot) | 90% |
| 서비스 오케스트레이션 | ✅ | completion-main + a2a-orch | 70% |
| OLAP 피벗 분석 | ✅ | data-platform-olap | 80% |
| Text2SQL | ✅ | text2sql (ReAct + RAG) | **95%** |
| 이벤트 감지 | ✅ | text2sql (SimpleCEP + events) | 60% |
| What-if 시뮬레이션 | ❌ | 미구현 | 0% |
| 데이터 패브릭 | ✅ | fabric (MindsDB + Neo4j) | 85% |
| 메타데이터 추출 | ✅ | fabric (3개 DB 어댑터) | 90% |
| Schema 모델링 | ✅ | text2sql (Neo4j 그래프) | 70% |
| 4계층 온톨로지 | ❌ | 미구현 (R→P→M→KPI) | 0% |
| 비정형→온톨로지 추출 | ❌ | 미구현 | 0% |
| See-why 원인분석 | ⚠️ | 데모 수준 | 20% |
| 데이터 프론트엔드 | ✅ | fabric/frontend (Vue3) | 75% |
| 감시 에이전트 | ⚠️ | text2sql (/watch-agent) | 40% |

### 4.5 계획 대비 실제 아키텍처 전환

```
[계획] K-AIR 독립 6개 마이크로서비스
┌──────────┐ ┌──────────┐ ┌──────────┐
│ platform │ │ analyzer │ │ text2sql │
└──────────┘ └──────────┘ └──────────┘
┌──────────┐ ┌──────────┐ ┌──────────┐
│ domain   │ │ fabric   │ │ frontend │
└──────────┘ └──────────┘ └──────────┘

        ↓ 실제 구현 시 전환 ↓

[실제] Process-GPT 플랫폼 위에 K-AIR 2개 모듈만 독립
┌─────────────────────────────────────────────────┐
│            Process-GPT 플랫폼 (14개 모듈)        │
│  gateway │ completion │ memento │ agents │ ...  │
├─────────────────────────────────────────────────┤
│  K-AIR 독립 모듈 (2개)                           │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ robo-data-   │  │ robo-data-text2sql       │ │
│  │ fabric       │  │ (도메인+분석 기능 통합)   │ │
│  └──────────────┘  └──────────────────────────┘ │
├─────────────────────────────────────────────────┤
│  도메인 도구 (2개)                               │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ data-platform│  │ antlr-code-parser        │ │
│  │ -olap        │  │                          │ │
│  └──────────────┘  └──────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

### 4.6 전환 이유 분석

| # | 설계 변경 | 추정 이유 |
|---|----------|----------|
| 1 | **독립 K-AIR → Process-GPT 위 레이어** | Process-GPT가 범용 플랫폼으로 성장하면서 인증/게이트웨이/오케스트레이션이 이미 구현됨 → K-AIR 별도 구현 불필요 |
| 2 | **domain-layer 미구현** | 4계층 온톨로지(R→P→M→KPI)는 엔터프라이즈 도메인 지식 필요 → text2sql의 스키마 그래프가 1차 대체 |
| 3 | **analyzer → olap + text2sql 분산** | OLAP은 Mondrian 기반 별도 도구로, 이벤트 감지는 text2sql에 CEP로 흡수 → 단일 모듈보다 기능별 분리 |
| 4 | **frontend → fabric 내장** | 데이터 관리 UI는 fabric 백엔드와 밀접 → 모노레포 형태가 개발 효율적 |
| 5 | **6개 → 2개 축소** | Process-GPT 플랫폼의 성숙으로 범용 기능(인증/UI/오케스트레이션) 재구현 불필요 → K-AIR 고유 도메인 로직만 독립 |

### 4.7 미구현 기능별 Axiom 구축 전략

> **전제**: Axiom은 비즈니스 프로세스 인텔리전스 플랫폼으로서 K-AIR의 미구현 기능을 재설계하여 적용한다.
> Axiom 기존 계획(Phase 1-3)과의 통합 지점을 명시하고, 엔터프라이즈 운영 도메인에 맞게 재해석한다.

#### 4.7.1 What-If 시뮬레이션 엔진

**K-AIR 상태**: 완전 미구현 (0%) — WorkFlowy에서도 "범위 외" 처리
**Axiom 필요성**: 비즈니스 최적화 계획 수립 시 다양한 성과 시나리오 비교 필수 (단기/중기/장기 계획, 시장 변동, 운영 효율화 시나리오 등)

```
┌─ What-If 시뮬레이션 엔진 (Axiom Phase 3.2) ──────────────────┐
│                                                                 │
│  1. 제약조건 정의 (Constraint Definition)                       │
│  ├─ 성과 지표 조정 (기본 vs 낙관 vs 비관)                      │
│  ├─ 계획 기간 변경 (단기, 중기, 장기)                          │
│  ├─ 현금흐름 가정 변경 (성장률, WACC)                          │
│  ├─ 리소스 분류 변경 (우선순위 재분류)                         │
│  └─ 자산 처분 가액 조정                                        │
│                                                                 │
│  2. 의존성 그래프 연산                                          │
│  ├─ 인과 모델: 현금흐름 → 성과 지표 → 조직 생존 가능성          │
│  ├─ 비즈니스 제약: 기업 가치 평가 원칙, 이해관계자 동의 임계값  │
│  └─ 최적화 문제 컴파일 (Phase 3 프로세스 최적화기 확장)         │
│                                                                 │
│  3. 다중 시나리오 솔버 (scipy.optimize 확장)                    │
│  ├─ 기본 시나리오 (현재 가정)                                   │
│  ├─ 낙관 시나리오 (+10% EBITDA, 낮은 WACC)                     │
│  ├─ 비관 시나리오 (-15% EBITDA, 금리 상승)                     │
│  ├─ 스트레스 테스트 (자산 급매, 조기 성과 달성)                 │
│  └─ 사용자 정의 시나리오 (UI 슬라이더)                          │
│                                                                 │
│  4. 결과 비교 및 시각화                                         │
│  ├─ 시나리오별: 실현가능성 점수, 총 성과 산출액, 계획 기간      │
│  ├─ 비교표: 시나리오 | 1차년도CF | 10차년도CF | 이해관계자별 성과│
│  ├─ 토네이도 차트 (각 파라미터 민감도)                          │
│  └─ 전환점 분석 ("성장률 몇 %에서 계획 실패하는가?")            │
│                                                                 │
│  5. 의사결정 지원                                               │
│  ├─ 최적 시나리오 추천 (실현가능성 + 이해관계자 만족도 최대화)  │
│  ├─ 전환점 식별 (어느 시점에서 계획이 실패하는가?)              │
│  └─ 시나리오 비교 보고서 PDF 내보내기                           │
└─────────────────────────────────────────────────────────────────┘
```

**데이터베이스 (신규 테이블)**:

| 테이블 | 주요 컬럼 | 용도 |
|--------|----------|------|
| `what_if_scenarios` | case_id, scenario_name, constraints_json, results_json | 시나리오 정의 및 결과 |
| `scenario_parameter_overrides` | scenario_id, parameter_path, override_value | 파라미터 오버라이드 |
| `scenario_results` | scenario_id, metric, value, period | 메트릭별 결과 (시나리오당 N행) |

**API 엔드포인트**:

```
POST   /api/v3/cases/{case_id}/what-if/create          # 시나리오 생성
PUT    /api/v3/cases/{case_id}/what-if/{scenario_id}    # 파라미터 수정
POST   /api/v3/cases/{case_id}/what-if/{scenario_id}/compute  # 계산 실행 (async)
GET    /api/v3/cases/{case_id}/what-if/compare          # 전체 시나리오 비교
DELETE /api/v3/cases/{case_id}/what-if/{scenario_id}    # 시나리오 삭제
```

**구현 전략**:
- Axiom Phase 3 프로세스 최적화기(scipy.optimize)를 파라미터 오버라이드 수용하도록 확장
- 시나리오 비교 엔진은 전/후 비교 테이블 + 민감도 분석으로 구성
- 프론트엔드: 시나리오 선택기 + 슬라이더 UI + 토네이도 차트 (Recharts)
- **예상 공수**: ~15일 (BE 8일, FE 7일)
- **의존성**: Phase 3 프로세스 최적화 엔진 완성 후

---

#### 4.7.2 4계층 온톨로지 (Resource → Process → Measure → KPI)

**K-AIR 상태**: 완전 미구현 (0%) — WorkFlowy에 설계만 존재, 저장소 미생성
**Axiom 필요성**: 비즈니스 프로세스 데이터의 체계적 계층 구조화 → 의사결정 지원, 자연어 질의, 근본원인 분석의 기반

```
┌─ Neo4j 4계층 온톨로지 (Axiom Phase 3.3) ─────────────────────┐
│                                                                 │
│  RESOURCE 계층 (하위: 원시 데이터)                              │
│  ├─ (:Resource {type, name, unit, case_id, org_id})             │
│  │   types: Organization, Asset, Employee, CashReserve, System  │
│  ├─ (:Asset:Resource {name, type, market_value, book_value})    │
│  ├─ (:Financial:Resource {fiscal_year, revenue, ebitda, cash})  │
│  └─ (:Obligation:Resource {counterparty, amount, type, status}) │
│          │                                                      │
│          ▼ [:PARTICIPATES_IN]                                   │
│                                                                 │
│  PROCESS 계층 (비즈니스 프로세스 실행 절차)                     │
│  ├─ (:Process {type, name, stage, start_date, end_date})        │
│  │   types: DataIngestion, DataValidation, ProcessAnalysis,     │
│  │          StakeholderReview, OptimizationExecution, Reporting  │
│  ├─ (:Activity {name, stage, responsible_party, deadline})      │
│  └─ (:Decision {type, date, authority, approver, outcome})      │
│          │                                                      │
│          ▼ [:PRODUCES]                                          │
│                                                                 │
│  MEASURE 계층 (프로세스 실행에서 파생된 지표)                   │
│  ├─ (:Measure {type, formula, data_type, case_id})              │
│  │   types: TotalDataPoints, ValidatedRecords, AnomalyCount,   │
│  │          OperatingCost, EfficiencyScore, ProcessThroughput   │
│  └─ (:MeasureSnapshot {measure_id, period, value})              │
│          │                                                      │
│          ▼ [:CONTRIBUTES_TO]                                    │
│                                                                 │
│  KPI 계층 (전략적 성과 지표)                                    │
│  ├─ (:KPI {type, name, target, actual, reporting_period})       │
│  │   types: ProcessEfficiency, OperationalROI,                  │
│  │          CycleTime, ComplianceScore, PredictionAccuracy      │
│  ├─ (:KPITarget {kpi_id, green_threshold, yellow, red})        │
│  └─ (:KPIHistory {kpi_id, period, value, status})              │
│                                                                 │
│  핵심 관계:                                                     │
│  (Resource)-[:PARTICIPATES_IN]->(Process)                       │
│  (Resource)-[:CONTRIBUTES_TO]->(Measure)                        │
│  (Process)-[:PRODUCES]->(Measure)                               │
│  (Measure)-[:CONTRIBUTES_TO]->(KPI)                             │
│  (KPI)-[:DEPENDS_ON]->(Measure)                                 │
│  (Process)-[:INFLUENCES]->(KPI)                                 │
└─────────────────────────────────────────────────────────────────┘
```

**비즈니스 프로세스 온톨로지 매핑 예시**:

```
[Resource] 대상 기업 A (자산 50억, 매출 30억)
    ↓ [:PARTICIPATES_IN]
[Process] 데이터 수집 → 데이터 등록 → 데이터 검증 → 리소스 배분
    ↓ [:PRODUCES]
[Measure] 총 데이터 포인트 100건, 검증 완료 80건, 활용 가능 40건
    ↓ [:CONTRIBUTES_TO]
[KPI] 프로세스 효율 50%, 사건 처리 기간 18일, 준법성 점수 95%
```

**구현 전략**:
- Neo4j 스키마 마이그레이션: 기존 flat 스키마에 4계층 레이블 추가
- 자동 인제스트 파이프라인: 기존 케이스 데이터(data_points, assets, stakeholders) → 온톨로지 노드 자동 생성
- 온톨로지 브라우저 UI: 4계층 드릴다운 시각화 (React Force Graph)
- **예상 공수**: ~20일 (Neo4j 스키마 7일, 인제스트 파이프라인 6일, UI 7일)
- **의존성**: Phase 1 Neo4j 5 인프라, Phase 2 케이스 데이터 축적

---

#### 4.7.3 비정형 문서 → 온톨로지 추출

**K-AIR 상태**: 완전 미구현 (0%) — Memento 서비스가 문서 파싱만 수행
**Axiom 필요성**: 비즈니스 문서, 분석 보고서, 이해관계자 의견서 등 비정형 문서에서 온톨로지 자동 구축

```
┌─ 비정형 문서 처리 파이프라인 (Axiom Phase 3.4) ──────────────┐
│                                                                 │
│  1. 문서 수집 (Document Ingestion)                              │
│  ├─ PDF 서술문, 분석 보고서, 비즈니스 문서                      │
│  ├─ 이해관계자 의견서, 이메일 교환                              │
│  └─ 정관, 이사회 의사록                                        │
│          │                                                      │
│          ▼                                                      │
│  2. 텍스트 추출 및 청킹                                        │
│  ├─ GPT-4o Vision (이미지/스캔 문서)                            │
│  ├─ pdfplumber (표 추출)                                        │
│  └─ Recursive text splitter (800토큰 청크)                      │
│          │                                                      │
│          ▼                                                      │
│  3. 개체명 인식 (NER) — LLM 기반                               │
│  ├─ 추출 대상: 조직명, 인명, 부서, 금액, 일자, 자산유형, 절차  │
│  ├─ GPT-4o Structured Output (JSON 모드)                        │
│  └─ 개체별 신뢰도 점수 (0.0-1.0)                               │
│          │                                                      │
│          ▼                                                      │
│  4. 관계 추출 (Relation Extraction)                             │
│  ├─ 개체 쌍 연결: ("조직 A", "프로세스 시작일", "2024-01-15")   │
│  ├─ 사건 체인: 절차 A → 절차 B → KPI 결과                      │
│  └─ 의존성 그래프: "자산 매각 시 → 가용 현금 증가"             │
│          │                                                      │
│          ▼                                                      │
│  5. 온톨로지 매핑                                               │
│  ├─ 추출된 개체 → 4계층 노드 자동 분류:                        │
│  │  ├─ "XYZ 주식회사" → (:Resource {type: Company})             │
│  │  ├─ "프로세스 실행" → (:Process {type: ProcessExecution})     │
│  │  ├─ "검증 완료 80건" → (:Measure {type: ValidatedRecords})  │
│  │  └─ "효율 50%" → (:KPI {type: ProcessEfficiency})           │
│  ├─ Neo4j 관계 자동 생성                                       │
│  └─ 매핑 신뢰도 산출 (0.0-1.0)                                 │
│          │                                                      │
│          ▼                                                      │
│  6. HITL 검토 (신뢰도 < 0.75 필드)                             │
│  ├─ 저신뢰 추출 표시 → 담당자 확인 요청                        │
│  ├─ 수정: 개체 연결 보정, 누락 관계 추가                       │
│  └─ 확인된 결과 → Neo4j 최종 반영                              │
└─────────────────────────────────────────────────────────────────┘
```

**API 엔드포인트**:

```
POST   /api/v3/documents/{doc_id}/extract-ontology      # 비동기 추출 작업
GET    /api/v3/documents/{doc_id}/ontology-status        # 추출 진행 상태
PUT    /api/v3/documents/{doc_id}/ontology/{entity_id}/confirm  # HITL 승인
GET    /api/v3/cases/{case_id}/ontology                  # 케이스 전체 온톨로지
POST   /api/v3/cases/{case_id}/ontology/review           # 일괄 HITL 검토
```

**구현 전략**:
- Axiom 기존 worker-extract를 확장: OCR 후 구조화 추출 → 온톨로지 매핑 단계 추가
- LangChain Structured Output으로 관계 추출 (JSON 스키마 정의)
- HITL 기존 3단계 신뢰도 패턴(99%/80%/<80%) 그대로 활용
- **예상 공수**: ~18일 (NER/관계 추출 8일, 온톨로지 매핑 5일, HITL UI 5일)
- **의존성**: 4계층 온톨로지 (4.7.2) 완성 후

---

#### 4.7.4 See-Why 근본원인 분석 엔진

**K-AIR 상태**: 데모 수준 (20%) — "See-why 원인분석"이 WorkFlowy에 있으나 구현은 미미
**Axiom 필요성**: 비즈니스 문제 원인의 체계적 분석 → 분석 보고서 자동 작성, 프로세스 최적화 계획 근거 강화

```
┌─ See-Why 근본원인 분석 (Axiom Phase 4) ──────────────────────┐
│                                                                 │
│  1. 인과 그래프 구축 (Causal Graph Construction)                │
│  ├─ 비즈니스 문제 원인 모델: X → Y (X가 문제의 원인)            │
│  ├─ 직접 원인: 높은 비용 구조, 낮은 수익성, 자산 감가           │
│  ├─ 매개 요인: 시장 변동, 인력 이탈, 공급망 단절               │
│  ├─ 결과: 운영 비효율, 성과 하락, 자산 급매                    │
│  └─ 학습 데이터: 과거 종결 사건 100건+ (수동 라벨링 필요)      │
│          │                                                      │
│          ▼                                                      │
│  2. 인과 추론 알고리즘                                          │
│  ├─ PC Algorithm (제약 기반): 관측 데이터에서 인과 구조 탐색    │
│  ├─ LiNGAM: 선형 비가우시안 비순환 모델                        │
│  ├─ DoWhy 라이브러리: 인과 효과 추정 + 백도어 기준 검증        │
│  └─ 임계값: 인과 연결 보고 최소 신뢰도 0.70                    │
│          │                                                      │
│          ▼                                                      │
│  3. 케이스별 근본원인 추출                                      │
│  ├─ 현재 사건 데이터 로드: 매출, 비용, 부채, 자산, 이해관계자   │
│  ├─ 비즈니스 문제 발생으로부터 역추적:                          │
│  │  ├─ Q: "왜 이 조직이 운영 위기에 빠졌는가?"                  │
│  │  ├─ A: 높은 부채비율(A) + EBITDA 하락(B) + 경기침체(C)      │
│  │  ├─ 심층: A ← M&A 인수자금 차입                             │
│  │  └─ 심층: B ← 공급망 교란 + 임금 상승                       │
│  ├─ 인과 그래프에서 역방향 탐색 → 상위 3-5개 근본원인 도출     │
│  └─ 각 원인의 인과 계수 산출 (기여도 %)                        │
│          │                                                      │
│          ▼                                                      │
│  4. 반사실 시나리오 생성 (Counterfactual)                       │
│  ├─ "비용비율이 60%가 아닌 40%였다면 위기가 발생했을까?"        │
│  ├─ 인과 모델로 반사실 결과 추정                                │
│  ├─ 민감도: 어떤 원인 변경이 가장 큰 영향?                     │
│  └─ 정량화: "비용비율 20% 감소 시 위기 확률 35% 하락"          │
│          │                                                      │
│          ▼                                                      │
│  5. 설명 및 시각화                                              │
│  ├─ 타임라인: 인과 체인 시계열 (M&A → 비용 급증 → 운영 비효율) │
│  ├─ 인과 DAG: 엣지 강도 포함 시각적 다이어그램                  │
│  ├─ SHAP 값: 각 요인의 최종 결과 기여도                        │
│  └─ 보고서: 서술적 설명 + 차트 (분석 보고서 자동 작성 연동)    │
└─────────────────────────────────────────────────────────────────┘
```

**데이터베이스 (신규 테이블)**:

| 테이블 | 주요 컬럼 | 용도 |
|--------|----------|------|
| `causal_graphs` | case_type, version, nodes_json, edge_count, training_samples | 인과 그래프 모델 |
| `case_causal_analysis` | case_id, root_causes_json, timeline_json, confidence | 사건별 분석 결과 |
| `causal_explanations` | case_id, causal_chain, shap_values, counterfactual_json | 설명 및 반사실 |

**API 엔드포인트**:

```
POST   /api/v3/cases/{case_id}/root-cause-analysis      # 비동기 분석 (1-2분)
GET    /api/v3/cases/{case_id}/root-causes               # 근본원인 목록
GET    /api/v3/cases/{case_id}/causal-timeline           # 인과 타임라인
POST   /api/v3/cases/{case_id}/counterfactual            # 반사실 시뮬레이션
GET    /api/v3/cases/{case_id}/root-cause-impact         # 민감도 분석
```

**구현 전략**:
- Phase 4 (출시 후): ML 모델 학습 파이프라인 구축 → 과거 사건 100건+ 필요
- DoWhy 기반 인과 추론 서비스 독립 배포
- LLM으로 인과 설명 서술문 생성 → 분석 보고서 자동 작성(Phase 3)과 연동
- **예상 공수**: ~25일 (인과 추론 엔진 12일, 데이터 수집/라벨링 8일, UI 5일)
- **의존성**: 과거 종결 사건 100건+ 라벨링, 4계층 온톨로지 완성

---

#### 4.7.5 Watch Agent (실시간 이벤트 감시 및 알림)

**K-AIR 상태**: 부분 구현 (40%) — text2sql에 SimpleCEP 엔진 + /watch-agent 엔드포인트
**Axiom 필요성**: 기한 도래, 목표 미달, 이해관계자 리뷰 등 비즈니스 이벤트 실시간 모니터링

```
┌─ Watch Agent 시스템 (Axiom Phase 2.5 ~ 3.1) ────────────────┐
│                                                                 │
│  1. 이벤트 정의                                                 │
│  ├─ 비즈니스 마일스톤 이벤트:                                   │
│  │  ├─ deadline_approaching (분석 보고서 제출 7일 전)            │
│  │  ├─ milestone_due (성과 목표 기일 도래)                      │
│  │  ├─ data_registered (신규 데이터 등록 접수)                  │
│  │  ├─ meeting_scheduled (이해관계자 리뷰 예정)                 │
│  │  └─ plan_approval_progress (실행 계획 승인 진행 상태)        │
│  ├─ 데이터 이상 이벤트:                                        │
│  │  ├─ cash_balance_low (가용 현금 < 운영 필요액 10%)           │
│  │  ├─ data_anomaly_spike (이상 데이터 > 전체의 10%)           │
│  │  └─ error_ratio_high (오류 비율 > 50%)                      │
│  └─ 운영 위험 이벤트:                                          │
│     ├─ approval_deadline_missed (승인 기한 도과)                │
│     ├─ analysis_report_overdue (분석 보고서 지연)               │
│     └─ process_anomaly_indicator (프로세스 이상 징후 규칙 매칭) │
│                                                                 │
│  2. 이벤트 구독 모델                                            │
│  ├─ 사용자 선택: 어떤 이벤트를 모니터링할지                     │
│  ├─ 임계값 설정: "기한 4일 전 알림"                             │
│  ├─ 채널 선택: 인앱 알림, 이메일, SMS, Slack                   │
│  └─ 빈도: 즉시, 일일 요약, 이벤트별                            │
│                                                                 │
│  3. 스트림 처리 엔진                                            │
│  ├─ event_outbox 5초 간격 폴링 (기존 Axiom Outbox 활용)        │
│  ├─ CEP 룰 평가:                                               │
│  │  ├─ IF deadline = TODAY+7 THEN alert deadline_approaching    │
│  │  ├─ IF new_data > total*0.10 THEN alert data_spike          │
│  │  └─ IF (errors/total) > 0.50 FOR 2주 연속 THEN escalate    │
│  ├─ 상태 추적: 이벤트 시퀀스 ("1시간 내 승인 3건")             │
│  └─ 시간적 추적: 기간 모니터링 ("작업 미결 30일 초과")         │
│                                                                 │
│  4. 알림 생성 및 발송                                           │
│  ├─ 심각도: LOW(정보), MEDIUM(경고), HIGH(긴급), CRITICAL(필수)│
│  ├─ 멀티채널 발송: 인앱 + 이메일 + SMS + Slack + Webhook       │
│  ├─ 중복 제거: 동일 이벤트 24시간 내 재알림 방지               │
│  └─ 감사 로그: 모든 알림 + 발송 상태 기록                      │
│                                                                 │
│  5. 알림 대시보드                                               │
│  ├─ 알림 목록: 심각도 + 시간순 정렬                             │
│  ├─ 액션: 확인, 보류, 해제, 조치("리뷰 일정 잡기")             │
│  └─ 에스컬레이션: CRITICAL 알림 1시간 미확인 시 상위자 전달    │
└─────────────────────────────────────────────────────────────────┘
```

**데이터베이스 (신규 테이블)**:

| 테이블 | 주요 컬럼 | 용도 |
|--------|----------|------|
| `watch_subscriptions` | case_id, user_id, event_type, threshold, channel | 구독 설정 |
| `watch_alerts` | case_id, event_type, severity, message, triggered_at | 발생 알림 |
| `watch_alert_deliveries` | alert_id, channel, sent_at, status | 발송 이력 |
| `watch_alert_feedback` | alert_id, was_helpful, led_to_action | 알림 피드백 |

**구현 전략**:
- Axiom 기존 Event Outbox + Redis Streams 인프라 위에 구축 (최소 변경)
- K-AIR SimpleCEP 패턴을 Python Faust 또는 자체 CEP 엔진으로 재구현
- 멀티채널 알림 디스패처: 이메일(SES), SMS(SNS), Slack(Webhook) 어댑터
- **예상 공수**: ~14일 (BE 8일, FE 6일)
- **의존성**: Phase 1 Event Outbox 인프라 (가장 빠르게 착수 가능)

---

#### 4.7.6 OLAP 분석 (피벗 테이블 + 자연어 질의)

**K-AIR 상태**: 부분 구현 (80%) — data-platform-olap에 Mondrian XML + LangGraph Text2SQL
**Axiom 필요성**: 비즈니스 프로세스 통계 분석 (유형별/조직별/기간별 성과 지표, 처리 기간, 데이터 분석)

```
┌─ OLAP 분석 엔진 (Axiom Phase 3.6) ──────────────────────────┐
│                                                                 │
│  1. 큐브 정의 (비즈니스 프로세스 도메인)                        │
│  ├─ 비즈니스 프로세스 큐브:                                     │
│  │  ├─ 차원(Dimension):                                        │
│  │  │  ├─ 사건: case_type, status, start_date                  │
│  │  │  ├─ 대상 조직: org_name, industry, region                │
│  │  │  ├─ 시간: start_year, quarter, month                     │
│  │  │  └─ 이해관계자: stakeholder_type, role, impact_band      │
│  │  └─ 측도(Measure):                                          │
│  │     ├─ 사건 수 (COUNT DISTINCT case_id)                     │
│  │     ├─ 총 데이터 포인트 (SUM data_points)                   │
│  │     ├─ 검증 비율 (SUM validated / SUM total)                │
│  │     ├─ 평균 성과 지표 (AVG performance_rate by class)       │
│  │     ├─ 사건 처리 기간 (AVG days start→completion)           │
│  │     └─ 이해관계자 만족도 (AVG actual / target)              │
│  └─ 현금흐름 큐브:                                             │
│     ├─ 차원: 사건, 대상 조직, 시간(회계연도)                   │
│     └─ 측도: 금액(SUM), 성장률(YoY %), 예측 정확도             │
│                                                                 │
│  2. 피벗 테이블 엔진                                            │
│  ├─ 행: 사건 유형, 대상 조직 업종, 시작 연도                    │
│  ├─ 열: 이해관계자 유형, 실행 연차                              │
│  ├─ 값: 성과 산출액, 효율 지표, 사건 수                        │
│  ├─ 필터: 사건 상태, 대상 조직 지역, 데이터 규모 범위          │
│  ├─ 드릴다운: 사건 유형 → 개별 사건 → 이해관계자 상세          │
│  └─ 드릴스루: 피벗 셀 클릭 → 원본 데이터 레코드                │
│                                                                 │
│  3. 집계 및 캐싱                                                │
│  ├─ PostgreSQL Materialized View (자주 조회되는 큐브)           │
│  ├─ Redis 캐시 (1시간 TTL)                                     │
│  └─ 이벤트 기반 갱신 (새 사건 데이터 입력 시)                  │
│                                                                 │
│  4. LLM 보조 질의 (K-AIR Text2SQL 패턴 활용)                   │
│  ├─ "2024년 제조업 프로세스 분석의 이해관계자별 성과 지표를 보여줘"│
│  ├─ LLM → SQL + PIVOT 구문 생성                                │
│  ├─ SQLGlot 검증 (구조 + 안전성)                               │
│  └─ 실행 → 결과 그리드 반환                                    │
│                                                                 │
│  5. 프론트엔드 UI                                               │
│  ├─ 드래그앤드롭 차원/측도 빌더                                 │
│  ├─ 인터랙티브 피벗 테이블 (확장/축소, 정렬)                   │
│  ├─ 시각화: 막대 차트, 히트맵, 파이 차트                       │
│  └─ 내보내기: CSV, Excel, PDF                                  │
└─────────────────────────────────────────────────────────────────┘
```

**구현 전략**:
- K-AIR data-platform-olap의 Mondrian XML 파서 + SQL 생성기를 Axiom에 이식
- PostgreSQL Materialized View로 팩트/디멘전 테이블 구성 (별도 DW 불필요)
- K-AIR Text2SQL의 ReAct 패턴 + SQLGlot 검증을 OLAP 질의에 적용
- React 피벗 UI: react-pivottable 또는 AG Grid Enterprise
- **예상 공수**: ~22일 (DW 설계 4일, BE 10일, FE 8일)
- **의존성**: Phase 2 현금흐름 테이블, Phase 3 Text2SQL 기반

### 4.8 미구현 기능 구축 로드맵

```
Phase 2.5 ──────────────────────────────────────────────────────
  │  Watch Agent (14일) ← 기존 Outbox 활용, 가장 빠른 착수 가능
  │  ├─ BE: CEP 엔진 + 알림 발송 (8일)
  │  └─ FE: 알림 대시보드 + 구독 관리 (6일)
  ▼
Phase 3.2 ──────────────────────────────────────────────────────
  │  What-If 시뮬레이션 (15일) ← 프로세스 최적화기 확장
  │  ├─ BE: 시나리오 솔버 + 비교 엔진 (8일)
  │  └─ FE: 시나리오 빌더 + 토네이도 차트 (7일)
  ▼
Phase 3.3 ──────────────────────────────────────────────────────
  │  4계층 온톨로지 (20일) ← 이후 기능의 기반
  │  ├─ Neo4j 스키마 마이그레이션 (7일)
  │  ├─ 자동 인제스트 파이프라인 (6일)
  │  └─ 온톨로지 브라우저 UI (7일)
  ▼
Phase 3.4 ──────────────────────────────────────────────────────
  │  비정형→온톨로지 추출 (18일) ← 4계층 온톨로지 의존
  │  ├─ NER + 관계 추출 (8일)
  │  ├─ 온톨로지 매핑 규칙 (5일)
  │  └─ HITL 검토 UI (5일)
  ▼
Phase 3.6 (병렬 가능) ──────────────────────────────────────────
  │  OLAP 분석 (22일) ← Phase 3 Text2SQL과 병렬 진행 가능
  │  ├─ DW 설계 + 큐브 정의 (4일)
  │  ├─ 피벗 엔진 + API (10일)
  │  └─ 피벗 UI (8일)
  ▼
Phase 4 (출시 후) ──────────────────────────────────────────────
  │  See-Why 근본원인 분석 (25일) ← 과거 데이터 100건+ 필요
  │  ├─ 데이터 수집 + 라벨링 (8일)
  │  ├─ 인과 추론 엔진 (12일)
  │  └─ 설명 UI + 보고서 연동 (5일)

총 추가 공수: ~114일 (약 5.5개월, 2인 기준 ~3개월)
```

### 4.9 미구현 기능 우선순위 매트릭스

| # | 기능 | 우선순위 | 공수 | Phase | 비즈니스 가치 | 기술 위험 | 의존성 |
|---|------|:--------:|:----:|:-----:|:-----------:|:---------:|--------|
| 1 | **Watch Agent** | **P0** | 14일 | 2.5 | ★★★★★ | 낮음 | Outbox (Phase 1) |
| 2 | **What-If 시뮬레이션** | **P0** | 15일 | 3.2 | ★★★★★ | 중간 | 프로세스 최적화기 (Phase 3) |
| 3 | **OLAP 분석** | **P1** | 22일 | 3.6 | ★★★★☆ | 낮음 | 현금흐름 (Phase 2) |
| 4 | **4계층 온톨로지** | **P1** | 20일 | 3.3 | ★★★☆☆ | 중간 | Neo4j (Phase 1) |
| 5 | **비정형→온톨로지** | **P2** | 18일 | 3.4 | ★★★☆☆ | 높음 | 온톨로지 (4.7.2) |
| 6 | **See-Why 근본원인** | **P2** | 25일 | 4 | ★★★★☆ | 높음 | 과거 데이터 100건+ |

> **P0 즉시 착수 근거**: Watch Agent는 기한 관리라는 운영 필수 지원, What-If는 프로세스 최적화 계획 수립의 핵심 요구사항
> **P2 후순위 근거**: 비정형→온톨로지 및 See-Why는 ML 모델 학습 데이터 확보가 전제조건

### 4.10 Axiom Series — 모듈 네이밍 및 통합 아키텍처

> K-AIR/Process-GPT의 18개 흩어진 저장소를 **6개 Axiom 모듈**로 재편한다.
> 각 모듈명은 프로젝트의 "자명한 원리(Axiom)"라는 정체성을 반영하며, 비즈니스 프로세스 인텔리전스 도메인에 최적화된 단일 모놀리식 모듈로 통합한다.

#### 4.10.1 Axiom Series 모듈 정의

| # | 모듈명 | 컨셉 | 역할 | Axiom 기술 스택 |
|---|--------|------|------|----------------|
| 1 | **Axiom Core** | 시스템의 중심, 모든 신뢰의 기점 | 인증, API Gateway, 서비스 오케스트레이션, BPM 엔진 | FastAPI + JWT + LangGraph + Redis Streams |
| 2 | **Axiom Vision** | 데이터를 분석해 미래를 내다보는 통찰력 | What-if 시뮬레이션, OLAP 피벗, 통계 대시보드, 근본원인 분석 | scipy + Mondrian + DoWhy + Recharts |
| 3 | **Axiom Oracle** | 질문에 데이터의 언어로 답하는 영매 | 자연어→SQL 변환, ReAct 추론, SQL Guard, 이벤트 CEP | LangChain + Neo4j + SQLGlot + GPT-4o |
| 4 | **Axiom Synapse** | 데이터 간 연결고리를 잇는 지능 신경망 | 4계층 온톨로지, 지식그래프, 비정형→온톨로지 추출, 관계 탐색 | Neo4j 5 + pgvector + GPT-4o Structured Output |
| 5 | **Axiom Weaver** | 흩어진 데이터를 하나의 직물로 짜내는 존재 | 데이터 패브릭, 메타데이터 추출, 다중 DB 추상화, ETL | MindsDB + PostgreSQL 어댑터 + Airflow |
| 6 | **Axiom Canvas** | 문서를 그리고 다듬는 창의적 작업 공간 | 웹 프론트엔드, 문서 편집, HITL 리뷰, 대시보드, 알림 | React 18 + TypeScript + Shadcn/ui + Zustand |

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Axiom Series Architecture                         │
│                                                                      │
│  ┌─ Axiom Canvas ──────────────────────────────────────────────┐    │
│  │  React 18 + Shadcn/ui + Zustand + TanStack Query           │    │
│  │  ├─ 케이스 대시보드 / 문서 관리 / HITL 리뷰               │    │
│  │  ├─ What-if 시나리오 빌더 (← Vision API)                   │    │
│  │  ├─ OLAP 피벗 테이블 (← Vision API)                        │    │
│  │  ├─ 온톨로지 브라우저 (← Synapse API)                      │    │
│  │  ├─ NL2SQL 대화형 쿼리 (← Oracle API)                      │    │
│  │  ├─ Watch 알림 대시보드 (← Core WebSocket)                 │    │
│  │  └─ 데이터소스 관리 (← Weaver API)                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│          │                                                           │
│          ▼ HTTP/WebSocket                                            │
│  ┌─ Axiom Core ────────────────────────────────────────────────┐    │
│  │  FastAPI + JWT Auth + RBAC + Redis Streams                  │    │
│  │  ├─ API Gateway (인증, 라우팅, 멀티테넌트 ContextVar)      │    │
│  │  ├─ BPM 엔진 (프로세스 정의/실행, Saga 보상)              │    │
│  │  ├─ LangGraph 오케스트레이터 (9노드, HITL interrupt)       │    │
│  │  ├─ Event Outbox → Redis Streams (at-least-once)           │    │
│  │  ├─ Watch Agent CEP 엔진 (알림 생성/발송)                  │    │
│  │  ├─ Worker 관리 (OCR, 추출, 생성, 동기화)                  │    │
│  │  └─ A2A 에이전트 오케스트레이션                             │    │
│  └──────┬──────────┬──────────┬──────────┬─────────────────────┘    │
│         │          │          │          │                           │
│         ▼          ▼          ▼          ▼                           │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐                  │
│  │  Axiom   ││  Axiom   ││  Axiom   ││  Axiom   │                  │
│  │  Vision  ││  Oracle  ││  Synapse ││  Weaver  │                  │
│  │ ──────── ││ ──────── ││ ──────── ││ ──────── │                  │
│  │ What-if  ││ NL→SQL   ││ 온톨로지 ││데이터    │                  │
│  │ OLAP     ││ ReAct    ││ 지식그래프││패브릭    │                  │
│  │ 근본원인 ││ SQL Guard││ NER 추출 ││메타데이터│                  │
│  │ 통계     ││ CEP/이벤트││프로세스  ││ETL      │                  │
│  │          ││          ││ 마이닝   ││          │                  │
│  │          ││          ││관계 탐색 ││          │                  │
│  └──────────┘└──────────┘└──────────┘└──────────┘                  │
│         │          │          │          │                           │
│         ▼          ▼          ▼          ▼                           │
│  ┌─ 데이터 계층 ───────────────────────────────────────────────┐    │
│  │  PostgreSQL 15 (RLS) │ Neo4j 5 (그래프+벡터) │ Redis 7     │    │
│  │  MinIO (S3)          │ MindsDB (다중 DB)     │ Airflow     │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.10.2 K-AIR 18개 저장소 → Axiom 6개 모듈 매핑

| K-AIR 저장소 | 흡수 대상 | 마이그레이션 작업 | 난이도 |
|-------------|----------|-----------------|:------:|
| **→ Axiom Core** | | | |
| process-gpt-gs-main/gateway | Core: API Gateway | Spring Boot → FastAPI 재작성 (JWT 필터 로직 이식) | ★★★ |
| process-gpt-completion-main | Core: BPM 엔진 | Python 코드 구조 리팩토링 (Axiom 패턴 적용) | ★★☆ |
| process-gpt-main | Core: 인프라/스키마 | K8s 매니페스트 참조 → Docker Compose → EKS 마이그레이션 | ★☆☆ |
| process-gpt-a2a-orch-main | Core: 에이전트 오케스트레이션 | A2A SDK → LangGraph 멀티에이전트 재구현 | ★★★ |
| process-gpt-agent-feedback-main | Core: 지식 학습 루프 | ReAct 패턴 유지, Mem0 → pgvector 전환 검토 | ★★☆ |
| process-gpt-agent-utils-main | Core: 공유 도구 라이브러리 | packages/ 디렉토리로 이동 | ★☆☆ |
| process-gpt-crewai-action-main | Core: 에이전트 액션 | CrewAI → LangGraph Tool 전환 | ★★★ |
| process-gpt-crewai-deep-research-main | Core: 보고서 생성 | CrewAI Flow → LangGraph 워크플로우 전환 | ★★★ |
| process-gpt-langchain-react-main | Core: ReAct + MCP | LangChain ReAct 패턴 직접 활용 (변경 최소) | ★☆☆ |
| process-gpt-react-voice-agent-main | Core: 음성 에이전트 | Axiom MVP 범위 외 (Phase 4+) | - |
| process-gpt-memento-main | Core: 문서 처리 워커 | 문서 파싱 로직 → worker-extract에 통합 | ★★☆ |
| process-gpt-bpmn-extractor-main | Core: BPMN 추출 워커 | PDF→BPMN 추출 로직 참조 (비즈니스 프로세스 매뉴얼 적용) | ★★☆ |
| **→ Axiom Vision** | | | |
| data-platform-olap-main | Vision: OLAP 엔진 | Mondrian XML 파서 + SQL 생성기 이식, Vue3→React | ★★☆ |
| (신규) What-if 엔진 | Vision: 시나리오 솔버 | 신규 개발 (scipy.optimize 기반) | ★★★ |
| (신규) See-Why 엔진 | Vision: 근본원인 분석 | 신규 개발 (DoWhy + 인과 추론) | ★★★ |
| **→ Axiom Oracle** | | | |
| robo-data-text2sql-main | Oracle: NL2SQL 전체 | 핵심 이식 대상 — ReAct + RAG + SQL Guard 직접 활용 | ★★☆ |
| **→ Axiom Synapse** | | | |
| robo-data-text2sql-main (Neo4j 부분) | Synapse: 그래프 스키마 | Neo4j 부트스트랩 + 그래프 검색 코드 분리 | ★★☆ |
| (신규) 4계층 온톨로지 | Synapse: R→P→M→KPI | 신규 개발 (Neo4j 스키마 확장) | ★★★ |
| (신규) 비정형→온톨로지 | Synapse: NER 추출 | 신규 개발 (GPT-4o 기반) | ★★★ |
| **→ Axiom Weaver** | | | |
| robo-data-fabric-main (백엔드) | Weaver: 데이터 패브릭 | FastAPI 코드 직접 활용 (MindsDB 연동) | ★☆☆ |
| **→ Axiom Canvas** | | | |
| robo-data-fabric-main/frontend | Canvas: 데이터소스 UI | Vue 3 → React 18 재작성 | ★★★ |
| process-gpt-vue3-main | Canvas: SpikeAdmin UI | Vue 3 → React 18 재작성 (컴포넌트 패턴 참조) | ★★★ |
| data-platform-olap-main/frontend | Canvas: OLAP UI | Vue 3 → React 18 재작성 | ★★★ |
| eventstorming-tool-vite-main | Canvas: Business Process Designer + Synapse: 프로세스 마이닝 | EventStorming 개념 모델을 비즈니스 프로세스 레벨로 확장 — 핵심 이식 대상 | ★★★ |
| antlr-code-parser-main | (제외) | Axiom 도메인과 무관 — 코드 역공학 도구 | - |

### 4.11 소스코드 통합 전략 (18개 → 6개 Axiom 모듈)

#### 4.11.1 통합 원칙

```
┌─ 소스코드 통합 5원칙 ──────────────────────────────────────────────┐
│                                                                      │
│  원칙 1: "로직 이식, 프레임워크 교체"                                │
│  → K-AIR의 비즈니스 로직(알고리즘, 파이프라인)은 보존하되,          │
│    프레임워크(Spring Boot, Vue 3, CrewAI)는 Axiom 스택으로 교체     │
│                                                                      │
│  원칙 2: "모노레포 단일 진입점"                                      │
│  → 18개 저장소를 Axiom 모노레포 내 6개 패키지로 통합               │
│    apps/canvas/ + services/{core,vision,oracle,synapse,weaver}/     │
│                                                                      │
│  원칙 3: "인터페이스 우선 통합"                                      │
│  → 모듈 간 통신은 REST API + Redis Streams (이벤트)로 표준화       │
│    내부 import 의존 금지 → 모듈 경계 명확화                         │
│                                                                      │
│  원칙 4: "점진적 이식 (Strangler Fig)"                               │
│  → 한 번에 전체 교체가 아닌, 기능 단위로 K-AIR → Axiom 이식        │
│    각 기능 이식 후 테스트 통과 확인 → 다음 기능 진행                │
│                                                                      │
│  원칙 5: "MVP 범위 외 코드는 참조만"                                 │
│  → 음성 에이전트, 이벤트스토밍, ANTLR 등은 이식하지 않고           │
│    패턴/알고리즘만 문서화하여 Phase 4+ 참조 자료로 보관             │
└──────────────────────────────────────────────────────────────────────┘
```

#### 4.11.2 Axiom 모노레포 디렉토리 구조

```
axiom/
├── apps/
│   └── canvas/                          # Axiom Canvas (React 18)
│       ├── src/
│       │   ├── features/
│       │   │   ├── cases/               # 케이스 관리 (기존 Axiom)
│       │   │   ├── documents/           # 문서 관리 (기존 Axiom)
│       │   │   ├── hitl-review/         # HITL 리뷰 (기존 Axiom)
│       │   │   ├── what-if/             # What-if 시뮬레이터 (← Vision)
│       │   │   ├── olap/               # OLAP 피벗 (← Vision)
│       │   │   ├── ontology/           # 온톨로지 브라우저 (← Synapse)
│       │   │   ├── nl2sql/             # NL2SQL 대화형 쿼리 (← Oracle)
│       │   │   ├── datasources/        # 데이터소스 관리 (← Weaver)
│       │   │   ├── watch-alerts/       # 알림 대시보드 (← Core)
│       │   │   └── chat/               # AI 채팅 (기존 Axiom)
│       │   └── shared/                 # 공통 컴포넌트/훅
│       └── package.json
│
├── services/
│   ├── core/                            # Axiom Core (FastAPI)
│   │   ├── app/
│   │   │   ├── api/                    # API 엔드포인트
│   │   │   │   ├── auth/              # JWT 인증 (← gs-main/gateway)
│   │   │   │   ├── cases/             # 케이스 CRUD (기존 Axiom)
│   │   │   │   ├── documents/         # 문서 관리 (기존 Axiom)
│   │   │   │   ├── process/           # BPM 실행 (← completion-main)
│   │   │   │   ├── agents/            # 에이전트 관리 (← a2a-orch)
│   │   │   │   └── watches/           # Watch 구독/알림 (신규)
│   │   │   ├── workers/
│   │   │   │   ├── ocr.py             # OCR 워커 (기존 Axiom)
│   │   │   │   ├── extract.py         # 추출 워커 (기존 Axiom)
│   │   │   │   ├── generate.py        # 문서 생성 (기존 Axiom)
│   │   │   │   ├── sync.py            # Outbox 동기화 (기존 Axiom)
│   │   │   │   └── watch_cep.py       # CEP 이벤트 처리 (← text2sql)
│   │   │   ├── orchestrator/
│   │   │   │   ├── langgraph_flow.py  # 9노드 오케스트레이터 (기존)
│   │   │   │   └── agent_loop.py      # 에이전트 루프 (← agent-feedback)
│   │   │   ├── bpm/
│   │   │   │   ├── engine.py          # BPM 엔진 (← completion-main)
│   │   │   │   ├── saga.py            # Saga 보상 (← completion-main)
│   │   │   │   └── extractor.py       # PDF→BPMN (← bpmn-extractor)
│   │   │   └── core/
│   │   │       ├── config.py          # 설정 (기존 Axiom)
│   │   │       ├── middleware.py      # 멀티테넌트 ContextVar (← completion)
│   │   │       └── security.py        # JWT + RBAC (← gs-main/gateway)
│   │   └── pyproject.toml
│   │
│   ├── vision/                          # Axiom Vision (FastAPI)
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── what_if.py         # What-if 시나리오 API (신규)
│   │   │   │   ├── olap.py            # OLAP 피벗 API (← olap-main)
│   │   │   │   ├── analytics.py       # 통계 대시보드 API (신규)
│   │   │   │   └── root_cause.py      # 근본원인 분석 API (신규 Phase 4)
│   │   │   ├── engines/
│   │   │   │   ├── scenario_solver.py # 시나리오 솔버 (← scipy)
│   │   │   │   ├── mondrian_parser.py # Mondrian XML 파서 (← olap-main)
│   │   │   │   ├── pivot_engine.py    # 피벗 쿼리 엔진 (← olap-main)
│   │   │   │   └── causal_engine.py   # DoWhy 인과 추론 (신규 Phase 4)
│   │   │   └── core/
│   │   │       └── config.py
│   │   └── pyproject.toml
│   │
│   ├── oracle/                          # Axiom Oracle (FastAPI)
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── text2sql.py        # NL2SQL 엔드포인트 (← text2sql)
│   │   │   │   ├── events.py          # 이벤트 룰/CEP (← text2sql)
│   │   │   │   └── feedback.py        # SQL 피드백 (← text2sql)
│   │   │   ├── pipelines/
│   │   │   │   ├── react_controller.py# ReAct 추론기 (← text2sql)
│   │   │   │   ├── rag_pipeline.py    # 5축 벡터 검색 (← text2sql)
│   │   │   │   └── sql_guard.py       # SQL 검증기 (← text2sql)
│   │   │   └── core/
│   │   │       ├── llm_factory.py     # LLM 클라이언트 팩토리 (← text2sql)
│   │   │       └── neo4j_client.py    # Neo4j 연결 (← text2sql)
│   │   └── pyproject.toml
│   │
│   ├── synapse/                         # Axiom Synapse (FastAPI)
│   │   ├── app/
│   │   │   ├── api/
│   │   │   │   ├── ontology.py        # 온톨로지 CRUD (신규)
│   │   │   │   ├── schema_edit.py     # 스키마 편집 (← text2sql)
│   │   │   │   └── extraction.py      # 비정형→온톨로지 (신규)
│   │   │   ├── graph/
│   │   │   │   ├── neo4j_bootstrap.py # 그래프 초기화 (← text2sql)
│   │   │   │   ├── graph_search.py    # 그래프 탐색 (← text2sql)
│   │   │   │   ├── ontology_schema.py # 4계층 스키마 (신규)
│   │   │   │   └── ontology_ingest.py # 자동 인제스트 (신규)
│   │   │   ├── extraction/
│   │   │   │   ├── ner_extractor.py   # 개체명 인식 (신규)
│   │   │   │   ├── relation_extractor.py # 관계 추출 (신규)
│   │   │   │   └── ontology_mapper.py # 온톨로지 매핑 (신규)
│   │   │   └── core/
│   │   │       └── neo4j_client.py
│   │   └── pyproject.toml
│   │
│   └── weaver/                          # Axiom Weaver (FastAPI)
│       ├── app/
│       │   ├── api/
│       │   │   ├── datasources.py     # 데이터소스 CRUD (← fabric)
│       │   │   ├── query.py           # SQL 쿼리 실행 (← fabric)
│       │   │   └── metadata.py        # 메타데이터 추출 (← fabric)
│       │   ├── adapters/
│       │   │   ├── postgresql.py      # PG 어댑터 (← fabric)
│       │   │   ├── mysql.py           # MySQL 어댑터 (← fabric)
│       │   │   └── oracle.py          # Oracle 어댑터 (← fabric)
│       │   ├── mindsdb/
│       │   │   └── client.py          # MindsDB HTTP 클라이언트 (← fabric)
│       │   └── core/
│       │       └── config.py
│       └── pyproject.toml
│
├── packages/                            # 공유 라이브러리
│   ├── shared-types/                   # Pydantic 모델 (모듈 간 공유)
│   ├── agent-tools/                    # 에이전트 도구 (← agent-utils)
│   └── db-models/                      # SQLAlchemy 모델 + Alembic
│
├── db/
│   ├── migrations/                     # Alembic 마이그레이션
│   └── seeds/                          # 초기 데이터
│
└── infra/
    ├── docker/
    │   └── docker-compose.yml          # 개발 환경 (6서비스 + DB)
    └── k8s/                            # EKS 배포 (Phase 3)
```

#### 4.11.3 기술 스택 전환 매트릭스

| 영역 | K-AIR/Process-GPT (원본) | Axiom (전환 후) | 전환 전략 |
|------|-------------------------|----------------|----------|
| **API Gateway** | Spring Boot + JJWT | FastAPI + python-jose | JWT 필터 로직 이식, 라우팅 규칙 YAML화 |
| **Frontend** | Vue 3 + Vuetify + Pinia | React 18 + Shadcn/ui + Zustand | 컴포넌트 패턴 참조, UI는 완전 재작성 |
| **DB 접근** | Supabase Client SDK | SQLAlchemy + asyncpg (직접) | RLS 정책 동일, 마이그레이션은 Alembic |
| **에이전트** | CrewAI + A2A SDK | LangGraph + LangChain | CrewAI Flow → LangGraph 노드 전환 |
| **실시간 협업** | Yjs CRDT + WebSocket | (Phase 4+) | 이벤트스토밍 도구는 참조만 |
| **문서 처리** | Memento (PDF/DOCX/HWP) | worker-extract (Textract + GPT-4o) | 파싱 로직 참조, OCR은 Textract 우선 |
| **인증** | Keycloak + Supabase Auth | JWT 자체 구현 + RBAC | Keycloak 토큰 구조 참조 |
| **벡터 검색** | pgvector + Neo4j Vector | pgvector + Neo4j Vector (동일) | 5축 벡터 검색 패턴 직접 이식 |
| **메시지 큐** | (없음 — 직접 HTTP 호출) | Redis Streams (at-least-once) | Axiom Event Outbox 패턴 적용 |
| **OLAP** | Mondrian XML + LangGraph | Mondrian XML + MaterializedView | XML 파서 이식, MV로 성능 보장 |

#### 4.11.4 단계별 통합 실행 계획

```
Phase 1 (MVP 기간, ~12주) ─────────────────────────────────────────
│
│  [Axiom Core] 기반 구축 (기존 Axiom 구현 + K-AIR 이식)
│  ├─ 1a. completion-main → Core: BPM 엔진 로직 이식 (3일)
│  │      · process_service.py → core/bpm/engine.py
│  │      · saga_manager.py → core/bpm/saga.py
│  │      · DBConfigMiddleware → core/middleware.py (ContextVar)
│  │
│  ├─ 1b. gs-main/gateway → Core: JWT 인증 이식 (2일)
│  │      · ForwardHostHeaderFilter.java → core/security.py (Python 재작성)
│  │      · WebSecurityConfig → FastAPI Depends() 패턴
│  │
│  ├─ 1c. langchain-react → Core: MCP 도구 통합 (2일)
│  │      · SafeToolLoader → core/tools/loader.py (우선순위 패턴 보존)
│  │      · MCP 서버 연동 로직 → core/tools/mcp_client.py
│  │
│  └─ 1d. memento-main → Core: 문서 파싱 참조 (1일)
│         · PDF/DOCX 파싱 로직 → worker-extract에서 참조
│         · (Axiom는 Textract + GPT-4o Vision 우선)
│
│  [Axiom Canvas] 기반 구축 (기존 Axiom React 프론트엔드)
│  └─ 1e. Vue3 컴포넌트 패턴 → React 컴포넌트 참조 (지속적)
│         · BPMN 뷰어 패턴 → React Flow
│         · 채팅 UI 패턴 → React 채팅 컴포넌트
│
▼
Phase 2 (분석 기능, ~12주) ─────────────────────────────────────────
│
│  [Axiom Oracle] 핵심 이식 (최고 우선순위 이식 대상)
│  ├─ 2a. text2sql-main → Oracle 서비스 전체 (5일)
│  │      · app/core/ → oracle/app/core/ (설정, Neo4j 클라이언트)
│  │      · app/pipelines/ → oracle/app/pipelines/ (RAG, ReAct, Guard)
│  │      · app/routers/text2sql.py → oracle/app/api/text2sql.py
│  │      · app/routers/events.py → oracle/app/api/events.py
│  │      · 변경 사항: Supabase → PostgreSQL 직접 연결
│  │
│  ├─ 2b. text2sql Neo4j 부분 분리 → Synapse (3일)
│  │      · app/core/neo4j_bootstrap.py → synapse/app/graph/
│  │      · app/core/graph_search.py → synapse/app/graph/
│  │      · Oracle은 Synapse API를 호출하는 구조로 전환
│  │
│  └─ 2c. Watch Agent 구축 (14일 — 4.7.5 참조)
│         · text2sql/events.py의 SimpleCEP → core/workers/watch_cep.py
│         · 알림 발송 디스패처 신규 구축
│
│  [Axiom Canvas + Synapse] EventStorming 비즈니스 확장
│  └─ 2d. EventStorming 비즈니스 확장 → Canvas + Synapse (20일)
│         · eventstorming-tool-vite-main 핵심 이식
│         · Yjs CRDT + Konva 캔버스 → Canvas: Business Process Designer
│         · EventStorming 7개 개념 → 비즈니스 프로세스 모델 매핑
│         · 이벤트 로그 바인딩 + pm4py → Synapse: 프로세스 마이닝 엔진
│
│  [Axiom Weaver] 이식 (데이터 패브릭)
│  └─ 2e. fabric-main → Weaver 서비스 (3일)
│         · app/routers/ → weaver/app/api/
│         · app/services/ → weaver/app/adapters/
│         · app/mindsdb/ → weaver/app/mindsdb/
│         · frontend/ → 제외 (Canvas에서 재작성)
│
▼
Phase 3 (계획 생성, ~12주) ─────────────────────────────────────────
│
│  [Axiom Vision] 구축 (분석 엔진)
│  ├─ 3a. olap-main → Vision: OLAP 엔진 이식 (5일)
│  │      · xml_parser.py → vision/app/engines/mondrian_parser.py
│  │      · sql_generator.py → vision/app/engines/pivot_engine.py
│  │      · frontend/ → 제외 (Canvas에서 재작성)
│  │
│  ├─ 3b. What-if 시뮬레이션 엔진 신규 구축 (15일 — 4.7.1 참조)
│  │
│  └─ 3c. OLAP 피벗 + Canvas UI 구축 (22일 — 4.7.6 참조)
│
│  [Axiom Synapse] 구축 (온톨로지)
│  ├─ 3d. 4계층 온톨로지 신규 구축 (20일 — 4.7.2 참조)
│  │
│  └─ 3e. 비정형→온톨로지 추출 (18일 — 4.7.3 참조)
│
│  [Axiom Canvas] K-AIR 기원 UI 구축
│  └─ 3f. Vue3 → React 재작성 (지속적)
│         · fabric/frontend → canvas/features/datasources/
│         · olap/frontend → canvas/features/olap/
│         · vue3-main 패턴 → canvas/features/ 전반
│
▼
Phase 4 (출시 후) ──────────────────────────────────────────────────
│
│  [Axiom Vision] 고급 분석
│  └─ 4a. See-Why 근본원인 분석 (25일 — 4.7.4 참조)
│
│  [참조만 — 이식하지 않음]
│  ├─ react-voice-agent → 음성 에이전트 (별도 검토)
│  └─ antlr-code-parser → 코드 분석 (Axiom 범위 외)
```

#### 4.11.5 모듈 간 통신 규약

```
┌─────────────────────────────────────────────────────────────────┐
│  Axiom 모듈 간 통신 (Internal API Contract)                      │
│                                                                   │
│  동기 호출 (REST):                                               │
│  Canvas ──HTTP──▶ Core ──HTTP──▶ Vision/Oracle/Synapse/Weaver   │
│                                                                   │
│  비동기 이벤트 (Redis Streams):                                   │
│  Core ──publish──▶ [event_outbox] ──consume──▶ Vision            │
│  Core ──publish──▶ [event_outbox] ──consume──▶ Synapse           │
│  Core ──publish──▶ [watch_events] ──consume──▶ Canvas (SSE)      │
│                                                                   │
│  데이터 공유:                                                     │
│  Core/Vision/Oracle/Synapse/Weaver ──▶ PostgreSQL (공유 DB)      │
│  Oracle/Synapse ──▶ Neo4j (공유 그래프)                           │
│  Core ──▶ Redis (캐시 + 스트림)                                   │
│                                                                   │
│  금지 패턴:                                                       │
│  ✗ Oracle → Core 직접 DB 쿼리 (API를 통해서만 접근)             │
│  ✗ Vision → Synapse import (REST API 호출만 허용)                │
│  ✗ Canvas → DB 직접 접근 (반드시 API 경유)                       │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.11.6 이식 시 핵심 변환 패턴

| # | K-AIR 패턴 | Axiom 변환 | 코드 예시 |
|---|-----------|-----------|----------|
| 1 | `Supabase.from_("table")` | `session.execute(select(Model))` | Supabase SDK → SQLAlchemy ORM |
| 2 | `keycloak_openid.decode_token()` | `jwt.decode(token, SECRET, algorithms=["HS256"])` | Keycloak → python-jose |
| 3 | `CrewAI(agents=[...]).kickoff()` | `graph.compile().invoke(state)` | CrewAI → LangGraph |
| 4 | `A2AClient.send_task(agent_url)` | `graph.invoke({"agent": agent_name})` | A2A SDK → LangGraph 멀티에이전트 |
| 5 | `Vue ref() / Pinia store` | `useState() / Zustand store` | Vue 3 반응성 → React 훅 |
| 6 | `ContextVar.get()` (테넌트) | `ContextVar.get()` (동일) | 멀티테넌트 패턴 그대로 활용 |
| 7 | `neo4j_driver.session()` | `neo4j_driver.session()` (동일) | Neo4j 드라이버 동일 |
| 8 | `mindsdb_client.query()` | `mindsdb_client.query()` (동일) | MindsDB HTTP 클라이언트 동일 |

> **핵심 인사이트**: K-AIR Python 백엔드 코드의 약 60%는 변경 최소화 이식 가능 (FastAPI→FastAPI, Neo4j→Neo4j, LangChain→LangChain).
> 가장 큰 전환 비용은 **프론트엔드 (Vue 3 → React)** 와 **에이전트 프레임워크 (CrewAI → LangGraph)**.

---

## 5. 핵심 기술 스택

### 5.1 확인된 기술 (소스코드 기준)

| 분류 | 기술 | 버전 | 사용 모듈 |
|------|------|------|----------|
| **Backend Framework** | FastAPI | 0.109~0.118 | completion, fabric, text2sql, memento 등 |
| | Spring Boot | 2.3.12 | gs-main/gateway |
| | Starlette | 0.39 | voice-agent, a2a-orch |
| | Express.js | 4.19 | eventstorming-tool |
| **Frontend** | Vue 3 | 3.2~3.5 | vue3, gs-main, fabric, olap, eventstorming |
| | Vuetify | 3.4.10 | vue3, gs-main |
| | Tailwind CSS | 3.4.19 | fabric/frontend |
| | Konva | 9.3.22 | eventstorming-tool |
| **State** | Pinia | 2.0~3.0 | vue3, gs-main, olap, fabric |
| | Yjs (CRDT) | 13.6.27 | eventstorming-tool |
| **Build** | Vite | 4.5~7.2 | vue3, gs-main, fabric, olap, eventstorming |
| **LLM** | OpenAI GPT-4o | latest | completion, text2sql, feedback 등 전체 |
| | Anthropic Claude | 0.54 | completion |
| | Google Gemini | 4.1.3 | text2sql |
| | Ollama | latest | completion (로컬) |
| **LLM Framework** | LangChain | 0.3.25~0.3.27 | completion, text2sql, memento, bpmn 등 |
| | LangGraph | 0.0.20~0.2.32 | bpmn, olap, voice-agent |
| | CrewAI | 0.152~0.175 | crewai-action, deep-research |
| | Mem0 | 0.1.108 | completion, feedback |
| **Agent Protocol** | A2A SDK | 0.2.4 | crewai-action, a2a-orch, agent-utils |
| | MCP (FastMCP) | 1.9+ | completion, langchain-react, feedback |
| **Database** | Supabase (PostgreSQL) | 2.15~2.39 | completion, gs-main, memento 등 전체 |
| | Neo4j | 5.23~6.0 | fabric, text2sql, bpmn, olap |
| | MindsDB | latest | fabric, text2sql |
| | pgvector | 0.3.6 | completion (벡터 임베딩) |
| **SQL** | SQLGlot | 27.24 | text2sql (구조적 SQL 검증) |
| | asyncpg | 0.29~0.30 | fabric, text2sql, olap |
| | aiomysql | 0.2 | fabric, text2sql |
| **Document** | pdfplumber | 0.11 | bpmn-extractor |
| | PyMuPDF | 1.23.8 | memento |
| | python-docx | 1.1.2 | memento |
| | python-pptx | 0.6.23 | memento |
| | HWP/HWPX 추출기 | custom | memento (vendor) |
| **BPMN/DMN** | bpmn-js | 17.9.1 | vue3, gs-main |
| | dmn-js | 17.4.0 | vue3, gs-main |
| **Chart/Viz** | ApexCharts | 3.40 | vue3 |
| | Mermaid | 11.10~11.12 | vue3, olap |
| | Cytoscape | 3.33.1 | vue3 (그래프) |
| **Parsing** | ANTLR | 4.13.1 | antlr-code-parser (Java/PL-SQL/PostgreSQL) |
| **Auth** | Keycloak | 24.0.2 | vue3, gs-main |
| | Supabase Auth | built-in | 전체 |
| | JWT (JJWT) | 0.9.1 | gs-main/gateway |
| **Real-time** | WebSocket | native | voice-agent, eventstorming |
| | SSE (Server-Sent Events) | starlette | text2sql, fabric |
| | Supabase Realtime | built-in | completion |
| | Socket.io | 4.7.4 | gs-main |
| **Monitoring** | LangSmith | 0.3.45 | completion |
| | OpenTelemetry | 0.55b1 | completion |
| **Infra** | Docker | standard | 전체 |
| | Kubernetes | 33.1 | process-gpt-main |
| | Apache Airflow | latest | olap (ETL DAGs) |

### 5.2 기술 스택 아키텍처 다이어그램

```
┌─ Frontend ──────────────────────────────────────────────────┐
│  Vue 3 │ TypeScript │ Vite │ Vuetify │ Pinia │ bpmn-js     │
│  Konva │ Yjs(CRDT)  │ ApexCharts │ Mermaid │ Monaco Editor │
└─────────────────────────────────────────────────────────────┘
                              │
┌─ API Gateway ───────────────┼───────────────────────────────┐
│  Spring Boot │ Spring Cloud Gateway │ JWT │ JJWT            │
└─────────────────────────────┼───────────────────────────────┘
                              │
┌─ Backend Services ──────────┼───────────────────────────────┐
│  FastAPI │ Starlette │ Uvicorn │ Pydantic v2                │
│  SQLAlchemy │ asyncpg │ aiomysql │ httpx                    │
└─────────────────────────────┼───────────────────────────────┘
                              │
┌─ AI/Agent Layer ────────────┼───────────────────────────────┐
│  LangChain │ LangGraph │ CrewAI │ Mem0 │ A2A SDK │ MCP     │
│  OpenAI │ Anthropic │ Gemini │ Ollama │ Transformers        │
└─────────────────────────────┼───────────────────────────────┘
                              │
┌─ Data Layer ────────────────┼───────────────────────────────┐
│  Supabase(PostgreSQL+pgvector+Auth+Realtime)                │
│  Neo4j 5 (Graph+VectorIndex+APOC)                           │
│  MindsDB (DataFabric+ML) │ Redis │ Apache Airflow           │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. 데이터 아키텍처

### 6.1 PostgreSQL (Supabase) 주요 테이블

`process-gpt-main/init.sql` (95KB) 기준:

```sql
-- ━━━ 테넌트 & 사용자 ━━━
tenants         (id, owner, mcp_config)
users           (id, username, email, tenant_id, role, skills, is_agent)

-- ━━━ 프로세스 정의 ━━━
proc_def        (id, name, bpmn, definition, type, tenant_id)
proc_def_version(proc_def_id, version, snapshot, diff, timestamp)
form_def        (id, name, fields_json, html, proc_def_id, activity_id)

-- ━━━ 프로세스 실행 ━━━
bpm_proc_inst   (proc_inst_id, proc_def_id, status, start_date)
bpm_work_item   (task_id, proc_inst_id, activity_id, assignee, status)
bpm_event       (event_id, proc_inst_id, event_type, event_status)

-- ━━━ 에이전트 & 메모리 ━━━
agent_memory    (agent_id, memory_data)
activity_log    (activity_id, user_id, action, timestamp)

-- ━━━ 설정 ━━━
configuration   (key, value, tenant_id)
mcp_config      (server_key, tool_definitions)

-- ━━━ ENUM 타입 ━━━
process_status  ('RUNNING', 'COMPLETED', 'TERMINATED', 'SUSPENDED')
todo_status     ('PENDING', 'IN_PROGRESS', 'DONE', 'CANCELLED')
agent_mode      ('AUTONOMOUS', 'SUPERVISED', 'MANUAL')

-- ━━━ RLS (Row Level Security) ━━━
-- 모든 주요 테이블에 tenant_id 기반 RLS 정책 적용
-- tenant_id() 함수로 현재 테넌트 자동 추출
```

### 6.2 Neo4j 그래프 스키마

#### robo-data-fabric (데이터 패브릭 메타데이터)

```cypher
(:DataSource {name, engine, host, port, database, user, password})
  -[:HAS_SCHEMA]-> (:Schema {name})
    -[:HAS_TABLE]-> (:Table {name, description})
      -[:HAS_COLUMN]-> (:Column {name, dtype, nullable, description})

(:Column)-[:FK_TO]->(:Column)           -- Foreign Key 관계
(:Table)-[:FK_TO_TABLE]->(:Table)        -- 테이블 레벨 FK
```

#### robo-data-text2sql (NL2SQL 벡터 + 그래프)

```cypher
(:Table {name, schema, db, description, vector, text_to_sql_vector, text_to_sql_is_valid})
(:Column {fqn, name, dtype, nullable, description, vector, text_to_sql_is_valid})
(:Query {question, sql, summary, vector, verified, canonical_id})
(:ValueMapping {natural_value, db_value, column_fqn, confidence, verified})

-- 관계
(Table)-[:HAS_COLUMN]->(Column)
(Column)-[:FK_TO]->(Column)
(Query)-[:USES_TABLE]->(Table)
(Query)-[:SIMILAR_TO {score}]->(Query)
(Column)-[:MAPPED_VALUE]->(ValueMapping)
```

### 6.3 데이터 흐름

```
┌─ 데이터 수집 ─────────────────────────────────────────────┐
│                                                            │
│  레거시 DB ──ETL──▶ Supabase PostgreSQL                    │
│  IoT 센서  ──Kafka──▶ 실시간 계측 데이터                   │
│  문서 파일  ──Upload──▶ Supabase Storage                   │
│  Google Drive ──OAuth──▶ Memento 문서 처리                 │
│                                                            │
├─ 데이터 처리 ─────────────────────────────────────────────┤
│                                                            │
│  MindsDB: 다중 DB 추상화 (MySQL/PostgreSQL 프로토콜)       │
│  Neo4j:   메타데이터 그래프 + 벡터 인덱스                  │
│  pgvector: 문서 임베딩 벡터 저장소                         │
│                                                            │
├─ 데이터 활용 ─────────────────────────────────────────────┤
│                                                            │
│  Text2SQL: 자연어 → SQL (Neo4j RAG + LLM)                  │
│  OLAP:     피벗 분석 (Mondrian + Star Schema)              │
│  RAG:      문서 기반 Q&A (Supabase Vector)                 │
│  Agent:    CrewAI 도구를 통한 데이터 접근                  │
└────────────────────────────────────────────────────────────┘
```

---

## 7. AI/LLM 아키텍처

### 7.1 LLM 통합 포인트

| 모듈 | LLM 용도 | 모델 | 프레임워크 |
|------|---------|------|-----------|
| **completion** | 프로세스 정의 생성, 채팅 | GPT-4o, Claude, Gemini, Ollama | LangChain |
| **text2sql** | SQL 생성 + 검증 + 캐시 | GPT-4o, Gemini Flash | LangChain |
| **bpmn-extractor** | PDF → 엔티티 추출 → BPMN | GPT-4o | LangGraph |
| **memento** | 문서 요약, 이미지 분석, RAG | GPT-4o, Vision | LangChain |
| **voice-agent** | 음성 대화 | GPT-4o Realtime | LangChain + LangGraph |
| **crewai-action** | 동적 에이전트 작업 | GPT-4o/4.1 | CrewAI |
| **deep-research** | 보고서 생성 (5단계) | GPT-4.1 | CrewAI Flow |
| **agent-feedback** | 피드백 분석/충돌 해결 | GPT-4o | LangChain (ReAct) |
| **langchain-react** | 코드 실행 + 문제 해결 | GPT-4 | LangGraph (ReAct) |
| **olap** | Text2SQL (피벗 쿼리) | GPT-4o-mini | LangGraph |
| **eventstorming** | 코드 → 이벤트스토밍/UML 역공학 | GPT-4o | OpenAI API |
| **vue3** | 35개 AI 생성기 (BPMN/DMN/Chart/Form 등) | GPT-4o | 직접 호출 |

### 7.2 LLM 클라이언트 팩토리 패턴

```python
# process-gpt-completion-main/features/process_chat/interfaces/chat_interface/clients/

class ClientFactory:
    @staticmethod
    def get_client(provider: str):
        match provider:
            case "openai":     return OpenAIClient()
            case "anthropic":  return AnthropicClient()
            case "google":     return GoogleClient()
            case "ollama":     return OllamaClient()
            case "langchain":  return LangChainClient()  # 체인 기반
```

### 7.3 Text2SQL RAG 파이프라인 (가장 정교한 LLM 통합)

```
사용자 자연어 질문
        │
        ▼
┌──── 멀티축 벡터 검색 (5개 축) ────┐
│  1. question: 질문 직접 임베딩     │
│  2. hyde: 가상 SQL 기반 검색       │
│  3. regex: 키워드 정규표현식       │
│  4. intent: 질문 의도 분류         │
│  5. prf: 개인화 순위              │
└──────────┬─────────────────────────┘
           │ 가중 합산 & 리랭킹
           ▼
┌──── FK 그래프 경로 탐색 ──────────┐
│  Neo4j에서 FK 관계 3홉까지 확장   │
│  관련 테이블/컬럼 자동 발견       │
└──────────┬─────────────────────────┘
           │ 유효성 필터 (빈 테이블/컬럼 제거)
           ▼
┌──── ReAct 에이전트 ───────────────┐
│  Step 1: 테이블/컬럼 선택          │
│  Step 2: SQL 후보 N개 동시 생성    │
│  Step 3: SQLGlot 구조적 검증      │
│  Step 4: 자동수정 (SQL Guard)      │
│  Step 5: 품질 게이트 (N회 LLM 심사)│
│  Step 6: 트리아지 (최적 SQL 선택)  │
└──────────┬─────────────────────────┘
           │
           ▼
┌──── SQL 실행 + 후처리 ────────────┐
│  SELECT-only + LIMIT 강제          │
│  타임아웃 30초                     │
│  결과 + Vega-Lite 시각화 추천      │
│  백그라운드: 쿼리 캐시 + 클러스터링│
└────────────────────────────────────┘
```

### 7.4 HITL (Human-in-the-Loop) 3단계 신뢰도

```
신뢰도 99%+  → 자동 실행 (사람 개입 불필요)
신뢰도 80%+  → 사람 확인 후 실행
신뢰도 <80%  → 사람이 직접 수정 → 학습 데이터로 활용
```

이 패턴은 text2sql, agent-feedback, bpmn-extractor에서 공통 사용된다.

---

## 8. 에이전트 시스템

### 8.1 에이전트 프레임워크 비교

| 저장소 | 프레임워크 | 패턴 | 도구 | 통신 |
|--------|-----------|------|------|------|
| **crewai-action** | CrewAI | Role-based Crew | MCP SafeToolLoader | A2A SDK (폴링) |
| **deep-research** | CrewAI Flow | 상태 머신 | MCP + 이미지/지식 | 내부 (Flow) |
| **agent-feedback** | LangChain | ReAct 5단계 | Memory/DMN/Skill 커밋 | Supabase 폴링 |
| **langchain-react** | LangGraph | ReAct | 9개 MCP 도구 (파일/코드) | CLI/FastAPI |
| **voice-agent** | LangGraph | Voice ReAct | 프로세스/할일/조직도 조회 | WebSocket |
| **a2a-orch** | A2A SDK | Sync/Async | 타겟 에이전트 호출 | HTTP + Webhook |

### 8.2 에이전트 지식 학습 루프 (agent-feedback)

```
User Feedback → Polling Manager (7초) → Feedback Processor
                                             │
                                    ReAct Agent (5단계)
                                    ├─ STEP 1: 목표/상황 이해
                                    ├─ STEP 2: 기존 지식 분석
                                    ├─ STEP 3: 충돌 분석
                                    │   └─ ConflictAnalyzer:
                                    │      operation: CREATE|UPDATE|DELETE|MERGE|SKIP
                                    │      conflict_level: NO|LOW|MEDIUM|HIGH
                                    ├─ STEP 4: 라우팅 결정
                                    │   └─ LearningRouter:
                                    │      → MEMORY (mem0 벡터)
                                    │      → DMN_RULE (Supabase proc_def XML)
                                    │      → SKILL (HTTP API / Skill Creator MCP)
                                    │      → MIXED (조합)
                                    └─ STEP 5: 머지 전략 수립
                                             │
                                    LearningCommitter (CRUD)
```

### 8.3 MCP (Model Context Protocol) 통합

```python
# agent-utils의 SafeToolLoader
class SafeToolLoader:
    def create_tools_from_names(tool_names: List[str]):
        # 1. MCP 서버에서 도구 동적 로드
        # 2. 보안 정책 기반 필터링
        # 3. 서버 출처 태깅
        # 4. 우선순위 정렬:
        #    claude-skills > computer-use > dmn_rule > mem0 > 기타 MCP
```

### 8.4 A2A (Agent-to-Agent) 프로토콜

```
┌─ 동기 모드 ────────────────────────────────────────────┐
│  Client → A2AAgentExecutor → 타겟 Agent → 응답 대기    │
└────────────────────────────────────────────────────────┘

┌─ 비동기 모드 (Webhook) ───────────────────────────────┐
│  Client → A2AAgentExecutor → 즉시 반환                 │
│                    ↓                                    │
│  타겟 Agent → 작업 완료 → Webhook Receiver (별도 Pod)   │
│                              ↓                          │
│                     Supabase에 결과 저장                │
└────────────────────────────────────────────────────────┘
```

---

## 9. 프로세스 엔진 (BPM)

### 9.1 프로세스 정의 모델

```python
# process-gpt-completion-main/process_definition.py

class ProcessDefinition:
    processDefinitionName: str
    processDefinitionId: str
    data: List[ProcessData]          # 데이터 소스 (SQL/DB)
    roles: List[ProcessRole]         # 역할 (할당 규칙)
    activities: List[ProcessActivity]# 활동 (BPMN 태스크)
    gateways: List[Gateway]          # 게이트웨이 (분기)
    transitions: List[Transition]    # 전이 (흐름)

class ProcessActivity:
    name: str
    id: str
    type: str                        # humanTask, serviceTask, scriptTask
    instruction: str                 # AI 에이전트 지시사항
    inputData: List[ProcessData]
    outputData: List[ProcessData]
    pythonCode: str                  # 커스텀 로직
    agent: str                       # 에이전트 ID
    agentMode: str                   # AUTONOMOUS, SUPERVISED, MANUAL
    orchestration: dict              # CrewAI 오케스트레이션 설정
```

### 9.2 프로세스 실행 흐름

```
1. NL 프로세스 정의 (LLM이 자연어 → BPMN 변환)
       │
2. 프로세스 인스턴스 생성
       │
3. 역할 바인딩 (참가자 할당)
       │
4. 워크아이템 실행 루프:
   ├─ 현재 활동 조회
   ├─ agentMode 확인:
   │   ├─ AUTONOMOUS → AI 자동 실행
   │   ├─ SUPERVISED → AI 실행 + 사람 확인
   │   └─ MANUAL → 사람 직접 처리
   ├─ 작업 제출 (submit_workitem)
   ├─ 게이트웨이 평가 (분기 조건)
   └─ 다음 활동으로 전이
       │
5. 보상 트랜잭션 (Saga 패턴)
   └─ 실패 시 MCP 도구로 자동 롤백
```

### 9.3 프로세스 계층 구조 (Definition Map)

```
MegaProcess (최상위 비즈니스 프로세스)
  ├── MajorProcess (주요 단계)
  │   ├── BaseProcess (기본 활동 = BPMN)
  │   │   └── SubProcess (세부 단계)
  │   └── BaseProcess
  └── MajorProcess
      └── BaseProcess
```

---

## 10. 데이터 플랫폼 (K-AIR 고유)

### 10.1 robo-data-fabric 아키텍처

```
┌─ Vue3 Frontend ─────────────────────────────────────┐
│  Dashboard │ DataSources │ QueryEditor │ MindsDB    │
└───────────────────────┬─────────────────────────────┘
                        │ Axios HTTP
┌───────────────────────▼─────────────────────────────┐
│  FastAPI Backend (port 8000)                         │
│                                                      │
│  ┌─ Routers ──────────────────────────────────────┐ │
│  │  datasources.py: CRUD + 메타데이터 추출 (SSE)  │ │
│  │  query.py: SQL 실행 + MindsDB Objects          │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ Services ─────────────────────────────────────┐ │
│  │  mindsdb_service.py: HTTP API 클라이언트 (308줄)│ │
│  │  neo4j_service.py: DataSource 노드 관리 (297줄)│ │
│  │  schema_introspection.py: 어댑터 (880줄)       │ │
│  │    └─ PostgreSQLAdapter                         │ │
│  │    └─ MySQLAdapter                              │ │
│  │    └─ OracleAdapter                             │ │
│  └────────────────────────────────────────────────┘ │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
  ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐
  │  Neo4j  │   │  MindsDB  │  │ 대상 DB │
  │  메타   │   │  (SQL     │  │ (PG,    │
  │  데이터 │   │   실행)   │  │  MySQL) │
  └─────────┘   └───────────┘  └─────────┘
```

### 10.2 robo-data-text2sql 아키텍처

```
┌─ API (FastAPI) ──────────────────────────────────────┐
│                                                      │
│  /text2sql/ask     : 단순 질의 (단일 라운드)         │
│  /text2sql/react   : ReAct 스트리밍 (다단계 추론)    │
│  /text2sql/meta/*  : 메타데이터 조회                 │
│  /text2sql/cache/* : 캐시/매핑/템플릿 관리           │
│  /text2sql/events/*: 이벤트 룰/스케줄러/알림         │
│  /text2sql/direct-sql: SQL 직접 실행                 │
│  /text2sql/watch-agent/*: 감시 에이전트              │
│                                                      │
│  ┌─ Core (24개 모듈) ──────────────────────────────┐ │
│  │  llm_factory.py     : LLM/Embedding 팩토리      │ │
│  │  graph_search.py    : 멀티축 벡터+그래프 검색    │ │
│  │  prompt.py          : SQL 생성 프롬프트          │ │
│  │  sql_guard.py       : SELECT-only + LIMIT 강제  │ │
│  │  sql_exec.py        : 타임아웃 + 행수 제한      │ │
│  │  viz.py             : Vega-Lite 시각화 추천      │ │
│  │  query_cache.py     : LLM 응답 캐시             │ │
│  │  background_jobs.py : 비동기 워커 (4개)         │ │
│  │  simple_cep.py      : 이벤트 감지 엔진          │ │
│  └─────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ ReAct (다단계 추론) ───────────────────────────┐ │
│  │  controller.py      : ReAct 루프 컨트롤러       │ │
│  │  state.py           : 세션 상태                 │ │
│  │  generators/ (19개) : LLM 생성기                │ │
│  │  tools/             : build_sql_context 등      │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 10.3 data-platform-olap 아키텍처

```
┌─ Vue3 Frontend ────────────────────────────────────┐
│  PivotEditor │ NaturalQuery │ CubeModeler │ ETL   │
└──────────────────────┬─────────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────────┐
│  FastAPI Backend                                    │
│                                                     │
│  ┌─ Services ────────────────────────────────────┐ │
│  │  xml_parser.py      : Mondrian XML 파서       │ │
│  │  sql_generator.py   : 피벗 쿼리 → SQL         │ │
│  │  metadata_store.py  : 큐브 메타데이터         │ │
│  │  db_executor.py     : SQL 실행                │ │
│  │  neo4j_client.py    : 데이터 계보             │ │
│  │  etl_service.py     : ETL 통합                │ │
│  │  airflow_service.py : Airflow DAG 관리        │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ LangGraph Workflow ──────────────────────────┐ │
│  │  text2sql.py:                                 │ │
│  │  parse_question → retrieve_schema →           │ │
│  │  generate_sql → execute_query → format_result │ │
│  └───────────────────────────────────────────────┘ │
└──────┬──────────────┬──────────────┬───────────────┘
       │              │              │
  ┌────▼────┐   ┌─────▼─────┐  ┌────▼────────┐
  │PostgreSQL│  │  Neo4j    │  │ Airflow     │
  │(팩트+   │  │  (데이터  │  │ (ETL DAGs:  │
  │ 차원)   │  │   계보)   │  │  데이터분석) │
  └─────────┘  └───────────┘  └─────────────┘
```

---

## 11. 프론트엔드 아키텍처

### 11.1 SpikeAdmin (process-gpt-vue3-main)

**규모**: 35개 AI 생성기, 70+ 컴포넌트, 20+ Pinia 스토어

**핵심 AI 생성기**:
- `ProcessDefinitionGenerator.js` (24KB) - 비즈니스 프로세스 자동 생성
- `FormDesignGenerator.js` (16KB) - 사용자 폼 자동 생성
- `DmnGenerator.js` (15KB) - DMN 의사결정 테이블 자동 생성
- `BpmnDiffGenerator.js` - BPMN 버전 비교
- `ProcessConsultingGenerator.js` - 프로세스 자문 AI
- `ChatAssistantGenerator.js` - 챗봇 생성
- `OrganizationChartGenerator.js` - 조직도 생성

**핵심 기능 모듈**:
- BPMN 디자이너 (bpmn-js 17.9.1)
- DMN 편집기 (dmn-js 17.4.0)
- 에이전트 채팅 (AgentChat.vue + AgentSkills.vue)
- OLAP 피벗 분석 (PivotEditor + NaturalQueryInput)
- 프로세스 정의 맵 (MegaProcess → BaseProcess 계층)
- 간트 차트 (dhtmlx-gantt 9.0.10)
- 문서 생성 (PDF, Word, Excel, PowerPoint)

### 11.2 Backend 팩토리 패턴

```typescript
// 환경에 따라 다른 Backend 구현체 선택
interface Backend {
    listDefinition(path, options): Promise<any>
    deleteDefinition(defId, options): Promise<any>
    findCurrentWorkItemByInstId(instId): Promise<any>
    // ... 40+ 메서드
}

class ProcessGPTBackend implements Backend { }  // 기본
class UEngineBackend implements Backend { }     // 레거시
class PalModeBackend implements Backend { }     // PAL 모드
```

### 11.3 EventStorming Tool (eventstorming-tool-vite-main)

**핵심 기술**: Yjs CRDT + Konva 2D Canvas + WebSocket
**Axiom 역할**: Canvas: Business Process Designer UI + Synapse: 프로세스 마이닝 엔진의 기반 — **핵심 이식 대상**

```
┌─ 실시간 협업 ────────────────────────────────────────┐
│  Yjs Doc (CRDT)                                      │
│  ├─ canvasItems: Y.Array  (이벤트스토밍 아이템)       │
│  ├─ connections: Y.Array  (연결선)                    │
│  └─ boardType: Y.Text    (Eventstorming | UML)       │
│                                                      │
│  WebSocket Provider ←──▶ Express.js 서버             │
│  UndoManager (실행 취소/다시 실행)                    │
└──────────────────────────────────────────────────────┘

┌─ 역공학 기능 ────────────────────────────────────────┐
│  ZIP 업로드 → 소스코드 분석 → OpenAI GPT 호출 →      │
│  이벤트스토밍 보드 자동 생성 + UML 다이어그램 생성    │
└──────────────────────────────────────────────────────┘
```

#### 11.3.1 비즈니스 프로세스 확장

EventStorming의 7개 핵심 개념을 비즈니스 프로세스 레벨로 매핑하여 Canvas Business Process Designer와 Synapse 프로세스 마이닝의 공통 모델로 활용한다.

**EventStorming → 비즈니스 프로세스 매핑**

| EventStorming 개념 | 비즈니스 프로세스 매핑 | 설명 |
|-------------------|---------------------|------|
| ContextBox | Business Domain | 비즈니스 도메인 경계 (조직, 부서, 시스템 등) |
| Command | Business Action | 비즈니스 행위 (승인, 발주, 검수 등 실행 가능한 액션) |
| Event | Business Event | 비즈니스 이벤트 (발생 사실 기록, 시간축 + 측정값 포함) |
| Aggregate | Business Entity | 비즈니스 엔티티 (주문, 고객, 재고 등 상태를 갖는 객체) |
| Policy | Business Rule | 비즈니스 규칙 (자동 트리거 조건, SLA, 임계값 등) |
| Actor | Stakeholder | 이해관계자 (역할, 부서, 외부 파트너 등) |
| ReadModel | Business Report | 비즈니스 보고서 (대시보드, KPI 뷰, 현황 조회 등) |

**4가지 확장 포인트**

```
┌─ 확장 1: 시간축 ────────────────────────────────────────┐
│  Event에 duration / SLA / timestamp 속성 추가           │
│  → Business Event가 "언제, 얼마나 걸렸는지" 표현 가능   │
│  → 프로세스 병목 분석의 기초 데이터                      │
└─────────────────────────────────────────────────────────┘

┌─ 확장 2: 측정값 바인딩 ────────────────────────────────┐
│  Event 체인에 Measure / KPI 연결                        │
│  → Command→Event→Policy 흐름에 비즈니스 지표 부착       │
│  → Synapse 온톨로지 R→P→M→KPI 4계층과 직접 연동        │
└─────────────────────────────────────────────────────────┘

┌─ 확장 3: 이벤트 로그 바인딩 ──────────────────────────┐
│  Business Event에 실제 데이터 소스 연결                  │
│  → ERP, MES, WMS 등의 트랜잭션 로그를 Event에 매핑      │
│  → Case ID + Activity + Timestamp 자동 추출             │
└─────────────────────────────────────────────────────────┘

┌─ 확장 4: 프로세스 마이닝 ─────────────────────────────┐
│  pm4py 기반 자동 발견 / 적합도 검사                     │
│  → 이벤트 로그 → Alpha Miner / Heuristic Miner 자동 발견│
│  → 설계 모델 vs 실제 로그 적합도(conformance) 검사      │
│  → 병목(bottleneck) 자동 감지 + 개선 제안               │
└─────────────────────────────────────────────────────────┘
```

**Axiom 활용 방향**

```
┌─────────────────────────────────────────────────────────────┐
│  eventstorming-tool-vite-main                                │
│  (Yjs CRDT + Konva 캔버스 + 7개 개념 모델)                   │
│                                                              │
│         ┌──────────────┐          ┌──────────────┐          │
│         │ Axiom Canvas │          │ Axiom Synapse│          │
│         │ ──────────── │          │ ──────────── │          │
│         │ Business     │          │ 프로세스     │          │
│         │ Process      │◀────────▶│ 마이닝 엔진  │          │
│         │ Designer UI  │          │              │          │
│         │              │          │ · pm4py      │          │
│         │ · 비즈니스   │          │ · 자동 발견  │          │
│         │   프로세스   │          │ · 적합도     │          │
│         │   시각적     │          │ · 병목 감지  │          │
│         │   모델링     │          │              │          │
│         │ · 실시간     │          │ · 이벤트로그 │          │
│         │   협업 편집  │          │   → 프로세스 │          │
│         │   (Yjs CRDT) │          │   모델 비교  │          │
│         └──────────────┘          └──────────────┘          │
│                                                              │
│  Canvas가 설계 모델을 그리면, Synapse가 실제 데이터로        │
│  검증하고 병목/이탈을 발견하는 피드백 루프                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. 인프라 및 배포

### 12.1 Kubernetes 매니페스트 (process-gpt-main)

```yaml
# 총 10개 Deployment
deployments/
  ├── completion-deployment.yaml       # BPM 코어 (Python)
  ├── frontend-deployment.yaml         # Vue3 SPA
  ├── gateway.yaml                     # Spring Boot Gateway
  ├── memento-deployment.yaml          # 문서 처리 서비스
  ├── crewai-action-deployment.yaml    # CrewAI 액션
  ├── crewai-deep-research-deployment.yaml
  ├── react-voice-agent-deployment.yaml# 음성 에이전트
  ├── polling-service-deployment.yaml  # 이벤트 폴링
  ├── scaling-agent.yaml               # 자동 스케일링
  └── airbnb-agent.yaml                # 데모 에이전트

# 서비스
services/
  ├── completion-service.yaml          # ClusterIP
  ├── gateway-service.yaml             # LoadBalancer
  ├── frontend-deployment-service.yaml
  ├── memento-service-service.yaml
  └── react-voice-agent-service.yaml

# 인프라
├── rbac.yaml                          # 역할 기반 접근 제어
├── pvc.yaml                           # 영구 볼륨 클레임
├── configmap-example.yaml             # 환경설정
└── secrets-example.yaml               # 시크릿 (API 키 등)
```

### 12.2 Docker Compose (로컬 개발)

```
각 서비스별 독립 docker-compose.yml:
  robo-data-fabric:   PostgreSQL 15 + MindsDB
  robo-data-text2sql: Neo4j 5.23 + PostgreSQL 16 + MindsDB
  data-platform-olap: PostgreSQL 15 + Airflow
  bpmn-extractor:     Neo4j 5 + FastAPI
  a2a-orch:           Executor Pod + Webhook Receiver Pod
```

### 12.3 필수 환경변수

```bash
# 공통
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
OPENAI_API_KEY=sk-...

# Gateway (Spring Boot)
JWT_SECRET=...
COMPLETION_SERVICE_URL=http://completion:8000

# Text2SQL
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
LLM_PROVIDER=openai|google|openai_compatible
LLM_MODEL=gpt-4o|gemini-3-flash-preview

# Data Fabric
MINDSDB_URL=http://localhost:47334

# Voice Agent
OPENAI_API_KEY=sk-... (Realtime API 필요)
```

---

## 13. 설계 의사결정 분석

### 13.1 아키텍처 수준 결정

| # | 결정 | 근거 (소스코드 분석 기반) |
|---|------|--------------------------|
| 1 | **Supabase를 공통 DB로 채택** | PostgreSQL + Auth + Realtime + Storage + pgvector를 단일 플랫폼으로 → 멀티테넌트 RLS + 벡터 검색 + 실시간 구독을 하나로 해결 |
| 2 | **Neo4j를 메타데이터 + 벡터 저장소로** | 그래프 DB의 관계 탐색(FK 경로) + 벡터 인덱스를 하나로 → Text2SQL RAG의 핵심 데이터 소스 |
| 3 | **MindsDB로 데이터 패브릭 구현** | 다중 DB 추상화 + MySQL 프로토콜 → MindsDB 하나로 PostgreSQL/MySQL 모두 접근 |
| 4 | **CrewAI + A2A SDK 조합** | CrewAI는 역할 기반 에이전트 관리, A2A SDK는 에이전트 간 통신 → 느슨한 결합의 에이전트 생태계 |
| 5 | **MCP (Model Context Protocol) 전면 채택** | 에이전트 도구를 MCP 서버로 격리 → 보안 + 도구 교체 용이 + claude-skills 통합 |
| 6 | **Spring Boot Gateway + FastAPI 서비스** | JWT 검증 + 라우팅은 Java/Spring이 성숙, AI 서비스는 Python 생태계 활용 → 각 언어의 강점 활용 |
| 7 | **Yjs CRDT로 실시간 협업** | Operational Transformation 대신 CRDT → 서버 부하 감소 + 오프라인 지원 + 자동 충돌 해결 |
| 8 | **Pinia (Vuex 교체)** | Vue 3 Composition API 친화적 + TypeScript 네이티브 지원 + 더 간결한 API |
| 9 | **Saga 패턴 (보상 트랜잭션)** | 마이크로서비스 간 분산 트랜잭션 → MCP 도구로 자동 롤백 |
| 10 | **LangGraph vs LangChain 사용 분리** | 단순 체인: LangChain, 복잡한 워크플로우(BPMN 추출, 음성 에이전트): LangGraph |

### 13.2 데이터 모델 수준 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | **init.sql 95KB 단일 파일** | 마이그레이션 없이 Supabase에 직접 배포 → 빠른 프로토타이핑 (단점: 버전 관리 어려움) |
| 2 | **ContextVar 기반 멀티테넌트** | 요청별 테넌트 격리 → RLS 정책과 연동, 글로벌 상태 오염 방지 |
| 3 | **Neo4j에 비밀번호 평문 저장** | TODO로 남아있음 → 프로토타입 단계의 기술 부채 |
| 4 | **proc_def에 definition JSON 저장** | BPMN XML + ProcessDefinition JSON 이중 저장 → BPMN 렌더링 + AI 접근 모두 지원 |

### 13.3 AI/에이전트 수준 결정

| # | 결정 | 근거 |
|---|------|------|
| 1 | **ReAct 패턴 전면 채택** | Text2SQL, agent-feedback, langchain-react 모두 ReAct → "추론 후 행동" 패턴이 검증 신뢰도 높음 |
| 2 | **멀티축 벡터 검색 (5축)** | 단일 벡터 검색의 한계 극복 → HyDE + keyword + intent + PRF 결합으로 재현율 향상 |
| 3 | **SQLGlot으로 SQL 검증** | LLM이 생성한 SQL의 구조적 무결성 검증 → SELECT-only 강제 + LIMIT 강제 |
| 4 | **Mem0로 장기 기억** | 에이전트 세션 간 학습 유지 → 벡터 기반 유사도 검색으로 관련 기억 인출 |
| 5 | **3가지 지식 저장소 분리** | MEMORY(벡터) + DMN_RULE(XML) + SKILL(API) → 지식 유형에 따른 최적 저장/검색 |
| 6 | **SafeToolLoader 우선순위** | claude-skills > computer-use > dmn_rule > mem0 → 도메인 도구 우선 |

---

## 14. Axiom 적용 시사점

### 14.1 직접 활용 가능 패턴

| K-AIR/ProcessGPT 패턴 | Axiom 적용 포인트 |
|----------------------|-------------------|
| **Text2SQL RAG 파이프라인** | 비즈니스 데이터 자연어 질의 (이해관계자/프로세스 조회) |
| **멀티축 벡터 검색 (5축)** | 비즈니스 문서 검색 정확도 향상 |
| **ReAct 에이전트 패턴** | HITL 3단계 신뢰도 (99%/80%/<80%) 그대로 활용 |
| **SQL Guard (SELECT-only + LIMIT)** | 엔터프라이즈 DB 안전 쿼리 보장 |
| **Neo4j 메타데이터 그래프** | 케이스 관계 그래프 (이해관계자↔대상 조직↔자산↔문서) |
| **Saga 보상 트랜잭션** | LOCK 불변성 위반 시 자동 롤백 |
| **BPMN 프로세스 엔진** | 비즈니스 프로세스 워크플로우 자동화 |
| **PDF → BPMN 추출** | 비즈니스 매뉴얼/규정 → 프로세스 정의 자동화 |
| **Memento 문서 처리** | HWP/PDF 비즈니스 문서 → RAG 검색 |
| **CrewAI Flow 보고서 생성** | 비즈니스 보고서 자동 생성 (자산목록/이해관계자목록 등) |
| **ContextVar 멀티테넌트** | 사건(case_id) 기반 데이터 격리 |
| **Mondrian OLAP** | 비즈니스 통계 분석 (유형별/조직별/기간별) |

### 14.2 기술 스택 차이점

| 항목 | K-AIR/ProcessGPT | Axiom (계획) | 비고 |
|------|------------------|-------------|------|
| **DB** | Supabase (호스팅) | PostgreSQL 15 (자체) | RLS 패턴 동일 |
| **Auth** | Supabase Auth + Keycloak | 자체 JWT | Keycloak 패턴 참조 가능 |
| **Frontend** | Vue 3 + Vuetify | React 18 + Shadcn/ui | 컴포넌트 패턴 참조 |
| **Gateway** | Spring Boot | FastAPI (직접) | K-AIR의 JWT 필터 패턴 참조 |
| **Agent** | CrewAI + A2A SDK | LangGraph (계획) | LangGraph가 더 적합 |
| **Vector** | pgvector + Neo4j Vector | pgvector (계획) | Neo4j 추가 고려 |

### 14.3 주의사항 (K-AIR의 기술 부채)

| 문제 | K-AIR 현황 | Axiom 대응 |
|------|-----------|-----------|
| Neo4j 비밀번호 평문 | TODO 상태 | Vault/암호화 필수 |
| CORS `allow_origins=["*"]` | 개발 편의 | 프로덕션에서 도메인 제한 |
| init.sql 95KB 단일 파일 | 마이그레이션 없음 | Alembic 마이그레이션 사용 |
| MindsDB 인증 미설정 | 개발 환경 | 프로덕션 인증 필수 |
| 테스트 커버리지 낮음 | 일부 모듈만 | pytest 기반 체계적 테스트 |

---

## 15. 부록: 모듈별 상세 API 명세

### 15.1 robo-data-fabric (데이터 패브릭)

```
GET    /datasources/types                     # 지원 DB 타입 목록
GET    /datasources/supported-engines         # 메타데이터 추출 지원 엔진
GET    /datasources                           # 데이터소스 목록
POST   /datasources                           # 데이터소스 생성
GET    /datasources/{name}                    # 데이터소스 조회
DELETE /datasources/{name}                    # 삭제
PUT    /datasources/{name}/connection         # 연결 정보 업데이트
GET    /datasources/{name}/health             # 헬스체크
POST   /datasources/{name}/test               # 연결 테스트
GET    /datasources/{name}/schemas            # 스키마 목록
GET    /datasources/{name}/tables             # 테이블 목록
GET    /datasources/{name}/tables/{t}/schema  # 테이블 스키마
GET    /datasources/{name}/tables/{t}/sample  # 샘플 데이터
POST   /datasources/{name}/extract-metadata   # 메타데이터 추출 (SSE 스트리밍)
POST   /query                                 # SQL 쿼리 실행
GET    /query/status                          # MindsDB 상태
POST   /query/materialized-table              # 물리화 테이블 생성
GET    /query/models                          # ML 모델 목록
GET    /query/jobs                            # 스케줄 작업
GET    /query/knowledge-bases                 # 지식 베이스
```

### 15.2 robo-data-text2sql (NL2SQL)

```
POST   /text2sql/ask                          # 단순 질의
POST   /text2sql/react                        # ReAct 스트리밍 (NDJSON)
POST   /text2sql/meta/tables                  # 테이블 검색
GET    /text2sql/meta/tables/{t}/columns      # 컬럼 조회
GET    /text2sql/meta/datasources             # 데이터소스 목록
PUT    /text2sql/schema-edit/tables/{t}/description    # 설명 수정
POST   /text2sql/schema-edit/relationships    # FK 관계 추가/삭제
POST   /text2sql/feedback                     # SQL 피드백
GET    /text2sql/history                      # 쿼리 이력 (페이지네이션)
POST   /text2sql/cache/enum/extract/{s}/{t}/{c}  # Enum 추출
POST   /text2sql/cache/mapping                # 값 매핑
GET    /text2sql/cache/similar-query          # 유사 쿼리
POST   /text2sql/direct-sql                   # SQL 직접 실행
POST   /text2sql/direct-sql/stream            # SQL 스트리밍
POST   /text2sql/direct-sql/materialized-view # View 생성
GET/POST/PUT/DELETE /text2sql/events/rules/*  # 이벤트 룰 CRUD
POST   /text2sql/events/scheduler/start|stop  # 스케줄러
GET    /text2sql/events/stream/alarms         # SSE 알람
POST   /text2sql/watch-agent/chat             # 감시 에이전트
```

### 15.3 process-gpt-completion (BPM 코어)

```
POST   /completion/complete                   # LLM 완성
POST   /completion/vision-complete            # 비전 모델
GET    /completion/set-tenant                 # 테넌트 설정
POST   /process/submit                        # 워크아이템 제출
POST   /process/initiate                      # 프로세스 시작
GET    /process/feedback                      # 피드백 조회
GET    /process/feedback-diff                 # 피드백 차이
GET    /process/rework-activities             # 재작업 활동
POST   /process-chat/define                   # NL → 프로세스 정의
POST   /process-chat/complete                 # 프롬프트 완성
POST   /multi-agent/chat                      # 에이전트 메시지
POST   /mcp/config                            # MCP 설정
POST   /mcp/execute-tool                      # MCP 도구 실행
GET    /complete-callbot/caller-info          # 콜봇 발신자 정보
GET    /complete-callbot/user-todolist        # 콜봇 할일 목록
```

### 15.4 data-platform-olap (OLAP)

```
POST   /api/schema/upload                     # Mondrian XML 업로드
POST   /api/schema/upload-text                # XML 텍스트 업로드
DELETE /api/cube/{name}                       # 큐브 삭제
GET    /api/cubes                             # 큐브 목록
GET    /api/cube/{name}/metadata              # 메타데이터
POST   /api/pivot/query                       # 피벗 쿼리 실행
POST   /api/nl2sql                            # 자연어 Text2SQL
POST   /api/pivot/drill-down                  # 드릴다운
POST   /api/pivot/drill-up                    # 드릴업
```

---

## 부록: 엔터프라이즈 데이터허브 매핑

### 사업 도메인 분류 (범용 예시)

| 도메인 | 데이터 소스 | 주요 시스템 |
|--------|------------|------------|
| **운영** | ERP, SCM, MES | 공급망 분석, 생산 공정 |
| **재무** | 회계 시스템, 재무 데이터웨어하우스 | 재무 분석, 예측 |
| **고객** | CRM, 고객 행동 데이터 | 고객 분석, 이탈 예측 |

### 데이터 흐름 (엔터프라이즈 일반)

```
[데이터허브 포탈] ─── 공통 진입점 (기존 유지)
       │
       ├─ 메타데이터 관리: OMD와 동일 I/F, BUT 저장은 Graph DB 온톨로지형
       │
       ├─ 수집 DB (피지컬 레이어)
       │   ├─ 실시간 IoT/센서 → Kafka → DT/AI 전달
       │   └─ 전사 DB → ETL → 데이터 적재
       │
       ├─ ODS (도메인 레이어)
       │   ├─ 실시간 데이터 → Kafka → GPU DB 적재
       │   ├─ 운영 부문: ERP, SCM, MES 시스템
       │   ├─ 재무 부문: 회계, 재무 분석 시스템
       │   └─ 고객 부문: CRM, 행동 분석 시스템
       │
       └─ 분석DB (다이나믹 레이어)
           ├─ 비즈니스 분석용 의사결정지원 테이블
           ├─ OLAP (Mondrian XML + Star Schema)
           └─ Star Schema / Data Mart 생성 지원
```

### ETL DAG 예시 (Apache Airflow)

```python
# data-platform-olap-main/airflow/dags/etl_operational_analysis.py
# 운영 데이터 분석 DAG
# etl_business_metrics_analysis.py
# 비즈니스 지표 분석 DAG
```

---

## 요약

| 항목 | 값 |
|------|-----|
| **프로젝트명** | K-AIR + Process-GPT (통합 AI 플랫폼) |
| **총 저장소** | **18개** |
| **주요 모듈** | 프레젠테이션(3) + 비즈니스(3) + 에이전트(7) + 데이터(3) + 인프라(2) |
| **총 API** | **150+ 엔드포인트** |
| **핵심 기술** | FastAPI, Vue3, LangChain, CrewAI, Neo4j, Supabase, MindsDB |
| **LLM 통합** | GPT-4o, Claude, Gemini, Ollama (4개 프로바이더) |
| **에이전트 프레임워크** | CrewAI + A2A SDK + MCP + Mem0 |
| **데이터베이스** | Supabase(PG+pgvector) + Neo4j(Graph+Vector) + MindsDB |
| **실시간** | WebSocket + SSE + Supabase Realtime + Yjs CRDT |
| **인프라** | Kubernetes + Docker Compose + Apache Airflow |
| **설계 철학** | 자연언어 중심 + 에이전트 자동화 + HITL 신뢰도 + 온톨로지 지식그래프 |
