# 문서-구현 갭 분석 보고서

> 상태: **보관(Outdated Snapshot)**
> 
> 본 문서는 2026-02-21 시점 스냅샷으로, 이후 Core/Oracle/Synapse/Weaver/Vision 라우트 구현 진척을 반영하지 않는다.
> 최신 기준 보고서는 `docs/04_status/full-spec-gap-analysis.md`를 사용한다.

기준일: 2026-02-21  
작성 범위: `docs/`, `services/*/docs`, `apps/canvas/docs` vs 실제 런타임 코드(`services/*/app`, `apps/canvas/src`) 및 테스트(`services/*/tests`, `apps/canvas/tests`)

---

## 1. 목적

본 문서는 Axiom 저장소의 설계/구현 계획 문서와 실제 코드 구현 상태를 대조하여:

1. 문서상 구현 완료로 표기됐으나 실제 코드가 없는 항목
2. 문서 API 계약과 실제 라우트 불일치 항목
3. Sprint/Gate 완료 주장 대비 증적(코드/테스트) 부족 항목

을 식별하고, 우선순위 기반 조치안을 제시한다.

---

## 2. 핵심 결론 (요약)

1. Program 문서에서 D3 완료로 선언된 일부 핵심 기능(Watch/CEP)이 코드 기준으로는 미구현 상태다.
2. 서비스별 API 문서가 실제 구현보다 훨씬 넓어, 계약 문서가 “구현 상태(Implemented/Planned)”를 반영하지 못하고 있다.
3. SSOT(포트/배포) 문서와 실제 `docker-compose.yml`, `k8s/` 매니페스트가 상이하다.
4. Sprint Exit 체크리스트의 완료 표시([x])를 뒷받침하는 코드 증적이 부족한 항목이 다수 존재한다.

---

## 3. 분석 방법

1. SSOT/Program/Sprint/Gate 문서에서 “완료/통과/구현” 주장 추출
2. 서비스별 API 문서에서 엔드포인트 목록 추출
3. 실제 FastAPI 라우트/프론트 API 호출 경로/테스트 코드와 1:1 비교
4. 심각도 분류

- `Critical`: 문서가 완료라고 주장하나 런타임 핵심 경로가 부재, 또는 SSOT 불일치로 운영 혼선 위험 높음
- `High`: 핵심 API 계약 대량 불일치, Sprint/Gate 신뢰도 저하
- `Medium`: 증적 강도 부족, 테스트 범위 불충분

---

## 4. 상세 갭 목록

## 4.1 Critical

### G-001. Watch/CEP D3 완료 주장 vs Core 구현 부재

- 문서 근거
  - `docs/03_implementation/program/10_feature-maturity-checklist.md:28`
  - `docs/03_implementation/program/10_feature-maturity-checklist.md:29`
  - `docs/03_implementation/program/10_feature-maturity-checklist.md:65`
  - `docs/03_implementation/program/10_feature-maturity-checklist.md:66`
  - `services/core/docs/02_api/watch-api.md:18`
- 실제 코드
  - Core 라우터 등록은 `health`, `process`만 존재: `services/core/app/main.py:25`, `services/core/app/main.py:26`
  - Watch 라우트 파일/등록 부재
  - Canvas는 Watch API 호출 중: `apps/canvas/src/lib/api/watch.ts:5`, `apps/canvas/src/lib/api/watch.ts:10`, `apps/canvas/src/lib/api/watch.ts:14`
- 판정
  - 문서 기준 D3 완료 주장과 런타임 구현이 정면 충돌
- 영향
  - 프론트 알림 기능 실패
  - Sprint 7 FM-005/FM-006 완료 신뢰도 저하

### G-002. SSOT 포트/배포 정의 vs 실제 Compose/K8s 불일치

- 문서 근거
  - SSOT 포트: `docs/02_api/service-endpoints-ssot.md:20`~`docs/02_api/service-endpoints-ssot.md:25`
  - Docker/K8s 포함 공식 아키텍처: `docs/02_api/service-endpoints-ssot.md:47`~`docs/02_api/service-endpoints-ssot.md:56`
- 실제 코드
  - Compose는 Vision/Weaver/Canvas/Redis만 포함: `docker-compose.yml:16`, `docker-compose.yml:29`, `docker-compose.yml:41`
  - Core/Oracle/Synapse compose 서비스 부재
  - Vision 포트 불일치(SSOT 8400 vs compose 8000): `docs/02_api/service-endpoints-ssot.md:24` vs `docker-compose.yml:21`
  - K8s도 Vision/Weaver/Canvas/Redis만 존재: `k8s/deployments.yaml:1`, `k8s/deployments.yaml:26`, `k8s/deployments.yaml:51`, `k8s/deployments.yaml:76`
- 판정
  - SSOT가 실제 배포 파일과 동기화되지 않음
- 영향
  - 환경 변수/포트 혼선, 온보딩/운영 실패 가능성 증가

---

## 4.2 High

### G-003. Core Process API 문서 대비 구현 축소

- 문서 근거
  - 10개 엔드포인트 명시: `services/core/docs/02_api/process-api.md:18`~`services/core/docs/02_api/process-api.md:27`
