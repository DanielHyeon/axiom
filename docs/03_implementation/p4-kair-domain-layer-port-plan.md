# P4: KAIR 전체 프로젝트 → Axiom 이식 계획서

> 작성일: 2026-03-22 (v2: 추가 7개 프로젝트 분석 반영)
> 대상: KAIR 8개 프로젝트 → Axiom 6개 서비스
> 분석 방법: 소스코드 라인 단위 비교 (KAIR ~98,000 LOC vs Axiom 230+ endpoints)

---

## 1. 전체 요약

### 이식 대상 (미이식 / 부분 이식)

| # | 기능 | KAIR LOC | 이식 대상 서비스 | 상태 | 우선순위 | 예상 LOC |
|---|------|----------|-----------------|------|----------|----------|
| 1 | BehaviorModel 실행 & 코드 생성 | 934 | Synapse + Weaver | **미이식** | P0 | ~800 |
| 2 | Object Explorer 드릴다운 | 348 | Weaver | **미이식** | P1 | ~400 |
| 3 | Instance Fetcher (데이터 프리뷰) | 291 | Weaver | **미이식** | P1 | ~350 |
| 4 | Materialized View 자동 생성 | 117 | Weaver | **미이식** | P1 | ~200 |
| 5 | Deep Agents 5계층 생성기 | 1,308 | Synapse | **미이식** | P2 | ~1,200 |
| 6 | SSE 스트리밍 (장기 작업 진행률) | 478 | Synapse | **미이식** | P2 | ~300 |
| 7 | 온톨로지 피드백 & 반복 개선 | 763 | Synapse | **미이식** | P2 | ~500 |
| 8 | 스키마 버전 관리 & 활성화 | 363 | Synapse | **부분 이식** | P3 | ~300 |
| 9 | Kafka CDC 로더 | 214 | 신규 워커 | **미이식** | P3 | ~250 |
| 10 | Neo4j 네이티브 RBAC + 감사 | 1,060 | Core | **불필요** | - | 0 |
| | **이식 대상 합계** | **5,816** | | | | **~4,300** |

### 이식 완료 (v5.0에서 이미 이식됨)

| # | 기능 | KAIR LOC | Axiom 서비스 | 위치 |
|---|------|----------|-------------|------|
| A | What-if 시뮬레이션 위자드 (9단계) | 6,782 | Vision | `whatif_wizard.py` + `whatif/` 서비스 7개 |
| B | 인과 분석 (Granger/VAR/RCA) | 1,363 | Vision | `causal_analysis_service.py` + `causal.py` |
| C | DMN 규칙 엔진 | 199 | Synapse | `dmn_engine.py` + `dmn.py` |
| D | LLM 관계 추론 | 372 | Synapse | `relation_inference.py` + `dmn.py` |
| E | LLM 시맨틱 캐시 | 228 | Oracle | `llm_cache.py` + `embedding_cache.py` |
| F | 자동 데이터소스 바인딩 | 615 | Weaver | `auto_binding_service.py` + `auto_binding.py` |
| G | 비즈니스 캘린더 | 273 | Vision | `business_calendar.py` |
| H | 시나리오 저장/비교 | 181 | Vision | `scenario_store.py` + `scenario_manager.py` |
| I | BPMN 파싱 | 371 | Core | `modules/process/infrastructure/bpm/` |
| J | PDF 추출 | 72 | Weaver | `document_ingestion.py` |
| K | 온톨로지 스키마 CRUD | 576 | Synapse | `ontology_service.py` + `ontology.py` |
| | **이식 완료 합계** | **~11,032** | | |

### 인프라/해당 없음

| # | 기능 | KAIR LOC | 사유 |
|---|------|----------|------|
| X1 | Neo4j 기본 서비스 | 166 | 인프라 코드 — Axiom 각 서비스에 내장 |
| X2 | Neo4j Guard 데코레이터 | 42 | 인프라 코드 |
| X3 | Dependency Injection | 16 | FastAPI 의존성 — 각 서비스에 내장 |
| X4 | LLM Factory | ~50 | 공통 유틸리티 — Axiom 각 서비스에 내장 |
| X5 | Config / Main | ~200 | 서비스 설정 — 각 서비스에 고유 |
| | **인프라 합계** | **~474** | |

> **KAIR 전체 코드베이스 ~20,483 LOC = 이식 완료 ~11,032 + 이식 대상 ~5,816 + 제외 1,060 + 인프라 ~474 + 기타 ~2,101**

> **판정 기준:**
> - **미이식**: KAIR에 존재하나 Axiom에 대응 코드 없음
> - **부분 이식**: 유사 기능 존재하나 핵심 로직 누락
> - **불필요**: Axiom이 이미 대체 메커니즘 보유 (JWT + PostgreSQL RBAC)

---

## 2. Phase 1: 핵심 도메인 로직 (P0)

---

### 2-1. BehaviorModel 실행 엔진 & 코드 생성

#### KAIR 소스 분석

| 파일 | LOC | 역할 |
|------|-----|------|
| `app/routers/ontology_behavior.py` | 409 | API 라우터 (7 엔드포인트) |
| `app/services/schema_store_behavior.py` | 525 | Neo4j CRUD + 필드 링크 관리 |

**KAIR 엔드포인트:**
```
GET    /object-types/{name}/behaviors           — BehaviorModel 목록 조회
POST   /object-types/{name}/behaviors           — BehaviorModel 생성 + READS/PREDICTS 링크
PATCH  /object-types/{name}/behaviors/{name}    — BehaviorModel 수정
DELETE /object-types/{name}/behaviors/{name}    — BehaviorModel 삭제
POST   /object-types/{name}/behaviors/{name}/execute — 모델 실행 (4가지 타입)
POST   /generate-code                           — LLM 기반 코드 생성
POST   /save-result-to-table                    — 결과 PostgreSQL 저장
```

**실행 엔진 4가지 타입:**

| 타입 | 설명 | 구현 방식 |
|------|------|----------|
| REST API | 외부 API 호출 | httpx POST/GET |
| DMN | 결정 테이블 실행 | DMNEngine.execute_decision_table() |
| JavaScript | 스크립트 실행 | 미구현 (501) |
| Python | 샌드박스 코드 실행 | exec() + 안전 제한 + LLM 자동 수정 (3회 재시도) |

