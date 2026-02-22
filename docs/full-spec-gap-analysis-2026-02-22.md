# 문서-코드 Full Spec 갭 분석 보고서 (2026-02-22)

기준일: 2026-02-22  
작성자: Codex (coding-standard 기준 적용)  
범위: `docs/`, `docs/implementation-plans/`, `services/*/docs`, `apps/canvas/docs` 대비 `services/*/app`, `apps/canvas/src`

## 1. 검토 범위 및 방법

### 1.1 검토 범위(문서 수)
- top-level 문서(`docs/*.md`): 10개
- 서비스 설계 문서(`services/*/docs/**/*.md`): 160개
- Canvas 설계 문서(`apps/canvas/docs/**/*.md`): 36개
- 구현계획 문서(`docs/implementation-plans/**/*.md`): 145개

### 1.2 판정 기준
- `Implemented`: 라우트/핵심 로직/기본 테스트가 존재하고 mock-only가 아님
- `Partial`: 라우트는 있으나 핵심 로직이 스텁/메모리/mock 중심
- `Not Implemented`: 설계 문서에 있으나 런타임 코드 경로가 없음

### 1.3 핵심 결론
- P0/P1 엔드포인트 복구는 상당수 완료됨(특히 Core Watch/Process, Synapse Extraction/Event-Log, Oracle Meta, Core Gateway).
- 그러나 "full spec" 기준(실연동/운영성/아키텍처 정책 준수)으로는 주요 영역이 아직 `Partial` 또는 `Not Implemented`.
- 가장 큰 갭은 `Self-Verification Harness`, `4-Source Lineage 강제`, `mock/in-memory 실행 경로의 실연동 전환`.

### 1.4 Sprint 9 델타 (2026-02-22)
- `G-001 Root-Cause`: `Not Implemented -> Partial` (최소 API 4종 + 테스트 추가)
- `G-004 SSOT 정합`: `Partial` 유지, 단 수동점검에서 자동검증(`tools/validate_ssot.py`)으로 개선
- `G-009 Canvas auth`: `Partial` 유지, 단 `ProtectedRoute` 우회 제거 + refresh flow 1차 구현으로 리스크 축소

---

## 2. Full Spec 미구현/부분구현 항목

## 2.1 Critical

### G-001. Vision Root-Cause API 설계 대비 부분구현 (Partial)
- 설계 근거
  - `services/vision/docs/02_api/root-cause-api.md:1`
  - `services/vision/docs/02_api/root-cause-api.md:4`
  - `services/vision/docs/02_api/root-cause-api.md:48`
- 코드 근거
  - Root-Cause 라우터 등록: `services/vision/app/main.py:4`, `services/vision/app/main.py:11`
  - 확장 API 구현(`causal-timeline`, `root-cause-impact`, `causal-graph`, `process-bottleneck`): `services/vision/app/api/root_cause.py:1`
  - 런타임 처리 확장: `services/vision/app/services/vision_runtime.py:227`
  - 단위 테스트 확장: `services/vision/tests/unit/test_root_cause_api.py:1`
- 판정: Partial (API 경로는 구현 완료, Synapse 실연동/실엔진 계산 고도화는 잔여)

### G-002. Self-Verification Harness 전사 정책 1차 구현 (Implemented)
- 설계 근거
  - `docs/architecture-self-verification.md:1`
  - `docs/architecture-self-verification.md:7`
  - `docs/architecture-self-verification.md:23`
- 코드 근거
  - Self-Verification 런타임/샘플링: `services/core/app/core/self_verification.py:1`
  - submit 경로 fail-routing: `services/core/app/services/process_service.py:300`
  - 통합 검증: `services/core/tests/integration/test_e2e_process_submit.py:1`
- 판정: Implemented (1차, Core process 경로 기준)

### G-003. 4-Source Ingestion lineage 필수 메타 1차 강제 (Implemented)
- 설계 근거
  - `docs/architecture-4source-ingestion.md:1`
  - `docs/architecture-4source-ingestion.md:48`
  - `docs/architecture-4source-ingestion.md:49`
