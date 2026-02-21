from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.services.synapse_gateway_service import (
    GatewayProxyError,
    SynapseGatewayService,
    synapse_gateway_service,
)

router = APIRouter(tags=["gateway"])


def get_synapse_gateway() -> SynapseGatewayService:
    return synapse_gateway_service


def _incoming_headers(request: Request) -> dict[str, str]:
    return {
        "Authorization": request.headers.get("Authorization", ""),
        "X-Tenant-Id": request.headers.get("X-Tenant-Id", "default"),
        "X-Request-Id": request.headers.get("X-Request-Id", ""),
    }


def _raise_proxy(err: GatewayProxyError) -> None:
    raise HTTPException(status_code=err.status_code, detail=err.body)


@router.post("/event-logs/upload", status_code=202)
async def upload_event_log(
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        body = await request.body()
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/event-logs/ingest",
            incoming_headers=_incoming_headers(request),
            raw_body=body,
            content_type=request.headers.get("Content-Type"),
            timeout=300.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/event-logs/db-connect", status_code=202)
async def db_connect_event_log(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/event-logs/ingest",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=300.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/event-logs/ingest", status_code=202)
async def ingest_event_log(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/event-logs/ingest",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=300.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/event-logs")
async def list_event_logs(
    request: Request,
    case_id: str,
    limit: int = 20,
    offset: int = 0,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path="/api/v3/synapse/event-logs/",
            incoming_headers=_incoming_headers(request),
            query_params={"case_id": case_id, "limit": limit, "offset": offset},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/event-logs/{log_id}")
async def get_event_log(
    log_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/event-logs/{log_id}",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.delete("/event-logs/{log_id}")
async def delete_event_log(
    log_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="DELETE",
            path=f"/api/v3/synapse/event-logs/{log_id}",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/event-logs/{log_id}/statistics")
async def event_log_statistics(
    log_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/event-logs/{log_id}/statistics",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/event-logs/{log_id}/preview")
async def event_log_preview(
    log_id: str,
    request: Request,
    limit: int = 100,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/event-logs/{log_id}/preview",
            incoming_headers=_incoming_headers(request),
            query_params={"limit": limit},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.put("/event-logs/{log_id}/column-mapping")
async def update_event_log_mapping(
    log_id: str,
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="PUT",
            path=f"/api/v3/synapse/event-logs/{log_id}/column-mapping",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/event-logs/{log_id}/refresh", status_code=202)
async def refresh_event_log(
    log_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path=f"/api/v3/synapse/event-logs/{log_id}/refresh",
            incoming_headers=_incoming_headers(request),
            timeout=300.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/event-logs/export-bpm", status_code=202)
async def export_bpm_event_log(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/event-logs/export-bpm",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=300.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/process-mining/discover", status_code=202)
async def proxy_process_mining_discover(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/process-mining/discover",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/process-mining/conformance", status_code=202)
async def proxy_process_mining_conformance(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/process-mining/conformance",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/process-mining/bottlenecks", status_code=202)
async def proxy_process_mining_bottlenecks_post(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/process-mining/bottlenecks",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/process-mining/performance", status_code=202)
async def proxy_process_mining_performance_post(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/process-mining/performance",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/process-mining/variants")
async def proxy_process_mining_variants(
    request: Request,
    case_id: str,
    log_id: str,
    sort_by: str = "frequency_desc",
    limit: int = 20,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path="/api/v3/synapse/process-mining/variants",
            incoming_headers=_incoming_headers(request),
            query_params={
                "case_id": case_id,
                "log_id": log_id,
                "sort_by": sort_by,
                "limit": limit,
            },
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/process-mining/tasks/{task_id}")
async def proxy_process_mining_task(
    task_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/process-mining/tasks/{task_id}",
            incoming_headers=_incoming_headers(request),
            timeout=30.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/process-mining/tasks/{task_id}/result")
async def proxy_process_mining_task_result(
    task_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/process-mining/tasks/{task_id}/result",
            incoming_headers=_incoming_headers(request),
            timeout=30.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/process-mining/results/{result_id}")
async def proxy_process_mining_result(
    result_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/process-mining/results/{result_id}",
            incoming_headers=_incoming_headers(request),
            timeout=30.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/process-mining/statistics/{log_id}")
async def proxy_process_mining_statistics(
    log_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/process-mining/statistics/{log_id}",
            incoming_headers=_incoming_headers(request),
            timeout=30.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/process-mining/bpmn/export")
async def proxy_process_mining_bpmn_export(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/process-mining/bpmn/export",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=60.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/process-mining/import-model")
async def proxy_process_mining_import_model(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/process-mining/import-model",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=60.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/process-mining/bottlenecks")
async def proxy_process_mining_bottlenecks(
    request: Request,
    case_id: str,
    log_id: str,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path="/api/v3/synapse/process-mining/bottlenecks",
            incoming_headers=_incoming_headers(request),
            query_params={"case_id": case_id, "log_id": log_id},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/extraction/documents/{doc_id}/extract-ontology", status_code=202)
async def proxy_extraction_start(
    doc_id: str,
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path=f"/api/v3/synapse/extraction/documents/{doc_id}/extract-ontology",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/extraction/documents/{doc_id}/ontology-status")
async def proxy_extraction_status(
    doc_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/extraction/documents/{doc_id}/ontology-status",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/extraction/documents/{doc_id}/ontology-result")
async def proxy_extraction_result(
    doc_id: str,
    request: Request,
    min_confidence: float = 0.0,
    include_rejected: bool = False,
    status: str = "all",
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/extraction/documents/{doc_id}/ontology-result",
            incoming_headers=_incoming_headers(request),
            query_params={
                "min_confidence": min_confidence,
                "include_rejected": str(include_rejected).lower(),
                "status": status,
            },
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.put("/extraction/ontology/{entity_id}/confirm")
async def proxy_extraction_confirm(
    entity_id: str,
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="PUT",
            path=f"/api/v3/synapse/extraction/ontology/{entity_id}/confirm",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/extraction/cases/{case_id}/ontology/review")
async def proxy_extraction_batch_review(
    case_id: str,
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path=f"/api/v3/synapse/extraction/cases/{case_id}/ontology/review",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/extraction/cases/{case_id}/review-queue")
async def proxy_extraction_review_queue(
    case_id: str,
    request: Request,
    limit: int = 50,
    offset: int = 0,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/extraction/cases/{case_id}/review-queue",
            incoming_headers=_incoming_headers(request),
            query_params={"limit": limit, "offset": offset},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/extraction/documents/{doc_id}/retry", status_code=202)
async def proxy_extraction_retry(
    doc_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path=f"/api/v3/synapse/extraction/documents/{doc_id}/retry",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/extraction/documents/{doc_id}/revert-extraction")
async def proxy_extraction_revert(
    doc_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path=f"/api/v3/synapse/extraction/documents/{doc_id}/revert-extraction",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/schema-edit/tables")
async def proxy_schema_edit_tables(
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path="/api/v3/synapse/schema-edit/tables",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/schema-edit/tables/{table_name}")
async def proxy_schema_edit_table(
    table_name: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/schema-edit/tables/{table_name}",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.put("/schema-edit/tables/{table_name}/description")
async def proxy_schema_edit_table_description(
    table_name: str,
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="PUT",
            path=f"/api/v3/synapse/schema-edit/tables/{table_name}/description",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.put("/schema-edit/columns/{table_name}/{column_name}/description")
async def proxy_schema_edit_column_description(
    table_name: str,
    column_name: str,
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="PUT",
            path=f"/api/v3/synapse/schema-edit/columns/{table_name}/{column_name}/description",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/schema-edit/relationships")
async def proxy_schema_edit_relationships(
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path="/api/v3/synapse/schema-edit/relationships",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/schema-edit/relationships")
async def proxy_schema_edit_create_relationship(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/schema-edit/relationships",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.delete("/schema-edit/relationships/{rel_id}")
async def proxy_schema_edit_delete_relationship(
    rel_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="DELETE",
            path=f"/api/v3/synapse/schema-edit/relationships/{rel_id}",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/schema-edit/tables/{table_name}/embedding")
async def proxy_schema_edit_table_embedding(
    table_name: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path=f"/api/v3/synapse/schema-edit/tables/{table_name}/embedding",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/schema-edit/batch-update-embeddings", status_code=202)
async def proxy_schema_edit_batch_embeddings(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/schema-edit/batch-update-embeddings",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/graph/search")
async def proxy_graph_search(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/graph/search",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/graph/vector-search")
async def proxy_graph_vector_search(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/graph/vector-search",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/graph/fk-path")
async def proxy_graph_fk_path(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/graph/fk-path",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/graph/ontology-path")
async def proxy_graph_ontology_path(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/graph/ontology-path",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/graph/tables/{table_name}/related")
async def proxy_graph_related_tables(
    table_name: str,
    request: Request,
    max_hops: int = 2,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/graph/tables/{table_name}/related",
            incoming_headers=_incoming_headers(request),
            query_params={"max_hops": max_hops},
            timeout=60.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/graph/stats")
async def proxy_graph_stats(
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path="/api/v3/synapse/graph/stats",
            incoming_headers=_incoming_headers(request),
            timeout=60.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/ontology")
async def proxy_ontology_get(
    request: Request,
    case_id: str,
    limit: int = 200,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path="/api/v3/synapse/ontology/",
            incoming_headers=_incoming_headers(request),
            query_params={"case_id": case_id, "limit": limit},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/ontology/extract-ontology")
async def proxy_ontology_extract(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/ontology/extract-ontology",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/ontology/cases/{case_id}/ontology")
async def proxy_ontology_case_graph(
    case_id: str,
    request: Request,
    layer: str = "all",
    include_relations: bool = True,
    verified_only: bool = False,
    limit: int = 500,
    offset: int = 0,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/ontology/cases/{case_id}/ontology",
            incoming_headers=_incoming_headers(request),
            query_params={
                "layer": layer,
                "include_relations": str(include_relations).lower(),
                "verified_only": str(verified_only).lower(),
                "limit": limit,
                "offset": offset,
            },
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/ontology/cases/{case_id}/ontology/summary")
async def proxy_ontology_case_summary(
    case_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/ontology/cases/{case_id}/ontology/summary",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/ontology/cases/{case_id}/ontology/{layer}")
async def proxy_ontology_case_layer(
    case_id: str,
    layer: str,
    request: Request,
    limit: int = 500,
    offset: int = 0,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/ontology/cases/{case_id}/ontology/{layer}",
            incoming_headers=_incoming_headers(request),
            query_params={"limit": limit, "offset": offset},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/ontology/nodes")
async def proxy_ontology_create_node(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/ontology/nodes",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/ontology/nodes/{node_id}")
async def proxy_ontology_get_node(
    node_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/ontology/nodes/{node_id}",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.put("/ontology/nodes/{node_id}")
async def proxy_ontology_update_node(
    node_id: str,
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="PUT",
            path=f"/api/v3/synapse/ontology/nodes/{node_id}",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.delete("/ontology/nodes/{node_id}")
async def proxy_ontology_delete_node(
    node_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="DELETE",
            path=f"/api/v3/synapse/ontology/nodes/{node_id}",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.post("/ontology/relations")
async def proxy_ontology_create_relation(
    request: Request,
    payload: dict[str, Any],
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="POST",
            path="/api/v3/synapse/ontology/relations",
            incoming_headers=_incoming_headers(request),
            json_body=payload,
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.delete("/ontology/relations/{relation_id}")
async def proxy_ontology_delete_relation(
    relation_id: str,
    request: Request,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="DELETE",
            path=f"/api/v3/synapse/ontology/relations/{relation_id}",
            incoming_headers=_incoming_headers(request),
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/ontology/nodes/{node_id}/neighbors")
async def proxy_ontology_neighbors(
    node_id: str,
    request: Request,
    limit: int = 100,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/ontology/nodes/{node_id}/neighbors",
            incoming_headers=_incoming_headers(request),
            query_params={"limit": limit},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)


@router.get("/ontology/nodes/{node_id}/path-to/{target_id}")
async def proxy_ontology_path(
    node_id: str,
    target_id: str,
    request: Request,
    max_depth: int = 6,
    gateway: SynapseGatewayService = Depends(get_synapse_gateway),
):
    try:
        return await gateway.request(
            method="GET",
            path=f"/api/v3/synapse/ontology/nodes/{node_id}/path-to/{target_id}",
            incoming_headers=_incoming_headers(request),
            query_params={"max_depth": max_depth},
            timeout=180.0,
        )
    except GatewayProxyError as err:
        _raise_proxy(err)