**Python 샌드박스 보안:**
```python
# 금지 패턴 (블랙리스트)
FORBIDDEN = ["import os", "import sys", "import subprocess",
             "__import__", "eval(", "exec(", "open(", "compile("]

# 허용 빌트인 (화이트리스트)
SAFE_BUILTINS = {abs, all, any, bin, bool, dict, enumerate,
                 filter, float, hex, int, len, list, map,
                 max, min, pow, print, range, round, set,
                 sorted, str, sum, tuple, type, zip}
```

**LLM 자동 수정 루프:**
```
실행 → 에러 발생 → LLM에 에러+코드 전달 → 수정 코드 생성 → 재실행 (최대 3회)
```

**코드 생성 (generate-code):**
```python
prompt = f"Generate {language} code for: {user_prompt}"
result = await generate_text(prompt, temperature=0.2~1.0)
# ```python ... ``` 블록 추출
```

**결과 저장 (save-result-to-table):**
```python
# 타입 추론: bool → BOOLEAN, int → BIGINT, float → DOUBLE PRECISION, else → TEXT
# CREATE TABLE IF NOT EXISTS {schema}.{table} (col1 TYPE, col2 TYPE, ...)
# INSERT INTO ... VALUES ($1, $2, ...) — asyncpg executemany
```

#### Axiom 현재 상태

| 항목 | 상태 | 위치 |
|------|------|------|
| BehaviorModel 생성 | ✅ 구현됨 | `synapse/app/api/ontology.py` — POST /behavior-models |
| BehaviorModel 조회 | ✅ 구현됨 | `synapse/app/api/ontology.py` — GET /behavior-models |
| Model Graph DAG | ✅ 구현됨 | `synapse/app/api/ontology.py` — GET /model-graph |
| READS_FIELD / PREDICTS_FIELD | ✅ 구현됨 | `synapse/app/services/ontology_service.py` |
| **BehaviorModel 실행** | ❌ 미구현 | — |
| **LLM 코드 생성** | ❌ 미구현 | — |
| **결과 PostgreSQL 저장** | ❌ 미구현 | — |
| **Python 샌드박스** | ❌ 미구현 | — |
| **DMN 실행 연계** | ❌ 미구현 | DMN 엔진은 존재하나 Behavior와 연결 안됨 |

#### 이식 계획

**대상 서비스:** Synapse (API + 서비스) + Weaver (MindsDB 실행 프록시)

**신규 파일:**
```
services/synapse/app/api/behavior_execution.py       (~200 LOC) — 실행/코드생성/결과저장 라우터
services/synapse/app/services/behavior_executor.py   (~350 LOC) — 4타입 실행 엔진 + 샌드박스
services/synapse/app/services/code_generator.py      (~150 LOC) — LLM 코드 생성
services/synapse/app/services/result_persister.py    (~100 LOC) — PostgreSQL 동적 테이블 생성
services/synapse/tests/unit/test_behavior_execution.py (~200 LOC) — 단위 테스트
```

**수정 파일:**
```
services/synapse/app/main.py                         — behavior_execution 라우터 등록
services/synapse/app/services/dmn_engine.py          — execute_decision_table 호출 어댑터 추가
```

**엔드포인트 설계:**
```
POST /api/v3/synapse/behaviors/{behavior_id}/execute
  Request:  { "instance_data": {...}, "options": {"timeout_seconds": 30} }
  Response: { "success": true, "data": {...}, "execution_time_ms": 123 }

POST /api/v3/synapse/behaviors/generate-code
  Request:  { "prompt": "...", "language": "python", "temperature": 0.5 }
  Response: { "code": "...", "language": "python" }

POST /api/v3/synapse/behaviors/save-result
  Request:  { "table_name": "...", "schema_name": "dw", "data": [{...}] }
  Response: { "success": true, "rows_inserted": 100 }
```

**보안 고려사항:**
- Python exec() 샌드박스는 완벽하지 않음 — 프로덕션에서는 Docker 격리 컨테이너 권장
- 현재 단계에서는 KAIR과 동일한 블랙리스트+화이트리스트 방식 적용
- 향후 RestrictedPython 또는 PyPy sandbox 전환 고려

**MindsDB 연계:**
- REST API 타입 실행 시 Weaver MindsDB 클라이언트 재활용 가능
- `weaver/app/services/mindsdb_client.py` — 이미 Circuit Breaker + Retry 구현됨
- Synapse → Weaver 서비스 토큰 기반 내부 HTTP 호출

**의존성:**
- asyncpg (결과 저장) — 이미 Synapse 의존성
- httpx (REST API 실행) — 이미 Synapse 의존성
- LLM 호출 — Oracle LLM Cache 재활용 또는 Synapse 자체 LLM 클라이언트

---

## 3. Phase 2: 데이터 탐색 & 프리뷰 (P1)

---

### 3-1. Object Explorer 드릴다운

#### KAIR 소스 분석

| 파일 | LOC | 역할 |
|------|-----|------|
| `app/routers/ontology_explorer.py` | 349 | 3개 엔드포인트 |

**KAIR 엔드포인트:**
```
POST /object-explorer/search      — 전체 텍스트 검색 (모든 ObjectType MV)
POST /object-explorer/children    — FK 기반 자식 노드 드릴다운
GET  /object-explorer/relationships/{name} — 관계 메타데이터 조회
```

**핵심 알고리즘 — 전체 텍스트 검색:**
1. Neo4j에서 모든 ObjectType + HAS_COLUMN 관계 조회
2. 각 ObjectType의 MV 또는 base query 확인
3. PostgreSQL 연결 → 1행 샘플링으로 컬럼 감지
4. ID 컬럼 (id, code, no, key) vs 텍스트 컬럼 (name, title, desc, label, 명, 이름) 자동 분류
5. 동적 `ILIKE` WHERE 절 생성 → 매칭 행 반환

**핵심 알고리즘 — FK 드릴다운:**
1. Neo4j에서 부모 ObjectType의 FK 관계 조회 (HAS_CHILD, FK_TO)
2. sourceCol/targetCol + matchStrategy (EXACT, CONTAINS, STARTS_WITH, ENDS_WITH)
3. 부모 properties에서 FK 값 추출 → 자식 테이블 WHERE 절 구성
4. 결과에서 ID/Name 휴리스틱 추출

