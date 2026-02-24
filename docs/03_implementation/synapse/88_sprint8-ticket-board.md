# SYNAPSE Sprint 8 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| SYNAPSE-S8-001 | Event-Log API 1차 구현 (`ingest/list/detail/preview/statistics`) | services/synapse/docs/02_api/event-log-api.md | SYNAPSE-S7-004 | 2d | backend-developer | 이벤트 로그 기본 흐름 동작 |
| SYNAPSE-S8-002 | Event-Log 매핑/재인제스트/삭제 API 구현 | services/synapse/docs/02_api/event-log-api.md | SYNAPSE-S8-001 | 1d | backend-developer | column-mapping/refresh/delete 동작 |
| SYNAPSE-S8-003 | Extraction API 1차 구현 (`extract/status/result`) | services/synapse/docs/02_api/extraction-api.md | SYNAPSE-S7-004 | 2d | backend-developer, api-developer | 비동기 상태머신 동작 |
| SYNAPSE-S8-004 | Extraction HITL API 구현 (`confirm/review/review-queue/retry/revert`) | services/synapse/docs/02_api/extraction-api.md | SYNAPSE-S8-003 | 1.5d | backend-developer, code-inspector-tester | 임계치 분기 + 재시도/보상 검증 |
| SYNAPSE-S8-005 | Schema-edit API 1차 구현 | services/synapse/docs/02_api/schema-edit-api.md | SYNAPSE-S7-004 | 1.5d | backend-developer | tables/relationships 기본 경로 동작 |
| SYNAPSE-S8-006 | Sprint8 리뷰 및 문서 상태 동기화 | docs/03_implementation/synapse/98_gate-pass-criteria.md | SYNAPSE-S8-001,SYNAPSE-S8-005 | 0.5d | code-reviewer, code-documenter | 상태 태그/근거 컬럼 최신화 |

