"""
인과 분석 엔진 (Hybrid Engine)
==============================

KAIR로부터 이식 -- VAR/Granger + 분해형 하이브리드 인과 분석.

관계 타입별 맞는 판정기를 붙이는 하이브리드 인과 분석:
- 동학(시차)형: VAR/Granger 검정
- 분해(정의)형: 로그 분해/기여도 (decomposition)
- VAR 실패(positive definite 등) -> 진단 후 분해형 라우팅 또는 전처리 재시도

사용법:
    engine = CausalAnalysisEngine(significance_level=0.05, max_lag=2)
    edges = engine.analyze(data=df, target_var="kpi_oee")
    scores = engine.calculate_impact_scores(edges)
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.vector_ar.var_model import VAR

# 경고 무시 -- statsmodels FutureWarning이 너무 많이 뜸
warnings.filterwarnings("ignore", category=FutureWarning)
logger = logging.getLogger(__name__)

# 분해형 관계 타입 상수 -- 온톨로지에서 FORMULA, DERIVED_FROM 등이면 분해형
DETERMINISTIC_RELATION_TYPES: frozenset[str] = frozenset({
    "FORMULA", "DERIVED_FROM", "AGGREGATES", "AGGREGATE", "COMPOSED_OF",
})


@dataclass(frozen=True)
class CausalEdge:
    """
    발견된 인과관계 엣지.

    source: 원인 변수 (node_id:field 또는 컬럼명)
    target: 결과 변수
    method: 'granger' | 'correlation' | 'decomposition'
    strength: 관계 강도 (0~1)
    p_value: 통계적 유의성
    lag: 시차 (Granger에서만 >0)
    direction: 'positive' | 'negative'
    """
    source: str
    target: str
    method: str
    strength: float
    p_value: float
    lag: int = 0
    direction: str = "positive"

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리로 변환 (API 응답용)"""
        return {
            "source": self.source,
            "target": self.target,
            "method": self.method,
            "strength": round(self.strength, 4),
            "p_value": round(self.p_value, 6),
            "lag": self.lag,
            "direction": self.direction,
        }


def diagnose_collinearity(
    data: pd.DataFrame,
    target_var: str,
    cause_vars: list[str],
    near_constant_threshold: float = 1e-10,
    high_corr_threshold: float = 0.999,
) -> dict[str, Any]:
    """
    공선성/종속성 진단 -- VAR 실패 시 분해형 라우팅 판단 근거.

    세 가지를 체크한다:
    1. 거의 상수인 열이 있는가? (분산이 아주 작은 열)
    2. 거의 동일한 열 쌍이 있는가? (상관계수 0.999 이상)
    3. 곱셈 근사가 가능한가? (target ~ product of causes -> log R-squared >= 0.99)

    하나라도 True면 is_likely_deterministic = True -> 분해형 라우팅
    """
    numeric = data.select_dtypes(include=[np.number])
    # 타겟이 숫자형이 아니면 진단 불가
    if target_var not in numeric.columns:
        return {
            "near_constant_cols": [],
            "high_corr_pairs": [],
            "multiplicative_fit_r2": 0.0,
            "is_likely_deterministic": False,
        }
    cause_vars = [c for c in cause_vars if c in numeric.columns]
    if not cause_vars:
        return {
            "near_constant_cols": [],
            "high_corr_pairs": [],
            "multiplicative_fit_r2": 0.0,
            "is_likely_deterministic": False,
        }

    # (1) 거의 상수인 열 찾기
    near_constant_cols: list[str] = []
    for col in [target_var] + cause_vars:
        if col not in numeric.columns:
            continue
        var = numeric[col].var()
        if pd.isna(var) or var < near_constant_threshold:
            near_constant_cols.append(col)

    # (2) 거의 동일한 열 쌍 찾기
    high_corr_pairs: list[tuple[str, str]] = []
    for i, a in enumerate(cause_vars):
        for b in cause_vars[i + 1:] + [target_var]:
            if a not in numeric.columns or b not in numeric.columns:
                continue
            r = numeric[a].corr(numeric[b])
            if not pd.isna(r) and abs(r) >= high_corr_threshold:
                high_corr_pairs.append((a, b))

    # (3) 곱셈 근사 검정: log(target) ~ sum(log(causes)) OLS 피팅
    multiplicative_fit_r2 = 0.0
    try:
        y = numeric[target_var].replace(0, np.nan).dropna()
        if len(y) >= 3:
            log_y = np.log(y)
            log_causes = numeric[cause_vars].replace(0, np.nan)
            log_causes = np.log(log_causes)
            log_causes = log_causes.dropna(how="all")
            common = log_y.index.intersection(log_causes.index)
            if len(common) >= 3:
                log_y = log_y.loc[common]
                log_causes = log_causes.loc[common].ffill().bfill()
                if not log_causes.isna().all().any():
                    # OLS: log(target) = intercept + sum(coef_i * log(cause_i))
                    X = np.column_stack([np.ones(len(log_causes)), log_causes.values])
                    y_val = log_y.values.astype(float)
                    coef, _, _, _ = np.linalg.lstsq(X, y_val, rcond=None)
                    pred = X @ coef
                    ss_res = ((y_val - pred) ** 2).sum()
                    ss_tot = ((y_val - y_val.mean()) ** 2).sum()
                    if ss_tot > 0:
                        multiplicative_fit_r2 = float(1 - ss_res / ss_tot)
    except Exception:
        pass

    # 하나라도 True면 분해형 가능성 큼
    is_likely_deterministic = (
        len(near_constant_cols) > 0
        or len(high_corr_pairs) > 0
        or multiplicative_fit_r2 >= 0.99
    )

    return {
        "near_constant_cols": near_constant_cols,
        "high_corr_pairs": high_corr_pairs,
        "multiplicative_fit_r2": multiplicative_fit_r2,
        "is_likely_deterministic": is_likely_deterministic,
    }


