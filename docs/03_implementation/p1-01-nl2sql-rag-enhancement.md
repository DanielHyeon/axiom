# P1-01: NL2SQL RAG 파이프라인 고도화 구현 계획

> Gap Analysis 항목 #6-#11 대응
> 작성일: 2026-03-20
> 대상 서비스: `services/oracle/`
> 소스 레퍼런스: KAIR `robo-data-text2sql/app/react/tools/build_sql_context_parts/`

---

## 1. 현재 상태 분석

### 1.1 Axiom Oracle 프로덕션 파이프라인 플로우

```
[POST /text2sql/ask]
    |
    v
NL2SQLPipeline.execute()                    # nl2sql_pipeline.py:255
    |
    +-- (1) llm_factory.embed(question)     # 벡터 임베딩 (MockLLMClient → [0.0]*1536)
    |
    +-- (2) _search_and_catalog()           # nl2sql_pipeline.py:155
    |       |
    |       +-- oracle_synapse_acl.search_schema_context()   # synapse_acl.py:209
    |       |       -> POST /api/v3/synapse/graph/search
    |       |       -> SchemaSearchResult(tables, value_mappings, cached_queries)
    |       |
    |       +-- _fetch_ontology_context()   # O3: 온톨로지 컨텍스트
    |               -> POST /api/v3/synapse/graph/ontology/context
    |
    +-- (3) _format_schema_ddl()            # 전체 스키마를 DDL 문자열로 변환
    |       -> "CREATE TABLE sales (...);" 형태의 전체 테이블 DDL
    |       -> value_mappings, similar_queries를 문자열로 append (500자 절단)
    |
    +-- (4) _generate_sql_llm()             # LLM SQL 생성
    |       -> 시스템 프롬프트 + DDL + question → SQL
    |
    +-- (5) sql_guard.guard_sql()           # sql_guard.py
    |       -> 문자열 FORBIDDEN_KEYWORDS 매칭 (regex 없음)
    |       -> sqlglot.parse_one() → SELECT 체크
    |       -> JOIN 깊이, 서브쿼리 깊이 체크
    |       -> LIMIT 자동 추가 (FIX)
    |
    +-- (6) sql_executor.execute_sql()      # 실행
    +-- (7) recommend_visualization()       # 시각화 추천
    +-- (8) cache_postprocessor.process()   # 캐시 (fire-and-forget)
    +-- (9) _forward_to_insight()           # Insight 로그 (fire-and-forget)
```

**핵심 문제점:**
- **스키마 과적**: `_format_schema_ddl()`이 검색된 **모든** 테이블의 전체 DDL을 LLM에 전달 -> 토큰 낭비
- **단축 RAG**: Synapse BC에 검색 위임 (단일 HTTP 호출) -> 멀티축 검색, HyDE, FK 순회 불가
- **문자열 가드**: `sql_guard.py`가 문자열 패턴 매칭 위주 -> AST 기반 심층 검증 부재
- **Enum 캐시 미활성**: `enum_cache_bootstrap.py`가 빈 스텁 (16줄, Mock only)
- **graph_search.py 미연결**: 5축 RRF + FK hop 스캐폴드 존재하나 파이프라인에 미사용

### 1.2 기존 스캐폴드 분석: `graph_search.py`

```python
# graph_search.py 현재 구조 (88줄)
class GraphSearchService:
    reciprocal_rank_fusion()     # Dict[str, List[SearchResult]] -> RRF 융합 (동작)
    pseudo_relevance_feedback()  # PRF 벡터 보간 (동작)
    search_relevant_schema()     # 5축 오케스트레이션 (Mock data 하드코딩)
        # Axis 1: Question Vector Match       -> Mock
        # Axis 2: HyDE Vector Match           -> Mock
        # Axis 3: Keyword Match               -> Mock
        # Axis 4: Intent Match                -> Mock (빈 리스트)
        # Axis 5: PRF Match                   -> Mock
        # FK Hops                             -> Mock 경로 하드코딩
```

**활용 가능 로직:** `reciprocal_rank_fusion()`, `pseudo_relevance_feedback()` -- 알고리즘은 올바르나 Neo4j 연결 부재

### 1.3 ACL 계층 구조

```
nl2sql_pipeline.py
    -> synapse_acl.py (OracleSynapseACL)    # 외부 BC 호출 + 도메인 변환
        -> HTTP POST to Synapse BC           # 검색 위임

graph_search.py (GraphSearchService)         # 로컬 Neo4j 직접 쿼리 (미사용)
```

**전환 전략**: `synapse_acl` 경로를 기본값으로 유지하면서 `graph_search` 경로를 feature flag로 활성화

---

## 2. KAIR 소스 분석: build_sql_context 10단계 오케스트레이션

KAIR `orchestrator.py`의 `execute()` 함수는 10단계 파이프라인:

```
(1) Embedding           # 질문 벡터 임베딩 (단일)
(1.5+3) HyDE + Similar  # 병렬 실행
    HyDE:               # hyde_flow.py → HyDE-Schema 생성 → 가상 스키마 임베딩 + 키워드 추출
    Similar:             # similar_flow.py → intent 추출 → 유사 쿼리 + value_mappings
(4) Table Search         # table_search_flow.py → 4축 벡터 검색 + PRF + FK 확장 + LLM 리랭크
(4.5) FK Prefetch        # neo4j.py → _neo4j_fetch_fk_relationships (join column 강제용)
(4.55) Schema Prefetch   # neo4j.py → _neo4j_fetch_table_schemas (컬럼 스코어링 + enum 값 hint)
(5) Column Search        # column_search_flow.py → 테이블별 top-K 컬럼 벡터 검색
(5.5) Schema XML         # schema_xml.py → 선별된 테이블+컬럼만 XML 생성
(5.55) Column Value Hints # column_value_hints_flow.py → 캐시된 enum 값 hint XML
(5.6) FK XML             # fk_flow.py → FK 관계 XML
(6) Resolved Values      # resolved_values_flow.py → 자연어→DB값 매핑 해결
(7) Suggestions          # suggestions_flow.py → 모호성 해소 제안
(8) Light Queries        # light_queries_flow.py → 경량 미리보기 쿼리 생성 + 실행 + 결과
```

**핵심 패턴:**
1. **Neo4j 직접 쿼리**: 모든 벡터 검색이 Neo4j 벡터 인덱스 직접 호출
2. **멀티축 가중 합산**: `table_search_flow.py`에서 4축(question/hyde/regex/intent) + PRF + FK 확장
3. **서브스키마 추출**: 최종 LLM 컨텍스트에 `selected_tables`의 `per_table_columns`만 포함
4. **HyDE 2단계**: 가상 SQL 생성 -> 임베딩 텍스트 생성 -> 스키마 임베딩 + 키워드
5. **Enum 캐시**: `Column.enum_values`에 JSON 저장, 런타임에 조회 (cold-start = bootstrap)

---

## 3. 구현 항목별 상세 계획

---

### #6. SQLGlot AST 기반 검증 강화

**현재 상태**: `app/core/sql_guard.py` (107줄)
- 문자열 `FORBIDDEN_KEYWORDS` 리스트 비교 (`"--"`, `"/*"` 등 주석 패턴 포함)
- `sqlglot.parse_one()` 후 `isinstance(parsed, exp.Select)` 체크
- JOIN 깊이: `find_all(exp.Join)` 개수 제한
- 서브쿼리 깊이: 재귀 `walk()` (버그 있음 -- 실제 depth가 아닌 Subquery 노드 수 카운트)
- LIMIT 자동 추가: `fixed_ast.limit(config.row_limit)`