#### Axiom 현재 상태

| 항목 | 상태 | 위치 |
|------|------|------|
| MindsDB Object Explorer | ✅ 기본 구현 | `weaver/app/api/query.py` — POST /object-explorer |
| 시맨틱 벡터 검색 | ✅ 구현됨 | `synapse/app/api/graph.py` — POST /vector-search |
| FK 경로 검색 | ✅ 구현됨 | `synapse/app/api/graph.py` — POST /fk-path |
| **다형성 텍스트 검색** | ❌ 미구현 | ILIKE 기반 다중 ObjectType 검색 없음 |
| **FK 기반 자식 드릴다운** | ❌ 미구현 | fk-path는 경로 탐색이지 데이터 조회 아님 |
| **Match Strategy** | ❌ 미구현 | EXACT/CONTAINS/STARTS_WITH/ENDS_WITH |

#### 이식 계획

**대상 서비스:** Weaver (데이터 접근 계층)

**신규 파일:**
```
services/weaver/app/api/object_explorer.py           (~250 LOC) — 3개 엔드포인트
services/weaver/app/services/object_explorer_service.py (~200 LOC) — 검색 & 드릴다운 로직
services/weaver/tests/unit/test_object_explorer.py    (~150 LOC) — 단위 테스트
```

**엔드포인트 설계:**
```
POST /api/v3/weaver/object-explorer/search
  Request:  { "query": "삼성전자", "limit": 100 }
  Response: { "results": [{ "objectType": "...", "id": "...", "name": "...", "properties": {...} }] }

POST /api/v3/weaver/object-explorer/children
  Request:  { "parent_type": "Company", "parent_id": "...", "parent_properties": {...} }
  Response: { "children": [{ "objectType": "...", "items": [...] }] }

GET /api/v3/weaver/object-explorer/relationships/{object_type_name}
  Response: { "outgoing": [...], "incoming": [...] }
```

**구현 방식:**
- Weaver가 Synapse에 ObjectType 메타데이터 요청 (HTTP)
- Weaver가 MindsDB 또는 asyncpg로 실제 데이터 검색
- 컬럼 분류 휴리스틱을 한국어 지원으로 확장 (명, 이름, 코드, 번호)

---

### 3-2. Instance Fetcher (데이터 프리뷰)

#### KAIR 소스 분석

| 파일 | LOC | 역할 |
|------|-----|------|
| `app/services/instance_fetcher.py` | 116 | 샘플 데이터 조회 |
| `app/routers/ontology_instances.py` | 177 | 3개 엔드포인트 |

**KAIR 엔드포인트:**
```
GET  /node/{node_id}/sample-data    — 노드 바인딩된 테이블의 샘플 행 조회
GET  /nodes/{node_id}/instances     — 인스턴스 건수 + 프리뷰
POST /instances/bulk-create         — 벌크 인스턴스 생성 (Neo4j)
```

**핵심 로직:**
```python
# 1. 노드에서 dataSourceSchema 추출
schema_info = node.properties.get("dataSourceSchema")  # {"schema": "public", "table": "orders"}

# 2. 건수 조회
SELECT COUNT(*) FROM {schema}.{table}

# 3. 프리뷰 데이터
SELECT * FROM {schema}.{table} LIMIT {limit}

# 4. SQL Injection 방지
def _validate_sql_identifier(name: str) -> bool:
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))
```

#### Axiom 현재 상태

| 항목 | 상태 | 위치 |
|------|------|------|
| 테이블 데이터 프리뷰 | ✅ Canvas에 DataPreviewPanel 존재 | `canvas/src/features/schema-canvas/` (G8) |
| Weaver 쿼리 실행 | ✅ 구현됨 | `weaver/app/api/query.py` — POST /query |
| **노드 기반 프리뷰** | ❌ 미구현 | 온톨로지 노드 → 바인딩된 테이블 → 프리뷰 경로 없음 |
| **인스턴스 건수 조회** | ❌ 미구현 | — |
| **벌크 인스턴스 생성** | ❌ 미구현 | — |

#### 이식 계획

**대상 서비스:** Weaver (데이터 패브릭)

**신규 파일:**
```
services/weaver/app/api/instance_fetcher.py           (~150 LOC) — 3개 엔드포인트
services/weaver/app/services/instance_fetcher_service.py (~120 LOC) — 프리뷰 로직
services/weaver/tests/unit/test_instance_fetcher.py    (~100 LOC)
```

**엔드포인트 설계:**
```
GET /api/v3/weaver/nodes/{node_id}/sample-data?limit=50
  Response: { "total_count": 12345, "preview": { "columns": [...], "rows": [...] } }

GET /api/v3/weaver/nodes/{node_id}/instances?limit=100
  Response: { "total_count": 12345, "preview_data": [...], "column_types": {...} }
```

**구현 방식:**
- Synapse에서 노드의 dataSourceSchema 정보 조회
- Weaver MindsDB 또는 asyncpg로 직접 쿼리
- SQL Identifier 검증 필수 (injection 방지)

---

### 3-3. Materialized View 자동 생성

#### KAIR 소스 분석

| 파일 | LOC | 역할 |
|------|-----|------|
| `app/services/materialized_view_service.py` | 118 | MV 생성/리프레시/삭제 |

**핵심 기능:**
```python
CREATE MATERIALIZED VIEW IF NOT EXISTS {schema}.{view_name} AS
SELECT * FROM {schema}.{table_name} WITH DATA;

# pg_cron 자동 리프레시 (선택적)
SELECT cron.schedule('refresh_{view_name}', '*/{interval} * * * *',
                     'REFRESH MATERIALIZED VIEW ...');
```

#### Axiom 현재 상태

| 항목 | 상태 | 위치 |
|------|------|------|
| MV 생성 기본 API | ✅ 기본 구현 | `weaver/app/api/query.py` — POST /materialized-views |
| **커스텀 SELECT 로직** | ❌ 미구현 | 단순 프록시만 존재 |
| **pg_cron 자동 리프레시** | ❌ 미구현 | — |
| **MV 삭제/관리** | ❌ 미구현 | — |

#### 이식 계획

**대상 서비스:** Weaver (기존 MV API 확장)

