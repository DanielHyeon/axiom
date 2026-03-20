"""
FallbackPredictor 단위 테스트
==============================

sklearn 기반 간이 예측기의 학습/예측/엣지 케이스를 검증한다.
"""

import numpy as np
import pandas as pd
import pytest

from app.engines.whatif_fallback import FallbackPredictor


class TestFallbackPredictorTrain:
    """학습 기능 테스트."""

    def test_train_linear_regression(self):
        """데이터 부족 시 LinearRegression 사용."""
        predictor = FallbackPredictor()
        # 10행, 1개 피처 → LinearRegression
        df = pd.DataFrame({
            "x": np.arange(10, dtype=float),
            "y": np.arange(10, dtype=float) * 2 + 1,
        })
        metrics = predictor.train("test_lr", df, "y", ["x"])
        assert metrics["r2"] > 0.9
        assert predictor.has_model("test_lr")

    def test_train_random_forest(self):
        """데이터 충분 시 RandomForestRegressor 사용."""
        predictor = FallbackPredictor()
        rng = np.random.RandomState(42)
        n = 50
        df = pd.DataFrame({
            "x1": rng.randn(n),
            "x2": rng.randn(n),
            "y": rng.randn(n),
        })
        # 50행, 2개 피처 → RandomForest
        metrics = predictor.train("test_rf", df, "y", ["x1", "x2"])
        assert "r2" in metrics
        assert "mae" in metrics
        assert predictor.has_model("test_rf")

    def test_train_insufficient_rows(self):
        """행 수 < 5이면 학습 불가."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [2.0, 4.0, 6.0]})
        metrics = predictor.train("too_small", df, "y", ["x"])
        assert metrics["r2"] == 0.0
        assert not predictor.has_model("too_small")

    def test_train_missing_target_column(self):
        """타겟 컬럼이 df에 없으면 학습 불가."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({"x": np.arange(20, dtype=float)})
        metrics = predictor.train("no_target", df, "y", ["x"])
        assert metrics["r2"] == 0.0

    def test_train_missing_feature_columns(self):
        """피처 컬럼이 df에 없으면 학습 불가."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({"y": np.arange(20, dtype=float)})
        metrics = predictor.train("no_features", df, "y", ["x1", "x2"])
        assert metrics["r2"] == 0.0

    def test_train_duplicate_features_deduplicated(self):
        """중복 피처 컬럼은 제거."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({
            "x": np.arange(20, dtype=float),
            "y": np.arange(20, dtype=float) * 3,
        })
        metrics = predictor.train("dedup", df, "y", ["x", "x", "x"])
        assert metrics["r2"] > 0.9

    def test_train_with_nan_rows(self):
        """NaN 행은 제거 후 학습."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({
            "x": list(range(20)) + [None, None],
            "y": list(range(0, 40, 2)) + [None, None],
        })
        metrics = predictor.train("with_nan", df, "y", ["x"])
        assert metrics["r2"] > 0.9


class TestFallbackPredictorPredict:
    """예측 기능 테스트."""

    def _trained_predictor(self) -> FallbackPredictor:
        """간단하게 학습된 predictor 반환."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({
            "x1": np.arange(50, dtype=float),
            "x2": np.arange(50, dtype=float) * 0.5,
            "y": np.arange(50, dtype=float) * 2 + 1,
        })
        predictor.train("model_a", df, "y", ["x1", "x2"])
        return predictor

    def test_predict_existing_model(self):
        """학습된 모델로 예측."""
        predictor = self._trained_predictor()
        result = predictor.predict("model_a", {"x1": 10.0, "x2": 5.0})
        assert result is not None
        assert isinstance(result, float)

    def test_predict_nonexistent_model(self):
        """존재하지 않는 모델은 None 반환."""
        predictor = FallbackPredictor()
        result = predictor.predict("no_such_model", {"x": 1.0})
        assert result is None

    def test_predict_with_feature_name_map(self):
        """featureName 매핑으로 예측."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({
            "원자재__lead_time": np.arange(50, dtype=float),
            "y": np.arange(50, dtype=float) * 2,
        })
        predictor.train(
            "mapped",
            df,
            "y",
            ["원자재__lead_time"],
            feature_name_map={"lead_time": "원자재__lead_time"},
        )
        result = predictor.predict("mapped", {"lead_time": 25.0})
        assert result is not None

    def test_predict_suffix_matching(self):
        """suffix 매칭으로 피처 찾기."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({
            "table__cost_index": np.arange(50, dtype=float),
            "y": np.arange(50, dtype=float) * 1.5,
        })
        predictor.train("suffix", df, "y", ["table__cost_index"])
        # "cost_index"로 요청 → "table__cost_index" 매칭
        result = predictor.predict("suffix", {"cost_index": 25.0})
        assert result is not None

    def test_predict_empty_input(self):
        """빈 입력 → 기본값(0.0)으로 예측."""
        predictor = self._trained_predictor()
        result = predictor.predict("model_a", {})
        assert result is not None


class TestFallbackPredictorMisc:
    """기타 유틸리티 테스트."""

    def test_model_count(self):
        """model_count 속성."""
        predictor = FallbackPredictor()
        assert predictor.model_count == 0

        df = pd.DataFrame({"x": np.arange(20, dtype=float), "y": np.arange(20, dtype=float)})
        predictor.train("m1", df, "y", ["x"])
        assert predictor.model_count == 1

    def test_clear(self):
        """clear()로 모든 모델 제거."""
        predictor = FallbackPredictor()
        df = pd.DataFrame({"x": np.arange(20, dtype=float), "y": np.arange(20, dtype=float)})
        predictor.train("m1", df, "y", ["x"])
        predictor.clear()
        assert predictor.model_count == 0
        assert not predictor.has_model("m1")
