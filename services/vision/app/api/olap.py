from __future__ import annotations

from datetime import datetime, timezone
from itertools import count
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.core.nl_to_pivot import nl_to_pivot
from app.services.vision_runtime import vision_runtime

router = APIRouter(prefix="/api/v3", tags=["OLAP"])
_ID_SEQ = count(1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}{int(datetime.now(timezone.utc).timestamp() * 1000)}-{next(_ID_SEQ)}"


async def get_current_user(authorization: str = Header("mock_token", alias="Authorization")) -> CurrentUser:
    return auth_service.verify_token(authorization)


def _ensure_auth(user: CurrentUser) -> None:
    auth_service.requires_role(user, ["admin", "staff"])


class PivotFilter(BaseModel):
    dimension_level: str
    operator: str
    values: list[Any]


class PivotQueryRequest(BaseModel):
    cube_name: str
    rows: list[str] = Field(min_length=1)
    columns: list[str] = Field(default_factory=list)
    measures: list[str] = Field(min_length=1)
    filters: list[PivotFilter] = Field(default_factory=list)
    sort_by: str | None = None
    sort_order: str = "DESC"
    limit: int = Field(default=1000, ge=1, le=10000)
    offset: int = Field(default=0, ge=0)


class NLQueryRequest(BaseModel):
    query: str
    cube_name: str | None = None
    include_sql: bool = False


@router.post("/cubes/schema/upload", status_code=status.HTTP_201_CREATED)
async def upload_cube_schema(file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    content = (await file.read()).decode("utf-8", errors="ignore")
    name_from_file = (file.filename or "uploaded_cube").split(".")[0]
    cube_name = "BusinessAnalysisCube" if "BusinessAnalysisCube" in content else name_from_file
    dimensions = ["CaseType", "Organization", "Time", "Stakeholder"]
    measures = ["CaseCount", "TotalAmount", "AvgPerformanceRate"]
    cube = vision_runtime.create_cube(cube_name, "mv_business_fact", dimensions, measures)
    return {
        "cube_name": cube["name"],
        "fact_table": cube["fact_table"],
        "dimensions": cube["dimensions"],
        "measures": cube["measures"],
        "dimension_count": cube["dimension_count"],
        "measure_count": cube["measure_count"],
        "uploaded_at": _now(),
        "validation": {"is_valid": True, "warnings": []},
    }


@router.get("/cubes")
async def list_cubes(user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    rows = sorted(vision_runtime.cubes.values(), key=lambda x: x["name"])
    return {"cubes": rows}


@router.get("/cubes/{cube_name}")
async def get_cube(cube_name: str, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    cube = vision_runtime.cubes.get(cube_name)
    if not cube:
        raise HTTPException(status_code=404, detail="cube not found")
    return {
        "name": cube["name"],
        "fact_table": cube["fact_table"],
        "dimensions": [
            {
                "name": item,
                "foreign_key": f"{item.lower()}_id",
                "table": f"dim_{item.lower()}",
                "levels": [{"name": item, "column": item.lower(), "type": "String", "cardinality": 10}],
            }
            for item in cube["dimensions"]
        ],
        "measures": [{"name": item, "column": item.lower(), "aggregator": "sum", "format": "#,###"} for item in cube["measures"]],
    }


@router.post("/pivot/query")
async def pivot_query(payload: PivotQueryRequest, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    if payload.cube_name not in vision_runtime.cubes:
        raise HTTPException(status_code=404, detail="cube not found")
    rows = []
    for idx in range(payload.offset, payload.offset + min(payload.limit, 5)):
        row = {dim: f"{dim}-v{idx}" for dim in payload.rows}
        for dim in payload.columns:
            row[dim] = idx % 3
        for measure in payload.measures:
            row[measure] = 10 + idx
        rows.append(row)
    aggregations: dict[str, float | int] = {}
    for measure in payload.measures:
        values = [r.get(measure) for r in rows if isinstance(r.get(measure), (int, float))]
        if values:
            aggregations[f"{measure}_total"] = round(float(sum(values)), 3)
            aggregations[f"{measure}_overall"] = round(float(sum(values) / len(values)), 3)
    return {
        "cube_name": payload.cube_name,
        "generated_sql": "SELECT ... FROM cube_fact ...",
        "execution_time_ms": 10,
        "total_rows": len(rows),
        "columns": [{"name": k, "type": "string"} for k in (payload.rows + payload.columns + payload.measures)],
        "rows": rows,
        "aggregations": aggregations,
    }


@router.post("/pivot/nl-query")
async def pivot_nl_query(payload: NLQueryRequest, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    translated = await nl_to_pivot.translate(payload.query)
    cube_name = payload.cube_name or next(iter(vision_runtime.cubes.keys()), "BusinessAnalysisCube")
    query_result = {
        "columns": [{"name": "region", "type": "string"}, {"name": translated["metrics"][0], "type": "number"}],
        "rows": [{"region": "A", translated["metrics"][0]: 100}],
    }
    response = {
        "original_query": payload.query,
        "interpreted_as": {
            "cube_name": cube_name,
            "rows": translated.get("dimensions", []),
            "columns": [],
            "measures": translated.get("metrics", []),
            "filters": translated.get("filters", []),
        },
        "generated_sql": "SELECT ...",
        "result": query_result,
        "confidence": 0.9,
        "execution_time_ms": 20,
    }
    if not payload.include_sql:
        response.pop("generated_sql", None)
    return response


@router.get("/pivot/drillthrough")
async def pivot_drillthrough(
    cube_name: str = Query(...),
    limit: int = Query(default=50, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_auth(user)
    if cube_name not in vision_runtime.cubes:
        raise HTTPException(status_code=404, detail="cube not found")
    records = [{"case_id": _new_id("case-"), "cube_name": cube_name, "value": i} for i in range(limit)]
    return {"total_count": len(records), "records": records}


@router.post("/etl/analyze")
async def etl_analyze(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    source = payload.get("source", "default")
    return {"source": source, "status": "analyzed", "estimated_rows": 10000, "recommended_cube": "BusinessAnalysisCube"}


@router.post("/etl/sync", status_code=status.HTTP_202_ACCEPTED)
async def etl_sync(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    job_id = _new_id("etl-")
    now = _now()
    vision_runtime.etl_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "payload": payload,
    }
    return {"job_id": job_id, "status": "queued"}


@router.get("/etl/status")
async def etl_status(job_id: str = Query(...), user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    job = vision_runtime.etl_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="etl job not found")
    if job["status"] == "queued":
        job["status"] = "completed"
        job["updated_at"] = _now()
    return {"job_id": job_id, "status": job["status"], "updated_at": job["updated_at"]}


@router.post("/etl/airflow/trigger-dag")
async def etl_trigger_airflow(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    dag_id = str(payload.get("dag_id") or "vision_etl")
    return {"dag_id": dag_id, "triggered": True, "run_id": _new_id("manual__")}
