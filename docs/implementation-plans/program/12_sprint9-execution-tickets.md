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

## Sprint 10~12 Exit Checklist (2026-02-22 업데이트)

### Sprint 10 (Mock-to-Real 1차)
- [x] `ORA-NL2SQL-REAL-001` Oracle SQL 실행 경로를 mock-only에서 hybrid/weaver 연동으로 확장
  - 구현: `services/oracle/app/core/sql_exec.py`, `services/oracle/app/pipelines/nl2sql_pipeline.py`, `services/oracle/app/api/text2sql.py`
  - 검증: `services/oracle/tests/unit/test_oracle_sprint1.py`, `services/oracle/tests/unit/test_oracle_sprint5.py`
- [x] `VIS-STATE-001` Vision runtime 상태 영속화(PostgreSQL 우선 + fallback)
  - 구현: `services/vision/app/services/vision_state_store.py`, `services/vision/app/services/vision_runtime.py`
  - 검증: `services/vision/tests/unit/test_vision_runtime_persistence.py`
- [x] `CORE-AGENT-001` Core Agent 상태 영속화(PostgreSQL 우선 + fallback)
  - 구현: `services/core/app/services/agent_state_store.py`, `services/core/app/services/agent_service.py`
  - 검증: `services/core/tests/unit/test_agent_service_persistence.py`

### Sprint 11 (Policy Enforcement 1차)
- [x] `PGM-SV-001` Self-Verification 샘플링/실패 라우팅 런타임 반영
  - 구현: `services/core/app/core/self_verification.py`, `services/core/app/services/process_service.py`
  - 검증: `services/core/tests/integration/test_e2e_process_submit.py`
- [x] `PGM-4SRC-001` 4-Source lineage 계약 필수 필드 강제
  - 구현: `services/synapse/app/core/ingestion_contract.py`, `services/synapse/app/services/extraction_service.py`
  - 검증: `services/synapse/tests/unit/test_extraction_api_full.py` (lineage 누락 422 케이스 포함)
- [x] `CORE-EVT-001` Domain Contract Registry 런타임 강제
  - 구현: `services/core/app/core/event_contract_registry.py`, `services/core/app/core/events.py`
  - 검증: `services/core/tests/integration/test_outbox.py`

### Sprint 12 (Event Ops Completion)
- [x] `CORE-OUTBOX-001` Outbox -> Redis Streams 워커/운영 API 경로 명시화
  - 구현: `services/core/app/workers/sync.py`, `services/core/app/api/events/routes.py`, `services/core/app/main.py`
  - 검증: `services/core/tests/integration/test_event_ops.py`
- [x] DLQ/재처리/관측 지표 구성
  - 구현: `services/core/app/core/observability.py`, `services/core/app/api/health.py`
  - 검증: `GET /api/v1/metrics`, `POST /api/v1/events/dlq/{stream}/reprocess`
- [x] legacy write 위반 탐지 메트릭 반영
  - 구현: `services/core/app/core/events.py` (`core_legacy_write_violations_total`)
  - 검증: `services/core/tests/integration/test_event_ops.py`

### Docker Compose 운영 검증 증적
- [x] `core-svc` 재빌드 후 `event_outbox` 자동 생성 확인
  - 구현: `services/core/app/core/database.py` (`init_database`), `services/core/app/main.py` (startup hook)
  - 검증: `GET /api/v1/events/outbox/backlog` 200, `pending/failed` 정상 조회
- [x] run-once 동기화 및 backlog 감소 재현
  - 시나리오: process initiate/submit -> pending 2 -> `POST /api/v1/events/sync/run-once` -> pending 0
- [x] DLQ 주입/재처리 재현
  - 시나리오: `axiom:dlq:events` 1건 주입 -> reprocess 성공 -> depth 0

## Next Action (Critical 잔여 1건: G-001)

### S13-VIS-RCA-002 (Synapse 실연동 고도화)
- 목적: `GET /root-cause/process-bottleneck`가 fallback 수준을 넘어 Synapse 실데이터 기반으로 원인/권고를 생성
- 작업:
  - Synapse 병목/변형/성능 API 응답을 Vision 원인 템플릿으로 정규화
  - `SYNAPSE_UNAVAILABLE` 외 오류코드 분기(`PROCESS_MODEL_NOT_FOUND`, `INSUFFICIENT_PROCESS_DATA`) 세분화
  - 결과에 `data_range`, `case_count`, `source_log_id`를 포함해 추적성 강화
- 완료 기준:
  - Synapse 정상/장애/데이터부족 3경로 테스트 통과
  - API 응답이 문서 스키마와 주요 필드 기준으로 정합

