"""PR7 tests: query_log_analyzer, driver_scorer, impact_graph_builder."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.services.query_log_analyzer import (
    AnalysisResult,
    AnalyzerConfig,
    CandidateStats,
    QueryEvidence,
    _is_time_like,
    _normalize_col_key,
)
from app.services.driver_scorer import (
    DriverScoreConfig,
    ScoredCandidate,
    score_candidates,
)
from app.services.impact_graph_builder import (
    GraphLimits,
    build_impact_graph,
    _edge_weight,
    _top_paths,
)


# ── Helpers ──────────────────────────────────────────────────

def _make_analysis(
    col_stats: dict | None = None,
    table_counts: dict | None = None,
    join_edges: dict | None = None,
    evidence_samples: dict | None = None,
    total_queries: int = 100,
    used_queries: int = 100,
) -> AnalysisResult:
    return AnalysisResult(
        time_from="2026-01-27T00:00:00+00:00",
        time_to="2026-02-26T00:00:00+00:00",
        total_queries=total_queries,
        used_queries=used_queries,
        column_stats=col_stats or {},
        table_counts=table_counts or {},
        join_edges=join_edges or {},
        evidence_samples=evidence_samples or {},
    )


def _make_candidate_stats(
    appear: int = 10,
    in_select: int = 5,
    in_filter: int = 3,
    in_group_by: int = 0,
    join_degree: int = 0,
    cooccur_with_kpi: int = 5,
    distinct_queries: int = 8,
) -> CandidateStats:
    cs = CandidateStats()
    cs.appear = appear
    cs.in_select = in_select
    cs.in_filter = in_filter
    cs.in_group_by = in_group_by
    cs.join_degree = join_degree
    cs.cooccur_with_kpi = cooccur_with_kpi
    cs.distinct_queries = distinct_queries
    cs.distinct_tables = {"orders"}
    return cs


def _make_evidence(executed_at: str = "2026-02-20T12:00:00+00:00") -> QueryEvidence:
    return QueryEvidence(
        query_id="q1", datasource="ds1",
        executed_at=executed_at,
        tables=["orders"], joins=[], predicates=[],
        select_cols=[], group_by=[],
    )


# ── Analyzer helpers tests ───────────────────────────────────

class TestAnalyzerHelpers:

    def test_is_time_like_true(self):
        assert _is_time_like("created_at") is True
        assert _is_time_like("order_date") is True
        assert _is_time_like("update_timestamp") is True

    def test_is_time_like_false(self):
        assert _is_time_like("product_name") is False
        assert _is_time_like("amount") is False

    def test_normalize_col_key_two_parts(self):
        assert _normalize_col_key("orders.amount") == "orders.amount"

    def test_normalize_col_key_three_parts(self):
        assert _normalize_col_key("public.orders.amount") == "orders.amount"

    def test_normalize_col_key_single_part(self):
        assert _normalize_col_key("amount") == ""

    def test_normalize_col_key_lowercases(self):
        assert _normalize_col_key("Orders.Amount") == "orders.amount"


# ── Driver scorer tests ──────────────────────────────────────

class TestDriverScorer:

    def test_empty_stats_returns_empty(self):
        analysis = _make_analysis()
        drivers, dims = score_candidates(analysis, "kpi:revenue")
        assert drivers == []
        assert dims == []

    def test_basic_driver_scoring(self):
        stats = {
            "orders.amount": _make_candidate_stats(
                in_filter=8, in_group_by=0, cooccur_with_kpi=10,
                distinct_queries=15,
            ),
            "orders.status": _make_candidate_stats(
                in_filter=2, in_group_by=5, cooccur_with_kpi=3,
                distinct_queries=10,
            ),
        }
        evidence = {
            "orders.amount": [_make_evidence()],
            "orders.status": [_make_evidence()],
        }
        analysis = _make_analysis(col_stats=stats, evidence_samples=evidence)
        drivers, dims = score_candidates(analysis, "kpi:revenue")

        assert len(drivers) >= 2
        # Amount should rank higher as driver (more filter, more cooccur)
        amount_drv = next(d for d in drivers if d.column == "amount")
        status_drv = next(d for d in drivers if d.column == "status")
        assert amount_drv.score > status_drv.score

    def test_time_column_penalized(self):
        stats = {
            "orders.created_at": _make_candidate_stats(
                in_filter=5, cooccur_with_kpi=5, distinct_queries=5,
            ),
            "orders.amount": _make_candidate_stats(
                in_filter=5, cooccur_with_kpi=5, distinct_queries=5,
            ),
        }
        evidence = {
            "orders.created_at": [_make_evidence()],
            "orders.amount": [_make_evidence()],
        }
        analysis = _make_analysis(col_stats=stats, evidence_samples=evidence)
        drivers, _ = score_candidates(analysis, "kpi:revenue")

        created_at = next(d for d in drivers if d.column == "created_at")
        amount = next(d for d in drivers if d.column == "amount")
        assert amount.score > created_at.score

    def test_group_by_column_becomes_dimension(self):
        stats = {
            "orders.region": _make_candidate_stats(
                in_filter=0, in_group_by=10, cooccur_with_kpi=5,
                distinct_queries=8,
            ),
        }
        evidence = {"orders.region": [_make_evidence()]}
        analysis = _make_analysis(col_stats=stats, evidence_samples=evidence)
        _, dims = score_candidates(analysis, "kpi:revenue")

        region = next(d for d in dims if d.column == "region")
        assert region.role == "DIMENSION"
        assert region.score > 0

    def test_min_distinct_queries_filter(self):
        stats = {
            "orders.rare_col": _make_candidate_stats(
                distinct_queries=1, cooccur_with_kpi=1,
            ),
        }
        evidence = {"orders.rare_col": [_make_evidence()]}
        analysis = _make_analysis(col_stats=stats, evidence_samples=evidence)
        drivers, dims = score_candidates(
            analysis, "kpi:revenue",
            cfg=DriverScoreConfig(min_distinct_queries=2),
        )
        assert len(drivers) == 0
        assert len(dims) == 0

    def test_top_n_limit(self):
        stats = {}
        evidence = {}
        for i in range(30):
            key = f"t{i}.col{i}"
            stats[key] = _make_candidate_stats(
                in_filter=i, cooccur_with_kpi=i, distinct_queries=5+i,
            )
            evidence[key] = [_make_evidence()]
        analysis = _make_analysis(col_stats=stats, evidence_samples=evidence)
        drivers, dims = score_candidates(
            analysis, "kpi:test",
            cfg=DriverScoreConfig(top_drivers=10, top_dimensions=10),
        )
        assert len(drivers) == 10
        assert len(dims) == 10

    def test_scores_are_non_negative(self):
        stats = {
            "orders.amount": _make_candidate_stats(
                in_filter=3, cooccur_with_kpi=2, distinct_queries=5,
            ),
        }
        evidence = {"orders.amount": [_make_evidence()]}
        analysis = _make_analysis(col_stats=stats, evidence_samples=evidence)
        drivers, dims = score_candidates(analysis, "kpi:revenue")
        for d in drivers:
            assert d.score >= 0.0
        for d in dims:
            assert d.score >= 0.0

    def test_breakdown_fields_present(self):
        stats = {
            "orders.amount": _make_candidate_stats(
                in_filter=3, cooccur_with_kpi=2, distinct_queries=5,
            ),
        }
        evidence = {"orders.amount": [_make_evidence()]}
        analysis = _make_analysis(col_stats=stats, evidence_samples=evidence)
        drivers, _ = score_candidates(analysis, "kpi:revenue")
        d = drivers[0]
        assert "usage" in d.breakdown
        assert "filter_ratio" in d.breakdown
        assert "volatility" in d.breakdown


# ── Graph builder tests ──────────────────────────────────────

class TestEdgeWeight:

    def test_zero_score_zero_cooccur(self):
        w = _edge_weight(0.0, 0)
        assert 0.0 <= w <= 1.0

    def test_high_score_high_cooccur(self):
        w = _edge_weight(0.9, 20)
        assert w > 0.5

    def test_clamped_to_01(self):
        w = _edge_weight(2.0, 100)  # artificially high
        assert w <= 1.0


class TestBuildImpactGraph:

    def _make_drivers(self) -> list[ScoredCandidate]:
        return [
            ScoredCandidate(
                column_key="orders.amount", table="orders", column="amount",
                role="DRIVER", score=0.85,
                breakdown={"cooccur_with_kpi": 10, "distinct_queries": 20},
            ),
            ScoredCandidate(
                column_key="orders.product_id", table="orders", column="product_id",
                role="DRIVER", score=0.65,
                breakdown={"cooccur_with_kpi": 5, "distinct_queries": 15},
            ),
        ]

    def _make_dims(self) -> list[ScoredCandidate]:
        return [
            ScoredCandidate(
                column_key="orders.region", table="orders", column="region",
                role="DIMENSION", score=0.55,
                breakdown={"cooccur_with_kpi": 3, "distinct_queries": 10},
            ),
        ]

    def test_graph_has_kpi_node(self):
        analysis = _make_analysis()
        result = build_impact_graph(
            analysis, "revenue", self._make_drivers(), self._make_dims(),
        )
        nodes = result["graph"]["nodes"]
        kpi_nodes = [n for n in nodes if n["type"] == "KPI"]
        assert len(kpi_nodes) == 1
        assert kpi_nodes[0]["id"] == "kpi:revenue"

    def test_graph_has_driver_nodes(self):
        analysis = _make_analysis()
        result = build_impact_graph(
            analysis, "revenue", self._make_drivers(), self._make_dims(),
        )
        nodes = result["graph"]["nodes"]
        driver_nodes = [n for n in nodes if n["type"] == "DRIVER"]
        assert len(driver_nodes) == 2

    def test_graph_has_dimension_nodes(self):
        analysis = _make_analysis()
        result = build_impact_graph(
            analysis, "revenue", self._make_drivers(), self._make_dims(),
        )
        nodes = result["graph"]["nodes"]
        dim_nodes = [n for n in nodes if n["type"] == "DIMENSION"]
        assert len(dim_nodes) == 1

    def test_kpi_to_driver_edges(self):
        analysis = _make_analysis()
        result = build_impact_graph(
            analysis, "revenue", self._make_drivers(), self._make_dims(),
        )
        edges = result["graph"]["edges"]
        influences = [e for e in edges if e["type"] == "INFLUENCES"]
        assert len(influences) == 2
        for e in influences:
            assert e["source"] == "kpi:revenue"

    def test_driver_coupled_edges_with_joins(self):
        analysis = _make_analysis(
            join_edges={("orders", "products"): 15},
        )
        drivers = [
            ScoredCandidate(
                column_key="orders.amount", table="orders", column="amount",
                role="DRIVER", score=0.85,
                breakdown={"cooccur_with_kpi": 10, "distinct_queries": 20},
            ),
            ScoredCandidate(
                column_key="products.price", table="products", column="price",
                role="DRIVER", score=0.7,
                breakdown={"cooccur_with_kpi": 8, "distinct_queries": 18},
            ),
        ]
        result = build_impact_graph(analysis, "revenue", drivers, [])
        edges = result["graph"]["edges"]
        coupled = [e for e in edges if e["type"] == "COUPLED"]
        assert len(coupled) >= 1

    def test_max_nodes_respected(self):
        drivers = []
        for i in range(150):
            drivers.append(ScoredCandidate(
                column_key=f"t.col{i}", table="t", column=f"col{i}",
                role="DRIVER", score=0.5,
                breakdown={"cooccur_with_kpi": 1, "distinct_queries": 5},
            ))
        analysis = _make_analysis()
        result = build_impact_graph(
            analysis, "kpi", drivers, [],
            limits=GraphLimits(max_nodes=50, max_edges=300),
        )
        nodes = result["graph"]["nodes"]
        assert len(nodes) <= 50

    def test_max_edges_respected(self):
        drivers = []
        for i in range(50):
            drivers.append(ScoredCandidate(
                column_key=f"t.col{i}", table="t", column=f"col{i}",
                role="DRIVER", score=0.5,
                breakdown={"cooccur_with_kpi": 1, "distinct_queries": 5},
            ))
        analysis = _make_analysis()
        result = build_impact_graph(
            analysis, "kpi", drivers, [],
            limits=GraphLimits(max_edges=10),
        )
        edges = result["graph"]["edges"]
        assert len(edges) <= 10

    def test_meta_fields(self):
        analysis = _make_analysis(total_queries=500, used_queries=400)
        result = build_impact_graph(
            analysis, "revenue", self._make_drivers(), self._make_dims(),
        )
        meta = result["graph"]["meta"]
        assert meta["schema_version"] == "insight/v3"
        assert meta["explain"]["total_queries_analyzed"] == 500
        assert meta["explain"]["used_queries"] == 400

    def test_paths_generated(self):
        analysis = _make_analysis()
        result = build_impact_graph(
            analysis, "revenue", self._make_drivers(), self._make_dims(),
        )
        paths = result["paths"]
        assert isinstance(paths, list)
        # Should have at least 1 path (KPI → driver)
        if self._make_drivers():
            assert len(paths) >= 1

    def test_evidence_generated(self):
        analysis = _make_analysis(
            evidence_samples={
                "orders.amount": [_make_evidence()],
            },
        )
        result = build_impact_graph(
            analysis, "revenue", self._make_drivers(), self._make_dims(),
        )
        evidence = result["evidence"]
        assert isinstance(evidence, dict)

    def test_empty_drivers_produces_minimal_graph(self):
        analysis = _make_analysis()
        result = build_impact_graph(analysis, "revenue", [], [])
        nodes = result["graph"]["nodes"]
        edges = result["graph"]["edges"]
        assert len(nodes) == 1  # just KPI
        assert len(edges) == 0


# ── Top paths tests ──────────────────────────────────────────

class TestTopPaths:

    def test_empty_edges(self):
        assert _top_paths("root", [], 3) == []

    def test_single_hop(self):
        edges = [{"source": "root", "target": "A", "weight": 0.8, "meta": {}}]
        paths = _top_paths("root", edges, 3)
        assert len(paths) == 1
        assert paths[0]["nodes"] == ["root", "A"]

    def test_two_hop(self):
        edges = [
            {"source": "root", "target": "A", "weight": 0.8, "meta": {"r": 1}},
            {"source": "A", "target": "B", "weight": 0.6, "meta": {"r": 2}},
        ]
        paths = _top_paths("root", edges, 5)
        # Should have: root→A and root→A→B
        assert len(paths) == 2
        two_hop = [p for p in paths if len(p["nodes"]) == 3]
        assert len(two_hop) == 1
        assert two_hop[0]["score"] == pytest.approx(1.4)


# ── Integration: scorer → builder pipeline ───────────────────

class TestScorerToBuilderPipeline:

    def test_full_pipeline(self):
        stats = {
            "orders.amount": _make_candidate_stats(
                in_filter=10, cooccur_with_kpi=15, distinct_queries=20,
            ),
            "orders.product_id": _make_candidate_stats(
                in_filter=5, in_group_by=0, join_degree=3,
                cooccur_with_kpi=8, distinct_queries=12,
            ),
            "orders.region": _make_candidate_stats(
                in_filter=1, in_group_by=8,
                cooccur_with_kpi=4, distinct_queries=10,
            ),
        }
        evidence = {k: [_make_evidence()] for k in stats}
        analysis = _make_analysis(
            col_stats=stats,
            evidence_samples=evidence,
            total_queries=500,
            used_queries=500,
        )

        drivers, dims = score_candidates(analysis, "kpi:revenue")
        assert len(drivers) > 0

        result = build_impact_graph(analysis, "revenue", drivers, dims)

        graph = result["graph"]
        assert len(graph["nodes"]) >= 2  # KPI + at least 1 driver
        assert len(graph["edges"]) >= 1  # at least KPI→driver
        assert graph["meta"]["explain"]["total_queries_analyzed"] == 500

        # Paths should exist
        assert len(result["paths"]) >= 1
