import uuid
from typing import Any

from app.services.schema_edit_store import SchemaEditStore


class SchemaEditDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class SchemaEditService:
    def __init__(self) -> None:
        self._store = SchemaEditStore()

    def clear(self) -> None:
        self._store.clear()

    def list_tables(self, tenant_id: str) -> dict[str, Any]:
        rows = self._store.list_tables(tenant_id)
        return {
            "tables": [
                {
                    **row,
                    "has_embedding": bool(row["has_embedding"]),
                }
                for row in rows
            ],
            "total": len(rows),
        }

    def get_table(self, tenant_id: str, table_name: str) -> dict[str, Any]:
        table = self._store.get_table(tenant_id, table_name)
        if not table:
            raise SchemaEditDomainError(400, "INVALID_TABLE_NAME", "table not found")
        table["has_embedding"] = bool(table["has_embedding"])
        return table

    def update_table_description(self, tenant_id: str, table_name: str, description: str) -> dict[str, Any]:
        if not description or len(description) > 500:
            raise SchemaEditDomainError(400, "INVALID_REQUEST", "description must be 1..500 chars")
        updated_at = self._store.update_table_description(tenant_id, table_name, description)
        if not updated_at:
            raise SchemaEditDomainError(400, "INVALID_TABLE_NAME", "table not found")
        return {
            "table_name": table_name,
            "description": description,
            "embedding_updated": True,
            "updated_at": updated_at,
        }

    def update_column_description(self, tenant_id: str, table_name: str, column_name: str, description: str) -> dict[str, Any]:
        table = self._store.get_table(tenant_id, table_name)
        if not table:
            raise SchemaEditDomainError(400, "INVALID_TABLE_NAME", "table not found")
        if not description or len(description) > 500:
            raise SchemaEditDomainError(400, "INVALID_REQUEST", "description must be 1..500 chars")
        found_column = any(item["name"] == column_name for item in table["columns"])
        if not found_column:
            raise SchemaEditDomainError(400, "INVALID_COLUMN_NAME", "column not found")
        updated_at = self._store.update_column_description(tenant_id, table_name, column_name, description)
        if not updated_at:
            raise SchemaEditDomainError(400, "INVALID_COLUMN_NAME", "column not found")
        return {
            "table_name": table_name,
            "column_name": column_name,
            "description": description,
            "embedding_updated": True,
            "updated_at": updated_at,
        }

    def list_relationships(self, tenant_id: str) -> dict[str, Any]:
        rows = self._store.list_relationships(tenant_id)
        return {
            "relationships": [
                {
                    "id": row["id"],
                    "source_table": row["source_table"],
                    "source_column": row["source_column"],
                    "target_table": row["target_table"],
                    "target_column": row["target_column"],
                    "type": row["relationship_type"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ],
            "total": len(rows),
        }

    def create_relationship(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        source_table = str(payload.get("source_table") or "").strip()
        source_column = str(payload.get("source_column") or "").strip()
        target_table = str(payload.get("target_table") or "").strip()
        target_column = str(payload.get("target_column") or "").strip()
        rel_type = str(payload.get("relationship_type") or "FK_TO").strip()
        description = payload.get("description")

        source = self._store.get_table(tenant_id, source_table)
        target = self._store.get_table(tenant_id, target_table)
        if not source or not target:
            raise SchemaEditDomainError(400, "INVALID_TABLE_NAME", "table not found")
        if source_table == target_table and source_column == target_column:
            raise SchemaEditDomainError(400, "SELF_REFERENCE", "self reference is not allowed")
        if not any(item["name"] == source_column for item in source["columns"]):
            raise SchemaEditDomainError(400, "INVALID_COLUMN_NAME", "source column not found")
        if not any(item["name"] == target_column for item in target["columns"]):
            raise SchemaEditDomainError(400, "INVALID_COLUMN_NAME", "target column not found")
        if self._store.relationship_exists(tenant_id, source_table, source_column, target_table, target_column):
            raise SchemaEditDomainError(400, "DUPLICATE_RELATIONSHIP", "relationship already exists")

        rel_id = f"rel-{uuid.uuid4()}"
        created = self._store.insert_relationship(
            tenant_id=tenant_id,
            rel_id=rel_id,
            source_table=source_table,
            source_column=source_column,
            target_table=target_table,
            target_column=target_column,
            relationship_type=rel_type,
            description=description,
        )
        return {
            "id": created["id"],
            "source_table": created["source_table"],
            "source_column": created["source_column"],
            "target_table": created["target_table"],
            "target_column": created["target_column"],
            "type": created["relationship_type"],
            "description": created["description"],
            "created_at": created["created_at"],
        }

    def delete_relationship(self, tenant_id: str, rel_id: str) -> dict[str, Any]:
        deleted = self._store.delete_relationship(tenant_id, rel_id)
        if not deleted:
            raise SchemaEditDomainError(404, "RELATIONSHIP_NOT_FOUND", "relationship not found")
        return {"deleted": True, "id": rel_id}

    def rebuild_table_embedding(self, tenant_id: str, table_name: str) -> dict[str, Any]:
        table = self._store.get_table(tenant_id, table_name)
        if not table:
            raise SchemaEditDomainError(400, "INVALID_TABLE_NAME", "table not found")
        updated_at = self._store.touch_table_embedding(tenant_id, table_name)
        return {"table_name": table_name, "embedding_updated": True, "updated_at": updated_at}

    def batch_update_embeddings(self, tenant_id: str, target: str = "all", force: bool = False) -> dict[str, Any]:
        if target not in {"all", "tables", "columns"}:
            raise SchemaEditDomainError(400, "INVALID_REQUEST", "target must be all|tables|columns")
        task_id = f"task-{uuid.uuid4()}"
        estimated = 0
        if target in {"all", "tables"}:
            estimated += self._store.batch_touch_tables(tenant_id, force=force)
        if target in {"all", "columns"}:
            estimated += self._store.count_columns(tenant_id)
        return {"task_id": task_id, "target": target, "estimated_count": estimated, "status": "processing"}


schema_edit_service = SchemaEditService()
