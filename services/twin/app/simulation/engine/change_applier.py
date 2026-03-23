"""ChangeSet 적용기 — 가정 패치를 baseline 상태에 적용한다."""
from __future__ import annotations

from typing import Any


def apply_change_sets(
    baseline_metrics: dict[str, float],
    change_sets: list[dict[str, Any]],
    coefficients: dict[str, dict[str, float]],
) -> dict[str, float]:
    """baseline 메트릭에 change_set을 순차 적용하여 scenario 메트릭을 반환한다.

    각 change_set의 patch_json에서 delta 값을 추출하고,
    해당 change_type의 계수를 곱해 메트릭 변화를 계산한다.
    """
    result = dict(baseline_metrics)

    for cs in change_sets:
        change_type = cs.get("change_type", "")
        patch = cs.get("patch_json", {})
        delta = patch.get("delta", 0.0)

        effects = coefficients.get(change_type, {})
        for metric, coeff in effects.items():
            if metric in result:
                result[metric] = result[metric] + (delta * coeff)

    return result