- 코드 근거
  - lineage 계약 검증기: `services/synapse/app/core/ingestion_contract.py:1`
  - extraction 시작 시 필수 검증/422 reject: `services/synapse/app/services/extraction_service.py:141`
  - 위반 케이스 테스트: `services/synapse/tests/unit/test_extraction_api_full.py:106`
- 판정: Implemented (1차, Synapse extraction 경로 기준)

### G-004. SSOT 배포 아키텍처 Runtime-Active 정합 구현 (Implemented)
- 설계 근거
  - `docs/service-endpoints-ssot.md:21`
  - `docs/service-endpoints-ssot.md:25`
  - `docs/service-endpoints-ssot.md:48`
- 코드/배포 근거
  - Compose runtime-active 서비스: `docker-compose.yml:1`
  - K8s runtime-active 서비스(Core/Postgres 포함) 반영: `k8s/deployments.yaml:1`, `k8s/services.yaml:1`
  - SSOT 동기화 및 매핑 검증 강화: `docs/service-endpoints-ssot.md:1`, `tools/validate_ssot.py:1`
  - 검증 결과: `python3 tools/validate_ssot.py` 통과
- 판정: Implemented (Runtime-Active 프로파일 기준)

## 2.2 High

### G-005. Oracle NL2SQL이 문서상 Implemented이나 실질 mock 파이프라인 (Partial)
- 설계 근거
  - `services/oracle/docs/02_api/text2sql-api.md:1`
- 코드 근거
  - 고정 mock 질의 기반 생성: `services/oracle/app/pipelines/nl2sql_pipeline.py:15`, `services/oracle/app/pipelines/nl2sql_pipeline.py:17`, `services/oracle/app/pipelines/nl2sql_pipeline.py:18`
  - SQL 실행 mock latency/결과: `services/oracle/app/core/sql_exec.py:23`, `services/oracle/app/core/sql_exec.py:25`, `services/oracle/app/core/sql_exec.py:36`
  - 인증도 mock token 기본값: `services/oracle/app/api/text2sql.py:12`
- 판정: Partial

### G-006. Vision What-if/OLAP 라우트는 존재하나 in-memory/mock 중심 (Partial)
- 설계 근거
  - `services/vision/docs/02_api/what-if-api.md:1`
  - `services/vision/docs/02_api/olap-api.md:1`
- 코드 근거
  - mock token 기반 인증: `services/vision/app/api/what_if.py:19`, `services/vision/app/api/olap.py:26`
  - OLAP generated_sql placeholder/샘플 반환: `services/vision/app/api/olap.py:129`, `services/vision/app/api/olap.py:156`
  - What-if 상태/결과 저장은 메모리 런타임(dict): `services/vision/app/services/vision_runtime.py:14`, `services/vision/app/services/vision_runtime.py:28`, `services/vision/app/services/vision_runtime.py:68`
  - Analytics는 명시적 stub: `services/vision/app/api/analytics.py:24`, `services/vision/app/api/analytics.py:32`
- 판정: Partial

### G-007. Core Agent/MCP가 영속/실연동 없는 메모리 서비스 중심 (Partial)
- 설계 근거
  - `services/core/docs/02_api/agent-api.md:1`
- 코드 근거
  - 피드백/지식/MCP 상태를 tenant별 메모리 dict로 관리: `services/core/app/services/agent_service.py:24`, `services/core/app/services/agent_service.py:25`, `services/core/app/services/agent_service.py:26`
- 판정: Partial

### G-008. Synapse Conformance Checker가 고정 결과 반환 스텁 (Partial)
- 설계 근거
  - `services/synapse/docs/02_api/process-mining-api.md:1`
- 코드 근거
  - 스텁 주석과 고정 점수 반환: `services/synapse/app/mining/conformance_checker.py:32`, `services/synapse/app/mining/conformance_checker.py:43`, `services/synapse/app/mining/conformance_checker.py:48`
