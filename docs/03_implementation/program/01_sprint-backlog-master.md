# Axiom 통합 스프린트 백로그 (Master)

## 1. 운영 원칙
- 스프린트 길이: 2주
- 완료 정의(DoD): 코드 + 테스트 + 문서 + Gate 체크리스트 충족
- 품질게이트: `lint + type + unit + integration + security` 필수
- 계약 우선: API/OpenAPI 변경은 구현 전 승인

## 2. 프로그램 스프린트 로드맵

### Sprint 1 (Foundation)
- 목표: SSOT/경계/공통 규칙 고정
- 범위: Core 00/01/02, Synapse 01, Oracle 01, Canvas 01
- 핵심 산출물:
  - 서비스 경계 고정 문서/검증 스크립트
  - 공통 에러 모델/권한 모델/포트 SSOT 적용
- 통과 기준:
  - 아키텍처 경계 위반 0건
  - 계약 변경 승인 프로세스 동작 확인

### Sprint 2 (Core Runtime)
- 목표: Core 프로세스/이벤트/보안 런타임 안정화
- 범위: Core 02/03/06/07/08
- 핵심 산출물:
  - 프로세스/워크아이템 상태전이 회귀 테스트
  - Outbox->Streams 멱등성 검증
  - 멀티테넌트 격리 검증 리포트
- 통과 기준:
  - Core Gate C1/C2 주요 항목 통과

### Sprint 3 (Graph Platform)
- 목표: Synapse + Weaver 그래프/메타데이터 기반 완성
- 범위: Synapse 02/03/06, Weaver 02/03/06/07
- 핵심 산출물:
  - 온톨로지/그래프 API 계약 테스트
  - metadata ingest/propagation 정합성 테스트
  - 4-Source Ingestion 계보 필드(`source_family/source_ref`) 저장 검증
- 통과 기준:
  - Synapse/Weaver Gate S1/W1 통과

### Sprint 4 (Oracle Intelligence)
- 목표: Oracle NL2SQL/품질게이트/보안 정책 구현
- 범위: Oracle 02/03/05/06/07
- 핵심 산출물:
  - SQL Guard + Quality Gate + Value Mapping 파이프라인
  - Synapse API 경유 그래프 검색/캐시 반영
- 통과 기준:
  - Oracle Gate O1/O2/O3 통과

### Sprint 5 (Vision Analytics)
- 목표: Vision 엔진(OLAP/What-if) API 안정화
- 범위: Vision 02/03/05/06/08
- 핵심 산출물:
  - 분석 API 계약 테스트 + 비동기 실행 안정화
  - ETL/MV 갱신 및 성능 검증
  - What-if 질문 템플릿(골든퀘션) 카탈로그 초안
- 통과 기준:
  - Vision Gate V1/V2 주요 항목 통과

### Sprint 6 (Canvas Integration)
- 목표: Canvas 기능 통합 및 E2E 안정화
- 범위: Canvas 02/03/04/06/07/08
- 핵심 산출물:
  - 핵심 사용자 여정 E2E 세트
  - 실시간 알림/협업/분석 연동 검증
- 통과 기준:
  - Canvas Gate U1/U2/U3 통과

### Sprint 7 (Hardening)
- 목표: 전 프로젝트 보안/성능/운영 하드닝
- 범위: 전 프로젝트 07/08/99
- 핵심 산출물:
  - 침투/부하/복구 리허설 결과
  - ADR 재평가 트리거 점검
  - Early Warning 폐루프 SLA(`detect->RCA->notify->resolve`) 검증 리포트
- 통과 기준:
  - Critical/High 취약점 0
  - 운영 리허설 완료

### Sprint 8 (API Alignment Recovery)
- 목표: 문서-구현 API 정합성 복구 및 우선순위 엔드포인트 구현 착수
- 범위: Core/Synapse/Oracle/Vision/Weaver API 갭 P0/P1
- 핵심 산출물:
  - 서비스별 `87_sprint8-ticket-board.md` 기준 P0 티켓 구현/검증
  - API 문서 상태(Implemented/Partial/Planned)와 근거(코드/티켓) 동기화
  - 프로그램 실행 티켓 문서 `11_sprint8-execution-tickets.md` 기준 통합 추적
- 통과 기준:
  - P0 엔드포인트 계약 테스트 통과
  - 서비스별 스프린트 보드 진행률 및 근거 링크 최신화

