"""
멀티테넌트 프로세스 그래프 — Neo4j 관계 타입 화이트리스트.

Phase 0 (플랫폼 하드닝): Cypher 동적 관계 타입 주입 방지.
Redis Streams로 전달된 relation_type을 Neo4j MERGE 전에 반드시 이 화이트리스트로 검증한다.
"""
from __future__ import annotations

# ── 프로세스 그래프 관계 타입 (v4.1 확정) ──────────────────
PROCESS_GRAPH_RELATION_TYPES: frozenset[str] = frozenset({
    "TRIGGERS",
    "BLOCKS",
    "DEPENDS_ON",
    "HANDOFF_TO",
    "CONSUMES",
    "PRODUCES",
    "GOVERNED_BY",
    "MEASURED_BY",
    "INFLUENCES_KPI",
    "MAPPED_TO",
})

# ── 기존 온톨로지 관계 타입 (Synapse 5계층) ────────────────
ONTOLOGY_RELATION_TYPES: frozenset[str] = frozenset({
    "DERIVED_FROM",
    "OBSERVED_IN",
    "PRECEDES",
    "SUPPORTS",
    "USES",
    "CAUSES",
    "INFLUENCES",
    "RELATED_TO",
})

# ── step 전이 관계 타입 ────────────────────────────────────
STEP_TRANSITION_TYPES: frozenset[str] = frozenset({
    "NEXT",
    "YES",
    "NO",
    "ERROR",
    "TIMEOUT",
    "ESCALATE",
})

# ── 구조 관계 타입 ─────────────────────────────────────────
STRUCTURAL_RELATION_TYPES: frozenset[str] = frozenset({
    "CONTAINS",
    "BELONGS_TO",
    "HAS_VERSION",
    "HAS_STEP",
    "CURRENT_STATE",
    "SNAPSHOTTED_AS",
})

# 전체 허용 목록
ALLOWED_RELATION_TYPES: frozenset[str] = (
    PROCESS_GRAPH_RELATION_TYPES
    | ONTOLOGY_RELATION_TYPES
    | STEP_TRANSITION_TYPES
    | STRUCTURAL_RELATION_TYPES
)


def validate_relation_type(rel_type: str) -> str:
    """Cypher 동적 관계 타입 주입 방지 — 화이트리스트 통과만 허용.

    통과하면 원본 문자열을 반환하고, 실패하면 ValueError를 발생시킨다.
    """
    if rel_type not in ALLOWED_RELATION_TYPES:
        raise ValueError(
            f"허용되지 않는 관계 타입: '{rel_type}'. "
            f"허용 목록: {sorted(ALLOWED_RELATION_TYPES)}"
        )
    return rel_type


def is_process_graph_relation(rel_type: str) -> bool:
    """프로세스 그래프 전용 관계 타입인지 판별한다."""
    return rel_type in PROCESS_GRAPH_RELATION_TYPES
