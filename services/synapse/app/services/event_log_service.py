import csv
import io
import uuid
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median
from typing import Any

from app.services.event_log_db import EventLogDbError, fetch_database_rows
from app.services.event_log_store import get_event_log_store


MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


class EventLogDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value is None:
        raise EventLogDomainError(400, "INVALID_TIMESTAMP", "timestamp is required")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventLogDomainError(400, "INVALID_TIMESTAMP", f"timestamp parse failed: {value}") from exc
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    weight = pos - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


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


def _record_from_store_row(row: dict[str, Any]) -> EventLogRecord:
    """Store 행을 EventLogRecord로 변환."""
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


class EventLogService:
    def __init__(self) -> None:
        self._logs: dict[str, EventLogRecord] = {}
        self._task_to_log: dict[str, str] = {}
        self._store = get_event_log_store()

    def clear(self) -> None:
        self._logs.clear()
        self._task_to_log.clear()
        if self._store:
            self._store.clear()

    def _get_log(self, tenant_id: str, log_id: str) -> EventLogRecord:
        if self._store:
            row = self._store.get(tenant_id, log_id)
            if not row:
                raise EventLogDomainError(404, "LOG_NOT_FOUND", "event log not found")
            return _record_from_store_row(row)
        record = self._logs.get(log_id)
        if not record or record.tenant_id != tenant_id:
            raise EventLogDomainError(404, "LOG_NOT_FOUND", "event log not found")
        return record

    def _raise_db_error(self, err: EventLogDbError) -> None:
        status_code = 503
        if err.code in {"INVALID_REQUEST", "MISSING_COLUMN"}:
            status_code = 400
        raise EventLogDomainError(status_code, err.code, err.message) from err

    def _validate_mapping(self, source_columns: set[str], mapping: dict[str, Any]) -> None:
        required = ["case_id_column", "activity_column", "timestamp_column"]
        for key in required:
            if not mapping.get(key):
                raise EventLogDomainError(400, "MISSING_COLUMN", f"{key} is required")
            if mapping[key] not in source_columns:
                raise EventLogDomainError(400, "MISSING_COLUMN", f"{mapping[key]} is missing")
        resource_column = mapping.get("resource_column")
        if resource_column and resource_column not in source_columns:
            raise EventLogDomainError(400, "MISSING_COLUMN", f"{resource_column} is missing")
        for col in mapping.get("additional_columns", []) or []:
            if col not in source_columns:
                raise EventLogDomainError(400, "MISSING_COLUMN", f"{col} is missing")

    def _build_canonical_events(self, raw_events: list[dict[str, Any]], mapping: dict[str, Any]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        case_col = mapping["case_id_column"]
        act_col = mapping["activity_column"]
        ts_col = mapping["timestamp_column"]
        resource_col = mapping.get("resource_column")
        additional = mapping.get("additional_columns", []) or []
        for row in raw_events:
            ts = _parse_timestamp(row.get(ts_col))
            attributes = {k: row.get(k) for k in additional if k in row}
            converted.append(
                {
                    "case_id": str(row.get(case_col)),
                    "activity": str(row.get(act_col)),
                    "timestamp": ts.isoformat(),
                    "resource": row.get(resource_col) if resource_col else None,
                    "attributes": attributes,
                }
            )
        converted.sort(key=lambda item: (item["case_id"], item["timestamp"]))
        return converted

    def _parse_csv(self, payload: bytes, mapping: dict[str, Any]) -> tuple[list[dict[str, Any]], set[str], list[dict[str, Any]]]:
        try:
            text = payload.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
        except Exception as exc:
            raise EventLogDomainError(400, "INVALID_CSV_FORMAT", "csv parse failed") from exc
        if not rows:
            raise EventLogDomainError(400, "INVALID_CSV_FORMAT", "csv has no rows")
        source_columns = set(rows[0].keys())
        self._validate_mapping(source_columns, mapping)
        return self._build_canonical_events(rows, mapping), source_columns, rows

    def _parse_xes(self, payload: bytes) -> tuple[list[dict[str, Any]], set[str], list[dict[str, Any]], dict[str, Any]]:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise EventLogDomainError(400, "INVALID_XES_FORMAT", "xes parse failed") from exc

        rows: list[dict[str, Any]] = []
        for trace in root.findall(".//trace"):
            case_id = None
            for child in trace:
                if child.tag.endswith("string") and child.attrib.get("key") == "concept:name":
                    case_id = child.attrib.get("value")
                    break
            if not case_id:
                case_id = str(uuid.uuid4())

            for event in trace.findall("./event"):
                row: dict[str, Any] = {"case_id": case_id}
                for attr in event:
                    key = attr.attrib.get("key")
                    value = attr.attrib.get("value")
                    if key and value is not None:
                        row[key] = value
                rows.append(row)

        if not rows:
            raise EventLogDomainError(400, "INVALID_XES_FORMAT", "xes has no events")

        mapping = {
            "case_id_column": "case_id",
            "activity_column": "concept:name",
            "timestamp_column": "time:timestamp",
            "resource_column": "org:resource",
            "additional_columns": [],
        }
        source_columns = set().union(*(set(r.keys()) for r in rows))
        self._validate_mapping(source_columns, mapping)
        return self._build_canonical_events(rows, mapping), source_columns, rows, mapping

    def _compute_statistics(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return {
                "total_events": 0,
                "total_cases": 0,
                "unique_activities": 0,
                "date_range": {"start": None, "end": None},
                "ingestion_duration_seconds": 0.0,
            }

        timestamps = [_parse_timestamp(item["timestamp"]) for item in events]
        total_events = len(events)
        case_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
        activity_counter: Counter[str] = Counter()
        resource_counter: Counter[str] = Counter()
        for event in events:
            case_map[event["case_id"]].append(event)
            activity_counter[event["activity"]] += 1
            if event.get("resource"):
                resource_counter[str(event["resource"])] += 1

        total_cases = len(case_map)
        case_durations: list[float] = []
        variants_counter: Counter[str] = Counter()
        for case_id, items in case_map.items():
            sorted_items = sorted(items, key=lambda x: x["timestamp"])
            first = _parse_timestamp(sorted_items[0]["timestamp"])
            last = _parse_timestamp(sorted_items[-1]["timestamp"])
            case_durations.append((last - first).total_seconds())
            variant = " > ".join(item["activity"] for item in sorted_items)
            variants_counter[variant] += 1

        case_durations_sorted = sorted(case_durations)
        avg_duration = sum(case_durations) / len(case_durations) if case_durations else 0.0
        unique_activities = len(activity_counter)
        total_variants = len(variants_counter)
        top3 = variants_counter.most_common(3)
        top3_cases = sum(count for _, count in top3)
        top3_coverage = (top3_cases / total_cases) if total_cases else 0.0

        activities = []
        for name, freq in activity_counter.most_common():
            activities.append(
                {
                    "name": name,
                    "frequency": freq,
                    "relative_frequency": round(freq / total_events, 3) if total_events else 0.0,
                    "avg_duration_seconds": round(avg_duration / max(unique_activities, 1), 2),
                }
            )

        resources = []
        for name, event_count in resource_counter.most_common(20):
            touched_cases = len({event["case_id"] for event in events if event.get("resource") == name})
            resources.append({"name": name, "event_count": event_count, "case_count": touched_cases})

        overview = {
            "total_events": total_events,
            "total_cases": total_cases,
            "unique_activities": unique_activities,
            "avg_events_per_case": round(total_events / total_cases, 3) if total_cases else 0.0,
            "date_range_start": min(timestamps).isoformat(),
            "date_range_end": max(timestamps).isoformat(),
        }
        case_duration = {
            "avg_seconds": round(avg_duration, 2),
            "median_seconds": round(median(case_durations_sorted), 2) if case_durations_sorted else 0.0,
            "min_seconds": round(min(case_durations_sorted), 2) if case_durations_sorted else 0.0,
            "max_seconds": round(max(case_durations_sorted), 2) if case_durations_sorted else 0.0,
            "p25_seconds": round(_percentile(case_durations_sorted, 0.25), 2),
            "p75_seconds": round(_percentile(case_durations_sorted, 0.75), 2),
            "p95_seconds": round(_percentile(case_durations_sorted, 0.95), 2),
        }
        return {
            "overview": overview,
            "activities": activities,
            "case_duration": case_duration,
            "variants": {"total_variants": total_variants, "top_3_coverage": round(top3_coverage, 3)},
            "resources": resources,
            "date_range": {"start": overview["date_range_start"], "end": overview["date_range_end"]},
            "ingestion_duration_seconds": 0.0,
        }

    def ingest(
        self,
        tenant_id: str,
        payload: dict[str, Any],
        file_bytes: bytes | None = None,
    ) -> dict[str, Any]:
        source_type = payload.get("source_type")
        if source_type not in {"csv", "xes", "database"}:
            raise EventLogDomainError(400, "INVALID_SOURCE_TYPE", "source_type must be csv|xes|database")
        case_id = payload.get("case_id")
        name = payload.get("name")
        if not case_id or not name:
            raise EventLogDomainError(400, "INVALID_REQUEST", "case_id and name are required")

        mapping = payload.get("column_mapping", {})
        source_columns: set[str]
        raw_events: list[dict[str, Any]]
        events: list[dict[str, Any]]
        if source_type == "csv":
            if file_bytes is None:
                raise EventLogDomainError(400, "INVALID_CSV_FORMAT", "csv file is required")
            if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                raise EventLogDomainError(413, "FILE_TOO_LARGE", "file size exceeds 500MB")
            events, source_columns, raw_events = self._parse_csv(file_bytes, mapping)
        elif source_type == "xes":
            if file_bytes is None:
                raise EventLogDomainError(400, "INVALID_XES_FORMAT", "xes file is required")
            if len(file_bytes) > MAX_FILE_SIZE_BYTES:
                raise EventLogDomainError(413, "FILE_TOO_LARGE", "file size exceeds 500MB")
            events, source_columns, raw_events, mapping = self._parse_xes(file_bytes)
        else:
            source_cfg = payload.get("source_config") or {}
            if not source_cfg.get("connection_id") or not source_cfg.get("table_name"):
                raise EventLogDomainError(503, "DATABASE_CONNECTION_FAILED", "database source config missing")
            max_rows = int((payload.get("filter") or {}).get("max_rows") or 1000000)
            where_clause = (payload.get("filter") or {}).get("where_clause")
            try:
                raw_events, source_columns = fetch_database_rows(
                    source_config=source_cfg,
                    mapping=mapping,
                    where_clause=where_clause,
                    max_rows=max_rows,
                )
            except EventLogDbError as err:
                self._raise_db_error(err)
            self._validate_mapping(source_columns, mapping)
            events = self._build_canonical_events(raw_events, mapping)

        log_id = f"log-{uuid.uuid4()}"
        task_id = f"task-ingest-{uuid.uuid4()}"
        created_at = _now_iso()
        record = EventLogRecord(
            log_id=log_id,
            tenant_id=tenant_id,
            case_id=str(case_id),
            name=str(name),
            source_type=source_type,
            status="completed",
            created_at=created_at,
            updated_at=created_at,
            source_config=payload.get("source_config", {}),
            options=payload.get("options", {}),
            filter=payload.get("filter", {}),
            column_mapping=mapping,
            raw_events=raw_events,
            events=events,
            source_columns=source_columns,
        )
        if self._store:
            self._store.insert(
                log_id=log_id,
                tenant_id=tenant_id,
                case_id=str(case_id),
                name=str(name),
                source_type=source_type,
                status="completed",
                source_config=payload.get("source_config", {}),
                options=payload.get("options", {}),
                filter_config=payload.get("filter", {}),
                column_mapping=mapping,
                source_columns=list(source_columns),
                raw_events=raw_events,
                events=events,
            )
        else:
            self._logs[log_id] = record
            self._task_to_log[task_id] = log_id

        return {
            "task_id": task_id,
            "log_id": log_id,
            "name": record.name,
            "source_type": record.source_type,
            "status": "ingesting",
            "created_at": created_at,
        }

    def list_logs(self, tenant_id: str, case_id: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        if not case_id:
            raise EventLogDomainError(400, "INVALID_REQUEST", "case_id is required")
        safe_limit = min(max(limit, 1), 100)
        safe_offset = max(offset, 0)

        if self._store:
            logs, total = self._store.list_by_case(tenant_id, case_id, safe_limit, safe_offset)
            return {"logs": logs, "total": total}
        all_logs = [item for item in self._logs.values() if item.tenant_id == tenant_id and item.case_id == case_id]
        all_logs.sort(key=lambda item: item.created_at, reverse=True)
        sliced = all_logs[safe_offset : safe_offset + safe_limit]
        logs = []
        for item in sliced:
            stats = self._compute_statistics(item.events)
            overview = stats["overview"]
            logs.append(
                {
                    "log_id": item.log_id,
                    "name": item.name,
                    "source_type": item.source_type,
                    "total_events": overview["total_events"],
                    "total_cases": overview["total_cases"],
                    "unique_activities": overview["unique_activities"],
                    "date_range_start": overview["date_range_start"],
                    "date_range_end": overview["date_range_end"],
                    "created_at": item.created_at,
                }
            )
        return {"logs": logs, "total": len(all_logs)}

    def get_log(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        stats = self._compute_statistics(record.events)
        overview = stats["overview"]
        return {
            "log_id": record.log_id,
            "case_id": record.case_id,
            "name": record.name,
            "source_type": record.source_type,
            "status": record.status,
            "column_mapping": record.column_mapping,
            "source_config": record.source_config,
            "statistics": {
                "total_events": overview["total_events"],
                "total_cases": overview["total_cases"],
                "unique_activities": overview["unique_activities"],
                "date_range": {
                    "start": overview["date_range_start"],
                    "end": overview["date_range_end"],
                },
            },
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def delete_log(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        self._get_log(tenant_id, log_id)
        if self._store:
            self._store.delete(tenant_id, log_id)
        else:
            del self._logs[log_id]
        return {"log_id": log_id, "deleted": True}

    def get_statistics(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        stats = self._compute_statistics(record.events)
        return {
            "log_id": record.log_id,
            "overview": stats["overview"],
            "activities": stats["activities"],
            "case_duration": stats["case_duration"],
            "variants": stats["variants"],
            "resources": stats["resources"],
        }

    def get_events_for_mining(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        return {
            "log_id": record.log_id,
            "case_id": record.case_id,
            "name": record.name,
            "events": list(record.events),
        }

    def get_preview(self, tenant_id: str, log_id: str, limit: int = 100) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        safe_limit = min(max(limit, 1), 100)
        return {
            "log_id": record.log_id,
            "column_mapping": record.column_mapping,
            "events": record.events[:safe_limit],
            "total_preview": min(safe_limit, len(record.events)),
        }

    def update_column_mapping(self, tenant_id: str, log_id: str, mapping: dict[str, Any]) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        self._validate_mapping(record.source_columns, mapping)
        try:
            new_events = self._build_canonical_events(record.raw_events, mapping)
        except EventLogDomainError:
            raise
        except Exception as exc:
            raise EventLogDomainError(422, "INGESTION_FAILED", "failed to reprocess after mapping update") from exc
        if self._store:
            self._store.update_events_and_mapping(
                tenant_id=tenant_id,
                log_id=log_id,
                column_mapping=mapping,
                raw_events=record.raw_events,
                events=new_events,
                source_columns=list(record.source_columns),
            )
        else:
            record.column_mapping = mapping
            record.events = new_events
            record.updated_at = _now_iso()
        stats = self._compute_statistics(new_events)["overview"]
        return {
            "log_id": record.log_id,
            "column_mapping": mapping,
            "reprocessing_status": "completed",
            "updated_statistics": {
                "total_cases": stats["total_cases"],
                "unique_activities": stats["unique_activities"],
            },
        }

    def refresh(self, tenant_id: str, log_id: str) -> dict[str, Any]:
        record = self._get_log(tenant_id, log_id)
        if record.source_type != "database":
            raise EventLogDomainError(400, "INVALID_SOURCE_TYPE", "refresh is only supported for database source")

        max_rows = int((record.filter or {}).get("max_rows") or 1000000)
        where_clause = (record.filter or {}).get("where_clause")
        try:
            raw_events, source_columns = fetch_database_rows(
                source_config=record.source_config,
                mapping=record.column_mapping,
                where_clause=where_clause,
                max_rows=max_rows,
            )
        except EventLogDbError as err:
            self._raise_db_error(err)
        self._validate_mapping(source_columns, record.column_mapping)
        events = self._build_canonical_events(raw_events, record.column_mapping)
        updated_at = _now_iso()
        if self._store:
            self._store.update_events_and_mapping(
                tenant_id=tenant_id,
                log_id=log_id,
                column_mapping=record.column_mapping,
                raw_events=raw_events,
                events=events,
                source_columns=list(source_columns),
            )
        else:
            record.raw_events = raw_events
            record.events = events
            record.source_columns = source_columns
            record.updated_at = updated_at
        task_id = f"task-refresh-{uuid.uuid4()}"
        if not self._store:
            self._task_to_log[task_id] = record.log_id
        return {
            "task_id": task_id,
            "log_id": record.log_id,
            "status": "ingesting",
            "created_at": updated_at,
        }

    def export_bpm(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        case_id = payload.get("case_id")
        name = payload.get("name") or "BPM Export Event Log"
        events = payload.get("events")
        if not case_id:
            raise EventLogDomainError(400, "INVALID_REQUEST", "case_id is required")
        if not isinstance(events, list) or not events:
            raise EventLogDomainError(400, "INVALID_REQUEST", "events is required")

        normalized_rows: list[dict[str, Any]] = []
        for item in events:
            if not all(key in item for key in ("case_id", "activity", "timestamp")):
                raise EventLogDomainError(400, "MISSING_COLUMN", "case_id/activity/timestamp are required")
            row = {
                "case_id": item["case_id"],
                "activity": item["activity"],
                "timestamp": item["timestamp"],
                "resource": item.get("resource"),
            }
            normalized_rows.append(row)

        mapping = {
            "case_id_column": "case_id",
            "activity_column": "activity",
            "timestamp_column": "timestamp",
            "resource_column": "resource",
            "additional_columns": [],
        }
        canonical = self._build_canonical_events(normalized_rows, mapping)
        source_columns = {"case_id", "activity", "timestamp", "resource"}

        log_id = f"log-{uuid.uuid4()}"
        task_id = f"task-export-{uuid.uuid4()}"
        now = _now_iso()
        record = EventLogRecord(
            log_id=log_id,
            tenant_id=tenant_id,
            case_id=str(case_id),
            name=str(name),
            source_type="bpm_export",
            status="completed",
            created_at=now,
            updated_at=now,
            column_mapping=mapping,
            raw_events=normalized_rows,
            events=canonical,
            source_columns=source_columns,
        )
        if self._store:
            self._store.insert(
                log_id=log_id,
                tenant_id=tenant_id,
                case_id=str(case_id),
                name=str(name),
                source_type="bpm_export",
                status="completed",
                source_config={},
                options={},
                filter_config={},
                column_mapping=mapping,
                source_columns=list(source_columns),
                raw_events=normalized_rows,
                events=canonical,
            )
        else:
            self._logs[log_id] = record
            self._task_to_log[task_id] = log_id
        return {
            "task_id": task_id,
            "log_id": log_id,
            "status": "ingesting",
            "source_type": "bpm_export",
            "created_at": now,
        }


event_log_service = EventLogService()
