"""Co-occurrence matrix — per-query column pair counting.

Tracks columns that appear together in the same query.  Used to replace
join_edges proxy with real co-occurrence data for DRIVER-DRIVER and
DRIVER-DIMENSION edges.

Cost control: ``max_cols_per_query`` (default 50) caps per-query pairs
at O(50^2) = O(2500).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple


@dataclass
class CooccurConfig:
    max_cols_per_query: int = 50
    min_cooccur_count: int = 2


@dataclass
class CooccurMatrix:
    """Symmetric co-occurrence counts between column keys."""

    pair_counts: Dict[Tuple[str, str], int] = field(default_factory=dict)
    total_queries: int = 0

    def strength(self, a: str, b: str) -> int:
        """Raw co-occurrence count for a pair."""
        key = tuple(sorted([a, b]))
        return self.pair_counts.get(key, 0)

    def top_partners(self, col_key: str, k: int = 10) -> List[Tuple[str, int]]:
        """Return top-k co-occurring partners for a given column."""
        matches = []
        for (a, b), cnt in self.pair_counts.items():
            partner = None
            if a == col_key:
                partner = b
            elif b == col_key:
                partner = a
            if partner and partner != col_key:
                matches.append((partner, cnt))
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:k]

    def normalize(self, a: str, b: str) -> float:
        """Jaccard-like normalization: cooccur(a,b) / (appear(a) + appear(b) - cooccur(a,b))."""
        cnt = self.strength(a, b)
        if cnt == 0:
            return 0.0
        a_total = self.strength(a, a) or cnt
        b_total = self.strength(b, b) or cnt
        denom = a_total + b_total - cnt
        return cnt / denom if denom > 0 else 0.0


def build_cooccur_matrix(
    per_query_columns: List[Set[str]],
    config: CooccurConfig | None = None,
) -> CooccurMatrix:
    """Build co-occurrence matrix from per-query column sets.

    Args:
        per_query_columns: Each set contains column_keys from one query.
    """
    if config is None:
        config = CooccurConfig()

    pair_counter: Counter = Counter()
    total = 0

    for cols in per_query_columns:
        total += 1
        col_list = sorted(cols)[:config.max_cols_per_query]

        # Self-counts (for normalization)
        for c in col_list:
            pair_counter[(c, c)] += 1

        # Pair counts
        for i in range(len(col_list)):
            for j in range(i + 1, len(col_list)):
                key = (col_list[i], col_list[j])
                pair_counter[key] += 1

    # Prune below threshold (keep self-counts)
    pruned = {
        k: v for k, v in pair_counter.items()
        if v >= config.min_cooccur_count or k[0] == k[1]
    }

    return CooccurMatrix(pair_counts=pruned, total_queries=total)
