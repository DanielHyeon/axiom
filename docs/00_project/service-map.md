# Service Map

## Service Topology

```text
                    ┌─────────────┐
                    │   Canvas    │ :5174 (host)
                    │  (Frontend) │
                    └──────┬──────┘
                           │ HTTP
              ┌────────────┼────────────┐
              │            │            │
      ┌───────▼──┐  ┌─────▼────┐  ┌───▼───────┐
      │  Core    │  │  Vision  │  │  Weaver   │
      │  :8002   │  │  :8100   │  │  :8001    │
      └───┬──────┘  └──────────┘  └───────────┘
          │              │
    ┌─────▼────┐  ┌──────▼────┐
    │  Oracle  │  │  Synapse  │
    │  :8004   │  │  :8003    │
    └──────────┘  └───────────┘

    Infrastructure:
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Postgres │  │  Redis   │  │  Neo4j   │
    │ :15432   │  │ :16379   │  │ :17474   │
    └──────────┘  └──────────┘  └──────────┘
```

## Port Table

| Service | Container Port | Host Port (Local) | Base URL |
|---------|---------------:|------------------:|----------|
| PostgreSQL | 5432 | 15432 | `postgresql://localhost:15432/insolvency_os` |
| Redis | 6379 | 16379 | `redis://localhost:16379` |
| Neo4j (HTTP) | 7474 | 17474 | `http://localhost:17474` |
| Neo4j (Bolt) | 7687 | 17687 | `bolt://localhost:17687` |
| Core | 8002 | 8002 | `http://localhost:8002` |
| Synapse | 8003 | 8003 | `http://localhost:8003` |
| Vision | 8000 | 8100 | `http://localhost:8100` |
| Weaver | 8001 | 8001 | `http://localhost:8001` |
| Oracle | 8004 | 8004 | `http://localhost:8004` |
| Canvas | 80 | 5174 | `http://localhost:5174` |

## DB Schema Isolation

단일 PostgreSQL 인스턴스(`insolvency_os`) 내 서비스별 스키마 격리:

| Schema | Owner Service | 주요 테이블 |
|--------|:------------:|-------------|
| `core` | Core | `event_outbox`, `bpm_work_item`, `bpm_process_definition`, `event_dead_letter`, `saga_execution_log`, `watch_*`, `core_case*` |
| `synapse` | Synapse | `event_outbox`, `schema_edit_*` |
| `vision` | Vision | `event_outbox`, `case_summary` (CQRS Read Model) |
| `weaver` | Weaver | `event_outbox`, `metadata_*` |
| `oracle` | Oracle | `query_history_*` |

## Inter-Service Communication

- **Canvas → Core/Vision/Weaver/Oracle**: HTTP REST (직접 호출)
- **Core ↔ Services**: Redis Streams 이벤트 버스 (비동기, Transactional Outbox 패턴)
- **All Services → PostgreSQL**: 직접 DB 연결 (서비스별 스키마 격리)
- **Synapse → Neo4j**: 지식 그래프 저장소 (Primary Owner)
- **Oracle/Weaver → Synapse**: ACL(Anti-Corruption Layer) 경유 Neo4j 간접 접근

## Redis Streams Topology

```text
axiom:core:events     → synapse_group, vision_group, watch_group
axiom:synapse:events  → weaver_group, oracle_group, core_group, vision_group
axiom:vision:events   → core_group, canvas_group
axiom:weaver:events   → synapse_group, oracle_group
axiom:watches         → watch_cep_group (Core Watch Module)
axiom:workers         → worker_group (Core Agent Module)
axiom:dlq:events      → DLQ 모니터링 (Admin API)
```

## Event-Driven Architecture

- **Outbox + Relay**: 4개 서비스(Core, Synapse, Vision, Weaver) 각각 `EventOutbox` 테이블 + Relay Worker
- **Event Contract Registry**: 16개 도메인 이벤트, `enforce_event_contract()` 검증
- **Dead Letter Queue**: `EventDeadLetter` DB 테이블 + `axiom:dlq:events` Redis Stream + Admin API
- **Saga Orchestrator**: 정방향 실행 + 자동 보상 + DB 영속화

## References

- [Service Endpoints SSOT](../02_api/service-endpoints-ssot.md) — 상세 엔드포인트 정보
- [Architecture README](../01_architecture/README.md) — DDD 아키텍처 개요
- [Domain Contract Registry](../06_governance/domain-contract-registry.md) — 이벤트 계약 거버넌스
- `docker-compose.yml` — 로컬 배포 프로파일