**KAIR 참조**: `app/core/sql_guard.py` (154줄)
- `sqlglot.parse_one(sql, read=dialect)` + dialect 매핑
- AST 기반 forbidden 노드 타입 검사: `isinstance(node, (exp.Insert, exp.Update, ...))`
- 체계적 서브쿼리 depth 재귀 계산
- `_check_allowed_tables()`: AST에서 테이블 이름 추출 -> 화이트리스트 검증

**변경 대상 파일**: `services/oracle/app/core/sql_guard.py`

**구현 내용:**

#### Step 6-1: 문자열 매칭 제거, AST 노드 검사 전환

```python
# 변경: guard_sql() 메서드
# AS-IS:
sql_upper = sql_query.upper()
for keyword in self.FORBIDDEN_KEYWORDS:
    if keyword in sql_upper:
        found.append(keyword)

# TO-BE:
def guard_sql(self, sql_query: str, config: GuardConfig = None) -> GuardResult:
    config = config or GuardConfig()
    violations: list[str] = []

    # Phase 1: AST 파싱
    try:
        parsed = sqlglot.parse_one(sql_query, dialect=config.dialect)
    except (sqlglot.errors.ParseError, sqlglot.errors.TokenError) as e:
        return GuardResult(status="REJECT", sql=sql_query, violations=[f"SQL 파싱 실패: {e}"])

    # Phase 2: Statement 타입 검증 (SELECT만 허용)
    if not isinstance(parsed, sqlglot.exp.Select):
        return GuardResult(status="REJECT", sql=sql_query,
                           violations=[f"SELECT 문만 허용. 감지: {type(parsed).__name__}"])

    # Phase 3: AST 노드 순회 — 금지 노드 타입 검출
    _FORBIDDEN_TYPES = (
        sqlglot.exp.Insert, sqlglot.exp.Update, sqlglot.exp.Delete,
        sqlglot.exp.Drop, sqlglot.exp.Create, sqlglot.exp.Alter,
        sqlglot.exp.Grant, sqlglot.exp.SetItem,  # EXEC/EXECUTE
    )
    for node in parsed.walk():
        if isinstance(node, _FORBIDDEN_TYPES):
            violations.append(f"금지된 SQL 연산: {type(node).__name__}")

    if violations:
        return GuardResult(status="REJECT", sql=sql_query, violations=violations)

    # Phase 4: 구조적 제한
    # ... (기존 JOIN/서브쿼리 깊이 로직 유지)
```

#### Step 6-2: 서브쿼리 깊이 측정 버그 수정

```python
# AS-IS: _measure_subquery_depth_simple() -- 버그: depth가 아닌 node count
# TO-BE: 정확한 재귀 depth 계산 (KAIR 패턴 참조)
def _measure_subquery_depth(self, ast: sqlglot.exp.Expression) -> int:
    """AST 트리를 재귀 순회하여 최대 서브쿼리 중첩 깊이를 계산."""
    def _walk(node: sqlglot.exp.Expression, depth: int) -> int:
        max_d = depth
        if isinstance(node, sqlglot.exp.Subquery):
            depth += 1
            max_d = depth
        for child in node.iter_expressions():
            max_d = max(max_d, _walk(child, depth))
        return max_d
    return _walk(ast, 0)
```

#### Step 6-3: 화이트리스트 테이블 검증 추가

```python
# GuardConfig에 allowed_tables 필드 추가
class GuardConfig(BaseModel):
    dialect: str = "postgres"
    max_join_depth: int = 5
    max_subquery_depth: int = 3
    row_limit: int = 1000
    allowed_tables: list[str] | None = None  # 신규: 허용 테이블 화이트리스트

# guard_sql() 내부에 추가:
if config.allowed_tables:
    referenced_tables = {
        table.name.lower()
        for table in parsed.find_all(sqlglot.exp.Table)
    }
    allowed_set = {t.lower() for t in config.allowed_tables}
    unauthorized = referenced_tables - allowed_set
    if unauthorized:
        violations.append(f"허용되지 않은 테이블: {', '.join(sorted(unauthorized))}")
```

#### Step 6-4: 다중 statement 방어 강화

```python
# sqlglot.parse()로 다중 statement 감지
parsed_list = sqlglot.parse(sql_query, dialect=config.dialect)
if len(parsed_list) > 1:
    return GuardResult(status="REJECT", sql=sql_query,
                       violations=["다중 SQL 문 감지 — 단일 SELECT만 허용"])
```

**복잡도**: Medium
**의존성**: 없음 (독립 모듈)
**검증**: 기존 테스트 + 공격 SQL 벡터 30개 추가 테스트

---

### #7. 서브스키마 추출 (LLM 컨텍스트 축소)

**현재 상태**: `nl2sql_pipeline.py`
- `_format_schema_ddl()`: 검색된 **모든** 테이블의 전체 DDL을 문자열 변환
- 컬럼 필터링 없음, 타입 힌트는 하드코딩 딕셔너리 (`_COLUMN_TYPE_HINTS`)

**KAIR 참조**: `schema_xml.py` + `column_search_flow.py`
- 테이블 리랭크 -> top-K 테이블만 선택
- 테이블별 top-K 컬럼만 벡터 검색으로 선택
- 최종 XML에 `selected_tables`의 `per_table_columns`만 포함

**변경 대상 파일**:
- `services/oracle/app/pipelines/nl2sql_pipeline.py`
- `services/oracle/app/core/graph_search.py` (신규 함수 추가)

**구현 내용:**

#### Step 7-1: SchemaContext 도메인 모델 생성

```python
# 신규 파일: services/oracle/app/core/schema_context.py

from dataclasses import dataclass, field

@dataclass
class RelevantColumn:
    """검색으로 선별된 관련 컬럼."""
    name: str
    data_type: str = "varchar"
    description: str = ""
    score: float = 0.0
    is_key: bool = False

@dataclass
class RelevantTable:
    """검색으로 선별된 관련 테이블 (서브스키마)."""
    name: str
    schema: str = ""
    description: str = ""
    columns: list[RelevantColumn] = field(default_factory=list)
    score: float = 0.0

@dataclass
class SubSchemaContext:
    """LLM에 전달할 축소된 스키마 컨텍스트."""
    tables: list[RelevantTable] = field(default_factory=list)
    fk_relationships: list[dict] = field(default_factory=list)
    value_mappings: list[dict] = field(default_factory=list)
    similar_queries: list[dict] = field(default_factory=list)
    enum_hints: list[dict] = field(default_factory=list)  # #8 enum cache
```

#### Step 7-2: _format_sub_schema_ddl() 신규 메서드

