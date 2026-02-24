# Ontology Phase O3: NL2SQL 인지 엔진 통합

> **상위 문서**: [04d_nl2sql-ontology-gap-analysis.md](04d_nl2sql-ontology-gap-analysis.md)
> **해결 항목**: I11-I14
> **전략적 위치**: 전체 시스템의 **핵심** — NL2SQL을 키워드 매칭(Layer 0)에서 의미 인지(Layer 2)로 전환
> **버전**: v3.0 (Production Skeleton — 코딩 즉시 착수 가능 수준)

---

## §0. O3의 목표: 사고 순서를 바꾸는 것

O3는 NL2SQL 파이프라인의 **사고 순서**를 근본적으로 변경한다.

```text
[현재 — Layer 0: 키워드 매칭]
자연어 → 하드코딩 4테이블 매칭 → SQL 생성 (hallucination 높음)

[O3 후 — Layer 2: 의미 인지]
자연어 → 온톨로지 그래프 탐색 → 비즈니스 용어 해석 → 물리 스키마 매핑 → SQL 생성
```

**이것은 검색의 개선이 아니라 인지 구조의 전환이다.**

핵심 설계 원칙:

1. **O3는 O2 없이도 동작해야 한다** — O2의 `MAPS_TO` 관계가 없으면 fulltext fallback으로 동작
2. **O2가 완성되면 자동으로 더 정확해진다** — `MAPS_TO` 관계가 생기면 confidence가 올라감
3. **실패는 침묵이 아니라 근거 부족 표시** — 매핑 근거가 불충분하면 "근거 부족" 배지로 사용자에게 표시
4. **그래프 폭발 방지** — depth/limit/관계 allowlist/row cap으로 제한
5. **반환은 "raw graph"가 아니라 컨텍스트용 힌트 세트** — Oracle에 넘길 목적으로 정리

완성 시 기대 효과:

| 사용자 질문 | 현재 (Layer 0) | O3 후 (Layer 2) |
| --- | --- | --- |
| "매출 추이" | 4테이블 중 매칭 실패 → hallucination | `Revenue:Measure` → `revenue.amount` (confidence 0.92) |
| "고객 이탈률" | `cases` 테이블 잘못 매칭 | `churn_rate:KPI` → `customer.status = 'churned'` (confidence 0.88) |
| "신규 조직 증가" | `organizations` 이름만 매칭 | `onboarding:Process` → `organization.created_at` (confidence 0.85) |

---

## §1. 데이터 계약 — Synapse 측 + Oracle 측 (양면)

O3의 데이터는 **두 BC의 경계**를 넘나든다. 각 BC는 자체 도메인 모델을 갖는다.

### 1.1 Synapse BC 측 도메인 모델 (생산자)

`services/synapse/app/services/graph_search_service.py`:

```python
from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass(frozen=True)
class SearchCandidate:
    """Fulltext/Vector 검색에서 나온 개별 후보 노드."""
    node: Dict[str, Any]     # Neo4j 노드 properties (또는 driver Node)
    score: float             # 검색 점수
    source_index: str        # "ontology_fulltext" | "schema_fulltext"

@dataclass(frozen=True)
class ContextTermMapping:
    """Synapse 측 용어 매핑 — Oracle에 넘기기 전 원본 형태."""
    term: str                # 사용자 원문: "매출"
    normalized: str          # 온톨로지 정규명: "Revenue"
    confidence: float        # 0.0 ~ 1.0
    mapped_tables: List[str] # ["revenue"]
    mapped_columns: List[str]# ["revenue.amount", "revenue.date"]
    evidence: Dict[str, Any] # {"source": "fulltext+neighbors", "best_candidate_score": 12.0}

@dataclass(frozen=True)
class OntologyContextV1:
    """Synapse가 API 응답으로 반환하는 컨텍스트 원본."""
    case_id: str
    query: str
    terms: List[ContextTermMapping]
    related_tables: List[Dict[str, Any]]
    related_columns: List[Dict[str, Any]]
    provenance: Dict[str, Any]
```

### 1.2 Oracle BC 측 도메인 모델 (소비자)

`services/oracle/app/infrastructure/acl/synapse_acl.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class MappedTarget:
    """매핑 대상 테이블/컬럼 정보."""
    table: str               # "revenue"
    columns: List[str]       # ["amount", "date", "org_id"]
    join_hint: str = ""      # "revenue.org_id = organization.id"

@dataclass(frozen=True)
class TermMapping:
    """Oracle 도메인: 비즈니스 용어 → 물리 스키마 매핑 단위."""
    term: str                # 사용자 원문 토큰: "매출"
    normalized: str          # 온톨로지 정규명: "Revenue"
    layer: str               # "measure" | "kpi" | "process" | "resource"
    confidence: float        # 0.0 ~ 1.0
    mapped_to: MappedTarget  # 물리 스키마 매핑
    evidence: str            # "MAPS_TO relation" | "fulltext score 0.85"

@dataclass(frozen=True)
class ContextProvenance:
    """컨텍스트 출처 추적 — 거버넌스/디버깅용."""
    source: str              # "synapse_ontology" | "fulltext_fallback"
    timestamp: str           # ISO8601
    case_id: str
    version: str = ""        # 온톨로지 스냅샷 버전 (O5 이후)

@dataclass(frozen=True)
class OntologyContext:
    """Oracle BC 내부 도메인 모델 — ACL이 Synapse 응답을 번역하여 생성."""
    term_mappings: List[TermMapping] = field(default_factory=list)
    related_tables: List[str] = field(default_factory=list)
    domain_hints: List[str] = field(default_factory=list)
    provenance: Optional[ContextProvenance] = None
```

### 1.3 Synapse 응답 → Oracle 변환 규칙

| Synapse (`OntologyContextV1`) | Oracle (`OntologyContext`) | 변환 |
| --- | --- | --- |
| `terms[].term` | `TermMapping.term` | 직접 |
| `terms[].normalized` | `TermMapping.normalized` | 직접 |
| `terms[].confidence` | `TermMapping.confidence` | float 캐스팅 |
| `terms[].mapped_tables` | `TermMapping.mapped_to.table` | 리스트 첫 번째 (primary) |
| `terms[].mapped_columns` | `TermMapping.mapped_to.columns` | 리스트 그대로 |
| `terms[].evidence` | `TermMapping.evidence` | dict → 문자열 요약 |
| `related_tables[].name` | `related_tables` | name만 추출 |
| `provenance` | `ContextProvenance` | 구조 변환 |

