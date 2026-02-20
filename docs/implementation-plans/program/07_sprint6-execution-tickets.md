# Sprint 6 실행 티켓 보드 (Program)

## 범위
- 목표: Canvas 통합 완성 + 전 서비스 E2E
- 전제: Sprint 5 Exit 승인 완료

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S6-PGM-001 | Program | Sprint 6 킥오프 및 E2E 범위 확정 | S5-PGM-006 | 0.5d | code-implementation-planner | 시나리오 승인 |
| S6-PGM-002 | Canvas | 핵심 사용자 여정 통합(대시보드/문서/NL2SQL/OLAP/온톨로지) | S6-PGM-001 | 5d | api-developer, code-inspector-tester | Canvas Gate U1 통과 |
| S6-PGM-003 | Canvas | 상태/캐시/실시간 이벤트 성능 최적화 | S6-PGM-002 | 3d | code-refactor, backend-developer | Canvas Gate U2 통과 |
| S6-PGM-004 | 전서비스 | E2E 연동 회귀 + 계약 회귀 일괄 실행 | S6-PGM-002,S6-PGM-003 | 2d | code-reviewer | 회귀 블로커 0건 |
| S6-PGM-005 | Program | Sprint 6 Exit Review | S6-PGM-002~004 | 1d | code-reviewer, code-security-auditor | Sprint7 진입 승인 |

## Sprint 6 Exit Criteria
- Canvas U1/U2 핵심 항목 통과
- 전서비스 연동 E2E 블로커 0건
