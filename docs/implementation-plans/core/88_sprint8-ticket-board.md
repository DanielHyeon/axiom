# CORE Sprint 8 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| CORE-S8-001 | Watch Alerts API 최소 구현 (`GET alerts`, `PUT acknowledge`, `PUT read-all`) | services/core/docs/02_api/watch-api.md | CORE-S7-004 | 1.5d | backend-developer, api-developer | Canvas Watch 화면 연동 성공 |
| CORE-S8-002 | Watch Subscriptions/Rules API 구현 | services/core/docs/02_api/watch-api.md | CORE-S8-001 | 1.5d | backend-developer, code-security-auditor | 구독 CRUD + rules API 동작 |
| CORE-S8-003 | Process Lifecycle 보강 (`/initiate`, `/status`, `/workitems`, `/approve-hitl`, `/rework`) | services/core/docs/02_api/process-api.md | CORE-S7-004 | 2d | backend-developer | 상태전이 회귀 테스트 통과 |
| CORE-S8-004 | Gateway event-log/process-mining 프록시 1차 구현 | services/core/docs/02_api/gateway-api.md | CORE-S8-003 | 1.5d | backend-developer | Core 경유 라우팅/에러 매핑 검증 |
| CORE-S8-005 | Sprint8 리뷰 및 API 문서 상태 동기화 | docs/implementation-plans/core/98_gate-pass-criteria.md | CORE-S8-001,CORE-S8-004 | 0.5d | code-reviewer, code-documenter | 상태 태그/근거 컬럼 최신화 |

