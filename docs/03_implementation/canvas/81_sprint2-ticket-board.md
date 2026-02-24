# CANVAS Sprint 2 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| CAN-S2-001 | API 클라이언트 에러/권한 처리 표준 적용 점검 | apps/canvas/docs/02_api/api-client.md | CAN-S1-006 | 1d | api-developer | 에러 핸들링 표준 준수 |
| CAN-S2-002 | BFF 경로 및 라우팅 계약 동기화 | apps/canvas/docs/03_backend/bff-layer.md | CAN-S2-001 | 0.5d | api-developer | 경로/권한 불일치 0건 |
| CAN-S2-003 | 핵심 화면 데이터 바인딩 검증(대시보드/문서/NL2SQL) | apps/canvas/docs/04_frontend/implementation-guide.md | CAN-S2-002 | 1d | code-inspector-tester | 누락/오표시 0건 |
| CAN-S2-004 | 인증/세션 보안 정책 적용 점검 | apps/canvas/docs/07_security/auth-flow.md | CAN-S2-001 | 0.5d | code-security-auditor | 세션 취약점 고위험 0건 |
| CAN-S2-005 | E2E 스모크 세트 작성 및 실행 | apps/canvas/docs/04_frontend/case-dashboard.md | CAN-S2-003 | 1d | code-inspector-tester | 스모크 E2E 통과 |
| CAN-S2-006 | Sprint2 결과 문서화 및 U1 사전점검 | docs/03_implementation/canvas/98_gate-pass-criteria.md | CAN-S2-004,CAN-S2-005 | 0.5d | code-reviewer, code-documenter | U1 선행 항목 통과 |
