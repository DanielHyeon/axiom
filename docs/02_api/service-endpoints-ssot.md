# Axiom Service Endpoints SSOT

> 기준일: 2026-03-21
> 상태: Synced (현재 배포 파일 기준)
> 기준 파일: `docker-compose.yml`, `k8s/deployments.yaml`, `k8s/services.yaml`, `k8s/configmaps.yaml`

## 목적

로컬/클러스터 환경에서 실제 배포 중인 서비스의 포트와 Canvas 환경 변수 기준을 단일 문서로 관리한다.

## 1. 현재 배포 프로파일 (Runtime-Active)

현재 저장소의 Compose/K8s 매니페스트 기준으로 활성화된 서비스는 아래 6개다.

| 서비스 | 컨테이너 포트 | 호스트 포트(로컬) | Base URL |
|---|---:|---:|---|
| Postgres DB | 5432 | 5432 | `postgresql://localhost:5432/insolvency_os` |
| Core | 8002 | 8002 | `http://localhost:8002` |
| Synapse | 8003 | 8003 | `http://localhost:8003` |
| Vision | 8000 | 8000 | `http://localhost:8000` |
| Weaver | 8001 | 8001 | `http://localhost:8001` |
| Oracle | 8004 | 8004 | `http://localhost:8004` |
| Canvas | 80 | 5173 | `http://localhost:5173` |
| Redis Bus | 6379 | 6379 | `redis://localhost:6379` |

## 2. Canvas 환경 변수 (현재 프로파일)

```bash
# .env.development (현재 Compose 프로파일)
VITE_VISION_URL=http://localhost:8000
VITE_WEAVER_URL=http://localhost:8001
VITE_WS_URL=ws://localhost:8000/ws
VITE_ORACLE_URL=http://localhost:8004
```

참고:
- Oracle NL2SQL은 Canvas에서 `oracleApi`(createApiClient)로 호출하며, 기본 Base URL은 `http://localhost:8004`(SSOT §1).
- `VITE_SYNAPSE_URL`는 현재 Compose/K8s 프로파일에서 기본 제공되지 않을 수 있으며, 필요 시 개별 주입.

## 2.1 Weaver Insight API 경로 (구현 기준)

Canvas에서 `weaverApi`(Axios)로 호출하며, Base URL은 `http://localhost:8001`(SSOT §1).

| 메서드 | 경로 | 설명 | 응답 |
|--------|------|------|------|
| POST | `/api/insight/logs` | Query Log 단건/배치 인제스트 | `{ inserted, deduped, trace_id }` |
| POST | `/api/insight/logs:ingest` | 대량 배치 인제스트 (max 5000) | `{ inserted, deduped, batch_id, trace_id }` |
| POST | `/api/insight/impact` | KPI Impact Graph 생성 요청 | 200 (캐시 히트) 또는 202 + `job_id` |
| GET | `/api/insight/jobs/{job_id}` | 비동기 Job 상태 폴링 | `{ status, progress, graph, trace_id }` |
| POST | `/api/insight/query-subgraph` | SQL → TABLE/COLUMN/PREDICATE 서브그래프 | `{ parse_result, graph, trace_id }` |

## 2.2 Oracle / Synapse 실제 API 경로 (구현 기준)

Core 오케스트레이터 등에서 호출 시 아래 경로·계약을 사용한다.

| 서비스 | 메서드 | 실제 경로 | 비고 |
|--------|--------|-----------|------|
| Oracle | POST | `{ORACLE_BASE_URL}/text2sql/ask` | `/api/v1/ask` 아님. body: `question`, `datasource_id`, `options`(include_viz 등) |
| Synapse | POST | `{SYNAPSE_BASE_URL}/api/v3/synapse/process-mining/discover` | `/analyze` 없음. discover/conformance/bottlenecks/performance 등 사용. discover는 payload에 `case_id`, `log_id` 필수 |

## 2.3 Synapse 시멘틱 계약 API (v5.1 추가)

> 기준일: 2026-03-22. Synapse `/api/v3/synapse/semantic/*` (48 endpoints)

