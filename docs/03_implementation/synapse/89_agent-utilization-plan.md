# SYNAPSE 에이전트 활용 실행 계획 (89)

## 1. 목적
- 11개 에이전트를 스프린트/문서번호/Gate 기준으로 명시적으로 배치한다.
- 계획(00~99), 실행(96~90), 통과(98), 추적(99) 간 책임 공백을 제거한다.

## 2. 에이전트 책임 매핑
| 에이전트 | 주 책임 | 1차 산출물 | 완료 기준 |
|---|---|---|---|
| code-implementation-planner | 범위/의존성/일정 고정 | 00/97/96~90 업데이트 | 선후행 충돌 0건 |
| backend-developer | 도메인/서비스 구현 | 03/06/08 실행 티켓 | 기능 회귀 blocker 0건 |
| api-developer | 계약/버전/오류 모델 | 02 및 통합 API 티켓 | 계약 테스트 100% 통과 |
| code-security-auditor | 위협/권한/민감정보 통제 | 07, 보안 검증 리포트 | Critical/High 0건 |
| code-inspector-tester | 테스트 설계/실행 | 테스트 케이스/회귀 결과 | 필수 시나리오 통과율 100% |
| code-reviewer | 결함/회귀/릴리스 리뷰 | 스프린트 Exit 리뷰 | 릴리스 blocker 0건 |
| code-refactor | 구조 단순화 | 리팩토링 작업 목록 | 복잡도/중복 지표 개선 |
| code-quality-refactorer | 스멜/가독성/명명 개선 | 품질 리팩토링 묶음 | 정적분석 경고 감소 |
| code-standards-enforcer | lint/type/test 정책 | 품질게이트 파이프라인 | 게이트 실패 규칙 적용 |
| code-documenter | 구현-문서 동기화 | 00~99 문서 정합 업데이트 | 코드-문서 불일치 0건 |
| technical-doc-writer | 결정사항 구조화 | 99/README/근거 링크 | 결정-사실 분리 유지 |

## 3. 스프린트별 주관 배치
| Sprint | 주관 에이전트 | 필수 협업 | 종료 조건 |
|---|---|---|---|
| S1 | code-implementation-planner | technical-doc-writer, code-documenter | 00/01/02/03 범위 고정 |
| S2 | backend-developer | api-developer, code-inspector-tester | 핵심 기능/API 1차 통과 |
| S3 | api-developer | backend-developer, code-security-auditor | 통합 계약 정합 완료 |
| S4 | code-security-auditor | code-reviewer, code-standards-enforcer | 보안 정책 적용 완료 |
| S5 | code-refactor, code-quality-refactorer | backend-developer, code-inspector-tester | 성능/품질 개선 지표 달성 |
| S6 | code-inspector-tester | api-developer, code-reviewer | E2E/회귀 통합 통과 |
| S7 | code-reviewer | technical-doc-writer, code-documenter | 최종 Gate/릴리스 승인 |

## 4. Gate 연계 체크리스트
- Gate S0: 설계 정합
  - 00~99 문서 존재 및 상호 링크 유효
  - traceability 반영율 100%
- Gate S1: 기능/API
  - 계약 테스트 100%
  - 권한/오류 표준 위반 0건
- Gate S2: 데이터/품질
  - 핵심 데이터 경로 불일치 0건
  - 성능/회귀 기준 충족
- Gate S3: 보안/운영
  - Critical/High 0건
  - 배포/롤백/복구 리허설 완료

## 5. 증적(Artifacts) 보관 규칙
- Sprint별 티켓 결과는 `96~90` 문서에 ID 단위로 기록한다.
- Gate 판정 결과는 `98_gate-pass-criteria.md` 항목 ID와 1:1로 매핑한다.
- 설계 반영 근거는 `99_traceability-matrix.md`에 문서 경로/상태로 누적한다.

## 6. 적용 범위
- 프로젝트: SYNAPSE
- 프론트엔드 특이사항: N/A