**수정 파일:**
```
services/weaver/app/api/query.py                      — MV 관련 엔드포인트 추가
services/weaver/app/services/materialized_view_service.py (~200 LOC 신규) — MV 서비스
```

**추가 엔드포인트:**
```
POST   /api/v3/weaver/materialized-views              — MV 생성 (커스텀 SELECT 지원)
GET    /api/v3/weaver/materialized-views               — MV 목록 조회
POST   /api/v3/weaver/materialized-views/{name}/refresh — 수동 리프레시
DELETE /api/v3/weaver/materialized-views/{name}        — MV 삭제
```

---

## 4. Phase 3: 온톨로지 생성 고도화 (P2)

---

### 4-1. Deep Agents 5계층 온톨로지 생성기

#### KAIR 소스 분석

| 파일 | LOC | 역할 |
|------|-----|------|
| `app/services/deep_agents/orchestrator.py` | 700+ | 멀티 에이전트 오케스트레이터 |
| `app/services/deep_agents/layer_agents.py` | 600+ | 5개 레이어별 에이전트 |
| `app/routers/ontology_generation.py` | 479 | 생성 API + SSE 스트리밍 |

**아키텍처:**
```
DeepAgentsOrchestrator
  ├── KPIAgent        — KPI 레이어 추출 (OEE, Throughput, Defect Rate)
  ├── MeasureAgent    — Measure 레이어 추출 (Availability, Quality)
  ├── DriverAgent     — Driver 레이어 추출 (환율, 수요, 유가)
  ├── ProcessAgent    — Process 레이어 추출 (Assembly, Inspection)
  └── ResourceAgent   — Resource 레이어 추출 (Machines, Operators)
```

**파이프라인:**
1. 문서 파싱 (PDF/텍스트)
2. 병렬/순차 레이어 추출 (LLM)
3. 품질 평가 (노드 수 임계값 ≥ 2, 신뢰도 0.4~1.0)
4. Human-in-the-Loop (신뢰도 < 0.6일 때 질문 생성)
5. 웹 검색 보강 (Tavily API, 선택적)
6. 교차 레이어 관계 추론 (RelationInference)
7. SSE 스트리밍 응답

**KAIR 엔드포인트:**
```
POST /generate-multi-layer        — 5계층 생성 (SSE 스트리밍)
POST /generate-multi-layer/sync   — 5계층 생성 (동기)
POST /auto-link-datasource        — 데이터소스 자동 연결
POST /auto-link-datasource/stream — 연결 진행률 스트리밍
POST /confirm-datasource          — 연결 확인
```

#### Axiom 현재 상태

| 항목 | 상태 | 위치 |
|------|------|------|
| 온톨로지 추출 | ✅ 구현됨 | `synapse/app/api/ontology.py` — POST /extract-ontology |
| 문서 기반 추출 | ✅ 구현됨 | `synapse/app/api/extraction.py` — 8개 엔드포인트 |
| HITL 리뷰 큐 | ✅ 구현됨 | `synapse/app/api/ontology.py` — HITL 엔드포인트 |
| 관계 추론 | ✅ 구현됨 | `synapse/app/api/dmn.py` — infer-relation |
| 데이터소스 자동 바인딩 | ✅ 구현됨 | `weaver/app/api/auto_binding.py` |
| Core AI Agent | ✅ 구현됨 | `core/app/orchestrator/` — LangGraph |
| **5개 레이어별 전문 에이전트** | ❌ 미구현 | 범용 추출만 존재, 레이어 특화 프롬프트 없음 |
| **병렬 레이어 추출** | ❌ 미구현 | — |
| **품질 평가 + 신뢰도** | ❌ 미구현 | — |
| **웹 검색 보강** | ❌ 미구현 | — |
| **SSE 스트리밍 진행률** | ❌ 미구현 | — |

#### 이식 계획

**대상 서비스:** Synapse

**신규 파일:**
```
services/synapse/app/services/deep_agents/
  __init__.py
  orchestrator.py                (~400 LOC) — 오케스트레이터
  layer_agents.py                (~350 LOC) — 5개 레이어 에이전트
  quality_evaluator.py           (~100 LOC) — 신뢰도 평가
services/synapse/app/api/multi_layer_generation.py (~250 LOC) — SSE 스트리밍 라우터
services/synapse/tests/unit/test_deep_agents.py    (~200 LOC)
```

**엔드포인트 설계:**
```
POST /api/v3/synapse/ontology/generate-multi-layer
  Request:  { "input_text": "...", "domain_hint": "제조", "target_layers": ["kpi","measure"], "parallel": true }
  Response: SSE (application/x-ndjson)
    → {"event": "start", "target_layers": [...]}
    → {"event": "layer_progress", "layer": "KPI", "progress": 50}
    → {"event": "layer_complete", "layer": "KPI", "node_count": 5}
    → {"event": "complete", "data": {...}}
```

**Core 오케스트레이터와의 차이점:**
- Core의 LangGraph Agent는 **범용 대화형 AI** (도구 호출 + 멀티스텝 추론)
- Deep Agents는 **도메인 특화 배치 추출** (PDF → 5계층 구조화)
- 서로 보완적 — Core Agent가 Deep Agents를 도구로 호출하는 구조 가능

---

### 4-2. SSE 스트리밍 (장기 작업 진행률)

#### KAIR 소스 분석

**구현 패턴:**
```python
event_queue: asyncio.Queue = asyncio.Queue(maxsize=2000)

async def run_generation():
    emit_event({"event": "start", ...})
    # ... 장기 작업 ...
    emit_event({"event": "complete", "data": result})

async def event_stream():
    task = asyncio.create_task(run_generation())
    while not generation_complete.is_set():
        try:
            ev = await asyncio.wait_for(event_queue.get(), timeout=0.25)
            yield ev
        except asyncio.TimeoutError:
            pass  # 하트비트

return StreamingResponse(event_stream(), media_type="application/x-ndjson")
```

#### Axiom 현재 상태

- Axiom에는 비동기 202 + 폴링 패턴이 주류 (causal, mining, extraction)
- SSE 스트리밍은 미구현

#### 이식 계획

**범용 SSE 유틸리티 생성:**
```
services/synapse/app/core/sse_stream.py (~80 LOC) — 재사용 가능한 SSE 헬퍼
```