| 그룹 | 메서드 | 경로 | 설명 |
|------|--------|------|------|
| 개념 | POST | `/api/v3/synapse/semantic/concepts` | 온톨로지 개념 등록 |
| 개념 | GET | `/api/v3/synapse/semantic/concepts` | 목록 (status/case 필터) |
| 개념 | GET | `/api/v3/synapse/semantic/concepts/{id}` | 단건 + 용어 |
| 개념 | PUT | `/api/v3/synapse/semantic/concepts/{id}` | 수정 (버전 증가) |
| 개념 | PATCH | `/api/v3/synapse/semantic/concepts/{id}/status` | 상태 전이 |
| 용어 | POST | `/api/v3/synapse/semantic/terms` | 용어 등록 |
| 용어 | POST | `/api/v3/synapse/semantic/terms/bulk` | 일괄 등록 |
| 용어 | GET | `/api/v3/synapse/semantic/terms/search?q=` | 검색 |
| 엔티티 | POST/GET/GET/{id}/PUT | `/api/v3/synapse/semantic/entities` | CRUD |
| 지표 | POST/GET/GET/{id}/PUT | `/api/v3/synapse/semantic/measures` | CRUD |
| 차원 | POST/GET/GET/{id}/PUT | `/api/v3/synapse/semantic/dimensions` | CRUD |
| 조인 | POST/GET/GET/{id}/PUT | `/api/v3/synapse/semantic/joins` | CRUD |
| 그레인 | POST/GET/GET/{id}/PUT | `/api/v3/synapse/semantic/grains` | CRUD |
| 품질 | POST/GET | `/api/v3/synapse/semantic/quality-contracts` | CRUD |
| 컴파일 | POST | `/api/v3/synapse/semantic/compile/entity/{id}` | 검증+SQL |
| 컴파일 | POST | `/api/v3/synapse/semantic/compile/measure/{id}` | 검증+SQL |
| 배포 | POST | `/api/v3/synapse/semantic/publish` | binding 검증→릴리스 |
| 배포 | GET | `/api/v3/synapse/semantic/releases` | 이력 |
| 카탈로그 | GET | `/api/v3/synapse/semantic/catalog` | 통합 카탈로그 |
| AI | GET | `/api/v3/synapse/semantic/ai-context` | LLM 소비용 (RBAC) |
| 팩 | POST/GET/GET/{id}/PUT/DELETE | `/api/v3/synapse/semantic/context-packs` | CRUD |
| 팩 | GET | `/api/v3/synapse/semantic/context-packs/{id}/resolve` | 해석 |
| 정책 | POST/GET/DELETE | `/api/v3/synapse/semantic/prompt-policies` | CRUD |

## 2.4 Weaver 품질 수집 API (v5.1 추가)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/quality/scan` | 테이블 품질 스캔 (freshness/completeness/uniqueness) |
| GET | `/api/quality/scores` | 최신 품질 점수 목록 |
| GET | `/api/quality/scores/{type}/{target_id}` | 특정 대상 최신 점수 |

## 3. 확장 목표 프로파일 (Runtime-Target)

아래는 전 서비스 통합 운영 시 목표 포트 맵이다. 현재 매니페스트에는 완전 반영되지 않았다.

| 서비스 | 목표 호스트 포트 | 목표 Base URL |
|---|---:|---|
| Core | 8002 | `http://localhost:8002/api/v1` |
| Weaver | 8001 | `http://localhost:8001/api/v1` |
| Oracle | 8002 | `http://localhost:8002/api/v1` |
| Synapse | 8003 | `http://localhost:8003/api/v1` |
| Vision | 8400 | `http://localhost:8400/api/v1` |
| Canvas | 3000 | `http://localhost:3000` |

## 4. 변경 규칙

1. 포트/서비스 변경 시 `docker-compose.yml` 또는 `k8s/*.yaml`을 먼저 수정한다.
2. 이후 본 문서를 같은 커밋에서 동기화한다.
3. Canvas 문서(`canvas/docs/01_architecture/api-integration.md`, `canvas/docs/08_operations/build-deploy.md`)의 로컬 예시도 함께 갱신한다.
4. full-spec 진행 항목은 `docs/04_status/full-spec-gap-analysis.md`를 기준으로 추적한다.
5. 변경 후 `python3 tools/validate_ssot.py`로 Runtime-Active 정합성을 검증한다.
