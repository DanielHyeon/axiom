# Axiom Vision - 시스템 개요

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **작성 근거**: K-AIR 역설계 분석 보고서 v2.0, ADR-001~005

---

## 이 문서가 답하는 질문

- Axiom Vision은 무엇이며 왜 필요한가?
- 3대 핵심 엔진(What-if, OLAP, See-Why)은 각각 어떤 역할을 하는가?
- 비즈니스 프로세스 인텔리전스에서 Vision이 해결하는 문제는 무엇인가?
- Vision 모듈의 기술 스택과 다른 Axiom 모듈과의 관계는?

---

## 1. 모듈 정체성

| 항목 | 값 |
|------|-----|
| **모듈명** | Axiom Vision |
| **컨셉** | 데이터를 분석해 미래를 내다보는 통찰력 |
| **역할** | What-if 시뮬레이션, 프로세스 시뮬레이션, OLAP 피벗 분석, 통계 대시보드, 근본원인 분석 |
| **기술 스택** | FastAPI + scipy.optimize + Mondrian XML + DoWhy + Recharts |
| **서비스 포트** | 8400 (기본값) |
| **의존 모듈** | Axiom Core (인증/라우팅), Axiom Canvas (프론트엔드), Axiom Synapse (프로세스 마이닝 데이터), PostgreSQL |

### 1.1 왜 Vision인가?

비즈니스 프로세스 인텔리전스에서 **"과거 데이터를 보는 것(Seeing)"** 을 넘어 **"미래를 내다보는 것(Vision)"** 이 핵심 가치다.

- **비즈니스 전략 수립**: 시나리오 비교 없이는 최적 전략을 찾을 수 없다
- **의사결정권자 보고**: OLAP 통계로 비즈니스 현황, 성과 분석, KPI 추이를 즉시 산출해야 한다
- **근본 원인 분석(Root Cause Analysis)**: 비즈니스 문제의 체계적 분석이 필수이다

---

## 2. 3대 핵심 엔진

