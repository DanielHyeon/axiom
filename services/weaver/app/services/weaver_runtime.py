from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WeaverRuntime:
    def __init__(self) -> None:
        self._id_seq = count(1)
        self.started_at = _now()
        self.datasources: dict[str, dict[str, Any]] = {}
        self.materialized_tables: dict[str, dict[str, Any]] = {}
        self.query_jobs: dict[str, dict[str, Any]] = {}
        self.query_models: dict[str, dict[str, Any]] = {}
        self.knowledge_bases: dict[str, dict[str, Any]] = {}
        self.glossary: dict[str, dict[str, Any]] = {}
        self.snapshots: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        self.table_tags: dict[tuple[str, str, str, str], set[str]] = {}
        self.column_tags: dict[tuple[str, str, str, str, str], set[str]] = {}

    def clear(self) -> None:
        self.datasources.clear()
        self.materialized_tables.clear()
        self.query_jobs.clear()
        self.query_models.clear()
        self.knowledge_bases.clear()
        self.glossary.clear()
        self.snapshots.clear()
        self.table_tags.clear()
        self.column_tags.clear()

    def new_id(self, prefix: str) -> str:
        return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000)}-{next(self._id_seq)}"

    def create_datasource(
        self,
        payload: dict[str, Any],
        *,
        storage_key: str | None = None,
        display_name: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        name = display_name or payload["name"]
        engine = payload["engine"]
        connection = dict(payload["connection"])
        ds = {
            "name": name,
            "tenant_id": tenant_id or "",
            "engine": engine,
            "connection": connection,
            "description": payload.get("description"),
            "status": "connected",
            "created_at": _now(),
            "metadata_extracted": False,
            "tables_count": None,
            "schemas_count": None,
        }
        self.datasources[storage_key or name] = ds
        return ds


weaver_runtime = WeaverRuntime()
