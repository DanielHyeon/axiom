# VISION Sprint 8 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| VISION-S8-001 | What-if CRUD 1차 구현 (`create/list/detail/update/delete`) | services/vision/docs/02_api/what-if-api.md | VISION-S7-004 | 2d | backend-developer, api-developer | CRUD 계약 테스트 통과 |
| VISION-S8-002 | What-if 계산 경로 구현 (`compute/status/result`) | services/vision/docs/02_api/what-if-api.md | VISION-S8-001 | 1.5d | backend-developer | 비동기 계산 흐름 검증 |
| VISION-S8-003 | OLAP 조회 경로 1차 구현 (`cubes`, `pivot/query`) | services/vision/docs/02_api/olap-api.md | VISION-S7-004 | 2d | backend-developer | 기본 피벗 조회 동작 |
| VISION-S8-004 | Sprint8 리뷰 및 문서 상태 동기화 | docs/03_implementation/vision/98_gate-pass-criteria.md | VISION-S8-001,VISION-S8-003 | 0.5d | code-reviewer, code-documenter | 상태 태그/근거 컬럼 최신화 |