```
┌─────────────────────────────────────────────────────────────────┐
│                      Axiom Vision                                │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  What-if 엔진    │  │  OLAP 엔진       │  │  See-Why     │  │
│  │  ──────────────  │  │  ──────────────   │  │  엔진        │  │
│  │  시나리오 솔버   │  │  피벗 쿼리 생성  │  │  ────────    │  │
│  │  민감도 분석     │  │  큐브 관리       │  │  인과 추론   │  │
│  │  전환점 탐색     │  │  NL→피벗         │  │  반사실 분석 │  │
│  │  (scipy)         │  │  ETL 동기화      │  │  SHAP 시각화 │  │
│  │                  │  │  (Mondrian)       │  │  (DoWhy)     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  통계 대시보드 (Analytics Dashboard)                      │   │
│  │  3개 엔진의 결과를 통합하는 시각화 레이어                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 What-if 시뮬레이션 엔진

| 항목 | 내용 |
|------|------|
| **해결 문제** | "비용 구조를 20% 개선하면 수익성이 어떻게 변할까?" |
| **핵심 기술** | scipy.optimize (constrained optimization) |
| **구현 상태** | 0% (신규 개발) |
| **Phase** | Phase 3.2 |
| **예상 공수** | ~15일 (BE 8일, FE 7일) |

**주요 기능**:
- 비즈니스 시나리오 비교: 성장/유지/축소 전략, 비용 변동, 자산 매각 조합
- 제약조건 기반 최적화: 최소 수익률, 운영자금 확보 등 제약 충족
- 토네이도 차트: 각 파라미터의 민감도 시각화
- 전환점 분석: "성장률이 몇 %에서 전략이 실패하는가?"
- 최적 시나리오 추천: 실현가능성 + 이해관계자 만족도 최대화
- **프로세스 시간축 시뮬레이션**: Synapse 프로세스 마이닝 데이터 기반으로 활동 소요시간 변경/자원 배분 변경 시 전체 주기 시간 영향을 시뮬레이션 ("승인 프로세스를 4시간→2시간으로 단축하면 전체 주기 시간은?")

### 2.2 OLAP 피벗 분석 엔진

| 항목 | 내용 |
|------|------|
| **해결 문제** | "2024년 제조업 비즈니스의 이해관계자별 성과 분석은?" |
| **핵심 기술** | Mondrian XML 큐브 + PostgreSQL Materialized View |
| **이식 원본** | K-AIR data-platform-olap-main (80% 구현) |
| **Phase** | Phase 3.6 |
| **예상 공수** | ~22일 (DW 4일, BE 10일, FE 8일) |

**주요 기능**:
- 비즈니스 분석 큐브: 비즈니스 유형/대상 조직/시간/이해관계자 차원, 건수/금액/KPI 측도
- 현금흐름 큐브: 비즈니스/대상 조직/회계연도 차원, 금액/성장률/예측정확도 측도
- 자연어 질의: LLM이 자연어를 피벗 쿼리로 변환 (LangGraph 워크플로우)
- 드릴다운/드릴스루: 집계 → 상세 → 원본 레코드 탐색
- ETL 동기화: OLTP → OLAP Materialized View 갱신 (full/incremental)

### 2.3 See-Why 근본원인 분석 엔진

| 항목 | 내용 |
|------|------|
| **해결 문제** | "이 조직의 비즈니스 실패 근본 원인은 무엇인가?" |
| **핵심 기술** | DoWhy + PC Algorithm + LiNGAM + SHAP |
| **구현 상태** | 20% (K-AIR에 데모 수준) |
| **Phase** | Phase 4 (출시 후) |
| **예상 공수** | ~25일 (엔진 12일, 데이터 8일, UI 5일) |

**주요 기능**:
- 인과 그래프 구축: 관측 데이터에서 PC Algorithm / LiNGAM으로 인과 구조 탐색
- 케이스별 근본원인 추출: 비즈니스 실패로부터 역추적, 상위 3~5개 원인 도출
- 반사실 시나리오: "비용 구조를 20% 개선하면 수익성이 어떻게 변할까?"
- SHAP 값 시각화: 각 요인의 최종 결과 기여도
- LLM 설명 생성: 인과 체인을 서술문으로 변환 (분석 보고서 연동)

**의존성**: 과거 종결 사건 100건 이상의 라벨링된 데이터 필요

---

## 3. 비즈니스 프로세스 인텔리전스 적용

### 3.1 Vision이 지원하는 업무 시나리오

| 시나리오 | 사용 엔진 | 사용자 | 예시 질의 |
|----------|----------|--------|----------|
| 비즈니스 전략 수립 | What-if | 프로세스 분석가 | "비용 10% 절감 시 수익률 개선 가능한가?" |
| 비즈니스 통계 보고 | OLAP | 의사결정권자, 프로세스 분석가 | "2024년 부서별 비즈니스 건수와 평균 처리 기간" |
| 이해관계자 분석 | OLAP | 이해관계자(Stakeholder), 프로세스 분석가 | "핵심 이해관계자 vs 일반 이해관계자 성과 비교" |
| KPI 민감도 | What-if | 프로세스 분석가 | "비용 1% 상승 시 KPI 변화량" |
| 근본 원인 분석(Root Cause Analysis) | See-Why | 분석가 | "이 조직의 성과 저하 근본 원인 3가지" |
| 반사실 검증 | See-Why | 의사결정권자 | "비용 구조를 개선했다면 실패를 피할 수 있었는가?" |
| 현금흐름 예측 | OLAP + What-if | 프로세스 분석가 | "3년차 현금 잔고 예측과 투자 가능액" |
| 프로세스 시간 시뮬레이션 | What-if | 프로세스 분석가 | "승인 프로세스를 4시간→2시간 단축하면 전체 주기 시간은?" |
| 프로세스 병목 원인 분석 | See-Why | 분석가 | "왜 배송 프로세스가 느려지고 있는가?" |
| 프로세스 KPI 통계 | OLAP | 의사결정권자 | "부서별 평균 처리 시간과 SLA 위반율" |

### 3.2 도메인 용어 정리 (Glossary)

| 용어 | 영문 | 정의 |
|------|------|------|
| 성과 지표 | KPI (Key Performance Indicator) | 핵심 비즈니스 목표 대비 실제 달성 비율 |
| 이해관계자 성과 | Stakeholder Performance | 이해관계자가 실제 달성한 성과 / 목표 성과 |
| EBITDA | EBITDA | 이자, 세금, 감가상각 전 영업이익 |
| 큐브 | Cube | OLAP에서 다차원 데이터 집합체 |
| 피벗 | Pivot | 데이터를 행/열/값으로 재구성하는 분석 |
| 프로세스 마이닝 | Process Mining | 이벤트 로그에서 실제 프로세스 흐름을 추출/분석하는 기법 |
| 주기 시간 | Cycle Time | 프로세스 시작부터 종료까지의 전체 소요 시간 |
| 프로세스 변형 | Process Variant | 동일 프로세스의 서로 다른 실행 경로 |
| 병목 | Bottleneck | 전체 프로세스 처리량을 제한하는 활동 또는 단계 |
| SLA | Service Level Agreement | 서비스 수준 합의 (목표 처리 시간 등) |

---

## 4. 시스템 위치 (Axiom Series 내)

```
┌─ Axiom Canvas ──────────────────────────────────────────────────┐
│  React 18 + Shadcn/ui                                            │
│  ├─ What-if 시나리오 빌더 ──────┐                               │
│  ├─ OLAP 피벗 테이블 ──────────┤── HTTP ──→ Axiom Vision        │
│  └─ 근본원인 분석 뷰어 ────────┘                               │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼ HTTP (JWT 인증)
┌─ Axiom Core ────────────────────────────────────────────────────┐
│  API Gateway + 인증 + 라우팅                                     │
│  /api/v3/cases/{case_id}/what-if/*  ──→  Vision                 │
│  /api/v3/cases/{case_id}/pivot/*    ──→  Vision                 │
│  /api/v3/cases/{case_id}/root-cause/* ──→ Vision                │
└──────────────────────────────────────────────────────────────────┘
         │
         ▼ HTTP (내부)
┌─ Axiom Vision ──────────────────────────────────────────────────┐
│  FastAPI (포트 8400)                                             │
│  ├─ What-if 엔진 (scipy.optimize)                               │
│  │   └─ 프로세스 시간축 시뮬레이션 (Synapse 연동)               │
│  ├─ OLAP 엔진 (Mondrian XML + SQL)                              │
│  │   └─ 프로세스 KPI 큐브 (Synapse 프로세스 데이터)             │
│  ├─ See-Why 엔진 (DoWhy) [Phase 4]                              │
│  │   └─ 프로세스 병목 인과 분석 (Synapse 병목 데이터)           │
│  └─ Analytics 집계                                               │
└──────────────────────────────────────────────────────────────────┘
         │                              │
         ▼ SQL                          ▼ REST API
┌─ PostgreSQL 15 ─────────────┐  ┌─ Axiom Synapse ──────────────┐
│  ├─ what_if_scenarios        │  │  프로세스 마이닝 엔진         │
│  ├─ scenario_results         │  │  ├─ 프로세스 모델/의존 그래프 │
│  ├─ Materialized Views       │  │  ├─ 활동별 소요시간 통계     │
│  │  (팩트/디멘전)            │  │  ├─ 병목 탐지 결과           │
│  ├─ causal_graphs [Phase 4]  │  │  ├─ 프로세스 변형 데이터     │
│  └─ 기존 Axiom 테이블       │  │  └─ 프로세스 KPI 시계열      │
│     (cases, organizations,   │  └────────────────────────────────┘
│      assets, stakeholders)   │
└──────────────────────────────┘
```

### 4.1 모듈 간 통신 규칙

| 방향 | 허용 | 금지 |
|------|------|------|
| Canvas → Vision | REST API (Core 경유) | 직접 접근 |
| Core → Vision | REST API (내부) | - |
| Vision → Core | Event Outbox (비동기) | 동기 호출 |
| Vision → Oracle | REST API (NL→SQL 위임) | 직접 import |
| Vision → PostgreSQL | SQLAlchemy (직접) | - |
| Vision → Synapse | REST API (온톨로지 조회, 프로세스 마이닝 데이터) | 직접 import |

---

## 5. 구현 로드맵

```
Phase 3.2 (최적화기 이후)
  │  What-if 시뮬레이션 (15일)
  │  ├─ BE: 시나리오 솔버 + 비교 엔진 (8일)
  │  └─ FE: 시나리오 빌더 + 토네이도 차트 (7일)
  ▼
Phase 3.6 (Text2SQL과 병렬 가능)
  │  OLAP 분석 (22일)
  │  ├─ DW 설계 + 큐브 정의 (4일)
  │  ├─ 피벗 엔진 + API (10일)
  │  └─ 피벗 UI (8일)
  ▼
Phase 4 (출시 후)
  │  See-Why 근본원인 분석 (25일)
  │  ├─ 데이터 수집 + 라벨링 (8일)
  │  ├─ 인과 추론 엔진 (12일)
  │  └─ 설명 UI + 보고서 연동 (5일)
```

| Phase | 기능 | 우선순위 | 공수 | 의존성 |
|-------|------|:--------:|:----:|--------|
| 3.2 | What-if 시뮬레이션 | P0 | 15일 | Phase 3 최적화기 |
| 3.6 | OLAP 분석 | P1 | 22일 | Phase 2 현금흐름 테이블 |
| 4 | See-Why 근본원인 | P2 | 25일 | 과거 데이터 100건+ |

**총 예상 공수**: ~62일 (2인 기준 약 1.5개월)

---

## 6. K-AIR 이식 매핑

| K-AIR 원본 | Vision 이식 대상 | 작업 내용 |
|------------|-----------------|----------|
| `data-platform-olap-main/xml_parser.py` | `vision/app/engines/mondrian_parser.py` | Mondrian XML 파서 이식 |
| `data-platform-olap-main/sql_generator.py` | `vision/app/engines/pivot_engine.py` | SQL 생성기 이식 |
| `data-platform-olap-main/` LangGraph 워크플로우 | `vision/app/engines/` NL→피벗 | 5노드 워크플로우 이식 |
| (신규) | `vision/app/engines/scenario_solver.py` | scipy 기반 시나리오 솔버 |
| (신규) | `vision/app/engines/causal_engine.py` | DoWhy 인과 추론 엔진 |

---

## 7. 설정 기본값

| 설정 키 | 기본값 | 설명 |
|---------|--------|------|
| `VISION_PORT` | 8400 | Vision 서비스 포트 |
| `DATABASE_URL` | (필수) | PostgreSQL 연결 문자열 |
| `OPENAI_MODEL` | gpt-4o | NL→피벗 변환용 LLM 모델 |
| `QUERY_TIMEOUT` | 30 | 쿼리 타임아웃 (초) |
| `MAX_ROWS` | 1000 | 단일 쿼리 최대 반환 행 수 |
| `SCENARIO_SOLVER_TIMEOUT` | 60 | 시나리오 솔버 타임아웃 (초) |
| `ETL_SYNC_INTERVAL` | 3600 | ETL 동기화 주기 (초, 기본 1시간) |
| `CAUSAL_MIN_CONFIDENCE` | 0.70 | 인과 연결 보고 최소 신뢰도 |
| `REDIS_URL` | (선택) | Redis 캐시 연결 (OLAP 캐싱) |
| `REDIS_CACHE_TTL` | 3600 | Redis 캐시 TTL (초) |

<!-- affects: 01_architecture, 02_api, 05_llm, 08_operations -->
<!-- requires-update: 01_architecture/architecture-overview.md, 01_architecture/what-if-engine.md, 01_architecture/root-cause-engine.md, 01_architecture/olap-engine.md -->
