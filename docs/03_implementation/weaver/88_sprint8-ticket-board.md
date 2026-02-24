# WEAVER Sprint 8 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| WEAVER-S8-001 | Datasource API 1차 구현 (list/detail/health/test) | services/weaver/docs/02_api/datasource-api.md | WEAVER-S7-004 | 1.5d | backend-developer, api-developer | 데이터소스 조회/검증 경로 동작 |
| WEAVER-S8-002 | Datasource API 확장 (connection update/schemas/tables/sample) | services/weaver/docs/02_api/datasource-api.md | WEAVER-S8-001 | 1.5d | backend-developer | 스키마/테이블 탐색 동작 |
| WEAVER-S8-003 | Query API 1차 구현 (`/api/query`, `/status`) | services/weaver/docs/02_api/query-api.md | WEAVER-S7-004 | 1d | backend-developer | 쿼리 실행 및 상태 조회 동작 |
| WEAVER-S8-004 | Metadata Catalog API 1차 구현 (snapshots/search/stats) | services/weaver/docs/02_api/metadata-catalog-api.md | WEAVER-S7-004 | 2d | backend-developer, api-developer | 카탈로그 핵심 경로 동작 |
| WEAVER-S8-005 | Sprint8 리뷰 및 문서 상태 동기화 | docs/03_implementation/weaver/98_gate-pass-criteria.md | WEAVER-S8-001,WEAVER-S8-004 | 0.5d | code-reviewer, code-documenter | 상태 태그/근거 컬럼 최신화 |