- 실제 코드
  - `/process/submit` 단일 구현: `services/core/app/api/process/routes.py:13`
- 누락 예시
  - `/initiate`, `/role-binding`, `/rework`, `/approve-hitl`, `/definitions` 등
- 영향
  - Process API 계약 기반 클라이언트/테스트 작성 시 대규모 실패

### G-004. Core Gateway/Agent/MCP 문서 대비 구현 부재

- 문서 근거
  - Gateway 보호 경로: `services/core/docs/02_api/gateway-api.md:45`~`services/core/docs/02_api/gateway-api.md:57`
  - SSE/WebSocket 경로: `services/core/docs/02_api/gateway-api.md:75`~`services/core/docs/02_api/gateway-api.md:79`
  - Agent/MCP API: `services/core/docs/02_api/agent-api.md:18`~`services/core/docs/02_api/agent-api.md:27`
- 실제 코드
  - 관련 라우트 미구현 (main 등록 기준)
  - 문서가 지목한 구현 파일도 부재:
    - `services/core/app/core/routes.py` (missing)
    - `services/core/app/core/security.py` (missing)
    - `services/core/app/core/rate_limiter.py` (missing)
- 영향
  - Core를 API Gateway로 전제한 전체 문서 체계의 실행 가능성 하락

### G-005. Oracle Meta/Events API 미구현

- 문서 근거
  - Meta API: `services/oracle/docs/02_api/meta-api.md:18`~`services/oracle/docs/02_api/meta-api.md:22`
  - Events API: `services/oracle/docs/02_api/events-api.md:28`~`services/oracle/docs/02_api/events-api.md:37`
- 실제 코드
  - Oracle 등록 라우트는 text2sql/health/feedback만: `services/oracle/app/main.py:10`~`services/oracle/app/main.py:12`
  - text2sql 실제 엔드포인트: `services/oracle/app/api/text2sql.py:37`, `services/oracle/app/api/text2sql.py:51`, `services/oracle/app/api/text2sql.py:66`
  - feedback 엔드포인트: `services/oracle/app/api/feedback.py:13`
- 영향
  - Sprint4 O1/O2/O3 및 API 계약 100% 통과 주장 검증 곤란

### G-006. Synapse Gate S1 대상 API 대규모 누락

- 문서 근거
  - Gate S1 요구: extraction/event-log/process-mining/schema-edit API 계약 100%: `docs/03_implementation/synapse/98_gate-pass-criteria.md:9`
  - Extraction API 목록: `services/synapse/docs/02_api/extraction-api.md:29`~`services/synapse/docs/02_api/extraction-api.md:36`
  - Event-log API 목록: `services/synapse/docs/02_api/event-log-api.md:33`~`services/synapse/docs/02_api/event-log-api.md:40`
  - Schema-edit API 목록: `services/synapse/docs/02_api/schema-edit-api.md:29`~`services/synapse/docs/02_api/schema-edit-api.md:37`
- 실제 코드
  - ontology stub + mining 일부 + graph 일부만 존재: `services/synapse/app/api/ontology.py:5`, `services/synapse/app/api/ontology.py:9`, `services/synapse/app/api/mining.py:7`, `services/synapse/app/api/mining.py:23`, `services/synapse/app/api/mining.py:36`, `services/synapse/app/api/mining.py:48`
  - process-mining 문서의 `/performance`도 누락: `services/synapse/docs/02_api/process-mining-api.md:39`
- 영향
  - Sprint3 플랫폼 완료 주장과 실구현 간 간극 큼

### G-007. Vision What-if/OLAP API 문서 대비 구현 축소

- 문서 근거
  - What-if 다중 엔드포인트: `services/vision/docs/02_api/what-if-api.md:47`~`services/vision/docs/02_api/what-if-api.md:60`
  - OLAP 다중 엔드포인트: `services/vision/docs/02_api/olap-api.md:34`~`services/vision/docs/02_api/olap-api.md:43`
- 실제 코드
  - `/analytics/execute`, `/analytics/what-if` 2개만 제공: `services/vision/app/api/analytics.py:22`, `services/vision/app/api/analytics.py:27`
  - main 라우트 등록도 analytics 단일: `services/vision/app/main.py:6`
- 영향
  - Vision V1/V2 “주요 항목 통과” 문구의 증적 부족

### G-008. Weaver Metadata/Catalog/API 문서 대비 구현 축소

- 문서 근거
  - Metadata Catalog API base: `services/weaver/docs/02_api/metadata-catalog-api.md:39`
  - Catalog 엔드포인트 다수: `services/weaver/docs/02_api/metadata-catalog-api.md:75`~`services/weaver/docs/02_api/metadata-catalog-api.md:80`
  - Datasource API 다수: `services/weaver/docs/02_api/datasource-api.md:19`~`services/weaver/docs/02_api/datasource-api.md:31`
  - Query API 다수: `services/weaver/docs/02_api/query-api.md:20`~`services/weaver/docs/02_api/query-api.md:25`