---

## §2. End-to-End Call Flow + Failure Policy

### 2.1 정상 흐름

```text
┌─────────────────────────────────────────────────────────────────┐
│ NL2SQL Pipeline (Oracle BC)                                      │
│                                                                   │
│  1. 사용자 질문 수신                                              │
│  2. _search_and_catalog()                                         │
│     ├── schema_result = ACL.search_schema_context()               │
│     └── ontology_ctx  = ACL.search_ontology_context()  ← 신규     │
│  3. _format_system_prompt(schema_result, ontology_ctx)            │
│  4. LLM SQL 생성                                                  │
│  5. Guard → Execute → Visualize → Summary                        │
└────────────────┬──────────────────────────────────────────────────┘
                 │
    ┌────────────┴────────────┐
    │ ACL.search_ontology_    │
    │ context()               │
    │                         │
    │  POST /api/v3/synapse/  │
    │  graph/ontology/context │
    └────────────┬────────────┘
                 │
    ┌────────────┴────────────┐
    │ Synapse BC              │
    │                         │
    │  GraphSearchService     │
    │  .context_v2()          │
    │                         │
    │  1. Fulltext 후보 수집   │
    │  2. 제한 BFS 확장        │
    │  3. 테이블/컬럼 추출     │
    │  4. Term mapping 구성    │
    └─────────────────────────┘
```

### 2.2 Failure Policy (장애 정책)

| 장애 시나리오 | Oracle 동작 | FE 표시 | 로그 |
| --- | --- | --- | --- |
| Synapse 타임아웃 (>6s) | `None` 반환 → degraded mode | "근거 부족" 배지 | `ontology_context_timeout=true` |
| Synapse 5xx / 503 | `None` 반환 → degraded mode | "근거 부족" 배지 | `ontology_context_error=true, status={code}` |
| case_id 없음 | 온톨로지 호출 스킵 | 표시 없음 (정상) | `ontology_context_skipped=true, reason=no_case_id` |
| 매핑 0건 반환 | 빈 `OntologyContext` | "근거 부족" 배지 | `ontology_mappings_count=0` |
| confidence < 0.6 전체 | prompt에 "확인 필요" 주석 추가 | "근거 부족" 배지 | `low_confidence_mappings=true` |

**핵심 원칙**: Synapse 장애가 NL2SQL 전체를 중단시켜서는 **절대 안 된다**.

### 2.3 Degraded Mode에서 LLM에게도 알려주는 이유

Synapse가 죽었는데 모델이 "나는 매출=revenue.amount를 안다" 같은 말을 만들어내면 오히려 위험하다. 그래서 **컨텍스트 없이 진행한다는 사실을 모델에게도 명시**해야 hallucination이 줄어든다.

```python
# degraded mode일 때 system prompt에 주입
"[Business Term → Schema Mapping]\n"
"- (synapse unavailable; proceed without ontology context)\n"
```

### 2.4 "근거 부족" 배지 (FE)

```typescript
{!hasOntologyContext && (
  <Badge variant="outline" className="text-amber-600">
    근거 부족 — 온톨로지 매핑 없이 생성됨
  </Badge>
)}
```

---

## §3. GraphSearchService v2 — Production Skeleton

> **리스크 1 완화**: 기존 `search()` 제거하지 않고 v2 메서드 병행 + Feature Flag 제어
> **파일**: `services/synapse/app/services/graph_search_service.py`

### 3.0 현재 상태 (하드코딩 — 제거 대상)

```python
# 4개 테이블만 인식 가능
self._tables = {
    "cases":         {"columns": ["id(uuid,PK)", "name(text)"]},
    "processes":     {"columns": ["id(uuid,PK)", "case_id(FK)", "efficiency_rate(numeric)"]},
    "organizations": {"columns": ["id(uuid,PK)", "name(text)"]},
    "metrics":       {"columns": ["id(uuid,PK)", "case_id(FK)", "value(numeric)"]},
}
```

### 3.1 핵심 설계 원칙 (코드에 반영)

- **Fulltext → 제한 BFS → 후보 정리** 3단계 분리
- **그래프 폭발 방지**: `_REL_ALLOWLIST`, depth cap, limit cap, row cap
- **반환은 raw graph가 아니라 컨텍스트용 힌트 세트** (Oracle에 넘길 목적)
- **Neo4j driver Node vs dict 양쪽 대응**: 방어적 접근자 패턴

### 3.2 관계 Allowlist (폭발 방지)

```python
class GraphSearchService:
    _REL_ALLOWLIST = [
        "MAPS_TO",
        "DEFINES",
        "TAGGED_AS",
        "FK_TO_TABLE",
        "DERIVED_FROM",
        "CONTRIBUTES_TO",
        "HAS_MEASURE",
        "HAS_KPI",
        "PART_OF",
    ]

    def __init__(self, neo4j: Neo4jClient):
        self.neo4j = neo4j
```

### 3.3 Fulltext 후보 수집

```python
async def _fulltext_candidates(
    self,
    index_name: str,
    q: str,
    limit: int = 20,
) -> List[SearchCandidate]:
    cypher = """
    CALL db.index.fulltext.queryNodes($index_name, $q) YIELD node, score
    RETURN node, score
    ORDER BY score DESC
    LIMIT $limit
    """
    rows = await self.neo4j.run(cypher, {
        "index_name": index_name, "q": q, "limit": limit,
    })
    out: List[SearchCandidate] = []
    for r in rows:
        node = r.get("node")
        score = float(r.get("score") or 0.0)
        if node is None:
            continue
        out.append(SearchCandidate(
            node=node, score=score, source_index=index_name,
        ))
    return out
```

### 3.4 제한 BFS 확장 (Bounded Neighbor Expansion)

> **핵심**: Neo4j 가변길이 패턴(`*..N`)은 폭발 위험이 크므로, **서비스 레이어에서 반복 수집**하는 방식이 안전하다.

