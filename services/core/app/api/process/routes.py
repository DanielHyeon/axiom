from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.middleware import get_current_tenant_id
from app.services.process_service import ProcessService
from pydantic import BaseModel, Field

router = APIRouter(prefix="/process", tags=["process"])


class InitiateRequest(BaseModel):
    proc_def_id: str
    input_data: dict = Field(default_factory=dict)
    role_bindings: list[dict] = Field(default_factory=list)


class SubmitRequest(BaseModel):
    item_id: str | None = None
    workitem_id: str | None = None
    result_data: dict


class ApproveHITLRequest(BaseModel):
    workitem_id: str
    approved: bool
    modifications: dict = Field(default_factory=dict)


class ReworkRequest(BaseModel):
    workitem_id: str
    reason: str
    revert_to_activity_id: str | None = None


@router.post("/initiate")
async def initiate_process_endpoint(
    req: InitiateRequest,
    db: AsyncSession = Depends(get_session),
):
    try:
        payload = dict(req.input_data or {})
        payload.setdefault("tenant_id", get_current_tenant_id())
        result = await ProcessService.initiate_process(
            db=db,
            proc_def_id=req.proc_def_id,
            input_data=payload,
        )
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/submit")
async def submit_workitem_endpoint(
    req: SubmitRequest,
    db: AsyncSession = Depends(get_session),
):
    try:
        item_id = req.workitem_id or req.item_id
        if not item_id:
            raise ValueError("workitem_id is required")
        result = await ProcessService.submit_workitem(db=db, item_id=item_id, submit_data=req.result_data)
        await db.commit()
        return {"data": result}
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{proc_inst_id}/status")
async def process_status_endpoint(proc_inst_id: str, db: AsyncSession = Depends(get_session)):
    try:
        return await ProcessService.get_process_status(db=db, proc_inst_id=proc_inst_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{proc_inst_id}/workitems")
async def process_workitems_endpoint(proc_inst_id: str, db: AsyncSession = Depends(get_session)):
    try:
        data = await ProcessService.get_workitems(db=db, proc_inst_id=proc_inst_id)
        return {"data": data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/approve-hitl")
async def approve_hitl_endpoint(req: ApproveHITLRequest, db: AsyncSession = Depends(get_session)):
    try:
        feedback = (req.modifications or {}).get("feedback", "")
        result = await ProcessService.approve_hitl(
            db=db,
            item_id=req.workitem_id,
            approved=req.approved,
            feedback=feedback,
        )
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/rework")
async def rework_workitem_endpoint(req: ReworkRequest, db: AsyncSession = Depends(get_session)):
    try:
        result = await ProcessService.rework_workitem(
            db=db,
            item_id=req.workitem_id,
            reason=req.reason,
            revert_to_activity_id=req.revert_to_activity_id,
        )
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