```python
# nl2sql_pipeline.py에 추가
def _format_sub_schema_ddl(self, ctx: SubSchemaContext) -> str:
    """서브스키마만으로 축소된 DDL + 컨텍스트 생성.

    AS-IS: 전체 테이블 전체 컬럼 DDL
    TO-BE: 관련 테이블의 관련 컬럼만 DDL + FK + value_mappings + enum_hints
    """
    lines: list[str] = []
    for t in ctx.tables:
        col_defs = []
        for c in t.columns:
            type_str = c.data_type or "VARCHAR"
            pk = " PRIMARY KEY" if c.is_key else ""
            desc = f"  -- {c.description}" if c.description else ""
            col_defs.append(f"  {c.name} {type_str}{pk}{desc}")
        table_name = f"{t.schema}.{t.name}" if t.schema else t.name
        table_desc = f"  -- {t.description}" if t.description else ""
        cols = ",\n".join(col_defs)
        lines.append(f"CREATE TABLE {table_name} ({table_desc}\n{cols}\n);")

    ddl = "\n\n".join(lines)

    # FK 관계
    if ctx.fk_relationships:
        fk_lines = []
        for fk in ctx.fk_relationships[:20]:
            fk_lines.append(
                f"  {fk.get('from_table','')}.{fk.get('from_column','')} "
                f"-> {fk.get('to_table','')}.{fk.get('to_column','')}"
            )
        ddl += "\n\n-- Foreign Key Relationships:\n" + "\n".join(fk_lines)

    # Enum 힌트 (#8과 연동)
    if ctx.enum_hints:
        hints = []
        for h in ctx.enum_hints[:30]:
            values_str = ", ".join([f"'{v}'" for v in h.get("values", [])[:10]])
            hints.append(f"  {h.get('table','')}.{h.get('column','')}: [{values_str}]")
        ddl += "\n\n-- Known Column Values:\n" + "\n".join(hints)

    # Value mappings
    if ctx.value_mappings:
        ddl += "\n\n-- Value Mappings (natural -> DB):\n"
        for vm in ctx.value_mappings[:10]:
            ddl += f"  '{vm.get('natural_language','')}' -> '{vm.get('db_value','')}' ({vm.get('table','')}.{vm.get('column','')})\n"

    # Similar queries
    if ctx.similar_queries:
        ddl += "\n\n-- Similar Cached Queries:\n"
        for sq in ctx.similar_queries[:3]:
            ddl += f"  Q: {sq.get('question','')[:100]}\n  SQL: {sq.get('sql','')[:200]}\n\n"

    return ddl
```

#### Step 7-3: 파이프라인 통합 — 전체 DDL을 서브스키마로 교체

```python
# nl2sql_pipeline.py의 execute() 메서드 변경:

# AS-IS:
schema_ddl = self._format_schema_ddl(schemas, value_mappings, similar_queries)

# TO-BE:
sub_schema = self._build_sub_schema_context(
    schema_catalog, value_mappings, similar_queries,
    question=question, question_vector=question_vector,
)
schema_ddl = self._format_sub_schema_ddl(sub_schema)
```

`_build_sub_schema_context()` 내부에서:
1. 테이블별 score 기준 top-K 테이블 선택 (기본 K=10)
2. 선택된 테이블의 컬럼 중 질문과 관련된 top-N 컬럼만 선택 (기본 N=15)
3. FK 관계를 선택된 테이블 간으로 제한

**복잡도**: Medium
**의존성**: #9 (graph_search 연결 시 full benefit)
**검증**: 기존 `/text2sql/ask` 엔드포인트 동일 입력/출력 비교

---

### #8. Enum 캐시 활성화

**현재 상태**: `app/pipelines/enum_cache_bootstrap.py` (16줄 빈 스텁)

**KAIR 참조**: `app/core/enum_cache_bootstrap.py` (511줄)
- Neo4j에서 후보 컬럼 조회 (text/char dtype + name hint 패턴)
- `SELECT DISTINCT col, COUNT(*) GROUP BY col LIMIT max_values+1`
- cardinality > max_values -> skip
- `Column.enum_values = JSON`, `Column.cardinality = int` 저장
- 동시성 제어: `asyncio.Semaphore(6)`, DB/Neo4j 세션 Lock

**변경 대상 파일**:
- `services/oracle/app/pipelines/enum_cache_bootstrap.py` (전면 재작성)
- `services/oracle/app/main.py` (startup에 bootstrap 호출 추가)
- `services/oracle/app/core/config.py` (설정 추가)

**구현 내용:**

#### Step 8-1: config.py에 enum 캐시 설정 추가

```python
# config.py에 추가
class Settings(BaseSettings):
    # ... 기존 설정 ...

    # Enum Cache Bootstrap
    ENUM_CACHE_ENABLED: bool = True
    ENUM_CACHE_MAX_VALUES: int = 100      # 100개 이하 distinct 값만 캐시
    ENUM_CACHE_MAX_COLUMNS: int = 2000    # 스캔 대상 최대 컬럼 수
    ENUM_CACHE_QUERY_TIMEOUT_SEC: float = 2.0
    ENUM_CACHE_CONCURRENCY: int = 4
    ENUM_CACHE_TARGET_SCHEMA: str = "public"
```

#### Step 8-2: enum_cache_bootstrap.py 전면 재작성

Axiom은 Synapse BC를 경유하지 않고 **직접 PostgreSQL + Neo4j** 접근:

```python
# services/oracle/app/pipelines/enum_cache_bootstrap.py

import asyncio
import json
import re
import time
from dataclasses import dataclass

import psycopg2
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# 캐시 대상 컬럼 판별 패턴
_NAME_HINT_RE = re.compile(r"(name|nm|title|code|cd|type|status|category|region|department)$|"
                            r"(^|_)(name|nm|title|code|cd|type|status|category|region|department)($|_)", re.I)
_TEXT_DTYPE_RE = re.compile(r"(char|text|varchar)", re.I)

@dataclass(frozen=True)
class EnumCacheResult:
    scanned: int
    cached: int
    skipped_high_cardinality: int
    skipped_empty: int
    errors: int
    elapsed_ms: float

def _should_cache_column(col_name: str, dtype: str) -> bool:
    """컬럼명/타입 패턴으로 enum 캐시 대상 여부 판별."""
    return bool(_NAME_HINT_RE.search(col_name) or _TEXT_DTYPE_RE.search(dtype))

class EnumCacheBootstrap:
    """
    서비스 시작 시 실행.
    저카디널리티 VARCHAR 컬럼의 DISTINCT 값을 조회하여
    Neo4j Column.enum_values에 캐시.
    """

    async def run(self, datasource_id: str = "") -> EnumCacheResult | None:
        if not settings.ENUM_CACHE_ENABLED:
            logger.info("enum_cache_disabled")
            return None

        started = time.perf_counter()
        db_url = settings.QUERY_HISTORY_DATABASE_URL
        max_values = settings.ENUM_CACHE_MAX_VALUES

        try:
            conn = psycopg2.connect(db_url)
            conn.set_session(readonly=True, autocommit=True)
            cur = conn.cursor()
        except Exception as exc:
            logger.warning("enum_cache_db_connect_failed", error=str(exc))
            return None

        # Step 1: information_schema에서 text-like 컬럼 목록 조회
        cur.execute("""
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s
              AND data_type IN ('character varying', 'text', 'character')
            ORDER BY table_schema, table_name, ordinal_position
            LIMIT %s
        """, (settings.ENUM_CACHE_TARGET_SCHEMA, settings.ENUM_CACHE_MAX_COLUMNS))

        candidates = cur.fetchall()

        cached = 0
        skipped_hi = 0
        skipped_empty = 0
        errors = 0

        for (schema, table, column, dtype) in candidates:
            if not _should_cache_column(column, dtype):
                continue

            try:
                # Step 2: 각 컬럼의 DISTINCT 값 + 빈도 조회
                cur.execute(f"""
                    SELECT "{column}" AS value, COUNT(*) AS cnt
                    FROM "{schema}"."{table}"
                    WHERE "{column}" IS NOT NULL
                    GROUP BY "{column}"
                    ORDER BY cnt DESC
                    LIMIT {max_values + 1}
                """)
                rows = cur.fetchall()

                if not rows:
                    skipped_empty += 1
                    continue

                if len(rows) > max_values:
                    skipped_hi += 1
                    continue

                # Step 3: enum_values JSON 생성
                enum_values = [
                    {"value": str(r[0]), "count": int(r[1])}
                    for r in rows if r[0] is not None
                ]

                if not enum_values:
                    skipped_empty += 1
                    continue

                # Step 4: 캐시 저장 (향후 Neo4j Column 노드 업데이트)
                # Phase 1: 로컬 인메모리 캐시
                _enum_cache_store[f"{schema}.{table}.{column}"] = {
                    "values": enum_values,
                    "cardinality": len(enum_values),
                }
                cached += 1

            except Exception as exc:
                errors += 1
                if errors <= 3:
                    logger.warning("enum_cache_column_error",
                                   table=f"{schema}.{table}", column=column, error=str(exc))

        cur.close()
        conn.close()

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        result = EnumCacheResult(
            scanned=len(candidates),
            cached=cached,
            skipped_high_cardinality=skipped_hi,
            skipped_empty=skipped_empty,
            errors=errors,
            elapsed_ms=elapsed_ms,
        )
        logger.info("enum_cache_bootstrap_done",
                     cached=cached, scanned=len(candidates), elapsed_ms=round(elapsed_ms, 1))
        return result

# 인메모리 캐시 (서비스 수명 동안 유지)
_enum_cache_store: dict[str, dict] = {}

def get_enum_values(fqn: str) -> list[dict] | None:
    """런타임에 캐시된 enum 값 조회. fqn = "schema.table.column" """
    entry = _enum_cache_store.get(fqn.lower())
    return entry["values"] if entry else None

def get_enum_hints_for_tables(table_names: list[str], schema: str = "public") -> list[dict]:
    """#7 서브스키마와 연동: 지정 테이블의 enum hint 목록 반환."""
    hints = []
    prefix_map: dict[str, list] = {}
    for fqn, entry in _enum_cache_store.items():
        parts = fqn.split(".")
        if len(parts) == 3:
            tbl = parts[1]
            prefix_map.setdefault(tbl, []).append((parts[2], entry["values"]))

    for tbl in table_names:
        for col, values in prefix_map.get(tbl, []):
            hints.append({
                "table": tbl,
                "column": col,
                "values": [v["value"] for v in values[:10]],
                "cardinality": len(values),
            })
    return hints

enum_cache_bootstrap = EnumCacheBootstrap()
```

