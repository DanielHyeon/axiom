# WEAVER Sprint 2 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| WEA-S2-001 | datasource API 계약 테스트 구현 | services/weaver/docs/02_api/datasource-api.md | WEA-S1-005 | 1d | api-developer | 계약 테스트 통과 |
| WEA-S2-002 | schema introspection/metadata propagation 경계 점검 | services/weaver/docs/03_backend/schema-introspection.md | WEA-S2-001 | 1d | backend-developer | 전파 누락/중복 허용치 이내 |
| WEA-S2-003 | Neo4j schema v2 소유권 규칙 검증 자동화 | services/weaver/docs/06_data/neo4j-schema-v2.md | WEA-S2-002 | 0.5d | code-inspector-tester | 소유권 위반 0건 |
| WEA-S2-004 | 연결보안/접근통제 테스트 자동화 | services/weaver/docs/07_security/connection-security.md | WEA-S2-001 | 0.5d | code-security-auditor | 비밀/권한 누출 0건 |
| WEA-S2-005 | Sprint2 결과 문서화 및 W1 사전점검 | docs/03_implementation/weaver/98_gate-pass-criteria.md | WEA-S2-003,WEA-S2-004 | 0.5d | code-reviewer, code-documenter | W1 선행 항목 통과 |