```python
# 사용 예시
async def generate_with_progress(request):
    async with SSEStream(maxsize=2000) as stream:
        task = asyncio.create_task(do_work(stream.emit))
        return StreamingResponse(stream, media_type="application/x-ndjson")
```

- Deep Agents 생성, 데이터소스 자동 연결 등에 적용
- 기존 202 폴링 패턴과 공존 (클라이언트 선택)

---

### 4-3. 온톨로지 피드백 & 반복 개선

#### KAIR 소스 분석

| 파일 | LOC | 역할 |
|------|-----|------|
| `app/services/schema_generator.py` | 900+ | 피드백 처리 + LLM 재생성 |

**핵심 로직:**
```
POST /feedback → 피드백 항목 배열 수신 → LLM으로 스키마 수정 → 새 버전 생성
```

**피드백 타입:**
- 노드 추가/삭제/수정
- 속성 변경 (타입, 설명)
- 관계 추가/삭제
- 레이어 이동

#### Axiom 현재 상태

| 항목 | 상태 | 위치 |
|------|------|------|
| 추출 엔티티 확인/거부 | ✅ 구현됨 | `synapse/app/api/extraction.py` — confirm/review |
| HITL 승인/거부 | ✅ 구현됨 | `synapse/app/api/ontology.py` — HITL endpoints |
| 온톨로지 노드 CRUD | ✅ 구현됨 | `synapse/app/api/ontology.py` |
| **LLM 기반 스키마 재생성** | ❌ 미구현 | 수동 CRUD만 가능, AI 재생성 없음 |
| **반복 개선 루프** | ❌ 미구현 | — |

#### 이식 계획

**대상 서비스:** Synapse

**신규 파일:**
```
services/synapse/app/services/schema_refiner.py (~300 LOC) — LLM 기반 스키마 개선
services/synapse/app/api/ontology_feedback.py   (~150 LOC) — 피드백 API
```

**엔드포인트:**
```
POST /api/v3/synapse/ontology/cases/{case_id}/feedback
  Request:  { "feedback": [{ "type": "add_node", "content": {...} }, ...] }
  Response: { "updated_nodes": [...], "new_version": "..." }
```

---

## 5. Phase 4: 운영 확장 (P3)

---

### 5-1. 스키마 버전 관리 & 활성화

#### KAIR 소스 분석

**엔드포인트:**
```
GET    /schemas                    — 전체 버전 목록
GET    /schemas/{id}              — 특정 버전 조회
PATCH  /schemas/{id}              — 이름 수정
POST   /schemas/{id}/activate     — 활성 스키마 설정 (단일 활성)
DELETE /schemas/{id}              — 버전 삭제
```

**Neo4j 저장:**
```cypher
(:Schema {id, name, isActive: boolean, schemaJson, createdAt, updatedAt})
```

#### Axiom 현재 상태

| 항목 | 상태 | 위치 |
|------|------|------|
| 스냅샷 생성/조회 | ✅ 구현됨 | `synapse/app/api/ontology.py` — snapshots |
| 스냅샷 diff | ✅ 구현됨 | `synapse/app/api/ontology.py` — diff |
| **활성 스키마 전환** | ❌ 미구현 | — |
| **스키마 버전 CRUD** | ❌ 미구현 | 스냅샷은 읽기 전용 |

#### 이식 계획

기존 스냅샷 API에 활성화 기능 추가:
```
POST /api/v3/synapse/ontology/cases/{case_id}/snapshots/{id}/activate
```

- 스냅샷을 "버전"으로 재해석
- 활성 스냅샷 → 현재 온톨로지로 복원

---

### 5-2. Kafka CDC 로더

#### KAIR 소스 분석

| 파일 | LOC | 역할 |
|------|-----|------|
| `app/loader/main.py` | 203 | Debezium CDC 이벤트 → Neo4j 동기화 |

**동작:**
```
Kafka (Debezium CDC) → Neo4j MERGE (:Instance) → [:HAS_INSTANCE] 링크
op: "c" (create), "u" (update), "d" (delete)
```

#### Axiom 현재 상태

- Axiom은 **Redis Streams**를 이벤트 버스로 사용 (내부 서비스 간)
- 외부 DB 변경 감지 메커니즘 없음
- Kafka/Debezium 인프라 미설정

#### 이식 계획

**우선순위 낮음 — 현재 Redis Streams로 충분**

향후 외부 운영 DB 변경 실시간 감지가 필요할 때:
```
services/synapse/app/workers/cdc_loader.py (~200 LOC) — Kafka consumer 워커
docker-compose.yml — Kafka + Debezium 서비스 추가
```

현재 Phase에서는 **보류**.

---

## 6. 제외 항목

### Neo4j 네이티브 RBAC (KAIR: 1,060 LOC)

**제외 사유:**
- Axiom은 이미 Core 서비스에서 JWT + PostgreSQL 기반 인증/인가 완비
- 7개 역할 (admin ~ viewer), 멀티테넌트 RLS, 레이트 리밋 모두 구현됨
- Neo4j에 사용자/역할을 중복 저장하면 데이터 정합성 이슈 발생
- KAIR의 Neo4j RBAC는 독립 서비스용 설계 — Axiom의 마이크로서비스에는 부적합

**Axiom 대체 메커니즘:**
```
Core JWT Auth → X-Tenant-Id 미들웨어 → 서비스별 RLS → PostgreSQL Row Security
```

---

## 7. 구현 일정 (권장)

```
Phase 1 (P0): BehaviorModel 실행 엔진
  ├── Synapse behavior_executor.py      — 4타입 실행 엔진
  ├── Synapse code_generator.py         — LLM 코드 생성
  ├── Synapse result_persister.py       — 결과 PostgreSQL 저장
  └── 테스트 + 코드 리뷰

Phase 2 (P1): 데이터 탐색
  ├── Weaver object_explorer.py         — FK 드릴다운
  ├── Weaver instance_fetcher.py        — 노드 데이터 프리뷰
  ├── Weaver materialized_view_service  — MV 확장
  └── 테스트 + 코드 리뷰

Phase 3 (P2): 온톨로지 생성 고도화
  ├── Synapse deep_agents/              — 5계층 생성기
  ├── Synapse sse_stream.py             — SSE 유틸리티
  ├── Synapse schema_refiner.py         — 피드백 재생성
  └── 테스트 + 코드 리뷰

Phase 4 (P3): 운영 확장 (선택)
  ├── Synapse 스냅샷 활성화 API
  └── Kafka CDC 로더 (보류)
```

