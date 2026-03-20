"""
What-if FallbackPredictor (sklearn 기반 간이 예측기)
=====================================================

MindsDB 없이도 What-if 시뮬레이션을 돌릴 수 있도록,
sklearn의 RandomForestRegressor / LinearRegression을 사용하는 폴백 예측기.

KAIR의 FallbackPredictor를 Axiom에 이식한 것.

사용 흐름:
1. train(model_name, df, target_col, feature_cols) -> 학습 데이터로 모델 학습
2. predict(model_name, input_data) -> featureName 기반 예측

모델 선택 기준:
- 데이터 >= 20행 AND 피처 >= 2개 -> RandomForestRegressor (정확도 우선)
- 그 외 -> LinearRegression (안정성 우선)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class FallbackPredictor:
    """
    sklearn 기반 간이 예측기.

    What-if 시뮬레이션에서 모델이 예측값을 내야 할 때,
    MindsDB가 없거나 실패하면 이 예측기가 대신 답을 준다.
    """

    def __init__(self) -> None:
        # 학습된 모델 저장소: model_name -> {model, features, target, name_to_idx}
        self._models: dict[str, dict[str, Any]] = {}

    def train(
        self,
        model_name: str,
        df: Any,
        target_col: str,
        feature_cols: list[str],
        feature_name_map: dict[str, str] | None = None,
    ) -> dict[str, float]:
        """
        sklearn 모델 학습.

        Args:
            model_name: 모델 이름 (저장 키)
            df: pandas DataFrame (학습 데이터)
            target_col: 예측할 타겟 컬럼 (df의 컬럼명)
            feature_cols: 피처 컬럼 리스트 (df의 컬럼명)
            feature_name_map: {featureName: df_column} 매핑
                예: {"lead_time_days": "일별 원자재...__lead_time_days"}
                -> predict() 호출 시 featureName으로 올바른 위치에 값을 넣기 위함

        Returns:
            {"r2": ..., "mae": ...} 학습 결과 메트릭
        """
        try:
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.linear_model import LinearRegression
            from sklearn.metrics import mean_absolute_error, r2_score

            # 중복 피처 컬럼 제거 + df에 실제로 있는 컬럼만 사용
            seen: set[str] = set()
            available_features: list[str] = []
            for c in feature_cols:
                if c in df.columns and c not in seen:
                    available_features.append(c)
                    seen.add(c)

            # 피처나 타겟이 없으면 학습 불가
            if not available_features or target_col not in df.columns:
                logger.warning("학습 불가: 사용 가능한 피처 또는 타겟 컬럼 없음 (%s)", model_name)
                return {"r2": 0.0, "mae": 0.0}

            # 결측치 제거 후 최소 행 수 체크
            sub = df[[target_col] + available_features].dropna()
            if len(sub) < 5:
                logger.warning("학습 불가: 데이터 부족 (행 수=%d, 최소=5) (%s)", len(sub), model_name)
                return {"r2": 0.0, "mae": 0.0}

            X = sub[available_features].values
            y = sub[target_col].values

            # 모델 선택: 데이터 충분하면 RandomForest, 아니면 LinearRegression
            if len(available_features) >= 2 and len(sub) >= 20:
                model = RandomForestRegressor(
                    n_estimators=50, max_depth=5, random_state=42, n_jobs=-1
                )
            else:
                model = LinearRegression()

            model.fit(X, y)
            pred = model.predict(X)

            # featureName -> feature index 매핑 (predict 시 사용)
            name_to_idx: dict[str, int] = {}
            if feature_name_map:
                for feat_name, df_col in feature_name_map.items():
                    if df_col in available_features:
                        name_to_idx[feat_name] = available_features.index(df_col)

            # 학습 결과 저장
            self._models[model_name] = {
                "model": model,
                "features": available_features,
                "target": target_col,
                "name_to_idx": name_to_idx,
            }

            r2 = float(r2_score(y, pred))
            mae = float(mean_absolute_error(y, pred))
            logger.info(
                "모델 학습 완료: %s (R2=%.4f, MAE=%.4f, rows=%d, features=%d)",
                model_name, r2, mae, len(sub), len(available_features),
            )
            return {"r2": r2, "mae": mae}

        except Exception as e:
            logger.warning("Fallback 학습 실패 (%s): %s", model_name, e)
            return {"r2": 0.0, "mae": 0.0}

    def predict(self, model_name: str, input_data: dict[str, float]) -> float | None:
        """
        학습된 모델로 예측.

        input_data의 키는 featureName (예: "lead_time_days")이므로,
        train() 시 저장한 name_to_idx 매핑을 통해 올바른 피처 위치에 값을 넣는다.

        매핑 우선순위:
        1. name_to_idx에서 직접 매칭 (featureName -> index)
        2. df 컬럼명 직접 매칭 (key가 학습 시 컬럼명과 동일)
        3. suffix 매칭 (key가 "__field"의 field 부분)

        Args:
            model_name: 학습된 모델 이름
            input_data: {featureName: value} 딕셔너리

        Returns:
            예측값 (float) 또는 None (모델 미존재/예측 실패 시)
        """
        info = self._models.get(model_name)
        if not info:
            return None

        try:
            n_features = len(info["features"])
            # 기본값: 0.0 (학습 데이터 평균으로 대체하면 더 좋지만, 단순화)
            feature_values = [0.0] * n_features
            name_to_idx = info.get("name_to_idx", {})

            for key, value in input_data.items():
                # 1순위: featureName -> index 매핑
                if key in name_to_idx:
                    feature_values[name_to_idx[key]] = float(value)
                    continue

                # 2순위: df 컬럼명 직접 매칭
                if key in info["features"]:
                    idx = info["features"].index(key)
                    feature_values[idx] = float(value)
                    continue

                # 3순위: suffix 매칭 ("테이블명__필드명"에서 "필드명" 부분)
                for i, feat_col in enumerate(info["features"]):
                    if feat_col.endswith(f"__{key}"):
                        feature_values[i] = float(value)
                        break

            X = np.array([feature_values])
            result = float(info["model"].predict(X)[0])
            return result

        except Exception as e:
            logger.warning(
                "Fallback 예측 실패 (%s): %s, input_keys=%s",
                model_name, e, list(input_data.keys()),
            )
            return None

    @property
    def model_count(self) -> int:
        """학습된 모델 수."""
        return len(self._models)

    def has_model(self, model_name: str) -> bool:
        """특정 모델이 학습되어 있는지 확인."""
        return model_name in self._models

    def clear(self) -> None:
        """모든 학습된 모델 제거."""
        self._models.clear()
