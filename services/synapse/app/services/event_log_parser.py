"""
EventLogParser — CSV/XES/DB 파싱 전담 (DDD-P2-04).

EventLogService에서 추출한 파싱·검증·정규화 책임.
"""
from __future__ import annotations

import csv
import io
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024


class EventLogParseError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if value is None:
        raise EventLogParseError(400, "INVALID_TIMESTAMP", "timestamp is required")
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventLogParseError(400, "INVALID_TIMESTAMP", f"timestamp parse failed: {value}") from exc
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class EventLogParser:
    """CSV, XES, DB 소스의 이벤트 로그 파싱 전담."""

    @staticmethod
    def validate_mapping(source_columns: set[str], mapping: dict[str, Any]) -> None:
        required = ["case_id_column", "activity_column", "timestamp_column"]
        for key in required:
            if not mapping.get(key):
                raise EventLogParseError(400, "MISSING_COLUMN", f"{key} is required")
            if mapping[key] not in source_columns:
                raise EventLogParseError(400, "MISSING_COLUMN", f"{mapping[key]} is missing")
        resource_column = mapping.get("resource_column")
        if resource_column and resource_column not in source_columns:
            raise EventLogParseError(400, "MISSING_COLUMN", f"{resource_column} is missing")
        for col in mapping.get("additional_columns", []) or []:
            if col not in source_columns:
                raise EventLogParseError(400, "MISSING_COLUMN", f"{col} is missing")

    @staticmethod
    def build_canonical_events(
        raw_events: list[dict[str, Any]], mapping: dict[str, Any],
    ) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        case_col = mapping["case_id_column"]
        act_col = mapping["activity_column"]
        ts_col = mapping["timestamp_column"]
        resource_col = mapping.get("resource_column")
        additional = mapping.get("additional_columns", []) or []
        for row in raw_events:
            ts = parse_timestamp(row.get(ts_col))
            attributes = {k: row.get(k) for k in additional if k in row}
            converted.append({
                "case_id": str(row.get(case_col)),
                "activity": str(row.get(act_col)),
                "timestamp": ts.isoformat(),
                "resource": row.get(resource_col) if resource_col else None,
                "attributes": attributes,
            })
        converted.sort(key=lambda item: (item["case_id"], item["timestamp"]))
        return converted

    def parse_csv(
        self, payload: bytes, mapping: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], set[str], list[dict[str, Any]]]:
        try:
            text = payload.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
        except Exception as exc:
            raise EventLogParseError(400, "INVALID_CSV_FORMAT", "csv parse failed") from exc
        if not rows:
            raise EventLogParseError(400, "INVALID_CSV_FORMAT", "csv has no rows")
        source_columns = set(rows[0].keys())
        self.validate_mapping(source_columns, mapping)
        return self.build_canonical_events(rows, mapping), source_columns, rows

    def parse_xes(
        self, payload: bytes,
    ) -> tuple[list[dict[str, Any]], set[str], list[dict[str, Any]], dict[str, Any]]:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise EventLogParseError(400, "INVALID_XES_FORMAT", "xes parse failed") from exc

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
            raise EventLogParseError(400, "INVALID_XES_FORMAT", "xes has no events")

        mapping = {
            "case_id_column": "case_id",
            "activity_column": "concept:name",
            "timestamp_column": "time:timestamp",
            "resource_column": "org:resource",
            "additional_columns": [],
        }
        source_columns = set().union(*(set(r.keys()) for r in rows))
        self.validate_mapping(source_columns, mapping)
        return self.build_canonical_events(rows, mapping), source_columns, rows, mapping