#### Step 8-3: main.py startup에 enum cache 호출 추가

```python
# main.py의 lifespan() 수정
@asynccontextmanager
async def lifespan(app: FastAPI):
    _seed_demo_tables()
    # Enum cache bootstrap (best-effort)
    from app.pipelines.enum_cache_bootstrap import enum_cache_bootstrap
    try:
        await enum_cache_bootstrap.run()
    except Exception as exc:
        logger.warning("enum_cache_startup_failed", error=str(exc))
    yield
```

**복잡도**: Medium
**의존성**: #7 (enum hints가 서브스키마 DDL에 포함)
**검증**: 서버 시작 후 `_enum_cache_store` 확인, `get_enum_hints_for_tables(["sales"])` 호출 검증

---

### #9. 멀티축 RAG 프로덕션 연결

**현재 상태**: `graph_search.py`의 `search_relevant_schema()`가 5축 Mock 데이터
**목표**: Mock을 Neo4j 실제 쿼리로 교체하고, 파이프라인에 연결

**변경 대상 파일**:
- `services/oracle/app/core/graph_search.py` (전면 재작성)
- `services/oracle/app/pipelines/nl2sql_pipeline.py` (호출 경로 전환)
- `services/oracle/app/core/config.py` (feature flag + 가중치 설정)

**구현 내용:**

#### Step 9-1: config.py에 RAG 설정 추가

```python
class Settings(BaseSettings):
    # ... 기존 ...

    # Graph Search RAG
    USE_LOCAL_GRAPH_SEARCH: bool = False    # True: graph_search.py 사용, False: synapse_acl 유지
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # 축별 가중치 (KAIR table_search_flow.py 참조)
    RAG_WEIGHT_QUESTION: float = 0.35
    RAG_WEIGHT_HYDE: float = 1.0
    RAG_WEIGHT_KEYWORD: float = 0.5
    RAG_WEIGHT_INTENT: float = 0.7
    RAG_WEIGHT_PRF: float = 0.8
    RAG_FK_BOOST: float = 0.01
    RAG_TOP_K_TABLES: int = 10
    RAG_TOP_K_COLUMNS_PER_TABLE: int = 15
    RAG_PER_AXIS_TOP_K: int = 20
```

#### Step 9-2: graph_search.py 프로덕션 재작성

