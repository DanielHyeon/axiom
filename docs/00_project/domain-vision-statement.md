# Axiom Domain Vision Statement

> **Version**: 1.0
> **Date**: 2026-02-24
> **Phase**: DDD-P0-04

---

## 1. Product Vision

Axiom은 **레거시 시스템의 비정형 프로세스를 AI 기반으로 구조화하고 최적화하는
Business Process Intelligence Platform**이다.

도산/회생 등 복잡한 법률 사무 도메인에서, 분산된 데이터를 통합하고
프로세스 마이닝 및 지식 그래프를 활용하여 업무 자동화와 의사결정 지원을 제공한다.

---

## 2. Core Domain: Business Process Intelligence Engine

Axiom의 핵심 차별화 요소이며, 가장 높은 DDD 투자가 집중되어야 하는 영역이다.

### 2.1 Core Service — Process Orchestration

- BPM 엔진을 통한 프로세스 라이프사이클 관리 (WorkItem, Case, Saga)
- AI Agent 오케스트레이션과 Human-in-the-Loop 협업 (LangGraph)
- Saga 기반 보상 트랜잭션으로 장기 프로세스 안정성 보장
- Transactional Outbox 패턴을 통한 이벤트 발행의 원자성 보장
- 도메인 이벤트 기반 서비스 간 통합 (Redis Streams)

### 2.2 Synapse Service — Process Intelligence

- 프로세스 마이닝을 통한 실제 프로세스 발견 / 적합도 검증 / 병목 분석
- 지식 그래프(Neo4j) 기반 도메인 온톨로지 자동 구축
- NER 기반 비정형 데이터 의미 추출 (법률 문서 → 구조화 데이터)
- 스키마 에디터를 통한 도메인 모델 시각화 및 편집

---

## 3. Supporting Domains

Core Domain의 가치를 증폭시키는 보조 도메인. 실용적 수준의 DDD 적용.

### 3.1 Vision — Analytics & Simulation

- KPI 대시보드 및 트렌드 분석 (분석 전용 읽기 모델)
- 이해관계자 분포 / 성과 추적
- 시뮬레이션 기반 시나리오 분석
- **BC 원칙**: Core 소유 데이터는 Core API를 통해서만 접근 (ACL 패턴)

### 3.2 Oracle — Natural Language Query

- 자연어 → SQL 변환을 통한 데이터 접근 민주화
- Weaver 메타데이터 기반 쿼리 컨텍스트 자동 구성
- 쿼리 이력 관리 및 학습

### 3.3 Weaver — Data Fabric

- 다중 데이터소스(PostgreSQL, MySQL, Oracle 등) 메타데이터 통합 패브릭
- 용어 사전(Glossary) 기반 비즈니스 의미 매핑
- 스냅샷 기반 스키마 변경 추적
- MindsDB 연동을 통한 AI/ML 쿼리 통합

---

## 4. Generic Domains

표준 구현으로 충분한 영역. 최소 DDD 투자.

### 4.1 Canvas — Presentation Layer

- React/TypeScript 기반 SPA (Vite)
- Core/Vision/Oracle API를 소비하는 순수 프레젠테이션 계층
- 도메인 로직 없음, API 계약에만 의존

### 4.2 Authentication & Authorization

- 표준 JWT 기반 인증/인가 (Core 서비스 내 Generic Subdomain)
- 테넌트 격리 (multi-tenancy) 지원
- RBAC (admin, staff, viewer)

---

## 5. Bounded Context Map

```
┌─────────────────────────────────────────────────────────┐
│                    CORE DOMAIN                          │
│  ┌─────────────┐          ┌─────────────────┐          │
│  │    Core      │ Events   │    Synapse       │          │
│  │ (Orchestr.) ├─────────►│ (Intelligence)   │          │
│  │             │◄─────────┤                  │          │
│  └──────┬──────┘ REST/gRPC └────────┬────────┘          │
│         │                           │                   │
└─────────┼───────────────────────────┼───────────────────┘
          │                           │
     ┌────┼────────────┬──────────────┼──────┐
     │    │ SUPPORTING  │             │      │
     ▼    ▼            ▼             ▼      │
┌─────────┐    ┌───────────┐    ┌─────────┐ │
│ Vision   │    │  Oracle    │    │ Weaver  │ │
│(Analytics│    │ (NL Query) │    │ (Fabric)│ │
│  ACL)    │    │            │    │         │ │
└─────────┘    └───────────┘    └─────────┘ │
     │              │                │       │
     └──────────────┼────────────────┘       │
                    │  GENERIC               │
               ┌────┴────┐                   │
               │ Canvas  │                   │
               │  (UI)   │                   │
               └─────────┘                   │
```

### Context 간 통합 패턴

| Upstream | Downstream | 패턴 | 채널 |
|----------|-----------|------|------|
| Core | Synapse | Published Language | Redis Streams (axiom:events) |
| Core | Vision | Open Host Service | REST API (/api/v1/cases/*) |
| Synapse | Core | Conformist | REST API (/api/synapse/*) |
| Core | Weaver | Separate Ways | 직접 의존 없음 |
| Weaver | Oracle | Customer-Supplier | REST API (/api/query) |
| Core, Vision, Oracle | Canvas | Open Host Service | REST API |

---

## 6. DDD Investment Guide

| Subdomain | 분류 | DDD 투자 수준 | 전술 패턴 | 우선순위 |
|-----------|------|:------------:|-----------|:-------:|
| **Core** | Core | **최고** | Aggregate, Domain Event, Saga, Repository, Outbox | P0 |
| **Synapse** | Core | **최고** | Domain Event, Entity, Value Object, Repository | P0 |
| **Vision** | Supporting | 중간 | ACL(Anti-Corruption Layer), Read Model, Service | P1 |
| **Oracle** | Supporting | 중간 | ACL, Service, Value Object | P2 |
| **Weaver** | Supporting | 중간 | Repository, Entity, Service | P1 |
| **Canvas** | Generic | 최소 | 없음 (API Consumer) | - |
| **Auth** | Generic | 최소 | 표준 JWT 라이브러리 활용 | - |

### 투자 수준 정의

- **최고**: 풍부한 도메인 모델, Aggregate Root 경계 설계, Domain Event 발행, Repository 패턴 적용, 도메인 전문가와 Ubiquitous Language 정립
- **중간**: ACL을 통한 BC 보호, Service 계층 정리, 기본 Entity/Value Object 구분, Core Domain과의 통합 계약 준수
- **최소**: 외부 라이브러리/프레임워크 활용, 도메인 모델 불필요, API 계약 준수만 확인

---

## 7. Ubiquitous Language (핵심 용어)

| 용어 | 정의 | 소유 BC |
|------|------|---------|
| **WorkItem** | 처리해야 할 개별 업무 단위 | Core |
| **Case** | 관련 WorkItem을 묶는 사건/절차 | Core |
| **Saga** | 장기 트랜잭션의 보상 흐름 | Core |
| **EventOutbox** | 트랜잭션 내 발행 보장을 위한 이벤트 임시 저장소 | Core |
| **MiningTask** | 프로세스 마이닝 실행 단위 | Synapse |
| **Ontology** | 도메인 개념 간 관계를 표현하는 지식 그래프 | Synapse |
| **DataSource** | Weaver가 관리하는 외부 데이터 연결 | Weaver |
| **Glossary** | 비즈니스 용어와 데이터 컬럼 간 매핑 | Weaver |
| **Tenant** | 멀티테넌시 격리 단위 | 전체 (Cross-cutting) |
