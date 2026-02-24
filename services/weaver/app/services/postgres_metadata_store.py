from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.services.resilience import CircuitBreakerOpenError, SimpleCircuitBreaker, with_retry


class PostgresStoreUnavailableError(RuntimeError):
    pass


class PostgresMetadataStore:
    _DB_SCHEMA = "weaver"

    def __init__(self) -> None:
        self._pool = None
        self._breaker = SimpleCircuitBreaker(failure_threshold=3, reset_timeout_seconds=20.0)

    async def _get_pool(self):
        try:
            self._breaker.preflight()
        except CircuitBreakerOpenError as exc:
            raise PostgresStoreUnavailableError(str(exc)) from exc
        if self._pool is not None:
            return self._pool
        dsn = settings.postgres_dsn
        if not dsn:
            raise PostgresStoreUnavailableError("POSTGRES_DSN is required for pg metadata mode")
        try:
            import asyncpg  # type: ignore
        except Exception as exc:
            raise PostgresStoreUnavailableError("asyncpg package is not installed") from exc
        async def _create():
            return await asyncpg.create_pool(
                dsn=dsn, min_size=1, max_size=5,
                server_settings={"search_path": f"{self._DB_SCHEMA},public"},
            )
        try:
            self._pool = await with_retry(_create, retries=2, base_delay_seconds=0.05)
            self._breaker.on_success()
        except CircuitBreakerOpenError as exc:
            raise PostgresStoreUnavailableError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            self._breaker.on_failure()
            raise PostgresStoreUnavailableError(str(exc)) from exc
        await self._migrate()
        return self._pool

    async def _migrate(self) -> None:
        pool = self._pool
        async with pool.acquire() as conn:
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._DB_SCHEMA}")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weaver_metadata_datasources (
                    name TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    engine TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weaver_metadata_snapshots (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    case_id TEXT NOT NULL,
                    datasource TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    description TEXT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    completed_at TIMESTAMPTZ NULL,
                    summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    graph_data_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                    UNIQUE(case_id, datasource, version)
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weaver_metadata_glossary_terms (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL DEFAULT '',
                    term TEXT NOT NULL,
                    definition TEXT NOT NULL,
                    synonyms_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                );
                """
            )
            await conn.execute("ALTER TABLE weaver_metadata_datasources ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT ''")
            await conn.execute("ALTER TABLE weaver_metadata_snapshots ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT ''")
            await conn.execute("ALTER TABLE weaver_metadata_glossary_terms ADD COLUMN IF NOT EXISTS tenant_id TEXT NOT NULL DEFAULT ''")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_weaver_metadata_datasources_tenant ON weaver_metadata_datasources(tenant_id)")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_weaver_metadata_snapshots_tenant_case_ds ON weaver_metadata_snapshots(tenant_id, case_id, datasource)"
            )
            await conn.execute(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints
                        WHERE table_name = 'weaver_metadata_snapshots'
                          AND constraint_name = 'weaver_metadata_snapshots_case_id_datasource_version_key'
                    ) THEN
                        ALTER TABLE weaver_metadata_snapshots
                        DROP CONSTRAINT weaver_metadata_snapshots_case_id_datasource_version_key;
                    END IF;
                END
                $$;
                """
            )
            await conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_weaver_metadata_snapshots_tenant_case_ds_ver ON weaver_metadata_snapshots(tenant_id, case_id, datasource, version)"
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_weaver_metadata_glossary_terms_tenant ON weaver_metadata_glossary_terms(tenant_id)")

    async def health_check(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")

    async def upsert_datasource(self, name: str, engine: str, tenant_id: str | None = None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO weaver_metadata_datasources(name, tenant_id, engine)
                VALUES($1, $2, $3)
                ON CONFLICT(name) DO UPDATE SET engine = EXCLUDED.engine, tenant_id = EXCLUDED.tenant_id
                """,
                name,
                tenant_id or "",
                engine,
            )

    async def delete_datasource(self, name: str, tenant_id: str | None = None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                await conn.execute("DELETE FROM weaver_metadata_datasources WHERE name = $1", name)
            else:
                await conn.execute("DELETE FROM weaver_metadata_datasources WHERE name = $1 AND tenant_id = $2", name, tenant_id)

    async def next_snapshot_version(self, case_id: str, datasource: str, tenant_id: str | None = None) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                row = await conn.fetchrow(
                    "SELECT COALESCE(MAX(version), 0) AS max_version FROM weaver_metadata_snapshots WHERE case_id = $1 AND datasource = $2",
                    case_id,
                    datasource,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT COALESCE(MAX(version), 0) AS max_version FROM weaver_metadata_snapshots WHERE tenant_id = $1 AND case_id = $2 AND datasource = $3",
                    tenant_id,
                    case_id,
                    datasource,
                )
            return int(row["max_version"]) + 1

    async def save_snapshot(self, item: dict[str, Any], tenant_id: str | None = None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO weaver_metadata_snapshots(
                    id, tenant_id, case_id, datasource, version, status, description, created_by, created_at, completed_at, summary_json, graph_data_json
                )
                VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12::jsonb)
                ON CONFLICT(id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    status = EXCLUDED.status,
                    description = EXCLUDED.description,
                    completed_at = EXCLUDED.completed_at,
                    summary_json = EXCLUDED.summary_json,
                    graph_data_json = EXCLUDED.graph_data_json
                """,
                item["id"],
                tenant_id if tenant_id is not None else str(item.get("tenant_id") or ""),
                item["case_id"],
                item["datasource"],
                int(item["version"]),
                item["status"],
                item.get("description"),
                item["created_by"],
                item["created_at"],
                item.get("completed_at"),
                json.dumps(item.get("summary", {}), ensure_ascii=True),
                json.dumps(item.get("graph_data", {}), ensure_ascii=True),
            )

    async def list_snapshots(self, case_id: str, datasource: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                rows = await conn.fetch(
                    """
                    SELECT * FROM weaver_metadata_snapshots
                    WHERE case_id = $1 AND datasource = $2
                    ORDER BY version DESC
                    """,
                    case_id,
                    datasource,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM weaver_metadata_snapshots
                    WHERE tenant_id = $1 AND case_id = $2 AND datasource = $3
                    ORDER BY version DESC
                    """,
                    tenant_id,
                    case_id,
                    datasource,
                )
        return [self._snapshot_row_to_item(r) for r in rows]

    async def get_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM weaver_metadata_snapshots
                    WHERE case_id = $1 AND datasource = $2 AND id = $3
                    """,
                    case_id,
                    datasource,
                    snapshot_id,
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM weaver_metadata_snapshots
                    WHERE tenant_id = $1 AND case_id = $2 AND datasource = $3 AND id = $4
                    """,
                    tenant_id,
                    case_id,
                    datasource,
                    snapshot_id,
                )
        return self._snapshot_row_to_item(row) if row else None

    async def delete_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str | None = None) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                result = await conn.execute(
                    """
                    DELETE FROM weaver_metadata_snapshots
                    WHERE case_id = $1 AND datasource = $2 AND id = $3
                    """,
                    case_id,
                    datasource,
                    snapshot_id,
                )
            else:
                result = await conn.execute(
                    """
                    DELETE FROM weaver_metadata_snapshots
                    WHERE tenant_id = $1 AND case_id = $2 AND datasource = $3 AND id = $4
                    """,
                    tenant_id,
                    case_id,
                    datasource,
                    snapshot_id,
                )
        return result.endswith("1")

    async def save_glossary_term(self, item: dict[str, Any], tenant_id: str | None = None) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO weaver_metadata_glossary_terms(id, tenant_id, term, definition, synonyms_json, created_at, updated_at)
                VALUES($1,$2,$3,$4,$5::jsonb,$6,$7)
                ON CONFLICT(id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    term = EXCLUDED.term,
                    definition = EXCLUDED.definition,
                    synonyms_json = EXCLUDED.synonyms_json,
                    updated_at = EXCLUDED.updated_at
                """,
                item["id"],
                tenant_id if tenant_id is not None else str(item.get("tenant_id") or ""),
                item["term"],
                item["definition"],
                json.dumps(item.get("synonyms", []), ensure_ascii=True),
                item["created_at"],
                item["updated_at"],
            )

    async def list_glossary_terms(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                rows = await conn.fetch("SELECT * FROM weaver_metadata_glossary_terms ORDER BY created_at DESC")
            else:
                rows = await conn.fetch(
                    "SELECT * FROM weaver_metadata_glossary_terms WHERE tenant_id = $1 ORDER BY created_at DESC",
                    tenant_id,
                )
        return [self._glossary_row_to_item(r) for r in rows]

    async def get_glossary_term(self, term_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                row = await conn.fetchrow("SELECT * FROM weaver_metadata_glossary_terms WHERE id = $1", term_id)
            else:
                row = await conn.fetchrow(
                    "SELECT * FROM weaver_metadata_glossary_terms WHERE id = $1 AND tenant_id = $2",
                    term_id,
                    tenant_id,
                )
        return self._glossary_row_to_item(row) if row else None

    async def delete_glossary_term(self, term_id: str, tenant_id: str | None = None) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                result = await conn.execute("DELETE FROM weaver_metadata_glossary_terms WHERE id = $1", term_id)
            else:
                result = await conn.execute(
                    "DELETE FROM weaver_metadata_glossary_terms WHERE id = $1 AND tenant_id = $2",
                    term_id,
                    tenant_id,
                )
        return result.endswith("1")

    async def search_glossary_terms(self, q: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        pool = await self._get_pool()
        pattern = f"%{q.lower()}%"
        async with pool.acquire() as conn:
            if tenant_id is None:
                rows = await conn.fetch(
                    """
                    SELECT * FROM weaver_metadata_glossary_terms
                    WHERE LOWER(term) LIKE $1 OR LOWER(definition) LIKE $1
                    ORDER BY created_at DESC
                    """,
                    pattern,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM weaver_metadata_glossary_terms
                    WHERE tenant_id = $1 AND (LOWER(term) LIKE $2 OR LOWER(definition) LIKE $2)
                    ORDER BY created_at DESC
                    """,
                    tenant_id,
                    pattern,
                )
        return [self._glossary_row_to_item(r) for r in rows]

    async def stats(self, tenant_id: str | None = None) -> dict[str, int]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if tenant_id is None:
                ds = await conn.fetchval("SELECT COUNT(*) FROM weaver_metadata_datasources")
                tm = await conn.fetchval("SELECT COUNT(*) FROM weaver_metadata_glossary_terms")
                sn = await conn.fetchval("SELECT COUNT(*) FROM weaver_metadata_snapshots")
            else:
                ds = await conn.fetchval("SELECT COUNT(*) FROM weaver_metadata_datasources WHERE tenant_id = $1", tenant_id)
                tm = await conn.fetchval("SELECT COUNT(*) FROM weaver_metadata_glossary_terms WHERE tenant_id = $1", tenant_id)
                sn = await conn.fetchval("SELECT COUNT(*) FROM weaver_metadata_snapshots WHERE tenant_id = $1", tenant_id)
        return {"datasources": int(ds or 0), "glossary_terms": int(tm or 0), "snapshots": int(sn or 0)}

    @staticmethod
    def _snapshot_row_to_item(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"] if "tenant_id" in row else "",
            "datasource": row["datasource"],
            "case_id": row["case_id"],
            "version": int(row["version"]),
            "status": row["status"],
            "description": row["description"],
            "created_by": row["created_by"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "summary": row["summary_json"] or {},
            "graph_data": row["graph_data_json"] or {},
        }

    @staticmethod
    def _glossary_row_to_item(row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"] if "tenant_id" in row else "",
            "term": row["term"],
            "definition": row["definition"],
            "synonyms": row["synonyms_json"] or [],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }


postgres_metadata_store = PostgresMetadataStore()