```python
async def _expand_neighbors_limited(
    self,
    node_ids: Sequence[str],
    depth: int = 2,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """관계 allowlist 안에서만 제한 확장 — 테이블/컬럼 후보 추가 수집."""
    if not node_ids:
        return []

    cypher = """
    MATCH (n)
    WHERE elementId(n) IN $node_ids
    CALL {
      WITH n
      MATCH (n)-[r]->(m) WHERE type(r) IN $rels
      RETURN n as src, r as rel, m as dst
      UNION
      WITH n
      MATCH (n)<-[r]-(m) WHERE type(r) IN $rels
      RETURN n as src, r as rel, m as dst
    }
    RETURN src, rel, dst
    LIMIT $limit
    """
    rows = await self.neo4j.run(
        cypher,
        {"node_ids": list(node_ids), "rels": self._REL_ALLOWLIST, "limit": limit},
    )

    edges: List[Dict[str, Any]] = []
    for r in rows:
        src, rel, dst = r.get("src"), r.get("rel"), r.get("dst")
        if src is None or rel is None or dst is None:
            continue
        edges.append({"src": src, "rel": rel, "dst": dst})

    # depth > 1: 안전 반복 수집 (iterative deepening)
    if depth <= 1:
        return edges

    seen_ids = set(node_ids)
    frontier = {self._safe_element_id(e["dst"]) for e in edges}
    frontier.discard(None)
    for _ in range(depth - 1):
        new_frontier = [x for x in frontier if x and x not in seen_ids]
        if not new_frontier:
            break
        seen_ids.update(new_frontier)
        more = await self._expand_neighbors_limited(
            new_frontier, depth=1, limit=limit,
        )
        edges.extend(more)
        frontier = {self._safe_element_id(e["dst"]) for e in more}
        frontier.discard(None)

    return edges
```

### 3.5 Node ID 호환 레이어

> **프로젝트 환경 차이 포인트**: Neo4jClient가 dict로 변환해서 반환하는지, driver Node 객체인지에 따라 여기만 수정하면 전체가 맞춰진다.

```python
def _safe_element_id(self, node_obj: Any) -> Optional[str]:
    """Neo4j driver Node 또는 dict에서 element_id를 안전하게 추출."""
    if node_obj is None:
        return None
    if isinstance(node_obj, dict):
        return (node_obj.get("elementId")
                or node_obj.get("element_id")
                or node_obj.get("id"))
    return (getattr(node_obj, "element_id", None)
            or getattr(node_obj, "elementId", None)
            or getattr(node_obj, "id", None))

def _node_labels(self, node: Any) -> List[str]:
    if isinstance(node, dict):
        return node.get("labels", []) or node.get("label", []) or []
    return list(getattr(node, "labels", []) or [])

def _node_props(self, node: Any) -> Dict[str, Any]:
    if isinstance(node, dict):
        return node.get("properties", node)
    try:
        return dict(node)
    except Exception:
        return {}
```

### 3.6 FK Path Search (Bounded)

```python
async def fk_path_v2(
    self,
    table_names: Sequence[str],
    max_hops: int = 3,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    if not table_names:
        return []

    cypher = f"""
    MATCH p=(t1:Table)-[:FK_TO_TABLE*..{max_hops}]->(t2:Table)
    WHERE t1.name IN $tables OR t2.name IN $tables
    RETURN p
    LIMIT $limit
    """
    rows = await self.neo4j.run(
        cypher, {"tables": list(table_names), "limit": limit},
    )
    return [{"path": r.get("p")} for r in rows if r.get("p") is not None]
```

### 3.7 `context_v2()` — NL2SQL 컨텍스트 생성 (핵심 메서드)

```python
async def context_v2(
    self,
    case_id: str,
    q: str,
    k_fulltext: int = 20,
    neighbor_depth: int = 2,
    neighbor_limit: int = 250,
) -> OntologyContextV1:
    """
    O3 핵심: NL2SQL에 주입할 컨텍스트를 만든다.
    - ontology_fulltext, schema_fulltext 양쪽에서 후보 수집
    - 주변 확장으로 Table/Column 힌트를 보강
    - term mapping은 "가장 강한 후보" 기준으로 정리
    - O2 MAPS_TO가 생기면 자동으로 정확도 상승
    """
    # 1) fulltext 후보
    ont = await self._fulltext_candidates(
        "ontology_fulltext", q, limit=k_fulltext,
    )
    sch = await self._fulltext_candidates(
        "schema_fulltext", q, limit=k_fulltext,
    )

    # 2) 후보 node id 수집
    candidate_nodes = ont + sch
    candidate_ids: List[str] = []
    for c in candidate_nodes:
        eid = self._safe_element_id(c.node)
        if eid:
            candidate_ids.append(eid)

    # 3) 주변 확장 (제한 BFS)
    edges = await self._expand_neighbors_limited(
        candidate_ids, depth=neighbor_depth, limit=neighbor_limit,
    )

    # 4) 관련 테이블/컬럼 추출
    related_tables = self._extract_tables(candidate_nodes, edges)
    related_columns = self._extract_columns(candidate_nodes, edges)

    # 5) term mapping 구성
    terms = self._build_term_mappings(
        q=q, candidates=candidate_nodes, edges=edges,
    )

    provenance = {
        "case_id": case_id,
        "query": q,
        "indexes": ["ontology_fulltext", "schema_fulltext"],
        "neighbor_depth": neighbor_depth,
        "neighbor_limit": neighbor_limit,
        "rel_allowlist": self._REL_ALLOWLIST,
    }

    return OntologyContextV1(
        case_id=case_id,
        query=q,
        terms=terms,
        related_tables=related_tables,
        related_columns=related_columns,
        provenance=provenance,
    )
```

### 3.8 Helper: 테이블/컬럼 추출