---

## 8. 리스크 & 완화 방안

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| Python exec() 보안 취약점 | BehaviorModel 실행 시 코드 인젝션 가능 | 블랙리스트+화이트리스트 적용, 향후 Docker 격리 전환 |
| Deep Agents LLM 비용 | 5개 에이전트 병렬 호출 시 토큰 소비 증가 | LangChain 캐시 활성화, 로컬 Gemma-3-12B 우선 사용 |
| MindsDB 가용성 | MV 리프레시, 쿼리 실행 실패 | Circuit Breaker 패턴 이미 적용됨 |
| SSE 연결 유지 | 리버스 프록시 버퍼링으로 스트리밍 차단 | `X-Accel-Buffering: no` 헤더 설정 |
| 스키마 버전 충돌 | 동시 활성화 요청 시 경쟁 조건 | Neo4j 트랜잭션으로 isActive 원자적 전환 |

---

## 9. 파일 변경 요약

### 신규 파일 (17개, ~4,300 LOC)

```
services/synapse/app/api/behavior_execution.py
services/synapse/app/api/multi_layer_generation.py
services/synapse/app/api/ontology_feedback.py
services/synapse/app/services/behavior_executor.py
services/synapse/app/services/code_generator.py
services/synapse/app/services/result_persister.py
services/synapse/app/services/schema_refiner.py
services/synapse/app/services/deep_agents/__init__.py
services/synapse/app/services/deep_agents/orchestrator.py
services/synapse/app/services/deep_agents/layer_agents.py
services/synapse/app/services/deep_agents/quality_evaluator.py
services/synapse/app/core/sse_stream.py
services/weaver/app/api/object_explorer.py
services/weaver/app/api/instance_fetcher.py
services/weaver/app/services/object_explorer_service.py
services/weaver/app/services/instance_fetcher_service.py
services/weaver/app/services/materialized_view_service.py
```

### 수정 파일 (4개)

```
services/synapse/app/main.py          — 신규 라우터 등록
services/weaver/app/main.py           — 신규 라우터 등록
services/synapse/app/services/dmn_engine.py — Behavior 실행 어댑터
services/weaver/app/api/query.py      — MV 엔드포인트 확장
```

### 테스트 파일 (6개)

```
services/synapse/tests/unit/test_behavior_execution.py
services/synapse/tests/unit/test_deep_agents.py
services/synapse/tests/unit/test_schema_refiner.py
services/weaver/tests/unit/test_object_explorer.py
services/weaver/tests/unit/test_instance_fetcher.py
services/weaver/tests/unit/test_materialized_view.py
```

---

## 10. 추가 KAIR 프로젝트 분석 (7개)

> 2026-03-22 추가 분석: robo-data-domain-layer 외 7개 프로젝트

### 10-1. 프로젝트별 분석 요약

| 프로젝트 | 기술 스택 | LOC | 핵심 기능 | 이식 판정 |
|----------|----------|-----|----------|----------|
| **kair-common** | Python (공유 라이브러리) | 1,528 | LLM 팩토리, 회로차단기, 로깅, 미들웨어 | **불필요** — Axiom 각 서비스에 동등 기능 내장 |
| **antlr-code-parser** | Java 21 + Spring Boot + ANTLR4 | 3,698 (수작성) | Java/PL-SQL/PostgreSQL 코드 파싱 → AST JSON | **범위 외** — 레거시 현대화 도구, Axiom 미션과 무관 |
| **process-gpt-gateway** | Java 21 + Spring Cloud Gateway | 498 | API 게이트웨이, JWT 인증, 크레딧 검증, 레이트 리밋 | **불필요** — Axiom은 서비스 직접 접근, Nginx/Traefik 대체 |
| **robo-data-analyzer** | Python + FastAPI + Neo4j | 27,871 | 코드 분석→Neo4j 그래프, 리니지, 글로서리, 비즈니스 캘린더 | **대부분 이식 완료** (아래 상세) |
| **robo-data-fabric** | Python + FastAPI + MindsDB + Neo4j | 5,425 | 메타데이터 패브릭, 스키마 인트로스펙션, 어댑터 패턴 | **대부분 이식 완료** (아래 상세) |
| **robo-data-text2sql** | Python + FastAPI + Neo4j + LangChain | 39,808 | NL2SQL ReAct 에이전트, 품질 게이트, 값 매핑, CEP | **핵심 갭 발견** (아래 상세) |
| **robo-data-frontend** | Vue 3 + TypeScript + Pinia | 170+ 컴포넌트 | UI (온톨로지, Text2SQL, What-If, OLAP, WatchAgent) | **프레임워크 불일치** — Vue→React 직접 이식 불가, 기능 참조만 |

---

### 10-2. robo-data-text2sql 갭 분석 (핵심)

> **가장 중요한 발견**: Axiom Oracle (8 endpoints, ~2,000 LOC)이 KAIR text2sql (39,808 LOC)에 비해 상당히 단순함

#### Axiom Oracle vs KAIR text2sql 비교

