# Architecture

크로스서비스 아키텍처 원칙과 설계 문서입니다.

## Documents

| Document | Description |
|----------|-------------|
| [semantic-layer.md](semantic-layer.md) | Semantic Layer 아키텍처 — Weaver/Synapse/Vision 책임 경계 정의 |
| [4source-ingestion.md](4source-ingestion.md) | 4-Source Ingestion — RDBMS, Legacy Code, Docs/Audio, External API 통합 파이프라인 |
| [self-verification.md](self-verification.md) | Self-Verification — 20% 샘플링 자동검증, 회귀 테스트, HITL 피드백 루프 |
| [adr-event-sourcing-evaluation.md](adr-event-sourcing-evaluation.md) | ADR: Event Sourcing 평가 — No-Go 결정, PoC 코드 보존 (DDD-P3-02) |

## DDD Architecture Overview

DDD Phase 0-3 구현 완료 (2026-02). 전체 구현 상세는 `docs/03_implementation/program/14~18` 문서 참조.

### Event-Driven Architecture

- **Transactional Outbox Pattern**: 4개 서비스(Core, Synapse, Vision, Weaver) 각각 `EventOutbox` 테이블 + Relay Worker 운영
- **Redis Streams Topology**: `axiom:core:events`, `axiom:synapse:events`, `axiom:vision:events`, `axiom:weaver:events`, `axiom:watches`, `axiom:workers`
- **Event Contract Registry**: 16개 도메인 이벤트 (Core 8 + Synapse 4 + Vision 2 + Weaver 2), 각 서비스에 `event_contract_registry.py`
- **Consumer-Driven Contract Testing**: 42개 JSON 스키마 (16 producer + 26 consumer) + CI 자동 검증

### Domain Model

- **Rich Aggregate**: WorkItem 상태 머신 (`TODO → IN_PROGRESS → SUBMITTED → DONE/REWORK/CANCELLED`), 낙관적 동시성(version)
- **Modular Monolith**: Core 서비스 `modules/{process,agent,case,watch}/` 각각 `domain/`, `application/`, `infrastructure/`, `api/` 레이어
- **DB Schema Isolation**: 5개 서비스별 PostgreSQL 스키마 (core, synapse, vision, weaver, oracle)

### Cross-Cutting Patterns

- **Anti-Corruption Layers**: OracleSynapseACL (431줄), OracleWeaverACL (119줄), Core SynapseACL (299줄), Vision CoreClient (164줄)
- **Saga Orchestrator**: 정방향 실행 + 자동 보상 + DB 영속화 (`saga_orchestrator.py` 346줄)
- **Dead Letter Queue**: `EventDeadLetter` DB 테이블 + Admin API (list/retry/discard) + Prometheus 메트릭 11종
- **CQRS**: Vision 서비스 `VISION_CQRS_MODE` (shadow/primary/standalone)

## Service-Level Architecture

각 서비스의 상세 아키텍처는 서비스별 docs에 있습니다:

- [Core Architecture](../../services/core/docs/01_architecture/)
- [Oracle Architecture](../../services/oracle/docs/01_architecture/)
- [Synapse Architecture](../../services/synapse/docs/01_architecture/)
- [Vision Architecture](../../services/vision/docs/01_architecture/)
- [Weaver Architecture](../../services/weaver/docs/01_architecture/)
- [Canvas Architecture](../../apps/canvas/docs/01_architecture/)
