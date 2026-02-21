import sys
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _import_psycopg2():
    try:
        import psycopg2  # type: ignore
        from psycopg2.extras import RealDictCursor  # type: ignore

        return psycopg2, RealDictCursor
    except Exception:
        for path in ("/usr/lib/python3/dist-packages", "/home/daniel/.local/lib/python3.12/site-packages"):
            if path not in sys.path:
                sys.path.append(path)
        import psycopg2  # type: ignore
        from psycopg2.extras import RealDictCursor  # type: ignore

        return psycopg2, RealDictCursor


class SchemaEditStore:
    def __init__(self, database_url: str | None = None) -> None:
        self._database_url = database_url or settings.SCHEMA_EDIT_DATABASE_URL
        self._schema_ready = False

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        return psycopg2.connect(self._database_url)

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_tables (
              tenant_id TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              column_count INTEGER NOT NULL,
              has_embedding BOOLEAN NOT NULL,
              last_updated TIMESTAMPTZ NOT NULL,
              PRIMARY KEY (tenant_id, name)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_columns (
              tenant_id TEXT NOT NULL,
              table_name TEXT NOT NULL,
              name TEXT NOT NULL,
              data_type TEXT NOT NULL,
              description TEXT NOT NULL,
              PRIMARY KEY (tenant_id, table_name, name)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_relationships (
              tenant_id TEXT NOT NULL,
              id TEXT NOT NULL,
              source_table TEXT NOT NULL,
              source_column TEXT NOT NULL,
              target_table TEXT NOT NULL,
              target_column TEXT NOT NULL,
              relationship_type TEXT NOT NULL,
              description TEXT,
              created_at TIMESTAMPTZ NOT NULL,
              PRIMARY KEY (tenant_id, id)
            )
            """
        )
        conn.commit()
        cur.close()
        conn.close()
        self._schema_ready = True

    def clear(self) -> None:
        self._ensure_schema()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM schema_relationships")
        cur.execute("DELETE FROM schema_columns")
        cur.execute("DELETE FROM schema_tables")
        conn.commit()
        cur.close()
        conn.close()

    def ensure_seed(self, tenant_id: str) -> None:
        self._ensure_schema()
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM schema_tables WHERE tenant_id = %s", (tenant_id,))
        count = cur.fetchone()[0]
        if count:
            cur.close()
            conn.close()
            return
        now = datetime.now(timezone.utc)
        cur.executemany(
            """
            INSERT INTO schema_tables(tenant_id, name, description, row_count, column_count, has_embedding, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (tenant_id, "processes", "프로세스 실행 내역", 1250, 4, True, now),
                (tenant_id, "organizations", "이해관계자 정보", 320, 2, True, now),
            ],
        )
        cur.executemany(
            """
            INSERT INTO schema_columns(tenant_id, table_name, name, data_type, description)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [
                (tenant_id, "processes", "id", "uuid", "PK"),
                (tenant_id, "processes", "org_id", "uuid", "조직 ID"),
                (tenant_id, "processes", "efficiency_rate", "float", "효율성 비율"),
                (tenant_id, "processes", "status", "varchar", "상태"),
                (tenant_id, "organizations", "id", "uuid", "PK"),
                (tenant_id, "organizations", "name", "varchar", "조직명"),
            ],
        )
        conn.commit()
        cur.close()
        conn.close()

    def list_tables(self, tenant_id: str) -> list[dict[str, Any]]:
        self.ensure_seed(tenant_id)
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            """
            SELECT name, description, row_count, column_count, has_embedding, last_updated
            FROM schema_tables WHERE tenant_id = %s ORDER BY name
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def get_table(self, tenant_id: str, table_name: str) -> dict[str, Any] | None:
        self.ensure_seed(tenant_id)
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            """
            SELECT name, description, row_count, column_count, has_embedding, last_updated
            FROM schema_tables WHERE tenant_id = %s AND name = %s
            """,
            (tenant_id, table_name),
        )
        table = cur.fetchone()
        if not table:
            cur.close()
            conn.close()
            return None
        cur.execute(
            """
            SELECT name, data_type, description
            FROM schema_columns WHERE tenant_id = %s AND table_name = %s ORDER BY name
            """,
            (tenant_id, table_name),
        )
        columns = cur.fetchall()
        cur.close()
        conn.close()
        return {**dict(table), "columns": [dict(row) for row in columns]}

    def update_table_description(self, tenant_id: str, table_name: str, description: str) -> str | None:
        self.ensure_seed(tenant_id)
        now = datetime.now(timezone.utc)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE schema_tables
            SET description = %s, has_embedding = TRUE, last_updated = %s
            WHERE tenant_id = %s AND name = %s
            """,
            (description, now, tenant_id, table_name),
        )
        updated = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        if updated == 0:
            return None
        return now.isoformat()

    def update_column_description(self, tenant_id: str, table_name: str, column_name: str, description: str) -> str | None:
        self.ensure_seed(tenant_id)
        now = datetime.now(timezone.utc)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE schema_columns
            SET description = %s
            WHERE tenant_id = %s AND table_name = %s AND name = %s
            """,
            (description, tenant_id, table_name, column_name),
        )
        updated = cur.rowcount
        if updated:
            cur.execute(
                "UPDATE schema_tables SET last_updated = %s WHERE tenant_id = %s AND name = %s",
                (now, tenant_id, table_name),
            )
        conn.commit()
        cur.close()
        conn.close()
        if updated == 0:
            return None
        return now.isoformat()

    def list_relationships(self, tenant_id: str) -> list[dict[str, Any]]:
        self.ensure_seed(tenant_id)
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            """
            SELECT id, source_table, source_column, target_table, target_column, relationship_type, description, created_at
            FROM schema_relationships WHERE tenant_id = %s ORDER BY id
            """,
            (tenant_id,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(row) for row in rows]

    def relationship_exists(
        self,
        tenant_id: str,
        source_table: str,
        source_column: str,
        target_table: str,
        target_column: str,
    ) -> bool:
        self.ensure_seed(tenant_id)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM schema_relationships
            WHERE tenant_id = %s AND source_table = %s AND source_column = %s AND target_table = %s AND target_column = %s
            LIMIT 1
            """,
            (tenant_id, source_table, source_column, target_table, target_column),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return bool(row)

    def insert_relationship(
        self,
        tenant_id: str,
        rel_id: str,
        source_table: str,
        source_column: str,
        target_table: str,
        target_column: str,
        relationship_type: str,
        description: str | None,
    ) -> dict[str, Any]:
        self.ensure_seed(tenant_id)
        created_at = datetime.now(timezone.utc)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO schema_relationships(
              tenant_id, id, source_table, source_column, target_table, target_column, relationship_type, description, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                tenant_id,
                rel_id,
                source_table,
                source_column,
                target_table,
                target_column,
                relationship_type,
                description,
                created_at,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
        return {
            "id": rel_id,
            "source_table": source_table,
            "source_column": source_column,
            "target_table": target_table,
            "target_column": target_column,
            "relationship_type": relationship_type,
            "description": description,
            "created_at": created_at.isoformat(),
        }

    def delete_relationship(self, tenant_id: str, rel_id: str) -> bool:
        self.ensure_seed(tenant_id)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM schema_relationships WHERE tenant_id = %s AND id = %s", (tenant_id, rel_id))
        deleted = cur.rowcount > 0
        conn.commit()
        cur.close()
        conn.close()
        return deleted

    def touch_table_embedding(self, tenant_id: str, table_name: str) -> str | None:
        table = self.get_table(tenant_id, table_name)
        if not table:
            return None
        return self.update_table_description(tenant_id, table_name, table["description"])

    def batch_touch_tables(self, tenant_id: str, force: bool) -> int:
        self.ensure_seed(tenant_id)
        now = datetime.now(timezone.utc)
        conn = self._connect()
        cur = conn.cursor()
        if force:
            cur.execute(
                "UPDATE schema_tables SET has_embedding = TRUE, last_updated = %s WHERE tenant_id = %s",
                (now, tenant_id),
            )
        else:
            cur.execute(
                "UPDATE schema_tables SET has_embedding = TRUE, last_updated = %s WHERE tenant_id = %s AND has_embedding = FALSE",
                (now, tenant_id),
            )
        count = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return int(count or 0)

    def count_columns(self, tenant_id: str) -> int:
        self.ensure_seed(tenant_id)
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM schema_columns WHERE tenant_id = %s", (tenant_id,))
        value = cur.fetchone()[0]
        cur.close()
        conn.close()
        return int(value or 0)
