# Program 에이전트 거버넌스 및 통과 판정 (09)

## 1. 목적
- 프로젝트별 `89_agent-utilization-plan.md`의 실행 일관성을 프로그램 레벨에서 통제한다.
- 스프린트 종료 시 에이전트별 승인/반려 권한과 증적 요건을 표준화한다.

## 2. 전사 RACI
| 영역 | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| 범위/일정 | code-implementation-planner | code-reviewer | technical-doc-writer | 전 프로젝트 |
| API 계약 | api-developer | code-reviewer | backend-developer, code-security-auditor | Canvas/연동팀 |
| 백엔드 구현 | backend-developer | code-reviewer | code-refactor, code-quality-refactorer | QA/운영 |
| 품질/테스트 | code-inspector-tester | code-reviewer | code-standards-enforcer | 전 프로젝트 |
| 보안 | code-security-auditor | code-reviewer | backend-developer, api-developer | 운영/컴플라이언스 |
| 표준/CI | code-standards-enforcer | code-reviewer | code-inspector-tester | 전 프로젝트 |
| 문서/추적 | code-documenter, technical-doc-writer | code-reviewer | code-implementation-planner | 전 프로젝트 |

## 3. Sprint Exit 최소 증적
- S1~S7 공통
  - 각 프로젝트 `96~90` 티켓 보드 상태 최신화
  - 각 프로젝트 `98_gate-pass-criteria.md` 체크 결과 반영
  - 각 프로젝트 `99_traceability-matrix.md` 반영율 100%
- S4/S7 보안 집중 구간
  - code-security-auditor 서명 결과(취약점 등급/조치 상태)
- S5 품질 집중 구간
  - code-refactor, code-quality-refactorer 개선 지표(복잡도/중복/경고 수)

## 4. 통과/반려 규칙
- 통과
  - 기능/계약/보안/성능/문서의 필수 항목이 모두 충족된 경우
- 조건부 통과
  - Non-blocker 결함만 존재하고, 다음 Sprint 이관 티켓이 명시된 경우
- 반려
  - Critical/High 취약점, 계약 위반, 회귀 blocker, 추적 누락 중 하나라도 존재

## 5. 프로그램 최종 승인 조건
- Program `08_sprint7-execution-tickets.md`의 모든 항목 완료
- 전 프로젝트 Gate 최종 상태가 통과 또는 조건부 통과
- 릴리스 문서와 운영 런북이 최신 설계 기준과 불일치 0건
