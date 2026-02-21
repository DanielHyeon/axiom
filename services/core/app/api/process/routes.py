from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.core.middleware import get_current_tenant_id
from app.services.process_service import ProcessDomainError, ProcessService
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
    force_complete: bool = False


class ApproveHITLRequest(BaseModel):
    workitem_id: str
    approved: bool
    modifications: dict = Field(default_factory=dict)


class ReworkRequest(BaseModel):
    workitem_id: str
    reason: str
    revert_to_activity_id: str | None = None


class RoleBindingRequest(BaseModel):
    proc_inst_id: str
    role_bindings: list[dict]


class DefinitionCreateRequest(BaseModel):
    name: str
    description: str | None = None
    type: str = "base"
    source: str
    activities_hint: list[str] = Field(default_factory=list)
    bpmn_xml: str | None = None


@router.post("/initiate", status_code=status.HTTP_201_CREATED)
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
            role_bindings=req.role_bindings,
        )
        await db.commit()
        return result
    except ProcessDomainError as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/role-binding")
async def role_binding_endpoint(req: RoleBindingRequest, db: AsyncSession = Depends(get_session)):
    try:
        result = await ProcessService.bind_roles(
            db=db,
            proc_inst_id=req.proc_inst_id,
            role_bindings=req.role_bindings,
            tenant_id=get_current_tenant_id(),
        )
        await db.commit()
        return result
    except ProcessDomainError as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
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
            raise ProcessDomainError(400, "MISSING_WORKITEM_ID", "workitem_id is required")
        result = await ProcessService.submit_workitem(
            db=db,
            item_id=item_id,
            submit_data=req.result_data,
            force_complete=req.force_complete,
        )
        await db.commit()
        return result
    except ProcessDomainError as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/feedback/{workitem_id}")
async def feedback_endpoint(workitem_id: str, db: AsyncSession = Depends(get_session)):
    try:
        return await ProcessService.get_feedback(db=db, workitem_id=workitem_id)
    except ProcessDomainError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{proc_inst_id}/status")
async def process_status_endpoint(proc_inst_id: str, db: AsyncSession = Depends(get_session)):
    try:
        return await ProcessService.get_process_status(db=db, proc_inst_id=proc_inst_id)
    except ProcessDomainError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/{proc_inst_id}/workitems")
async def process_workitems_endpoint(
    proc_inst_id: str,
    status: str | None = None,
    agent_mode: str | None = None,
    db: AsyncSession = Depends(get_session),
):
    try:
        data = await ProcessService.get_workitems(
            db=db,
            proc_inst_id=proc_inst_id,
            status=status,
            agent_mode=agent_mode,
        )
        return {"data": data}
    except ProcessDomainError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
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
    except ProcessDomainError as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/definitions")
async def list_definitions_endpoint(
    cursor: str | None = None,
    limit: int = 20,
    sort: str = "created_at:desc",
    db: AsyncSession = Depends(get_session),
):
    try:
        return await ProcessService.list_definitions(
            db=db,
            tenant_id=get_current_tenant_id(),
            cursor=cursor,
            limit=limit,
            sort=sort,
        )
    except ProcessDomainError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/definitions", status_code=status.HTTP_201_CREATED)
async def create_definitions_endpoint(
    req: DefinitionCreateRequest,
    db: AsyncSession = Depends(get_session),
):
    try:
        result = await ProcessService.create_definition(
            db=db,
            tenant_id=get_current_tenant_id(),
            name=req.name,
            source=req.source,
            definition_type=req.type,
            description=req.description,
            activities_hint=req.activities_hint,
            bpmn_xml=req.bpmn_xml,
        )
        await db.commit()
        return result
    except ProcessDomainError as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
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
    except ProcessDomainError as e:
        await db.rollback()
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal Server Error")
