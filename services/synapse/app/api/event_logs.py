import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.services.event_log_service import EventLogDomainError, event_log_service

router = APIRouter(prefix="/api/v3/synapse/event-logs", tags=["Event Logs"])


def _tenant(request: Request) -> str:
    return getattr(request.state, "tenant_id", "default")


def _error_to_http(err: EventLogDomainError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail={"code": err.code, "message": err.message})


def _parse_multipart_payload(raw: bytes, content_type: str) -> tuple[dict[str, Any], bytes | None]:
    boundary_key = "boundary="
    if boundary_key not in content_type:
        raise EventLogDomainError(400, "INVALID_REQUEST", "multipart boundary missing")
    boundary = content_type.split(boundary_key, 1)[1].strip()
    delimiter = ("--" + boundary).encode()
    parts = raw.split(delimiter)

    metadata_text: str | None = None
    file_bytes: bytes | None = None
    for part in parts:
        chunk = part.strip()
        if not chunk or chunk == b"--":
            continue
        if b"\r\n\r\n" not in chunk:
            continue
        head, body = chunk.split(b"\r\n\r\n", 1)
        body = body.rstrip(b"\r\n")
        headers_text = head.decode(errors="ignore")
        if 'name="metadata"' in headers_text:
            metadata_text = body.decode("utf-8", errors="ignore")
        elif 'name="file"' in headers_text:
            file_bytes = body

    if metadata_text is None:
        raise EventLogDomainError(400, "INVALID_REQUEST", "metadata is required in multipart request")
    try:
        payload = json.loads(metadata_text)
    except json.JSONDecodeError as exc:
        raise EventLogDomainError(400, "INVALID_REQUEST", "metadata must be valid json") from exc
    return payload, file_bytes


@router.post("/ingest", status_code=202)
async def ingest_event_log(
    request: Request,
):
    try:
        parsed_payload: dict[str, Any]
        file_bytes: bytes | None = None
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            raw = await request.body()
            parsed_payload, file_bytes = _parse_multipart_payload(raw, content_type)
        else:
            try:
                parsed_payload = await request.json()
            except Exception as exc:
                raise EventLogDomainError(400, "INVALID_REQUEST", "json body is required") from exc

        result = event_log_service.ingest(
            tenant_id=_tenant(request),
            payload=parsed_payload,
            file_bytes=file_bytes,
        )
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.get("/")
async def list_event_logs(request: Request, case_id: str, limit: int = 20, offset: int = 0):
    try:
        result = event_log_service.list_logs(
            tenant_id=_tenant(request),
            case_id=case_id,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.get("/{log_id}")
async def get_event_log(request: Request, log_id: str):
    try:
        result = event_log_service.get_log(tenant_id=_tenant(request), log_id=log_id)
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.delete("/{log_id}")
async def delete_event_log(request: Request, log_id: str):
    try:
        result = event_log_service.delete_log(tenant_id=_tenant(request), log_id=log_id)
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.get("/{log_id}/statistics")
async def event_log_statistics(request: Request, log_id: str):
    try:
        result = event_log_service.get_statistics(tenant_id=_tenant(request), log_id=log_id)
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.get("/{log_id}/preview")
async def event_log_preview(request: Request, log_id: str, limit: int = 100):
    try:
        result = event_log_service.get_preview(tenant_id=_tenant(request), log_id=log_id, limit=limit)
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.put("/{log_id}/column-mapping")
async def update_event_log_mapping(request: Request, log_id: str, payload: dict[str, Any]):
    try:
        result = event_log_service.update_column_mapping(
            tenant_id=_tenant(request),
            log_id=log_id,
            mapping=(payload or {}).get("column_mapping") or {},
        )
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.post("/{log_id}/refresh", status_code=202)
async def refresh_event_log(request: Request, log_id: str):
    try:
        result = event_log_service.refresh(tenant_id=_tenant(request), log_id=log_id)
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)


@router.post("/export-bpm", status_code=202)
async def export_bpm_event_log(request: Request, payload: dict[str, Any]):
    try:
        result = event_log_service.export_bpm(tenant_id=_tenant(request), payload=payload or {})
        return {"success": True, "data": result}
    except EventLogDomainError as err:
        raise _error_to_http(err)
