"""
EventLog Worker 파서 (worker-system.md §3.6).
CSV/XES 스트리밍 검증 및 이벤트 추출. case 경계 보장은 청킹 시 동일 case가 분리되지 않도록 함.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any, Iterator

# CSV 필수 컬럼 (worker-system §3.6)
CSV_REQUIRED = {"case_id", "activity", "timestamp"}


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]


def _normalize_headers(row: list[str]) -> list[str]:
    return [h.strip().lower() for h in row]


def validate_csv(content: bytes) -> ValidationResult:
    """CSV 헤더 검증: 필수 컬럼 존재 확인."""
    errors: list[str] = []
    try:
        text = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        header = next(reader, None)
        if not header:
            return ValidationResult(False, ["CSV has no header"])
        normalized = set(_normalize_headers(header))
        missing = CSV_REQUIRED - normalized
        if missing:
            errors.append(f"Missing required columns: {missing}")
        return ValidationResult(len(errors) == 0, errors)
    except Exception as e:
        return ValidationResult(False, [str(e)])


def _find_column(fieldnames: list[str], names: set[str]) -> str | None:
    norm = {f.strip().lower(): f for f in fieldnames}
    for n in names:
        if n in norm:
            return norm[n]
    return None


def parse_csv_chunks(
    content: bytes,
    chunk_size: int,
    column_mapping: dict[str, str] | None = None,
) -> Iterator[list[dict[str, Any]]]:
    """CSV를 청크로 파싱. 동일 case_id의 이벤트가 청크 경계에서 분리되지 않도록 함."""
    mapping = column_mapping or {}
    text = content.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return
    case_key = mapping.get("case_id") or _find_column(reader.fieldnames, {"case_id"})
    activity_key = mapping.get("activity") or _find_column(reader.fieldnames, {"activity", "act"})
    timestamp_key = mapping.get("timestamp") or _find_column(reader.fieldnames, {"timestamp", "time"})
    if not case_key or not activity_key or not timestamp_key:
        return

    chunk: list[dict[str, Any]] = []
    current_case: str | None = None
    for row in reader:
        case_val = (row.get(case_key) or "").strip()
        evt = {
            "case_id": case_val,
            "activity": (row.get(activity_key) or "").strip(),
            "timestamp": (row.get(timestamp_key) or "").strip(),
        }
        if current_case is not None and case_val != current_case and len(chunk) >= chunk_size:
            yield chunk
            chunk = []
        chunk.append(evt)
        current_case = case_val
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
            current_case = None
    if chunk:
        yield chunk


def validate_xes(content: bytes) -> ValidationResult:
    """XES 최소 구조 검증: <log>, <trace>, <event> 존재."""
    errors: list[str] = []
    try:
        text = content.decode("utf-8", errors="replace")
        if "<log" not in text and "<xes" not in text.lower():
            errors.append("XES: root log element not found")
        if "<trace>" not in text and "<trace " not in text:
            errors.append("XES: trace element not found")
        if "<event>" not in text and "<event " not in text:
            errors.append("XES: event element not found")
        return ValidationResult(len(errors) == 0, errors)
    except Exception as e:
        return ValidationResult(False, [str(e)])


# XES 파싱은 복잡하므로 간단한 라인/태그 기반 추출. pm4py 등 사용 시 의존성 증가.
# 여기서는 전체 파일을 Synapse에 보내고 Synapse가 파싱하도록 할 수 있음.
def parse_xes_chunks(
    content: bytes,
    chunk_size: int,
) -> Iterator[list[dict[str, Any]]]:
    """XES에서 이벤트를 추출해 청크로 yield. 단순 구현: <event> 내 key/value 수집."""
    text = content.decode("utf-8", errors="replace")
    # 매우 단순한 파서: <event>...</event> 블록에서 string key/value 추출
    event_blocks = re.findall(r"<event[^>]*>(.*?)</event>", text, re.DOTALL | re.IGNORECASE)
    chunk: list[dict[str, Any]] = []
    for block in event_blocks:
        evt: dict[str, Any] = {}
        for m in re.finditer(r'<string\s+key="([^"]+)"\s+value="([^"]*)"', block):
            evt[m.group(1)] = m.group(2)
        if evt:
            # 표준 필드명 정규화
            case_id = evt.get("concept:name") or evt.get("case:id") or evt.get("case_id") or ""
            activity = evt.get("concept:name") or evt.get("activity") or evt.get("org:resource") or ""
            ts = evt.get("time:timestamp") or evt.get("timestamp") or ""
            chunk.append({"case_id": str(case_id), "activity": str(activity), "timestamp": str(ts), **evt})
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
