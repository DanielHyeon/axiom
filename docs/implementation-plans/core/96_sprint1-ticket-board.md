# CORE Sprint 1 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| CORE-S1-001 | Core 서비스 경계(인증/프로세스/이벤트) 확정 | services/core/docs/01_architecture/architecture-overview.md | - | 0.5d | code-implementation-planner | 경계표 승인 |
| CORE-S1-002 | Gateway/Process/Watch API 계약 점검 | services/core/docs/02_api/gateway-api.md | CORE-S1-001 | 1d | api-developer | 계약 이슈 0건 |
| CORE-S1-003 | 멀티테넌트 격리 기본 점검 항목 정의 | services/core/docs/07_security/data-isolation.md | CORE-S1-001 | 0.5d | code-security-auditor | 격리 점검 케이스 확정 |
| CORE-S1-004 | Outbox/Streams 경계 확인 체크리스트 작성 | services/core/docs/06_data/event-outbox.md | CORE-S1-001 | 0.5d | backend-developer | 이벤트 경계 체크리스트 배포 |
| CORE-S1-005 | 품질게이트(CI) 최소 세트 확정 | services/core/docs/08_operations/deployment.md | CORE-S1-002 | 1d | code-standards-enforcer | lint/type/test/security 워크플로우 정의 |
| CORE-S1-006 | Sprint1 산출물 문서 동기화 | docs/implementation-plans/core/* | CORE-S1-002,CORE-S1-005 | 0.5d | code-documenter | 00/01/02/07/08 계획 문서 최신화 |