```python
# services/oracle/app/core/graph_search.py

from __future__ import annotations
import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm_factory import llm_factory

import structlog
logger = structlog.get_logger()


class SearchResult(BaseModel):
    id: str
    name: str
    schema_name: str = ""
    type: str  # 'table', 'column', 'query'
    description: str = ""
    data_type: str = ""  # 컬럼 전용
    rrf_score: float = 0.0


@dataclass
class MultiAxisSearchResult:
    """멀티축 검색 최종 결과."""
    tables: list[SearchResult]
    columns_by_table: dict[str, list[SearchResult]]  # table_fqn -> columns
    fk_paths: list[dict]
    cached_queries: list[dict]
    value_mappings: list[dict]
    search_metadata: dict = None  # 디버그용


class GraphSearchService:
    """5축 멀티 RAG 검색 + RRF 융합 + FK 확장.

    KAIR build_sql_context orchestrator의 Axiom 적응:
    - Neo4j 벡터 인덱스 직접 쿼리
    - 5축: question / hyde / keyword / intent / PRF
    - Reciprocal Rank Fusion (RRF)
    - FK 1-hop 확장
    """

    def __init__(self):
        self._neo4j_driver = None

    async def _get_neo4j_session(self):
        """Neo4j 세션 lazy init."""
        if self._neo4j_driver is None:
            from neo4j import AsyncGraphDatabase
            self._neo4j_driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return self._neo4j_driver.session()

    # --- RRF (기존 로직 유지, 제네릭화) ---

    def reciprocal_rank_fusion(
        self,
        results_by_axis: dict[str, list[SearchResult]],
        weights: dict[str, float] | None = None,
        k: int = 60,
    ) -> list[SearchResult]:
        """가중 RRF 융합."""
        fused_scores: dict[str, float] = defaultdict(float)
        items: dict[str, SearchResult] = {}
        weights = weights or {}

        for axis, results in results_by_axis.items():
            w = weights.get(axis, 1.0)
            for rank, result in enumerate(results, start=1):
                fused_scores[result.id] += w / (k + rank)
                if result.id not in items or result.rrf_score < fused_scores[result.id]:
                    items[result.id] = result

        sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        final = []
        for id_, score in sorted_results:
            res = items[id_]
            res.rrf_score = score
            final.append(res)
        return final

    # --- PRF (기존 로직 유지) ---

    async def pseudo_relevance_feedback(
        self,
        initial_vectors: list[list[float]],
        question_vector: list[float],
        alpha: float = 0.7,
    ) -> list[float]:
        if not initial_vectors:
            return question_vector
        mean_vector = np.mean(initial_vectors, axis=0)
        prf_vector = alpha * np.array(question_vector) + (1 - alpha) * mean_vector
        return prf_vector.tolist()

    # --- Neo4j 벡터 검색 ---

    async def _search_tables_by_vector(
        self, vector: list[float], top_k: int = 20,
    ) -> list[SearchResult]:
        """Neo4j 테이블 벡터 인덱스 검색."""
        cypher = """
        CALL db.index.vector.queryNodes('table_vec_index', $k, $embedding)
        YIELD node, score
        WHERE node:Table
        RETURN
          COALESCE(node.schema, '') AS schema,
          COALESCE(node.name, '') AS name,
          COALESCE(node.description, '') AS description,
          score AS score
        ORDER BY score DESC
        LIMIT $k
        """
        async with await self._get_neo4j_session() as session:
            result = await session.run(cypher, k=top_k, embedding=vector)
            records = await result.data()

        return [
            SearchResult(
                id=f"{r['schema']}.{r['name']}".lower(),
                name=r['name'],
                schema_name=r['schema'],
                type='table',
                description=r.get('description', ''),
                rrf_score=float(r.get('score', 0)),
            )
            for r in records
        ]

    async def _search_columns_for_table(
        self, vector: list[float], table_fqn: str, top_k: int = 15,
    ) -> list[SearchResult]:
        """특정 테이블의 컬럼 벡터 검색."""
        parts = table_fqn.split(".", 1)
        schema = parts[0] if len(parts) > 1 else ""
        table = parts[-1]

        cypher = """
        MATCH (t:Table)-[:HAS_COLUMN]->(c:Column)
        WHERE toLower(t.name) = $table_name
          AND ($schema IS NULL OR toLower(COALESCE(t.schema,'')) = $schema)
          AND c.vector IS NOT NULL
        WITH c, t, vector.similarity.cosine(c.vector, $embedding) AS score
        RETURN
          c.name AS name,
          c.dtype AS dtype,
          c.description AS description,
          score AS score
        ORDER BY score DESC
        LIMIT $k
        """
        async with await self._get_neo4j_session() as session:
            result = await session.run(
                cypher, table_name=table.lower(),
                schema=schema.lower() if schema else None,
                embedding=vector, k=top_k,
            )
            records = await result.data()

        return [
            SearchResult(
                id=f"{table_fqn}.{r['name']}".lower(),
                name=r['name'],
                type='column',
                data_type=r.get('dtype', ''),
                description=r.get('description', ''),
                rrf_score=float(r.get('score', 0)),
            )
            for r in records
        ]

    async def _fetch_fk_neighbors_1hop(
        self, seed_fqns: list[str], limit: int = 50,
    ) -> list[SearchResult]:
        """FK 1-hop 이웃 테이블 확장."""
        if not seed_fqns:
            return []

        cypher = """
        UNWIND $seeds AS seed
        MATCH (t1:Table)-[:HAS_COLUMN]->(c1:Column)-[:FK_TO]->(c2:Column)<-[:HAS_COLUMN]-(t2:Table)
        WITH t2,
             (toLower(COALESCE(t1.schema,'')) + '.' + toLower(t1.name)) AS fqn1
        WHERE fqn1 = seed
        RETURN DISTINCT
          COALESCE(t2.schema,'') AS schema,
          t2.name AS name,
          COALESCE(t2.description,'') AS description
        LIMIT $limit
        """
        async with await self._get_neo4j_session() as session:
            result = await session.run(
                cypher, seeds=[s.lower() for s in seed_fqns], limit=limit
            )
            records = await result.data()

        return [
            SearchResult(
                id=f"{r['schema']}.{r['name']}".lower(),
                name=r['name'],
                schema_name=r['schema'],
                type='table',
                description=r.get('description', ''),
                rrf_score=settings.RAG_FK_BOOST,
            )
            for r in records
        ]

    async def _fetch_fk_relationships(
        self, table_fqns: list[str], limit: int = 50,
    ) -> list[dict]:
        """선택된 테이블 간 FK 관계 조회."""
        if not table_fqns:
            return []

        cypher = """
        MATCH (t1:Table)-[:HAS_COLUMN]->(c1:Column)-[fk:FK_TO]->(c2:Column)<-[:HAS_COLUMN]-(t2:Table)
        WITH t1, c1, c2, t2,
             (toLower(COALESCE(t1.schema,'')) + '.' + toLower(t1.name)) AS fqn1,
             (toLower(COALESCE(t2.schema,'')) + '.' + toLower(t2.name)) AS fqn2
        WHERE fqn1 IN $fqns AND fqn2 IN $fqns
        RETURN
          t1.name AS from_table, c1.name AS from_column,
          t2.name AS to_table, c2.name AS to_column
        LIMIT $limit
        """
        async with await self._get_neo4j_session() as session:
            result = await session.run(
                cypher, fqns=[f.lower() for f in table_fqns], limit=limit
            )
            return await result.data()

    # --- 5축 오케스트레이션 ---

    async def search_relevant_schema(
        self,
        question: str,
        question_vector: list[float],
        datasource_id: str,
        top_k: int | None = None,
        max_fk_hops: int = 1,
        hyde_vector: list[float] | None = None,     # #10 HyDE
        intent_vector: list[float] | None = None,
    ) -> MultiAxisSearchResult:
        """5축 동시 검색 → RRF 융합 → FK 확장 → 컬럼 검색."""
        top_k = top_k or settings.RAG_TOP_K_TABLES
        per_axis_k = settings.RAG_PER_AXIS_TOP_K

        # Axis 1: Question Vector
        axis_tasks = {
            "question": self._search_tables_by_vector(question_vector, per_axis_k),
        }

        # Axis 2: HyDE Vector (#10과 연동)
        if hyde_vector:
            axis_tasks["hyde"] = self._search_tables_by_vector(hyde_vector, per_axis_k)

        # Axis 3: Keyword (키워드 임베딩)
        try:
            import re
            keywords = re.findall(r'[\w가-힣]+', question)[:10]
            if keywords:
                kw_text = " ".join(keywords)
                kw_vector = await llm_factory.embed(kw_text)
                axis_tasks["keyword"] = self._search_tables_by_vector(kw_vector, per_axis_k)
        except Exception:
            pass

        # Axis 4: Intent Vector
        if intent_vector:
            axis_tasks["intent"] = self._search_tables_by_vector(intent_vector, per_axis_k)

        # 병렬 실행
        axis_keys = list(axis_tasks.keys())
        axis_results_list = await asyncio.gather(*axis_tasks.values(), return_exceptions=True)
        results_by_axis: dict[str, list[SearchResult]] = {}
        for key, res in zip(axis_keys, axis_results_list):
            if isinstance(res, Exception):
                logger.warning("graph_search_axis_failed", axis=key, error=str(res))
                continue
            results_by_axis[key] = res

        # RRF 융합
        weights = {
            "question": settings.RAG_WEIGHT_QUESTION,
            "hyde": settings.RAG_WEIGHT_HYDE,
            "keyword": settings.RAG_WEIGHT_KEYWORD,
            "intent": settings.RAG_WEIGHT_INTENT,
        }
        fused = self.reciprocal_rank_fusion(results_by_axis, weights=weights)

        # Axis 5: PRF (상위 결과 기반 피드백)
        if fused:
            top_vectors = [question_vector]  # 향후 테이블 벡터 조회로 확장
            prf_vector = await self.pseudo_relevance_feedback(top_vectors, question_vector)
            prf_results = await self._search_tables_by_vector(prf_vector, per_axis_k)
            results_by_axis["prf"] = prf_results
            weights["prf"] = settings.RAG_WEIGHT_PRF
            fused = self.reciprocal_rank_fusion(results_by_axis, weights=weights)

        # FK 확장
        seed_fqns = [r.id for r in fused[:min(top_k, 10)]]
        fk_neighbors = await self._fetch_fk_neighbors_1hop(seed_fqns, limit=30)

        # FK 이웃을 후보에 추가 (낮은 점수)
        existing_ids = {r.id for r in fused}
        for n in fk_neighbors:
            if n.id not in existing_ids:
                fused.append(n)
                existing_ids.add(n.id)

        # Top-K 테이블 선택
        selected_tables = fused[:top_k]

        # 테이블별 컬럼 검색
        col_per_table = settings.RAG_TOP_K_COLUMNS_PER_TABLE
        col_tasks = {
            t.id: self._search_columns_for_table(question_vector, t.id, col_per_table)
            for t in selected_tables
        }
        col_keys = list(col_tasks.keys())
        col_results = await asyncio.gather(*col_tasks.values(), return_exceptions=True)
        columns_by_table: dict[str, list[SearchResult]] = {}
        for key, res in zip(col_keys, col_results):
            if not isinstance(res, Exception):
                columns_by_table[key] = res

        # FK 관계 (선택된 테이블 간)
        fk_relationships = await self._fetch_fk_relationships(
            [t.id for t in selected_tables], limit=50
        )

        return MultiAxisSearchResult(
            tables=selected_tables,
            columns_by_table=columns_by_table,
            fk_paths=fk_relationships,
            cached_queries=[],
            value_mappings=[],
            search_metadata={
                "axes_used": list(results_by_axis.keys()),
                "fk_neighbors_count": len(fk_neighbors),
                "total_candidates": len(fused),
            },
        )


graph_search_service = GraphSearchService()
```

