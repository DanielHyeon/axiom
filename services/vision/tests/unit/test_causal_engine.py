"""
인과 분석 엔진 단위 테스트.

CausalAnalysisEngine의 핵심 기능을 검증한다:
- Granger 인과 관계 감지
- 곱셈/덧셈 분해형 관계 탐지
- VAR 실패 시 폴백
- 공선성 진단
- 영향도 점수 정규화
- 데이터 부족 경고
- CausalEdge 직렬화
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.engines.causal_analysis_engine import (
    CausalAnalysisEngine,
    CausalEdge,
    DETERMINISTIC_RELATION_TYPES,
    diagnose_collinearity,
)


class TestCausalAnalysisEngine:
    """CausalAnalysisEngine 핵심 기능 테스트."""

    @pytest.fixture
    def engine(self) -> CausalAnalysisEngine:
        """기본 설정의 엔진 인스턴스."""
        return CausalAnalysisEngine(significance_level=0.05, min_correlation=0.3, max_lag=2)

    @pytest.fixture
    def simple_causal_data(self) -> pd.DataFrame:
        """명확한 인과 관계: x -> y (lag=2)"""
        np.random.seed(42)
        n = 200
        x = np.random.randn(n).cumsum()
        y = np.zeros(n)
        for i in range(2, n):
            y[i] = 0.7 * x[i - 2] + 0.3 * np.random.randn()
        return pd.DataFrame({"x": x, "y": y})

    @pytest.fixture
    def multiplicative_data(self) -> pd.DataFrame:
        """곱셈 분해 관계: target = a * b"""
        np.random.seed(42)
        n = 100
        a = np.random.uniform(1, 10, n)
        b = np.random.uniform(1, 5, n)
        target = a * b
        return pd.DataFrame({"a": a, "b": b, "target": target})

    @pytest.fixture
    def additive_data(self) -> pd.DataFrame:
        """덧셈 분해 관계: target = a + b + c"""
        np.random.seed(42)
        n = 100
        a = np.random.uniform(10, 50, n)
        b = np.random.uniform(5, 30, n)
        c = np.random.uniform(1, 10, n)
        target = a + b + c
        return pd.DataFrame({"a": a, "b": b, "c": c, "target": target})

    def test_granger_causality_detection(
        self, engine: CausalAnalysisEngine, simple_causal_data: pd.DataFrame
    ) -> None:
        """Granger 인과 관계가 올바르게 감지되는지 검증."""
        edges = engine.analyze(simple_causal_data, target_var="y")
        # 최소한 하나의 엣지가 발견되어야 함
        assert len(edges) > 0
        # x -> y Granger 엣지가 있어야 함
        granger_edges = [e for e in edges if e.method == "granger"]
        assert len(granger_edges) > 0
        assert granger_edges[0].source == "x"
        assert granger_edges[0].target == "y"
        # lag > 0 (시차가 있는 관계)
        assert granger_edges[0].lag > 0

    def test_multiplicative_decomposition(
        self, engine: CausalAnalysisEngine, multiplicative_data: pd.DataFrame
    ) -> None:
        """곱셈 분해 관계 탐지 검증."""
        hints = {("a", "target"): "deterministic", ("b", "target"): "deterministic"}
        edges = engine.analyze(
            multiplicative_data, target_var="target", relation_hints=hints
        )
        # a, b 둘 다 엣지로 나와야 함
        assert len(edges) >= 2
        decomp = [e for e in edges if e.method == "decomposition"]
        assert len(decomp) >= 2
        # strength는 0~1 범위
        for e in decomp:
            assert 0.0 <= e.strength <= 1.0

    def test_additive_decomposition(
        self, engine: CausalAnalysisEngine, additive_data: pd.DataFrame
    ) -> None:
        """덧셈 분해 관계 탐지 검증."""
        hints = {
            ("a", "target"): "deterministic",
            ("b", "target"): "deterministic",
            ("c", "target"): "deterministic",
        }
        edges = engine.analyze(
            additive_data, target_var="target", relation_hints=hints
        )
        # 세 변수 모두 엣지로 나와야 함
        assert len(edges) >= 3
        sources = {e.source for e in edges}
        assert "a" in sources
        assert "b" in sources
        assert "c" in sources

    def test_impact_scores_normalized(
        self, engine: CausalAnalysisEngine, simple_causal_data: pd.DataFrame
    ) -> None:
        """영향도 점수가 0~1로 정규화되는지 검증."""
        edges = engine.analyze(simple_causal_data, target_var="y")
        scores = engine.calculate_impact_scores(edges)
        assert all(0.0 <= v <= 1.0 for v in scores.values())
        # 최소한 하나의 점수가 있고, 최대값이 1.0이어야 함
        if scores:
            assert max(scores.values()) == 1.0

    def test_insufficient_data_warning(self, engine: CausalAnalysisEngine) -> None:
        """데이터 부족 시 UserWarning 발생 검증."""
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0]})
        with pytest.warns(UserWarning, match="데이터가 충분하지 않습니다"):
            engine.analyze(df, target_var="y")

    def test_non_numeric_target_raises(self, engine: CausalAnalysisEngine) -> None:
        """타겟 변수가 숫자형이 아닐 때 ValueError 발생."""
        df = pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
        with pytest.raises(ValueError, match="타겟 변수"):
            engine.analyze(df, target_var="y")

    def test_no_cause_vars_raises(self, engine: CausalAnalysisEngine) -> None:
        """인과 후보 변수가 없을 때 ValueError 발생."""
        df = pd.DataFrame({"y": [1.0, 2.0, 3.0], "z": ["a", "b", "c"]})
        with pytest.raises(ValueError, match="인과 후보 변수가 없습니다"):
            engine.analyze(df, target_var="y")

    def test_var_failure_fallback(self, engine: CausalAnalysisEngine) -> None:
        """VAR 실패 시 상관/분해형 폴백이 작동하는지 검증."""
        np.random.seed(42)
        n = 50
        x = np.random.randn(n)
        # y가 x와 거의 동일 → VAR positive definite 실패 가능
        y = x + 1e-12 * np.random.randn(n)
        df = pd.DataFrame({"x": x, "y": y})
        edges = engine.analyze(df, target_var="y")
        # VAR 실패해도 상관 또는 분해형으로 엣지가 나와야 함
        assert len(edges) > 0

    def test_edge_to_dict(self) -> None:
        """CausalEdge.to_dict() 직렬화 검증."""
        edge = CausalEdge(
            source="x", target="y", method="granger",
            strength=0.85, p_value=0.001, lag=2, direction="positive"
        )
        d = edge.to_dict()
        assert d["source"] == "x"
        assert d["target"] == "y"
        assert d["method"] == "granger"
        assert d["strength"] == 0.85
        assert d["p_value"] == 0.001
        assert d["lag"] == 2
        assert d["direction"] == "positive"

    def test_edge_frozen(self) -> None:
        """CausalEdge가 frozen dataclass인지 검증."""
        edge = CausalEdge(
            source="x", target="y", method="granger",
            strength=0.5, p_value=0.01,
        )
        with pytest.raises(AttributeError):
            edge.source = "z"  # type: ignore[misc]

    def test_deterministic_relation_types(self) -> None:
        """분해형 관계 타입 상수 검증."""
        assert "DERIVED_FROM" in DETERMINISTIC_RELATION_TYPES
        assert "FORMULA" in DETERMINISTIC_RELATION_TYPES
        assert "CAUSES" not in DETERMINISTIC_RELATION_TYPES

    def test_empty_impact_scores(self, engine: CausalAnalysisEngine) -> None:
        """빈 엣지 목록에 대한 영향도 점수."""
        scores = engine.calculate_impact_scores([])
        assert scores == {}

    def test_mixed_hints(self, engine: CausalAnalysisEngine) -> None:
        """dynamic + deterministic 혼합 hints 처리."""
        np.random.seed(42)
        n = 100
        a = np.random.uniform(1, 10, n)
        b = np.random.randn(n).cumsum()
        target = a * 2 + b * 0.5 + np.random.randn(n) * 0.1
        df = pd.DataFrame({"a": a, "b": b, "target": target})
        hints = {("a", "target"): "deterministic"}
        edges = engine.analyze(df, target_var="target", relation_hints=hints)
        # a는 decomposition, b는 granger 또는 correlation
        assert len(edges) >= 1


class TestDiagnoseCollinearity:
    """공선성 진단 함수 테스트."""

    def test_near_constant_detection(self) -> None:
        """거의 상수인 열 감지."""
        df = pd.DataFrame({
            "target": [1.0, 1.0, 1.0, 1.0],
            "cause": [2.0, 3.0, 4.0, 5.0],
        })
        result = diagnose_collinearity(df, "target", ["cause"])
        assert "target" in result["near_constant_cols"]

    def test_high_correlation_detection(self) -> None:
        """거의 동일한 열 쌍 감지."""
        n = 100
        x = np.arange(n, dtype=float)
        df = pd.DataFrame({"target": x, "cause": x * 1.0000001})
        result = diagnose_collinearity(df, "target", ["cause"])
        assert len(result["high_corr_pairs"]) > 0

    def test_multiplicative_fit(self) -> None:
        """곱셈 근사 R-squared 검증."""
        np.random.seed(42)
        a = np.random.uniform(1, 10, 100)
        b = np.random.uniform(1, 5, 100)
        df = pd.DataFrame({"a": a, "b": b, "target": a * b})
        result = diagnose_collinearity(df, "target", ["a", "b"])
        assert result["multiplicative_fit_r2"] > 0.95
        assert result["is_likely_deterministic"] is True

    def test_not_deterministic(self) -> None:
        """분해형이 아닌 데이터."""
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            "target": np.random.randn(n),
            "cause": np.random.randn(n),
        })
        result = diagnose_collinearity(df, "target", ["cause"])
        assert result["is_likely_deterministic"] is False

    def test_empty_cause_vars(self) -> None:
        """빈 cause_vars 처리."""
        df = pd.DataFrame({"target": [1.0, 2.0, 3.0]})
        result = diagnose_collinearity(df, "target", [])
        assert result["is_likely_deterministic"] is False

    def test_non_numeric_target(self) -> None:
        """숫자형이 아닌 타겟 처리."""
        df = pd.DataFrame({"target": ["a", "b", "c"], "cause": [1.0, 2.0, 3.0]})
        result = diagnose_collinearity(df, "target", ["cause"])
        assert result["is_likely_deterministic"] is False


class TestFitVarModel:
    """VAR 모델 단독 피팅 테스트."""

    def test_fit_success(self) -> None:
        """VAR 모델 피팅 성공."""
        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            "x": np.random.randn(n).cumsum(),
            "y": np.random.randn(n).cumsum(),
        })
        engine = CausalAnalysisEngine()
        result = engine.fit_var_model(df)
        assert result is not None
        assert result.k_ar >= 1

    def test_fit_insufficient_data(self) -> None:
        """데이터 부족 시 ValueError."""
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0]})
        engine = CausalAnalysisEngine()
        with pytest.raises(ValueError, match="데이터가 충분하지 않습니다"):
            engine.fit_var_model(df)


class TestGrangerCausality:
    """Granger 인과 검정 단독 실행 테스트."""

    def test_granger_test(self) -> None:
        """VAR 결과로부터 Granger 검정 실행."""
        np.random.seed(42)
        n = 200
        x = np.random.randn(n).cumsum()
        y = np.zeros(n)
        for i in range(2, n):
            y[i] = 0.7 * x[i - 2] + 0.3 * np.random.randn()
        df = pd.DataFrame({"x": x, "y": y})
        engine = CausalAnalysisEngine()
        var_results = engine.fit_var_model(df)
        result = engine.test_granger_causality(var_results, "x", "y")
        assert "f_statistic" in result
        assert "p_value" in result
        assert "is_significant" in result
