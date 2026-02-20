# Sprint 7 실행 티켓 보드 (Program)

## 범위
- 목표: 보안/성능/운영 하드닝 및 릴리스 승인
- 전제: Sprint 6 Exit 승인 완료

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S7-PGM-001 | Program | Sprint 7 킥오프 및 하드닝 체크리스트 확정 | S6-PGM-005 | 0.5d | code-implementation-planner | 체크리스트 승인 |
| S7-PGM-002 | 전서비스 | 보안 감사(SAST/DAST/권한우회/비밀관리) | S7-PGM-001 | 3d | code-security-auditor | Critical/High 0건 |
| S7-PGM-003 | 전서비스 | 성능/부하/복구 리허설 | S7-PGM-001 | 3d | backend-developer | RTO/RPO/SLI 목표 충족 |
| S7-PGM-004 | 전서비스 | 코드 리뷰/리팩토링/표준 준수 마감 | S7-PGM-002,S7-PGM-003 | 2d | code-reviewer, code-refactor, code-standards-enforcer | 릴리스 블로커 0건 |
| S7-PGM-005 | Core | FM-005 완료: Watch Early Warning 폐루프 SLA 계측 완료 | S7-PGM-003 | 1d | backend-developer, code-inspector-tester | FM-005 D3 완료 |
| S7-PGM-006 | Core | FM-006 완료: CEP 오탐률/지연 지표 튜닝 마감 | S7-PGM-005 | 1d | backend-developer, code-reviewer | FM-006 D3 완료 |
| S7-PGM-007 | Vision | FM-004 착수: See-Why Phase 4 킥오프 패키지 작성 | S7-PGM-003 | 1d | code-implementation-planner, backend-developer | FM-004 D2 착수 완료 |
| S7-PGM-008 | Program | 최종 릴리스 승인 리뷰 | S7-PGM-002~007 | 1d | code-reviewer, technical-doc-writer | 릴리스 승인 |

## Sprint 7 Exit Criteria
- Critical/High 취약점 0건
- 운영 리허설/복구 테스트 통과
- 최종 문서(00~99, 95~98) 최신화 완료
- FM-005/FM-006 상태가 `D3 구현 완료`로 갱신됨
- FM-004 상태가 `D2 구현 착수`로 갱신됨
