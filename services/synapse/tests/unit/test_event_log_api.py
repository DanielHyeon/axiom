import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.event_log_service import event_log_service

AUTH = {"Authorization": "Bearer local-oracle-token"}


@pytest_asyncio.fixture
async def ac():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


def setup_function():
    event_log_service.clear()


@pytest.mark.asyncio
async def test_event_log_ingest_and_read_flow(ac: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    rows = [
        {"order_id": "ORD-1", "event_type": "주문 접수", "event_time": "2024-01-02T09:15:00Z", "handler_name": "김영수", "department": "영업팀"},
        {"order_id": "ORD-1", "event_type": "결제 확인", "event_time": "2024-01-02T09:45:00Z", "handler_name": "이지은", "department": "회계팀"},
        {"order_id": "ORD-2", "event_type": "주문 접수", "event_time": "2024-01-03T10:15:00Z", "handler_name": "김영수", "department": "영업팀"},
        {"order_id": "ORD-2", "event_type": "결제 확인", "event_time": "2024-01-03T10:35:00Z", "handler_name": "이지은", "department": "회계팀"},
    ]
    monkeypatch.setattr(
        "app.services.event_log_service.fetch_database_rows",
        lambda source_config, mapping, where_clause, max_rows: (rows, set(rows[0].keys())),
    )

    payload = {
        "case_id": "case-1",
        "name": "ERP 주문 이벤트",
        "source_type": "database",
        "source_config": {"connection_id": "conn-1", "table_name": "order_events"},
        "column_mapping": {
            "case_id_column": "order_id",
            "activity_column": "event_type",
            "timestamp_column": "event_time",
            "resource_column": "handler_name",
            "additional_columns": ["department"],
        },
        "filter": {"where_clause": "event_time >= '2024-01-01'", "max_rows": 100},
    }
    ingest = await ac.post("/api/v3/synapse/event-logs/ingest", json=payload, headers=AUTH)
    assert ingest.status_code == 202
    body = ingest.json()
    assert body["success"] is True
    log_id = body["data"]["log_id"]

    logs = await ac.get("/api/v3/synapse/event-logs/", params={"case_id": "case-1"}, headers=AUTH)
    assert logs.status_code == 200
    assert logs.json()["data"]["total"] == 1
    assert logs.json()["data"]["logs"][0]["log_id"] == log_id

    detail = await ac.get(f"/api/v3/synapse/event-logs/{log_id}", headers=AUTH)
    assert detail.status_code == 200
    assert detail.json()["data"]["source_type"] == "database"

    stats = await ac.get(f"/api/v3/synapse/event-logs/{log_id}/statistics", headers=AUTH)
    assert stats.status_code == 200
    assert stats.json()["data"]["overview"]["total_events"] > 0
    assert stats.json()["data"]["variants"]["total_variants"] >= 1

    preview = await ac.get(
        f"/api/v3/synapse/event-logs/{log_id}/preview",
        params={"limit": 2},
        headers=AUTH,
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["total_preview"] == 2


@pytest.mark.asyncio
async def test_event_log_mapping_refresh_and_delete(ac: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    rows = [
        {"order_id": "ORD-1", "event_type": "주문 접수", "event_time": "2024-01-02T09:15:00Z", "handler_name": "김영수", "department": "영업팀"},
        {"order_id": "ORD-1", "event_type": "결제 확인", "event_time": "2024-01-02T09:45:00Z", "handler_name": "이지은", "department": "회계팀"},
    ]
    monkeypatch.setattr(
        "app.services.event_log_service.fetch_database_rows",
        lambda source_config, mapping, where_clause, max_rows: (rows, set(rows[0].keys())),
    )

    db_payload = {
        "case_id": "case-2",
        "name": "ERP 주문 이벤트",
        "source_type": "database",
        "source_config": {"connection_id": "conn-1", "table_name": "order_events"},
        "column_mapping": {
            "case_id_column": "order_id",
            "activity_column": "event_type",
            "timestamp_column": "event_time",
            "resource_column": "handler_name",
            "additional_columns": ["department"],
        },
        "filter": {"where_clause": "event_time >= '2024-01-01'", "max_rows": 100},
    }
    ingest = await ac.post("/api/v3/synapse/event-logs/ingest", json=db_payload, headers=AUTH)
    assert ingest.status_code == 202
    log_id = ingest.json()["data"]["log_id"]

    update = await ac.put(
        f"/api/v3/synapse/event-logs/{log_id}/column-mapping",
        json={
            "column_mapping": {
                "case_id_column": "order_id",
                "activity_column": "event_type",
                "timestamp_column": "event_time",
                "resource_column": "handler_name",
                "additional_columns": ["department"],
            }
        },
        headers=AUTH,
    )
    assert update.status_code == 200
    assert update.json()["data"]["reprocessing_status"] == "completed"

    refresh = await ac.post(f"/api/v3/synapse/event-logs/{log_id}/refresh", headers=AUTH)
    assert refresh.status_code == 202
    assert refresh.json()["data"]["status"] == "ingesting"

    deleted = await ac.delete(f"/api/v3/synapse/event-logs/{log_id}", headers=AUTH)
    assert deleted.status_code == 200

    not_found = await ac.get(f"/api/v3/synapse/event-logs/{log_id}", headers=AUTH)
    assert not_found.status_code == 404
    assert not_found.json()["detail"]["code"] == "LOG_NOT_FOUND"


@pytest.mark.asyncio
async def test_event_log_validation_errors(ac: AsyncClient):
    invalid = await ac.post(
        "/api/v3/synapse/event-logs/ingest",
        json={"case_id": "case-3", "name": "bad", "source_type": "unsupported"},
        headers=AUTH,
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INVALID_SOURCE_TYPE"


@pytest.mark.asyncio
async def test_event_log_db_where_clause_security(ac: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "AXIOM_EVENTLOG_CONNECTIONS_JSON",
        json.dumps({"conn-1": {"engine": "postgres", "database_url": "postgresql://u:p@localhost:5432/db"}}),
    )
    payload = {
        "case_id": "case-3",
        "name": "unsafe",
        "source_type": "database",
        "source_config": {"connection_id": "conn-1", "table_name": "order_events"},
        "column_mapping": {
            "case_id_column": "order_id",
            "activity_column": "event_type",
            "timestamp_column": "event_time",
        },
        "filter": {"where_clause": "1=1; DROP TABLE order_events"},
    }
    res = await ac.post("/api/v3/synapse/event-logs/ingest", json=payload, headers=AUTH)
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "INVALID_REQUEST"
