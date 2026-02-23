"""
케이스 목록·활동·문서 리뷰 API (Canvas Full-spec Phase A / Phase D).
GET /api/v1/cases — 케이스 목록 (tenant 기준, core_case 테이블).
GET /api/v1/cases/activities — 최근 활동 (core_case_activity, tenant 또는 case_id 필터).
POST /api/v1/cases/:caseId/documents/:docId/review — 문서 리뷰 영속 (core_document_review).
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user
from app.models.base_models import Case, CaseActivity, DocumentReview

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseItem(BaseModel):
    id: str
    title: str
    status: str
    priority: str
    createdAt: str
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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """케이스 목록. tenant_id는 JWT 기준. core_case 테이블 조회."""
    tenant_id = current_user.get("tenant_id") or "default"
    count_q = select(func.count()).select_from(Case).where(Case.tenant_id == tenant_id)
    if status:
        count_q = count_q.where(Case.status == status)
    total = (await db.execute(count_q)).scalar() or 0
    q = select(Case).where(Case.tenant_id == tenant_id)
    if status:
        q = q.where(Case.status == status)
    q = q.order_by(Case.created_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    items = [
        CaseItem(
            id=r.id,
            title=r.title,
            status=r.status,
            priority=r.priority,
            createdAt=r.created_at.isoformat() if r.created_at else "",
            dueDate=r.due_date.isoformat() if r.due_date else None,
        )
        for r in rows
    ]
    return CaseListResponse(items=items, total=total)


@router.get("/activities", response_model=ActivitiesResponse)
async def list_case_activities(
    case_id: str | None = Query(None, description="케이스 ID 필터(없으면 tenant 전체 최근 활동)"),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """최근 활동 타임라인. core_case_activity 조회."""
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
