"""문서→온톨로지 추출 파이프라인 API (Phase 2-G).

엔드포인트:
  POST /upload          — 문서 업로드 + 텍스트 추출 + 청킹
  POST /extract         — DDD 개념 추출 시작 (비동기 백그라운드 잡)
  GET  /extract/status  — 추출 잡 진행률 폴링
  GET  /extract/result  — 추출 결과 조회
  POST /extract/apply   — 추출 결과를 Synapse 온톨로지에 적용

인증: get_current_insight_user (JWT 또는 서비스 토큰)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser
from app.core.insight_auth import get_current_insight_user, get_effective_tenant_id
from app.services.document_service import document_service
from app.services.ddd_extraction_service import ddd_extraction_service

logger = logging.getLogger("axiom.weaver.document_api")

router = APIRouter(
    prefix="/api/v3/weaver/documents",
    tags=["document-ingestion"],
)


# ── 요청/응답 모델 ──────────────────────────────────────────── #


class DocumentUploadResponse(BaseModel):
    """문서 업로드 응답."""
    doc_id: str
    filename: str
    file_type: str
    page_count: int
    fragment_count: int
    status: str  # uploaded | processing | processed | failed


class ExtractionStartRequest(BaseModel):
    """DDD 추출 시작 요청."""
    doc_id: str
    case_id: str = ""
    target_layers: list[str] = Field(
        default=["process", "resource", "measure"],
        description="추출 대상 온톨로지 계층",
    )


class ExtractionJobResponse(BaseModel):
    """추출 잡 상태 응답."""
    job_id: str
    doc_id: str
    status: str  # queued | running | done | error
    progress: int = Field(ge=0, le=100, description="진행률 (0-100)")


class DocFragmentSchema(BaseModel):
    """문서 조각 — 추출 결과의 소스 앵커."""
    id: str
    doc_id: str
    page: int
    span_start: int
    span_end: int
    text: str


class ExtractedEntity(BaseModel):
    """LLM이 추출한 DDD 개념."""
    name: str
    entity_type: str = ""  # aggregate | command | event | policy
    description: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_text: str = ""
    source_anchor: dict[str, Any] = {}
    properties: dict[str, Any] = {}
    suggested_layer: str = ""  # kpi | measure | process | resource | driver
    suggested_relations: list[dict[str, Any]] = []


class ExtractionResult(BaseModel):
    """문서에서 추출된 전체 결과."""
    doc_id: str
    aggregates: list[ExtractedEntity] = []
    commands: list[ExtractedEntity] = []
    events: list[ExtractedEntity] = []
    policies: list[ExtractedEntity] = []
    relations: list[dict[str, Any]] = []
    total_entities: int = 0
    avg_confidence: float = 0.0


class ApplyRequest(BaseModel):
    """온톨로지 적용 요청."""
    job_id: str
    case_id: str
    selected_entities: list[str] = Field(
        default=[],
        description="적용할 엔티티 이름 목록 (빈 리스트면 전체 적용)",
    )


class ApplyResponse(BaseModel):
    """온톨로지 적용 응답."""
    applied_count: int
    node_ids: list[str] = []
    skipped: int = 0


# ── 엔드포인트 ───────────────────────────────────────────────── #


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="문서 업로드 + 텍스트 추출 + 청킹",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF, DOCX, TXT, MD 파일"),
    case_id: str = Query(default="", description="연결할 케이스 ID"),
    user: CurrentUser = Depends(get_current_insight_user),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """문서를 업로드하고 텍스트를 추출·청킹한다.

    지원 형식: PDF, DOCX, TXT, MD
    청킹 전략: 페이지 기반 + 의미 단위 (최대 1200자)
    """
    # 파일 크기 제한 (50MB)
    max_size = 50 * 1024 * 1024
    file_bytes = await file.read()
    if len(file_bytes) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"파일 크기 초과: {len(file_bytes)} > {max_size} bytes",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 이름이 필요합니다",
        )

    # 파일 확장자 화이트리스트 검증
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "csv"}
    ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": f"지원하지 않는 파일 형식입니다: .{ext}",
                "allowed": sorted(ALLOWED_EXTENSIONS),
            },
        )

    # 파일 타입 결정 (content_type 또는 확장자 기반)
    file_type = file.content_type or ""

    try:
        result = await document_service.upload_document(
            file_bytes=file_bytes,
            filename=file.filename,
            file_type=file_type,
            case_id=case_id,
            tenant_id=tenant_id,
        )
        return DocumentUploadResponse(**result)
    except Exception as exc:
        logger.error("문서 업로드 실패: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"문서 업로드 중 오류 발생: {str(exc)[:200]}",
        ) from exc


@router.post(
    "/extract",
    response_model=ExtractionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="DDD 개념 추출 시작 (비동기)",
)
async def start_extraction(
    body: ExtractionStartRequest,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_insight_user),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """DDD 개념 추출을 비동기 백그라운드 잡으로 시작한다.

    프래그먼트별 LLM 호출 → 구조화된 JSON 파싱 → 퍼지 중복 제거
    """
    # 문서 존재 여부 확인 (tenant_id로 데이터 격리)
    doc = await document_service.get_document(body.doc_id, tenant_id=tenant_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"문서를 찾을 수 없습니다: {body.doc_id}",
        )

    # 추출 잡 생성
    job_id = await document_service.create_extraction_job(
        doc_id=body.doc_id,
        case_id=body.case_id,
        tenant_id=tenant_id,
    )

    # 백그라운드 태스크로 추출 실행
    background_tasks.add_task(
        _run_extraction_job,
        job_id=job_id,
        doc_id=body.doc_id,
        case_id=body.case_id,
    )

    return ExtractionJobResponse(
        job_id=job_id,
        doc_id=body.doc_id,
        status="queued",
        progress=0,
    )


@router.get(
    "/extract/status",
    response_model=ExtractionJobResponse,
    summary="추출 잡 진행률 폴링",
)
async def get_extraction_status(
    job_id: str = Query(..., description="추출 잡 ID"),
    user: CurrentUser = Depends(get_current_insight_user),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """추출 잡의 현재 진행 상태를 반환한다."""
    job = await document_service.get_job(job_id, tenant_id=tenant_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"추출 잡을 찾을 수 없습니다: {job_id}",
        )

    return ExtractionJobResponse(
        job_id=job["id"],
        doc_id=job["doc_id"],
        status=job["status"],
        progress=job["progress"],
    )


@router.get(
    "/extract/result",
    response_model=ExtractionResult,
    summary="추출 결과 조회",
)
async def get_extraction_result(
    job_id: str = Query(..., description="추출 잡 ID"),
    user: CurrentUser = Depends(get_current_insight_user),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """완료된 추출 잡의 결과를 반환한다."""
    job = await document_service.get_job(job_id, tenant_id=tenant_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"추출 잡을 찾을 수 없습니다: {job_id}",
        )

    if job["status"] != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"추출이 아직 완료되지 않았습니다 (status={job['status']})",
        )

    result = job.get("result") or {}
    return ExtractionResult(
        doc_id=job["doc_id"],
        aggregates=[
            ExtractedEntity(**e) for e in result.get("aggregates", [])
        ],
        commands=[
            ExtractedEntity(**e) for e in result.get("commands", [])
        ],
        events=[
            ExtractedEntity(**e) for e in result.get("events", [])
        ],
        policies=[
            ExtractedEntity(**e) for e in result.get("policies", [])
        ],
        relations=result.get("relations", []),
        total_entities=result.get("total_entities", 0),
        avg_confidence=result.get("avg_confidence", 0.0),
    )


@router.post(
    "/extract/apply",
    response_model=ApplyResponse,
    summary="추출 결과를 Synapse 온톨로지에 적용",
)
async def apply_to_ontology(
    body: ApplyRequest,
    user: CurrentUser = Depends(get_current_insight_user),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """추출 결과를 Synapse 온톨로지 노드로 변환하여 적용한다.

    1. 각 entity를 해당 layer의 노드로 변환
    2. suggested_relations를 관계로 생성
    3. DocFrag → DERIVED_FROM 관계로 트레이서빌리티 연결
    """
    # 잡 존재 및 완료 여부 확인 (tenant_id로 데이터 격리)
    job = await document_service.get_job(body.job_id, tenant_id=tenant_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"추출 잡을 찾을 수 없습니다: {body.job_id}",
        )

    if job["status"] != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"추출이 완료되지 않아 적용할 수 없습니다 (status={job['status']})",
        )

    result = job.get("result") or {}
    if not result:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="추출 결과가 비어 있습니다",
        )

    try:
        apply_result = await ddd_extraction_service.apply_to_ontology(
            extraction_result=result,
            case_id=body.case_id,
            tenant_id=tenant_id,
            selected_entity_names=body.selected_entities or None,
        )
        return ApplyResponse(**apply_result)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("온톨로지 적용 실패: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"온톨로지 적용 중 오류: {str(exc)[:200]}",
        ) from exc


# ── 백그라운드 추출 워커 ──────────────────────────────────────── #


async def _run_extraction_job(
    job_id: str,
    doc_id: str,
    case_id: str,
) -> None:
    """백그라운드에서 DDD 추출을 실행한다.

    진행 상태를 DB에 주기적으로 업데이트하며,
    완료 시 결과를 JSONB로 저장한다.
    """
    try:
        # 잡 상태 → running
        await document_service.update_job_progress(job_id, "running", 10)

        # 프래그먼트 조회
        fragments = await document_service.get_fragments(doc_id)
        if not fragments:
            await document_service.update_job_progress(
                job_id, "error", 0, error="프래그먼트가 없습니다",
            )
            return

        await document_service.update_job_progress(job_id, "running", 20)

        # DDD 개념 추출
        extraction_result = await ddd_extraction_service.extract_from_fragments(
            fragments=fragments,
            case_id=case_id,
        )

        # 완료
        await document_service.update_job_progress(
            job_id, "done", 100, result=extraction_result,
        )
        logger.info(
            "DDD 추출 완료: job=%s, entities=%d",
            job_id, extraction_result.get("total_entities", 0),
        )

    except Exception as exc:
        logger.error("DDD 추출 실패: job=%s, error=%s", job_id, exc, exc_info=True)
        await document_service.update_job_progress(
            job_id, "error", 0, error=str(exc)[:500],
        )
