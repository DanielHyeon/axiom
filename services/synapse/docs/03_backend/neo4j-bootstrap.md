# Neo4j 초기화 및 인덱스/제약조건 관리

## 이 문서가 답하는 질문

- Neo4j 스키마는 어떻게 초기화되는가?
- 어떤 인덱스와 제약조건이 필요한가?
- K-AIR text2sql의 부트스트랩 코드에서 무엇이 변경되었는가?
- 4계층 온톨로지 스키마 확장은 어떻게 수행하는가?

<!-- affects: data, operations -->
<!-- requires-update: 06_data/neo4j-schema.md, 08_operations/deployment.md -->

---

## 1. K-AIR 원본: neo4j_bootstrap.py

K-AIR `app/core/neo4j_bootstrap.py`는 다음을 수행했다:

1. Neo4j 연결 확인
2. 기존 노드 유형별 유니크 제약조건 생성
3. 벡터 인덱스 생성 (table_vector, column_vector, query_vector)
4. 초기 Table/Column 노드 생성 (DB 메타데이터에서)
5. FK 관계 생성

---

## 2. Synapse 부트스트랩 확장

### 2.1 실행 시점

```python
# app/main.py
from contextlib import asynccontextmanager
from app.graph.neo4j_bootstrap import Neo4jBootstrap


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Neo4j schema
    bootstrap = Neo4jBootstrap(neo4j_client)
    await bootstrap.initialize()

    yield

    # Shutdown: Close connections
    await neo4j_client.close()


app = FastAPI(lifespan=lifespan)
```

### 2.2 초기화 순서

```
1. 연결 확인 (health check)
2. 기존 스키마 제약조건 (K-AIR 이식)
   ├─ Table 유니크 제약조건
   ├─ Column 유니크 제약조건
   └─ Query 유니크 제약조건
3. 벡터 인덱스 (K-AIR 이식)
   ├─ table_vector
   ├─ column_vector
   └─ query_vector
4. 4계층 온톨로지 스키마 (신규)
   ├─ Resource 제약조건/인덱스
   ├─ Process 제약조건/인덱스
   ├─ Measure 제약조건/인덱스
   └─ KPI 제약조건/인덱스
5. 풀텍스트 인덱스 (신규)
6. 스키마 버전 기록
```

---

## 3. 제약조건 정의

### 3.1 기존 K-AIR 이식 제약조건

```cypher
-- Table unique constraint
CREATE CONSTRAINT table_name_unique IF NOT EXISTS
FOR (t:Table)
REQUIRE t.name IS UNIQUE;

-- Column composite unique constraint
CREATE CONSTRAINT column_composite_unique IF NOT EXISTS
FOR (c:Column)
REQUIRE (c.table_name, c.name) IS UNIQUE;

-- Query unique constraint
CREATE CONSTRAINT query_question_unique IF NOT EXISTS
FOR (q:Query)
REQUIRE q.question IS UNIQUE;
```

### 3.2 4계층 온톨로지 제약조건 (신규)

```cypher
-- Resource: id must be unique
CREATE CONSTRAINT resource_id_unique IF NOT EXISTS
FOR (r:Resource)
REQUIRE r.id IS UNIQUE;

-- Process: id must be unique
CREATE CONSTRAINT process_id_unique IF NOT EXISTS
FOR (p:Process)
REQUIRE p.id IS UNIQUE;

-- Measure: id must be unique
CREATE CONSTRAINT measure_id_unique IF NOT EXISTS
FOR (m:Measure)
REQUIRE m.id IS UNIQUE;

-- KPI: id must be unique
CREATE CONSTRAINT kpi_id_unique IF NOT EXISTS
FOR (k:KPI)
REQUIRE k.id IS UNIQUE;

-- All ontology nodes: case_id must exist (node key)
CREATE CONSTRAINT resource_case_id IF NOT EXISTS
FOR (r:Resource)
REQUIRE r.case_id IS NOT NULL;

CREATE CONSTRAINT process_case_id IF NOT EXISTS
FOR (p:Process)
REQUIRE p.case_id IS NOT NULL;

CREATE CONSTRAINT measure_case_id IF NOT EXISTS
FOR (m:Measure)
REQUIRE m.case_id IS NOT NULL;

CREATE CONSTRAINT kpi_case_id IF NOT EXISTS
FOR (k:KPI)
REQUIRE k.case_id IS NOT NULL;
```

