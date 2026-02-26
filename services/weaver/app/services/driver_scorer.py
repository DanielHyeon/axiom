"""Driver scorer — rank candidate columns as DRIVER or DIMENSION.

v1 scoring axes (4-axis):
  - Usage (0.45): KPI co-occur + distinct_queries breadth
  - Role Signal (0.25): filter→DRIVER, group_by→DIMENSION
  - Discriminative (0.20): filter+join mix → DRIVER, group_by only → penalty
  - Volatility (0.10): 2-half time split, frequency change bonus

Pure Python — no DB dependency.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from app.services.query_log_analyzer import (
    AnalysisResult,
    CandidateStats,
    _is_time_like,
)


@dataclass
class DriverScoreConfig:
    top_drivers: int = 20
    top_dimensions: int = 20
    w_usage: float = 0.45
    w_role: float = 0.25
    w_discriminative: float = 0.20
    w_volatility: float = 0.10
    time_dim_penalty: float = 0.35
    common_dim_penalty: float = 0.15
    min_distinct_queries: int = 2


@dataclass
class ScoredCandidate:
    column_key: str
    table: str
    column: str
    role: str          # "DRIVER" | "DIMENSION"
    score: float
    breakdown: dict


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _log1p(x: float) -> float:
    return math.log(1.0 + max(0.0, x))


def _parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts).astimezone(timezone.utc)


def score_candidates(
    analysis: AnalysisResult,
    kpi_fingerprint: str,
    cfg: DriverScoreConfig | None = None,
) -> Tuple[List[ScoredCandidate], List[ScoredCandidate]]:
    """Return ``(drivers_ranked, dimensions_ranked)``."""
    if cfg is None:
        cfg = DriverScoreConfig()

    col_stats = analysis.column_stats
    if not col_stats:
        return [], []

    # Volatility: 2-halves split
    time_from = _parse_iso(analysis.time_from)
    time_to = _parse_iso(analysis.time_to)
    mid = time_from + (time_to - time_from) / 2

    vol_ratio: Dict[str, float] = {}
    for ck, evidences in analysis.evidence_samples.items():
        recent = older = 0
        for ev in evidences:
            try:
                dt = _parse_iso(ev.executed_at)
            except Exception:
                continue
            if dt >= mid:
                recent += 1
            else:
                older += 1
        vol_ratio[ck] = abs(math.log((recent + 1) / (older + 1)))

    drivers: List[ScoredCandidate] = []
    dims: List[ScoredCandidate] = []

    for ck, st in col_stats.items():
        if "." not in ck:
            continue
        table, col = ck.split(".", 1)

        if st.distinct_queries < cfg.min_distinct_queries:
            continue

        # Signals
        usage = _log1p(st.cooccur_with_kpi) * _sigmoid(st.distinct_queries / 3.0)

        total_role = max(1, st.in_filter + st.in_group_by + st.join_degree + st.in_select)
        filter_ratio = st.in_filter / total_role
        group_ratio = st.in_group_by / total_role
        join_ratio = st.join_degree / total_role

        discriminative_driver = _sigmoid(
            (filter_ratio + 0.6 * join_ratio) - 0.8 * group_ratio
        )
        discriminative_dim = _sigmoid(group_ratio - 0.5 * filter_ratio)

        volatility = _sigmoid(vol_ratio.get(ck, 0.0))

        # Penalties
        penalty = 0.0
        if _is_time_like(col):
            penalty += cfg.time_dim_penalty
        if col.lower() in ("status", "state", "type", "category", "region", "country"):
            penalty += cfg.common_dim_penalty

        # DRIVER score
        role_driver = _sigmoid(
            2.0 * filter_ratio + 1.2 * join_ratio - 1.0 * group_ratio
        )
        score_driver = (
            cfg.w_usage * usage
            + cfg.w_role * role_driver
            + cfg.w_discriminative * discriminative_driver
            + cfg.w_volatility * volatility
        )
        score_driver = max(0.0, score_driver * (1.0 - penalty))

        drivers.append(ScoredCandidate(
            column_key=ck, table=table, column=col,
            role="DRIVER", score=float(score_driver),
            breakdown={
                "usage": float(usage),
                "filter_ratio": float(filter_ratio),
                "group_ratio": float(group_ratio),
                "join_ratio": float(join_ratio),
                "role_driver": float(role_driver),
                "discriminative": float(discriminative_driver),
                "volatility": float(volatility),
                "penalty": float(penalty),
                "cooccur_with_kpi": int(st.cooccur_with_kpi),
                "distinct_queries": int(st.distinct_queries),
            },
        ))

        # DIMENSION score
        role_dim = _sigmoid(
            2.2 * group_ratio + 0.4 * filter_ratio - 0.3 * join_ratio
        )
        score_dim = (
            cfg.w_usage * usage
            + cfg.w_role * role_dim
            + cfg.w_discriminative * discriminative_dim
            + 0.05 * volatility
        )
        dim_penalty = cfg.time_dim_penalty * 0.6 if _is_time_like(col) else 0.0
        score_dim = max(0.0, score_dim * (1.0 - dim_penalty))

        dims.append(ScoredCandidate(
            column_key=ck, table=table, column=col,
            role="DIMENSION", score=float(score_dim),
            breakdown={
                "usage": float(usage),
                "filter_ratio": float(filter_ratio),
                "group_ratio": float(group_ratio),
                "join_ratio": float(join_ratio),
                "role_dim": float(role_dim),
                "discriminative": float(discriminative_dim),
                "volatility": float(volatility),
                "penalty": float(dim_penalty),
                "cooccur_with_kpi": int(st.cooccur_with_kpi),
                "distinct_queries": int(st.distinct_queries),
            },
        ))

    drivers.sort(key=lambda x: x.score, reverse=True)
    dims.sort(key=lambda x: x.score, reverse=True)

    return drivers[:cfg.top_drivers], dims[:cfg.top_dimensions]
