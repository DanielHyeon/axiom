from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from itertools import count
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, auth_service
from app.engines.mondrian_parser import parse_string as mondrian_parse_string, validate_parsed
from app.engines.nl_to_pivot import nl_to_pivot
from app.engines.pivot_engine import generate_pivot_sql, _resolve_level_column, _table_alias
from app.services.vision_runtime import vision_runtime, PivotQueryTimeoutError, VisionRuntimeError

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
    try:
        parsed = mondrian_parse_string(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SCHEMA", "message": f"XML 파싱 실패: {e}"})
    if not parsed.get("cubes"):
        raise HTTPException(status_code=400, detail={"code": "INVALID_SCHEMA", "message": "유효한 Cube가 없습니다"})
    cube_meta = parsed["cubes"][0]
    warnings = validate_parsed(cube_meta)
    cube_name = cube_meta.get("name") or (file.filename or "uploaded_cube").split(".")[0]
    fact_table = cube_meta.get("fact_table") or "mv_business_fact"
    dimensions = cube_meta.get("dimensions") or []
    measures = cube_meta.get("measures") or []
    dimension_details = cube_meta.get("dimension_details")
    measure_details = cube_meta.get("measure_details")
    cube = vision_runtime.create_cube(
        cube_name,
        fact_table,
        dimensions,
        measures,
        dimension_details=dimension_details,
        measure_details=measure_details,
    )
    return {
        "cube_name": cube["name"],
        "fact_table": cube["fact_table"],
        "dimensions": cube["dimensions"],
        "measures": cube["measures"],
        "dimension_count": cube["dimension_count"],
        "measure_count": cube["measure_count"],
        "uploaded_at": _now(),
        "validation": {"is_valid": len(warnings) == 0, "warnings": warnings},
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
    cube = vision_runtime.cubes.get(payload.cube_name)
    if not cube:
        raise HTTPException(status_code=404, detail={"code": "CUBE_NOT_FOUND", "message": "큐브를 찾을 수 없습니다"})
    filters = [f.model_dump() for f in payload.filters]
    try:
        generated_sql, sql_params = generate_pivot_sql(
            cube,
            payload.rows,
            payload.columns or [],
            payload.measures,
            filters,
            sort_by=payload.sort_by,
            sort_order=payload.sort_order or "DESC",
            limit=payload.limit,
            offset=payload.offset,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PIVOT", "message": str(e)})
    start = time.perf_counter()
    try:
        rows, column_names = vision_runtime.execute_pivot_query(generated_sql, sql_params, timeout_seconds=30)
    except PivotQueryTimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"code": "QUERY_TIMEOUT", "message": "쿼리 실행 시간이 30초를 초과했습니다"},
        )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    if not rows and not column_names:
        column_names = payload.rows + payload.columns + payload.measures
        rows = []
    aggregations: dict[str, float | int] = {}
    for measure in payload.measures:
        values = [r.get(measure) for r in rows if isinstance(r.get(measure), (int, float))]
        if values:
            aggregations[f"{measure}_total"] = round(float(sum(values)), 3)
            aggregations[f"{measure}_overall"] = round(float(sum(values) / len(values)), 3)
        else:
            aggregations[f"{measure}_total"] = 0
            aggregations[f"{measure}_overall"] = 0
    return {
        "cube_name": payload.cube_name,
        "generated_sql": generated_sql,
        "execution_time_ms": elapsed_ms,
        "total_rows": len(rows),
        "columns": [{"name": k, "type": "number" if k in payload.measures else "string"} for k in column_names],
        "rows": rows,
        "aggregations": aggregations,
    }


@router.post("/pivot/nl-query")
async def pivot_nl_query(payload: NLQueryRequest, user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    cube_context = nl_to_pivot.build_cube_context(vision_runtime.cubes)
    cube_name_hint = payload.cube_name or next(iter(vision_runtime.cubes.keys()), None)
    translated = await nl_to_pivot.translate(payload.query, cube_context, cube_name_hint)
    cube_name = translated.get("cube_name") or cube_name_hint or "BusinessAnalysisCube"
    rows = translated.get("rows") or ["region"]
    columns = translated.get("columns") or []
    measures = translated.get("measures") or translated.get("metrics") or ["CaseCount"]
    filters = translated.get("filters") or []
    confidence = float(translated.get("confidence", 0.7))

    cube = vision_runtime.cubes.get(cube_name)
    if not cube:
        cube_name = next(iter(vision_runtime.cubes.keys()), "BusinessAnalysisCube")
        cube = vision_runtime.cubes.get(cube_name)
    if not cube:
        return {
            "original_query": payload.query,
            "interpreted_as": {"cube_name": cube_name, "rows": rows, "columns": columns, "measures": measures, "filters": filters},
            "result": {"columns": [], "rows": [], "total_rows": 0},
            "confidence": confidence,
            "execution_time_ms": 0,
        }

    pivot_payload = PivotQueryRequest(
        cube_name=cube_name,
        rows=rows,
        columns=columns,
        measures=measures,
        filters=[PivotFilter(dimension_level=f.get("dimension_level", ""), operator=f.get("operator", "="), values=f.get("values", [])) for f in filters],
        limit=1000,
        offset=0,
    )
    start = time.perf_counter()
    try:
        generated_sql, sql_params = generate_pivot_sql(
            cube,
            pivot_payload.rows,
            pivot_payload.columns or [],
            pivot_payload.measures,
            [f.model_dump() for f in pivot_payload.filters],
            limit=pivot_payload.limit,
            offset=pivot_payload.offset,
        )
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "original_query": payload.query,
            "interpreted_as": {"cube_name": cube_name, "rows": rows, "columns": columns, "measures": measures, "filters": filters},
            "result": {"columns": [], "rows": [], "total_rows": 0},
            "confidence": confidence,
            "execution_time_ms": elapsed_ms,
        }
    try:
        query_rows, column_names = vision_runtime.execute_pivot_query(generated_sql, sql_params, timeout_seconds=30)
    except PivotQueryTimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"code": "QUERY_TIMEOUT", "message": "쿼리 실행 시간이 30초를 초과했습니다"},
        )
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    result_columns = [{"name": k, "type": "number" if k in measures else "string"} for k in column_names]
    response = {
        "original_query": payload.query,
        "interpreted_as": {"cube_name": cube_name, "rows": rows, "columns": columns, "measures": measures, "filters": filters},
        "result": {"columns": result_columns, "rows": query_rows, "total_rows": len(query_rows)},
        "confidence": confidence,
        "execution_time_ms": elapsed_ms,
    }
    if payload.include_sql:
        response["generated_sql"] = generated_sql
    return response


