from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.services.process_mining_service import ProcessMiningDomainError, process_mining_service

router = APIRouter(prefix="/api/v3/synapse/process-mining", tags=["Process Mining"])


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", "default")


def _user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


def _error_to_http(err: ProcessMiningDomainError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message})


@router.post("/discover", status_code=202)
async def discover_process(request: Request, payload: dict[str, Any]):
    try:
        result = process_mining_service.submit_discover(
            tenant_id=_tenant(request), payload=payload or {}, requested_by=_user(request)
        )
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.post("/conformance", status_code=202)
async def conformance_check(request: Request, payload: dict[str, Any]):
    try:
        result = process_mining_service.submit_conformance(
            tenant_id=_tenant(request), payload=payload or {}, requested_by=_user(request)
        )
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.post("/bottlenecks", status_code=202)
async def bottlenecks_analyze(request: Request, payload: dict[str, Any]):
    try:
        result = process_mining_service.submit_bottlenecks(
            tenant_id=_tenant(request), payload=payload or {}, requested_by=_user(request)
        )
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.post("/performance", status_code=202)
async def performance_analyze(request: Request, payload: dict[str, Any]):
    try:
        result = process_mining_service.submit_performance(
            tenant_id=_tenant(request), payload=payload or {}, requested_by=_user(request)
        )
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.get("/variants")
async def get_variants(
    request: Request,
    case_id: str,
    log_id: str,
    sort_by: str = "frequency_desc",
    limit: int = 20,
    min_cases: int = 1,
):
    try:
        result = process_mining_service.list_variants(
            tenant_id=_tenant(request),
            case_id=case_id,
            log_id=log_id,
            sort_by=sort_by,
            limit=limit,
            min_cases=min_cases,
        )
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.get("/bottlenecks")
async def get_bottlenecks(
    request: Request,
    case_id: str,
    log_id: str,
    sort_by: str = "bottleneck_score_desc",
    sla_source: str = "eventstorming",
):
    try:
        result = process_mining_service.get_bottlenecks(
            tenant_id=_tenant(request),
            case_id=case_id,
            log_id=log_id,
            sort_by=sort_by,
            sla_source=sla_source,
        )
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.get("/tasks/{task_id}")
async def get_task(request: Request, task_id: str):
    try:
        result = process_mining_service.get_task(tenant_id=_tenant(request), task_id=task_id)
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.get("/tasks/{task_id}/result")
async def get_task_result(request: Request, task_id: str):
    try:
        result = process_mining_service.get_task_result(tenant_id=_tenant(request), task_id=task_id)
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.get("/results/{result_id}")
async def get_result(request: Request, result_id: str):
    try:
        result = process_mining_service.get_result(tenant_id=_tenant(request), result_or_task_id=result_id)
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.get("/statistics/{log_id}")
async def get_statistics(request: Request, log_id: str):
    try:
        result = process_mining_service.get_statistics(tenant_id=_tenant(request), log_id=log_id)
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.post("/bpmn/export")
async def export_bpmn(request: Request, payload: dict[str, Any]):
    try:
        result = process_mining_service.export_bpmn(tenant_id=_tenant(request), payload=payload or {})
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)


@router.post("/import-model")
async def import_model(request: Request, payload: dict[str, Any]):
    try:
        result = process_mining_service.import_model(
            tenant_id=_tenant(request), payload=payload or {}, requested_by=_user(request)
        )
        return {"success": True, "data": result}
    except ProcessMiningDomainError as err:
        raise _error_to_http(err)
