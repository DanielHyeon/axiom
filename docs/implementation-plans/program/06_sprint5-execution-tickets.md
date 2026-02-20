# Sprint 5 실행 티켓 보드 (Program)

## 범위
- 목표: Vision 분석 엔진(OLAP/What-if) 안정화
- 전제: Sprint 4 Exit 승인 완료

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S5-PGM-001 | Program | Sprint 5 킥오프 및 분석 계약 재검토 | S4-PGM-006 | 0.5d | code-implementation-planner | 범위 승인 |
| S5-PGM-002 | Vision | analytics/olap/what-if API 완성 (root-cause 제외) | S5-PGM-001 | 5d | backend-developer, api-developer | Vision Gate V1 통과 |
| S5-PGM-003 | Vision | ETL/MV/큐브/솔버 데이터 경로 안정화 | S5-PGM-002 | 3d | backend-developer | Vision Gate V2 통과 |
| S5-PGM-004 | Canvas | OLAP/What-if 화면 연동 및 성능 점검 | S5-PGM-002 | 2d | api-developer, code-inspector-tester | 화면-API 정합/성능 통과 |
| S5-PGM-005 | Vision | FM-001 완료: What-if 잔여 Gate 항목 종료 | S5-PGM-002,S5-PGM-003 | 1d | backend-developer, code-reviewer | FM-001 D3 완료 |
| S5-PGM-006 | Program | Sprint 5 Exit Review | S5-PGM-002~005 | 1d | code-reviewer, code-security-auditor | Sprint6 진입 승인 |

## Sprint 5 Exit Criteria
- Vision V1/V2 핵심 항목 통과
- 분석 API 계약 충돌 Critical 0건
- FM-001 상태가 `D3 구현 완료`로 갱신됨

## Phase 4 이관 항목
- See-Why(root-cause) API/엔진 구현은 `services/vision/docs/00_overview/system-overview.md`의 Phase 4(출시 후) 일정으로 이관