@router.get("/pivot/drillthrough")
async def pivot_drillthrough(
    request: Request,
    cube_name: str = Query(...),
    limit: int = Query(default=50, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_auth(user)
    cube = vision_runtime.cubes.get(cube_name)
    if not cube:
        raise HTTPException(
            status_code=404,
            detail={"code": "INVALID_CUBE_NAME", "message": f"큐브 '{cube_name}'을(를) 찾을 수 없습니다"},
        )

    fact_table = (cube.get("fact_table") or "mv_business_fact").strip()
    if not fact_table:
        fact_table = "mv_business_fact"

    # 쿼리 파라미터 중 cube_name, limit 이외는 차원 필터로 해석 (Dimension.Level = value)
    filters: list[dict[str, Any]] = []
    for key, value in request.query_params.multi_items():
        if key in {"cube_name", "limit"}:
            continue
        if value is None or value == "":
            continue
        filters.append({"dimension_level": key, "operator": "=", "values": [value]})

    where_parts: list[str] = []
    params: list[Any] = []
    join_clauses: list[str] = []
    join_set: set[str] = set()

    for f in filters:
        dim_level = f["dimension_level"]
        vals = f.get("values") or []
        alias, col = _resolve_level_column(cube, dim_level)
        safe_col = col.replace('"', "").replace(";", "")
        # 필요 시 차원 테이블 조인
        if alias != "f" and alias not in join_set:
            join_set.add(alias)
            dim = next(
                (
                    d
                    for d in (cube.get("dimension_details") or [])
                    if _table_alias(d.get("table", "")) == alias
                ),
                None,
            )
            if dim:
                fk = dim.get("foreign_key") or ""
                pk = dim.get("primary_key") or "id"
                if fk:
                    join_clauses.append(
                        f"LEFT JOIN {dim.get('table', '')} {alias} ON f.{fk} = {alias}.{pk}"
                    )
        if vals:
            where_parts.append(f"{alias}.{safe_col} = %s")
            params.append(vals[0])

    sql = (
        "SELECT f.case_id, f.case_number, f.company_name, f.case_type, "
        "f.filing_date, f.total_obligations, f.performance_rate "
        f"FROM {fact_table} f"
    )
    if join_clauses:
        sql += " " + " ".join(join_clauses)
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " LIMIT %s"
    params.append(limit)

    try:
        rows, _ = vision_runtime.execute_pivot_query(sql, params, timeout_seconds=30)
    except PivotQueryTimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"code": "QUERY_TIMEOUT", "message": "쿼리 실행 시간이 30초를 초과했습니다"},
        )

    if not rows:
        # DB 미구현/스키마 불일치 시 기존 스텁 형태로 폴백
        records = [{"case_id": _new_id("case-"), "cube_name": cube_name, "value": i} for i in range(limit)]
        return {"total_count": len(records), "records": records}

    return {"total_count": len(rows), "records": rows}


