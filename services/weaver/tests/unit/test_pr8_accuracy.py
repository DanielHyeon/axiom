"""PR8 tests: cooccur_matrix, kpi_metric_mapper, node_id."""
from __future__ import annotations

import pytest

from app.services.cooccur_matrix import (
    CooccurConfig,
    CooccurMatrix,
    build_cooccur_matrix,
)
from app.services.kpi_metric_mapper import (
    KpiDefinition,
    KpiMapperConfig,
    KpiMetricMapper,
    KpiMatch,
)
from app.services.node_id import (
    column_node_id,
    column_node_id_from_key,
    datasource_node_id,
    is_same_entity,
    kpi_node_id,
    metric_node_id,
    parse_node_id,
    table_node_id,
)


# ── CooccurMatrix tests ──────────────────────────────────────

class TestBuildCooccurMatrix:

    def test_empty_input(self):
        m = build_cooccur_matrix([])
        assert m.total_queries == 0
        assert m.pair_counts == {}

    def test_single_query_two_cols(self):
        m = build_cooccur_matrix(
            [{"orders.amount", "orders.status"}],
            config=CooccurConfig(min_cooccur_count=1),
        )
        assert m.total_queries == 1
        assert m.strength("orders.amount", "orders.status") == 1
        # Self-counts
        assert m.strength("orders.amount", "orders.amount") == 1

    def test_symmetric(self):
        m = build_cooccur_matrix(
            [{"a", "b"}, {"a", "b"}],
            config=CooccurConfig(min_cooccur_count=1),
        )
        assert m.strength("a", "b") == m.strength("b", "a")

    def test_min_count_pruning(self):
        m = build_cooccur_matrix(
            [{"a", "b"}],
            config=CooccurConfig(min_cooccur_count=2),
        )
        # Single occurrence pruned
        assert m.strength("a", "b") == 0
        # Self-counts preserved
        assert m.strength("a", "a") == 1

    def test_min_count_keeps_frequent(self):
        m = build_cooccur_matrix(
            [{"a", "b"}, {"a", "b"}, {"a", "b"}],
            config=CooccurConfig(min_cooccur_count=2),
        )
        assert m.strength("a", "b") == 3

    def test_max_cols_per_query(self):
        big_set = {f"col{i}" for i in range(100)}
        m = build_cooccur_matrix(
            [big_set],
            config=CooccurConfig(max_cols_per_query=5, min_cooccur_count=1),
        )
        # Only 5 cols kept → max 5 self-counts + C(5,2)=10 pairs
        assert m.total_queries == 1
        total_pairs = sum(1 for k, v in m.pair_counts.items() if k[0] != k[1])
        assert total_pairs <= 10


class TestCooccurMatrixMethods:

    def _make_matrix(self) -> CooccurMatrix:
        return build_cooccur_matrix(
            [
                {"a", "b", "c"},
                {"a", "b"},
                {"a", "c"},
                {"b", "c"},
            ],
            config=CooccurConfig(min_cooccur_count=1),
        )

    def test_strength(self):
        m = self._make_matrix()
        assert m.strength("a", "b") == 2
        assert m.strength("a", "c") == 2
        assert m.strength("b", "c") == 2

    def test_top_partners(self):
        m = self._make_matrix()
        partners = m.top_partners("a", k=5)
        assert len(partners) == 2
        partner_names = {p[0] for p in partners}
        assert "b" in partner_names
        assert "c" in partner_names

    def test_jaccard_normalization(self):
        m = self._make_matrix()
        norm = m.normalize("a", "b")
        assert 0.0 < norm <= 1.0
        # a appears 3 times, b appears 3 times, cooccur 2 times
        # Jaccard = 2 / (3 + 3 - 2) = 0.5
        assert norm == pytest.approx(0.5)

    def test_normalize_zero(self):
        m = CooccurMatrix()
        assert m.normalize("x", "y") == 0.0


# ── KpiMetricMapper tests ────────────────────────────────────

class TestKpiMetricMapper:

    def _make_mapper(self) -> KpiMetricMapper:
        defs = [
            KpiDefinition(
                kpi_id="revenue",
                name="Total Revenue",
                metric_sql="SUM(order_amount)",
                aliases=["total_sales", "total_revenue"],
            ),
            KpiDefinition(
                kpi_id="order_count",
                name="Order Count",
                metric_sql="COUNT(order_id)",
                aliases=["num_orders"],
            ),
        ]
        return KpiMetricMapper(defs)

    def test_exact_match(self):
        mapper = self._make_mapper()
        matches = mapper.match_select_exprs([
            {"expr": "SUM(order_amount)", "alias": "rev"},
        ])
        assert len(matches) == 1
        assert matches[0].kpi_id == "revenue"
        assert matches[0].match_type == "exact"
        assert matches[0].confidence == 1.0

    def test_alias_match(self):
        mapper = self._make_mapper()
        matches = mapper.match_select_exprs([
            {"expr": "SUM(o.amt)", "alias": "total_sales"},
        ])
        alias_matches = [m for m in matches if m.match_type == "alias"]
        assert len(alias_matches) >= 1
        assert alias_matches[0].kpi_id == "revenue"
        assert alias_matches[0].confidence == 0.7

    def test_fuzzy_match(self):
        mapper = self._make_mapper()
        # KPI name "Order Count" appears as substring in alias
        matches = mapper.match_select_exprs([
            {"expr": "SUM(x.cnt)", "alias": "monthly order count report"},
        ])
        fuzzy_matches = [m for m in matches if m.match_type == "fuzzy"]
        assert len(fuzzy_matches) >= 1
        assert fuzzy_matches[0].confidence == 0.3

    def test_no_match(self):
        mapper = self._make_mapper()
        matches = mapper.match_select_exprs([
            {"expr": "MAX(temperature)", "alias": "max_temp"},
        ])
        assert len(matches) == 0

    def test_exact_priority_over_alias(self):
        mapper = self._make_mapper()
        matches = mapper.match_select_exprs([
            {"expr": "SUM(order_amount)", "alias": "total_sales"},
        ])
        # Exact match should be found (may also find alias match but deduped)
        assert any(m.match_type == "exact" for m in matches)

    def test_best_match_returns_highest_confidence(self):
        mapper = self._make_mapper()
        best = mapper.best_match([
            {"expr": "SUM(order_amount)", "alias": "rev"},
        ])
        assert best is not None
        assert best.confidence == 1.0

    def test_best_match_returns_none_for_no_match(self):
        mapper = self._make_mapper()
        best = mapper.best_match([
            {"expr": "MAX(xyz)", "alias": "abc"},
        ])
        assert best is None

    def test_dedup_same_kpi(self):
        mapper = self._make_mapper()
        matches = mapper.match_select_exprs([
            {"expr": "SUM(order_amount)", "alias": "total_sales"},
        ])
        kpi_ids = [m.kpi_id for m in matches]
        assert kpi_ids.count("revenue") == 1  # not duplicated


