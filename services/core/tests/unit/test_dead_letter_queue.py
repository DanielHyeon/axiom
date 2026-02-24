"""DDD-P3-05: Unit tests for Dead Letter Queue model and observability metrics.

Tests DLQ model fields, metrics registry P3-05 additions.
"""
import pytest

from app.core.observability import MetricsRegistry


class TestMetricsRegistryP305:
    """Test P3-05 metric additions."""

    def test_dlq_db_unresolved_gauge(self):
        m = MetricsRegistry()
        m.set_gauge("core_dlq_db_unresolved", 5.0)
        assert m.get_gauge("core_dlq_db_unresolved") == 5.0

    def test_dlq_retry_counter(self):
        m = MetricsRegistry()
        m.inc("core_dlq_retry_total")
        m.inc("core_dlq_retry_total")
        assert m.get_counter("core_dlq_retry_total") == 2.0

    def test_dlq_discard_counter(self):
        m = MetricsRegistry()
        m.inc("core_dlq_discard_total")
        assert m.get_counter("core_dlq_discard_total") == 1.0

    def test_relay_lag_gauge(self):
        m = MetricsRegistry()
        m.set_gauge("core_relay_lag_seconds", 1.5)
        assert m.get_gauge("core_relay_lag_seconds") == 1.5

    def test_prometheus_render_includes_p305_metrics(self):
        m = MetricsRegistry()
        m.set_gauge("core_dlq_db_unresolved", 3.0)
        m.inc("core_dlq_retry_total", 2.0)
        m.inc("core_dlq_discard_total", 1.0)
        m.set_gauge("core_relay_lag_seconds", 0.5)

        output = m.render_prometheus()
        assert "core_dlq_db_unresolved 3.0" in output
        assert "core_dlq_retry_total 2.0" in output
        assert "core_dlq_discard_total 1.0" in output
        assert "core_relay_lag_seconds 0.5" in output

    def test_prometheus_render_has_all_metric_types(self):
        m = MetricsRegistry()
        output = m.render_prometheus()

        # Verify all expected metric names are present
        expected_metrics = [
            "core_event_outbox_published_total",
            "core_event_outbox_failed_total",
            "core_event_outbox_pending",
            "core_dlq_messages_total",
            "core_dlq_depth",
            "core_dlq_reprocess_success_total",
            "core_dlq_reprocess_failed_total",
            "core_dlq_db_unresolved",
            "core_dlq_retry_total",
            "core_dlq_discard_total",
            "core_relay_lag_seconds",
            "core_legacy_write_violations_total",
        ]
        for metric in expected_metrics:
            assert metric in output, f"Missing metric: {metric}"


class TestEventDeadLetterModel:
    """Test EventDeadLetter SQLAlchemy model structure."""

    def test_model_has_expected_columns(self):
        from app.models.base_models import EventDeadLetter
        mapper = EventDeadLetter.__table__
        column_names = {c.name for c in mapper.columns}
        expected = {
            "id", "original_event_id", "event_type", "aggregate_type",
            "aggregate_id", "payload", "failure_reason", "retry_count",
            "first_failed_at", "last_failed_at", "resolved_at",
            "resolution", "tenant_id",
        }
        assert expected.issubset(column_names), f"Missing columns: {expected - column_names}"

    def test_model_tablename(self):
        from app.models.base_models import EventDeadLetter
        assert EventDeadLetter.__tablename__ == "event_dead_letter"


class TestSagaExecutionLogModel:
    """Test SagaExecutionLog SQLAlchemy model structure."""

    def test_model_has_expected_columns(self):
        from app.models.base_models import SagaExecutionLog
        mapper = SagaExecutionLog.__table__
        column_names = {c.name for c in mapper.columns}
        expected = {
            "id", "saga_name", "tenant_id", "status",
            "context_snapshot", "steps_log", "started_at",
            "completed_at", "error",
        }
        assert expected.issubset(column_names)

    def test_model_tablename(self):
        from app.models.base_models import SagaExecutionLog
        assert SagaExecutionLog.__tablename__ == "saga_execution_log"
