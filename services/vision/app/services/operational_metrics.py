"""
운영 메트릭 수집기.

VisionRuntime에서 분리된 근본 원인 분석 API 호출 메트릭 수집/렌더링 담당 클래스.
"""
from __future__ import annotations

from typing import Any


class OperationalMetricsCollector:
    """
    근본 원인 분석 API의 호출 횟수, 성공/실패, 레이턴시 등 운영 메트릭을 수집하는 클래스.

    Prometheus 포맷 렌더링도 지원한다.
    """

    def __init__(self) -> None:
        self._metrics: dict[str, Any] = {}
        self.reset()

    def reset(self) -> None:
        """모든 메트릭 초기화 (서비스 재시작/테스트 시 호출)."""
        self._metrics = {
            "calls_total": 0,
            "success_total": 0,
            "error_total": 0,
            "latency_ms_total": 0.0,
            "operations": {},
        }

    def record_call(self, operation: str, success: bool, latency_ms: float) -> None:
        """API 호출 1건의 메트릭을 기록."""
        metrics = self._metrics
        metrics["calls_total"] += 1
        metrics["latency_ms_total"] += max(latency_ms, 0.0)
        if success:
            metrics["success_total"] += 1
        else:
            metrics["error_total"] += 1

        op = metrics["operations"].setdefault(
            operation,
            {"calls_total": 0, "success_total": 0, "error_total": 0, "latency_ms_total": 0.0},
        )
        op["calls_total"] += 1
        op["latency_ms_total"] += max(latency_ms, 0.0)
        if success:
            op["success_total"] += 1
        else:
            op["error_total"] += 1

    def get_operational_metrics(self) -> dict[str, Any]:
        """현재 수집된 운영 메트릭 스냅샷 반환."""
        metrics = self._metrics
        calls_total = int(metrics["calls_total"])
        error_total = int(metrics["error_total"])
        avg_latency_ms = (
            0.0 if calls_total == 0 else round(float(metrics["latency_ms_total"]) / calls_total, 3)
        )
        failure_rate = 0.0 if calls_total == 0 else round(error_total / calls_total, 6)
        operations: dict[str, Any] = {}
        for name, item in metrics["operations"].items():
            op_calls = int(item["calls_total"])
            operations[name] = {
                "calls_total": op_calls,
                "error_total": int(item["error_total"]),
                "avg_latency_ms": (
                    0.0 if op_calls == 0 else round(float(item["latency_ms_total"]) / op_calls, 3)
                ),
            }
        return {
            "calls_total": calls_total,
            "success_total": int(metrics["success_total"]),
            "error_total": error_total,
            "failure_rate": failure_rate,
            "avg_latency_ms": avg_latency_ms,
            "operations": operations,
        }

    def render_prometheus(self) -> str:
        """Prometheus 텍스트 포맷으로 메트릭 렌더링."""
        snapshot = self.get_operational_metrics()
        lines = [
            "# HELP vision_root_cause_calls_total Total root cause API calls",
            "# TYPE vision_root_cause_calls_total counter",
            f"vision_root_cause_calls_total {snapshot['calls_total']}",
            "# HELP vision_root_cause_errors_total Total root cause API errors",
            "# TYPE vision_root_cause_errors_total counter",
            f"vision_root_cause_errors_total {snapshot['error_total']}",
            "# HELP vision_root_cause_failure_rate Root cause API failure rate",
            "# TYPE vision_root_cause_failure_rate gauge",
            f"vision_root_cause_failure_rate {snapshot['failure_rate']}",
            "# HELP vision_root_cause_avg_latency_ms Average root cause API latency milliseconds",
            "# TYPE vision_root_cause_avg_latency_ms gauge",
            f"vision_root_cause_avg_latency_ms {snapshot['avg_latency_ms']}",
        ]
        for op_name, op in snapshot["operations"].items():
            lines.append(
                f'vision_root_cause_operation_calls_total{{operation="{op_name}"}} {op["calls_total"]}'
            )
            lines.append(
                f'vision_root_cause_operation_errors_total{{operation="{op_name}"}} {op["error_total"]}'
            )
            lines.append(
                f'vision_root_cause_operation_avg_latency_ms{{operation="{op_name}"}} {op["avg_latency_ms"]}'
            )
        return "\n".join(lines) + "\n"
