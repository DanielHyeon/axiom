# CANVAS Sprint 7 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| CANVAS-S7-001 | 하드닝 범위/잔여 리스크 확정 | apps/canvas/docs/07_security/auth-flow.md | CANVAS-S6-004 | 0.5d | code-implementation-planner | 하드닝 체크리스트 승인 |
| CANVAS-S7-002 | 보안 감사 및 취약점 제거 | apps/canvas/docs/07_security/auth-flow.md | CANVAS-S7-001 | 1.5d | code-security-auditor | Critical/High 0건 |
| CANVAS-S7-003 | 성능/복구 리허설 및 운영 기준 검증 | apps/canvas/docs/08_operations/build-deploy.md | CANVAS-S7-002 | 1d | backend-developer | SLO/RTO 목표 충족 |
| CANVAS-S7-004 | 최종 Gate 체크 및 릴리스 문서 확정 | docs/implementation-plans/canvas/98_gate-pass-criteria.md | CANVAS-S7-003 | 0.5d | code-reviewer, technical-doc-writer | 릴리스 승인 |
