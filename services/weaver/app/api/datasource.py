from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, List

router = APIRouter(prefix="/datasource", tags=["DataSource"])

class DataSourceCreate(BaseModel):
    name: str
    type: str # postgres, mysql, etc
    connection_config: Dict[str, Any]

@router.post("")
async def create_datasource(payload: DataSourceCreate):
    # Stub for WEA-S2-001 API Contract
    return {"status": "created", "id": "ds_mock_123"}

@router.post("/{ds_id}/sync")
async def sync_schema(ds_id: str):
    # Stub WEA-S2-002 Introspection API
    return {"status": "sync_started", "job_id": "job_456"}