| 기능 | KAIR text2sql | Axiom Oracle | 상태 |
|------|--------------|-------------|------|
| 기본 NL2SQL (/ask) | ✅ 구현 | ✅ 구현 | 이식 완료 |
| ReAct 에이전트 (/react) | ✅ C-Pipeline (탐색→수렴→탈출) | ✅ 단순 ReAct (5회 반복) | **갭: C-Pipeline 미이식** |
| SQLGlot AST 검증 | ✅ 구현 | ✅ 구현 | 이식 완료 |
| Enum 캐시 | ✅ 부트스트랩 자동 로딩 | ✅ 구현 | 이식 완료 |
| LLM 캐시 | ✅ LangChain SQLite/Redis | ✅ 2단계 (해시+임베딩) | 이식 완료 |
| 피드백 수집 | ✅ 구현 | ✅ 구현 | 이식 완료 |
| 값 매핑 | ✅ 자동 추출 + DB 검증 | ✅ 구현 | 이식 완료 |
| **HyDE 생성** | ✅ 가상 SQL로 검색 다양성 확보 | ❌ 미구현 | **P1 이식 대상** |
| **테이블 리랭킹** | ✅ LLM 기반 후보 테이블 재순위 | ❌ 미구현 | **P1 이식 대상** |
| **루브릭 기반 SQL 평가** | ✅ 다기준 점수화 (탐색 4후보→최적 선택) | ❌ 미구현 | **P1 이식 대상** |
| **대화 연속성** | ✅ conversation_state 토큰 (base64) | ❌ 미구현 | **P1 이식 대상** |
| **Text2SQL 유효성 플래그** | ✅ 빈 테이블/컬럼 자동 비활성화 | ❌ 미구현 | **P2 이식 대상** |
| **쿼리 유사도 클러스터링** | ✅ canonical_id + 벡터 유사도 | ❌ 미구현 | **P2 이식 대상** |
| **이벤트 규칙 / CEP** | ✅ SQL 기반 모니터링 규칙 엔진 | ⚠️ Core WatchRule 기본만 | **P2 이식 대상** |
| **Watch Agent** | ✅ LLM 기반 모니터링 설정 대화형 | ❌ 미구현 | **P3 이식 대상** |
| **스키마 편집 (Text2SQL 내)** | ✅ 테이블/컬럼 설명 수정 + FK 추가 | ✅ Synapse schema-edit로 분리됨 | 이식 완료 (다른 서비스) |
| **MV 관리 (Text2SQL 내)** | ✅ 생성/리프레시/목록 | ⚠️ Weaver 기본만 | Phase 2에서 처리 |

#### 추가 이식 대상 (robo-data-text2sql → Oracle)

| # | 기능 | KAIR LOC | 우선순위 | 예상 LOC | 대상 서비스 |
|---|------|----------|----------|----------|-----------|
| 11 | ReAct C-Pipeline (탐색→수렴→탈출) | ~2,200 | **P1** | ~1,500 | Oracle |
| 12 | HyDE 생성 (가상 SQL 검색 다양성) | ~300 | **P1** | ~200 | Oracle |
| 13 | 테이블 리랭킹 (LLM 재순위) | ~350 | **P1** | ~250 | Oracle |
| 14 | 루브릭 기반 SQL 평가 | ~500 | **P1** | ~400 | Oracle |
| 15 | 대화 연속성 (conversation_state) | ~837 | **P1** | ~500 | Oracle |
| 16 | Text2SQL 유효성 플래그 | ~400 | **P2** | ~300 | Oracle + Synapse |
| 17 | 쿼리 유사도 클러스터링 | ~300 | **P2** | ~200 | Oracle |
| 18 | 이벤트 규칙 / CEP 강화 | ~1,400 | **P2** | ~800 | Core |
| 19 | Watch Agent (대화형 모니터링) | ~500 | **P3** | ~400 | Core |
| | **text2sql 추가 합계** | **~6,787** | | **~4,550** | |

---

### 10-3. robo-data-analyzer 분석

| 기능 | KAIR LOC | Axiom 상태 | 이식 판정 |
|------|----------|-----------|----------|
| 코드 분석 → Neo4j 그래프 | ~15,000 | ❌ 미구현 | **범위 외** (레거시 현대화 도구) |
| ETL 코드 기반 데이터 리니지 | ~2,000 | ⚠️ OLAP Studio에 리니지 있으나 코드 기반 아님 | **P3** (선택적) |
| 비즈니스 글로서리 CRUD | ~1,500 | ✅ Weaver metadata_catalog + Synapse metadata_graph | 이식 완료 |
| 비즈니스 캘린더 | ~800 | ✅ Vision business_calendar | 이식 완료 |
| 스키마 시맨틱 검색 | ~500 | ✅ Synapse vector-search | 이식 완료 |
| DW 스타 스키마 등록 | ~400 | ✅ OLAP Studio model CRUD | 이식 완료 |
| 파이프라인 제어 (pause/resume/stop) | ~300 | ❌ 미구현 | **P3** (선택적) |

> **결론**: 핵심 기능 대부분 이식 완료. 코드 기반 리니지와 파이프라인 제어만 남음 (낮은 우선순위).

---

### 10-4. robo-data-fabric 분석

| 기능 | KAIR LOC | Axiom 상태 | 이식 판정 |
|------|----------|-----------|----------|
| 데이터소스 CRUD + MindsDB 등록 | ~950 | ✅ Weaver datasource API | 이식 완료 |
| 스키마 인트로스펙션 (PostgreSQL/MySQL 어댑터) | ~750 | ✅ Weaver schema_introspection | 이식 완료 |
| SSE 스트리밍 메타데이터 추출 | ~250 | ⚠️ Weaver는 동기 추출만 | Phase 3 SSE에서 통합 |
| SQL 쿼리 프록시 (MindsDB) | ~425 | ✅ Weaver query API + MindsDB client | 이식 완료 |
| Neo4j 메타데이터 그래프 | ~450 | ✅ Synapse metadata_graph | 이식 완료 |
| Fernet 패스워드 암호화 | ~126 | ❌ 미구현 | **P2** (보안 강화) |
| MySQL 어댑터 | ~199 | ❌ PostgreSQL만 지원 | **P3** (선택적) |

> **결론**: 대부분 이식 완료. Fernet 암호화와 MySQL 어댑터만 잔여 갭.

---

### 10-5. kair-common 분석

| 모듈 | KAIR LOC | Axiom 대체 | 이식 판정 |
|------|----------|-----------|----------|
| LLM 팩토리 (OpenAI/Gemini/Anthropic/Compatible) | 607 | Oracle llm_factory (서비스별 개별 구현) | **불필요** — 각 서비스가 자체 구현 |
| 회로 차단기 | 114 | Weaver resilience.py (SimpleCircuitBreaker) | **불필요** — 동등 기능 |
| 구조화 로깅 + 상관관계 ID | 169 | 각 서비스 structlog 설정 | **불필요** — structlog이 더 발전된 방식 |
| HTTP 클라이언트 (지수 백오프 재시도) | 91 | 각 서비스 httpx 래퍼 | **불필요** |
| 보안 헤더 미들웨어 | 38 | 각 서비스 개별 설정 | **불필요** |
| 통합 예외 계층 | 56 | 서비스별 개별 예외 | **유용하나 저우선순위** |
| 통합 미들웨어 설정 | 62 | 서비스별 개별 설정 | **불필요** |
| 레이트 리밋 (slowapi) | 49 | 각 서비스 커스텀 구현 | **불필요** |
| OpenTelemetry | 49 | OLAP Studio에 선택적 구현 | **불필요** |
| Prometheus 메트릭 | 35 | 미구현 | **P3** (선택적) |

