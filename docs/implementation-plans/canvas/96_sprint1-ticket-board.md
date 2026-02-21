# CANVAS Sprint 1 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| CAN-S1-001 | 라우팅/상태관리/컴포넌트 경계 고정 | apps/canvas/docs/01_architecture/architecture-overview.md | - | 0.5d | code-implementation-planner | 경계 위반 규칙 확정 |
| CAN-S1-002 | API 통합 경로 및 env/SSOT 동기화 점검 | apps/canvas/docs/01_architecture/api-integration.md | CAN-S1-001 | 0.5d | api-developer | 서비스 URL/WS 경로 일치 |
| CAN-S1-003 | 프론트엔드 우선순위 기능군 백로그 확정 | apps/canvas/docs/04_frontend/feature-priority-matrix.md | CAN-S1-001 | 0.5d | code-documenter | P0/P1 기능 세트 고정 |
| CAN-S1-004 | 인증/권한/세션 보안 체크리스트 확정 | apps/canvas/docs/07_security/auth-flow.md | CAN-S1-002 | 0.5d | code-security-auditor | 권한 우회 테스트 항목 확정 |
| CAN-S1-005 | [DONE] E2E 핵심 여정 정의(대시보드-문서-NL2SQL) | apps/canvas/docs/04_frontend/case-dashboard.md | CAN-S1-003 | 1d | code-inspector-tester | E2E 시나리오 문서 완료 |
| CAN-S1-006 | [DONE] 문서/추적 매트릭스 동기화 | docs/implementation-plans/canvas/* | CAN-S1-004,CAN-S1-005 | 0.5d | code-documenter | 추적 누락 0건 |

