# WEAVER Sprint 1 티켓 보드

| Ticket ID | 작업 | 참조 설계 문서 | 선행 의존 | 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| WEA-S1-001 | Adapter/Metadata 경계 고정 | services/weaver/docs/01_architecture/adapter-pattern.md | - | 0.5d | code-implementation-planner | 어댑터 책임 매트릭스 승인 |
| WEA-S1-002 | datasource/metadata/query API 계약 점검 | services/weaver/docs/02_api/datasource-api.md | WEA-S1-001 | 1d | api-developer | 계약 불일치 0건 |
| WEA-S1-003 | Neo4j schema v2 소유권 규칙 확정 | services/weaver/docs/06_data/neo4j-schema-v2.md | WEA-S1-001 | 0.5d | backend-developer | 노드/속성 소유권 표 확정 |
| WEA-S1-004 | 연결보안/데이터접근 점검 항목 정의 | services/weaver/docs/07_security/connection-security.md | WEA-S1-002 | 0.5d | code-security-auditor | 비밀관리/권한 점검표 완료 |
| WEA-S1-005 | 문서/추적 매트릭스 동기화 | docs/03_implementation/weaver/* | WEA-S1-003,WEA-S1-004 | 0.5d | code-documenter | 추적 누락 0건 |

