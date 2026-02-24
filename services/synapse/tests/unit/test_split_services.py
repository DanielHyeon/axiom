"""
DDD-P2-04 분할 서비스 독립 단위 테스트.

ProcessMiningService / EventLogService God Class 분할 후
각 클래스의 독립 동작을 검증한다.
"""
from __future__ import annotations

import pytest

# ═══════════════════════════════════════════════════════════════
# 1. MiningUtils
# ═══════════════════════════════════════════════════════════════

from app.services.mining_utils import (
    activity_duration_stats,
    build_case_paths,
    parse_ts,
    percentile,
    utcnow_iso,
)


class TestMiningUtils:
    def test_utcnow_iso(self):
        iso = utcnow_iso()
        assert "T" in iso
        assert "+" in iso or "Z" in iso

    def test_parse_ts_iso(self):
        dt = parse_ts("2024-01-15T10:30:00Z")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.hour == 10

    def test_percentile_basic(self):
        assert percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.5) == 3.0
        assert percentile([], 0.5) == 0.0

    def test_percentile_p95(self):
        data = list(range(1, 101))
        p95 = percentile([float(x) for x in data], 0.95)
        assert 95.0 <= p95 <= 96.0

    def test_build_case_paths(self):
        events = [
            {"case_id": "A", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z"},
            {"case_id": "A", "activity": "End", "timestamp": "2024-01-01T01:00:00Z"},
            {"case_id": "B", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z"},
        ]
        paths = build_case_paths(events)
        assert "A" in paths
        assert "B" in paths
        assert len(paths["A"]) == 2
        assert len(paths["B"]) == 1

    def test_activity_duration_stats(self):
        events = [
            {"case_id": "A", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z"},
            {"case_id": "A", "activity": "End", "timestamp": "2024-01-01T01:00:00Z"},
        ]
        paths = build_case_paths(events)
        stats = activity_duration_stats(paths)
        assert "Start" in stats


# ═══════════════════════════════════════════════════════════════
# 2. MiningTaskCoordinator
# ═══════════════════════════════════════════════════════════════

from app.services.mining_task_coordinator import MiningTaskCoordinator, MiningTaskError


class TestMiningTaskCoordinator:
    def setup_method(self):
        self.coord = MiningTaskCoordinator()
        self.coord._store = None  # in-memory mode
        self.coord.clear()

    def test_create_and_get_task(self):
        task = self.coord.create_task("t1", "discover", "case-1", "log-1", "user-1")
        assert task.task_id.startswith("task-")
        assert task.status == "queued"
        result = self.coord.get_task_dict("t1", task.task_id)
        assert result["status"] == "queued"

    def test_set_running_and_completed(self):
        task = self.coord.create_task("t1", "discover", "case-1", "log-1", None)
        self.coord.set_running(task)
        assert task.status == "running"
        self.coord.set_completed(task, {"some": "result"})
        assert task.status == "completed"

    def test_task_not_found(self):
        with pytest.raises(MiningTaskError) as exc_info:
            self.coord.get_task_dict("t1", "nonexistent")
        assert exc_info.value.code == "TASK_NOT_FOUND"

    def test_result_not_found_for_running(self):
        task = self.coord.create_task("t1", "discover", "case-1", "log-1", None)
        self.coord.set_running(task)
        with pytest.raises(MiningTaskError) as exc_info:
            self.coord.get_task_result_dict("t1", task.task_id)
        assert exc_info.value.code == "RESULT_NOT_FOUND"


# ═══════════════════════════════════════════════════════════════
# 3. EventLogParser
# ═══════════════════════════════════════════════════════════════

from app.services.event_log_parser import EventLogParseError, EventLogParser


class TestEventLogParser:
    def setup_method(self):
        self.parser = EventLogParser()

    def test_validate_mapping_ok(self):
        cols = {"order_id", "event_type", "event_time"}
        mapping = {"case_id_column": "order_id", "activity_column": "event_type", "timestamp_column": "event_time"}
        self.parser.validate_mapping(cols, mapping)

    def test_validate_mapping_missing(self):
        cols = {"order_id", "event_type"}
        mapping = {"case_id_column": "order_id", "activity_column": "event_type", "timestamp_column": "event_time"}
        with pytest.raises(EventLogParseError):
            self.parser.validate_mapping(cols, mapping)

    def test_build_canonical_events(self):
        rows = [
            {"order_id": "A", "event_type": "Start", "event_time": "2024-01-01T00:00:00Z"},
            {"order_id": "A", "event_type": "End", "event_time": "2024-01-01T01:00:00Z"},
        ]
        mapping = {"case_id_column": "order_id", "activity_column": "event_type",
                    "timestamp_column": "event_time", "additional_columns": []}
        events = self.parser.build_canonical_events(rows, mapping)
        assert len(events) == 2
        assert events[0]["case_id"] == "A"
        assert events[0]["activity"] == "Start"

    def test_parse_csv(self):
        csv_bytes = (
            "order_id,event_type,event_time\n"
            "ORD-1,Start,2024-01-01T00:00:00Z\n"
            "ORD-1,End,2024-01-01T01:00:00Z\n"
        ).encode("utf-8")
        mapping = {"case_id_column": "order_id", "activity_column": "event_type", "timestamp_column": "event_time"}
        events, source_columns, raw_events = self.parser.parse_csv(csv_bytes, mapping)
        assert len(events) == 2
        assert "order_id" in source_columns

    def test_parse_csv_empty(self):
        csv_bytes = b"order_id,event_type,event_time\n"
        mapping = {"case_id_column": "order_id", "activity_column": "event_type", "timestamp_column": "event_time"}
        with pytest.raises(EventLogParseError, match="no rows"):
            self.parser.parse_csv(csv_bytes, mapping)

    def test_parse_xes(self):
        xes_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<log>
  <trace>
    <string key="concept:name" value="case-1"/>
    <event>
      <string key="concept:name" value="Start"/>
      <date key="time:timestamp" value="2024-01-01T00:00:00Z"/>
      <string key="org:resource" value="Alice"/>
    </event>
    <event>
      <string key="concept:name" value="End"/>
      <date key="time:timestamp" value="2024-01-01T01:00:00Z"/>
      <string key="org:resource" value="Bob"/>
    </event>
  </trace>
</log>"""
        events, source_columns, raw_events, mapping = self.parser.parse_xes(xes_bytes)
        assert len(events) == 2
        assert mapping["case_id_column"] == "case_id"


# ═══════════════════════════════════════════════════════════════
# 4. EventLogStatistics
# ═══════════════════════════════════════════════════════════════

from app.services.event_log_statistics import EventLogStatistics


class TestEventLogStatistics:
    def test_compute_empty(self):
        stats = EventLogStatistics.compute([])
        assert stats["total_events"] == 0
        assert stats["total_cases"] == 0

    def test_compute_basic(self):
        events = [
            {"case_id": "A", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z"},
            {"case_id": "A", "activity": "End", "timestamp": "2024-01-01T01:00:00Z"},
            {"case_id": "B", "activity": "Start", "timestamp": "2024-01-02T00:00:00Z"},
            {"case_id": "B", "activity": "End", "timestamp": "2024-01-02T02:00:00Z"},
        ]
        stats = EventLogStatistics.compute(events)
        assert stats["overview"]["total_events"] == 4
        assert stats["overview"]["total_cases"] == 2
        assert stats["overview"]["unique_activities"] == 2
        assert stats["case_duration"]["avg_seconds"] > 0
        assert stats["variants"]["total_variants"] == 1
        assert len(stats["activities"]) == 2

    def test_compute_resources(self):
        events = [
            {"case_id": "A", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z", "resource": "Alice"},
            {"case_id": "A", "activity": "End", "timestamp": "2024-01-01T01:00:00Z", "resource": "Bob"},
        ]
        stats = EventLogStatistics.compute(events)
        assert len(stats["resources"]) == 2


# ═══════════════════════════════════════════════════════════════
# 5. EventLogRepository
# ═══════════════════════════════════════════════════════════════

from app.services.event_log_repository import EventLogRecord, EventLogRepoError, EventLogRepository


class TestEventLogRepository:
    def setup_method(self):
        self.repo = EventLogRepository()
        self.repo._store = None  # in-memory mode
        self.repo.clear()

    def _make_record(self, log_id: str = "log-1", tenant_id: str = "t1", case_id: str = "c1") -> EventLogRecord:
        return EventLogRecord(
            log_id=log_id, tenant_id=tenant_id, case_id=case_id,
            name="test-log", source_type="csv", status="completed",
            created_at="2024-01-01T00:00:00Z", updated_at="2024-01-01T00:00:00Z",
            events=[{"case_id": "A", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z"}],
        )

    def test_save_and_get(self):
        record = self._make_record()
        self.repo.save(record)
        result = self.repo.get("t1", "log-1")
        assert result.log_id == "log-1"
        assert result.name == "test-log"

    def test_get_not_found(self):
        with pytest.raises(EventLogRepoError):
            self.repo.get("t1", "nonexistent")

    def test_delete(self):
        self.repo.save(self._make_record())
        result = self.repo.delete("t1", "log-1")
        assert result["deleted"] is True
        with pytest.raises(EventLogRepoError):
            self.repo.get("t1", "log-1")

    def test_list_by_case(self):
        self.repo.save(self._make_record("log-1"))
        self.repo.save(self._make_record("log-2"))
        items, total = self.repo.list_by_case("t1", "c1")
        assert total == 2
        assert len(items) == 2

    def test_update_events_and_mapping(self):
        self.repo.save(self._make_record())
        new_events = [{"case_id": "A", "activity": "Updated", "timestamp": "2024-01-02T00:00:00Z"}]
        self.repo.update_events_and_mapping(
            tenant_id="t1", log_id="log-1", column_mapping={"new": "mapping"},
            raw_events=[], events=new_events, source_columns=["case_id"],
        )
        record = self.repo.get("t1", "log-1")
        assert record.events == new_events
        assert record.column_mapping == {"new": "mapping"}


# ═══════════════════════════════════════════════════════════════
# 6. BottleneckService
# ═══════════════════════════════════════════════════════════════

from app.services.bottleneck_service import BottleneckService


class TestBottleneckService:
    def test_analyze_basic(self):
        coord = MiningTaskCoordinator()
        coord._store = None
        svc = BottleneckService(coord)
        events = [
            {"case_id": "A", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z"},
            {"case_id": "A", "activity": "Review", "timestamp": "2024-01-01T02:00:00Z"},
            {"case_id": "A", "activity": "End", "timestamp": "2024-01-01T03:00:00Z"},
        ]
        result = svc.analyze(events, sort_by="bottleneck_score_desc", _sla_source="eventstorming")
        assert "bottlenecks" in result
        assert isinstance(result["bottlenecks"], list)


# ═══════════════════════════════════════════════════════════════
# 7. VariantService
# ═══════════════════════════════════════════════════════════════

from app.services.variant_service import VariantService


class TestVariantService:
    def test_analyze_basic(self):
        svc = VariantService()
        events = [
            {"case_id": "A", "activity": "Start", "timestamp": "2024-01-01T00:00:00Z"},
            {"case_id": "A", "activity": "End", "timestamp": "2024-01-01T01:00:00Z"},
            {"case_id": "B", "activity": "Start", "timestamp": "2024-01-02T00:00:00Z"},
            {"case_id": "B", "activity": "End", "timestamp": "2024-01-02T01:00:00Z"},
        ]
        case_paths = build_case_paths(events)
        result = svc.analyze(case_paths, sort_by="frequency_desc", limit=10, min_cases=1)
        assert "variants" in result
        assert result["total_variants"] >= 1
        assert result["variants"][0]["case_count"] == 2


# ═══════════════════════════════════════════════════════════════
# 8. Facade backward compat
# ═══════════════════════════════════════════════════════════════

from app.services.process_mining_service import ProcessMiningDomainError, ProcessMiningService


class TestProcessMiningServiceFacade:
    def test_backward_compat_error(self):
        assert ProcessMiningDomainError is MiningTaskError

    def test_facade_instantiation(self):
        svc = ProcessMiningService()
        assert hasattr(svc, "_coord")
        assert hasattr(svc, "_discovery")
        assert hasattr(svc, "_conformance")
        assert hasattr(svc, "_bottleneck")
        assert hasattr(svc, "_variant")

    def test_clear(self):
        svc = ProcessMiningService()
        svc._coord._store = None
        svc.clear()  # should not raise


from app.services.event_log_service import EventLogDomainError, EventLogService


class TestEventLogServiceFacade:
    def test_facade_instantiation(self):
        svc = EventLogService()
        assert hasattr(svc, "_parser")
        assert hasattr(svc, "_repo")
        assert hasattr(svc, "_stats")

    def test_store_property(self):
        svc = EventLogService()
        svc._store = None
        assert svc._store is None

    def test_clear(self):
        svc = EventLogService()
        svc._store = None
        svc.clear()

    def test_ingest_csv_via_facade(self):
        svc = EventLogService()
        svc._store = None
        csv_bytes = (
            "order_id,event_type,event_time\n"
            "ORD-1,Start,2024-01-01T00:00:00Z\n"
            "ORD-1,End,2024-01-01T01:00:00Z\n"
        ).encode("utf-8")
        payload = {
            "case_id": "case-1", "name": "test-log", "source_type": "csv",
            "column_mapping": {
                "case_id_column": "order_id", "activity_column": "event_type",
                "timestamp_column": "event_time",
            },
        }
        result = svc.ingest("t1", payload, file_bytes=csv_bytes)
        assert result["status"] == "ingesting"
        assert "log_id" in result

        stats = svc.get_statistics("t1", result["log_id"])
        assert stats["overview"]["total_events"] == 2

    def test_domain_error_compat(self):
        svc = EventLogService()
        svc._store = None
        with pytest.raises(EventLogDomainError, match="source_type must be"):
            svc.ingest("t1", {"case_id": "c", "name": "bad", "source_type": "foo"})
