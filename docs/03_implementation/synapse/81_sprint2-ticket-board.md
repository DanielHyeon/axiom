# SYNAPSE Sprint 2 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| SYN-S2-001 | graph/ontology API 계약 테스트 구현 | services/synapse/docs/02_api/graph-api.md | SYN-S1-006 | 1d | api-developer | 계약 테스트 통과율 100% |
| SYN-S2-002 | ontology ingest 이벤트 경계 구현 점검 | services/synapse/docs/03_backend/ontology-ingest.md | SYN-S2-001 | 1d | backend-developer | 이벤트 멱등성 통과 |
| SYN-S2-003 | extraction 파이프라인 구조화 출력 검증 | services/synapse/docs/05_llm/structured-output.md | SYN-S2-001 | 1d | code-inspector-tester | 파싱 실패율 목표치 이내 |
| SYN-S2-004 | Neo4j bootstrap/인덱스 자동 점검 | services/synapse/docs/03_backend/neo4j-bootstrap.md | SYN-S2-002 | 0.5d | backend-developer | bootstrap 실패 0건 |
| SYN-S2-005 | 보안(case/tenant) 차단 시나리오 자동화 | services/synapse/docs/07_security/data-access.md | SYN-S2-001 | 0.5d | code-security-auditor | 격리 우회 불가 |
| SYN-S2-006 | Sprint2 결과 문서화 및 S1 사전점검 | docs/03_implementation/synapse/98_gate-pass-criteria.md | SYN-S2-003,SYN-S2-005 | 0.5d | code-reviewer, code-documenter | S1 선행 항목 통과 |
