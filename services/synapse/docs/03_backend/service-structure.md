# 서비스 내부 구조

## 이 문서가 답하는 질문

- Synapse FastAPI 서버의 파일 구조와 각 모듈의 책임은?
- 의존성 주입(DI) 패턴은 어떻게 구현하는가?
- 트랜잭션 경계는 어디에 있는가?
- 서비스 간 호출 시 에러 처리 규칙은?

<!-- affects: api, backend -->
<!-- requires-update: 02_api/* -->

---

## 1. 디렉터리 구조

```
services/synapse/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 앱 생성, 라우터 등록
│   ├── config.py                  # 환경설정 (pydantic-settings)
│   ├── dependencies.py            # 공통 의존성 (DI)
│   │
│   ├── api/                       # API Layer (HTTP 인터페이스)
│   │   ├── __init__.py
│   │   ├── ontology.py           # 온톨로지 CRUD 엔드포인트
│   │   ├── schema_edit.py        # 스키마 편집 엔드포인트 (← K-AIR)
│   │   ├── extraction.py         # 비정형→온톨로지 추출 엔드포인트
│   │   └── graph.py              # 그래프 탐색 엔드포인트
│   │
│   ├── graph/                     # Graph Layer (Neo4j 전담)
│   │   ├── __init__.py
│   │   ├── neo4j_bootstrap.py    # 스키마 초기화 (← K-AIR)
│   │   ├── graph_search.py       # 벡터+FK 검색 (← K-AIR)
│   │   ├── ontology_schema.py    # 4계층 온톨로지 스키마 (신규)
│   │   └── ontology_ingest.py    # 자동 인제스트 (신규)
│   │
│   ├── extraction/                # Extraction Layer (LLM 전담)
│   │   ├── __init__.py
│   │   ├── ner_extractor.py      # NER (← GPT-4o Structured Output)
│   │   ├── relation_extractor.py # 관계 추출 (← GPT-4o)
│   │   └── ontology_mapper.py    # 온톨로지 매핑 (규칙 기반)
│   │
│   ├── services/                  # Service Layer (비즈니스 로직)
│   │   ├── __init__.py
│   │   ├── ontology_service.py   # 온톨로지 CRUD 비즈니스 로직
│   │   ├── extraction_service.py # 추출 파이프라인 오케스트레이션
│   │   ├── graph_service.py      # 검색 비즈니스 로직
│   │   └── schema_service.py     # 스키마 편집 비즈니스 로직
│   │
│   ├── models/                    # Pydantic 모델
│   │   ├── __init__.py
│   │   ├── ontology.py           # 온톨로지 요청/응답 모델
│   │   ├── extraction.py         # 추출 요청/응답 모델
│   │   ├── graph.py              # 검색 요청/응답 모델
│   │   └── schema.py             # 스키마 편집 모델
│   │
│   ├── core/                      # Core Layer (인프라)
│   │   ├── __init__.py
│   │   ├── neo4j_client.py       # Neo4j 드라이버 관리
│   │   ├── embedding_client.py   # 임베딩 API 클라이언트
│   │   ├── llm_client.py         # GPT-4o API 클라이언트
│   │   └── redis_client.py       # Redis Streams 소비자
│   │
│   └── events/                    # 이벤트 처리
│       ├── __init__.py
│       ├── consumer.py           # Redis Streams 이벤트 소비자
│       └── handlers.py           # 이벤트 핸들러 (인제스트 트리거)
│
├── tests/
│   ├── conftest.py
│   ├── test_ontology.py
│   ├── test_extraction.py
│   ├── test_graph_search.py
│   └── test_schema_edit.py
│
├── pyproject.toml
├── Dockerfile
└── docs/                          # 이 문서들이 위치
```

---

## 2. 레이어 간 호출 규칙

```
[API Layer]  →  [Service Layer]  →  [Graph Layer]  →  [Neo4j]
                     │
                     └→ [Extraction Layer]  →  [GPT-4o]
                     │
                     └→ [Core Layer]  →  [Redis/PostgreSQL]
```

### 2.1 허용되는 호출

| From | To | 허용 |
|------|-----|------|
| API | Service | O |
| Service | Graph | O |
| Service | Extraction | O |
| Service | Core | O |
| Extraction | Core (LLM client) | O |
| Graph | Core (Neo4j client) | O |

### 2.2 금지되는 호출

| From | To | 금지 이유 |
|------|-----|----------|
| API | Graph | Service Layer 우회 (비즈니스 로직 누락) |
| API | Extraction | Service Layer 우회 |
| API | Core | Service Layer 우회 |
| Extraction | Graph | 관심사 혼합 (LLM과 DB 분리) |
| Graph | Extraction | 관심사 혼합 |

---

## 3. 의존성 주입 (DI)

### 3.1 FastAPI Depends 패턴

```python
# app/dependencies.py
from functools import lru_cache
from neo4j import AsyncGraphDatabase

from app.config import Settings
from app.core.neo4j_client import Neo4jClient
from app.core.llm_client import LLMClient
from app.core.embedding_client import EmbeddingClient


@lru_cache()
def get_settings() -> Settings:
    return Settings()


async def get_neo4j_client(
    settings: Settings = Depends(get_settings)
) -> Neo4jClient:
    return Neo4jClient(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)


async def get_llm_client(
    settings: Settings = Depends(get_settings)
) -> LLMClient:
    return LLMClient(
        api_key=settings.openai_api_key,
        model=settings.llm_model,  # "gpt-4o"
    )


async def get_embedding_client(
    settings: Settings = Depends(get_settings)
) -> EmbeddingClient:
    return EmbeddingClient(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,  # "text-embedding-3-small"
    )
```

### 3.2 서비스 의존성

```python
# app/api/ontology.py
from fastapi import APIRouter, Depends
from app.services.ontology_service import OntologyService
from app.dependencies import get_neo4j_client

router = APIRouter(prefix="/ontology", tags=["ontology"])


async def get_ontology_service(
    neo4j: Neo4jClient = Depends(get_neo4j_client),
) -> OntologyService:
    return OntologyService(neo4j=neo4j)


@router.get("/cases/{case_id}/ontology")
async def get_case_ontology(
    case_id: str,
    service: OntologyService = Depends(get_ontology_service),
):
    return await service.get_case_ontology(case_id)
```

---

## 4. 설정 관리

```python
# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "axiom-synapse"
    debug: bool = False
    log_level: str = "INFO"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str  # required, no default
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 50

    # PostgreSQL (task state, extraction results)
    database_url: str  # required
    database_pool_size: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_stream_group: str = "synapse-consumer"

    # OpenAI
    openai_api_key: str  # required
    llm_model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Extraction
    extraction_chunk_size: int = 800
    extraction_chunk_overlap: int = 100
    hitl_confidence_threshold: float = 0.75
    max_concurrent_extractions: int = 5
    max_entities_per_chunk: int = 50

    # Vector Search
    vector_search_min_score: float = 0.7
    fk_max_hops: int = 3

    class Config:
        env_file = ".env"
        env_prefix = "SYNAPSE_"
```

---

## 5. 트랜잭션 경계

### 5.1 Neo4j 트랜잭션

Neo4j 트랜잭션은 Graph Layer 함수 단위로 관리한다.

```python
# app/graph/ontology_schema.py
class OntologySchemaManager:
    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j

    async def create_resource_node(self, case_id: str, node_data: dict) -> dict:
        """
        Single transaction: create node + set properties
        """
        async with self.neo4j.session() as session:
            result = await session.execute_write(
                self._create_resource_tx, case_id, node_data
            )
            return result

    @staticmethod
    async def _create_resource_tx(tx, case_id: str, node_data: dict):
        query = """
        CREATE (n:Resource {
            id: randomUUID(),
            case_id: $case_id,
            ...
        })
        RETURN n
        """
        result = await tx.run(query, case_id=case_id, **node_data)
        return await result.single()
```

### 5.2 다중 노드/관계 생성 시

여러 노드와 관계를 한번에 생성해야 할 때는 단일 트랜잭션 내에서 처리한다.

```python
async def create_ontology_subgraph(self, case_id: str, nodes: list, relations: list):
    """
    Atomic transaction: all nodes + relations created together or none
    """
    async with self.neo4j.session() as session:
        result = await session.execute_write(
            self._create_subgraph_tx, case_id, nodes, relations
        )
        return result
```

### 5.3 PostgreSQL 트랜잭션

추출 작업 상태는 PostgreSQL에 저장한다. Neo4j와 PostgreSQL 간의 분산 트랜잭션은 사용하지 않는다 (최종 일관성).

```
추출 작업 상태 머신:
PostgreSQL (extraction_tasks 테이블)
  QUEUED → PROCESSING → COMPLETED | FAILED

Neo4j 반영:
  COMPLETED 상태에서 Graph Layer로 커밋
  실패 시 PostgreSQL에 에러 기록, Neo4j는 변경 없음
```

---

## 6. 에러 처리 전략

### 6.1 에러 계층

```python
# app/core/exceptions.py

class SynapseError(Exception):
    """Base exception for Synapse service"""
    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code


class NodeNotFoundError(SynapseError):
    def __init__(self, node_id: str):
        super().__init__("NODE_NOT_FOUND", f"Node {node_id} not found", 404)


class InvalidRelationError(SynapseError):
    def __init__(self, source_layer: str, target_layer: str, relation_type: str):
        super().__init__(
            "INVALID_RELATION_DIRECTION",
            f"Relation {relation_type} not allowed from {source_layer} to {target_layer}",
            400
        )


class ExtractionFailedError(SynapseError):
    def __init__(self, doc_id: str, step: str, reason: str):
        super().__init__(
            "EXTRACTION_FAILED",
            f"Extraction failed for {doc_id} at step {step}: {reason}",
            422
        )


class Neo4jUnavailableError(SynapseError):
    def __init__(self):
        super().__init__("NEO4J_UNAVAILABLE", "Neo4j service unavailable", 503)
```

### 6.2 글로벌 에러 핸들러

```python
# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Axiom Synapse")


@app.exception_handler(SynapseError)
async def synapse_error_handler(request: Request, exc: SynapseError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message
            }
        }
    )
```

---

## 7. 로깅 규칙

| 레벨 | 용도 | 예시 |
|------|------|------|
| DEBUG | Neo4j Cypher 쿼리, LLM 요청/응답 상세 | `Cypher: MATCH (n:Resource)...` |
| INFO | API 호출, 추출 작업 시작/완료, 노드 생성 | `Extraction started: doc_id=...` |
| WARNING | HITL 임계값 미달, 재시도 | `Low confidence entity: 0.65` |
| ERROR | Neo4j 연결 실패, LLM 타임아웃 | `Neo4j connection failed: ...` |

### 구조화된 로깅

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "ontology_node_created",
    case_id=case_id,
    node_type="Company",
    node_id=node_id,
    source="extracted",
    confidence=0.95
)
```

---

## 금지 규칙

- API Layer에서 Graph Layer를 직접 호출하지 않는다
- Extraction Layer에서 Neo4j를 직접 조작하지 않는다
- 설정값을 하드코딩하지 않는다 (모두 환경변수 경유)
- Neo4j와 PostgreSQL 간 분산 트랜잭션을 사용하지 않는다

## 필수 규칙

- 모든 API 응답은 `{"success": bool, "data": ...}` 형식을 따른다
- 에러 응답은 `{"success": false, "error": {"code": str, "message": str}}` 형식을 따른다
- 구조화된 로깅 (structlog)을 사용한다
- 모든 설정은 pydantic-settings로 관리한다

---

## 근거 문서

- `01_architecture/architecture-overview.md` (아키텍처 전체)
- K-AIR 역설계 분석 보고서 섹션 4.11.2 (디렉터리 구조)
