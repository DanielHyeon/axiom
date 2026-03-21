# Axiom

AI-powered Business Process Intelligence Platform.

레거시 시스템 위에 의미 계층(Semantic Layer)을 구축하여, 의사결정자와 분석가에게 프로세스 인텔리전스를 제공합니다.

## Services

| Service | Port | Description |
|---------|------|-------------|
| **Core** | 8002 | Business process orchestration, agent framework |
| **Vision** | 8000 | OLAP analytics, what-if simulation, root cause analysis |
| **Weaver** | 8001 | Metadata fabric, data source integration |
| **Oracle** | 8004 | NL2SQL engine, query generation |
| **Synapse** | — | Process mining, knowledge graph, ontology |
| **Canvas** | 5173 | React/TypeScript frontend UI |

## Quick Start

```bash
docker-compose up -d
```

Canvas: http://localhost:5173

## Documentation

- [docs/](docs/README.md) — 프로젝트 전체 문서 (아키텍처, 구현계획, 상태추적 등)
- [services/core/docs/](services/core/docs/) — Core 서비스 설계 문서
- [services/oracle/docs/](services/oracle/docs/) — Oracle 서비스 설계 문서
- [services/synapse/docs/](services/synapse/docs/) — Synapse 서비스 설계 문서
- [services/vision/docs/](services/vision/docs/) — Vision 서비스 설계 문서
- [services/weaver/docs/](services/weaver/docs/) — Weaver 서비스 설계 문서
- [canvas/docs/](canvas/docs/) — Canvas 프론트엔드 설계 문서

## Tech Stack

- **Backend:** Python, FastAPI, LangGraph, Redis Streams
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, shadcn/ui
- **Database:** PostgreSQL, Neo4j, Redis
- **Infrastructure:** Docker, Kubernetes

## Todo

- **테넌트+업무:** 회사구분 + 업무(프로세스) 구분 되어야 함
- **업무연결:** 업무(프로세스)간 연결하여 온톨로지 분석 및 What if 분석이 되어야함
- **버전관리:** 업무(프로세스)데이터의 버전 관리 기능 추가 되어야 함
- **버전저장:** 버전이 계속 변경되고 이것을 저장되고 버전닝 되어야 함. 리믹스 및 추가 불러오기, 되돌리기 기능 있어야함 
- **버전파생:** 버전 파생 기능, 리믹스 및 새로 불러오기, 되돌리기 기능 있어야함 
