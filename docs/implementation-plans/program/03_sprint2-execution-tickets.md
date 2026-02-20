# Sprint 2 실행 티켓 보드 (Program)

## 범위
- 목표: Core Runtime 본격 구현 + 연동 서비스 계약 고정
- 전제: Sprint 1 Exit 승인 완료

## 티켓 목록

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S2-PGM-001 | Program | Sprint 2 킥오프 및 Sprint 1 잔여 리스크 정리 | S1-PGM-010 | 0.5d | code-implementation-planner | 리스크 이관표 확정 |
| S2-PGM-002 | Core | Core Runtime 구현(프로세스/이벤트/보안) 완료 | S2-PGM-001 | 6d | backend-developer | Core Gate C1/C2 핵심 통과 |
| S2-PGM-003 | Synapse | Graph API 계약 고정 + ingest 준비 | S2-PGM-001 | 4d | backend-developer, api-developer | Synapse Gate S1 선행조건 충족 |
| S2-PGM-004 | Weaver | 메타데이터 API/스키마 v2 연동 준비 | S2-PGM-001 | 4d | backend-developer, api-developer | Weaver Gate W1 선행조건 충족 |
| S2-PGM-005 | Oracle | text2sql API/보안 정책/연동 어댑터 구현 시작 | S2-PGM-003 | 4d | backend-developer, api-developer | Oracle Gate O1 선행조건 충족 |
| S2-PGM-006 | Vision | 분석 API 계약/비동기 실행 준비 | S2-PGM-001 | 3d | backend-developer, api-developer | Vision Gate V1 선행조건 충족 |
| S2-PGM-007 | Canvas | Core/Oracle/Synapse/Weaver/Vision 계약 반영 BFF 경로 점검 | S2-PGM-002,S2-PGM-003,S2-PGM-004,S2-PGM-005,S2-PGM-006 | 3d | api-developer, code-documenter | Canvas 계약 정합 리포트 완료 |
| S2-PGM-008 | Program | Sprint 2 Exit Review (기능/API/보안 점검) | S2-PGM-002~007 | 1d | code-reviewer, code-security-auditor | Sprint3 진입 승인 |

## Sprint 2 Exit Criteria
- Core 주요 런타임 흐름 회귀 0건
- 연동 API 계약 충돌 Critical 0건
- 보안 고위험 이슈 0건
