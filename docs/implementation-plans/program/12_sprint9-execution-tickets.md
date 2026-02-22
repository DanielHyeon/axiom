# Sprint 9 실행 티켓 보드 (Program)

## 범위
- 목표: `docs/full-spec-gap-analysis-2026-02-22.md` 기준 Critical 갭의 P0 구간 착수 및 운영 리스크 선제 제거
- 전제: Sprint 8의 API 경로 복구는 완료, Sprint 9부터 Full Spec 완성도를 기준으로 트래킹

| Ticket ID | 프로젝트 | 작업 | 선행 의존 | 예상 공수 | 담당 에이전트 | 완료 기준 |
|---|---|---|---|---|---|---|
| S9-PGM-001 | Program | Sprint 9 킥오프 및 Full Spec P0 범위 확정 | S8-PGM-009 | 0.5d | code-implementation-planner | Sprint 9 범위/의존성 승인 |
| S9-VIS-001 | Vision | Root-Cause API 최소 골격 구현 (`/root-cause-analysis`, `/status`, `/root-causes`, `/counterfactual`) | S9-PGM-001 | 2d | backend-developer, api-developer | 라우트+서비스+테스트 통과 |
| S9-CAN-001 | Canvas | 실제 인증 강제(ProtectedRoute) 및 refresh token 플로우 1차 | S9-PGM-001 | 2d | frontend-developer, backend-developer | 로그인/만료/갱신 시나리오 통과 |
| S9-PGM-002 | Program | SSOT/Compose/K8s 정합성 점검 자동화 스크립트 추가 | S9-PGM-001 | 1.5d | code-standards-enforcer | 포트/서비스 불일치 검출 자동화 |
| S9-QA-001 | Program | Full Spec 리그레션 테스트 템플릿 수립 (Critical 우선) | S9-VIS-001,S9-CAN-001 | 1d | code-inspector-tester | Critical 항목 테스트 매트릭스 생성 |
| S9-PGM-003 | Program | Sprint 9 Exit 리뷰 및 문서 상태 동기화 | S9-VIS-001,S9-CAN-001,S9-PGM-002 | 0.5d | code-reviewer, code-documenter | 보고서/백로그/API 태그 동기화 |

## Sprint 9 Exit Criteria
- [x] Vision Root-Cause 최소 API 4개 엔드포인트가 동작하고 테스트가 존재한다.
- [x] Canvas 인증이 mock bypass 없이 만료/갱신 경로를 포함해 동작한다.
- [x] SSOT-Compose-K8s 불일치 검출이 수동 점검이 아닌 스크립트로 재현 가능하다.
- [x] Critical 갭 항목의 문서 상태와 코드 상태 불일치가 0건이다.

## Sprint 10~12 후속 구현 계획 (보고서 기준)

### Sprint 10 (Mock-to-Real 전환 1차)
- Oracle NL2SQL mock 제거 1차 (`ORA-NL2SQL-REAL-001`)
- Vision What-if/OLAP 상태 영속화 1차 (`VIS-STATE-001`)
- Core Agent/MCP 저장소 영속화 1차 (`CORE-AGENT-001`)

### Sprint 11 (정책 구현 1차)
- Self-Verification Harness 골격 (`PGM-SV-001`)
- 4-Source lineage 계약 강제 (`PGM-4SRC-001`)
- Domain Contract Registry 런타임 강제 (`CORE-EVT-001`)

### Sprint 12 (운영 완성)
- Outbox -> Redis Streams 워커/컨슈머 운영경로 명시화 (`CORE-OUTBOX-001`)
- DLQ/재처리/관측 지표 완성
- legacy write 위반 탐지 규칙 운영 반영

## 2026-02-22 진행 메모
- [x] `S9-VIS-001` 1차 완료 (최소 API 4종 + 테스트 통과)
  - 구현:
    - `services/vision/app/api/root_cause.py`
    - `services/vision/app/services/vision_runtime.py`
    - `services/vision/app/main.py`
  - 테스트:
    - `services/vision/tests/unit/test_root_cause_api.py`
    - `services/vision/tests/unit/test_vision_p2_api_full.py`
- [x] `S9-CAN-001` 1차 완료 (인증 우회 제거 + refresh 구현)
  - 구현:
    - `apps/canvas/src/components/ProtectedRoute.tsx`
    - `apps/canvas/src/stores/authStore.ts`
    - `apps/canvas/src/pages/auth/LoginPage.tsx`
    - `apps/canvas/src/lib/api-client.ts`
    - `apps/canvas/src/App.tsx`
  - 검증:
    - `cd apps/canvas && npm run build` 통과
  - 비고:
    - 로그인은 Core `/api/v1/auth/login` 실호출을 우선 시도하며, `VITE_AUTH_FALLBACK_MOCK=false` 설정 시 mock fallback 비활성화 가능
- [x] `S9-PGM-002` 1차 완료 (SSOT 정합 자동 점검 스크립트 추가)
  - 구현:
    - `tools/validate_ssot.py`
    - `docs/service-endpoints-ssot.md`
  - 검증:
    - `python3 tools/validate_ssot.py` 통과
- [x] `S9-QA-001` 1차 완료 (Critical 리그레션 매트릭스 수립)
  - 산출물:
    - `docs/implementation-plans/program/13_fullspec-critical-regression-matrix.md`
- [x] `S9-PGM-003` 완료 (Sprint 9 Exit 리뷰 및 상태 동기화)
  - 동기화 문서:
    - `docs/full-spec-gap-analysis-2026-02-22.md`
    - `docs/planned-endpoints-priority-backlog-2026-02-21.md`
    - `docs/implementation-plans/program/10_feature-maturity-checklist.md`
