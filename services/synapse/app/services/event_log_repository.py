"""
EventLogRepository — 이벤트 로그 CRUD 전담 (DDD-P2-04).

EventLogService에서 추출한 저장·조회·삭제 책임.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.event_log_store import get_event_log_store


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventLogRepoError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass
class EventLogRecord:
    log_id: str
    tenant_id: str
    case_id: str
    name: str
    source_type: str
    status: str
    created_at: str
    updated_at: str
    source_config: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    filter: dict[str, Any] = field(default_factory=dict)
    column_mapping: dict[str, Any] = field(default_factory=dict)
    raw_events: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    source_columns: set[str] = field(default_factory=set)


def record_from_store_row(row: dict[str, Any]) -> EventLogRecord:
    sc = row.get("source_columns")
    source_columns = set(sc) if isinstance(sc, list) else (sc if isinstance(sc, set) else set())
    return EventLogRecord(
        log_id=row["log_id"],
        tenant_id=row["tenant_id"],
        case_id=row["case_id"],
        name=row["name"],
        source_type=row["source_type"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        source_config=row.get("source_config") or {},
        options=row.get("options") or {},
        filter=row.get("filter") or {},
        column_mapping=row.get("column_mapping") or {},
        raw_events=row.get("raw_events") or [],
        events=row.get("events") or [],
        source_columns=source_columns,
    )


class EventLogRepository:
    """이벤트 로그 레코드 저장·조회·삭제 전담."""

    def __init__(self) -> None:
        self._logs: dict[str, EventLogRecord] = {}
        self._task_to_log: dict[str, str] = {}
        self._store = get_event_log_store()

    def clear(self) -> None:
        self._logs.clear()
        self._task_to_log.clear()
        if self._store:
            self._store.clear()

    @property
    def store(self):
        return self._store

    def get(self, tenant_id: str, log_id: str) -> EventLogRecord:
        if self._store:
            row = self._store.get(tenant_id, log_id)
            if not row:
                raise EventLogRepoError(404, "LOG_NOT_FOUND", "event log not found")
            return record_from_store_row(row)
        record = self._logs.get(log_id)
        if not record or record.tenant_id != tenant_id:
            raise EventLogRepoError(404, "LOG_NOT_FOUND", "event log not found")
        return record

    def save(self, record: EventLogRecord) -> str:
        task_id = f"task-ingest-{uuid.uuid4()}"
        if self._store:
            self._store.insert(
                log_id=record.log_id,
                tenant_id=record.tenant_id,
                case_id=record.case_id,
                name=record.name,
                source_type=record.source_type,
                status=record.status,
                source_config=record.source_config,
                options=record.options,
                filter_config=record.filter,
                column_mapping=record.column_mapping,
                source_columns=list(record.source_columns),
                raw_events=record.raw_events,
                events=record.events,
            )
        else:
            self._logs[record.log_id] = record
            self._task_to_log[task_id] = record.log_id
        return task_id

    def update_events_and_mapping(
        self,
        tenant_id: str,
        log_id: str,
        column_mapping: dict[str, Any],
        raw_events: list[dict[str, Any]],
        events: list[dict[str, Any]],
        source_columns: list[str],
    ) -> None:
        if self._store:
            self._store.update_events_and_mapping(
                tenant_id=tenant_id,
                log_id=log_id,
                column_mapping=column_mapping,
                raw_events=raw_events,
                events=events,
                source_columns=source_columns,
            )
        else:
            record = self._logs.get(log_id)
            if record:
                record.column_mapping = column_mapping
                record.raw_events = raw_events
                record.events = events
                record.source_columns = set(source_columns)
                record.updated_at = _now_iso()

    def delete(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        self.get(tenant_id, log_id)  # ensure exists
        if self._store:
            self._store.delete(tenant_id, log_id)
        else:
            del self._logs[log_id]
        return {"log_id": log_id, "deleted": True}

    def list_by_case(
        self, tenant_id: str, case_id: str, limit: int = 20, offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        if self._store:
            return self._store.list_by_case(tenant_id, case_id, limit, offset)
        all_logs = [
            item for item in self._logs.values()
            if item.tenant_id == tenant_id and item.case_id == case_id
        ]
        all_logs.sort(key=lambda item: item.created_at, reverse=True)
        return all_logs[offset:offset + limit], len(all_logs)
