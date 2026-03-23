"""Diff 계산기 — baseline vs scenario 메트릭 비교."""
from __future__ import annotations

from typing import Any


def calculate_diff(
    baseline: dict[str, float],
    scenario: dict[str, float],
) -> dict[str, Any]:
    """baseline과 scenario 메트릭의 차이를 계산한다.

    반환:
        {metric: {baseline, scenario, delta, delta_pct}}
    """
    diff: dict[str, Any] = {}

    all_metrics = set(baseline.keys()) | set(scenario.keys())
    for metric in sorted(all_metrics):
        b = baseline.get(metric, 0.0)
        s = scenario.get(metric, 0.0)
        delta = s - b
        delta_pct = (delta / b * 100) if b != 0 else 0.0

        diff[metric] = {
            "baseline": round(b, 4),
            "scenario": round(s, 4),
            "delta": round(delta, 4),
            "delta_pct": round(delta_pct, 2),
        }

    return diff