#### Step 9-3: nl2sql_pipeline.py의 검색 경로 전환

```python
# nl2sql_pipeline.py의 _search_and_catalog() 수정

async def _search_and_catalog(self, question, question_vector, tenant_id, datasource_id, case_id=None):
    """Feature flag에 따라 로컬 graph_search 또는 synapse_acl 사용."""

    if settings.USE_LOCAL_GRAPH_SEARCH and question_vector:
        # 신규 경로: 로컬 Neo4j 멀티축 RAG
        try:
            from app.core.graph_search import graph_search_service, MultiAxisSearchResult

            multi_result = await graph_search_service.search_relevant_schema(
                question=question,
                question_vector=question_vector,
                datasource_id=datasource_id,
                top_k=settings.RAG_TOP_K_TABLES,
            )

            # MultiAxisSearchResult -> (catalog, source, vm, sq, ontology)
            catalog = self._multi_axis_to_catalog(multi_result)
            ontology_ctx = await self._fetch_ontology_context(case_id, question, tenant_id)
            return catalog, "local_graph_rag", multi_result.value_mappings, multi_result.cached_queries, ontology_ctx
        except Exception as exc:
            logger.warning("local_graph_search_fallback", error=str(exc))

    # 기존 경로: synapse_acl (변경 없음)
    return await self._search_and_catalog_via_synapse(question, question_vector, tenant_id, datasource_id, case_id)
```

**복잡도**: High
**의존성**: Neo4j 연결 설정, 벡터 인덱스 사전 생성
**검증**: `USE_LOCAL_GRAPH_SEARCH=false`(기본) → 기존 동작, `=true` → Neo4j 경로

---

### #10. HyDE (Hypothetical Document Embeddings) 검색

**현재 상태**: 없음. 질문 벡터만 사용

**KAIR 참조**: `hyde_flow.py`
- `HydeSchemaGenerator.generate()` → 가상 SQL 스키마 구조 생성
- `build_hyde_embedding_text()` → 임베딩용 텍스트 합성
- 가상 스키마 임베딩 + 검색 키워드(테이블/컬럼) 추출
- 실패 시 fallback_terms(regex 추출 키워드) 사용

**변경 대상 파일**:
- `services/oracle/app/core/hyde.py` (신규 파일)
- `services/oracle/app/pipelines/nl2sql_pipeline.py` (HyDE 벡터 파이프라인 주입)

**구현 내용:**

#### Step 10-1: hyde.py 신규 모듈 생성

```python
# services/oracle/app/core/hyde.py
"""HyDE (Hypothetical Document Embeddings) for NL2SQL.

질문으로부터 가상 SQL/스키마 구조를 생성하고 임베딩하여
실제 스키마 벡터와의 유사도를 높인다.
"""
from __future__ import annotations

from dataclasses import dataclass
import structlog

from app.core.llm_factory import llm_factory

logger = structlog.get_logger()

_HYDE_SYSTEM_PROMPT = """You are a database schema expert. Given a natural language question about data,
generate a hypothetical SQL query and list the likely table/column names involved.

Output format (exactly):
TABLES: table1, table2
COLUMNS: col1, col2, col3
SQL: SELECT ...
"""

_HYDE_USER_TEMPLATE = "Question: {question}\n\nGenerate hypothetical schema context."


@dataclass
class HydeResult:
    """HyDE 생성 결과."""
    hyde_embedding: list[float]       # 가상 스키마 임베딩
    hyde_text: str                     # 임베딩에 사용된 텍스트
    keywords_tables: list[str]         # 추출된 테이블 키워드
    keywords_columns: list[str]        # 추출된 컬럼 키워드
    used_fallback: bool = False


async def generate_hyde(
    question: str,
    fallback_keywords: list[str] | None = None,
) -> HydeResult:
    """HyDE 텍스트 생성 → 임베딩.

    실패 시 질문 텍스트 + fallback_keywords로 대체.
    """
    q = (question or "").strip()
    if not q:
        return HydeResult(
            hyde_embedding=await llm_factory.embed(q),
            hyde_text=q,
            keywords_tables=[],
            keywords_columns=[],
            used_fallback=True,
        )

    hyde_text = ""
    keywords_tables: list[str] = []
    keywords_columns: list[str] = []
    used_fallback = False

    try:
        user_prompt = _HYDE_USER_TEMPLATE.format(question=q)
        response = await llm_factory.generate(
            user_prompt, system_prompt=_HYDE_SYSTEM_PROMPT, temperature=0.2
        )

        if response:
            hyde_text = response.strip()
            # 키워드 파싱
            for line in hyde_text.split("\n"):
                line = line.strip()
                if line.upper().startswith("TABLES:"):
                    keywords_tables = [t.strip() for t in line.split(":", 1)[1].split(",") if t.strip()]
                elif line.upper().startswith("COLUMNS:"):
                    keywords_columns = [c.strip() for c in line.split(":", 1)[1].split(",") if c.strip()]
    except Exception as exc:
        logger.warning("hyde_generation_failed", error=str(exc))
        used_fallback = True

    if not hyde_text:
        # Fallback: 질문 + 키워드 결합
        used_fallback = True
        fallback = fallback_keywords or []
        hyde_text = f"{q}\n{' '.join(fallback[:10])}"

    # 임베딩 생성
    hyde_embedding = await llm_factory.embed(hyde_text[:8000])

    return HydeResult(
        hyde_embedding=hyde_embedding,
        hyde_text=hyde_text,
        keywords_tables=keywords_tables[:10],
        keywords_columns=keywords_columns[:15],
        used_fallback=used_fallback,
    )
```

