# K-AIR text2sql Neo4j 코드 Synapse 분리 가이드

> Reference
> - `docs/legacy-data-isolation-policy.md`
> - `docs/architecture-semantic-layer.md`

## 이 문서가 답하는 질문

- K-AIR text2sql의 Neo4j 코드를 어떻게 Synapse로 분리하는가?
- 어떤 파일이 이식 대상이며 어떻게 변환하는가?
- Oracle이 Synapse API를 호출하도록 전환하는 절차는?
- 마이그레이션 중 하위 호환성은 어떻게 유지하는가?

<!-- affects: backend, api, operations -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

---

## 1. 마이그레이션 개요

### 1.1 전/후 비교

```
[Before] K-AIR text2sql (monolithic)
  app/
  ├── core/
  │   ├── neo4j_bootstrap.py   ← Neo4j 스키마 + 벡터 인덱스
  │   ├── graph_search.py      ← 벡터 검색 + FK 탐색
  │   └── config.py            ← Neo4j 설정 포함
  ├── routers/
  │   ├── text2sql.py          ← NL2SQL (Neo4j 의존)
  │   └── schema_edit.py       ← 스키마 편집
  └── pipelines/
      └── rag_pipeline.py      ← 5축 벡터 검색 (Neo4j 의존)


[After] Axiom 서비스 분리
  services/oracle/    (← text2sql NL2SQL 부분)
  ├── app/pipelines/
  │   ├── react_controller.py
  │   ├── rag_pipeline.py    ← Synapse API 호출로 전환
  │   └── sql_guard.py
  └── app/core/
      └── neo4j_client.py    ← 삭제, Synapse API 사용

  services/synapse/   (← text2sql Neo4j 부분)
  ├── app/graph/
  │   ├── neo4j_bootstrap.py ← 이식 + 4계층 확장
  │   └── graph_search.py    ← 이식
  ├── app/api/
  │   ├── schema_edit.py     ← 이식
  │   └── graph.py           ← 신규 (검색 API)
  └── app/core/
      └── neo4j_client.py    ← 이식
```

### 1.2 일정

| 단계 | 기간 | 내용 |
|------|------|------|
| Phase 2b-1 | 1일 | neo4j_bootstrap.py, graph_search.py 파일 이식 |
| Phase 2b-2 | 1일 | Synapse API 엔드포인트 구축 (graph, schema_edit) |
| Phase 2b-3 | 1일 | Oracle을 Synapse API 호출로 전환 + 통합 테스트 |
| **합계** | **3일** | |

---

## 2. 파일별 이식 계획

### 2.1 neo4j_bootstrap.py

| 항목 | K-AIR 원본 | Synapse 대상 |
|------|-----------|-------------|
| 파일 | `app/core/neo4j_bootstrap.py` | `synapse/app/graph/neo4j_bootstrap.py` |
| 변경점 | 동기 → 비동기 | `neo4j` → `neo4j async` 드라이버 |
| 추가점 | - | 4계층 온톨로지 제약조건/인덱스 추가 |
| 추가점 | - | SchemaVersion 노드 추가 |
| 삭제점 | Supabase 설정 참조 | Axiom 설정 체계로 교체 |

**핵심 변환 코드**:

```python
# K-AIR (Before) - synchronous
from neo4j import GraphDatabase

def bootstrap_neo4j():
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("CREATE CONSTRAINT ...")

# Axiom Synapse (After) - asynchronous
from neo4j import AsyncGraphDatabase

async def bootstrap_neo4j():
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    async with driver.session() as session:
        await session.run("CREATE CONSTRAINT ...")
```

### 2.2 graph_search.py

| 항목 | K-AIR 원본 | Synapse 대상 |
|------|-----------|-------------|
| 파일 | `app/core/graph_search.py` | `synapse/app/graph/graph_search.py` |
| 변경점 | 동기 → 비동기 | 드라이버 전환 |
| 추가점 | - | 온톨로지 경로 탐색 메서드 추가 |
| 이관점 | 5축 벡터 검색 | Oracle로 이관 (Synapse는 기본 검색만) |

**5축 벡터 검색 분리 결정**:

```
K-AIR 5축: question / hyde / regex / intent / PRF
   │
   ├── question, hyde → Oracle (Text2SQL 특화)
   ├── regex → Oracle (쿼리 패턴 매칭)
   ├── intent → Oracle (의도 분류)
   ├── PRF → Oracle (Pseudo Relevance Feedback)
   │
   └── 기본 벡터 검색 (table, column, query) → Synapse
```

