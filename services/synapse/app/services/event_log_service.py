"""EventLogService — Facade (DDD-P2-04). 내부를 전문 서비스에 위임."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.event_log_db import EventLogDbError, fetch_database_rows  # noqa: F401 — re-export for test patches
from app.services.event_log_parser import EventLogParseError, EventLogParser
from app.services.event_log_repository import EventLogRecord, EventLogRepoError, EventLogRepository
from app.services.event_log_statistics import EventLogStatistics

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


class EventLogDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wrap(err: EventLogParseError | EventLogRepoError) -> EventLogDomainError:
    return EventLogDomainError(err.status_code, err.code, err.message)


class EventLogService:
    """기존 인터페이스 유지하는 Facade. 내부를 전문 서비스에 위임."""

    def __init__(self) -> None:
        self._parser = EventLogParser()
        self._repo = EventLogRepository()
        self._stats = EventLogStatistics()

    @property
    def _store(self):
        return self._repo._store

    @_store.setter
    def _store(self, value):
        self._repo._store = value

    def clear(self) -> None:
        self._repo.clear()

    def _get_log(self, tenant_id: str, log_id: str) -> EventLogRecord:
        try:
            return self._repo.get(tenant_id, log_id)
        except EventLogRepoError as err:
            raise _wrap(err) from err

    def _raise_db_error(self, err: EventLogDbError) -> None:
        sc = 400 if err.code in {"INVALID_REQUEST", "MISSING_COLUMN"} else 503
        raise EventLogDomainError(sc, err.code, err.message) from err

    def ingest(self, tenant_id: str, payload: dict[str, Any], file_bytes: bytes | None = None) -> dict[str, Any]:
        source_type = payload.get("source_type")
        if source_type not in {"csv", "xes", "database"}:
            raise EventLogDomainError(400, "INVALID_SOURCE_TYPE", "source_type must be csv|xes|database")
        case_id, name = payload.get("case_id"), payload.get("name")
        if not case_id or not name:
            raise EventLogDomainError(400, "INVALID_REQUEST", "case_id and name are required")
        mapping = payload.get("column_mapping", {})
        try:
            if source_type == "csv":
                if file_bytes is None:
                    raise EventLogDomainError(400, "INVALID_CSV_FORMAT", "csv file is required")
                if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                    raise EventLogDomainError(413, "FILE_TOO_LARGE", "file size exceeds 500MB")
                events, source_columns, raw_events = self._parser.parse_csv(file_bytes, mapping)
            elif source_type == "xes":
                if file_bytes is None:
                    raise EventLogDomainError(400, "INVALID_XES_FORMAT", "xes file is required")
                if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                    raise EventLogDomainError(413, "FILE_TOO_LARGE", "file size exceeds 500MB")
                events, source_columns, raw_events, mapping = self._parser.parse_xes(file_bytes)
            else:
                source_cfg = payload.get("source_config") or {}
                if not source_cfg.get("connection_id") or not source_cfg.get("table_name"):
                    raise EventLogDomainError(503, "DATABASE_CONNECTION_FAILED", "database source config missing")
                max_rows = int((payload.get("filter") or {}).get("max_rows") or 1000000)
                where_clause = (payload.get("filter") or {}).get("where_clause")
                try:
                    raw_events, source_columns = fetch_database_rows(
                        source_config=source_cfg, mapping=mapping,
                        where_clause=where_clause, max_rows=max_rows,
                    )
                except EventLogDbError as err:
                    self._raise_db_error(err)
                self._parser.validate_mapping(source_columns, mapping)
                events = self._parser.build_canonical_events(raw_events, mapping)
        except EventLogParseError as err:
            raise _wrap(err) from err
        log_id = f"log-{uuid.uuid4()}"
        created_at = _now_iso()
        record = EventLogRecord(
            log_id=log_id, tenant_id=tenant_id, case_id=str(case_id),
            name=str(name), source_type=source_type, status="completed",
            created_at=created_at, updated_at=created_at,
            source_config=payload.get("source_config", {}),
            options=payload.get("options", {}), filter=payload.get("filter", {}),
            column_mapping=mapping, raw_events=raw_events,
            events=events, source_columns=source_columns,
        )
        task_id = self._repo.save(record)
        return {
            "task_id": task_id, "log_id": log_id, "name": record.name,
            "source_type": record.source_type, "status": "ingesting", "created_at": created_at,
        }

    def list_logs(self, tenant_id: str, case_id: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        if not case_id:
            raise EventLogDomainError(400, "INVALID_REQUEST", "case_id is required")
        safe_limit, safe_offset = min(max(limit, 1), 100), max(offset, 0)
        try:
            if self._store:
                logs, total = self._repo.list_by_case(tenant_id, case_id, safe_limit, safe_offset)
                return {"logs": logs, "total": total}
            items, total = self._repo.list_by_case(tenant_id, case_id, safe_limit, safe_offset)
        except EventLogRepoError as err:
            raise _wrap(err) from err
        logs = []
        for item in items:
            ov = self._stats.compute(item.events)["overview"]
            logs.append({
                "log_id": item.log_id, "name": item.name, "source_type": item.source_type,
                "total_events": ov["total_events"], "total_cases": ov["total_cases"],
                "unique_activities": ov["unique_activities"],
                "date_range_start": ov["date_range_start"], "date_range_end": ov["date_range_end"],
                "created_at": item.created_at,
            })
        return {"logs": logs, "total": total}

    def get_log(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        ov = self._stats.compute(record.events)["overview"]
        return {
            "log_id": record.log_id, "case_id": record.case_id,
            "name": record.name, "source_type": record.source_type,
            "status": record.status, "column_mapping": record.column_mapping,
            "source_config": record.source_config,
            "statistics": {
                "total_events": ov["total_events"], "total_cases": ov["total_cases"],
                "unique_activities": ov["unique_activities"],
                "date_range": {"start": ov["date_range_start"], "end": ov["date_range_end"]},
            },
            "created_at": record.created_at, "updated_at": record.updated_at,
        }

    def delete_log(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        try:
            return self._repo.delete(tenant_id, log_id)
        except EventLogRepoError as err:
            raise _wrap(err) from err

    def get_statistics(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        stats = self._stats.compute(record.events)
        return {
            "log_id": record.log_id, "overview": stats["overview"],
            "activities": stats["activities"], "case_duration": stats["case_duration"],
            "variants": stats["variants"], "resources": stats["resources"],
        }

    def get_events_for_mining(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        return {"log_id": record.log_id, "case_id": record.case_id,
                "name": record.name, "events": list(record.events)}

    def get_preview(self, tenant_id: str, log_id: str, limit: int = 100) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        safe_limit = min(max(limit, 1), 100)
        return {"log_id": record.log_id, "column_mapping": record.column_mapping,
                "events": record.events[:safe_limit],
                "total_preview": min(safe_limit, len(record.events))}

    def update_column_mapping(self, tenant_id: str, log_id: str, mapping: dict[str, Any]) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        try:
            self._parser.validate_mapping(record.source_columns, mapping)
            new_events = self._parser.build_canonical_events(record.raw_events, mapping)
        except EventLogParseError as err:
            raise _wrap(err) from err
        except Exception as exc:
            raise EventLogDomainError(422, "INGESTION_FAILED", "failed to reprocess after mapping update") from exc
        try:
            self._repo.update_events_and_mapping(
                tenant_id=tenant_id, log_id=log_id, column_mapping=mapping,
                raw_events=record.raw_events, events=new_events,
                source_columns=list(record.source_columns),
            )
        except EventLogRepoError as err:
            raise _wrap(err) from err
        ov = self._stats.compute(new_events)["overview"]
        return {
            "log_id": record.log_id, "column_mapping": mapping,
            "reprocessing_status": "completed",
            "updated_statistics": {"total_cases": ov["total_cases"], "unique_activities": ov["unique_activities"]},
        }

    def refresh(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        if record.source_type != "database":
            raise EventLogDomainError(400, "INVALID_SOURCE_TYPE", "refresh is only supported for database source")
        max_rows = int((record.filter or {}).get("max_rows") or 1000000)
        where_clause = (record.filter or {}).get("where_clause")
        try:
            raw_events, source_columns = fetch_database_rows(
                source_config=record.source_config, mapping=record.column_mapping,
                where_clause=where_clause, max_rows=max_rows,
            )
        except EventLogDbError as err:
            self._raise_db_error(err)
        try:
            self._parser.validate_mapping(source_columns, record.column_mapping)
            events = self._parser.build_canonical_events(raw_events, record.column_mapping)
        except EventLogParseError as err:
            raise _wrap(err) from err
        try:
            self._repo.update_events_and_mapping(
                tenant_id=tenant_id, log_id=log_id, column_mapping=record.column_mapping,
                raw_events=raw_events, events=events, source_columns=list(source_columns),
            )
        except EventLogRepoError as err:
            raise _wrap(err) from err
        return {"task_id": f"task-refresh-{uuid.uuid4()}", "log_id": record.log_id,
                "status": "ingesting", "created_at": _now_iso()}

    def export_bpm(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id, name = payload.get("case_id"), payload.get("name") or "BPM Export Event Log"
        events = payload.get("events")
        if not case_id:
            raise EventLogDomainError(400, "INVALID_REQUEST", "case_id is required")
        if not isinstance(events, list) or not events:
            raise EventLogDomainError(400, "INVALID_REQUEST", "events is required")
        normalized: list[dict[str, Any]] = []
        for item in events:
            if not all(k in item for k in ("case_id", "activity", "timestamp")):
                raise EventLogDomainError(400, "MISSING_COLUMN", "case_id/activity/timestamp are required")
            normalized.append({"case_id": item["case_id"], "activity": item["activity"],
                               "timestamp": item["timestamp"], "resource": item.get("resource")})
        mapping = {"case_id_column": "case_id", "activity_column": "activity",
                   "timestamp_column": "timestamp", "resource_column": "resource",
                   "additional_columns": []}
        try:
            canonical = self._parser.build_canonical_events(normalized, mapping)
        except EventLogParseError as err:
            raise _wrap(err) from err
        now = _now_iso()
        record = EventLogRecord(
            log_id=f"log-{uuid.uuid4()}", tenant_id=tenant_id,
            case_id=str(case_id), name=str(name), source_type="bpm_export",
            status="completed", created_at=now, updated_at=now,
            column_mapping=mapping, raw_events=normalized,
            events=canonical, source_columns={"case_id", "activity", "timestamp", "resource"},
        )
        task_id = self._repo.save(record)
        return {"task_id": task_id, "log_id": record.log_id,
                "status": "ingesting", "source_type": "bpm_export", "created_at": now}


event_log_service = EventLogService()
