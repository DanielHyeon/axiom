import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

from tests.unit.conftest import make_admin_token


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


class FakeSynapseClient:
    def list_datasources(self):
        return [
            {
                "id": "ds_business_main",
                "name": "Business Main DB",
                "type": "postgresql",
                "host": "localhost",
                "database": "insolvency_os",
                "schema": "public",
                "status": "active",
            }
        ]

    async def list_schema_tables(self, tenant_id: str):
        return {
            "success": True,
            "data": {
                "tables": [
                    {"name": "processes", "description": "프로세스 실행 내역", "column_count": 4, "has_embedding": True},
                    {"name": "organizations", "description": "이해관계자 정보", "column_count": 2, "has_embedding": True},
                ]
            },
        }

    async def get_schema_table(self, tenant_id: str, table_name: str):
        if table_name != "processes":
            raise RuntimeError("not found")
        return {
            "success": True,
            "data": {
                "name": "processes",
                "description": "프로세스 실행 내역",
                "has_embedding": True,
                "columns": [
                    {"name": "id", "data_type": "uuid", "description": "PK"},
                    {"name": "org_id", "data_type": "uuid", "description": "조직 ID"},
                ],
            },
        }

    async def update_table_description(self, tenant_id: str, table_name: str, description: str):
        return {"success": True, "data": {"table_name": table_name, "description": description, "embedding_updated": True}}

    async def update_column_description(self, tenant_id: str, table_name: str, column_name: str, description: str):
        return {
            "success": True,
            "data": {"table_name": table_name, "column_name": column_name, "description": description, "embedding_updated": True},
        }


def _admin_headers():
    return {"Authorization": f"Bearer {make_admin_token()}"}


@pytest.mark.asyncio
async def test_meta_list_tables(monkeypatch, ac: AsyncClient):
    import app.api.meta as meta_api

    monkeypatch.setattr(meta_api, "synapse_client", FakeSynapseClient())
    res = await ac.get("/text2sql/meta/tables", params={"datasource_id": "ds_business_main"}, headers=_admin_headers())
    assert res.status_code == 200
    payload = res.json()
    assert payload["success"] is True
    assert payload["data"]["pagination"]["total_count"] == 2


@pytest.mark.asyncio
async def test_meta_table_columns(monkeypatch, ac: AsyncClient):
    import app.api.meta as meta_api

    monkeypatch.setattr(meta_api, "synapse_client", FakeSynapseClient())
    res = await ac.get(
        "/text2sql/meta/tables/processes/columns",
        params={"datasource_id": "ds_business_main"},
        headers=_admin_headers(),
    )
    assert res.status_code == 200
    assert res.json()["data"]["table"]["name"] == "processes"


@pytest.mark.asyncio
async def test_meta_datasources(monkeypatch, ac: AsyncClient):
    import app.api.meta as meta_api

    monkeypatch.setattr(meta_api, "synapse_client", FakeSynapseClient())
    res = await ac.get("/text2sql/meta/datasources", headers=_admin_headers())
    assert res.status_code == 200
    assert len(res.json()["data"]["datasources"]) == 1


@pytest.mark.asyncio
async def test_meta_update_description(monkeypatch, ac: AsyncClient):
    import app.api.meta as meta_api

    monkeypatch.setattr(meta_api, "synapse_client", FakeSynapseClient())
    table_res = await ac.put(
        "/text2sql/meta/tables/processes/description",
        json={"datasource_id": "ds_business_main", "description": "설명 수정"},
        headers=_admin_headers(),
    )
    assert table_res.status_code == 200
    assert table_res.json()["data"]["vector_updated"] is True

    col_res = await ac.put(
        "/text2sql/meta/columns/public.processes.org_id/description",
        json={"datasource_id": "ds_business_main", "description": "조직 식별자"},
        headers=_admin_headers(),
    )
    assert col_res.status_code == 200
    assert col_res.json()["data"]["column_fqn"] == "public.processes.org_id"
