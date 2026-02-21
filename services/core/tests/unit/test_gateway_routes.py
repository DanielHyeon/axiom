import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.gateway.routes import (
    db_connect_event_log,
    delete_event_log,
    event_log_preview,
    event_log_statistics,
    export_bpm_event_log,
    get_event_log,
    ingest_event_log,
    list_event_logs,
    proxy_extraction_batch_review,
    proxy_extraction_confirm,
    proxy_extraction_result,
    proxy_extraction_retry,
    proxy_extraction_revert,
    proxy_extraction_review_queue,
    proxy_extraction_start,
    proxy_extraction_status,
    proxy_graph_fk_path,
    proxy_graph_ontology_path,
    proxy_graph_related_tables,
    proxy_graph_search,
    proxy_graph_stats,
    proxy_graph_vector_search,
    proxy_ontology_case_graph,
    proxy_ontology_case_layer,
    proxy_ontology_case_summary,
    proxy_ontology_create_node,
    proxy_ontology_create_relation,
    proxy_ontology_delete_node,
    proxy_ontology_delete_relation,
    proxy_ontology_extract,
    proxy_ontology_get,
    proxy_ontology_get_node,
    proxy_ontology_neighbors,
    proxy_ontology_path,
    proxy_ontology_update_node,
    proxy_process_mining_bottlenecks,
    proxy_process_mining_bottlenecks_post,
    proxy_process_mining_bpmn_export,
    proxy_process_mining_conformance,
    proxy_process_mining_discover,
    proxy_process_mining_import_model,
    proxy_process_mining_performance_post,
    proxy_process_mining_result,
    proxy_process_mining_statistics,
    proxy_process_mining_task,
    proxy_process_mining_task_result,
    proxy_schema_edit_batch_embeddings,
    proxy_schema_edit_column_description,
    proxy_schema_edit_create_relationship,
    proxy_schema_edit_delete_relationship,
    proxy_schema_edit_relationships,
    proxy_schema_edit_table,
    proxy_schema_edit_table_description,
    proxy_schema_edit_table_embedding,
    proxy_schema_edit_tables,
    proxy_process_mining_variants,
    refresh_event_log,
    update_event_log_mapping,
    upload_event_log,
)
from app.services.synapse_gateway_service import GatewayProxyError, SynapseGatewayService


class FakeGateway(SynapseGatewayService):
    def __init__(self):
        super().__init__(base_url="http://fake")

    async def request(self, **kwargs):
        if "/error" in kwargs["path"]:
            raise GatewayProxyError(503, {"code": "SERVICE_CIRCUIT_OPEN"})
        return {
            "ok": True,
            "method": kwargs["method"],
            "path": kwargs["path"],
            "query": kwargs.get("query_params") or {},
            "json": kwargs.get("json_body"),
            "raw_len": len(kwargs.get("raw_body") or b""),
            "timeout": kwargs.get("timeout"),
            "content_type": kwargs.get("content_type"),
        }


def make_request(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
    query_string: str = "",
) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "query_string": query_string.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    sent = False

    async def receive():
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