- 판정: Partial

### G-009. Canvas가 인증/핵심 화면에서 부분적 mock 흐름 유지 (Partial)
- 설계 근거
  - `apps/canvas/docs/04_frontend/feature-priority-matrix.md:1`
- 코드 근거
  - 보호 라우트 우회 제거: `apps/canvas/src/components/ProtectedRoute.tsx:6`
  - refresh token 호출 구현: `apps/canvas/src/stores/authStore.ts:40`
  - API 클라이언트 mock token 제거: `apps/canvas/src/lib/api-client.ts:17`
  - 단, 개발 편의 fallback(mock)은 env 기반으로 선택 가능: `apps/canvas/src/pages/auth/LoginPage.tsx:16`
  - 주요 페이지 placeholder/mock: `apps/canvas/src/pages/process/ProcessDesigner.tsx:17`, `apps/canvas/src/pages/ontology/OntologyBrowser.tsx:12`
- 판정: Partial

## 2.3 Medium

### G-010. Outbox -> Redis Streams 운영 경로 1차 구현 (Implemented)
- 설계 근거
  - `services/core/docs/99_decisions/ADR-004-redis-streams-event-bus.md:92`
  - `services/core/docs/06_data/outbox-checklist.md:7`
- 코드 근거
  - Outbox insert: `services/core/app/core/events.py:1`
  - Sync worker(run-once/loop): `services/core/app/workers/sync.py:1`
  - 운영 API(backlog/retry/dlq/reprocess): `services/core/app/api/events/routes.py:1`
  - Docker Compose 실검증: run-once 이후 pending 감소 및 DLQ 재처리 성공 재현
- 판정: Implemented (1차, Core 이벤트 운영 경로 기준)

### G-011. Legacy Read-only 정책을 강제 검증하는 가드/정책 엔진 부재 (Partial)
- 설계 근거
  - `docs/legacy-data-isolation-policy.md:10`
- 코드 근거
  - 정책 위반 탐지 메트릭 추가: `services/core/app/core/events.py:1` (`core_legacy_write_violations_total`)
  - 다만 read-only 연결 강제/위반 차단을 전 서비스에 공통 적용하는 중앙 가드는 여전히 부재
- 판정: Partial

---

## 3. 구현 완료로 판단된 영역 (요약)

다음 영역은 기존 갭 문서 대비 실구현 증거가 확인됨.
- Core Watch/Process/Agent/Gateway 라우터 등록: `services/core/app/main.py:29`, `services/core/app/main.py:30`, `services/core/app/main.py:31`, `services/core/app/main.py:32`
- Oracle Meta/Events 라우터 등록: `services/oracle/app/main.py:15`, `services/oracle/app/main.py:16`
- Synapse Event-Log/Extraction/Schema-Edit/Mining 라우터 등록: `services/synapse/app/main.py:30`, `services/synapse/app/main.py:31`, `services/synapse/app/main.py:32`, `services/synapse/app/main.py:33`
- Weaver Datasource/Query/Metadata Catalog 라우터 등록: `services/weaver/app/main.py:28`, `services/weaver/app/main.py:29`, `services/weaver/app/main.py:30`

---

## 4. 구현 계획 (실행 우선순위)

## 4.1 Phase A (P0, 1~2주): 운영 리스크 제거
1. Vision Root-Cause 최소 API 골격 구현
- 범위: `/root-cause-analysis`, `/root-cause-analysis/status`, `/root-causes`, `/counterfactual`
- 완료조건: 라우트 + 서비스 계층 + 최소 단위/통합 테스트 + 상태태그 `Implemented/Partial` 정합

2. Canvas 인증 실전화
- 범위: `ProtectedRoute` 강제 인증, refresh token 플로우 구현, mock token 제거
- 완료조건: 로그인/만료/갱신 E2E 3시나리오 통과