#### Step 10-2: 파이프라인 통합

```python
# nl2sql_pipeline.py의 execute() 메서드에 HyDE 단계 추가

async def execute(self, question, datasource_id, options=None, user=None, case_id=None):
    # ... 기존 코드 ...

    # 1. Embed
    question_vector = await llm_factory.embed(question)

    # 1.5 HyDE (신규) — question_vector와 병렬 가능하나, LLM 호출이므로 순차
    hyde_result = None
    if settings.USE_LOCAL_GRAPH_SEARCH:
        from app.core.hyde import generate_hyde
        try:
            fallback_kw = re.findall(r'[\w가-힣]+', question)[:10]
            hyde_result = await generate_hyde(question, fallback_keywords=fallback_kw)
        except Exception:
            pass

    # 2. Graph search (hyde_vector 전달)
    schema_catalog, schema_source, value_mappings, similar_queries, ontology_ctx = \
        await self._search_and_catalog(
            question, question_vector, tenant_id, datasource_id, case_id,
            hyde_vector=hyde_result.hyde_embedding if hyde_result else None,
        )
    # ... 나머지 동일 ...
```

**복잡도**: Medium
**의존성**: #9 (graph_search에 hyde_vector 파라미터 전달)
**검증**: HyDE 생성 로그 확인, hyde_embedding 벡터 차원 검증, fallback 경로 테스트

---

### #11. FK 그래프 순회 활성화

**현재 상태**: `graph_search.py`의 FK hop이 Mock 하드코딩

**KAIR 참조**:
- `neo4j.py` → `_neo4j_fetch_fk_neighbors_1hop()`: 실제 Cypher 쿼리
- `table_search_flow.py` → FK 확장: 1-hop + optional 2-hop, 부스트 점수
- `fk_flow.py` → FK 관계 XML 생성

