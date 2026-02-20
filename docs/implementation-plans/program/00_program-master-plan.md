# Axiom 통합 구현 프로그램 계획서

## 1. 목적
- 기존 설계 문서(`apps/canvas/docs`, `services/*/docs`)를 구현 가능한 작업 패키지로 전환한다.
- 프로젝트별( Core / Oracle / Synapse / Vision / Weaver / Canvas ) 구현 순서와 의존성을 명시한다.
- 각 단계별 통과 기준(Gate)을 정의하여, 설계-구현-검증의 추적 가능성을 확보한다.

## 2. 에이전트 활용 프레임
| 에이전트 | 활용 목적 | 산출물 |
|---|---|---|
| `code-implementation-planner` | 요구사항/의존성/순차 계획 수립 | 번호별 구현 계획, 단계 순서 |
| `backend-developer` | 서비스 내부 구현 설계(도메인/트랜잭션/성능) | 03/06/08 구체 작업 |
| `api-developer` | API 계약/버전/에러 모델/Idempotency | 02 API 구현 패키지 |
| `code-security-auditor` | 위협모델/RLS/권한/민감정보 통제 | 07 보안 통과 기준 |
| `code-inspector-tester` | 테스트 아키텍처/경계값/회귀 검증 | 테스트 계획/커버리지 기준 |
| `code-reviewer` | 결함/회귀/운영 리스크 리뷰 | Gate 직전 결함 목록 |
| `code-refactor` | 구조 단순화 및 점진적 리팩토링 | 기술부채 해소 작업 |
| `code-quality-refactorer` | 코드 스멜 제거, 가독성 강화 | 리팩토링 체크리스트 |
| `code-standards-enforcer` | lint/type/test 품질게이트 자동화 | CI 기준 및 정책 |
| `code-documenter` | 코드/API/운영 문서 최신화 | 구현 동기화 문서 |
| `technical-doc-writer` | 문서번호 체계 기반 문서 구성/결정-사실 분리 | 00~99 문서 유지 전략 |

## 3. 구현 순서 (프로그램 레벨)
1. `Core` 기반 인프라(인증, 워크플로우, 이벤트, 운영 관측)
2. `Synapse` 그래프/온톨로지/마이닝 기반 구축
3. `Weaver` 메타데이터 수집/동기화 및 그래프 스키마 보강
4. `Oracle` NL2SQL + 품질게이트 + Synapse 연동 경로 확정
5. `Vision` OLAP/What-if/Root Cause 엔진 및 API 안정화
6. `Canvas` 프론트엔드 통합(BFF/API 계약, UX, 실시간 상호작용)

## 4. 교차 의존성
- `Oracle -> Synapse`: 그래프/메타 탐색, 캐시 반영 API 의존
- `Canvas -> Core`: 인증/JWT, WebSocket 알림, 프로세스/문서 흐름 의존
- `Canvas -> Oracle/Synapse/Vision/Weaver`: 기능별 API 계약 의존
- `Vision/Oracle/Synapse/Weaver -> Core`: 멀티테넌시/보안/운영 공통 기준 의존
- 공통 포트/엔드포인트는 `docs/service-endpoints-ssot.md`를 SSOT로 사용
- 데이터 의미 계층은 `docs/architecture-semantic-layer.md`를 기준으로 Weaver/Synapse/Vision 책임을 분리
- 레거시 원본 불변 원칙은 `docs/legacy-data-isolation-policy.md`를 전 서비스 공통 정책으로 적용

## 5. 프로그램 Gate
- `Gate P1 (설계 정합성)`: 프로젝트별 00~99 계획서 완성 + 추적 매트릭스 100%
- `Gate P2 (계약 고정)`: API 계약(OpenAPI/에러코드/권한표) 확정, 브레이킹 변경 승인 체계 확립
- `Gate P3 (구현 완성)`: 기능/보안/성능/운영 테스트 통과, Critical 결함 0
- `Gate P4 (운영 준비)`: 배포/복구/관측/경보/런북 검증 완료

## 6. 문서 연동 규칙
- 구현 시 모든 변경은 해당 번호 문서(00~99)에 반영한다.
- ADR 변경은 99에 선반영 후 구현한다.
- 통과 기준 미충족 시 다음 단계로 이동하지 않는다.
- API 문서는 구현 상태를 `Implemented / Experimental / Planned`로 명시하고 코드 상태와 동기화한다.
