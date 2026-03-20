from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class FeatureSpec:
    variable: str
    label: str
    baseline: float
    minimum: float
    maximum: float
    weight: float
    high_is_risk: bool
    threshold: float | None
    causal_chain: tuple[str, ...]


FEATURE_SPECS: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        variable="debt_ratio",
        label="부채비율",
        baseline=1.0,
        minimum=0.7,
        maximum=1.9,
        weight=1.25,
        high_is_risk=True,
        threshold=1.0,
        causal_chain=("차입 증가", "이자비용 상승", "현금흐름 악화"),
    ),
    FeatureSpec(
        variable="ebitda",
        label="EBITDA",
        baseline=1_200_000_000.0,
        minimum=400_000_000.0,
        maximum=1_800_000_000.0,
        weight=1.1,
        high_is_risk=False,
        threshold=1_200_000_000.0,
        causal_chain=("원가 상승", "마진 축소", "상환여력 저하"),
    ),
    FeatureSpec(
        variable="interest_rate_env",
        label="금리 환경",
        baseline=3.7,
        minimum=2.5,
        maximum=7.0,
        weight=0.85,
        high_is_risk=True,
        threshold=None,
        causal_chain=("기준금리 상승", "변동금리 부담 증가"),
    ),
    FeatureSpec(
        variable="operating_margin",
        label="영업이익률",
        baseline=0.14,
        minimum=0.04,
        maximum=0.24,
        weight=0.9,
        high_is_risk=False,
        threshold=0.10,
        causal_chain=("매출원가 증가", "수익성 저하", "현금창출력 약화"),
    ),
    FeatureSpec(
        variable="inventory_turnover",
        label="재고회전율",
        baseline=6.0,
        minimum=2.0,
        maximum=9.0,
        weight=0.6,
        high_is_risk=False,
        threshold=4.5,
        causal_chain=("재고 누적", "운전자본 부담", "유동성 압박"),
    ),
)


def _seed_from(case_id: str, payload: dict[str, Any]) -> int:
    key = f"{case_id}|{payload.get('analysis_depth','full')}|{payload.get('max_root_causes',5)}|{payload.get('language','ko')}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _unit(seed: int, index: int) -> float:
    mixed = (seed ^ (index * 0x9E3779B97F4A7C15)) & ((1 << 64) - 1)
    return (mixed % 10_000) / 9_999.0


def _risk_ratio(spec: FeatureSpec, actual: float) -> float:
    baseline = max(abs(spec.baseline), 1e-9)
    if spec.high_is_risk:
        return max((actual - spec.baseline) / baseline, 0.0)
    return max((spec.baseline - actual) / baseline, 0.0)


def _description(spec: FeatureSpec, actual: float) -> str:
    if spec.high_is_risk:
        return f"{spec.label}이(가) 기준치를 상회해 리스크를 키웠습니다."
    return f"{spec.label} 저하가 실패 확률 증가에 영향을 주었습니다."


