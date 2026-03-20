from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.core.neo4j_client import neo4j_client
from app.services.ontology_service import OntologyService
from app.services.ontology_exporter import OntologyExporter
from app.services.quality_service import OntologyQualityService
from app.services.hitl_service import HITLService
from app.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/v3/synapse/ontology", tags=["Ontology"])
ontology_service = OntologyService(neo4j_client)
ontology_exporter = OntologyExporter(ontology_service)
quality_service = OntologyQualityService(ontology_service)
hitl_service = HITLService(ontology_service=ontology_service)
snapshot_service = SnapshotService(neo4j_client, ontology_service)


# ── Pydantic 요청/응답 모델 ────────────────────────────────────


class RelationUpdateRequest(BaseModel):
    """관계 속성 업데이트 요청 모델"""
    weight: float | None = Field(None, ge=0.0, le=1.0, description="영향도 가중치 (0.0~1.0)")
    lag: int | None = Field(None, ge=0, description="시간 지연 (일 단위)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="관계 신뢰도 (0.0~1.0)")
    source_layer: str | None = Field(None, description="소스 노드 레이어")
    target_layer: str | None = Field(None, description="타겟 노드 레이어")
    from_field: str | None = Field(None, description="소스 필드명")
    to_field: str | None = Field(None, description="타겟 필드명")
    method: str | None = Field(None, description="분석 방법 (granger/correlation/manual)")
    direction: str | None = Field(None, description="영향 방향 (positive/negative)")
    type: str | None = Field(None, description="관계 타입 변경 (선택)")
    properties: dict[str, Any] | None = Field(None, description="추가 속성")


class BulkRelationUpdateItem(BaseModel):
    """일괄 업데이트 개별 항목"""
    source_id: str
    target_id: str
    type: str = "CAUSES"
    weight: float | None = Field(None, ge=0.0, le=1.0)
    lag: int | None = Field(None, ge=0)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    source_layer: str | None = None
    target_layer: str | None = None
    from_field: str | None = None
    to_field: str | None = None
    method: str | None = None
    direction: str | None = None


class BulkRelationUpdateRequest(BaseModel):
    """관계 일괄 업데이트 요청 모델"""
    updates: list[BulkRelationUpdateItem]


class BehaviorModelCreateRequest(BaseModel):
    """BehaviorModel 생성 요청"""
    name: str = Field(..., description="모델 이름")
    model_type: str = Field("unknown", description="모델 타입 (RandomForest, LinearRegression 등)")
    status: str = Field("pending", description="상태: pending|training|trained|failed|disabled")
    metrics_json: str | None = Field("{}", description="성능 메트릭 JSON")
    feature_view_sql: str | None = Field("", description="학습 데이터 SQL")
    train_data_rows: int | None = Field(0, description="학습 데이터 행 수")
    reads: list[dict[str, Any]] | None = Field(
        default_factory=list,
        description="READS_FIELD 목록: [{source_node_id, field, lag, feature_name}]",
    )
    predicts: list[dict[str, Any]] | None = Field(
        default_factory=list,
        description="PREDICTS_FIELD 목록: [{target_node_id, field, confidence}]",
    )


def _tenant(request: Request) -> str:
    """테넌트 ID 추출 — 없으면 401 반환 (fail-closed)"""
    tid = getattr(request.state, "tenant_id", None)
    if not tid:
        raise HTTPException(status_code=401, detail="tenant_id not resolved")
    return tid


# ── 기존 온톨로지 CRUD (하위 호환 유지) ────────────────────────


@router.get("/")
async def get_ontology(request: Request, case_id: str | None = None, limit: int = 200):
    if not case_id:
        raise HTTPException(status_code=400, detail="case_id is required")
    data = await ontology_service.get_case_ontology(case_id=case_id, limit=limit)
    return {"success": True, "data": data, "tenant_id": _tenant(request)}


@router.post("/extract-ontology")
async def extract_ontology(request: Request, payload: dict[str, Any]):
    try:
        result = await ontology_service.extract_ontology(tenant_id=_tenant(request), payload=payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": result}


@router.get("/cases/{case_id}/ontology")
async def get_case_ontology(
    case_id: str,
    layer: str = "all",
    include_relations: bool = True,
    verified_only: bool = False,
    min_weight: float | None = None,
    min_confidence: float | None = None,
    limit: int = 500,
    offset: int = 0,
):
    data = await ontology_service.get_case_ontology(
        case_id=case_id,
        layer=layer,
        include_relations=include_relations,
        verified_only=verified_only,
        min_weight=min_weight,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )
    return {"success": True, "data": data, "pagination": data["pagination"]}


@router.get("/cases/{case_id}/ontology/summary")
async def get_case_ontology_summary(case_id: str):
    return {"success": True, "data": await ontology_service.get_case_summary(case_id)}


@router.get("/cases/{case_id}/ontology/{layer}")
async def get_case_ontology_by_layer(case_id: str, layer: str, limit: int = 500, offset: int = 0):
    data = await ontology_service.get_case_ontology(case_id=case_id, layer=layer, limit=limit, offset=offset)
    return {"success": True, "data": data, "pagination": data["pagination"]}


@router.post("/nodes")
async def create_node(request: Request, payload: dict[str, Any]):
    try:
        data = await ontology_service.create_node(tenant_id=_tenant(request), payload=payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/nodes/{node_id}")
async def get_node(node_id: str):
    data = ontology_service.get_node(node_id)
    if not data:
        raise HTTPException(status_code=404, detail="node not found")
    return {"success": True, "data": data}


@router.put("/nodes/{node_id}")
async def update_node(node_id: str, request: Request, payload: dict[str, Any]):
    try:
        data = await ontology_service.update_node(tenant_id=_tenant(request), node_id=node_id, payload=payload or {})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: str, request: Request):
    """노드 삭제 — tenant_id 검증 포함"""
    try:
        data = await ontology_service.delete_node(node_id=node_id, tenant_id=_tenant(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/relations")
async def create_relation(request: Request, payload: dict[str, Any]):
    try:
        data = await ontology_service.create_relation(tenant_id=_tenant(request), payload=payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/relations/{relation_id}")
async def delete_relation(relation_id: str, request: Request):
    """관계 삭제 — tenant_id 검증 포함"""
    try:
        data = await ontology_service.delete_relation(relation_id=relation_id, tenant_id=_tenant(request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ── 관계 가중치 업데이트 (신규) ────────────────────────────────


@router.patch("/relations/{relation_id}")
async def update_relation(relation_id: str, request: Request, body: RelationUpdateRequest):
    """
    기존 관계의 weight/lag/confidence 등 속성을 업데이트.
    PATCH 메서드로 부분 업데이트를 지원한다.
    """
    # Pydantic 모델에서 None이 아닌 필드만 추출
    payload = body.model_dump(exclude_none=True)
    try:
        data = await ontology_service.update_relation(
            tenant_id=_tenant(request), relation_id=relation_id, payload=payload
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.patch("/relations:bulk")
async def bulk_update_relations(request: Request, body: BulkRelationUpdateRequest):
    """
    상관/인과 분석 결과를 관계에 일괄 반영.
    기존 관계가 있으면 업데이트, 없으면 새로 생성한다.

    요청 본문의 각 항목에는 case_id가 필요하므로, query parameter로 case_id를 받는다.
    """
    # body에서 case_id를 첫 항목의 source_id가 속한 case에서 추론하거나, 직접 전달
    if not body.updates:
        raise HTTPException(status_code=400, detail="updates 목록이 비어 있습니다")

    # case_id는 첫 항목의 source 노드에서 추론
    first_source = body.updates[0].source_id
    case_id = ontology_service.get_case_id_for_node(first_source)
    if not case_id:
        raise HTTPException(status_code=400, detail=f"source 노드 '{first_source}'를 찾을 수 없습니다")

    updates_dicts = [item.model_dump(exclude_none=True) for item in body.updates]
    try:
        data = await ontology_service.bulk_update_relations(
            tenant_id=_tenant(request), case_id=case_id, updates=updates_dicts
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.patch("/cases/{case_id}/relations:bulk")
async def bulk_update_relations_with_case(case_id: str, request: Request, body: BulkRelationUpdateRequest):
    """
    case_id를 URL path로 명시적으로 받는 일괄 업데이트 엔드포인트.
    /relations:bulk의 대안으로, case_id를 URL에서 직접 지정할 수 있다.
    """
    if not body.updates:
        raise HTTPException(status_code=400, detail="updates 목록이 비어 있습니다")
    updates_dicts = [item.model_dump(exclude_none=True) for item in body.updates]
    try:
        data = await ontology_service.bulk_update_relations(
            tenant_id=_tenant(request), case_id=case_id, updates=updates_dicts
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/nodes/{node_id}/neighbors")
async def get_neighbors(node_id: str, limit: int = 100):
    try:
        data = await ontology_service.get_neighbors(node_id=node_id, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/nodes/{node_id}/path-to/{target_id}")
async def get_path(node_id: str, target_id: str, max_depth: int = 6):
    try:
        data = await ontology_service.path_to(source_id=node_id, target_id=target_id, max_depth=max_depth)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ── BehaviorModel CRUD (신규) ────────────────────────────────


@router.post("/cases/{case_id}/behavior-models")
async def create_behavior_model(case_id: str, request: Request, body: BehaviorModelCreateRequest):
    """
    OntologyBehavior:Model 노드를 생성하고 READS_FIELD/PREDICTS_FIELD 링크를 설정.
    Neo4j에 :OntologyBehavior:Model 멀티레이블 노드로 저장된다.
    """
    model_data = body.model_dump()
    try:
        data = await ontology_service.create_behavior_model(
            tenant_id=_tenant(request), case_id=case_id, model_data=model_data
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/cases/{case_id}/behavior-models")
async def list_behavior_models(case_id: str):
    """해당 case의 모든 BehaviorModel 목록 조회"""
    data = await ontology_service.list_behavior_models(case_id=case_id)
    return {"success": True, "data": data, "total": len(data)}


@router.get("/cases/{case_id}/model-graph")
async def get_model_graph(case_id: str):
    """
    시뮬레이션용 모델 DAG 구조 반환.
    Vision 서비스의 What-if 시뮬레이션에서 이 API를 호출하여 모델 그래프를 로드한다.

    Returns:
        {models: [...], reads: [...], predicts: [...]}
    """
    data = await ontology_service.get_model_graph(case_id=case_id)
    return {"success": True, "data": data}


# -- O5-1: OWL/RDF Export -----------------------------------------------------


@router.get("/cases/{case_id}/export")
async def export_ontology(case_id: str, format: str = "turtle", request: Request = None):
    tenant_id = _tenant(request) if request else "unknown"
    try:
        if format == "turtle":
            content = await ontology_exporter.export_turtle(case_id, tenant_id)
            return Response(
                content,
                media_type="text/turtle",
                headers={"Content-Disposition": f'attachment; filename="ontology-{case_id}.ttl"'},
            )
        elif format == "jsonld":
            content = await ontology_exporter.export_jsonld(case_id, tenant_id)
            return Response(
                content,
                media_type="application/ld+json",
                headers={"Content-Disposition": f'attachment; filename="ontology-{case_id}.jsonld"'},
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use 'turtle' or 'jsonld'.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}") from exc


# -- O5-2: Quality Dashboard --------------------------------------------------


@router.get("/cases/{case_id}/quality")
async def get_quality_report(case_id: str):
    report = await quality_service.generate_report(case_id)
    return {"success": True, "data": report}


# -- O5-3: HITL Review Queue --------------------------------------------------


@router.get("/cases/{case_id}/hitl")
async def list_hitl_items(case_id: str, status: str = "pending", limit: int = 50, offset: int = 0):
    data = hitl_service.list_items(case_id=case_id, status=status, limit=limit, offset=offset)
    return {"success": True, "data": data}


@router.post("/hitl/submit")
async def submit_hitl(request: Request, body: dict[str, Any]):
    node_id = str(body.get("node_id") or "").strip()
    case_id = str(body.get("case_id") or "").strip()
    if not node_id or not case_id:
        raise HTTPException(status_code=400, detail="node_id and case_id are required")
    data = hitl_service.submit_for_review(node_id=node_id, case_id=case_id, tenant_id=_tenant(request))
    return {"success": True, "data": data}


@router.post("/hitl/{item_id}/approve")
async def approve_hitl(item_id: str, request: Request, body: dict[str, Any] | None = None):
    body = body or {}
    reviewer_id = str(body.get("reviewer_id") or _tenant(request))
    comment = str(body.get("comment") or "")
    try:
        data = await hitl_service.approve(item_id=item_id, reviewer_id=reviewer_id, comment=comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/hitl/{item_id}/reject")
async def reject_hitl(item_id: str, request: Request, body: dict[str, Any] | None = None):
    body = body or {}
    reviewer_id = str(body.get("reviewer_id") or _tenant(request))
    comment = str(body.get("comment") or "")
    try:
        data = await hitl_service.reject(item_id=item_id, reviewer_id=reviewer_id, comment=comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# -- O5-4: Version Management (Snapshots) -------------------------------------


@router.post("/cases/{case_id}/snapshots")
async def create_snapshot(case_id: str, request: Request):
    data = await snapshot_service.create_snapshot(case_id=case_id, tenant_id=_tenant(request))
    return {"success": True, "data": data}


@router.get("/cases/{case_id}/snapshots")
async def list_snapshots(case_id: str):
    data = await snapshot_service.list_snapshots(case_id=case_id)
    return {"success": True, "data": data}


@router.get("/snapshots/diff")
async def diff_snapshots(snapshot_a: str, snapshot_b: str):
    try:
        data = await snapshot_service.diff_snapshots(snapshot_a=snapshot_a, snapshot_b=snapshot_b)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# -- O5-5: GlossaryTerm <-> Ontology Bridge ------------------------------------


@router.get("/cases/{case_id}/glossary-suggest")
async def suggest_glossary(case_id: str, term: str):
    if not term.strip():
        raise HTTPException(status_code=400, detail="term is required")
    data = await ontology_service.suggest_glossary_matches(term_name=term, case_id=case_id)
    return {"success": True, "data": data}


@router.post("/cases/{case_id}/glossary-link")
async def create_glossary_link(case_id: str, body: dict[str, Any]):
    term_id = str(body.get("term_id") or "").strip()
    node_id = str(body.get("node_id") or "").strip()
    if not term_id or not node_id:
        raise HTTPException(status_code=400, detail="term_id and node_id are required")
    try:
        data = await ontology_service.create_glossary_link(term_id=term_id, node_id=node_id, case_id=case_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Link creation failed: {exc}") from exc
    return {"success": True, "data": data}