@pytest.mark.asyncio
async def test_gateway_event_log_routes_direct():
    gateway = FakeGateway()
    headers = {"authorization": "Bearer token", "x-tenant-id": "acme", "x-request-id": "req-1"}

    req = make_request("POST", "/api/v1/event-logs/ingest", headers=headers)
    resp = await ingest_event_log(request=req, payload={"source_type": "database"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/event-logs/ingest"
    assert resp["timeout"] == 300.0

    req = make_request("POST", "/api/v1/event-logs/db-connect", headers=headers)
    resp = await db_connect_event_log(request=req, payload={"source_type": "database"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/event-logs/ingest"

    req = make_request(
        "POST",
        "/api/v1/event-logs/upload",
        headers={**headers, "content-type": "multipart/form-data; boundary=abc"},
        body=b"--abc\r\n...",
    )
    resp = await upload_event_log(request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/event-logs/ingest"
    assert resp["raw_len"] > 0

    req = make_request("GET", "/api/v1/event-logs", headers=headers, query_string="case_id=c1&limit=10&offset=5")
    resp = await list_event_logs(request=req, case_id="c1", limit=10, offset=5, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/event-logs/"
    assert resp["query"]["case_id"] == "c1"

    req = make_request("GET", "/api/v1/event-logs/log1", headers=headers)
    resp = await get_event_log(log_id="log1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/event-logs/log1"

    req = make_request("DELETE", "/api/v1/event-logs/log1", headers=headers)
    resp = await delete_event_log(log_id="log1", request=req, gateway=gateway)
    assert resp["method"] == "DELETE"

    req = make_request("GET", "/api/v1/event-logs/log1/statistics", headers=headers)
    resp = await event_log_statistics(log_id="log1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/event-logs/log1/statistics"

    req = make_request("GET", "/api/v1/event-logs/log1/preview", headers=headers, query_string="limit=12")
    resp = await event_log_preview(log_id="log1", request=req, limit=12, gateway=gateway)
    assert resp["query"]["limit"] == 12

    req = make_request("PUT", "/api/v1/event-logs/log1/column-mapping", headers=headers)
    resp = await update_event_log_mapping(
        log_id="log1",
        request=req,
        payload={"column_mapping": {"case_id_column": "id"}},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/event-logs/log1/column-mapping"

    req = make_request("POST", "/api/v1/event-logs/log1/refresh", headers=headers)
    resp = await refresh_event_log(log_id="log1", request=req, gateway=gateway)
    assert resp["timeout"] == 300.0

    req = make_request("POST", "/api/v1/event-logs/export-bpm", headers=headers)
    resp = await export_bpm_event_log(
        request=req,
        payload={"case_id": "c1", "events": [{"case_id": "C-1", "activity": "A", "timestamp": "2024-01-01T00:00:00Z"}]},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/event-logs/export-bpm"


@pytest.mark.asyncio
async def test_gateway_process_mining_and_extraction_routes_direct():
    gateway = FakeGateway()
    headers = {"authorization": "Bearer token", "x-tenant-id": "acme"}

    req = make_request("POST", "/api/v1/process-mining/discover", headers=headers)
    resp = await proxy_process_mining_discover(
        request=req,
        payload={"log_id": "l1", "algorithm": "inductive"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/discover"

    req = make_request("POST", "/api/v1/process-mining/conformance", headers=headers)
    resp = await proxy_process_mining_conformance(
        request=req,
        payload={"log_id": "l1", "reference_model": {}},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/conformance"

    req = make_request("POST", "/api/v1/process-mining/bottlenecks", headers=headers)
    resp = await proxy_process_mining_bottlenecks_post(
        request=req,
        payload={"log_id": "l1"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/bottlenecks"

    req = make_request("POST", "/api/v1/process-mining/performance", headers=headers)
    resp = await proxy_process_mining_performance_post(
        request=req,
        payload={"log_id": "l1"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/performance"

    req = make_request("GET", "/api/v1/process-mining/variants", headers=headers, query_string="case_id=c1&log_id=l1")
    resp = await proxy_process_mining_variants(
        request=req,
        case_id="c1",
        log_id="l1",
        sort_by="frequency_desc",
        limit=20,
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/variants"

    req = make_request("GET", "/api/v1/process-mining/bottlenecks", headers=headers, query_string="case_id=c1&log_id=l1")
    resp = await proxy_process_mining_bottlenecks(
        request=req,
        case_id="c1",
        log_id="l1",
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/bottlenecks"

    req = make_request("GET", "/api/v1/process-mining/tasks/t1", headers=headers)
    resp = await proxy_process_mining_task(task_id="t1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/process-mining/tasks/t1"

    req = make_request("GET", "/api/v1/process-mining/tasks/t1/result", headers=headers)
    resp = await proxy_process_mining_task_result(task_id="t1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/process-mining/tasks/t1/result"

    req = make_request("GET", "/api/v1/process-mining/results/r1", headers=headers)
    resp = await proxy_process_mining_result(result_id="r1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/process-mining/results/r1"

    req = make_request("GET", "/api/v1/process-mining/statistics/l1", headers=headers)
    resp = await proxy_process_mining_statistics(log_id="l1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/process-mining/statistics/l1"

    req = make_request("POST", "/api/v1/process-mining/bpmn/export", headers=headers)
    resp = await proxy_process_mining_bpmn_export(
        request=req, payload={"result_id": "r1"}, gateway=gateway
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/bpmn/export"

    req = make_request("POST", "/api/v1/process-mining/import-model", headers=headers)
    resp = await proxy_process_mining_import_model(
        request=req, payload={"result_id": "r1"}, gateway=gateway
    )
    assert resp["path"] == "/api/v3/synapse/process-mining/import-model"

    req = make_request("POST", "/api/v1/extraction/documents/doc-1/extract-ontology", headers=headers)
    resp = await proxy_extraction_start(
        doc_id="doc-1",
        request=req,
        payload={"case_id": "c1"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/extraction/documents/doc-1/extract-ontology"

    req = make_request("GET", "/api/v1/extraction/documents/doc-1/ontology-status", headers=headers)
    resp = await proxy_extraction_status(doc_id="doc-1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/extraction/documents/doc-1/ontology-status"

    req = make_request("GET", "/api/v1/extraction/documents/doc-1/ontology-result", headers=headers)
    resp = await proxy_extraction_result(
        doc_id="doc-1",
        request=req,
        min_confidence=0.5,
        include_rejected=True,
        status="all",
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/extraction/documents/doc-1/ontology-result"

    req = make_request("PUT", "/api/v1/extraction/ontology/entity-1/confirm", headers=headers)
    resp = await proxy_extraction_confirm(
        entity_id="entity-1",
        request=req,
        payload={"action": "approve", "reviewer_id": "u1"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/extraction/ontology/entity-1/confirm"

    req = make_request("POST", "/api/v1/extraction/cases/c1/ontology/review", headers=headers)
    resp = await proxy_extraction_batch_review(
        case_id="c1",
        request=req,
        payload={"reviews": [], "reviewer_id": "u1"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/extraction/cases/c1/ontology/review"

    req = make_request("GET", "/api/v1/extraction/cases/c1/review-queue", headers=headers)
    resp = await proxy_extraction_review_queue(case_id="c1", request=req, limit=50, offset=0, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/extraction/cases/c1/review-queue"

    req = make_request("POST", "/api/v1/extraction/documents/doc-1/retry", headers=headers)
    resp = await proxy_extraction_retry(doc_id="doc-1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/extraction/documents/doc-1/retry"

    req = make_request("POST", "/api/v1/extraction/documents/doc-1/revert-extraction", headers=headers)
    resp = await proxy_extraction_revert(doc_id="doc-1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/extraction/documents/doc-1/revert-extraction"

    req = make_request("GET", "/api/v1/schema-edit/tables", headers=headers)
    resp = await proxy_schema_edit_tables(request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/schema-edit/tables"

    req = make_request("GET", "/api/v1/schema-edit/tables/processes", headers=headers)
    resp = await proxy_schema_edit_table(table_name="processes", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/schema-edit/tables/processes"

    req = make_request("PUT", "/api/v1/schema-edit/tables/processes/description", headers=headers)
    resp = await proxy_schema_edit_table_description(
        table_name="processes",
        request=req,
        payload={"description": "desc"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/schema-edit/tables/processes/description"

    req = make_request("PUT", "/api/v1/schema-edit/columns/processes/id/description", headers=headers)
    resp = await proxy_schema_edit_column_description(
        table_name="processes",
        column_name="id",
        request=req,
        payload={"description": "id desc"},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/schema-edit/columns/processes/id/description"

    req = make_request("GET", "/api/v1/schema-edit/relationships", headers=headers)
    resp = await proxy_schema_edit_relationships(request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/schema-edit/relationships"

    req = make_request("POST", "/api/v1/schema-edit/relationships", headers=headers)
    resp = await proxy_schema_edit_create_relationship(
        request=req,
        payload={
            "source_table": "processes",
            "source_column": "org_id",
            "target_table": "organizations",
            "target_column": "id",
        },
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/schema-edit/relationships"

    req = make_request("DELETE", "/api/v1/schema-edit/relationships/rel-1", headers=headers)
    resp = await proxy_schema_edit_delete_relationship(rel_id="rel-1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/schema-edit/relationships/rel-1"

    req = make_request("POST", "/api/v1/schema-edit/tables/processes/embedding", headers=headers)
    resp = await proxy_schema_edit_table_embedding(table_name="processes", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/schema-edit/tables/processes/embedding"

    req = make_request("POST", "/api/v1/schema-edit/batch-update-embeddings", headers=headers)
    resp = await proxy_schema_edit_batch_embeddings(
        request=req,
        payload={"target": "all", "force": False},
        gateway=gateway,
    )
    assert resp["path"] == "/api/v3/synapse/schema-edit/batch-update-embeddings"


@pytest.mark.asyncio
async def test_gateway_graph_and_ontology_routes_direct():
    gateway = FakeGateway()
    headers = {"authorization": "Bearer token", "x-tenant-id": "acme"}

    req = make_request("POST", "/api/v1/graph/search", headers=headers)
    resp = await proxy_graph_search(request=req, payload={"query": "효율성"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/graph/search"

    req = make_request("POST", "/api/v1/graph/vector-search", headers=headers)
    resp = await proxy_graph_vector_search(request=req, payload={"query": "조직"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/graph/vector-search"

    req = make_request("POST", "/api/v1/graph/fk-path", headers=headers)
    resp = await proxy_graph_fk_path(request=req, payload={"start_table": "processes"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/graph/fk-path"

    req = make_request("POST", "/api/v1/graph/ontology-path", headers=headers)
    resp = await proxy_graph_ontology_path(request=req, payload={"case_id": "c1"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/graph/ontology-path"

    req = make_request("GET", "/api/v1/graph/tables/processes/related", headers=headers)
    resp = await proxy_graph_related_tables(table_name="processes", request=req, max_hops=2, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/graph/tables/processes/related"

    req = make_request("GET", "/api/v1/graph/stats", headers=headers)
    resp = await proxy_graph_stats(request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/graph/stats"

    req = make_request("GET", "/api/v1/ontology", headers=headers, query_string="case_id=c1&limit=200")
    resp = await proxy_ontology_get(request=req, case_id="c1", limit=200, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/"

    req = make_request("POST", "/api/v1/ontology/extract-ontology", headers=headers)
    resp = await proxy_ontology_extract(request=req, payload={"case_id": "c1"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/extract-ontology"

    req = make_request("GET", "/api/v1/ontology/cases/c1/ontology", headers=headers)
    resp = await proxy_ontology_case_graph(case_id="c1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/cases/c1/ontology"

    req = make_request("GET", "/api/v1/ontology/cases/c1/ontology/summary", headers=headers)
    resp = await proxy_ontology_case_summary(case_id="c1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/cases/c1/ontology/summary"

    req = make_request("GET", "/api/v1/ontology/cases/c1/ontology/resource", headers=headers)
    resp = await proxy_ontology_case_layer(case_id="c1", layer="resource", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/cases/c1/ontology/resource"

    req = make_request("POST", "/api/v1/ontology/nodes", headers=headers)
    resp = await proxy_ontology_create_node(request=req, payload={"case_id": "c1", "id": "n1"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/nodes"

    req = make_request("GET", "/api/v1/ontology/nodes/n1", headers=headers)
    resp = await proxy_ontology_get_node(node_id="n1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/nodes/n1"

    req = make_request("PUT", "/api/v1/ontology/nodes/n1", headers=headers)
    resp = await proxy_ontology_update_node(node_id="n1", request=req, payload={"properties": {}}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/nodes/n1"

    req = make_request("DELETE", "/api/v1/ontology/nodes/n1", headers=headers)
    resp = await proxy_ontology_delete_node(node_id="n1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/nodes/n1"

    req = make_request("POST", "/api/v1/ontology/relations", headers=headers)
    resp = await proxy_ontology_create_relation(request=req, payload={"case_id": "c1"}, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/relations"

    req = make_request("DELETE", "/api/v1/ontology/relations/r1", headers=headers)
    resp = await proxy_ontology_delete_relation(relation_id="r1", request=req, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/relations/r1"

    req = make_request("GET", "/api/v1/ontology/nodes/n1/neighbors", headers=headers)
    resp = await proxy_ontology_neighbors(node_id="n1", request=req, limit=10, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/nodes/n1/neighbors"

    req = make_request("GET", "/api/v1/ontology/nodes/n1/path-to/n2", headers=headers)
    resp = await proxy_ontology_path(node_id="n1", target_id="n2", request=req, max_depth=4, gateway=gateway)
    assert resp["path"] == "/api/v3/synapse/ontology/nodes/n1/path-to/n2"


@pytest.mark.asyncio
async def test_gateway_error_passthrough_direct():
    gateway = FakeGateway()
    headers = {"authorization": "Bearer token", "x-tenant-id": "acme"}
    req = make_request("GET", "/api/v1/event-logs/error", headers=headers)
    with pytest.raises(HTTPException) as exc_info:
        await get_event_log(log_id="error", request=req, gateway=gateway)
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "SERVICE_CIRCUIT_OPEN"

    req = make_request("GET", "/api/v1/process-mining/tasks/error/result", headers=headers)
    with pytest.raises(HTTPException) as exc_info:
        await proxy_process_mining_task_result(task_id="error", request=req, gateway=gateway)
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["code"] == "SERVICE_CIRCUIT_OPEN"
