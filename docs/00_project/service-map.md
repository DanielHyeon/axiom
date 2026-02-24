# Service Map

## Service Topology

```
                    ┌─────────────┐
                    │   Canvas    │ :5173
                    │  (Frontend) │
                    └──────┬──────┘
                           │ HTTP
              ┌────────────┼────────────┐
              │            │            │
      ┌───────▼──┐  ┌─────▼────┐  ┌───▼───────┐
      │  Core    │  │  Vision  │  │  Weaver   │
      │  :8002   │  │  :8000   │  │  :8001    │
      └───┬──────┘  └──────────┘  └───────────┘
          │
    ┌─────▼────┐  ┌───────────┐
    │  Oracle  │  │  Synapse  │
    │  :8004   │  │  (worker) │
    └──────────┘  └───────────┘
```

## Port Table

| Service | Container Port | Host Port (Local) | Base URL |
|---------|---------------:|------------------:|----------|
| PostgreSQL | 5432 | 5432 | `postgresql://localhost:5432/insolvency_os` |
| Core | 8002 | 8002 | `http://localhost:8002` |
| Vision | 8000 | 8000 | `http://localhost:8000` |
| Weaver | 8001 | 8001 | `http://localhost:8001` |
| Oracle | 8004 | 8004 | `http://localhost:8004` |
| Canvas | 80 | 5173 | `http://localhost:5173` |
| Redis | 6379 | 6379 | `redis://localhost:6379` |

## Inter-Service Communication

- **Canvas → Core/Vision/Weaver/Oracle**: HTTP REST (직접 호출)
- **Core ↔ Services**: Redis Streams 이벤트 버스 (비동기)
- **All Services → PostgreSQL**: 직접 DB 연결 (서비스별 스키마 격리)
- **Synapse/Oracle/Weaver → Neo4j**: 지식 그래프 저장소

## References

- [Service Endpoints SSOT](../02_api/service-endpoints-ssot.md) — 상세 엔드포인트 정보
- `docker-compose.yml` — 로컬 배포 프로파일
- `k8s/` — Kubernetes 매니페스트