---

## 4. 인덱스 정의

### 4.1 벡터 인덱스 (K-AIR 이식)

```cypher
CREATE VECTOR INDEX table_vector IF NOT EXISTS
FOR (t:Table)
ON (t.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};

CREATE VECTOR INDEX column_vector IF NOT EXISTS
FOR (c:Column)
ON (c.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};

CREATE VECTOR INDEX query_vector IF NOT EXISTS
FOR (q:Query)
ON (q.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};
```

### 4.2 복합 인덱스 (신규)

```cypher
-- Resource: case_id + type lookup (most common query pattern)
CREATE INDEX resource_case_type IF NOT EXISTS
FOR (r:Resource)
ON (r.case_id, r.type);

-- Process: case_id + type lookup
CREATE INDEX process_case_type IF NOT EXISTS
FOR (p:Process)
ON (p.case_id, p.type);

-- Measure: case_id + type lookup
CREATE INDEX measure_case_type IF NOT EXISTS
FOR (m:Measure)
ON (m.case_id, m.type);

-- KPI: case_id + type lookup
CREATE INDEX kpi_case_type IF NOT EXISTS
FOR (k:KPI)
ON (k.case_id, k.type);

-- Extraction source tracking
CREATE INDEX resource_source IF NOT EXISTS
FOR (r:Resource)
ON (r.source);

-- Verification status
CREATE INDEX resource_verified IF NOT EXISTS
FOR (r:Resource)
ON (r.case_id, r.verified);
```

### 4.3 풀텍스트 인덱스 (신규)

```cypher
-- Full-text search across ontology node names and descriptions
CREATE FULLTEXT INDEX ontology_fulltext IF NOT EXISTS
FOR (n:Resource|Process|Measure|KPI)
ON EACH [n.name, n.description];

-- Full-text search for table/column descriptions
CREATE FULLTEXT INDEX schema_fulltext IF NOT EXISTS
FOR (n:Table|Column)
ON EACH [n.name, n.description];
```

---

## 5. 부트스트랩 구현