# ── 1b) 통합 분해형 기여도 함수 ──
# 기존 _decomposition_contribution_multiplicative / _additive를 하나로 통합.
# mode="multiplicative" → np.log 변환 + replace(0, np.nan)
# mode="additive" → identity 변환 (변환 없음)

def _decomposition_contribution(
    data: pd.DataFrame,
    target_var: str,
    source_vars: list[str],
    *,
    mode: str = "multiplicative",
) -> list[CausalEdge]:
    """
    분해형 기여도 계산 (곱셈/덧셈 통합).

    곱셈 분해: target ~ product(sources) → log 변환 후 기여도 계산
    덧셈 분해: target ~ sum(sources) → 변환 없이 기여도 계산

    기여도 = |delta(변환된 source_i)| / |delta(변환된 target)|
    """
    edges: list[CausalEdge] = []
    numeric = data.select_dtypes(include=[np.number])
    if target_var not in numeric.columns:
        return edges
    source_vars = [c for c in source_vars if c in numeric.columns]
    if not source_vars:
        return edges

    # 곱셈 모드: 0을 NaN으로 치환 (log(0) 방지)
    if mode == "multiplicative":
        df = numeric[[target_var] + source_vars].replace(0, np.nan).dropna(how="all")
    else:
        df = numeric[[target_var] + source_vars].dropna(how="all")

    if len(df) < 2:
        return edges

    try:
        # 곱셈 모드: log 변환 / 덧셈 모드: identity
        if mode == "multiplicative":
            transformed_target = np.log(df[target_var])
            transformed_sources = np.log(df[source_vars])
        else:
            transformed_target = df[target_var]
            transformed_sources = df[source_vars]

        # 차분 (변화량) 계산
        d_target = transformed_target.diff().dropna()
        d_sources = transformed_sources.diff().dropna()
        common = d_target.index.intersection(d_sources.index)
        if len(common) < 1:
            return edges
        d_target = d_target.loc[common]
        d_sources = d_sources.loc[common]

        # 총 변화량 (0 나누기 방지)
        total_abs = d_target.abs().sum()
        if total_abs < 1e-20:
            total_abs = 1.0

        # 각 소스 변수별 기여도 계산
        for col in source_vars:
            contrib = d_sources[col].abs().sum()
            ratio = contrib / total_abs
            ratio = min(1.0, max(0.0, float(ratio)))
            direction = "positive" if d_sources[col].corr(d_target) >= 0 else "negative"
            edges.append(CausalEdge(
                source=col,
                target=target_var,
                method="decomposition",
                strength=ratio,
                p_value=0.0,
                lag=0,
                direction=direction,
            ))
    except (ValueError, TypeError, KeyError) as e:
        label = "곱셈" if mode == "multiplicative" else "덧셈"
        logger.warning("%s 분해 실패: %s", label, e)
    return edges