def _root_cause_from_causal_edges(
    case_id: str,
    payload: dict[str, Any],
    causal_edges: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    인과 분석 엣지 기반 근본원인 랭킹.

    각 엣지의 strength, p_value, method를 조합하여
    impact_score를 계산하고 순위를 매긴다.
    """
    max_root_causes = min(max(int(payload.get("max_root_causes", 5)), 1), 10)

    # method별 가중치: granger > decomposition > correlation
    method_weight = {"granger": 1.2, "decomposition": 1.0, "correlation": 0.8}

    # 엣지별 impact 계산
    scored: list[dict[str, Any]] = []
    for edge in causal_edges:
        strength = float(edge.get("strength", 0.0))
        p_value = float(edge.get("p_value", 1.0))
        confidence = 1.0 - p_value
        weight = method_weight.get(edge.get("method", ""), 0.8)
        impact = strength * confidence * weight

        scored.append({
            "variable": edge["source"],
            "variable_label": edge["source"],
            "shap_value": round(impact, 4),
            "contribution_pct": 0.0,  # 아래에서 계산
            "actual_value": strength,
            "critical_threshold": None,
            "description": f"{edge['source']} -> {edge['target']} ({edge.get('method', 'unknown')})",
            "causal_chain": [edge["source"], edge.get("method", ""), edge["target"]],
            "confidence": round(confidence, 3),
            "direction": edge.get("direction", "positive"),
            "lag": edge.get("lag", 0),
            "method": edge.get("method", "unknown"),
            "high_is_risk": True,
        })

    scored.sort(key=lambda x: x["shap_value"], reverse=True)
    selected = scored[:max_root_causes]

    # contribution_pct 계산
    total_shap = sum(item["shap_value"] for item in selected) or 1.0
    root_causes: list[dict[str, Any]] = []
    for rank, item in enumerate(selected, 1):
        item["rank"] = rank
        item["contribution_pct"] = round((item["shap_value"] / total_shap) * 100.0, 2)
        root_causes.append(item)

    # 전체 예측 확률 (인과 분석 기반)
    overall_confidence = round(
        sum(item["confidence"] for item in root_causes) / max(len(root_causes), 1), 3
    )
    predicted_failure_probability = round(
        _clamp(0.3 + total_shap * 0.4, 0.3, 0.95), 3
    )

    return {
        "root_causes": root_causes,
        "overall_confidence": overall_confidence,
        "predicted_failure_probability": predicted_failure_probability,
        "confidence_basis": {
            "model": "causal-analysis-engine-v1",
            "edge_count": len(causal_edges),
            "top_k": len(root_causes),
        },
        "explanation": "VAR/Granger + 분해형 하이브리드 인과 분석 기반 근본원인 산출",
    }


def run_root_cause_engine(
    case_id: str,
    payload: dict[str, Any],
    causal_edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    근본원인 분석 엔진.

    causal_edges가 주어지면 실제 인과 분석 결과 기반으로 근본원인 산출.
    없으면 기존 FeatureSpec 기반 결정론적 엔진 사용 (하위 호환).
    """
    # 인과 분석 결과가 있으면 새 엔진 사용
    if causal_edges:
        return _root_cause_from_causal_edges(case_id, payload, causal_edges)

    # 기존 레거시 로직
    seed = _seed_from(case_id, payload)
    max_root_causes = min(max(int(payload.get("max_root_causes", 5)), 1), 10)
    scored: list[dict[str, Any]] = []
    for idx, spec in enumerate(FEATURE_SPECS, start=1):
        u = _unit(seed, idx)
        actual = spec.minimum + ((spec.maximum - spec.minimum) * u)
        risk = _risk_ratio(spec, actual)
        shap = max(0.0, spec.weight * (0.03 + risk))
        scored.append(
            {
                "variable": spec.variable,
                "variable_label": spec.label,
                "actual_value": round(actual, 4 if actual < 10 else 2),
                "critical_threshold": spec.threshold,
                "causal_chain": list(spec.causal_chain),
                "risk_ratio": risk,
                "shap_value": shap,
                "description": _description(spec, actual),
                "high_is_risk": spec.high_is_risk,
            }
        )

    scored.sort(key=lambda item: item["shap_value"], reverse=True)
    selected = scored[:max_root_causes]
    total_shap = sum(item["shap_value"] for item in selected) or 1.0
    root_causes = []
    for rank, item in enumerate(selected, start=1):
        contribution_pct = (item["shap_value"] / total_shap) * 100.0
        confidence = _clamp(0.62 + (item["risk_ratio"] * 0.28), 0.62, 0.95)
        root_causes.append(
            {
                "rank": rank,
                "variable": item["variable"],
                "variable_label": item["variable_label"],
                "shap_value": round(item["shap_value"], 4),
                "contribution_pct": round(contribution_pct, 2),
                "actual_value": item["actual_value"],
                "critical_threshold": item["critical_threshold"],
                "description": item["description"],
                "causal_chain": item["causal_chain"],
                "confidence": round(confidence, 3),
                "direction": "positive",
                "high_is_risk": item["high_is_risk"],
            }
        )

    predicted_failure_probability = _clamp(0.42 + (sum(item["shap_value"] for item in selected) * 0.18), 0.42, 0.96)
    confidence_basis = {
        "model": "deterministic-risk-engine-v1",
        "deterministic_seed": seed % 100_000,
        "feature_count": len(FEATURE_SPECS),
        "top_k": len(root_causes),
    }
    explanation = "핵심 근본원인은 상위 위험지표의 결합 효과로 산출되었습니다."
    return {
        "root_causes": root_causes,
        "overall_confidence": round(_clamp(0.65 + (predicted_failure_probability * 0.25), 0.65, 0.95), 3),
        "predicted_failure_probability": round(predicted_failure_probability, 3),
        "confidence_basis": confidence_basis,
        "explanation": explanation,
    }


def run_counterfactual_engine(
    analysis: dict[str, Any],
    variable: str,
    actual_value: float,
    counterfactual_value: float,
) -> dict[str, Any]:
    root_causes = analysis.get("root_causes") or []
    selected = next((item for item in root_causes if item.get("variable") == variable), None)
    if selected is None:
        sensitivity = 0.12
        high_is_risk = True
    else:
        sensitivity = max(0.08, float(selected.get("contribution_pct", 0.0)) / 100.0)
        high_is_risk = bool(selected.get("high_is_risk", True))

    denominator = max(abs(actual_value), 1e-6)
    if high_is_risk:
        directional_change = (actual_value - counterfactual_value) / denominator
    else:
        directional_change = (counterfactual_value - actual_value) / denominator

    impact = _clamp(directional_change * sensitivity, -0.65, 0.65)
    before = float(analysis.get("predicted_failure_probability", 0.78))
    after = _clamp(before - impact, 0.01, 0.99)
    return {
        "estimated_failure_probability_before": round(before, 3),
        "estimated_failure_probability_after": round(after, 3),
        "risk_reduction_pct": round((before - after) * 100.0, 2),
        "confidence_basis": {
            "method": "variable-sensitivity-table-v1",
            "variable": variable,
            "sensitivity": round(sensitivity, 4),
            "directional_change": round(directional_change, 4),
        },
    }
