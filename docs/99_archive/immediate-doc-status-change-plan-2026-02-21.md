# 즉시 수정 문서 목록 (상태값 변경안)

기준일: 2026-02-21  
근거 보고서: `docs/99_archive/gap-analysis-docs-vs-implementation-2026-02-21.md`

---

## 1. 변경 원칙

1. 코드/라우트/테스트 증적이 없는 완료 표기는 즉시 하향 조정
2. “완료([x], D3)”는 구현 증적이 확인될 때만 유지
3. SSOT는 실제 배포 파일과 불일치 시 `Accepted` 유지 금지

---

## 2. 즉시 수정 대상 (P0)

| 우선순위 | 문서 | 현재 상태 | 제안 상태 | 변경 이유 |
|---|---|---|---|---|
| P0 | `docs/03_implementation/program/10_feature-maturity-checklist.md` | Watch Agent: `D3 완료`, CEP: `D3 완료` | Watch/CEP 모두 `D2 진행` 또는 `재검증 필요` | Core에 `/api/v1/watches/*` 및 CEP 경로 구현 부재 |
| P0 | `docs/03_implementation/program/10_feature-maturity-checklist.md` | FM-005, FM-006 단계 `D3` | FM-005, FM-006 `D2` | 완료 기준(운영 지표/계약 테스트) 증적 미확인 |
| P0 | `docs/03_implementation/program/08_sprint7-execution-tickets.md` | Exit Criteria 중 FM-005/FM-006 완료 체크 `[x]` | 해당 2개 항목 `[ ]`로 조정 + “재검증 진행중” 주석 | 체크리스트와 실구현 불일치 |
| P0 | `docs/02_api/service-endpoints-ssot.md` | `상태: Accepted` | `상태: Needs Sync` (또는 `Draft`) | SSOT 포트/서비스 구성과 `docker-compose.yml`, `k8s/` 불일치 |

---

## 3. 단기 수정 대상 (P1)

| 우선순위 | 문서 | 현재 상태 | 제안 상태 | 변경 이유 |
|---|---|---|---|---|
| P1 | `services/core/docs/02_api/process-api.md` | 암묵적으로 구현 완료처럼 보임 | 엔드포인트별 `Implemented/Planned` 태깅 추가 | 실제 구현은 `/submit` 중심 |
| P1 | `services/core/docs/02_api/watch-api.md` | 구현 문서 형태 | 상단에 `상태: Planned` 명시 | 라우트 미구현 |
| P1 | `services/core/docs/02_api/agent-api.md` | 구현 문서 형태 | 상단에 `상태: Planned` 명시 | 라우트 미구현 |
| P1 | `services/core/docs/02_api/gateway-api.md` | 구현 전제 문서 | 상단에 `상태: Partial` 명시 | 문서 내 다수 경로/미들웨어 파일 부재 |
| P1 | `services/oracle/docs/02_api/meta-api.md` | 구현 문서 형태 | `상태: Planned` | `/text2sql/meta/*` 라우트 부재 |
| P1 | `services/oracle/docs/02_api/events-api.md` | 구현 문서 형태 | `상태: Planned` | `/text2sql/events/*` 라우트 부재 |
| P1 | `services/synapse/docs/02_api/extraction-api.md` | 구현 문서 형태 | `상태: Planned` | 문서 엔드포인트 다수 미구현 |
| P1 | `services/synapse/docs/02_api/event-log-api.md` | 구현 문서 형태 | `상태: Planned` | 라우트 부재 |
| P1 | `services/synapse/docs/02_api/schema-edit-api.md` | 구현 문서 형태 | `상태: Planned` | 라우트 부재 |
| P1 | `services/vision/docs/02_api/what-if-api.md` | Draft + 광범위 API | `상태: Partial` 명시 | 실제 `/analytics/what-if` 단일에 가까움 |
| P1 | `services/vision/docs/02_api/olap-api.md` | Draft + 광범위 API | `상태: Planned` | `/cubes`, `/pivot`, `/etl` 미구현 |
| P1 | `services/weaver/docs/02_api/metadata-catalog-api.md` | 구현 문서 형태 | `상태: Planned` | `/api/v1/metadata/*` 부재 |
| P1 | `services/weaver/docs/02_api/datasource-api.md` | 광범위 CRUD/조회 | `상태: Partial` | 실제 create/sync 중심 |
| P1 | `services/weaver/docs/02_api/query-api.md` | 다수 query API | `상태: Partial` | 실제 execute 단일 중심 |

---

## 4. 근거 매핑 (핵심)

- Program D3/티켓 근거:  
  - `docs/03_implementation/program/10_feature-maturity-checklist.md`  
  - `docs/03_implementation/program/08_sprint7-execution-tickets.md`
- Core 구현 근거:  
  - `services/core/app/main.py`  
  - `services/core/app/api/process/routes.py`
- Canvas 호출 근거:  
  - `apps/canvas/src/lib/api/watch.ts`
- SSOT 불일치 근거:  
  - `docs/02_api/service-endpoints-ssot.md`  
  - `docker-compose.yml`  
  - `k8s/deployments.yaml`, `k8s/services.yaml`
- 서비스별 API 불일치 근거:  
  - `services/oracle/app/main.py`, `services/oracle/app/api/*`  
  - `services/synapse/app/api/*`  
  - `services/vision/app/api/*`  
  - `services/weaver/app/api/*`

---

## 5. 바로 적용 순서

1. Program 상태 문서 2개 우선 수정  
2. SSOT 상태값 수정  
3. 서비스 API 문서에 상태 태그 일괄 삽입 (`Implemented/Partial/Planned`)