- 실제 코드
  - datasource: create/sync만 구현: `services/weaver/app/api/datasource.py:12`, `services/weaver/app/api/datasource.py:17`
  - query: execute 단일: `services/weaver/app/api/query.py:16`
  - main 등록 라우터 2개만: `services/weaver/app/main.py:7`, `services/weaver/app/main.py:8`
- 영향
  - W1/W2 계약 범위 대비 구현 부족

---

## 4.3 Medium

### G-009. Sprint Exit 체크 완료 표시 대비 코드 증적 약함

- 문서 근거
  - Sprint 7 Exit 체크 완료: `docs/03_implementation/program/08_sprint7-execution-tickets.md:18`~`docs/03_implementation/program/08_sprint7-execution-tickets.md:23`
  - D3 증적 규칙: Gate 증적 + 운영 지표 캡처 + 회귀 테스트: `docs/03_implementation/program/10_feature-maturity-checklist.md:75`~`docs/03_implementation/program/10_feature-maturity-checklist.md:78`
- 실제 코드
  - 일부 테스트는 스모크/스텁 중심
  - 예: 멀티테넌트 미들웨어 테스트가 실제 tenant 반영값을 검증하지 못한다고 주석 명시: `services/core/tests/unit/test_middleware.py:14`~`services/core/tests/unit/test_middleware.py:16`
- 영향
  - “완료” 상태의 신뢰도 저하, 감사/릴리스 근거 부족

---

## 5. Sprint/Gate 관점 정리

## 5.1 Program Sprint 7

- 문서상 상태
  - `S7-PGM-005`, `S7-PGM-006` 완료로 표기: `docs/03_implementation/program/08_sprint7-execution-tickets.md:13`, `docs/03_implementation/program/08_sprint7-execution-tickets.md:14`
- 실제 판정
  - Watch/CEP 핵심 라우트 자체가 부재하여 완료 판정 재검증 필요

## 5.2 Core Gate C1/C2

- 문서상 기준
  - Watch/Agent/Gateway 권한 누락 엔드포인트 0건: `docs/03_implementation/core/98_gate-pass-criteria.md:11`
- 실제 판정
  - 해당 API 대다수 자체가 미구현 상태라 “누락 0건” 판정이 성립 어려움

## 5.3 Synapse Gate S1

- 문서상 기준
  - extraction/event-log/schema-edit 포함 계약 100%: `docs/03_implementation/synapse/98_gate-pass-criteria.md:9`
- 실제 판정
  - 해당 API 그룹 대부분 미구현

---

## 6. 조치 우선순위 (권고)

## 6.1 P0 (즉시, 1~2일)

1. Program 문서 상태를 현실화
   - `D3 완료` -> `D2 진행` 또는 `Experimental`로 즉시 조정 (Watch/CEP 관련)
2. API 문서에 상태 태그 추가
   - 각 엔드포인트에 `Implemented | Stub | Planned` 표시
3. SSOT 포트/배포 동기화
   - SSOT를 compose/k8s에 맞추거나, compose/k8s를 SSOT에 맞춰 수정

## 6.2 P1 (단기, 1주)

1. Core Watch 최소 기능 구현
   - `/api/v1/watches/alerts`
   - `/api/v1/watches/alerts/{id}/acknowledge`
   - `/api/v1/watches/alerts/read-all`
   - Canvas 연동 우선 복구
2. Synapse 누락 API 최소 뼈대 추가
   - event-log, extraction, schema-edit 경로만이라도 계약 수준으로 노출
3. Oracle meta/events 라우트 추가
   - 문서와 최소 정합 확보

## 6.3 P2 (중기, 2~4주)

1. Vision OLAP/What-if 실제 CRUD/compute 경로 확장
2. Weaver metadata catalog API 확장
3. Gate 증적 자동화
   - “문서 완료 체크”와 “코드/테스트 존재”를 CI에서 자동 대조

---

## 7. 권장 운영 규칙 (재발 방지)

1. “완료 체크([x], D3)”는 다음 3조건 동시 만족 시에만 허용
   - 라우트/핵심 코드 존재
   - 계약 테스트 존재
   - 운영 관측 지표 증적 링크 존재
2. API 문서는 반드시 엔드포인트 상태 태깅
   - `Implemented`가 아니면 샘플 응답 앞에 명시
3. Sprint Exit 템플릿에 자동 증적 링크 필수화
   - 코드 파일, 테스트 파일, 실행 로그, 대시보드 캡처

---

## 8. 참고 증적 파일

- Program/Feature 성숙도: `docs/03_implementation/program/10_feature-maturity-checklist.md`
- Sprint 7 보드: `docs/03_implementation/program/08_sprint7-execution-tickets.md`
- SSOT: `docs/02_api/service-endpoints-ssot.md`
- Core 구현 엔트리: `services/core/app/main.py`
- Core Watch 문서: `services/core/docs/02_api/watch-api.md`
- Canvas Watch 호출: `apps/canvas/src/lib/api/watch.ts`
- Oracle 구현 엔트리: `services/oracle/app/main.py`
- Synapse 구현 엔트리: `services/synapse/app/main.py`
- Vision 구현 엔트리: `services/vision/app/main.py`
- Weaver 구현 엔트리: `services/weaver/app/main.py`
