from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.services.extraction_service import ExtractionDomainError, extraction_service

router = APIRouter(prefix="/api/v3/synapse/extraction", tags=["Extraction"])


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", "default")


def _as_http_error(err: ExtractionDomainError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message})


@router.post("/documents/{doc_id}/extract-ontology", status_code=status.HTTP_202_ACCEPTED)
async def extract_ontology(doc_id: str, payload: dict[str, Any], request: Request):
    try:
        result = extraction_service.start_extraction(_tenant(request), doc_id, payload or {})
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)


@router.get("/documents/{doc_id}/ontology-status")
async def extraction_status(doc_id: str, request: Request):
    try:
        result = extraction_service.get_status(_tenant(request), doc_id)
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)


@router.get("/documents/{doc_id}/ontology-result")
async def extraction_result(
    doc_id: str,
    request: Request,
    min_confidence: float = 0.0,
    include_rejected: bool = False,
    status: str = Query(default="all"),
):
    try:
        result = extraction_service.get_result(
            _tenant(request),
            doc_id,
            min_confidence=min_confidence,
            include_rejected=include_rejected,
            status=status,
        )
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)


@router.put("/ontology/{entity_id}/confirm")
async def confirm_entity(entity_id: str, payload: dict[str, Any], request: Request):
    try:
        result = extraction_service.confirm_entity(_tenant(request), entity_id, payload or {})
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)


@router.post("/cases/{case_id}/ontology/review")
async def batch_review(case_id: str, payload: dict[str, Any], request: Request):
    try:
        result = extraction_service.batch_review(_tenant(request), case_id, payload or {})
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)


@router.get("/cases/{case_id}/review-queue")
async def review_queue(case_id: str, request: Request, limit: int = 50, offset: int = 0):
    try:
        result = extraction_service.review_queue(_tenant(request), case_id, limit=limit, offset=offset)
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)


@router.post("/documents/{doc_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_extraction(doc_id: str, request: Request):
    try:
        result = extraction_service.retry(_tenant(request), doc_id)
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)


@router.post("/documents/{doc_id}/revert-extraction")
async def revert_extraction(doc_id: str, request: Request):
    try:
        result = extraction_service.revert(_tenant(request), doc_id)
        return {"success": True, "data": result}
    except ExtractionDomainError as err:
        raise _as_http_error(err)
