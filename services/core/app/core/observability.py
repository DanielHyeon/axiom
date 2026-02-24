from __future__ import annotations

from collections import defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = defaultdict(float)

    def inc(self, name: str, value: float = 1.0) -> None:
        self._counters[name] += value

    def set_gauge(self, name: str, value: float) -> None:
        self._gauges[name] = value

    def get_counter(self, name: str) -> float:
        return self._counters.get(name, 0.0)

    def get_gauge(self, name: str) -> float:
        return self._gauges.get(name, 0.0)

    def reset(self) -> None:
        self._counters.clear()
        self._gauges.clear()

    def render_prometheus(self) -> str:
        lines = [
            # ── Outbox metrics ──
            "# HELP core_event_outbox_published_total Outbox published events",
            "# TYPE core_event_outbox_published_total counter",
            f"core_event_outbox_published_total {self.get_counter('core_event_outbox_published_total')}",
            "# HELP core_event_outbox_failed_total Outbox publish failures",
            "# TYPE core_event_outbox_failed_total counter",
            f"core_event_outbox_failed_total {self.get_counter('core_event_outbox_failed_total')}",
            "# HELP core_event_outbox_pending Outbox pending events",
            "# TYPE core_event_outbox_pending gauge",
            f"core_event_outbox_pending {self.get_gauge('core_event_outbox_pending')}",
            # ── DLQ stream metrics ──
            "# HELP core_dlq_messages_total Total DLQ moved messages",
            "# TYPE core_dlq_messages_total counter",
            f"core_dlq_messages_total {self.get_counter('core_dlq_messages_total')}",
            "# HELP core_dlq_depth DLQ stream depth",
            "# TYPE core_dlq_depth gauge",
            f"core_dlq_depth {self.get_gauge('core_dlq_depth')}",
            "# HELP core_dlq_reprocess_success_total DLQ reprocess success",
            "# TYPE core_dlq_reprocess_success_total counter",
            f"core_dlq_reprocess_success_total {self.get_counter('core_dlq_reprocess_success_total')}",
            "# HELP core_dlq_reprocess_failed_total DLQ reprocess failures",
            "# TYPE core_dlq_reprocess_failed_total counter",
            f"core_dlq_reprocess_failed_total {self.get_counter('core_dlq_reprocess_failed_total')}",
            # ── DLQ DB metrics (DDD-P3-05) ──
            "# HELP core_dlq_db_unresolved Dead letter events unresolved in DB",
            "# TYPE core_dlq_db_unresolved gauge",
            f"core_dlq_db_unresolved {self.get_gauge('core_dlq_db_unresolved')}",
            "# HELP core_dlq_retry_total Manual DLQ retry count",
            "# TYPE core_dlq_retry_total counter",
            f"core_dlq_retry_total {self.get_counter('core_dlq_retry_total')}",
            "# HELP core_dlq_discard_total Manual DLQ discard count",
            "# TYPE core_dlq_discard_total counter",
            f"core_dlq_discard_total {self.get_counter('core_dlq_discard_total')}",
            # ── Relay lag (DDD-P3-05) ──
            "# HELP core_relay_lag_seconds Outbox to Stream relay lag",
            "# TYPE core_relay_lag_seconds gauge",
            f"core_relay_lag_seconds {self.get_gauge('core_relay_lag_seconds')}",
            # ── Legacy ──
            "# HELP core_legacy_write_violations_total Legacy write policy violations detected",
            "# TYPE core_legacy_write_violations_total counter",
            f"core_legacy_write_violations_total {self.get_counter('core_legacy_write_violations_total')}",
        ]
        return "\n".join(lines)


metrics_registry = MetricsRegistry()
