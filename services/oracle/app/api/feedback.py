from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.api.text2sql import get_current_user
from app.core.auth import CurrentUser
from app.core.query_history import query_history_repo

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
