import pytest

from app.services.event_log_service import EventLogDomainError, EventLogService


def _csv_bytes() -> bytes:
    content = (
        "order_id,event_type,event_time,handler_name,department,priority,amount\n"
        "ORD-1,주문 접수,2024-01-02T09:15:00Z,김영수,영업팀,normal,150000\n"
        "ORD-1,결제 확인,2024-01-02T09:45:00Z,이지은,회계팀,normal,150000\n"
        "ORD-2,주문 접수,2024-01-03T10:15:00Z,김영수,영업팀,high,250000\n"
        "ORD-2,결제 확인,2024-01-03T10:35:00Z,이지은,회계팀,high,250000\n"
    )
    return content.encode("utf-8")


def _csv_payload() -> dict:
    return {
        "case_id": "case-1",
        "name": "csv-log",
        "source_type": "csv",
        "column_mapping": {
            "case_id_column": "order_id",
            "activity_column": "event_type",
            "timestamp_column": "event_time",
            "resource_column": "handler_name",
            "additional_columns": ["department", "priority", "amount"],
        },
    }



def test_service_csv_ingest_and_stats():
    service = EventLogService()
    result = service.ingest(tenant_id="t1", payload=_csv_payload(), file_bytes=_csv_bytes())
    assert result["status"] == "ingesting"
    log_id = result["log_id"]

    listing = service.list_logs(tenant_id="t1", case_id="case-1")
    assert listing["total"] == 1
    assert listing["logs"][0]["log_id"] == log_id

    stats = service.get_statistics(tenant_id="t1", log_id=log_id)
    assert stats["overview"]["total_events"] == 4
    assert stats["overview"]["total_cases"] == 2
    assert stats["variants"]["total_variants"] >= 1


def test_service_database_refresh(monkeypatch: pytest.MonkeyPatch):
    rows = [
        {"order_id": "ORD-1", "event_type": "주문 접수", "event_time": "2024-01-02T09:15:00Z", "handler_name": "김영수", "department": "영업팀"},
        {"order_id": "ORD-1", "event_type": "결제 확인", "event_time": "2024-01-02T09:45:00Z", "handler_name": "이지은", "department": "회계팀"},
    ]
    monkeypatch.setattr(
        "app.services.event_log_service.fetch_database_rows",
        lambda source_config, mapping, where_clause, max_rows: (rows, set(rows[0].keys())),
    )

    service = EventLogService()
    payload = {
        "case_id": "case-2",
        "name": "db-log",
        "source_type": "database",
        "source_config": {"connection_id": "conn-1", "table_name": "order_events"},
        "column_mapping": {
            "case_id_column": "order_id",
            "activity_column": "event_type",
            "timestamp_column": "event_time",
            "resource_column": "handler_name",
            "additional_columns": ["department"],
        },
        "filter": {"max_rows": 20, "where_clause": "event_type IS NOT NULL"},
    }
    ingested = service.ingest(tenant_id="t1", payload=payload)
    refreshed = service.refresh(tenant_id="t1", log_id=ingested["log_id"])
    assert refreshed["status"] == "ingesting"


def test_service_validation_errors():
    service = EventLogService()
    with pytest.raises(EventLogDomainError, match="source_type must be"):
        service.ingest(tenant_id="t1", payload={"case_id": "c", "name": "bad", "source_type": "foo"})

    with pytest.raises(EventLogDomainError, match="connection config not found"):
        service.ingest(
            tenant_id="t1",
            payload={
                "case_id": "c",
                "name": "db",
                "source_type": "database",
                "source_config": {"connection_id": "missing", "table_name": "order_events"},
                "column_mapping": {
                    "case_id_column": "order_id",
                    "activity_column": "event_type",
                    "timestamp_column": "event_time",
                },
            },
        )
