"""
영향 전파기 — PostgreSQL relation/transition 엣지 기반 downstream 재계산.

Phase 5 초기 버전: Neo4j 불필요, PostgreSQL의 process_relation_edges +
step_transition_edges를 사용하여 영향 전파를 계산한다.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID


def propagate_impact(
    source_metrics: dict[str, float],
    relation_edges: list[dict[str, Any]],
    coefficients: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """소스 프로세스의 메트릭 변화를 downstream 관계를 따라 전파한다.

    relation_edges: [{target_entity_id, relation_type, weight, ...}]
    반환: [{target_entity_id, propagated_metrics, relation_type}]
    """
    propagated: list[dict[str, Any]] = []

    for edge in relation_edges:
        target_id = edge.get("target_entity_id")
        relation_type = edge.get("relation_type", "TRIGGERS")
        weight = float(edge.get("weight") or 1.0)

        # 관계 가중치로 메트릭 영향 감쇄
        target_delta: dict[str, float] = {}
        for metric, value in source_metrics.items():
            target_delta[metric] = value * weight

        propagated.append({
            "target_entity_id": str(target_id),
            "relation_type": relation_type,
            "weight": weight,
            "propagated_metrics": target_delta,
        })

    return propagated
