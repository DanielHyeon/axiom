from __future__ import annotations

from threading import Lock
from typing import Mapping


class MetricsService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = {
            "weaver_request_guard_rate_limited_total": 0,
            "weaver_request_guard_idempotency_in_progress_total": 0,
            "weaver_request_guard_idempotency_mismatch_total": 0,
        }
        self._labeled_counters: dict[tuple[str, tuple[tuple[str, str], ...]], int] = {}

    def clear(self) -> None:
        with self._lock:
            for key in self._counters:
                self._counters[key] = 0
            self._labeled_counters.clear()

    def inc(self, name: str, amount: int = 1, labels: Mapping[str, str] | None = None) -> None:
        with self._lock:
            if labels:
                normalized = tuple(sorted((str(k), str(v)) for k, v in labels.items()))
                key = (name, normalized)
                self._labeled_counters[key] = int(self._labeled_counters.get(key, 0)) + amount
            else:
                self._counters[name] = int(self._counters.get(name, 0)) + amount

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            result = dict(self._counters)
            for (name, labels), value in self._labeled_counters.items():
                suffix = ",".join(f"{k}={v}" for k, v in labels)
                result[f"{name}{{{suffix}}}"] = value
            return result

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

    @classmethod
    def _labels_text(cls, labels: tuple[tuple[str, str], ...]) -> str:
        return ",".join(f'{k}="{cls._escape(v)}"' for k, v in labels)

    def render_prometheus(self) -> str:
        rows: list[str] = []
        with self._lock:
            names = sorted(set(self._counters.keys()) | {k[0] for k in self._labeled_counters.keys()})
            for name in names:
                rows.append(f"# TYPE {name} counter")
                base = int(self._counters.get(name, 0))
                rows.append(f"{name} {base}")
                labeled_rows = sorted((labels, value) for (metric, labels), value in self._labeled_counters.items() if metric == name)
                for labels, value in labeled_rows:
                    rows.append(f"{name}{{{self._labels_text(labels)}}} {value}")
        return "\n".join(rows) + "\n"


metrics_service = MetricsService()