3. SSOT-배포 파일 동기화
- 범위: `docs/service-endpoints-ssot.md`와 `docker-compose.yml`, `k8s/*.yaml` 단일 기준 정렬
- 완료조건: 포트/서비스 목록 불일치 0건

## 4.2 Phase B (P1, 2~4주): mock -> 실제 런타임 전환
1. Oracle NL2SQL 실연동
- 작업: 실제 schema retrieval, SQL generation 파이프라인, 실행엔진 연결, mock 제거
- 완료조건: `/ask`, `/react`, `/direct-sql`이 샘플 고정값 없이 실제 datasource 결과 반환

2. Vision What-if/OLAP 영속화
- 작업: `VisionRuntime` 메모리 저장소를 DB 기반으로 교체, ETL/job 상태 영속화
- 완료조건: 프로세스 재시작 후 시나리오/큐브/ETL 상태 보존

3. Core Agent/MCP 영속화 및 외부 MCP 연동 강화
- 작업: feedback/knowledge 저장소 DB화, MCP 실행 결과 감사로그/재시도 정책
- 완료조건: 메모리 리셋 없이 상태 유지 + 실패 재처리 가능

## 4.3 Phase C (P1~P2, 3~5주): 아키텍처 정책 구현
상태: `PGM-SV-001`, `PGM-4SRC-001`, `CORE-EVT-001` 1차 구현 완료 (Sprint 11).

1. Self-Verification Harness 구현
- 작업: 20% 샘플링 validator, fail routing, HITL queue 연결, KPI 수집
- 완료조건: `self-check pass/fail`, `HITL routing rate` 대시보드 노출

2. 4-Source lineage 메타 강제
- 작업: 공통 ingestion contract(`source_origin`, `lineage_path`, `idempotency_key`) 검증 미들웨어
- 완료조건: 필수 필드 누락 이벤트/레코드 reject + CI 계약 테스트 추가

3. Domain Contract Registry 실행 강제
- 작업: outbox insert 시 registry 검증(이벤트명/버전/idempotency rule)
- 완료조건: 비등록 이벤트 DB 반영 차단

## 4.4 Phase D (P2, 2~3주): 이벤트 파이프라인 운영 완성
상태: `CORE-OUTBOX-001` 1차 구현 완료 (Sprint 12), 운영 지표/재처리 API 포함.

1. Outbox -> Redis Streams 퍼블리셔 워커 명시적 운영 경로 추가
2. Consumer Group, 재처리, DLQ, 관측 지표 구성
3. 정책 위반(legacy write) 탐지 규칙 추가

완료조건:
- Outbox pending backlog SLA 충족
- DLQ 재처리 성공률 목표 달성
- legacy read-only 위반 탐지 0건

---

## 5. 권고 티켓 분해 (즉시 생성 권장)

1. `VIS-RCA-001` Root-Cause API 최소 구현
2. `CAN-AUTH-001` Canvas real auth/refresh 적용
3. `PGM-SSOT-001` SSOT-Compose-K8s 동기화
4. `ORA-NL2SQL-REAL-001` Oracle mock 제거 1차
5. `VIS-STATE-001` Vision runtime 영속화
6. `CORE-AGENT-001` Agent knowledge/feedback DB화
7. `PGM-SV-001` Self-Verification Harness 구현
8. `PGM-4SRC-001` 4-source lineage contract 강제
9. `CORE-EVT-001` Domain contract registry runtime enforcement
10. `CORE-OUTBOX-001` Outbox publisher/consumer 운영 경로 완성

---

## 6. 요약
- "엔드포인트 존재 여부" 관점의 미구현은 크게 줄었음.
- "full spec(실연동/운영/정책)" 관점에서 잔여 핵심 갭은 7건(Critical 1, High 5, Medium 1)으로 축소됨.
- 우선순위는 `Root-Cause + Auth + SSOT` -> `mock 제거` -> `Self-Verification/4-source/contract enforcement` 순으로 진행하는 것이 리스크 대비 효과가 가장 큼.
