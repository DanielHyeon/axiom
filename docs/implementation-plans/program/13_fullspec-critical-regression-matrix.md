# Full Spec Critical 리그레션 매트릭스

기준일: 2026-02-22  
기준 보고서: `docs/full-spec-gap-analysis-2026-02-22.md`  
스프린트 연계: `docs/implementation-plans/program/12_sprint9-execution-tickets.md`

## 1. 목적

Critical 갭(G-001~G-004)의 구현/회귀 검증 기준을 테스트 케이스로 고정한다.

## 2. 테스트 매트릭스

| Gap ID | 검증 대상 | 테스트 유형 | 테스트 파일/티켓 | 현재 상태 | 통과 기준 |
|---|---|---|---|---|---|
| G-001 | Vision Root-Cause 최소 API | Unit/API | `services/vision/tests/unit/test_root_cause_api.py` | In Progress (1차 구현) | 4개 최소 엔드포인트 2xx/권한/오류경로 검증 |
| G-002 | Self-Verification Harness | Integration | `services/core/tests/integration/test_e2e_process_submit.py` | Implemented (1차 런타임 반영) | 샘플링(20%) + fail-routing 경로 재현, self_verification 메타 응답 확인 |
| G-003 | 4-Source lineage 강제 | Contract/Integration | `services/synapse/tests/unit/test_extraction_api_full.py` | Implemented (1차 계약 강제) | 필수 필드 누락 시 `422/INGESTION_LINEAGE_REQUIRED` reject 재현 |
| G-004 | SSOT-Compose-K8s 정합성 | CLI/Static Check | `tools/validate_ssot.py` | Implemented (검증 자동화 1차) | 스크립트 실행 시 불일치 0건 |

## 3. 실행 규칙

1. Sprint 종료 전 Critical 4개 모두 상태를 `Implemented / In Progress / Planned`로 갱신한다.
2. `In Progress` 항목은 최소 하나의 실행 가능한 테스트 경로를 반드시 연결한다.
3. 신규 환경변수/포트/서비스 변경 시 `tools/validate_ssot.py`를 CI 또는 PR 체크에서 실행한다.

## 4. 다음 액션

1. G-002/G-003는 Sprint 11 구현분 기준 `Implemented` 상태 유지 여부를 회귀 테스트로 확인
2. G-001(G-004 포함)의 `In Progress/Partial` 항목을 다음 스프린트에서 `Implemented`로 승격
3. Sprint 12 운영 지표(`outbox backlog`, `DLQ reprocess`, `legacy violation`)를 리그레션 항목으로 추가 확장
