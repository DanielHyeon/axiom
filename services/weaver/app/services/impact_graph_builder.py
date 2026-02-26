"""Impact graph builder — produce graph JSON from scored candidates.

Graph structure:
  - KPI node (root, always 1)
  - DRIVER → KPI edges (score + cooccur)
  - DRIVER ↔ DRIVER edges (join table co-usage)
  - DRIVER → DIMENSION edges (co-usage proxy)
  - Top paths: KPI → A → B (depth <= 3)

Pure Python — no DB dependency.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List

from app.services.query_log_analyzer import AnalysisResult
from app.services.driver_scorer import ScoredCandidate
from app.services.node_id import kpi_node_id, column_node_id_from_key, parse_node_id


@dataclass
class GraphLimits:
    max_nodes: int = 120
    max_edges: int = 300
    depth: int = 3
    top_paths: int = 3


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _edge_weight(score: float, cooccur: int = 0) -> float:
    return _clamp(0.75 * score + 0.25 * (1.0 - math.exp(-cooccur / 5.0)))


def build_impact_graph(
    analysis: AnalysisResult,
    kpi_fingerprint: str,
    drivers: List[ScoredCandidate],
    dimensions: List[ScoredCandidate],
    limits: GraphLimits | None = None,
) -> Dict[str, Any]:
    """Build the full impact graph JSON.

    Returns::

        {
            "graph": {"meta": ..., "nodes": [...], "edges": [...]},
            "paths": [...],
            "evidence": {...},
        }
    """
    if limits is None:
        limits = GraphLimits()

    truncated = False
    kpi_id = kpi_node_id(kpi_fingerprint)

    # ── Nodes ─────────────────────────────────────────────────
    nodes: List[dict] = [{
        "id": kpi_id, "type": "KPI",
        "label": kpi_fingerprint, "score": 1.0,
        "meta": {"time_from": analysis.time_from, "time_to": analysis.time_to},
    }]

    def nid(c: ScoredCandidate) -> str:
        return column_node_id_from_key(c.column_key)

    # Each column gets exactly one role: assign by higher score (driver vs dimension)
    drv_score: dict[str, ScoredCandidate] = {c.column_key: c for c in drivers}
    dim_score: dict[str, ScoredCandidate] = {c.column_key: c for c in dimensions}
    all_keys = list(dict.fromkeys(
        [c.column_key for c in drivers] + [c.column_key for c in dimensions]
    ))
    final_drv: list[ScoredCandidate] = []
    final_dim: list[ScoredCandidate] = []
    for ck in all_keys:
        d = drv_score.get(ck)
        m = dim_score.get(ck)
        if d and m:
            if d.score >= m.score:
                final_drv.append(d)
            else:
                final_dim.append(m)
        elif d:
            final_drv.append(d)
        elif m:
            final_dim.append(m)

    max_total = limits.max_nodes - 1
    drv = final_drv[:max_total]
    dim = final_dim[:max(0, max_total - len(drv))]

    for c in drv:
        nodes.append({
            "id": nid(c), "type": "DRIVER",
            "label": c.column_key, "score": float(c.score),
            "meta": c.breakdown,
        })
    for c in dim:
        nodes.append({
            "id": nid(c), "type": "DIMENSION",
            "label": c.column_key, "score": float(c.score),
            "meta": c.breakdown,
        })

    if len(nodes) >= limits.max_nodes:
        truncated = True

    node_scores = {n["id"]: float(n.get("score", 0.0)) for n in nodes}

    # ── Edges ─────────────────────────────────────────────────
    edges: List[dict] = []
    ec = 0

    # 1) KPI → DRIVER
    for c in drv:
        w = _edge_weight(c.score, c.breakdown.get("cooccur_with_kpi", 0))
        edges.append({
            "id": f"{kpi_id}__{nid(c)}", "source": kpi_id,
            "target": nid(c), "type": "INFLUENCES", "weight": w,
            "meta": {
                "reason": "cooccur_with_kpi+role_signal",
                "cooccur_with_kpi": c.breakdown.get("cooccur_with_kpi", 0),
            },
        })
        ec += 1
        if ec >= limits.max_edges:
            truncated = True
            break

    # 2) DRIVER ↔ DRIVER (cooccur matrix preferred, join_edges fallback)
    cooccur = analysis.cooccur
    driver_tables = {nid(c): c.table for c in drv}
    driver_col_keys = {nid(c): c.column_key for c in drv}
    join_strength: Dict[tuple, int] = defaultdict(int)
    for (ta, tb), cnt in analysis.join_edges.items():
        join_strength[tuple(sorted([ta, tb]))] += cnt

    if ec < limits.max_edges:
        drv_ids = [nid(c) for c in drv]
        for i in range(len(drv_ids)):
            for j in range(i + 1, len(drv_ids)):
                a, b = drv_ids[i], drv_ids[j]

                # Prefer cooccur matrix when available
                if cooccur is not None:
                    cnt = cooccur.strength(driver_col_keys[a], driver_col_keys[b])
                else:
                    key = tuple(sorted([driver_tables[a], driver_tables[b]]))
                    cnt = join_strength.get(key, 0)

                if cnt <= 0:
                    continue
                w = _clamp(
                    (1.0 - math.exp(-cnt / 6.0))
                    * (0.4 + 0.3 * node_scores[a] + 0.3 * node_scores[b])
                )
                if w < 0.15:
                    continue
                reason = "cooccur_matrix" if cooccur is not None else "join_edge"
                edges.append({
                    "id": f"{a}__{b}", "source": a, "target": b,
                    "type": "COUPLED", "weight": w,
                    "meta": {"reason": reason, "cooccur_count": cnt},
                })
                ec += 1
                if ec >= limits.max_edges:
                    truncated = True
                    break
            if ec >= limits.max_edges:
                break

    # 3) DRIVER → DIMENSION (cooccur preferred, score proxy fallback)
    dim_col_keys = {nid(c): c.column_key for c in dim}
    if ec < limits.max_edges:
        drv_ids = [nid(c) for c in drv]
        dim_scores = {nid(c): c.score for c in dim}
        for d in drv_ids:
            for c in dim:
                m = nid(c)
                if dim_scores.get(m, 0) < 0.15:
                    continue

                # Prefer cooccur strength when available
                if cooccur is not None:
                    co_cnt = cooccur.strength(driver_col_keys[d], dim_col_keys[m])
                    co_norm = cooccur.normalize(driver_col_keys[d], dim_col_keys[m])
                    w = _clamp(
                        0.4 * co_norm
                        + 0.3 * node_scores[d]
                        + 0.3 * node_scores[m]
                    )
                else:
                    co_cnt = 0
                    w = _clamp(0.35 * node_scores[d] + 0.35 * node_scores[m])

                if w < 0.18:
                    continue
                reason = "cooccur" if cooccur is not None and co_cnt > 0 else "co_usage_proxy"
                edges.append({
                    "id": f"{d}__{m}", "source": d, "target": m,
                    "type": "EXPLAINS_BY", "weight": w,
                    "meta": {"reason": reason, "cooccur_count": co_cnt},
                })
                ec += 1
                if ec >= limits.max_edges:
                    truncated = True
                    break
            if ec >= limits.max_edges:
                break

    # ── Paths (top K, depth <= 3) ─────────────────────────────
    paths = _top_paths(kpi_id, edges, limits.top_paths)

    # ── Evidence (compact) ────────────────────────────────────
    evidence = _compact_evidence(analysis, [n["id"] for n in nodes])

    return {
        "graph": {
            "meta": {
                "schema_version": "insight/v3",
                "analysis_version": "v1",
                "generated_at": None,  # filled by worker
                "time_range": {"from": analysis.time_from, "to": analysis.time_to},
                "datasource": None,
                "cache_hit": False,
                "limits": {
                    "max_nodes": limits.max_nodes,
                    "max_edges": limits.max_edges,
                    "depth": limits.depth,
                    "top_paths": limits.top_paths,
                },
                "truncated": truncated,
                "explain": {
                    "total_queries_analyzed": analysis.total_queries,
                    "used_queries": analysis.used_queries,
                    "mode": "primary",
                },
            },
            "nodes": nodes,
            "edges": edges,
        },
        "paths": paths,
        "evidence": evidence,
    }


def _top_paths(root_id: str, edges: List[dict], k: int) -> List[dict]:
    """Simple path enumeration: root -> A -> B (depth <= 3)."""
    out_edges: Dict[str, list] = defaultdict(list)
    for e in edges:
        out_edges[e["source"]].append(e)

    candidates = []
    for e1 in out_edges.get(root_id, []):
        a = e1["target"]
        candidates.append(([root_id, a], float(e1["weight"]), [e1["meta"]]))
        for e2 in out_edges.get(a, []):
            b = e2["target"]
            if b == root_id:
                continue
            score = float(e1["weight"]) + float(e2["weight"])
            candidates.append(([root_id, a, b], score, [e1["meta"], e2["meta"]]))

    candidates.sort(key=lambda x: x[1], reverse=True)
    return [{"nodes": p, "score": s, "why": w} for p, s, w in candidates[:k]]


def _compact_evidence(
    analysis: AnalysisResult, node_ids: List[str],
) -> Dict[str, List[dict]]:
    """Per-node top 3 evidence for Query Subgraph."""
    out: Dict[str, List[dict]] = {}
    for nid in node_ids:
        parsed = parse_node_id(nid)
        if not parsed or parsed["prefix"] != "col":
            continue
        # Reconstruct column_key (table.column) from parsed parts
        parts = parsed["parts"]
        if len(parts) >= 3:
            ck = f"{parts[-2]}.{parts[-1]}"
        elif len(parts) == 2:
            ck = f"{parts[0]}.{parts[1]}"
        else:
            continue
        evs = analysis.evidence_samples.get(ck, [])
        if not evs:
            continue
        out[nid] = [
            {
                "query_id": ev.query_id,
                "executed_at": ev.executed_at,
                "tables": ev.tables[:10],
                "joins": ev.joins[:6],
                "predicates": ev.predicates[:8],
                "group_by": ev.group_by[:8],
                "select": ev.select_cols[:8],
            }
            for ev in evs[:3]
        ]
    return out
