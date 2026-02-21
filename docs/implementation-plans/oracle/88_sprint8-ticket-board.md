# ORACLE Sprint 8 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| ORACLE-S8-001 | Meta API 조회 경로 구현 (`tables`, `columns`, `datasources`) | services/oracle/docs/02_api/meta-api.md | ORACLE-S7-004 | 1.5d | backend-developer, api-developer | 조회 API 계약 테스트 통과 |
| ORACLE-S8-002 | Meta API 수정 경로 구현 (`table/column description`) | services/oracle/docs/02_api/meta-api.md | ORACLE-S8-001 | 1d | backend-developer, code-security-auditor | Admin 권한 검증 포함 동작 |
| ORACLE-S8-003 | Events API 이관 전략 확정 (Oracle 유지 vs Core Watch 완전 이관) | services/oracle/docs/02_api/events-api.md | ORACLE-S7-004 | 0.5d | code-implementation-planner, code-reviewer | 단일 전략 승인 |
| ORACLE-S8-004 | (선택) Events API 최소 구현 또는 Core 프록시 적용 | services/oracle/docs/02_api/events-api.md | ORACLE-S8-003 | 1.5d | backend-developer | 승인 전략 기준 최소 경로 동작 |
| ORACLE-S8-005 | Sprint8 리뷰 및 문서 상태 동기화 | docs/implementation-plans/oracle/98_gate-pass-criteria.md | ORACLE-S8-001,ORACLE-S8-004 | 0.5d | code-reviewer, code-documenter | 상태 태그/근거 컬럼 최신화 |

