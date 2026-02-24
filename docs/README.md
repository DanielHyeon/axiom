# Axiom Documentation

프로젝트 전체 문서의 마스터 인덱스입니다.

## Directory Structure

| Directory | Description |
|-----------|-------------|
| [00_project/](00_project/README.md) | 프로젝트 개요, 서비스 토폴로지 |
| [01_architecture/](01_architecture/README.md) | 크로스서비스 아키텍처 (Semantic Layer, Ingestion, Verification) |
| [02_api/](02_api/README.md) | API 레지스트리 & 서비스 엔드포인트 SSOT |
| [03_implementation/](03_implementation/README.md) | 구현 계획 (프로그램 + 6개 서비스별) |
| [04_status/](04_status/README.md) | Gap 분석 & 구현 상태 추적 |
| [05_backlog/](05_backlog/README.md) | 로드맵 & 백로그 |
| [06_governance/](06_governance/README.md) | 거버넌스, 정책, 도메인 계약 |
| [07_research/](07_research/README.md) | 리서치 자료 (K-AIR 분석, AI 아키텍처) |
| [99_archive/](99_archive/README.md) | 아카이브 (대체된 문서) |

## Numbering Convention

`00`~`08` 카테고리 넘버링은 서비스별 문서(`services/*/docs/`)의 체계와 동일합니다:

```
00 = overview/project    05 = LLM
01 = architecture        06 = governance (data at service level)
02 = API                 07 = research (security at service level)
03 = implementation      08 = operations
04 = status              99 = archive/decisions
```

## Service-Level Documentation

각 서비스는 자체 `/docs/` 디렉토리에 상세 설계 문서를 보유합니다:

- [services/core/docs/](../services/core/docs/) — Core (process orchestration, agents)
- [services/oracle/docs/](../services/oracle/docs/) — Oracle (NL2SQL, query engine)
- [services/synapse/docs/](../services/synapse/docs/) — Synapse (process mining, ontology)
- [services/vision/docs/](../services/vision/docs/) — Vision (OLAP, what-if, root cause)
- [services/weaver/docs/](../services/weaver/docs/) — Weaver (metadata fabric, adapters)
- [apps/canvas/docs/](../apps/canvas/docs/) — Canvas (React frontend)