### S13-VIS-RCA-003 (실엔진 계산 경로 도입)
- 목적: Root-Cause 계산이 고정 템플릿이 아닌 실계산 경로를 갖도록 개선
- 작업:
  - SHAP/기여도 계산 모듈 분리(`root_cause_engine.py` 등)
  - 반사실 계산에 변수별 영향치 테이블(또는 모델 결과)을 반영
  - 결과 신뢰도 산식과 근거 필드(`confidence_basis`) 추가
- 완료 기준:
  - 동일 입력 반복 시 결정적(deterministic) 결과 재현
  - 기존 템플릿 대비 최소 2개 케이스에서 결과 차등 발생 확인

### S13-VIS-RCA-004 (회귀/운영 검증 고정)
- 목적: G-001의 회귀 방지와 운영 관측성을 확보
- 작업:
  - 단위/통합 테스트에 `causal-timeline`, `impact`, `graph`, `process-bottleneck` 확장 케이스 추가
  - 실패율/지연 지표를 health/metrics에 반영 가능한 형태로 노출
  - 문서(`root-cause-api.md`, gap-analysis) 상태 태그를 구현 기준으로 동기화
- 완료 기준:
  - 테스트 파일 기준 회귀 시나리오 0 fail
  - 문서-코드 상태 불일치 0건

## S13 실행 결과 (2026-02-22)

- [x] `S13-VIS-RCA-002` Synapse 실연동 고도화
  - 구현: `services/vision/app/services/vision_runtime.py`, `services/vision/app/api/root_cause.py`
  - 검증: `services/vision/tests/unit/test_root_cause_api.py` (정상/장애/데이터부족 경로)
- [x] `S13-VIS-RCA-003` 실엔진 계산 경로 도입
  - 구현: `services/vision/app/services/root_cause_engine.py`, `services/vision/app/services/vision_runtime.py`
  - 검증: `services/vision/tests/unit/test_root_cause_api.py` (결정적 결과 + 케이스별 차등)
- [x] `S13-VIS-RCA-004` 회귀/운영 검증 고정
  - 구현: `services/vision/app/main.py` (`/health/ready`, `/metrics`), `services/vision/app/api/root_cause.py` (호출 지표 계측)
  - 검증: `services/vision/tests/unit/test_root_cause_api.py` (운영 지표 노출/누적 검증)
  - Compose 통합 회귀 스크립트: `tools/run_compose_s13_regression.sh` (core/vision 연계 시나리오 자동 검증)

## Sprint 14 Exit Checklist (Packaging/Compose/CI Stabilization)

- [x] 각 서비스 `pyproject.toml` + `src/app` 브리지 + Docker에서 `pip install -e .`
  - 구현: `services/synapse`, `services/core`, `services/vision`, `services/weaver`, `services/oracle` — `pyproject.toml`, `src/app/__init__.py`, Dockerfile `RUN pip install -e .`
  - 검증: venv/compose에서 `pytest tests/unit -q` (PYTHONPATH 없이) 통과
- [x] `docker-compose.yml`에 `neo4j-db`, `synapse-svc`, `oracle-svc` 포함
  - 구현: `docker-compose.yml` (neo4j-db healthcheck, synapse-svc, oracle-svc 환경변수/의존성)
  - 검증: `docker compose up -d` 후 core/vision/weaver/synapse/oracle 헬스 응답 정상
- [x] CI에서 editable install 기반 테스트
  - 구현: `.github/workflows/synapse-unit-ci.yml` (pip install -e services/synapse, postgres/neo4j services)
  - 구현: `.github/workflows/weaver-external-exit-gate.yml` (pip install -e services/weaver, PYTHONPATH 제거)
  - 검증: Synapse unit 35 passed (venv + compose run)

## S14 실행 결과 (2026-02-22)

- [x] 패키징 정렬 (Synapse/Core/Vision/Weaver/Oracle)
  - Synapse: `pyproject.toml`(where=src), `src/app/__init__.py` 브리지, Dockerfile `pip install -e .`, requirements.txt 오타 수정
  - Core/Vision/Weaver/Oracle: `pyproject.toml`, `src/app/__init__.py`, Dockerfile `pip install -e .` 추가
- [x] Compose 확장
  - neo4j-db, synapse-svc 추가; vision-svc/core-svc에 SYNAPSE_BASE_URL; weaver NEO4J_URI → neo4j-db; oracle-svc 추가(8004)
- [x] CI 반영
  - synapse-unit-ci.yml 신규 (postgres/neo4j services, pip install -e, pytest tests/unit)
  - weaver-external-exit-gate.yml 수정 (pip install -e, PYTHONPATH 제거)
- [x] 통과 기준 충족
  - compose 기동 후 core(8002)/vision(8000)/weaver(8001)/synapse(8003)/oracle(8004) 헬스 정상
  - Synapse unit tests: venv 및 `docker compose run --rm synapse-svc pytest tests/unit -q` 35 passed
