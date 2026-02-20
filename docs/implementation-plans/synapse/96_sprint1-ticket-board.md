# SYNAPSE Sprint 1 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| SYN-S1-001 | Synapse Graph API 경계/책임 고정 | services/synapse/docs/01_architecture/architecture-overview.md | - | 0.5d | code-implementation-planner | 외부 서비스 접근 규칙 확정 |
| SYN-S1-002 | graph/ontology API 계약 검토 | services/synapse/docs/02_api/graph-api.md | SYN-S1-001 | 1d | api-developer | 계약 충돌 0건 |
| SYN-S1-003 | Neo4j bootstrap 및 인덱스 책임 정의 | services/synapse/docs/03_backend/neo4j-bootstrap.md | SYN-S1-001 | 0.5d | backend-developer | bootstrap 책임표 승인 |
| SYN-S1-004 | HITL 임계값 분기 사전 검증 항목 정의 | services/synapse/docs/99_decisions/ADR-004-hitl-threshold.md | SYN-S1-002 | 0.5d | code-inspector-tester | 분기 테스트 케이스 정의 |
| SYN-S1-005 | 보안(case_id/tenant_id) 체크리스트 확정 | services/synapse/docs/07_security/data-access.md | SYN-S1-002 | 0.5d | code-security-auditor | 격리 위반 테스트 케이스 확정 |
| SYN-S1-006 | 문서/추적 매트릭스 동기화 | docs/implementation-plans/synapse/* | SYN-S1-004,SYN-S1-005 | 0.5d | code-documenter | 추적 매트릭스 누락 0건 |