### Sprint 9 (Full Spec P0 Start)
- 목표: Full Spec Critical 갭 착수 (Root-Cause/Auth/SSOT 운영 정합)
- 범위: Vision Root-Cause 최소 API, Canvas 실제 인증 1차, SSOT 정합 자동 점검
- 핵심 산출물:
  - `docs/03_implementation/program/12_sprint9-execution-tickets.md` 기준 P0 티켓 수행
  - Critical 갭 항목의 코드/문서 상태 동기화
  - Full Spec 리그레션 템플릿(Critical) 수립
- 통과 기준:
  - Root-Cause 최소 엔드포인트 동작 + 테스트 통과
  - Canvas 인증 만료/갱신 E2E 시나리오 통과
  - SSOT 불일치 자동 검출 가능

### Sprint 10 (Mock-to-Real 1차)
- 목표: mock/in-memory 핵심 경로의 실연동 전환 시작
- 범위: Oracle NL2SQL, Vision runtime state, Core Agent/MCP 영속화 1차
- 통과 기준:
  - mock 기반 고정 응답 의존 경로 축소가 코드/테스트로 증명됨

### Sprint 11 (Policy Enforcement 1차)
- 목표: Self-Verification/4-Source/Contract Registry 정책 런타임 적용
- 범위: `PGM-SV-001`, `PGM-4SRC-001`, `CORE-EVT-001`
- 통과 기준:
  - 필수 정책 위반 시 reject 또는 fail-routing이 재현됨

### Sprint 12 (Event Ops Completion)
- 목표: 이벤트 파이프라인 운영 완성 및 위반 탐지 폐루프 마감
- 범위: `CORE-OUTBOX-001`, DLQ/재처리/관측 지표, legacy write 탐지
- 통과 기준:
  - Outbox backlog SLA, DLQ 재처리 성공률, legacy 위반 탐지 지표 확인

### Sprint 13 (Vision Root-Cause Fullspec Completion)
- 목표: Critical `G-001`(Vision Root-Cause) 완전 구현
- 범위: `S13-VIS-RCA-002`, `S13-VIS-RCA-003`, `S13-VIS-RCA-004`
- 핵심 산출물:
  - Synapse 실연동 병목 RCA + 오류코드 세분화(`SYNAPSE_UNAVAILABLE`, `PROCESS_MODEL_NOT_FOUND`, `INSUFFICIENT_PROCESS_DATA`)
  - SHAP/Counterfactual 실계산 경로 + `confidence_basis` 응답
  - Root-Cause 운영 지표(`/health/ready`, `/metrics`) 및 compose 회귀 스크립트
- 통과 기준:
  - `services/vision/tests/unit/test_root_cause_api.py` 회귀 통과
  - `tools/run_compose_s13_regression.sh` 시나리오 통과

### Sprint 14 (Packaging/Compose/CI Stabilization) — 완료
- 목표: 서비스별 import/실행 안정성 표준화(`src` + editable install)
- 범위: Synapse/Core/Vision/Weaver/Oracle 패키징 정렬, Compose 서비스 확장, CI 반영
- 핵심 산출물:
  - 각 서비스 `pyproject.toml` + `src/app` 브리지 + `pip install -e .` Docker 적용
  - `docker-compose.yml`에 `neo4j-db`, `synapse-svc`, `oracle-svc` 포함
  - CI에서 editable install 기반 테스트(`synapse-unit-ci.yml`, weaver gate 정렬)
- 통과 기준:
  - compose 환경에서 core/vision/weaver/synapse/oracle 헬스 응답 정상
  - Synapse unit tests venv/compose 양쪽 통과
- 완료: 2026-02-22 (증적: `12_sprint9-execution-tickets.md` Sprint 14 Exit Checklist 및 S14 실행 결과)

## 3. 크로스 의존성 차단 규칙
- Oracle은 Synapse API 가용 전 독립 완료로 인정하지 않음
- Canvas E2E 완료는 Core/Oracle/Synapse/Vision/Weaver 계약 테스트 통과가 선행
- ADR 변경은 해당 스프린트 시작 전에 `99_decisions` 반영 필수

## 4. 리스크 버퍼
- 스프린트당 20% 버퍼(계약 변경/데이터 이슈/성능 회귀)
- 운영 리스크(배포/롤백)는 Sprint 7 이전에 최소 1회 예행