# ── node_id tests ────────────────────────────────────────────

class TestNodeId:

    def test_table_node_id(self):
        assert table_node_id("public", "orders") == "tbl:public.orders"

    def test_column_node_id(self):
        assert column_node_id("public", "orders", "amount") == "col:public.orders.amount"

    def test_column_node_id_from_key_two_parts(self):
        assert column_node_id_from_key("orders.amount") == "col:public.orders.amount"

    def test_column_node_id_from_key_three_parts(self):
        assert column_node_id_from_key("sales.orders.amount") == "col:sales.orders.amount"

    def test_kpi_node_id(self):
        assert kpi_node_id("total_revenue") == "kpi:total_revenue"

    def test_metric_node_id(self):
        assert metric_node_id("sum_amount") == "metric:sum_amount"

    def test_datasource_node_id(self):
        assert datasource_node_id("oracle_prod") == "ds:oracle_prod"


class TestParseNodeId:

    def test_parse_column(self):
        result = parse_node_id("col:public.orders.amount")
        assert result == {"prefix": "col", "parts": ["public", "orders", "amount"]}

    def test_parse_table(self):
        result = parse_node_id("tbl:public.orders")
        assert result == {"prefix": "tbl", "parts": ["public", "orders"]}

    def test_parse_kpi(self):
        result = parse_node_id("kpi:revenue")
        assert result == {"prefix": "kpi", "parts": ["revenue"]}

    def test_invalid_no_colon(self):
        assert parse_node_id("nocolon") is None

    def test_invalid_prefix(self):
        assert parse_node_id("xxx:something") is None

    def test_roundtrip_column(self):
        nid = column_node_id("public", "orders", "amount")
        parsed = parse_node_id(nid)
        assert parsed["prefix"] == "col"
        assert parsed["parts"] == ["public", "orders", "amount"]

    def test_roundtrip_table(self):
        nid = table_node_id("myschema", "users")
        parsed = parse_node_id(nid)
        assert parsed["prefix"] == "tbl"
        assert parsed["parts"] == ["myschema", "users"]


class TestIsSameEntity:

    def test_same_column(self):
        assert is_same_entity(
            "col:public.orders.amount",
            "col:public.orders.amount",
        ) is True

    def test_schema_defaulting(self):
        assert is_same_entity(
            "col:orders.amount",
            "col:public.orders.amount",
        ) is True

    def test_different_column(self):
        assert is_same_entity(
            "col:public.orders.amount",
            "col:public.orders.status",
        ) is False

    def test_different_prefix(self):
        assert is_same_entity(
            "col:public.orders.amount",
            "tbl:public.orders",
        ) is False

    def test_table_schema_defaulting(self):
        assert is_same_entity(
            "tbl:orders",
            "tbl:public.orders",
        ) is True

    def test_invalid_ids(self):
        assert is_same_entity("garbage", "col:a.b.c") is False
        assert is_same_entity("col:a.b.c", "garbage") is False


# ── Integration: analyzer with cooccur ───────────────────────

class TestAnalyzerWithCooccur:

    def test_analysis_result_has_cooccur_field(self):
        from app.services.query_log_analyzer import AnalysisResult, CandidateStats
        result = AnalysisResult(
            time_from="2026-01-27T00:00:00+00:00",
            time_to="2026-02-26T00:00:00+00:00",
            total_queries=0,
            used_queries=0,
            column_stats={},
            table_counts={},
            join_edges={},
            evidence_samples={},
            cooccur=None,
        )
        assert result.cooccur is None

    def test_analysis_result_with_cooccur_matrix(self):
        from app.services.query_log_analyzer import AnalysisResult
        m = build_cooccur_matrix(
            [{"a", "b"}, {"a", "b"}],
            config=CooccurConfig(min_cooccur_count=1),
        )
        result = AnalysisResult(
            time_from="2026-01-27T00:00:00+00:00",
            time_to="2026-02-26T00:00:00+00:00",
            total_queries=2,
            used_queries=2,
            column_stats={},
            table_counts={},
            join_edges={},
            evidence_samples={},
            cooccur=m,
        )
        assert result.cooccur is not None
        assert result.cooccur.strength("a", "b") == 2
