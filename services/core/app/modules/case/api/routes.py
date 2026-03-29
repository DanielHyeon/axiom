"""
케이스 목록·활동·문서 리뷰·통계 API (Canvas Full-spec Phase A / Phase D + DDD-P0-02).
GET /api/v1/cases — 케이스 목록 (tenant 기준, core_case 테이블).
GET /api/v1/cases/stats — 케이스 집계 통계 (Vision 등 외부 BC 전용).
GET /api/v1/cases/trend — 월별 케이스 추이 (Vision 트렌드 차트 전용).
GET /api/v1/cases/activities — 최근 활동 (core_case_activity, tenant 또는 case_id 필터).
GET /api/v1/cases/{case_id}/info — 개별 케이스 조회 (Vision case_financial 전용).
POST /api/v1/cases/:caseId/documents/:docId/review — 문서 리뷰 영속 (core_document_review).
"""
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, cast, String, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.base_models import Case, CaseActivity, DocumentReview

router = APIRouter(prefix="/cases", tags=["cases"])


def _escape_like(value: str) -> str:
    """SQL LIKE 와일드카드(%, _, \\) 이스케이프 — ILIKE 주입 방지."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class CaseItem(BaseModel):
    id: str
    title: str
    status: str
    priority: str
    assignee: str | None = None
    createdAt: str
    updatedAt: str | None = None
    dueDate: str | None = None


class CaseListResponse(BaseModel):
    items: list[CaseItem]
    total: int


class ActivityItem(BaseModel):
    id: str
    time: str
    text: str


class ActivitiesResponse(BaseModel):
    items: list[ActivityItem]


@router.get("", response_model=CaseListResponse)
async def list_cases(
    status: str | None = Query(None, description="필터: PENDING, IN_PROGRESS, COMPLETED, REJECTED"),
    search: str | None = Query(None, description="제목 검색 (ILIKE)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """케이스 목록. tenant_id는 JWT 기준. core_case 테이블 조회. search로 제목 필터링."""
    tenant_id = current_user.get("tenant_id") or "default"
    count_q = select(func.count()).select_from(Case).where(Case.tenant_id == tenant_id)
    if status:
        count_q = count_q.where(Case.status == status)
    if search:
        # 와일드카드 이스케이프 적용하여 ILIKE 주입 방지
        safe_search = _escape_like(search)
        count_q = count_q.where(Case.title.ilike(f"%{safe_search}%"))
    total = (await db.execute(count_q)).scalar() or 0
    q = select(Case).where(Case.tenant_id == tenant_id)
    if status:
        q = q.where(Case.status == status)
    if search:
        safe_search = _escape_like(search)
        q = q.where(Case.title.ilike(f"%{safe_search}%"))
    q = q.order_by(Case.created_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    items = [
        CaseItem(
            id=r.id,
            title=r.title,
            status=r.status,
            priority=r.priority,
            assignee=r.assignee,
            createdAt=r.created_at.isoformat() if r.created_at else "",
            updatedAt=r.updated_at.isoformat() if r.updated_at else None,
            dueDate=r.due_date.isoformat() if r.due_date else None,
        )
        for r in rows
    ]
    return CaseListResponse(items=items, total=total)


# --- BC 경계 보호 엔드포인트 (DDD-P0-02: Vision 등 외부 BC 전용) ---


class CaseStatsResponse(BaseModel):
    total_cases: int
    active_cases: int


@router.get("/stats", response_model=CaseStatsResponse)
async def get_case_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """케이스 집계 통계. Vision 등 외부 BC가 core_case 직접 조회 대신 사용."""
    tenant_id = current_user.get("tenant_id") or "default"
    total = (await db.execute(
        select(func.count()).select_from(Case).where(Case.tenant_id == tenant_id)
    )).scalar() or 0
    active = (await db.execute(
        select(func.count()).select_from(Case).where(
            Case.tenant_id == tenant_id,
            Case.status == "IN_PROGRESS",
        )
    )).scalar() or 0
    return CaseStatsResponse(total_cases=total, active_cases=active)


class CaseTrendItem(BaseModel):
    period: str
    new_cases: int
    completed_cases: int
    active_cases: int


class CaseTrendResponse(BaseModel):
    granularity: str
    from_date: str
    to_date: str
    series: list[CaseTrendItem]


@router.get("/trend", response_model=CaseTrendResponse)
async def get_case_trend(
    from_date: date = Query(..., description="시작일 (YYYY-MM-DD)"),
    to_date: date = Query(..., description="종료일 (YYYY-MM-DD)"),
    granularity: str = Query("monthly", description="집계 단위: monthly"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """월별 케이스 추이. Vision 트렌드 차트에서 core_case 직접 조회 대신 사용."""
    tenant_id = current_user.get("tenant_id") or "default"
    # Build month-period expression: YYYY-MM
    period_expr = func.to_char(Case.created_at, "YYYY-MM")
    q = (
        select(
            period_expr.label("period"),
            func.count(Case.id).label("new_cases"),
            func.count(Case.id).filter(Case.status == "COMPLETED").label("completed_cases"),
            func.count(Case.id).filter(Case.status == "IN_PROGRESS").label("active_cases"),
        )
        .where(
            Case.tenant_id == tenant_id,
            cast(Case.created_at, String) >= from_date.isoformat(),
            cast(Case.created_at, String) <= to_date.isoformat() + "T23:59:59",
        )
        .group_by(period_expr)
        .order_by(period_expr)
    )
    rows = (await db.execute(q)).all()
    series = [
        CaseTrendItem(
            period=r.period,
            new_cases=r.new_cases or 0,
            completed_cases=r.completed_cases or 0,
            active_cases=r.active_cases or 0,
        )
        for r in rows
    ]
    return CaseTrendResponse(
        granularity=granularity,
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
        series=series,
    )


class CaseInfoResponse(BaseModel):
    id: str
    title: str
    status: str


@router.get("/{case_id}/info", response_model=CaseInfoResponse)
async def get_case_info(
    case_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """개별 케이스 조회. Vision case_financial에서 core_case 직접 조회 대신 사용."""
    tenant_id = current_user.get("tenant_id") or "default"
    row = (await db.execute(
        select(Case).where(Case.id == case_id, Case.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseInfoResponse(id=row.id, title=row.title, status=row.status)


@router.get("/activities", response_model=ActivitiesResponse)
async def list_case_activities(
    case_id: str | None = Query(None, description="케이스 ID 필터(없으면 tenant 전체 최근 활동)"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """최근 활동 타임라인. core_case_activity 조회.
    NOTE: /{case_id} 보다 먼저 선언해야 "activities"가 case_id로 매칭되지 않는다."""
    tenant_id = current_user.get("tenant_id") or "default"
    q = select(CaseActivity).where(CaseActivity.tenant_id == tenant_id)
    if case_id:
        q = q.where(CaseActivity.case_id == case_id)
    q = q.order_by(CaseActivity.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    items = [
        ActivityItem(
            id=r.id,
            time=r.created_at.isoformat() if r.created_at else "",
            text=r.text,
        )
        for r in rows
    ]
    return ActivitiesResponse(items=items)


class CaseDetailResponse(BaseModel):
    """케이스 상세 — 모든 필드 포함."""
    id: str
    title: str
    status: str
    priority: str
    assignee: str | None = None
    createdAt: str
    updatedAt: str | None = None
    dueDate: str | None = None


@router.get("/{case_id}", response_model=CaseDetailResponse)
async def get_case_detail(
    case_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """케이스 상세 조회 — Canvas CaseDetailPage 전용."""
    tenant_id = current_user.get("tenant_id") or "default"
    row = (await db.execute(
        select(Case).where(Case.id == case_id, Case.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseDetailResponse(
        id=row.id,
        title=row.title,
        status=row.status,
        priority=row.priority,
        assignee=row.assignee,
        createdAt=row.created_at.isoformat() if row.created_at else "",
        updatedAt=row.updated_at.isoformat() if row.updated_at else None,
        dueDate=row.due_date.isoformat() if row.due_date else None,
    )


# --- 문서 CRUD (Canvas documentApi 계약) ---


class DocumentItem(BaseModel):
    """문서 목록/상세 응답 모델."""
    id: str
    name: str
    type: str = "document"
    status: str = "draft"
    size: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class DocumentListResponse(BaseModel):
    items: list[DocumentItem]
    total: int


@router.get("/{case_id}/documents", response_model=DocumentListResponse)
async def list_case_documents(
    case_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """케이스에 연결된 문서 목록 조회. document_review 테이블에서 유니크 document_id를 반환."""
    result = await db.execute(
        select(DocumentReview)
        .where(DocumentReview.case_id == case_id)
        .order_by(DocumentReview.created_at.desc())
    )
    reviews = result.scalars().all()
    items = [
        DocumentItem(
            id=r.document_id,
            name=f"Document {r.document_id[:8]}",
            status=r.status or "draft",
            createdAt=r.created_at.isoformat() if r.created_at else None,
        )
        for r in reviews
    ]
    return DocumentListResponse(items=items, total=len(items))


@router.get("/{case_id}/documents/{doc_id}")
async def get_case_document(
    case_id: str,
    doc_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """문서 상세 조회."""
    result = await db.execute(
        select(DocumentReview).where(
            DocumentReview.case_id == case_id,
            DocumentReview.document_id == doc_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentItem(
        id=row.document_id,
        name=f"Document {row.document_id[:8]}",
        status=row.status or "draft",
        createdAt=row.created_at.isoformat() if row.created_at else None,
    )


# --- 문서 리뷰 (Phase D: Canvas documentReviewApi 계약) ---

class DocumentReviewRequest(BaseModel):
    action: str = Field(..., description="approve | reject | request_changes")
    comment: str | None = None


class DocumentReviewResponse(BaseModel):
    documentId: str
    status: str = Field(..., description="approved | rejected | changes_requested")
    message: str | None = None


@router.post("/{case_id}/documents/{doc_id}/review", response_model=DocumentReviewResponse)
async def submit_document_review(
    case_id: str,
    doc_id: str,
    body: DocumentReviewRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """
    문서 리뷰 액션. core_document_review에 영속, core_case_activity에 이벤트 추가.
    """
    tenant_id = current_user.get("tenant_id") or "default"
    user_id = current_user.get("user_id")
    status_map = {
        "approve": "approved",
        "reject": "rejected",
        "request_changes": "changes_requested",
    }
    status = status_map.get(body.action, "changes_requested")

    existing = await db.execute(
        select(DocumentReview).where(
            DocumentReview.case_id == case_id,
            DocumentReview.document_id == doc_id,
        )
    )
    review_row = existing.scalar_one_or_none()
    if review_row:
        review_row.status = status
        review_row.comment = body.comment
        review_row.reviewed_by = user_id
    else:
        review_row = DocumentReview(
            case_id=case_id,
            document_id=doc_id,
            tenant_id=tenant_id,
            status=status,
            comment=body.comment,
            reviewed_by=user_id,
        )
        db.add(review_row)
    activity = CaseActivity(
        case_id=case_id,
        tenant_id=tenant_id,
        activity_type="document_review",
        text=f"문서 {doc_id} 리뷰: {status}" + (f" — {body.comment}" if body.comment else ""),
        meta={"document_id": doc_id, "status": status},
    )
    db.add(activity)
    await db.commit()
    await db.refresh(review_row)
    return DocumentReviewResponse(documentId=doc_id, status=status, message=body.comment)
