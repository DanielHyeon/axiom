"""O5-3: HITL (Human-in-the-Loop) Review Queue Service."""
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger()


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


class HITLService:
    """HITL 리뷰 큐 관리. PostgreSQL 기반."""

    _DB_SCHEMA = "synapse"

    def __init__(self, database_url: str | None = None, ontology_service=None) -> None:
        self._database_url = database_url or settings.SCHEMA_EDIT_DATABASE_URL
        self._ontology = ontology_service
        self._ready = False

    def _connect(self):
        psycopg2, _ = _import_psycopg2()
        conn = psycopg2.connect(self._database_url)
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {self._DB_SCHEMA}, public")
        cur.close()
        return conn

    def _ensure_table(self) -> None:
        if self._ready:
            return
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self._DB_SCHEMA}")
        conn.commit()
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {self._DB_SCHEMA}.hitl_review_queue (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                node_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reviewer_id TEXT,
                submitted_at TIMESTAMPTZ DEFAULT now(),
                reviewed_at TIMESTAMPTZ,
                review_comment TEXT
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_hitl_case_status
            ON {self._DB_SCHEMA}.hitl_review_queue (case_id, status)
        """)
        conn.commit()
        cur.close()
        conn.close()
        self._ready = True
        logger.info("hitl_table_ensured")

    def submit_for_review(self, node_id: str, case_id: str, tenant_id: str) -> dict[str, Any]:
        """Submit a node for HITL review."""
        self._ensure_table()
        item_id = str(uuid.uuid4())
        conn = self._connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO hitl_review_queue (id, node_id, case_id, tenant_id, status)
            VALUES (%s, %s, %s, %s, 'pending')
            """,
            (item_id, node_id, case_id, tenant_id),
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info("hitl_submitted", item_id=item_id, node_id=node_id, case_id=case_id)
        return {"id": item_id, "node_id": node_id, "case_id": case_id, "status": "pending"}

    def list_items(self, case_id: str, status: str = "pending", limit: int = 50, offset: int = 0) -> dict[str, Any]:
        """List review items for a case."""
        self._ensure_table()
        _, cursor_cls = _import_psycopg2()
        conn = self._connect()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            """
            SELECT id, node_id, case_id, tenant_id, status, reviewer_id, submitted_at, reviewed_at, review_comment
            FROM hitl_review_queue
            WHERE case_id = %s AND status = %s
            ORDER BY submitted_at DESC
            LIMIT %s OFFSET %s
            """,
            (case_id, status, limit, offset),
        )
        rows = cur.fetchall()

        cur.execute(
            "SELECT COUNT(*) FROM hitl_review_queue WHERE case_id = %s AND status = %s",
            (case_id, status),
        )
        total = cur.fetchone()["count"]
        cur.close()
        conn.close()

        items = []
        for row in rows:
            item = dict(row)
            # Enrich with node data from ontology service
            if self._ontology:
                node = self._ontology.get_node(item["node_id"])
                if node:
                    item["node_name"] = node.get("properties", {}).get("name", item["node_id"])
                    item["node_layer"] = node.get("layer", "unknown")
            items.append(item)

        return {
            "items": items,
            "pagination": {"total": total, "limit": limit, "offset": offset},
        }

    async def approve(self, item_id: str, reviewer_id: str, comment: str = "") -> dict[str, Any]:
        """Approve a review item → set ontology node verified=true."""
        self._ensure_table()
        conn = self._connect()
        _, cursor_cls = _import_psycopg2()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            "SELECT node_id, case_id, tenant_id FROM hitl_review_queue WHERE id = %s AND status = 'pending'",
            (item_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            raise KeyError("Review item not found or already processed")

        node_id = row["node_id"]
        tenant_id = row["tenant_id"]

        # Update review status
        cur.execute(
            """
            UPDATE hitl_review_queue
            SET status = 'approved', reviewer_id = %s, reviewed_at = now(), review_comment = %s
            WHERE id = %s
            """,
            (reviewer_id, comment, item_id),
        )
        conn.commit()
        cur.close()
        conn.close()

        # Update ontology node verified=true
        if self._ontology:
            try:
                await self._ontology.update_node(
                    tenant_id=tenant_id,
                    node_id=node_id,
                    payload={"properties": {"verified": True}},
                )
            except Exception as exc:
                logger.warning("hitl_approve_node_update_failed", error=str(exc), node_id=node_id)

        logger.info("hitl_approved", item_id=item_id, node_id=node_id, reviewer_id=reviewer_id)
        return {"id": item_id, "status": "approved", "node_id": node_id}

    async def reject(self, item_id: str, reviewer_id: str, comment: str = "") -> dict[str, Any]:
        """Reject a review item → delete ontology node."""
        self._ensure_table()
        conn = self._connect()
        _, cursor_cls = _import_psycopg2()
        cur = conn.cursor(cursor_factory=cursor_cls)
        cur.execute(
            "SELECT node_id, case_id FROM hitl_review_queue WHERE id = %s AND status = 'pending'",
            (item_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            conn.close()
            raise KeyError("Review item not found or already processed")

        node_id = row["node_id"]

        # Update review status
        cur.execute(
            """
            UPDATE hitl_review_queue
            SET status = 'rejected', reviewer_id = %s, reviewed_at = now(), review_comment = %s
            WHERE id = %s
            """,
            (reviewer_id, comment, item_id),
        )
        conn.commit()
        cur.close()
        conn.close()

        # Delete ontology node
        if self._ontology:
            try:
                await self._ontology.delete_node(node_id=node_id)
            except Exception as exc:
                logger.warning("hitl_reject_node_delete_failed", error=str(exc), node_id=node_id)

        logger.info("hitl_rejected", item_id=item_id, node_id=node_id, reviewer_id=reviewer_id)
        return {"id": item_id, "status": "rejected", "node_id": node_id}