```python
def _extract_tables(
    self,
    candidates: Sequence[SearchCandidate],
    edges: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    tables: Dict[str, Dict[str, Any]] = {}

    def add(node: Any, score: float, via: str) -> None:
        labels = self._node_labels(node)
        props = self._node_props(node)
        if "Table" in labels or props.get("kind") == "table":
            name = props.get("name") or props.get("table") or props.get("id")
            if not name:
                return
            cur = tables.get(name)
            if cur is None or score > float(cur.get("score", 0.0)):
                tables[name] = {
                    "name": name, "score": score,
                    "via": via, "props": props,
                }

    for c in candidates:
        add(c.node, c.score, f"fulltext:{c.source_index}")
    for e in edges:
        dst = e.get("dst")
        if dst:
            add(dst, 0.5, f"neighbor:{self._node_labels(dst)}")

    return sorted(
        tables.values(),
        key=lambda x: float(x.get("score", 0.0)),
        reverse=True,
    )[:30]

def _extract_columns(
    self,
    candidates: Sequence[SearchCandidate],
    edges: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cols: Dict[str, Dict[str, Any]] = {}

    def add(node: Any, score: float, via: str) -> None:
        labels = self._node_labels(node)
        props = self._node_props(node)
        if "Column" in labels or props.get("kind") == "column":
            table = props.get("table") or props.get("table_name")
            name = props.get("name") or props.get("column") or props.get("id")
            if not name:
                return
            key = f"{table}.{name}" if table else name
            cur = cols.get(key)
            if cur is None or score > float(cur.get("score", 0.0)):
                cols[key] = {
                    "key": key, "table": table, "name": name,
                    "score": score, "via": via, "props": props,
                }

    for c in candidates:
        add(c.node, c.score, f"fulltext:{c.source_index}")
    for e in edges:
        dst = e.get("dst")
        if dst:
            add(dst, 0.5, "neighbor")

    return sorted(
        cols.values(),
        key=lambda x: float(x.get("score", 0.0)),
        reverse=True,
    )[:50]
```

### 3.9 Helper: Term Mapping 구성

```python
def _build_term_mappings(
    self,
    q: str,
    candidates: Sequence[SearchCandidate],
    edges: Sequence[Dict[str, Any]],
) -> List[ContextTermMapping]:
    """
    최소 버전:
    - q 자체를 1개 term으로 취급 (추후 토크나이저/키워드 추출 도입 가능)
    - GlossaryTerm/KPI/Measure 후보에 가중치 부여
    - MAPS_TO/DEFINES 관계가 있으면 mapped_tables/columns 강화
    """
    term = q.strip()
    if not term:
        return []

    # 가장 높은 점수 후보 (GlossaryTerm 우선)
    best = None
    best_score = 0.0
    best_kind = None

    for c in candidates:
        labels = self._node_labels(c.node)
        props = self._node_props(c.node)
        kind = props.get("kind")

        # 온톨로지 노드 가중치
        if "GlossaryTerm" in labels or kind == "glossary":
            weight = 1.2
        elif "KPI" in labels or kind == "kpi":
            weight = 1.0
        elif "Measure" in labels or kind == "measure":
            weight = 1.0
        else:
            weight = 0.7

        score = c.score * weight
        if score > best_score:
            best_score = score
            best = c
            best_kind = kind or (labels[0] if labels else None)

    # confidence scaling (환경에 맞게 조정)
    confidence = min(0.95, max(0.2, best_score / 10.0))

    # edges에서 MAPS_TO/DEFINES 관계의 Table/Column 수집
    mapped_tables: List[str] = []
    mapped_cols: List[str] = []

    for e in edges:
        rel = e.get("rel")
        rel_type = None
        if isinstance(rel, dict):
            rel_type = rel.get("type")
        else:
            rel_type = getattr(rel, "type", None)

        if rel_type not in ("MAPS_TO", "DEFINES"):
            continue

        dst = e.get("dst")
        if dst is None:
            continue
        labels = self._node_labels(dst)
        props = self._node_props(dst)

        if "Table" in labels:
            name = props.get("name")
            if name:
                mapped_tables.append(name)
        if "Column" in labels:
            t = props.get("table") or props.get("table_name")
            c = props.get("name")
            if c:
                mapped_cols.append(f"{t}.{c}" if t else c)

    evidence = {
        "source": "fulltext+neighbors",
        "best_candidate_kind": best_kind,
        "best_candidate_score": best_score,
    }

    normalized = (
        self._node_props(best.node).get("name") if best else None
    ) or term

    return [
        ContextTermMapping(
            term=term,
            normalized=str(normalized),
            confidence=float(confidence),
            mapped_tables=sorted(set(mapped_tables))[:10],
            mapped_columns=sorted(set(mapped_cols))[:20],
            evidence=evidence,
        )
    ]
```

### 3.10 Mapping Source 2-Stage 설계 (O2↔O3 의존성)

| Stage | O2 상태 | 매핑 소스 | confidence 범위 | evidence |
| --- | --- | --- | --- | --- |
| **Stage 1** (O3 단독) | O2 미완성, `MAPS_TO` 없음 | Fulltext only | 0.2 ~ 0.7 | `"fulltext score X.XX"` |
| **Stage 2** (O2 + O3) | O2 완성, `MAPS_TO` 존재 | Fulltext + BFS bridge | 0.5 ~ 0.95 | `"MAPS_TO relation (verified)"` |

**Stage 전환은 자동**: `MAPS_TO` 관계가 생기면 `_expand_neighbors_limited()`가 MAPS_TO를 따라가므로 Query B 결과가 0건 → N건으로 변화한다.

### 3.11 프로젝트 환경 차이 확인 포인트

> 아래 항목은 코딩 착수 전 **반드시** 확인해야 한다.

1. **`Neo4jClient.run()` 반환 형태**: dict로 변환된 것인지, driver `Node`/`Relationship` 객체인지
   - 위 코드는 둘 다 방어적으로 대응하나, 프로젝트 표준을 하나로 정하는 것을 권장
2. **Node ID 기준**: `elementId(n)` vs `id(n)`
   - 운영에서 `elementId`를 쓰면 안정적 (내부 id 재사용 문제 회피)
   - FE/BE 타입 계약에서 `source_id`가 elementId인지 통일 필요
3. **Fulltext index 이름**: `ontology_fulltext`, `schema_fulltext`가 `neo4j_bootstrap.py`에 정의된 이름과 일치하는지

---

## §4. Synapse API Endpoint

> **파일**: `services/synapse/app/api/graph.py`

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.services.graph_search_service import GraphSearchService

router = APIRouter(prefix="/api/v3/synapse/graph", tags=["graph"])


class ContextRequest(BaseModel):
    case_id: str
    query: str


