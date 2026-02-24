# Axiom Project Overview

## Mission

레거시 시스템의 데이터를 AI 친화적 의미 계층으로 변환하여, 비즈니스 프로세스 인텔리전스를 제공하는 플랫폼.

## Architecture

Axiom은 6개의 마이크로서비스와 1개의 프론트엔드로 구성됩니다:

- **Core** — 비즈니스 프로세스 오케스트레이션, AI 에이전트 프레임워크
- **Vision** — OLAP 분석, What-if 시뮬레이션, Root Cause 분석
- **Weaver** — 메타데이터 패브릭, 데이터소스 통합, 스키마 인트로스펙션
- **Oracle** — NL2SQL 엔진, 자연어 쿼리 → SQL 변환
- **Synapse** — 프로세스 마이닝, 지식 그래프, 4-레이어 온톨로지
- **Canvas** — React/TypeScript 프론트엔드 UI

서비스 간 통신은 Redis Streams 이벤트 버스를 통해 이루어집니다.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, LangGraph |
| Frontend | React 18, TypeScript, Vite, Tailwind v4, shadcn/ui |
| Database | PostgreSQL, Neo4j (knowledge graph), Redis (cache/event bus) |
| AI/LLM | OpenAI GPT-4o, LangChain, LangGraph |
| Infra | Docker Compose (local), Kubernetes (production) |

## Related Documents

- [Service Map](service-map.md) — 서비스 토폴로지 & 포트 정보
- [Architecture](../01_architecture/README.md) — 크로스서비스 아키텍처
- [Implementation Plans](../03_implementation/README.md) — 구현 계획
