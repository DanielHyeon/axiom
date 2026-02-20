# Sprint 3 실행 티켓 보드 (Program)

## 범위
- 목표: Synapse + Weaver 그래프/메타데이터 플랫폼 완성
- 전제: Sprint 2 Exit 승인 완료

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S3-PGM-001 | Program | Sprint 3 킥오프 및 계약 고정 재확인 | S2-PGM-008 | 0.5d | code-implementation-planner | 범위/의존 승인 |
| S3-PGM-002 | Synapse | ontology/extraction/process-mining API 구현 완성 | S3-PGM-001 | 5d | backend-developer, api-developer | Synapse Gate S1/S2 핵심 통과 |
| S3-PGM-003 | Weaver | datasource/metadata 동기화 및 schema v2 운영 고정 | S3-PGM-001 | 5d | backend-developer, api-developer | Weaver Gate W1/W2 핵심 통과 |
| S3-PGM-004 | Oracle | Synapse/Weaver 연동 의존성 검증(조회/캐시) | S3-PGM-002,S3-PGM-003 | 2d | backend-developer | 연동 리스크 0건 |
| S3-PGM-005 | Canvas | 온톨로지/메타 브라우저 연동 검증 | S3-PGM-002,S3-PGM-003 | 2d | api-developer, code-inspector-tester | 화면-API 정합 통과 |
| S3-PGM-006 | Program | Sprint 3 Exit Review | S3-PGM-002~005 | 1d | code-reviewer, code-security-auditor | Sprint4 진입 승인 |

## Sprint 3 Exit Criteria
- Synapse/Weaver 계약 테스트 100%
- 그래프/메타데이터 정합성 Critical 이슈 0건
