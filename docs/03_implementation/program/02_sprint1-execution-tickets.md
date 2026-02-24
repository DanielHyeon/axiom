# Sprint 1 실행 티켓 보드 (Program)

## 범위
- 대상: Core, Oracle, Synapse, Vision, Weaver, Canvas
- 목표: 경계/계약/SSOT 고정 + Sprint 2 진입 조건 충족

## 티켓 목록

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S1-PGM-001 | Program | Sprint 1 킥오프 및 공통 DoD 확정 | - | 0.5d | code-implementation-planner | 전 프로젝트 DoD/게이트 정의 승인 |
| S1-PGM-002 | Program | API 변경 승인 프로세스(사전 ADR/계약 검토) 가동 | S1-PGM-001 | 0.5d | api-developer, technical-doc-writer | 변경 승인 체크리스트 운영 시작 |
| S1-PGM-003 | Program | 공통 품질게이트 파이프라인 템플릿 확정 | S1-PGM-001 | 1d | code-standards-enforcer | lint/type/test/security 파이프라인 합의 |
| S1-PGM-004 | Core | Core Sprint1 티켓 완료 | S1-PGM-001 | 4d | backend-developer | CORE Sprint1 보드 완료 |
| S1-PGM-005 | Synapse | Synapse Sprint1 티켓 완료 | S1-PGM-001 | 3d | backend-developer | SYNAPSE Sprint1 보드 완료 |
| S1-PGM-006 | Oracle | Oracle Sprint1 티켓 완료 | S1-PGM-005 | 3d | backend-developer, api-developer | ORACLE 경계/계약 정합 완료 |
| S1-PGM-007 | Weaver | Weaver Sprint1 티켓 완료 | S1-PGM-001 | 3d | backend-developer | WEAVER Sprint1 보드 완료 |
| S1-PGM-008 | Vision | Vision Sprint1 티켓 완료 | S1-PGM-001 | 2d | backend-developer | VISION ADR/경계 정합 완료 |
| S1-PGM-009 | Canvas | Canvas Sprint1 티켓 완료 | S1-PGM-004,S1-PGM-006,S1-PGM-007,S1-PGM-008 | 3d | code-documenter, api-developer | Canvas API 통합 기준 고정 |
| S1-PGM-010 | Program | Sprint1 Exit Review (경계 위반/계약 리스크 점검) | S1-PGM-004~009 | 1d | code-reviewer, code-security-auditor | Sprint2 진입 승인 |

## Sprint 1 Exit Criteria
- 아키텍처 경계 위반 Critical 0건
- API 계약 변경 승인 프로세스 운영 증적 확보
- 각 프로젝트 `80_sprint1-ticket-board.md`의 모든 티켓 `Done`