# ── 하위 호환 래퍼 (기존 코드가 직접 호출할 경우 대비) ──

def _decomposition_contribution_multiplicative(
    data: pd.DataFrame,
    target_var: str,
    source_vars: list[str],
) -> list[CausalEdge]:
    """곱셈 분해 래퍼 — _decomposition_contribution(mode='multiplicative') 호출."""
    return _decomposition_contribution(data, target_var, source_vars, mode="multiplicative")


def _decomposition_contribution_additive(
    data: pd.DataFrame,
    target_var: str,
    source_vars: list[str],
) -> list[CausalEdge]:
    """덧셈 분해 래퍼 — _decomposition_contribution(mode='additive') 호출."""
    return _decomposition_contribution(data, target_var, source_vars, mode="additive")


class CausalAnalysisEngine:
    """
    하이브리드 인과 분석 엔진.

    관계 타입별 맞는 판정기를 붙인다:
    - 동학(시차)형: VAR/Granger 검정
    - 분해(정의)형: 로그/덧셈 기여도 (decomposition)
    - VAR 실패 시 진단 -> 분해형 라우팅 또는 전처리 재시도
    """

    def __init__(
        self,
        significance_level: float = 0.05,
        min_correlation: float = 0.3,
        max_lag: int = 2,
    ) -> None:
        self.significance_level = significance_level
        self.min_correlation = min_correlation
        self.max_lag = max_lag

    # ── 1a) Pearson 상관 보강 (중복 제거) ──
    # VAR 성공 후 + VAR 실패 후 동일 코드가 2번 반복되던 것을 하나로 추출.

    def _correlate_fallback(
        self,
        numeric_data: pd.DataFrame,
        target_var: str,
        cause_vars: list[str],
        existing_edges: list[CausalEdge],
    ) -> list[CausalEdge]:
        """Granger에서 유의하지 않은 변수에 Pearson 상관을 보강한다."""
        new_edges: list[CausalEdge] = []
        for cause_var in cause_vars:
            # 이미 엣지가 있는 변수는 건너뜀
            if any(e.source == cause_var for e in existing_edges):
                continue
            try:
                # 리뷰 #7: 양쪽 공통 dropna (길이 불일치 방지)
                pair = numeric_data[[cause_var, target_var]].dropna()
                if len(pair) < 3:
                    continue
                corr, p_value = stats.pearsonr(pair[cause_var], pair[target_var])
                if abs(corr) >= self.min_correlation and p_value < self.significance_level:
                    direction = "positive" if corr > 0 else "negative"
                    new_edges.append(CausalEdge(
                        source=cause_var,
                        target=target_var,
                        method="correlation",
                        strength=abs(corr),
                        p_value=p_value,
                        lag=0,
                        direction=direction,
                    ))
            except (ValueError, TypeError) as e:
                logger.debug("Pearson 상관 계산 실패 (%s → %s): %s", cause_var, target_var, e)
                continue
        return new_edges

    # ── 1c) 곱셈 시도 → 실패 시 덧셈 패턴 추출 ──
    # "곱셈 분해 시도 → 결과 없으면 덧셈 분해" 패턴이 3회 반복되던 것을 하나로 추출.

    @staticmethod
    def _try_decomposition(
        data: pd.DataFrame,
        target_var: str,
        source_vars: list[str],
    ) -> list[CausalEdge]:
        """곱셈 분해를 시도하고, 결과가 없으면 덧셈 분해를 시도한다."""
        edges = _decomposition_contribution(data, target_var, source_vars, mode="multiplicative")
        if not edges:
            edges = _decomposition_contribution(data, target_var, source_vars, mode="additive")
        return edges

    def analyze(
        self,
        data: pd.DataFrame,
        target_var: str,
        max_lag: int | None = None,
        relation_hints: dict[tuple[str, str], str] | None = None,
    ) -> list[CausalEdge]:
        """
        핵심 진입점 -- 하이브리드 인과 분석 실행.

        흐름:
        1. relation_hints에서 deterministic 소스를 분류
        2. 나머지는 VAR/Granger 시도
        3. VAR 실패 시 진단 -> 분해형 라우팅 or 상관 보강
        4. deterministic 소스는 별도 분해형 처리
        5. 결과가 비었으면 전체에 대해 분해형 최종 시도
        """
        if max_lag is None:
            max_lag = self.max_lag
        relation_hints = relation_hints or {}

        # 숫자형 컬럼만 사용
        numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
        if target_var not in numeric_cols:
            raise ValueError(f"타겟 변수 '{target_var}'가 숫자형 데이터에 없습니다.")
        cause_vars = [c for c in numeric_cols if c != target_var]
        if len(cause_vars) < 1:
            raise ValueError("인과 후보 변수가 없습니다.")

        numeric_data = data[numeric_cols].dropna()

        # 최소 데이터 행 수 체크
        min_required = max_lag * 2 + 10
        if len(numeric_data) < min_required:
            warnings.warn(
                f"데이터가 충분하지 않습니다. 최소 {min_required}행 권장 "
                f"(현재: {len(numeric_data)}행). "
                "분해형 또는 상관만 사용될 수 있습니다.",
                UserWarning,
                stacklevel=2,
            )

        # 컬럼명에서 node_id 추출 (node_id:field -> node_id)
        def _col_to_node_id(col: str) -> str:
            return col.split(":")[0] if ":" in col else col

        target_node_id = _col_to_node_id(target_var)

        # deterministic 소스 분류
        deterministic_sources = [
            c for c in cause_vars
            if relation_hints.get((_col_to_node_id(c), target_node_id)) == "deterministic"
            or relation_hints.get((c, target_var)) == "deterministic"
        ]

        # deterministic이 아닌 cause_vars만 Granger/상관 분석 대상
        dynamic_causes = [
            c for c in cause_vars
            if c not in deterministic_sources
        ]

        edges: list[CausalEdge] = []
        try_var = len(deterministic_sources) != len(cause_vars)

        if try_var:
            try:
                # VAR 모델 피팅 (AIC 기반 최적 시차 선택)
                var_model = VAR(numeric_data)
                var_results = var_model.fit(maxlags=max_lag, ic="aic")
                optimal_lag = var_results.k_ar

                # 각 cause_var에 대해 Granger 검정
                for cause_var in dynamic_causes:
                    try:
                        test_data = numeric_data[[target_var, cause_var]]
                        if len(test_data) < optimal_lag + 10:
                            continue
                        result = grangercausalitytests(
                            test_data,
                            maxlag=min(optimal_lag, max_lag),
                            verbose=False,
                        )
                        min_p_value = 1.0
                        best_lag = 1
                        best_f_stat = 0.0
                        for lag in range(1, min(optimal_lag, max_lag) + 1):
                            if lag in result:
                                f_stat = result[lag][0]["ssr_ftest"][0]
                                p_value = result[lag][0]["ssr_ftest"][1]
                                if p_value < min_p_value:
                                    min_p_value = p_value
                                    best_lag = lag
                                    best_f_stat = f_stat
                        if min_p_value < self.significance_level:
                            corr = numeric_data[cause_var].corr(numeric_data[target_var])
                            direction = "positive" if corr > 0 else "negative"
                            strength = min(1.0, best_f_stat / 20)
                            edges.append(CausalEdge(
                                source=cause_var,
                                target=target_var,
                                method="granger",
                                strength=strength,
                                p_value=min_p_value,
                                lag=best_lag,
                                direction=direction,
                            ))
                    except (ValueError, np.linalg.LinAlgError) as e:
                        logger.debug("Granger 검정 실패 (%s → %s): %s", cause_var, target_var, e)
                        continue

                # Granger에서 유의하지 않은 변수 -> Pearson 상관 보강
                corr_edges = self._correlate_fallback(
                    numeric_data, target_var, dynamic_causes, edges,
                )
                edges.extend(corr_edges)

            except (ValueError, np.linalg.LinAlgError) as e:
                # 1d) VAR/Granger 관련 예외를 구체적 타입으로 처리
                err_msg = str(e).lower()
                logger.info("VAR 피팅 실패 (분류 신호로 사용): %s", e)
                diag = diagnose_collinearity(numeric_data, target_var, cause_vars)
                if diag["is_likely_deterministic"]:
                    logger.info("진단: 분해형 관계 가능성 큼 -> decomposition 라우팅")
                    edges.extend(self._try_decomposition(numeric_data, target_var, cause_vars))
                else:
                    if "positive definite" in err_msg or "leading minor" in err_msg:
                        logger.info("VAR 실패했으나 진단상 분해형 아님 -> 상관만 보강")
                    corr_edges = self._correlate_fallback(
                        numeric_data, target_var, cause_vars, edges,
                    )
                    edges.extend(corr_edges)

        # deterministic 소스 별도 처리 (곱셈 -> 덧셈 순서)
        if deterministic_sources:
            decomp_edges = self._try_decomposition(
                numeric_data, target_var, deterministic_sources,
            )
            for e in decomp_edges:
                if not any(x.source == e.source and x.target == e.target for x in edges):
                    edges.append(e)

        # 결과가 비었으면 -> 전체에 대해 분해형 최종 시도
        if not edges and try_var:
            edges.extend(self._try_decomposition(numeric_data, target_var, cause_vars))

        edges.sort(key=lambda e: e.strength, reverse=True)
        return edges

    def fit_var_model(
        self,
        data: pd.DataFrame,
        max_lag: int | None = None,
    ) -> Any:
        """VAR 모델 단독 피팅."""
        if max_lag is None:
            max_lag = self.max_lag
        numeric_data = data.select_dtypes(include=[np.number]).dropna()
        if len(numeric_data) < max_lag * 2 + 10:
            raise ValueError(f"데이터가 충분하지 않습니다. 최소 {max_lag * 2 + 10}행 필요")
        var_model = VAR(numeric_data)
        return var_model.fit(maxlags=max_lag, ic="aic")

    def test_granger_causality(
        self,
        var_results: Any,
        cause_var: str,
        effect_var: str,
    ) -> dict[str, Any]:
        """Granger 인과 검정 단독 실행."""
        try:
            test_result = var_results.test_causality(effect_var, cause_var, kind="f")
            return {
                "f_statistic": test_result.test_statistic,
                "p_value": test_result.pvalue,
                "is_significant": test_result.pvalue < self.significance_level,
            }
        except (ValueError, np.linalg.LinAlgError, AttributeError):
            endog = var_results.model.endog
            var_names = var_results.model.names
            if cause_var not in var_names or effect_var not in var_names:
                raise ValueError(f"변수 '{cause_var}' 또는 '{effect_var}'가 모델에 없습니다.")
            cause_idx = var_names.index(cause_var)
            effect_idx = var_names.index(effect_var)
            test_data = pd.DataFrame({
                effect_var: endog[:, effect_idx],
                cause_var: endog[:, cause_idx],
            })
            result = grangercausalitytests(
                test_data, maxlag=var_results.k_ar, verbose=False,
            )
            min_p = 1.0
            best_lag = 1
            best_f_stat = 0.0
            for lag in range(1, var_results.k_ar + 1):
                if lag in result:
                    f_stat = result[lag][0]["ssr_ftest"][0]
                    p_value = result[lag][0]["ssr_ftest"][1]
                    if p_value < min_p:
                        min_p = p_value
                        best_lag = lag
                        best_f_stat = f_stat
            return {
                "f_statistic": best_f_stat,
                "p_value": min_p,
                "is_significant": min_p < self.significance_level,
                "lag": best_lag,
            }

    def calculate_impact_scores(
        self,
        edges: list[CausalEdge],
    ) -> dict[str, float]:
        """엣지 목록 -> 변수별 영향도 점수 (0~1 정규화)."""
        impact_scores: dict[str, float] = {}
        for edge in edges:
            source = edge.source
            confidence_weight = 1.0 - edge.p_value
            impact = edge.strength * confidence_weight
            if source not in impact_scores:
                impact_scores[source] = 0.0
            impact_scores[source] += impact

        if impact_scores:
            max_score = max(impact_scores.values())
            if max_score > 0:
                impact_scores = {k: round(v / max_score, 4) for k, v in impact_scores.items()}

        return impact_scores