> **결론**: Axiom은 각 서비스에 동등 기능을 내장하여 공유 라이브러리 불필요. 통합 예외 계층은 코드 품질 측면에서 유용하나 기능적 갭은 아님.

---

### 10-6. 프론트엔드 UI 기능 참조 (robo-data-frontend → Canvas 비교)

> Vue→React 직접 이식은 불가하나, Canvas에 없는 UI 기능을 식별하여 향후 구현 참조로 활용

| KAIR UI 기능 | Canvas 상태 | 참조 가치 |
|-------------|-----------|----------|
| Object Explorer 드릴다운 UI | ❌ 미구현 | **높음** — Phase 2 백엔드와 연계 |
| DMN 의사결정 테이블 편집기 (DMN.js) | ❌ 미구현 | **중간** — Synapse DMN 엔진은 있으나 UI 없음 |
| BPMN 프로세스 뷰어 (BPMN.js) | ❌ 미구현 | **중간** — Core BPM은 있으나 Canvas에 뷰어 없음 |
| Watch Agent 워크플로 에디터 (VueFlow) | ❌ 미구현 | **중간** — 비주얼 모니터링 설정 |
| 데이터 품질 프로파일링 UI | ❌ 미구현 | **낮음** |
| 인시던트 관리 UI | ❌ 미구현 | **낮음** |
| 코드 분석 업로드 (ANTLR) | ❌ 미구현 | **범위 외** |
| Neo4j NVL 그래프 뷰어 | ⚠️ Cytoscape 사용 | **불필요** — Cytoscape가 더 유연 |

---

## 11. 통합 이식 로드맵 (전체 KAIR → Axiom)

### Phase 1 (P0-P1): 핵심 비즈니스 로직

| # | 기능 | 소스 | 대상 | 예상 LOC |
|---|------|------|------|----------|
| 1 | BehaviorModel 실행 & 코드 생성 | domain-layer | Synapse | ~800 |
| 11 | ReAct C-Pipeline (탐색→수렴→탈출) | text2sql | Oracle | ~1,500 |
| 12 | HyDE 생성 | text2sql | Oracle | ~200 |
| 13 | 테이블 리랭킹 | text2sql | Oracle | ~250 |
| 14 | 루브릭 기반 SQL 평가 | text2sql | Oracle | ~400 |
| 15 | 대화 연속성 | text2sql | Oracle | ~500 |
| | **Phase 1 합계** | | | **~3,650** |

### Phase 2 (P1): 데이터 탐색 & 품질

| # | 기능 | 소스 | 대상 | 예상 LOC |
|---|------|------|------|----------|
| 2 | Object Explorer 드릴다운 | domain-layer | Weaver | ~400 |
| 3 | Instance Fetcher | domain-layer | Weaver | ~350 |
| 4 | Materialized View 관리 | domain-layer | Weaver | ~200 |
| 16 | Text2SQL 유효성 플래그 | text2sql | Oracle+Synapse | ~300 |
| 17 | 쿼리 유사도 클러스터링 | text2sql | Oracle | ~200 |
| 20 | Fernet 패스워드 암호화 | data-fabric | Weaver | ~150 |
| | **Phase 2 합계** | | | **~1,600** |

### Phase 3 (P2): 온톨로지 생성 & 모니터링

| # | 기능 | 소스 | 대상 | 예상 LOC |
|---|------|------|------|----------|
| 5 | Deep Agents 5계층 생성기 | domain-layer | Synapse | ~1,200 |
| 6 | SSE 스트리밍 | domain-layer | Synapse | ~300 |
| 7 | 온톨로지 피드백 & 재생성 | domain-layer | Synapse | ~500 |
| 18 | 이벤트 규칙 / CEP 강화 | text2sql | Core | ~800 |
| | **Phase 3 합계** | | | **~2,800** |

### Phase 4 (P3): 운영 확장 (선택)

| # | 기능 | 소스 | 대상 | 예상 LOC |
|---|------|------|------|----------|
| 8 | 스키마 버전 관리 | domain-layer | Synapse | ~300 |
| 9 | Kafka CDC 로더 | domain-layer | 신규 워커 | ~250 |
| 19 | Watch Agent (대화형) | text2sql | Core | ~400 |
| 21 | MySQL 어댑터 | data-fabric | Weaver | ~200 |
| | **Phase 4 합계** | | | **~1,150** |

### 전체 합계

| Phase | 예상 LOC | 서비스 |
|-------|----------|--------|
| Phase 1 | ~3,650 | Synapse, Oracle |
| Phase 2 | ~1,600 | Weaver, Oracle, Synapse |
| Phase 3 | ~2,800 | Synapse, Core |
| Phase 4 | ~1,150 | Synapse, Core, Weaver |
| **총합** | **~9,200** | |

---

## 12. 제외 항목 종합

| 프로젝트 | 기능 | LOC | 제외 사유 |
|----------|------|-----|----------|
| domain-layer | Neo4j 네이티브 RBAC | 1,060 | Axiom JWT + PostgreSQL RBAC로 충분 |
| kair-common | 전체 | 1,528 | Axiom 각 서비스에 동등 기능 내장 |
| antlr-code-parser | 전체 | 3,698 | 레거시 현대화 도구 — Axiom 디지털 트윈 미션과 무관 |
| process-gpt-gateway | 전체 | 498 | Axiom은 API 게이트웨이 불요 (서비스 직접 접근) |
| robo-data-analyzer | 코드 분석 파이프라인 | ~15,000 | 레거시 현대화 — Axiom 미션과 무관 |
| robo-data-frontend | Vue 3 UI | ~50,000+ | React/Canvas로 별도 구현 완료 (프레임워크 불일치) |
| **제외 합계** | | **~71,784** | |
