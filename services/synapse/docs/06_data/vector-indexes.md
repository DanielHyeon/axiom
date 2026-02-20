# 벡터 인덱스 설계

## 이 문서가 답하는 질문

- Neo4j에서 벡터 인덱스는 어떻게 구성되는가?
- 임베딩 모델과 차원은?
- 임베딩 생성 전략은?
- 검색 성능 튜닝 파라미터는?

<!-- affects: backend, api -->
<!-- requires-update: 01_architecture/graph-search.md, 02_api/graph-api.md -->

---

## 1. 벡터 인덱스 목록

| 인덱스명 | 대상 노드 | 속성 | 차원 | 유사도 함수 | 용도 |
|---------|----------|------|------|-----------|------|
| `table_vector` | `:Table` | `embedding` | 1536 | cosine | 테이블 검색 |
| `column_vector` | `:Column` | `embedding` | 1536 | cosine | 컬럼 검색 |
| `query_vector` | `:Query` | `embedding` | 1536 | cosine | 유사 쿼리 검색 |

---

## 2. 임베딩 모델

### 2.1 선택된 모델

| 항목 | 값 |
|------|---|
| 모델 | `text-embedding-3-small` (OpenAI) |
| 차원 | 1536 |
| 최대 입력 | 8,191 토큰 |
| 비용 | $0.02 / 1M 토큰 |

### 2.2 선택 근거

| 후보 | 차원 | 성능 (MTEB) | 비용 | 결정 |
|------|------|-----------|------|------|
| text-embedding-3-small | 1536 | 62.3 | $0.02/1M | **채택** |
| text-embedding-3-large | 3072 | 64.6 | $0.13/1M | 비용 대비 성능 향상 미미 |
| text-embedding-ada-002 | 1536 | 61.0 | $0.10/1M | 레거시 |

> **결정**: 비용 효율 최적, 한국어 성능 충분, K-AIR에서도 동일 모델 사용으로 호환성 보장

---

## 3. 임베딩 생성 전략

### 3.1 테이블 임베딩 입력

```python
def build_table_embedding_text(table_name: str, description: str, columns: list) -> str:
    """
    Build embedding input text for a Table node.
    Includes table description + key column names/types.
    """
    col_summary = ", ".join([
        f"{c['name']}({c['data_type']})"
        for c in columns[:10]  # Top 10 columns
    ])

    return f"테이블: {table_name}\n설명: {description}\n주요 컬럼: {col_summary}"


# Example output:
# "테이블: processes\n설명: 프로세스 실행 내역. 비즈니스 프로세스에서 각 단계의
#  유형, 지표, 상태를 기록한다.\n주요 컬럼: id(uuid),
#  case_id(uuid), org_id(uuid), process_type(varchar), ..."
```

### 3.2 컬럼 임베딩 입력

```python
def build_column_embedding_text(
    table_name: str, column_name: str, data_type: str, description: str
) -> str:
    """
    Build embedding input text for a Column node.
    """
    return (
        f"테이블 {table_name}의 컬럼 {column_name}\n"
        f"데이터 타입: {data_type}\n"
        f"설명: {description}"
    )

# Example:
# "테이블 processes의 컬럼 efficiency_rate\n데이터 타입: numeric\n
#  설명: 프로세스 효율성 비율. 해당 프로세스의 입력 대비 출력 비율 (%)"
```

### 3.3 쿼리 임베딩 입력

```python
def build_query_embedding_text(question: str, description: str) -> str:
    """
    Build embedding input text for a Query node.
    Uses the natural language question primarily.
    """
    text = question
    if description:
        text += f"\n{description}"
    return text

# Example:
# "조직별 프로세스 효율성을 조회하시오\n각 조직의 프로세스 효율성
#  비율과 처리량을 반환"
```

### 3.4 임베딩 생성 구현

```python
# app/core/embedding_client.py
class EmbeddingClient:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text"""
        response = await self.client.embeddings.create(
            model=self.model,
            input=text
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts (max 2048 per batch)"""
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts[:2048]
        )
        return [item.embedding for item in response.data]
```

---

## 4. 검색 파라미터

### 4.1 기본 파라미터

| 파라미터 | 값 | 근거 |
|---------|---|------|
| Top-K (Table) | 5 | K-AIR에서 검증된 최적값 |
| Top-K (Column) | 10 | 테이블보다 세분화된 검색 필요 |
| Top-K (Query) | 5 | 유사 쿼리 참조용 |
| min_score | 0.7 | 0.7 미만은 관련성 낮음 (경험적) |

### 4.2 Neo4j 벡터 검색 성능

| 지표 | 예상 값 | 조건 |
|------|--------|------|
| 검색 지연 | < 50ms | 1,000 노드 이하 |
| 검색 지연 | < 200ms | 10,000 노드 이하 |
| 인덱스 빌드 | < 30초 | 1,000 노드 |

### 4.3 Neo4j 벡터 인덱스 내부

Neo4j 5의 벡터 인덱스는 HNSW (Hierarchical Navigable Small Worlds) 알고리즘을 사용한다.

| HNSW 파라미터 | 기본값 | 설명 |
|-------------|-------|------|
| `m` | 16 | 각 노드의 이웃 수 |
| `efConstruction` | 200 | 빌드 시 탐색 깊이 |
| `efSearch` | - | 검색 시 탐색 깊이 (Top-K에 비례) |

---

## 5. 임베딩 갱신 전략

### 5.1 자동 갱신 트리거

| 이벤트 | 갱신 대상 |
|--------|----------|
| 테이블 description 변경 | 해당 Table 노드 임베딩 |
| 컬럼 description 변경 | 해당 Column 노드 임베딩 |
| 새 쿼리 등록 | 해당 Query 노드 임베딩 |
| 배치 임베딩 API 호출 | 전체 또는 지정 범위 |

### 5.2 임베딩 일관성

```python
async def update_table_embedding(self, table_name: str, new_description: str):
    """
    Atomic update: description + embedding together.
    Ensures embedding always matches current description.
    """
    # 1. Generate new embedding
    embed_text = build_table_embedding_text(table_name, new_description, columns)
    new_embedding = await self.embedding_client.embed(embed_text)

    # 2. Update Neo4j atomically
    async with self.neo4j.session() as session:
        await session.run(
            """
            MATCH (t:Table {name: $name})
            SET t.description = $description,
                t.embedding = $embedding,
                t.updated_at = datetime()
            """,
            name=table_name,
            description=new_description,
            embedding=new_embedding
        )
```

---

## 6. 향후 확장: 온톨로지 노드 벡터 인덱스

4계층 온톨로지 노드에도 벡터 인덱스를 추가할 수 있다. 현재는 계획 단계이다.

| 인덱스 후보 | 대상 | 용도 | 우선순위 |
|-----------|------|------|---------|
| `resource_vector` | Resource | 자원 유사도 검색 | 중 |
| `process_vector` | Process | 프로세스 유사도 검색 | 저 |

> **미결정**: 온톨로지 노드 벡터 검색의 실제 사용 시나리오가 확인된 후 결정

---

## 근거 문서

- `01_architecture/graph-search.md` (검색 아키텍처)
- `06_data/neo4j-schema.md` (Neo4j 스키마)
- ADR-001: Neo4j 5 선택 근거
