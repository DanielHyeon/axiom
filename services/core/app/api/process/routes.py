from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.services.process_service import ProcessService
from pydantic import BaseModel

router = APIRouter(prefix="/process", tags=["process"])

class SubmitRequest(BaseModel):
    item_id: str
    result_data: dict

@router.post("/submit")
async def submit_workitem_endpoint(
    req: SubmitRequest, 
    db: AsyncSession = Depends(get_session)
):
    try:
        # In this mock, we assume ProcessService throws an error if not found.
        # But we don't have real DB inserts, so we just attempt it.
        result = await ProcessService.submit_workitem(db=db, item_id=req.item_id, submit_data=req.result_data)
        await db.commit() # The Router commits the DB!
        return {"data": result}
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
