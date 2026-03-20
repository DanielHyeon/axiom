from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from app.api.text2sql import get_current_user
from app.core.auth import CurrentUser, auth_service
from app.core.query_history import query_history_repo
from app.core.feedback_analytics import feedback_analytics

router = APIRouter(prefix="/feedback", tags=["Feedback"])

class FeedbackRequest(BaseModel):
    query_id: str
    rating: str = Field(..., pattern="^(positive|negative|partial)$")
    comment: Optional[str] = None
    corrected_sql: Optional[str] = None

@router.post("")
async def submit_feedback(payload: FeedbackRequest, user: CurrentUser = Depends(get_current_user)):
    success = await query_history_repo.save_feedback(
        query_id=payload.query_id,
        rating=payload.rating,
        comment=payload.comment,
        corrected_sql=payload.corrected_sql,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
    )
    if not success:
        raise HTTPException(status_code=404, detail="query history not found")
    return {"success": success}


@router.get("/list")
async def list_feedback(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    rating: str | None = Query(default=None, pattern="^(positive|negative|partial)$"),
    datasource_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
):
    """피드백 목록 조회 (페이지네이션). admin/manager 전용."""
    auth_service.requires_role(user, ["admin", "manager"])
    data = await feedback_analytics.get_feedback_list(
        tenant_id=str(user.tenant_id),
        page=page,
        page_size=page_size,
        rating=rating,
        datasource_id=datasource_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {"success": True, "data": data}
