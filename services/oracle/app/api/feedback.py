from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.core.query_history import query_history_repo

router = APIRouter(prefix="/feedback", tags=["Feedback"])

class FeedbackRequest(BaseModel):
    query_id: str
    rating: str # 'positive', 'negative', 'partial'
    comment: Optional[str] = None

@router.post("")
async def submit_feedback(payload: FeedbackRequest):
    success = await query_history_repo.save_feedback(payload.query_id, payload.rating, payload.comment)
    return {"success": success}
