import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


class FakeHistoryRepo:
    def __init__(self):
        self.saved = []
        self.feedback_saved = {}
        self.detail = {}

    async def save_query_history(self, record):
        query_id = f"q-{len(self.saved) + 1}"
        self.saved.append((query_id, record))
        self.detail[query_id] = {
            "id": query_id,
            "question": record.get("question"),
            "sql": record.get("sql"),
            "status": "success",
            "result": record.get("result", {}),
            "metadata": record.get("metadata", {}),
            "row_count": record.get("row_count"),
            "datasource_id": record.get("datasource_id"),
            "created_at": "2026-02-21T00:00:00+00:00",
            "feedback": None,
        }
        return query_id

    async def save_feedback(self, query_id, rating, comment=None, corrected_sql=None, tenant_id=None, user_id=None):
        if query_id not in self.detail:
            return False
        self.feedback_saved[query_id] = {"rating": rating, "comment": comment, "corrected_sql": corrected_sql}
        self.detail[query_id]["feedback"] = {"rating": rating, "comment": comment}
        return True

    async def list_history(self, tenant_id, datasource_id, status, date_from, date_to, page, page_size):
        class Page:
            pass

        page_obj = Page()
        items = list(self.detail.values())
        page_obj.items = items
        page_obj.total_count = len(items)
        page_obj.page = page
        page_obj.page_size = page_size
        return page_obj

    async def get_history_detail(self, tenant_id, query_id):
        return self.detail.get(query_id)


@pytest.fixture(autouse=True)
def override_repo(monkeypatch):
    fake = FakeHistoryRepo()
    import app.api.text2sql as text2sql_api
    import app.api.feedback as feedback_api

    monkeypatch.setattr(text2sql_api, "query_history_repo", fake)
    monkeypatch.setattr(feedback_api, "query_history_repo", fake)
    return fake


@pytest.mark.asyncio
async def test_ask_includes_query_id_and_history_list(override_repo, ac: AsyncClient, auth_headers: dict):
    ask_payload = {
        "question": "Show me everything",
        "datasource_id": "ds_business_main",
        "options": {"row_limit": 1000},
    }
    ask_res = await ac.post("/text2sql/ask", json=ask_payload, headers=auth_headers)
    assert ask_res.status_code == 200
    query_id = ask_res.json()["data"]["metadata"].get("query_id")
    assert query_id

    history_res = await ac.get("/text2sql/history", headers=auth_headers)
    assert history_res.status_code == 200
    body = history_res.json()
    assert body["success"] is True
    assert body["data"]["pagination"]["total_count"] >= 1


@pytest.mark.asyncio
async def test_history_detail_not_found(override_repo, ac: AsyncClient, auth_headers: dict):
    res = await ac.get("/text2sql/history/not-found", headers=auth_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_feedback_submit_and_validation(override_repo, ac: AsyncClient, auth_headers: dict):
    ask_payload = {
        "question": "Show me everything",
        "datasource_id": "ds_business_main",
        "options": {"row_limit": 1000},
    }
    ask_res = await ac.post("/text2sql/ask", json=ask_payload, headers=auth_headers)
    data = ask_res.json()["data"]
    query_id = (data.get("metadata") or {}).get("query_id")
    assert query_id

    ok = await ac.post(
        "/feedback",
        json={"query_id": query_id, "rating": "positive", "comment": "good"},
        headers=auth_headers,
    )
    assert ok.status_code == 200
    assert ok.json() == {"success": True}

    invalid = await ac.post("/feedback", json={"query_id": query_id, "rating": "bad"}, headers=auth_headers)
    assert invalid.status_code == 422

    missing = await ac.post("/feedback", json={"query_id": "missing", "rating": "positive"}, headers=auth_headers)
    assert missing.status_code == 404