**변경 대상 파일**: `graph_search.py`의 `_fetch_fk_neighbors_1hop()`, `_fetch_fk_relationships()`
(#9에서 이미 구현된 내용의 확장)

**구현 내용:**

#### Step 11-1: 2-hop FK 순회 옵션 추가

```python
# graph_search.py의 search_relevant_schema()에 2-hop 지원 추가

# config.py에 추가
RAG_FK_ENABLE_2HOP: bool = True
RAG_FK_SEED_K: int = 10        # FK 확장 시드 테이블 수
RAG_FK_MAX_NEIGHBORS: int = 30  # 최대 FK 이웃 수
```

```python
# graph_search.py의 FK 확장 부분 수정

# FK 1-hop
seed_fqns = [r.id for r in fused[:settings.RAG_FK_SEED_K]]
fk_neighbors = await self._fetch_fk_neighbors_1hop(seed_fqns, limit=settings.RAG_FK_MAX_NEIGHBORS)

# FK 2-hop (optional)
if settings.RAG_FK_ENABLE_2HOP and fk_neighbors:
    hop1_fqns = [n.id for n in fk_neighbors]
    combined_seeds = list(set(seed_fqns + hop1_fqns))
    hop2 = await self._fetch_fk_neighbors_1hop(
        combined_seeds, limit=settings.RAG_FK_MAX_NEIGHBORS
    )
    # 기존 + hop2에서 중복 제거
    existing_ids = {r.id for r in fused} | {n.id for n in fk_neighbors}
    for n in hop2:
        if n.id not in existing_ids:
            n.rrf_score = settings.RAG_FK_BOOST * 0.5  # 2-hop은 점수 반감
            fk_neighbors.append(n)
            existing_ids.add(n.id)
```

#### Step 11-2: FK 관계 정보를 서브스키마 컨텍스트에 포함

```python
# nl2sql_pipeline.py의 _build_sub_schema_context()에서 FK 관계 추출

def _build_sub_schema_context(self, multi_result, ...):
    ctx = SubSchemaContext()
    # ... 테이블/컬럼 변환 ...

    # FK 관계를 컨텍스트에 포함
    ctx.fk_relationships = multi_result.fk_paths
    return ctx
```

이로써 `_format_sub_schema_ddl()` (#7)에서 FK 관계가 LLM 프롬프트에 포함:
```
-- Foreign Key Relationships:
  sales.company_id -> companies.id
  orders.product_id -> products.id
```

#### Step 11-3: React Agent에도 FK 경로 전달

```python
# react_agent.py의 _select_tables()에 FK 확장 추가

if settings.USE_LOCAL_GRAPH_SEARCH:
    multi_result = await graph_search_service.search_relevant_schema(...)
    names = [t.name for t in multi_result.tables]
    # FK 확장된 테이블이 이미 포함됨
    return list(dict.fromkeys(names)), "멀티축 RAG + FK 확장 기반 테이블 선택"
```

**복잡도**: Low (대부분 #9에서 구현)
**의존성**: #9
**검증**: FK 관계가 있는 테이블 쿼리 시 FK neighbor가 결과에 포함되는지 확인

---

## 4. 마이그레이션 전략

### 4.1 점진적 전환 (Feature Flag 방식)

```
Phase 0 (현재):  USE_LOCAL_GRAPH_SEARCH=false
                 → 모든 요청이 synapse_acl 경로

Phase 1 (#6,#7,#8): USE_LOCAL_GRAPH_SEARCH=false (유지)
                 → SQLGuard AST 강화, 서브스키마 추출, Enum 캐시
                 → synapse_acl 경로에서도 benefit (서브스키마 + enum)

Phase 2 (#9,#10,#11): USE_LOCAL_GRAPH_SEARCH=true (전환)
                 → graph_search 경로 활성화
                 → synapse_acl 경로를 fallback으로 유지
                 → A/B 테스트 후 기본값 전환
```

### 4.2 호환성 보장

| 변경 항목 | 기존 API 계약 | 영향 |
|-----------|--------------|------|
| #6 SQLGuard | `GuardResult` 모델 동일 | 없음 (내부 로직만 변경) |
| #7 서브스키마 | LLM 프롬프트 내부 변경 | API 응답 동일 |
| #8 Enum 캐시 | 신규 모듈, API 변경 없음 | 없음 |
| #9 Graph Search | `search_relevant_schema()` 시그니처 확장 | 기존 호출 호환 |
| #10 HyDE | 신규 모듈 | 없음 |
| #11 FK | #9 내부 확장 | 없음 |

### 4.3 Rollback 계획

```python
# 환경변수 하나로 전체 롤백
USE_LOCAL_GRAPH_SEARCH=false  # → 즉시 synapse_acl 경로 복원
ENUM_CACHE_ENABLED=false      # → enum 캐시 비활성화
```

---

## 5. 의존성

### 5.1 Python 패키지 (requirements.txt 추가)

```
# 기존
sqlglot==23.0.0            # 이미 설치됨 -- #6에서 활용 확대

# 신규
neo4j==5.20.0              # Neo4j async driver (#9, #11)
numpy==1.26.4              # PRF 벡터 연산 (#9) -- 이미 graph_search.py에서 import
```

### 5.2 인프라 전제조건

| 항목 | 상태 | 필요 작업 |
|------|------|-----------|
| Neo4j 5.20 | Docker Compose 존재 | 벡터 인덱스 생성 (`table_vec_index`, `column_vec_index`) |
| PostgreSQL | 동작 중 | Enum 캐시용 읽기 전용 접근 확인 |
| Embedding API | MockLLMClient | 실제 모델 연동 시 변경 필요 |

### 5.3 Neo4j 벡터 인덱스 사전 생성

```cypher
-- 서비스 시작 전 1회 실행 (또는 bootstrap에서)
CREATE VECTOR INDEX table_vec_index IF NOT EXISTS
FOR (t:Table) ON (t.vector)
OPTIONS { indexConfig: { `vector.dimensions`: 1536, `vector.similarity_function`: 'cosine' } };

CREATE VECTOR INDEX column_vec_index IF NOT EXISTS
FOR (c:Column) ON (c.vector)
OPTIONS { indexConfig: { `vector.dimensions`: 1536, `vector.similarity_function`: 'cosine' } };
```

---

## 6. 테스트 계획

### 6.1 단위 테스트

| 모듈 | 테스트 파일 | 테스트 항목 |
|------|------------|------------|
| #6 SQLGuard | `tests/core/test_sql_guard.py` | AST 파싱 실패, 금지 노드 감지, 다중 statement, 서브쿼리 깊이, 화이트리스트 |
| #7 SubSchema | `tests/core/test_schema_context.py` | Top-K 테이블 선택, 컬럼 필터링, DDL 포맷 |
| #8 Enum Cache | `tests/pipelines/test_enum_cache.py` | 컬럼 필터링 패턴, 고카디널리티 skip, 캐시 저장/조회 |
| #9 GraphSearch | `tests/core/test_graph_search.py` | RRF 융합, PRF 벡터, 축별 검색 (Mock Neo4j) |
| #10 HyDE | `tests/core/test_hyde.py` | 생성 성공/실패, fallback, 키워드 파싱 |
| #11 FK | `tests/core/test_fk_traversal.py` | 1-hop, 2-hop, 중복 제거 |

### 6.2 Golden Query Set A/B 테스트 (50개)

```
카테고리 분포:
- 단일 테이블 집계 (15개): "서울전자 반도체 매출 합계"
- 다중 테이블 조인 (10개): FK 순회 필요한 쿼리
- 필터 + 그룹 (10개): 날짜/지역/카테고리 복합 조건
- 모호한 자연어 (5개): "지난달 실적 좋은 곳"
- Enum 값 매칭 (5개): "부산 지역 원자재 매출"
- 복합 서브쿼리 (5개): 중첩 SELECT 포함
```

A/B 비교 메트릭:
- **정확도**: 생성된 SQL이 올바른 결과를 반환하는 비율
- **토큰 효율**: LLM에 전달된 프롬프트 토큰 수 (서브스키마 < 전체 DDL)
- **응답 시간**: 전체 파이프라인 레이턴시

### 6.3 통합 테스트

```python
# tests/integration/test_nl2sql_e2e.py

@pytest.mark.asyncio
async def test_ask_with_local_graph_search():
    """USE_LOCAL_GRAPH_SEARCH=true 경로 E2E."""
    # 1. Neo4j에 테스트 스키마 seed
    # 2. POST /text2sql/ask
    # 3. 응답 SQL 검증
    # 4. 메타데이터의 schema_source == "local_graph_rag" 확인

@pytest.mark.asyncio
async def test_ask_fallback_to_synapse():
    """Neo4j 장애 시 synapse_acl fallback."""
    # 1. Neo4j 연결 불가 상태 모사
    # 2. POST /text2sql/ask
    # 3. 정상 응답 + schema_source == "synapse" 확인
```

---

## 7. 위험 요소

### 7.1 ACL 패턴 무결성

| 위험 | 영향도 | 완화 전략 |
|------|--------|----------|
| synapse_acl 우회로 인한 BC 경계 위반 | High | Feature flag로 경로 분리, synapse_acl 호출 완전 유지 |
| Neo4j 연결 실패 시 서비스 중단 | High | try/except + synapse_acl fallback, startup에서 Neo4j 없이도 부팅 가능 |
| 인메모리 enum 캐시 메모리 폭증 | Medium | `MAX_VALUES=100`, `MAX_COLUMNS=2000` 제한, 메모리 모니터링 |

### 7.2 하위 호환성

| 위험 | 영향도 | 완화 전략 |
|------|--------|----------|
| SQLGuard 강화로 기존 통과 SQL 거부 | Medium | 기존 테스트 전량 재실행, 거부 기준 문서화 |
| 서브스키마 축소로 LLM 컨텍스트 부족 | Medium | top_k 조정 가능, 전체 DDL fallback 유지 |
| HyDE 생성 지연으로 응답 시간 증가 | Low | HyDE 타임아웃 2초, 실패 시 skip (질문벡터만 사용) |

### 7.3 성능

| 항목 | 예상 레이턴시 추가 | 완화 |
|------|-------------------|------|
| HyDE LLM 호출 | +200-500ms | 비동기 + 타임아웃 |
| Neo4j 5축 검색 | +100-300ms (병렬) | asyncio.gather |
| FK 2-hop | +50-100ms | 결과 캐싱, seed_k 제한 |
| Enum bootstrap | 서비스 시작 시 1회 | 비동기, 서비스 가용성 미차단 |

---

## 8. 구현 순서 및 일정

```
Week 1:  #6 SQLGuard AST 강화 + #8 Enum 캐시 활성화
         → 독립 모듈, 기존 경로 영향 없음

Week 2:  #7 서브스키마 추출
         → #8 enum hints 통합

Week 3:  #9 멀티축 RAG 프로덕션 + #10 HyDE + #11 FK 순회
         → graph_search.py 전면 재작성, 파이프라인 연결

Week 4:  통합 테스트 + Golden Query A/B + 성능 튜닝
         → Feature flag 전환 결정
```

---

## 9. 파일 변경 목록 요약

### 신규 파일
| 파일 | 목적 |
|------|------|
| `app/core/schema_context.py` | #7 서브스키마 도메인 모델 |
| `app/core/hyde.py` | #10 HyDE 생성기 |
| `tests/core/test_sql_guard.py` | #6 SQLGuard 테스트 |
| `tests/core/test_schema_context.py` | #7 서브스키마 테스트 |
| `tests/pipelines/test_enum_cache.py` | #8 Enum 캐시 테스트 |
| `tests/core/test_graph_search.py` | #9 멀티축 RAG 테스트 |
| `tests/core/test_hyde.py` | #10 HyDE 테스트 |
| `tests/core/test_fk_traversal.py` | #11 FK 순회 테스트 |

### 수정 파일
| 파일 | 변경 내용 |
|------|----------|
| `app/core/sql_guard.py` | #6 AST 기반 검증 전환, 서브쿼리 depth 수정, 화이트리스트 추가 |
| `app/core/graph_search.py` | #9 #11 전면 재작성 (Mock -> Neo4j 실제 연결) |
| `app/core/config.py` | #8 #9 설정 추가 (enum 캐시, RAG 가중치, Neo4j, feature flag) |
| `app/pipelines/nl2sql_pipeline.py` | #7 #9 #10 서브스키마, 검색 경로 분기, HyDE 통합 |
| `app/pipelines/enum_cache_bootstrap.py` | #8 전면 재작성 (스텁 -> 실제 구현) |
| `app/main.py` | #8 startup에 enum cache 호출 추가 |
| `app/pipelines/react_agent.py` | #9 graph_search 경로 추가 |
| `requirements.txt` | `neo4j==5.20.0` 추가 |
