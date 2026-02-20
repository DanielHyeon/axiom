# Sprint 4 실행 티켓 보드 (Program)

## 범위
- 목표: Oracle NL2SQL + 품질게이트 + 보안 정책 본격 구현
- 전제: Sprint 3 Exit 승인 완료

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S4-PGM-001 | Program | Sprint 4 킥오프 및 Oracle 의존성 확정 | S3-PGM-006 | 0.5d | code-implementation-planner | 범위 승인 |
| S4-PGM-002 | Oracle | NL2SQL 파이프라인 + SQL Guard + 실행 경계 구현 | S4-PGM-001 | 5d | backend-developer, api-developer | Oracle Gate O1 통과 |
| S4-PGM-003 | Oracle | 품질게이트/캐시/ValueMapping 구현 | S4-PGM-002 | 3d | backend-developer | Oracle Gate O2 통과 |
| S4-PGM-004 | Oracle | 보안정책(마스킹/ACL/row limit) 적용 검증 | S4-PGM-002 | 2d | code-security-auditor | Oracle Gate O3 통과 |
| S4-PGM-005 | Canvas | NL2SQL UI 연동/에러 처리/E2E 검증 | S4-PGM-002,S4-PGM-003 | 2d | api-developer, code-inspector-tester | 사용자 여정 통과 |
| S4-PGM-006 | Program | Sprint 4 Exit Review | S4-PGM-002~005 | 1d | code-reviewer, code-security-auditor | Sprint5 진입 승인 |

## Sprint 4 Exit Criteria
- Oracle O1/O2/O3 핵심 항목 통과
- NL2SQL 흐름의 고위험 보안 이슈 0건