### 2.3 schema_edit.py (라우터)

| 항목 | K-AIR 원본 | Synapse 대상 |
|------|-----------|-------------|
| 파일 | `app/routers/schema_edit.py` | `synapse/app/api/schema_edit.py` |
| 변경점 | Flask/FastAPI 라우터 → Axiom 표준 라우터 |
| 추가점 | - | 배치 임베딩 갱신 API |
| 변경점 | Supabase Auth → JWT (Core 경유) |

---

## 3. Oracle 전환 절차

### 3.1 전환 전 Oracle의 Neo4j 직접 사용

```python
# Oracle (Before) - direct Neo4j access
class RAGPipeline:
    def __init__(self, neo4j_driver):
        self.neo4j = neo4j_driver

    async def search_relevant_tables(self, query: str):
        embedding = await embed(query)
        async with self.neo4j.session() as session:
            result = await session.run(
                "CALL db.index.vector.queryNodes('table_vector', 5, $embedding)",
                embedding=embedding
            )
            return [record async for record in result]
```

### 3.2 전환 후 Oracle의 Synapse API 호출

```python
# Oracle (After) - Synapse API call
import httpx

class RAGPipeline:
    def __init__(self, synapse_url: str, service_token: str):
        self.synapse_url = synapse_url
        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {service_token}"}
        )

    async def search_relevant_tables(self, query: str, case_id: str):
        response = await self.client.post(
            f"{self.synapse_url}/api/v3/synapse/graph/search",
            json={
                "query": query,
                "case_id": case_id,
                "options": {
                    "vector_search": {"enabled": True, "table_top_k": 5},
                    "fk_traversal": {"enabled": True, "max_hops": 3}
                }
            }
        )
        return response.json()["data"]
```

### 3.3 전환 체크리스트

- [ ] Oracle의 neo4j_client.py 삭제
- [ ] Oracle의 graph_search 임포트 제거
- [ ] Oracle에 Synapse HTTP 클라이언트 추가
- [ ] 환경변수 추가: `ORACLE_SYNAPSE_URL`, `ORACLE_SYNAPSE_TOKEN`
- [ ] Oracle → Synapse 통합 테스트
- [ ] 응답 시간 벤치마크 (직접 → API 호출 오버헤드 확인)

---

## 4. 하위 호환성

### 4.1 Neo4j 스키마 호환

- 기존 Table/Column/Query/ValueMapping 노드와 관계는 변경 없이 유지
- 4계층 온톨로지 노드/관계는 추가만 (기존 데이터 영향 없음)
- 벡터 인덱스 이름과 구조 동일 (table_vector, column_vector, query_vector)

### 4.2 API 호환

기존 K-AIR schema-edit API URL을 Synapse URL로 매핑:

| K-AIR URL | Synapse URL |
|-----------|------------|
| `/schema-edit/tables/{name}/description` | `/api/v3/synapse/schema-edit/tables/{name}/description` |
| `/schema-edit/relationships` | `/api/v3/synapse/schema-edit/relationships` |

### 4.3 데이터 마이그레이션

기존 Neo4j 데이터는 마이그레이션 필요 없이 그대로 사용한다. Synapse 부트스트랩이 `IF NOT EXISTS` 패턴으로 4계층 온톨로지 스키마를 추가하므로, 기존 데이터에 영향을 주지 않는다.

---

## 5. 롤백 계획

마이그레이션 실패 시:

1. Oracle의 Synapse API 클라이언트 설정을 비활성화
2. Oracle의 이전 neo4j_client.py를 복원 (git revert)
3. Synapse 서비스 중지
4. Neo4j에 추가된 4계층 온톨로지 노드/관계는 기존 기능에 영향 없으므로 그대로 둠

---

## 6. 성능 영향 분석

| 경로 | Before (직접) | After (API 경유) | 차이 |
|------|-------------|-----------------|------|
| 벡터 검색 | ~50ms | ~80ms | +30ms (HTTP 오버헤드) |
| FK 경로 탐색 | ~30ms | ~60ms | +30ms |
| 통합 검색 | ~80ms | ~140ms | +60ms |

> **판단**: 60ms 추가 지연은 Text2SQL 전체 파이프라인 (2-5초) 대비 미미하다. 서비스 분리의 장점(장애 격리, 독립 스케일링)이 크다.

---

## 근거 문서

- K-AIR 역설계 분석 보고서 섹션 4.11.4 (Phase 2b)
- `01_architecture/architecture-overview.md`
- `01_architecture/graph-search.md`
