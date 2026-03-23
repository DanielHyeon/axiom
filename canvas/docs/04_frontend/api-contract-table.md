# Canvas API 계약표 (API Contract Table)

> **작성일**: 2026-03-24
> **목적**: 프론트엔드가 호출하는 모든 백엔드 API의 연동 상태를 single source of truth로 관리한다.
> **갱신 규칙**: 신규 API 추가 또는 mock→real 전환 시 이 문서를 먼저 갱신한다.

---

## 요약

| 카테고리 | 총 API | Real | Mock | Hybrid | 비고 |
|----------|:------:|:----:|:----:|:------:|------|
| Core (케이스/Watch/CEP/문서/에이전트) | 31 | 31 | 0 | 0 | |
| 데이터 관리 (데이터소스/글로서리) | 30 | 29 | 0 | 1 | |
| NL2SQL & 쿼리 | 7 | 7 | 0 | 0 | |
| 시맨틱 레이어 (Synapse) | 53 | 53 | 0 | 0 | |
| 온톨로지 & 그래프 | 13 | 13 | 0 | 0 | |
| 리니지 & 스키마 | 13 | 13 | 0 | 0 | |
| Insight/KPI | 8 | 5 | 0 | 3 | **kpis/drivers/detail 백엔드 미구현** |
| OLAP & 시각화 | 21 | 21 | 0 | 0 | |
| 프로세스 마이닝 | 3 | 3 | 0 | 0 | |
| 데이터 품질 | 7 | 1 | 5 | 1 | **rules/tests/incidents 백엔드 미구현** |
| 피드백 | 7 | 7 | 0 | 0 | |
| **합계** | **193** | **183** | **5** | **5** | **94.8% real** |

---

## Mock/Hybrid API 목록 (출시 전 해소 필요)

| API | 파일 | 상태 | 백엔드 상태 | 해소 방안 |
|-----|------|:----:|-----------|----------|
| `GET /api/insight/kpis` | `features/insight/api/insightApi.ts` | Mock | Weaver 미구현 | 하드코딩 샘플 → Weaver API 구현 후 연결 |
| `GET /api/insight/drivers` | `features/insight/api/insightApi.ts` | Mock | Weaver 미구현 | 클라이언트 파생 → Weaver API 구현 후 연결 |
| `GET /api/insight/drivers/detail` | `features/insight/api/insightApi.ts` | Mock | Weaver 미구현 | 스텁 → Weaver API 구현 후 연결 |
| DQ Rules CRUD | `features/data-quality/api/dataQualityApi.ts` | Mock | Weaver 미구현 | 로컬 mock → Weaver quality rules API 구현 |
| DQ Tests 실행 | `features/data-quality/api/dataQualityApi.ts` | Mock | Weaver 미구현 | 로컬 mock → Weaver test runner API 구현 |
| DQ Incidents 상태 변경 | `features/data-quality/api/dataQualityApi.ts` | Mock | Weaver 미구현 | 로컬 mock → Weaver incidents API 구현 |
| DQ Scores | `features/data-quality/api/dataQualityApi.ts` | Hybrid | Weaver 구현 | 9차원→4카테고리 매핑 검증 필요 |
| DQ Breaches | `features/data-quality/api/dataQualityApi.ts` | Hybrid | Weaver 구현 | 60점 threshold 검증 필요 |

---

## 스트리밍 API

| 타입 | API | 파일 |
|------|-----|------|
| SSE | `POST /api/datasources/{name}/extract-metadata` | `weaverDatasourceApi.ts` |
| NDJSON | `POST /text2sql/react` | `oracleNl2sqlApi.ts` |
| WebSocket | Watch 알림 실시간 | `lib/watchStream.ts` |

---

## 문서 관리 API 계약 (Phase 1 핵심)

> 현재 `documentReviewApi.ts`에 리뷰 1개만 존재. 아래는 HITL 워크플로 완성을 위해 필요한 계약.

| 메서드 | 엔드포인트 | Core 구현 | 프론트 구현 | 비고 |
|--------|-----------|:---------:|:---------:|------|
| GET | `/api/v1/cases/{caseId}/documents` | ✅ | ❌ 필요 | 목록 조회 |
| GET | `/api/v1/cases/{caseId}/documents/{docId}` | ✅ | ❌ 필요 | 상세 조회 |
| POST | `/api/v1/cases/{caseId}/documents` | ✅ | ❌ 필요 | 문서 생성 |
| PUT | `/api/v1/cases/{caseId}/documents/{docId}` | ✅ | ❌ 필요 | 문서 수정 |
| POST | `/api/v1/cases/{caseId}/documents/{docId}/review` | ✅ | ✅ 있음 | 리뷰 액션 |
| GET | `/api/v1/cases/{caseId}/documents/{docId}/comments` | ❓ 확인 필요 | ❌ 필요 | 코멘트 목록 |
| POST | `/api/v1/cases/{caseId}/documents/{docId}/comments` | ❓ 확인 필요 | ❌ 필요 | 코멘트 추가 |

---

## 변경 이력

| 날짜 | 변경 |
|------|------|
| 2026-03-24 | 초기 작성. 193개 API 전수 조사 |