@router.post("/ontology/context")
async def ontology_context(
    req: ContextRequest,
    request: Request,
    svc: GraphSearchService = Depends(),
):
    """NL2SQL에서 사용할 온톨로지 컨텍스트 조회.

    내부적으로 Fulltext → 제한 BFS → 후보 정리 3단계를 실행하여
    비즈니스 용어 매핑 + 관련 테이블 + 도메인 힌트를 반환한다.
    """
    try:
        ctx = await svc.context_v2(case_id=req.case_id, q=req.query)
        return {
            "case_id": ctx.case_id,
            "query": ctx.query,
            "terms": [
                {
                    "term": t.term,
                    "normalized": t.normalized,
                    "confidence": t.confidence,
                    "mapped_tables": t.mapped_tables,
                    "mapped_columns": t.mapped_columns,
                    "evidence": t.evidence,
                }
                for t in ctx.terms
            ],
            "related_tables": ctx.related_tables,
            "related_columns": ctx.related_columns,
            "provenance": ctx.provenance,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## §5. OracleSynapseACL — Production Code

> **파일**: `services/oracle/app/infrastructure/acl/synapse_acl.py`

### 5.1 ACL 확장 원칙

1. **Synapse BC의 응답을 Oracle BC 도메인 모델로 번역**
2. **Synapse 장애 = `None` 반환 (degraded mode)** — NL2SQL 중단 금지
3. **기존 `search_schema_context()` 패턴 준수**: `_request_with_retry()` 방식
4. **나중에 정책을 바꿔 "Synapse 없으면 중단"으로 가고 싶다면 여기서 예외를 던지도록만 바꾸면 됨** (호출부 변경 불필요)

### 5.2 `search_ontology_context()` 구현

```python
class OracleSynapseACL:
    def __init__(self, base_url: str, timeout_s: float = 6.0):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    async def search_ontology_context(
        self,
        case_id: str,
        query: str,
    ) -> Optional[OntologyContext]:
        """
        O3 핵심.
        - Synapse 503/timeout → None 반환 (degraded mode)
        - raw json → Oracle 도메인 모델로 변환
        """
        url = f"{self.base_url}/api/v3/synapse/graph/ontology/context"
        payload = {"case_id": case_id, "query": query}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(url, json=payload)
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(
                "ontology_context_failed",
                error=str(e), case_id=case_id, query=query[:100],
            )
            return None  # degraded mode

        if resp.status_code == 503:
            return None
        if resp.status_code >= 400:
            # 4xx/5xx: NL2SQL은 크래시 금지이므로 degraded
            logger.warning(
                "ontology_context_http_error",
                status=resp.status_code, case_id=case_id,
            )
            return None

        data = resp.json() if resp.content else {}
        return self._translate_ontology_context(data, case_id)

    def _translate_ontology_context(
        self,
        data: dict,
        case_id: str,
    ) -> OntologyContext:
        """Synapse 원본 응답 → Oracle 도메인 모델 변환."""
        term_mappings = []
        for t in (data.get("terms") or []):
            mapped_cols = list(t.get("mapped_columns") or [])
            mapped_tbls = list(t.get("mapped_tables") or [])

            term_mappings.append(TermMapping(
                term=str(t.get("term") or ""),
                normalized=str(t.get("normalized") or ""),
                layer=str(t.get("layer") or ""),
                confidence=float(t.get("confidence") or 0.0),
                mapped_to=MappedTarget(
                    table=mapped_tbls[0] if mapped_tbls else "",
                    columns=mapped_cols,
                    join_hint=str(t.get("join_hint") or ""),
                ),
                evidence=str(t.get("evidence") or "unknown"),
            ))

        provenance = ContextProvenance(
            source="synapse_ontology",
            timestamp=str(data.get("timestamp") or ""),
            case_id=case_id,
        )

        related_tables = [
            rt.get("name") or rt
            for rt in (data.get("related_tables") or [])
            if rt
        ]

        return OntologyContext(
            term_mappings=term_mappings,
            related_tables=related_tables,
            domain_hints=list(data.get("domain_hints") or []),
            provenance=provenance,
        )
```

---

## §6. NL2SQL Pipeline Prompt 주입 — Production Code

> **파일**: `services/oracle/app/pipelines/nl2sql_pipeline.py`

### 6.1 `_search_and_catalog()` 패치

```python
async def _search_and_catalog(self, *, case_id: str, question: str,
                               system_prompt: str, **kwargs) -> str:
    """기존: schema catalog만. 변경: ontology context 끼워 넣어 prompt 강화."""
    # 1) Synapse에서 context 조회 (degraded 가능)
    ctx: Optional[OntologyContext] = None
    if case_id:
        ctx = await self.synapse_acl.search_ontology_context(
            case_id=case_id, query=question,
        )

    # 2) system prompt에 매핑 섹션 주입
    if ctx is not None and ctx.term_mappings:
        system_prompt += "\n\n" + _format_ontology_context_for_prompt(ctx)
    else:
        # degraded mode: 모델에게도 컨텍스트 부재를 명시
        system_prompt += (
            "\n\n[Business Term → Schema Mapping]\n"
            "- (synapse unavailable; proceed without ontology context)\n"
        )

    # 3) 기존 catalog/search 로직 계속...
    return system_prompt
```

### 6.2 `_format_ontology_context_for_prompt()` — Confidence 기반 행동 규칙

```python
def _format_ontology_context_for_prompt(ctx: OntologyContext) -> str:
    """OntologyContext → System Prompt 주입 텍스트.

    Confidence 기반 3단계:
    - >= 0.8: 확신 매핑 → "이 매핑을 사용하여 SQL 생성"
    - 0.6 ~ 0.8: 참고 매핑 → "DDL도 확인"
    - < 0.6: 저신뢰 → "DDL 기반으로 생성"
    """
    lines = ["[Business Term → Schema Mapping]"]

    if not ctx.term_mappings:
        lines.append("- (no mappings found)")
        return "\n".join(lines)

    high = [t for t in ctx.term_mappings if t.confidence >= 0.8]
    mid = [t for t in ctx.term_mappings if 0.6 <= t.confidence < 0.8]
    low = [t for t in ctx.term_mappings if t.confidence < 0.6]

    if high:
        lines.append("")
        lines.append("### Confirmed Mappings (use these for SQL generation)")
        for t in high:
            cols = ", ".join(t.mapped_to.columns) if t.mapped_to.columns else "?"
            lines.append(
                f'- "{t.term}" → {t.mapped_to.table}.{{{cols}}} '
                f'({t.layer}, confidence={t.confidence:.2f})'
            )
            if t.mapped_to.join_hint:
                lines.append(f'  JOIN hint: {t.mapped_to.join_hint}')

    if mid:
        lines.append("")
        lines.append("### Reference Mappings (verify against DDL)")
        for t in mid:
            cols = ", ".join(t.mapped_to.columns) if t.mapped_to.columns else "?"
            lines.append(
                f'- "{t.term}" → {t.mapped_to.table}.{{{cols}}} '
                f'({t.layer}, confidence={t.confidence:.2f})'
            )

    if low:
        lines.append("")
        lines.append("### Low Confidence (generate SQL from DDL, not these)")
        for t in low:
            cols = ", ".join(t.mapped_to.columns) if t.mapped_to.columns else "?"
            lines.append(
                f'- "{t.term}" → {t.mapped_to.table}.{{{cols}}} '
                f'({t.layer}, confidence={t.confidence:.2f}, '
                f'evidence="{t.evidence}")'
            )

    lines.append("")
    lines.append("Rules:")
    lines.append("1) Prefer mapped tables/columns above when generating SQL.")
    lines.append("2) If a mapped term appears in the question, "
                 "include at least one mapped column unless clearly irrelevant.")
    lines.append("3) If mapping confidence < 0.60, ask a clarification question "
                 "OR generate SQL with explicit assumptions.")
    lines.append("4) If a JOIN hint is provided, use that JOIN condition.")

    if ctx.related_tables:
        lines.append(f"\nRelated tables: {', '.join(ctx.related_tables)}")

    return "\n".join(lines)
```

### 6.3 System Prompt 최종 구성 예시

```text
You are an expert SQL generator for PostgreSQL.

## Database Schema (DDL)
CREATE TABLE revenue (
    id UUID PRIMARY KEY, amount NUMERIC NOT NULL,
    date DATE NOT NULL, org_id UUID REFERENCES organization(id)
);
...

[Business Term → Schema Mapping]

### Confirmed Mappings (use these for SQL generation)
- "매출" → revenue.{amount, date} (measure, confidence=0.92)
  JOIN hint: revenue.org_id = organization.id

### Reference Mappings (verify against DDL)
- "조직별" → organization.{name, id} (resource, confidence=0.72)

Rules:
1) Prefer mapped tables/columns above when generating SQL.
2) If a mapped term appears in the question, include at least one mapped column.
3) If mapping confidence < 0.60, ask a clarification question OR generate SQL with explicit assumptions.
4) If a JOIN hint is provided, use that JOIN condition.

Related tables: revenue, organization

## Value Mappings
- processes.process_type: "도산" = "insolvency", ...

Generate a single PostgreSQL query for: "조직별 매출 추이 보여줘"
```

---

## §7. Meta API 폴백 전략 변경

> **파일**: `services/oracle/app/api/meta.py`

### 7.1 현재 상태 (제거 대상)

```python
# meta.py:28-44 — 하드코딩 폴백
def _fallback_tables():
    return [
        {"name": "processes", "description": "프로세스 실행 내역", ...},
        {"name": "organizations", "description": "이해관계자 정보", ...},
    ]
```

### 7.2 변경

```python
async def list_tables(
    datasource_id: str = Query(...),
    search: str = Query(""),
    request: Request = None,
):
    tenant_id = extract_tenant_id(request)
    try:
        tables = await oracle_synapse_acl.list_tables(
            tenant_id=tenant_id, datasource_id=datasource_id, search=search,
        )
    except httpx.TimeoutException:
        logger.error("meta_api_tables_timeout", datasource_id=datasource_id)
        raise HTTPException(status_code=503, detail={
            "code": "SYNAPSE_TIMEOUT",
            "message": "메타데이터 서비스 응답 시간 초과",
            "retry_after_seconds": 5,
        })
    except Exception as exc:
        logger.error("meta_api_tables_failed", error=str(exc))
        raise HTTPException(status_code=503, detail={
            "code": "SYNAPSE_UNAVAILABLE",
            "message": "메타데이터 서비스에 연결할 수 없습니다",
            "retry_after_seconds": 10,
        })
    return {"success": True, "data": {"tables": tables}}
```

### 7.3 운영 안전성 체크리스트

- [ ] `_fallback_tables()` 호출부 모두 제거 (`grep -r "_fallback_tables" services/oracle/` = 0건)
- [ ] FE에서 503 응답 시 "재시도" 버튼 표시 (NL2SQL Phase 3 P3-4와 연동)
- [ ] `retry_after_seconds` 값을 FE에서 활용

---

## §8. ReactAgent 온톨로지 우선 후보 — Production Code

> **파일**: `services/oracle/app/pipelines/react_agent.py`

```python
def _extract_preferred_tables(
    ctx: Optional[OntologyContext],
) -> List[str]:
    """OntologyContext에서 우선 테이블 추출."""
    if ctx is None:
        return []
    out = []
    for t in ctx.term_mappings:
        if t.mapped_to.table:
            out.append(t.mapped_to.table)
        # mapped_to.columns에서 table 부분 파싱
        for c in t.mapped_to.columns:
            if "." in c:
                out.append(c.split(".", 1)[0])
    # related_tables도 포함
    out.extend(ctx.related_tables)
    # unique preserve order
    seen = set()
    uniq = []
    for x in out:
        if x and x not in seen:
            uniq.append(x)
            seen.add(x)
    return uniq


class ReactAgent:
    async def _select_tables(
        self,
        question: str,
        schema_tables: List[str],
        ctx: Optional[OntologyContext] = None,
    ) -> List[str]:
        """온톨로지 테이블을 우선 후보로 prepend."""
        preferred = _extract_preferred_tables(ctx)
        result = preferred + [
            t for t in schema_tables if t not in set(preferred)
        ]
        return result[:20]
```

---

## §9. Phase O3 수정 파일 요약

| 파일 | 변경 | 위험도 |
| --- | --- | --- |
| `services/synapse/app/services/graph_search_service.py` | `context_v2()` + fulltext + BFS + FK + helpers (기존 유지) | MEDIUM |
| `services/synapse/app/api/graph.py` | `POST /ontology/context` 엔드포인트 추가 | LOW |
| `services/oracle/app/infrastructure/acl/synapse_acl.py` | `TermMapping` + `OntologyContext` + `search_ontology_context()` | MEDIUM |
| `services/oracle/app/pipelines/nl2sql_pipeline.py` | `_search_and_catalog()` 확장 + `_format_ontology_context_for_prompt()` | MEDIUM |
| `services/oracle/app/pipelines/react_agent.py` | `_select_tables()` 온톨로지 우선 후보 | LOW |
| `services/oracle/app/api/meta.py` | `_fallback_tables()` 제거 + 503 핸들링 | LOW |

---

## §10. 구현 순서 (5-Step, Feature Flag 기반)

### Step 1: Feature Flag + 데이터 계약 정의

- `services/synapse/app/core/config.py`에 `FEATURE_SEARCH_V2 = bool(os.getenv("FEATURE_SEARCH_V2", "false"))` 추가
- Synapse 측: `SearchCandidate`, `ContextTermMapping`, `OntologyContextV1` 정의
- Oracle 측: `TermMapping`, `MappedTarget`, `OntologyContext`, `ContextProvenance` 정의
- **검증**: dataclass 생성/직렬화 단위 테스트

### Step 2: Synapse — GraphSearchService v2 + API

- `graph_search_service.py`에 `context_v2()` + 3대 쿼리 + helpers 구현
- `graph.py`에 `POST /ontology/context` 엔드포인트 추가
- **검증**: FakeNeo4j 기반 단위 테스트 + API contract 테스트

### Step 3: Oracle — ACL 확장

- `synapse_acl.py`에 `search_ontology_context()` + `_translate_ontology_context()` 구현
- 타임아웃 6초, failure → `None` (degraded mode)
- **검증**: ACL 단위 테스트 (mock Synapse 응답)

### Step 4: Oracle — Pipeline + ReactAgent 통합

- `nl2sql_pipeline.py`의 `_search_and_catalog()` 확장
- `_format_ontology_context_for_prompt()` confidence 기반 포맷터
- `react_agent.py`의 `_select_tables()` 온톨로지 우선 후보
- **검증**: Pipeline 통합 테스트

### Step 5: meta.py 폴백 제거 + Feature Flag 전환

- `_fallback_tables()` 완전 제거
- `FEATURE_SEARCH_V2 = true` 기본값 전환
- **검증**: Gate O3 전체 통과

### Feature Flag 전환 전략

```python
# graph_search_service.py
async def search(self, payload: dict) -> dict:
    if settings.FEATURE_SEARCH_V2:
        v2_result = await self.search_v2(payload)
        if settings.SEARCH_V2_AB_LOGGING:
            v1_result = await self._search_legacy(payload)
            logger.info("search_ab_compare",
                v1_tables=len(v1_result.get("data", {}).get("tables", {}).get("vector_matched", [])),
                v2_tables=len(v2_result.get("data", {}).get("tables", {}).get("vector_matched", [])),
            )
        return v2_result
    return await self._search_legacy(payload)
```

### PR 분할 전략 (리뷰 효율)

| PR | 범위 | 의존 |
| --- | --- | --- |
| **PR-1** (Synapse) | GraphSearchService v2 + context endpoint + 테스트 | 없음 |
| **PR-2** (Oracle) | `synapse_acl.search_ontology_context` + prompt 주입 + 테스트 | PR-1 머지 후 |
| **PR-3** (Oracle) | `react_agent` 테이블 우선순위 + `meta.py` 폴백 제거 | PR-2 머지 후 |

---

## §11. Gate O3 — PR 수준 체크리스트 + 테스트 코드

### 11.1 Unit Tests

#### 테스트 1: Synapse — Neo4j 호출 검증 (하드코딩 아님)

```python
# services/synapse/tests/test_graph_search_service_v2.py
import pytest
from app.services.graph_search_service import GraphSearchService

class FakeNeo4j:
    def __init__(self):
        self.calls = []

    async def run(self, cypher, params):
        self.calls.append((cypher, params))
        if "db.index.fulltext.queryNodes" in cypher:
            return [{
                "node": {
                    "labels": ["GlossaryTerm"],
                    "name": "매출",
                    "elementId": "n1",
                },
                "score": 12.0,
            }]
        return []

@pytest.mark.asyncio
async def test_context_v2_calls_fulltext():
    neo = FakeNeo4j()
    svc = GraphSearchService(neo)
    ctx = await svc.context_v2(case_id="c1", q="매출 추이")
    assert ctx.case_id == "c1"
    # fulltext가 호출되었는지 확인
    assert any("db.index.fulltext.queryNodes" in c[0] for c in neo.calls)
```

#### 테스트 2: Oracle — Prompt 주입 검증

```python
# services/oracle/tests/test_prompt_injection.py
import pytest
from app.pipelines.nl2sql_pipeline import _format_ontology_context_for_prompt
from app.infrastructure.acl.synapse_acl import (
    OntologyContext, TermMapping, MappedTarget,
)

def test_prompt_contains_mapping_section():
    ctx = OntologyContext(
        term_mappings=[TermMapping(
            term="매출",
            normalized="Revenue",
            layer="measure",
            confidence=0.92,
            mapped_to=MappedTarget(
                table="revenue",
                columns=["amount", "date"],
            ),
            evidence="MAPS_TO relation",
        )],
        related_tables=["revenue"],
    )
    s = _format_ontology_context_for_prompt(ctx)
    assert "[Business Term → Schema Mapping]" in s
    assert "revenue" in s
    assert "amount" in s
    assert "confidence=0.92" in s

def test_prompt_degraded_mode():
    """빈 OntologyContext일 때 no mappings found 메시지."""
    ctx = OntologyContext()
    s = _format_ontology_context_for_prompt(ctx)
    assert "no mappings found" in s
```

#### 테스트 3: 하드코딩 제거 확인 (가장 중요)

```python
# services/synapse/tests/test_no_hardcoding.py
def test_no_hardcoded_tables_edges():
    """O3 완료 후 _tables, _fk_edges 인스턴스 변수가 없어야 한다."""
    from app.services.graph_search_service import GraphSearchService
    assert not hasattr(GraphSearchService, "_tables"), \
        "_tables 하드코딩이 아직 남아있음"
    assert not hasattr(GraphSearchService, "_fk_edges"), \
        "_fk_edges 하드코딩이 아직 남아있음"
```

### 11.2 Contract Tests

- [ ] `POST /api/v3/synapse/graph/ontology/context` → 200 응답 스키마 검증
- [ ] 응답에 `terms[].confidence`, `terms[].evidence`, `terms[].mapped_columns` 필드 존재
- [ ] `related_tables` 필드 타입: `list[dict]` (각 dict에 `name` 키)
- [ ] 빈 query → 200 + 빈 terms 배열 (에러가 아님)

### 11.3 Integration Tests

- [ ] `context_v2()`가 Neo4j Cypher 실행 확인 (하드코딩 아님)
- [ ] Feature Flag `FEATURE_SEARCH_V2=true/false` 전환 동작 확인
- [ ] A/B 비교 로그에 `v1_tables`, `v2_tables` 필드 존재
- [ ] Synapse 타임아웃 시 `None` 반환 + `ontology_context_failed` 로그
- [ ] Synapse 503 시 `None` 반환 + 에러 로그
- [ ] `_fallback_tables()` 코드에서 완전 제거됨

### 11.4 Scenario Tests (E2E)

- [ ] "매출 추이" → revenue 테이블 SELECT 생성 (confidence >= 0.7)
- [ ] "고객 이탈률" → customer 테이블 + status 필터 (confidence >= 0.7)
- [ ] "조직별 매출" → revenue + organization JOIN (join_hint 활용)
- [ ] Synapse 장애 시 NL2SQL 정상 동작 (degraded mode + "근거 부족" 배지)
- [ ] case_id 없이 호출 시 온톨로지 스킵, 스키마만으로 정상 동작
- [ ] `FEATURE_SEARCH_V2=false` 시 기존 `search()` 로직 동작 (regression 없음)

### 11.5 Performance Gate

- [ ] v2 응답 시간 p95 < v1 p95 x 1.5
- [ ] 온톨로지 컨텍스트 호출 p95 < 6000ms (타임아웃 이내)
- [ ] System prompt 전체 길이: ontology context 포함 시 +2000 tokens 이내

---

## 부록 A: 인지 흐름 전/후 비교

### 변경 전 (Layer 0)

```text
사용자: "매출 추이 보여줘"
  ↓
GraphSearchService.search()
  → self._tables에서 "매출" 토큰 매칭
  → "cases", "processes" 등 하드코딩 4개 테이블만 반환
  ↓
NL2SQL Pipeline
  → 잘못된 테이블에서 SQL 생성 시도
  → hallucination 또는 에러
```

### 변경 후 (Layer 2) — Stage 1 (O3 단독, O2 미완)

```text
사용자: "매출 추이 보여줘"
  ↓
GraphSearchService.context_v2()
  → _fulltext_candidates("ontology_fulltext", "매출 추이")
    → GlossaryTerm "매출" (score 12.0)
  → _fulltext_candidates("schema_fulltext", "매출 추이")
    → Table "revenue" (score 8.5)
  → _expand_neighbors_limited(depth=2)
    → Column "revenue.amount" (via neighbor)
  → _build_term_mappings()
    → MAPS_TO 없음 → fulltext only (confidence 0.65)
  ↓
OntologyContext (Stage 1)
  → TermMapping: "매출" → revenue.{amount, date}
    (confidence=0.65, evidence="fulltext score 12.0")
  ↓
NL2SQL Pipeline (Reference Mapping 수준)
  → "매출" = revenue.amount 참고 매핑 (DDL 확인)
  → SELECT date, SUM(amount) FROM revenue GROUP BY date
  → ✅ 개선된 SQL (하드코딩 대비 월등)
```

### 변경 후 (Layer 2) — Stage 2 (O2 + O3 완성)

```text
사용자: "매출 추이 보여줘"
  ↓
GraphSearchService.context_v2()
  → _fulltext_candidates → GlossaryTerm "매출" (score 12.0)
  → _expand_neighbors_limited(depth=2)
    → MAPS_TO: Revenue:Measure → Table:revenue ← O2에서 생성된 관계!
    → Column "revenue.amount", "revenue.date"
  → _build_term_mappings()
    → MAPS_TO 존재 → confidence 상승 (0.92)
  ↓
OntologyContext (Stage 2)
  → TermMapping: "매출" → revenue.{amount, date}
    (confidence=0.92, evidence="MAPS_TO relation (verified)")
  → join_hint: "revenue.org_id = organization.id"
  ↓
NL2SQL Pipeline (Confirmed Mapping 수준)
  → "매출" = revenue.amount 확신 매핑 사용
  → SELECT date, SUM(amount) FROM revenue GROUP BY date ORDER BY date
  → ✅ 고신뢰 SQL
```

---

## 부록 B: O2↔O3 의존성 매트릭스

| O3 컴포넌트 | O2 필요 여부 | O2 없을 때 동작 | O2 있을 때 개선 |
| --- | --- | --- | --- |
| `_fulltext_candidates()` | 불필요 | fulltext 인덱스로 동작 | 변화 없음 |
| `_expand_neighbors_limited()` | **부분 필요** | MAPS_TO 결과 0건 → 다른 관계만 확장 | MAPS_TO로 Table bridge 작동 |
| `fk_path_v2()` | 불필요 | FK_TO_TABLE로 동작 | 변화 없음 |
| `_build_term_mappings()` | 불필요 | fulltext 기반 저신뢰 매핑 | MAPS_TO 기반 고신뢰 매핑 |
| `TermMapping.confidence` | 불필요 | 0.2~0.7 범위 | 0.5~0.95 범위 |
| `TermMapping.evidence` | 불필요 | `"fulltext score X.XX"` | `"MAPS_TO relation (verified)"` |

---

## 부록 C: 프로젝트 환경 통일 필요 사항

| 항목 | 확인 사항 | 권장 |
| --- | --- | --- |
| `Neo4jClient.run()` 반환 형태 | dict vs driver Node 객체 | dict 통일 (이미 변환하고 있다면 유지) |
| Node ID | `elementId(n)` vs `id(n)` | `elementId` 사용 (내부 id 재사용 회피) |
| Fulltext index 이름 | `neo4j_bootstrap.py`와 일치 여부 | `ontology_fulltext`, `schema_fulltext` 확인 |
| `_REL_ALLOWLIST` | 프로젝트에서 사용하는 관계 타입 전수 | bootstrap 기반으로 allowlist 갱신 |
| httpx 타임아웃 | ACL에서 6초 hard cap | 운영 환경에 맞게 조정 가능 |
