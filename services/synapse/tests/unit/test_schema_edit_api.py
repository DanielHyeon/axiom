import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.schema_edit_service import schema_edit_service

AUTH = {"Authorization": "Bearer local-oracle-token"}


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def setup_function():
    class FakeStore:
        def __init__(self):
            self.tables = {}
            self.relationships = {}

        def _seed_tables(self):
            return {
                "processes": {
                    "name": "processes",
                    "description": "프로세스 실행 내역",
                    "row_count": 1250,
                    "column_count": 4,
                    "has_embedding": True,
                    "last_updated": "2024-01-01T00:00:00+00:00",
                    "columns": [
                        {"name": "id", "data_type": "uuid", "description": "PK"},
                        {"name": "org_id", "data_type": "uuid", "description": "조직 ID"},
                        {"name": "efficiency_rate", "data_type": "float", "description": "효율성 비율"},
                        {"name": "status", "data_type": "varchar", "description": "상태"},
                    ],
                },
                "organizations": {
                    "name": "organizations",
                    "description": "이해관계자 정보",
                    "row_count": 320,
                    "column_count": 2,
                    "has_embedding": True,
                    "last_updated": "2024-01-01T00:00:00+00:00",
                    "columns": [
                        {"name": "id", "data_type": "uuid", "description": "PK"},
                        {"name": "name", "data_type": "varchar", "description": "조직명"},
                    ],
                },
            }

        def _ensure_tenant(self, tenant_id):
            if tenant_id not in self.tables:
                self.tables[tenant_id] = self._seed_tables()
            if tenant_id not in self.relationships:
                self.relationships[tenant_id] = {}

        def clear(self):
            self.relationships = {}

        def list_tables(self, tenant_id):
            self._ensure_tenant(tenant_id)
            return [
                {
                    "name": value["name"],
                    "description": value["description"],
                    "row_count": value["row_count"],
                    "column_count": value["column_count"],
                    "has_embedding": value["has_embedding"],
                    "last_updated": value["last_updated"],
                }
                for value in self.tables[tenant_id].values()
            ]

        def get_table(self, tenant_id, table_name):
            self._ensure_tenant(tenant_id)
            return self.tables[tenant_id].get(table_name)

        def update_table_description(self, tenant_id, table_name, description):
            self._ensure_tenant(tenant_id)
            row = self.tables[tenant_id].get(table_name)
            if not row:
                return None
            row["description"] = description
            return "2024-01-02T00:00:00+00:00"

        def update_column_description(self, tenant_id, table_name, column_name, description):
            self._ensure_tenant(tenant_id)
            row = self.tables[tenant_id].get(table_name)
            if not row:
                return None
            for col in row["columns"]:
                if col["name"] == column_name:
                    col["description"] = description
                    return "2024-01-02T00:00:00+00:00"
            return None

        def list_relationships(self, tenant_id):
            self._ensure_tenant(tenant_id)
            return list(self.relationships[tenant_id].values())

        def relationship_exists(self, tenant_id, source_table, source_column, target_table, target_column):
            self._ensure_tenant(tenant_id)
            for rel in self.relationships[tenant_id].values():
                if (
                    rel["source_table"] == source_table
                    and rel["source_column"] == source_column
                    and rel["target_table"] == target_table
                    and rel["target_column"] == target_column
                ):
                    return True
            return False

        def insert_relationship(self, tenant_id, rel_id, source_table, source_column, target_table, target_column, relationship_type, description):
            self._ensure_tenant(tenant_id)
            row = {
                "id": rel_id,
                "source_table": source_table,
                "source_column": source_column,
                "target_table": target_table,
                "target_column": target_column,
                "relationship_type": relationship_type,
                "description": description,
                "created_at": "2024-01-02T00:00:00+00:00",
            }
            self.relationships[tenant_id][rel_id] = row
            return row

        def delete_relationship(self, tenant_id, rel_id):
            self._ensure_tenant(tenant_id)
            return self.relationships[tenant_id].pop(rel_id, None) is not None

        def touch_table_embedding(self, tenant_id, table_name):
            self._ensure_tenant(tenant_id)
            return "2024-01-02T00:00:00+00:00"

        def batch_touch_tables(self, tenant_id, force):
            self._ensure_tenant(tenant_id)
            return len(self.tables[tenant_id])

        def count_columns(self, tenant_id):
            self._ensure_tenant(tenant_id)
            return sum(len(t["columns"]) for t in self.tables[tenant_id].values())

    schema_edit_service._store = FakeStore()


@pytest.mark.asyncio
async def test_schema_edit_full_flow(ac: AsyncClient):
    tables = await ac.get("/api/v3/synapse/schema-edit/tables", headers=AUTH)
    assert tables.status_code == 200
    assert tables.json()["data"]["total"] >= 1

    detail = await ac.get("/api/v3/synapse/schema-edit/tables/processes", headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()["data"]["name"] == "processes"

    upd_table = await ac.put(
        "/api/v3/synapse/schema-edit/tables/processes/description",
        json={"description": "프로세스 실행 내역 테이블"},
        headers=AUTH,
    )
    assert upd_table.status_code == 200
    assert upd_table.json()["data"]["embedding_updated"] is True

    detail_after = await ac.get("/api/v3/synapse/schema-edit/tables/processes", headers=AUTH)
    assert detail_after.status_code == 200
    assert detail_after.json()["data"]["description"] == "프로세스 실행 내역 테이블"

    upd_col = await ac.put(
        "/api/v3/synapse/schema-edit/columns/processes/efficiency_rate/description",
        json={"description": "효율성 비율"},
        headers=AUTH,
    )
    assert upd_col.status_code == 200

    create_rel = await ac.post(
        "/api/v3/synapse/schema-edit/relationships",
        json={
            "source_table": "processes",
            "source_column": "org_id",
            "target_table": "organizations",
            "target_column": "id",
            "relationship_type": "FK_TO",
        },
        headers=AUTH,
    )
    assert create_rel.status_code == 201
    rel_id = create_rel.json()["data"]["id"]

    rels = await ac.get("/api/v3/synapse/schema-edit/relationships", headers=AUTH)
    assert rels.status_code == 200
    assert rels.json()["data"]["total"] == 1

    embedding = await ac.post("/api/v3/synapse/schema-edit/tables/processes/embedding", headers=AUTH)
    assert embedding.status_code == 200

    batch = await ac.post(
        "/api/v3/synapse/schema-edit/batch-update-embeddings",
        json={"target": "all", "force": False},
        headers=AUTH,
    )
    assert batch.status_code == 202
    assert batch.json()["data"]["status"] == "processing"

    deleted = await ac.delete(f"/api/v3/synapse/schema-edit/relationships/{rel_id}", headers=AUTH)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True
