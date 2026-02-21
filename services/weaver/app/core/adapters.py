from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DataSourceAdapter(ABC):
    @abstractmethod
    async def test_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def extract_schema(self) -> dict[str, Any]:
        raise NotImplementedError


class PostgresAdapter(DataSourceAdapter):
    def __init__(self, dsn: str, *, connect_timeout_seconds: float = 3.0, max_tables: int = 200) -> None:
        if not dsn:
            raise ValueError("dsn is required")
        self.dsn = dsn
        self.connect_timeout_seconds = connect_timeout_seconds
        self.max_tables = max_tables

    def _is_mock(self) -> bool:
        return self.dsn.startswith("mock_")

    async def extract_schema(self) -> dict[str, Any]:
        if self._is_mock():
            return {
                "engine": "postgresql",
                "schema": "public",
                "tables": [
                    {
                        "name": "users",
                        "columns": [
                            {"name": "id", "type": "uuid", "nullable": False},
                            {"name": "email", "type": "text", "nullable": False},
                        ],
                    },
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "id", "type": "uuid", "nullable": False},
                            {"name": "user_id", "type": "uuid", "nullable": False},
                            {"name": "total_amount", "type": "numeric", "nullable": False},
                        ],
                    },
                ],
            }
        try:
            import asyncpg  # type: ignore
        except Exception as exc:
            raise RuntimeError("asyncpg package is required for postgres adapter") from exc

        conn = await asyncpg.connect(dsn=self.dsn, timeout=self.connect_timeout_seconds)
        try:
            rows = await conn.fetch(
                """
                SELECT
                    t.table_name,
                    c.column_name,
                    c.data_type,
                    (c.is_nullable = 'YES') AS is_nullable,
                    c.ordinal_position
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c
                  ON c.table_schema = t.table_schema
                 AND c.table_name = t.table_name
                WHERE t.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                ORDER BY t.table_name, c.ordinal_position
                LIMIT $1
                """,
                self.max_tables * 100,
            )
        finally:
            await conn.close()

        tables: dict[str, dict[str, Any]] = {}
        for row in rows:
            table_name = str(row["table_name"])
            bucket = tables.setdefault(table_name, {"name": table_name, "columns": []})
            col_name = row.get("column_name")
            if not col_name:
                continue
            bucket["columns"].append(
                {
                    "name": str(col_name),
                    "type": str(row.get("data_type") or "text"),
                    "nullable": bool(row.get("is_nullable", True)),
                }
            )
        return {"engine": "postgresql", "schema": "public", "tables": list(tables.values())}

    async def test_connection(self) -> bool:
        if self._is_mock():
            return True
        try:
            import asyncpg  # type: ignore
        except Exception:
            return False
        try:
            conn = await asyncpg.connect(dsn=self.dsn, timeout=self.connect_timeout_seconds)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            return True
        except Exception:
            return False
