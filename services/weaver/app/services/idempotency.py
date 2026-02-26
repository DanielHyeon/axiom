from __future__ import annotations

import hashlib
from datetime import datetime


def realtime_query_id(
    normalized_sql: str,
    tenant_id: str,
    datasource_id: str,
    request_id: str,
) -> str:
    """Deterministic query_id for realtime (single-log) path."""
    data = f"{normalized_sql}|{tenant_id}|{datasource_id}|{request_id}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]


def batch_query_id(
    normalized_sql: str,
    tenant_id: str,
    datasource_id: str,
    executed_at: datetime,
) -> str:
    """Deterministic query_id for batch path — 5-minute bucket rounding."""
    bucket = executed_at.replace(
        minute=(executed_at.minute // 5) * 5, second=0, microsecond=0,
    )
    data = f"{normalized_sql}|{tenant_id}|{datasource_id}|{bucket.isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32]