```python
# app/graph/neo4j_bootstrap.py
from app.core.neo4j_client import Neo4jClient
import structlog

logger = structlog.get_logger()


class Neo4jBootstrap:
    """
    Neo4j schema initialization and migration.
    Runs on service startup. All operations are idempotent (IF NOT EXISTS).
    """

    SCHEMA_VERSION = "2.0.0"  # 1.x = K-AIR legacy, 2.x = Axiom Synapse

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    async def initialize(self):
        """Main initialization entry point"""
        logger.info("neo4j_bootstrap_start", version=self.SCHEMA_VERSION)

        await self._check_connection()
        await self._create_legacy_constraints()    # K-AIR compatibility
        await self._create_vector_indexes()         # K-AIR vector indexes
        await self._create_ontology_constraints()   # 4-layer ontology
        await self._create_ontology_indexes()       # Ontology indexes
        await self._create_fulltext_indexes()       # Full-text search
        await self._record_schema_version()

        logger.info("neo4j_bootstrap_complete", version=self.SCHEMA_VERSION)

    async def _check_connection(self):
        """Verify Neo4j connectivity"""
        async with self.neo4j.session() as session:
            result = await session.run("RETURN 1 AS check")
            record = await result.single()
            if record["check"] != 1:
                raise RuntimeError("Neo4j health check failed")
        logger.info("neo4j_connection_verified")

    async def _create_legacy_constraints(self):
        """K-AIR text2sql schema constraints"""
        constraints = [
            "CREATE CONSTRAINT table_name_unique IF NOT EXISTS FOR (t:Table) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT column_composite_unique IF NOT EXISTS FOR (c:Column) REQUIRE (c.table_name, c.name) IS UNIQUE",
            "CREATE CONSTRAINT query_question_unique IF NOT EXISTS FOR (q:Query) REQUIRE q.question IS UNIQUE",
        ]
        await self._execute_batch(constraints, "legacy_constraints")

    async def _create_vector_indexes(self):
        """Vector indexes for similarity search"""
        indexes = [
            """CREATE VECTOR INDEX table_vector IF NOT EXISTS
               FOR (t:Table) ON (t.embedding)
               OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}""",
            """CREATE VECTOR INDEX column_vector IF NOT EXISTS
               FOR (c:Column) ON (c.embedding)
               OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}""",
            """CREATE VECTOR INDEX query_vector IF NOT EXISTS
               FOR (q:Query) ON (q.embedding)
               OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}""",
        ]
        await self._execute_batch(indexes, "vector_indexes")

    async def _create_ontology_constraints(self):
        """4-layer ontology constraints"""
        layers = ["Resource", "Process", "Measure", "KPI"]
        constraints = []
        for layer in layers:
            constraints.append(
                f"CREATE CONSTRAINT {layer.lower()}_id_unique IF NOT EXISTS "
                f"FOR (n:{layer}) REQUIRE n.id IS UNIQUE"
            )
            constraints.append(
                f"CREATE CONSTRAINT {layer.lower()}_case_id IF NOT EXISTS "
                f"FOR (n:{layer}) REQUIRE n.case_id IS NOT NULL"
            )
        await self._execute_batch(constraints, "ontology_constraints")

    async def _create_ontology_indexes(self):
        """Composite indexes for ontology queries"""
        layers = ["Resource", "Process", "Measure", "KPI"]
        indexes = []
        for layer in layers:
            indexes.append(
                f"CREATE INDEX {layer.lower()}_case_type IF NOT EXISTS "
                f"FOR (n:{layer}) ON (n.case_id, n.type)"
            )
        indexes.append(
            "CREATE INDEX resource_source IF NOT EXISTS "
            "FOR (r:Resource) ON (r.source)"
        )
        indexes.append(
            "CREATE INDEX resource_verified IF NOT EXISTS "
            "FOR (r:Resource) ON (r.case_id, r.verified)"
        )
        await self._execute_batch(indexes, "ontology_indexes")

    async def _create_fulltext_indexes(self):
        """Full-text search indexes"""
        indexes = [
            """CREATE FULLTEXT INDEX ontology_fulltext IF NOT EXISTS
               FOR (n:Resource|Process|Measure|KPI)
               ON EACH [n.name, n.description]""",
            """CREATE FULLTEXT INDEX schema_fulltext IF NOT EXISTS
               FOR (n:Table|Column)
               ON EACH [n.name, n.description]""",
        ]
        await self._execute_batch(indexes, "fulltext_indexes")

    async def _record_schema_version(self):
        """Record schema version as a graph property"""
        async with self.neo4j.session() as session:
            await session.run(
                """
                MERGE (v:SchemaVersion {service: 'synapse'})
                SET v.version = $version, v.updated_at = datetime()
                """,
                version=self.SCHEMA_VERSION
            )

    async def _execute_batch(self, queries: list, batch_name: str):
        """Execute a batch of schema modification queries"""
        async with self.neo4j.session() as session:
            for query in queries:
                try:
                    await session.run(query)
                except Exception as e:
                    logger.error("schema_query_failed",
                                 batch=batch_name, query=query[:100], error=str(e))
                    raise
        logger.info("schema_batch_complete", batch=batch_name, count=len(queries))
```

---

## 6. K-AIR 이식 변경점

| 항목 | K-AIR 원본 | Axiom Synapse |
|------|-----------|--------------|
| Neo4j 드라이버 | 동기 (neo4j) | 비동기 (neo4j async) |
| 스키마 생성 | 앱 시작 시 직접 실행 | `lifespan` 이벤트 내 실행 |
| 인덱스 | 벡터 3개만 | 벡터 3 + 복합 6 + 풀텍스트 2 |
| 제약조건 | Table/Column/Query | + Resource/Process/Measure/KPI |
| 버전 관리 | 없음 | SchemaVersion 노드로 추적 |
| 에러 처리 | 최소 | 배치별 로깅 + 재시도 |

---

## 금지 규칙

- 부트스트랩 외부에서 제약조건/인덱스를 생성하지 않는다
- `IF NOT EXISTS` 없이 스키마 수정 쿼리를 실행하지 않는다
- 프로덕션에서 `DROP CONSTRAINT/INDEX`를 자동으로 실행하지 않는다

## 필수 규칙

- 모든 스키마 수정은 멱등적이어야 한다 (IF NOT EXISTS)
- 스키마 버전을 SchemaVersion 노드에 기록한다
- 부트스트랩 실패 시 서비스 시작을 중단한다

---

## 근거 문서

- K-AIR `app/core/neo4j_bootstrap.py` 원본 코드
- `06_data/neo4j-schema.md` (전체 스키마)
- `06_data/vector-indexes.md` (벡터 인덱스 상세)