@router.post("/etl/analyze")
async def etl_analyze(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    source = payload.get("source", "default")
    return {"source": source, "status": "analyzed", "estimated_rows": 10000, "recommended_cube": "BusinessAnalysisCube"}


def _run_etl_refresh_background(job_id: str) -> None:
    """백그라운드 스레드에서 ETL REFRESH 실행 (동기 호출)."""
    vision_runtime.run_etl_refresh_sync(job_id)


def _get_airflow_base_url() -> str:
    import os as _os
    return (_os.getenv("AIRFLOW_BASE_URL") or "").strip().rstrip("/")


@router.post("/etl/sync", status_code=status.HTTP_202_ACCEPTED)
async def etl_sync(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    try:
        job = vision_runtime.queue_etl_job(payload)
    except VisionRuntimeError as e:
        if e.code == "ETL_IN_PROGRESS":
            raise HTTPException(
                status_code=503,
                detail={"code": "ETL_IN_PROGRESS", "message": e.message},
            ) from e
        raise
    asyncio.create_task(asyncio.to_thread(_run_etl_refresh_background, job["job_id"]))
    return {
        "sync_id": job["job_id"],
        "job_id": job["job_id"],
        "sync_type": job.get("sync_type", "full"),
        "target_views": job.get("target_views", []),
        "status": "RUNNING",
        "started_at": job.get("started_at") or job.get("created_at"),
    }


@router.get("/etl/status")
async def etl_status(
    sync_id: str | None = Query(None, alias="sync_id"),
    job_id: str | None = Query(None, alias="job_id"),
    user: CurrentUser = Depends(get_current_user),
):
    _ensure_auth(user)
    sid = sync_id or job_id
    if not sid:
        raise HTTPException(status_code=400, detail="sync_id or job_id required")
    job_id = sid
    job = vision_runtime.get_etl_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="etl job not found")
    return {
        "sync_id": job.get("job_id", job_id),
        "status": job.get("status", "queued"),
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "duration_seconds": job.get("duration_seconds"),
        "rows_affected": job.get("rows_affected", {}),
    }


@router.post("/etl/airflow/trigger-dag")
async def etl_trigger_airflow(payload: dict[str, Any], user: CurrentUser = Depends(get_current_user)):
    _ensure_auth(user)
    dag_id = str(payload.get("dag_id") or "vision_olap_full_sync")
    conf = dict(payload.get("conf") or {})
    base = _get_airflow_base_url()
    if not base:
        return {"dag_id": dag_id, "triggered": True, "dag_run_id": _new_id("manual__"), "state": "queued"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.post(
                f"{base}/dags/{dag_id}/dagRuns",
                json={"conf": conf},
            )
            r.raise_for_status()
            data = r.json()
            return {
                "dag_id": dag_id,
                "triggered": True,
                "dag_run_id": data.get("dag_run_id", ""),
                "state": data.get("state", "queued"),
            }
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail={"code": "AIRFLOW_UNAVAILABLE", "message": str(e)},
            ) from e
