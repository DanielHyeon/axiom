"""
시멘틱 계약 API 라우터 — Control Plane 엔드포인트

온톨로지 개념 거버넌스 + 시멘틱 엔티티/지표/차원/조인/품질 계약의
정의·승인·카탈로그를 담당한다.
실제 쿼리 실행(Data Plane)은 Weaver 또는 후속 runtime에서 수행한다.

주의: 모든 엔드포인트는 sync(def)로 선언한다.
SemanticStore가 동기 psycopg2를 사용하므로, FastAPI가 자동으로
스레드풀에서 실행하여 이벤트 루프 차단을 방지한다.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.models.semantic_models import (
    OntologyConceptCreate,
    OntologyConceptUpdate,
    OntologyConceptStatusChange,
    OntologyTermCreate,
    OntologyTermBulkCreate,
    SemanticEntityCreate,
    SemanticEntityUpdate,
    SemanticMeasureCreate,
    SemanticMeasureUpdate,
    SemanticDimensionCreate,
    SemanticDimensionUpdate,
    JoinContractCreate,
    JoinContractUpdate,
    QualityContractCreate,
    SemanticPublishRequest,
    GrainContractCreate,
    GrainContractUpdate,
    CompileRequest,
    ContextPackCreate,
    ContextPackUpdate,
    PromptPolicyCreate,
    PromptPolicyUpdate,
    TrainingQueryRequest,
    SemanticSegmentCreate,
    SemanticSegmentUpdate,
    TimeContractCreate,
    TimeContractUpdate,
    AccessPolicyCreate,
    AccessPolicyUpdate,
    SnapshotBuildRequest,
    SnapshotActivateRequest,
    SnapshotInvalidateRequest,
    ConsumerBindingHeartbeat,
    OntologyRuleCreate,
    OntologyRuleUpdate,
    OntologyPolicyCreate,
    OntologyPolicyUpdate,
    OntologyRelationCreate,
    OntologyRelationUpdate,
    AliasGroupCreate,
    ExpansionRuleCreate,
    ExpansionRuleUpdate,
    IntentModelCreate,
    InferenceLogCreate,
    QuestionFeedbackCreate,
)
from app.services.semantic_store import SemanticStore
from app.services.semantic_compiler import SemanticCompiler
from app.services.quality_trust import quality_trust_service
from app.services.semantic_yaml import SemanticYamlExporter, SemanticYamlImporter
from app.services.semantic_snapshot_service import SnapshotBuilder, SnapshotRegistry

router = APIRouter(
    prefix="/api/v3/synapse/semantic",
    tags=["Semantic Contract"],
)

# 모듈 레벨 싱글턴 (기존 Synapse 패턴)
_store = SemanticStore()
_compiler = SemanticCompiler(_store)
_yaml_exporter = SemanticYamlExporter(_store)
_yaml_importer = SemanticYamlImporter(_store)
_snapshot_builder = SnapshotBuilder(_store)
_snapshot_registry = SnapshotRegistry()

# limit 상한
_MAX_LIMIT = 500


def _tenant(request: Request) -> str:
    """TenantMiddleware가 설정한 tenant_id 추출"""
    tid = getattr(request.state, "tenant_id", None)
    if not tid:
        raise HTTPException(status_code=401, detail="tenant_id가 확인되지 않았습니다")
    return tid


def _user(request: Request) -> str | None:
    """현재 사용자 ID (reviewer 기록용)"""
    return getattr(request.state, "user_id", None)


def _clamp_limit(limit: int) -> int:
    return min(max(limit, 1), _MAX_LIMIT)


# ========================================
# 온톨로지 개념 (L3 거버넌스 확장)
# ========================================

@router.post("/concepts", status_code=201)
def create_concept(request: Request, body: OntologyConceptCreate):
    """온톨로지 개념 등록 — 비즈니스 정의, 책임자, 감도 수준 포함"""
    try:
        data = _store.create_concept(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/concepts")
def list_concepts(
    request: Request,
    case_id: str | None = None,
    status: str | None = None,
    approval_scope: str | None = None,
    domain_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """개념 목록 조회 — 상태/케이스/승인스코프/도메인 필터 지원 (§5.1, §5.2)"""
    data = _store.list_concepts(
        _tenant(request), case_id=case_id, status=status,
        approval_scope=approval_scope, domain_id=domain_id,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/concepts/{concept_id}")
def get_concept(request: Request, concept_id: str):
    """개념 단건 조회 — 바인딩된 용어 목록 포함"""
    tenant = _tenant(request)
    concept = _store.get_concept(tenant, concept_id)
    if not concept:
        raise HTTPException(status_code=404, detail=f"concept_id '{concept_id}'를 찾을 수 없습니다")
    terms = _store.list_terms_by_concept(tenant, concept_id)
    return {"success": True, "data": {**concept, "terms": terms}}


@router.put("/concepts/{concept_id}")
def update_concept(request: Request, concept_id: str, body: OntologyConceptUpdate):
    """개념 수정 — None 필드 무시 (PATCH 방식), 버전 자동 증가"""
    try:
        data = _store.update_concept(_tenant(request), concept_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.patch("/concepts/{concept_id}/status")
def change_concept_status(request: Request, concept_id: str, body: OntologyConceptStatusChange):
    """개념 상태 전이 — draft→review→approved→deprecated (규칙 기반)

    §5.2: approval_scope='domain'인 개념은 도메인 스튜어드가 직접 review→approved 승인 가능.
    approval_scope='global'인 개념은 관리자(admin/manager) 리뷰 필요.
    """
    tenant = _tenant(request)
    user_id = _user(request)
    try:
        # §5.2: global scope + approved 전이 시 admin/manager 권한 확인
        if body.status == "approved":
            concept = _store.get_concept(tenant, concept_id)
            if not concept:
                raise HTTPException(status_code=404, detail=f"concept_id '{concept_id}'를 찾을 수 없습니다")
            scope = concept.get("approval_scope", "global")
            if scope == "global":
                # 전역 스코프: admin, manager, 또는 서비스 계정(system)만 승인 가능
                role = getattr(request.state, "user_role", None)
                if role not in {"admin", "manager", "system"}:
                    raise HTTPException(
                        status_code=403,
                        detail="global 승인 스코프: admin 또는 manager 권한이 필요합니다",
                    )
            # domain 스코프: 누구나 review→approved 전이 가능 (도메인 스튜어드 신뢰)
        data = _store.change_concept_status(tenant, concept_id, body.status, approved_by=user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# 온톨로지 용어 (L3 동의어/약어 관리)
# ========================================

@router.post("/terms", status_code=201)
def create_term(request: Request, body: OntologyTermCreate):
    """온톨로지 용어 등록 — 개념에 동의어/약어/레거시 용어 바인딩"""
    try:
        data = _store.create_term(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/terms/bulk", status_code=201)
def create_terms_bulk(request: Request, body: OntologyTermBulkCreate):
    """용어 일괄 등록"""
    try:
        data = _store.create_terms_bulk(_tenant(request), [t.model_dump() for t in body.terms])
    except (KeyError, ValueError) as exc:
        status_code = 404 if isinstance(exc, KeyError) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {"success": True, "data": data, "count": len(data)}


@router.get("/terms/search")
def search_terms(request: Request, q: str, limit: int = Query(50, ge=1, le=200)):
    """용어 검색 — surface_form ILIKE 매칭"""
    data = _store.search_terms(_tenant(request), q, limit=_clamp_limit(limit))
    return {"success": True, "data": data, "count": len(data)}


# ========================================
# 시멘틱 엔티티 (L2)
# ========================================

@router.post("/entities", status_code=201)
def create_entity(request: Request, body: SemanticEntityCreate):
    """시멘틱 엔티티 등록 — 물리 테이블을 의미 계층으로 승격"""
    try:
        data = _store.create_entity(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/entities")
def list_entities(
    request: Request,
    case_id: str | None = None,
    domain_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """시멘틱 엔티티 목록 조회 — §5.1: domain_id 필터 지원"""
    data = _store.list_entities(_tenant(request), case_id=case_id, domain_id=domain_id, limit=_clamp_limit(limit), offset=offset)
    return {"success": True, "data": data, "count": len(data)}


@router.get("/entities/{entity_id}")
def get_entity(request: Request, entity_id: str):
    data = _store.get_entity(_tenant(request), entity_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"entity_id '{entity_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/entities/{entity_id}")
def update_entity(request: Request, entity_id: str, body: SemanticEntityUpdate):
    try:
        data = _store.update_entity(_tenant(request), entity_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# 시멘틱 지표 (L2)
# ========================================

@router.post("/measures", status_code=201)
def create_measure(request: Request, body: SemanticMeasureCreate):
    """시멘틱 지표 등록 — 중앙화된 단일 지표 정의"""
    try:
        data = _store.create_measure(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/measures")
def list_measures(
    request: Request,
    case_id: str | None = None,
    entity_id: str | None = None,
    domain_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """시멘틱 지표 목록 조회 — §5.1: domain_id 필터 지원"""
    data = _store.list_measures(_tenant(request), case_id=case_id, entity_id=entity_id, domain_id=domain_id, limit=_clamp_limit(limit), offset=offset)
    return {"success": True, "data": data, "count": len(data)}


@router.get("/measures/{measure_id}")
def get_measure(request: Request, measure_id: str):
    data = _store.get_measure(_tenant(request), measure_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"measure_id '{measure_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/measures/{measure_id}")
def update_measure(request: Request, measure_id: str, body: SemanticMeasureUpdate):
    try:
        data = _store.update_measure(_tenant(request), measure_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# 시멘틱 차원 (L2)
# ========================================

@router.post("/dimensions", status_code=201)
def create_dimension(request: Request, body: SemanticDimensionCreate):
    """시멘틱 차원 등록"""
    try:
        data = _store.create_dimension(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/dimensions")
def list_dimensions(
    request: Request,
    case_id: str | None = None,
    entity_id: str | None = None,
    domain_id: str | None = None,
    conformed_group: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """시멘틱 차원 목록 조회 — §5.1: domain_id, conformed_group 필터 지원"""
    data = _store.list_dimensions(
        _tenant(request), case_id=case_id, entity_id=entity_id,
        domain_id=domain_id, conformed_group=conformed_group,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/dimensions/{dimension_id}")
def get_dimension(request: Request, dimension_id: str):
    data = _store.get_dimension(_tenant(request), dimension_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"dimension_id '{dimension_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/dimensions/{dimension_id}")
def update_dimension(request: Request, dimension_id: str, body: SemanticDimensionUpdate):
    try:
        data = _store.update_dimension(_tenant(request), dimension_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# 조인 계약 (L2)
# ========================================

@router.post("/joins", status_code=201)
def create_join_contract(request: Request, body: JoinContractCreate):
    """조인 계약 등록 — 허용/금지 조인 명시화"""
    try:
        data = _store.create_join_contract(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/joins")
def list_join_contracts(
    request: Request,
    case_id: str | None = None,
    allowed_for_ai: bool | None = None,
    domain_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """조인 계약 목록 조회 — §5.1: domain_id 필터 지원"""
    data = _store.list_join_contracts(
        _tenant(request), case_id=case_id, allowed_for_ai=allowed_for_ai,
        domain_id=domain_id, limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/joins/{join_id}")
def get_join_contract(request: Request, join_id: str):
    data = _store.get_join_contract(_tenant(request), join_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"join_id '{join_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/joins/{join_id}")
def update_join_contract(request: Request, join_id: str, body: JoinContractUpdate):
    try:
        data = _store.update_join_contract(_tenant(request), join_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# 품질 계약 (L2)
# ========================================

@router.post("/quality-contracts", status_code=201)
def create_quality_contract(request: Request, body: QualityContractCreate):
    """품질 계약 등록 — 엔티티/지표/차원에 대한 품질 SLA"""
    try:
        data = _store.create_quality_contract(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/quality-contracts")
def list_quality_contracts(
    request: Request,
    case_id: str | None = None,
    target_type: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    data = _store.list_quality_contracts(
        _tenant(request), case_id=case_id, target_type=target_type,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


# ========================================
# 그레인 계약 (L2)
# ========================================

@router.post("/grains", status_code=201)
def create_grain_contract(request: Request, body: GrainContractCreate):
    """그레인 계약 등록 — 엔티티 행 단위 유일성 규칙"""
    try:
        data = _store.create_grain_contract(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/grains")
def list_grain_contracts(
    request: Request,
    case_id: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    data = _store.list_grain_contracts(
        _tenant(request), case_id=case_id, entity_id=entity_id,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/grains/{grain_id}")
def get_grain_contract(request: Request, grain_id: str):
    data = _store.get_grain_contract(_tenant(request), grain_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"grain_id '{grain_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/grains/{grain_id}")
def update_grain_contract(request: Request, grain_id: str, body: GrainContractUpdate):
    try:
        data = _store.update_grain_contract(_tenant(request), grain_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# §5.2 시멘틱 세그먼트 (L2)
# ========================================

@router.post("/segments", status_code=201)
def create_segment(request: Request, body: SemanticSegmentCreate):
    """시멘틱 세그먼트 등록 — 엔티티의 필터 기반 데이터 분할"""
    try:
        data = _store.create_segment(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/segments")
def list_segments(
    request: Request,
    entity_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """세그먼트 목록 조회 — entity_id 필터 지원"""
    data = _store.list_segments(
        _tenant(request), entity_id=entity_id,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/segments/{segment_id}")
def get_segment(request: Request, segment_id: str):
    data = _store.get_segment(_tenant(request), segment_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"segment_id '{segment_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/segments/{segment_id}")
def update_segment(request: Request, segment_id: str, body: SemanticSegmentUpdate):
    try:
        data = _store.update_segment(_tenant(request), segment_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/segments/{segment_id}")
def delete_segment(request: Request, segment_id: str):
    deleted = _store.delete_segment(_tenant(request), segment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"segment_id '{segment_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


# ========================================
# §5.2 시간 계약 (L2)
# ========================================

@router.post("/time-contracts", status_code=201)
def create_time_contract(request: Request, body: TimeContractCreate):
    """시간 계약 등록 — 엔티티의 시간 축 의미론 정의"""
    try:
        data = _store.create_time_contract(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/time-contracts")
def list_time_contracts(
    request: Request,
    entity_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """시간 계약 목록 조회 — entity_id 필터 지원"""
    data = _store.list_time_contracts(
        _tenant(request), entity_id=entity_id,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/time-contracts/{time_contract_id}")
def get_time_contract(request: Request, time_contract_id: str):
    data = _store.get_time_contract(_tenant(request), time_contract_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"time_contract_id '{time_contract_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/time-contracts/{time_contract_id}")
def update_time_contract(request: Request, time_contract_id: str, body: TimeContractUpdate):
    try:
        data = _store.update_time_contract(_tenant(request), time_contract_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/time-contracts/{time_contract_id}")
def delete_time_contract(request: Request, time_contract_id: str):
    deleted = _store.delete_time_contract(_tenant(request), time_contract_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"time_contract_id '{time_contract_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


# ========================================
# §5.2 접근 정책 (L2)
# ========================================

@router.post("/access-policies", status_code=201)
def create_access_policy(request: Request, body: AccessPolicyCreate):
    """접근 정책 등록 — 행/열 수준 데이터 접근 제어"""
    try:
        data = _store.create_access_policy(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/access-policies")
def list_access_policies(
    request: Request,
    entity_id: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """접근 정책 목록 조회 — entity_id, is_active 필터 지원"""
    data = _store.list_access_policies(
        _tenant(request), entity_id=entity_id, is_active=is_active,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/access-policies/{access_policy_id}")
def get_access_policy(request: Request, access_policy_id: str):
    data = _store.get_access_policy(_tenant(request), access_policy_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"access_policy_id '{access_policy_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/access-policies/{access_policy_id}")
def update_access_policy(request: Request, access_policy_id: str, body: AccessPolicyUpdate):
    try:
        data = _store.update_access_policy(_tenant(request), access_policy_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/access-policies/{access_policy_id}")
def delete_access_policy(request: Request, access_policy_id: str):
    deleted = _store.delete_access_policy(_tenant(request), access_policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"access_policy_id '{access_policy_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


# ========================================
# Semantic Compiler (검증 + SQL 생성)
# ========================================

@router.post("/compile/entity/{entity_id}")
def compile_entity(request: Request, entity_id: str):
    """엔티티 계약 컴파일 — 검증 + SQL 뷰 템플릿 생성"""
    result = _compiler.compile_entity(_tenant(request), entity_id)
    return {"success": True, "data": result}


@router.post("/compile/measure/{measure_id}")
def compile_measure(request: Request, measure_id: str):
    """지표 계약 컴파일 — 검증 + SQL SELECT 생성"""
    result = _compiler.compile_measure(_tenant(request), measure_id)
    return {"success": True, "data": result}


# ========================================
# 배포 + 카탈로그
# ========================================

@router.post("/publish", status_code=201)
def publish_semantic_object(request: Request, body: SemanticPublishRequest):
    """시멘틱 객체 배포 — ontology binding 검증 후 릴리스 기록 생성"""
    try:
        data = _store.publish(
            _tenant(request),
            body.semantic_object_type,
            body.semantic_object_id,
            reviewer=_user(request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/releases")
def list_releases(request: Request, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """배포 이력 조회"""
    data = _store.list_releases(_tenant(request), limit=_clamp_limit(limit), offset=offset)
    return {"success": True, "data": data, "count": len(data)}


@router.get("/catalog")
def get_catalog(request: Request, case_id: str | None = None):
    """통합 카탈로그 — 개념 + 엔티티 + 지표 + 차원 + 조인 요약"""
    data = _store.get_catalog(_tenant(request), case_id=case_id)
    return {"success": True, "data": data}


# ========================================
# AI 컨텍스트 (Oracle/LLM 소비용)
# ========================================

@router.get("/ai-context")
def get_ai_context(request: Request, case_id: str | None = None):
    """AI 소비용 시멘틱 컨텍스트 팩 — approved 계약만 포함

    Oracle NL2SQL이 raw schema 대신 이 컨텍스트를 소비한다.
    SQL 표현식이 포함되므로 서비스 토큰 또는 ai:use 권한 필요.
    """
    # RBAC: 서비스 계정(system) 또는 analyst 이상만 접근 허용
    role = getattr(request.state, "user_role", None)
    allowed_roles = {"system", "admin", "analyst", "engineer"}
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="ai-context 접근 권한이 없습니다 (analyst 이상 필요)")
    data = _store.get_ai_context(_tenant(request), case_id=case_id)
    return {"success": True, "data": data}


# ========================================
# AI 컨텍스트 팩 (L5)
# ========================================

@router.post("/context-packs", status_code=201)
def create_context_pack(request: Request, body: ContextPackCreate):
    """AI 컨텍스트 팩 등록 — 의도별 시멘틱 컨텍스트 프리셋"""
    try:
        data = _store.create_context_pack(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/context-packs")
def list_context_packs(
    request: Request,
    case_id: str | None = None,
    intent_type: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    data = _store.list_context_packs(
        _tenant(request), case_id=case_id, intent_type=intent_type,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/context-packs/{context_pack_id}")
def get_context_pack(request: Request, context_pack_id: str):
    data = _store.get_context_pack(_tenant(request), context_pack_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"context_pack_id '{context_pack_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/context-packs/{context_pack_id}")
def update_context_pack(request: Request, context_pack_id: str, body: ContextPackUpdate):
    try:
        data = _store.update_context_pack(_tenant(request), context_pack_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/context-packs/{context_pack_id}")
def delete_context_pack(request: Request, context_pack_id: str):
    deleted = _store.delete_context_pack(_tenant(request), context_pack_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"context_pack_id '{context_pack_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


@router.get("/context-packs/{context_pack_id}/resolve")
def resolve_context_pack(request: Request, context_pack_id: str):
    """컨텍스트 팩을 해석 — 포함된 시멘틱 객체 + 프롬프트 정책을 조합하여 반환"""
    role = getattr(request.state, "user_role", None)
    allowed_roles = {"system", "admin", "analyst", "engineer"}
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="context-pack resolve 접근 권한이 없습니다")
    try:
        data = _store.resolve_context_pack(_tenant(request), context_pack_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# 프롬프트 정책 (L5)
# ========================================

@router.post("/prompt-policies", status_code=201)
def create_prompt_policy(request: Request, body: PromptPolicyCreate):
    """프롬프트 정책 등록 — ContextPack에 바인딩되는 LLM 가드레일 규칙"""
    try:
        data = _store.create_prompt_policy(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/prompt-policies")
def list_prompt_policies(request: Request, context_pack_id: str):
    """특정 ContextPack의 프롬프트 정책 목록"""
    data = _store.list_prompt_policies(_tenant(request), context_pack_id)
    return {"success": True, "data": data, "count": len(data)}


@router.delete("/prompt-policies/{prompt_policy_id}")
def delete_prompt_policy(request: Request, prompt_policy_id: str):
    deleted = _store.delete_prompt_policy(_tenant(request), prompt_policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"prompt_policy_id '{prompt_policy_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


# ========================================
# L4: Reasoning & Governance — 충돌 탐지 + 영향 분석
# ========================================

_VALID_IMPACT_OBJECT_TYPES = {"concept", "entity", "measure", "dimension", "join"}


@router.get("/conflicts")
def detect_semantic_conflicts(request: Request):
    """시멘틱 충돌 탐지 — 동일 이름/용어를 가진 서로 다른 개념/지표를 찾는다.

    L4 거버넌스 계층에서 데이터 품질 문제를 사전에 발견하기 위한 엔드포인트.
    """
    data = _store.detect_conflicts(_tenant(request))
    return {"success": True, "data": data}


@router.get("/impact/{object_type}/{object_id}")
def analyze_semantic_impact(request: Request, object_type: str, object_id: str):
    """영향 분석 — 특정 시멘틱 객체 변경 시 영향받는 downstream 객체를 분석한다.

    지원하는 object_type: concept, entity, measure, dimension, join
    """
    if object_type not in _VALID_IMPACT_OBJECT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"object_type은 {sorted(_VALID_IMPACT_OBJECT_TYPES)} 중 하나여야 합니다: {object_type}",
        )
    data = _store.analyze_impact(_tenant(request), object_type, object_id)
    return {"success": True, "data": data}


# ========================================
# Sprint 2: 품질 신뢰 등급 (Quality Trust Tier)
# ========================================

@router.get("/quality/runtime/{entity_id}")
def get_quality_runtime(request: Request, entity_id: str):
    """엔티티별 품질 신뢰 등급 조회 — Oracle/Canvas 소비용

    시멘틱 엔티티에 연결된 품질 계약의 점수를 기반으로
    4단계 신뢰 등급(TRUSTED/CAUTION/REFERENCE_ONLY/BLOCKED)을 결정한다.
    """
    tenant_id = _tenant(request)

    # 1. 엔티티 존재 확인
    entity = _store.get_entity(tenant_id, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"entity_id '{entity_id}'를 찾을 수 없습니다")

    # 2. 해당 엔티티에 연결된 품질 계약에서 점수 수집
    # — quality_contracts 테이블에서 target_type='entity', target_id=entity_id인 행을 조회
    dimension_scores = _collect_quality_scores(tenant_id, entity_id)

    # 3. 신뢰 등급 평가
    result = quality_trust_service.evaluate(dimension_scores)

    return {
        "success": True,
        "data": {
            "entity_id": entity_id,
            "trust_tier": result.trust_tier,
            "final_score": result.final_score,
            "allow_execution": result.allow_execution,
            "response_mode": result.response_mode,
            "user_banner": result.user_banner,
            "hard_fail_codes": result.hard_fail_codes,
            "soft_fail_codes": result.soft_fail_codes,
            "dimension_breakdown": result.dimension_breakdown,
        },
    }


class QualityEvaluateRequest(BaseModel):
    """품질 점수 직접 평가 요청 모델"""
    dimension_scores: dict[str, float]


@router.post("/quality/evaluate")
def evaluate_quality_scores(request: Request, body: QualityEvaluateRequest):
    """품질 점수 직접 평가 — 차원별 점수를 받아 신뢰 등급을 반환

    Oracle이 시멘틱 컨텍스트의 품질 경고를 기반으로
    등급을 계산할 때 사용할 수 있는 유틸리티 엔드포인트.
    """
    _tenant(request)  # 인증 확인

    dimension_scores: dict[str, float] = body.dimension_scores
    if not dimension_scores:
        raise HTTPException(status_code=400, detail="dimension_scores가 필요합니다")

    result = quality_trust_service.evaluate(dimension_scores)

    return {
        "success": True,
        "data": {
            "trust_tier": result.trust_tier,
            "final_score": result.final_score,
            "allow_execution": result.allow_execution,
            "response_mode": result.response_mode,
            "user_banner": result.user_banner,
            "hard_fail_codes": result.hard_fail_codes,
            "soft_fail_codes": result.soft_fail_codes,
            "dimension_breakdown": result.dimension_breakdown,
        },
    }


# ========================================
# P3 §5.4: Metrics as Code — YAML Export/Import
# ========================================

class YamlImportRequest(BaseModel):
    """YAML import 요청 — YAML 문자열 + 옵션"""
    yaml_content: str
    dry_run: bool = False
    git_commit_sha: str | None = None
    case_id: str = ""


@router.get("/export/yaml")
def export_yaml(
    request: Request,
    domain_id: str | None = None,
    case_id: str | None = None,
    format: str = Query("single", pattern="^(single|multi)$"),
):
    """시멘틱 계약을 YAML로 내보낸다 (Metrics as Code).

    format 파라미터:
    - single: 하나의 YAML 문서로 내보냄 (기본값)
    - multi: 동일 (현재 버전에서는 single과 동일)

    Content-Type: application/x-yaml 로 반환한다.
    """
    from fastapi.responses import Response

    tenant = _tenant(request)
    yaml_content = _yaml_exporter.export(
        tenant_id=tenant,
        domain_id=domain_id,
        case_id=case_id,
    )
    return Response(
        content=yaml_content,
        media_type="application/x-yaml",
        headers={"Content-Disposition": "attachment; filename=semantic-contracts.yaml"},
    )


@router.get("/export/yaml/json")
def export_yaml_as_json(
    request: Request,
    domain_id: str | None = None,
    case_id: str | None = None,
):
    """시멘틱 계약 YAML을 JSON 래퍼로 반환한다.

    프론트엔드에서 JSON으로 받아 파일 다운로드 처리할 때 사용.
    """
    tenant = _tenant(request)
    yaml_content = _yaml_exporter.export(
        tenant_id=tenant,
        domain_id=domain_id,
        case_id=case_id,
    )
    return {"success": True, "data": {"yaml": yaml_content}}


@router.post("/import/yaml")
def import_yaml(request: Request, body: YamlImportRequest):
    """YAML에서 시멘틱 계약을 가져온다 (Metrics as Code).

    전략: ID 기준 upsert — 존재하면 update, 없으면 create.
    dry_run=true이면 검증만 수행하고 DB 변경 없음.
    git_commit_sha를 전달하면 릴리스 이력에 기록한다.
    """
    tenant = _tenant(request)
    result = _yaml_importer.import_yaml(
        tenant_id=tenant,
        yaml_content=body.yaml_content,
        dry_run=body.dry_run,
        git_sha=body.git_commit_sha,
        case_id=body.case_id,
    )

    if result.get("errors"):
        # 검증 오류가 있으면 400 반환
        raise HTTPException(
            status_code=400,
            detail={"message": "YAML import 검증 실패", "errors": result["errors"]},
        )

    return {"success": True, "data": result}


def _collect_quality_scores(tenant_id: str, entity_id: str) -> dict[str, float]:
    """엔티티에 연결된 품질 점수를 수집한다.

    두 단계로 점수를 조회한다 (실측 우선):
    1. Weaver 품질 수집 파이프라인의 실제 측정값 (quality_scores 테이블)
    2. 실측이 없으면 → 품질 계약의 임계치를 기본 점수로 사용 (폴백)

    주의: 품질 계약 임계치는 "목표"이지 "실측"이 아니다.
    실측이 없을 때만 보수적 기본값으로 사용한다.
    """
    import httpx

    scores: dict[str, float] = {}

    # --- 1단계: Weaver 실측 점수 조회 ---
    try:
        # Weaver 품질 API 호출 (내부 서비스 통신)
        weaver_url = "http://weaver:8001/api/quality/scores/entity/" + entity_id
        resp = httpx.get(weaver_url, timeout=5.0, headers={"X-Tenant-Id": tenant_id})
        if resp.status_code == 200:
            data = resp.json()
            # Weaver가 반환하는 실측 점수를 차원별로 매핑
            if data.get("freshness_score") is not None:
                scores["freshness"] = float(data["freshness_score"])
            if data.get("completeness_score") is not None:
                scores["completeness"] = float(data["completeness_score"])
            if data.get("uniqueness_score") is not None:
                scores["uniqueness"] = float(data["uniqueness_score"])
            if data.get("owner_score") is not None:
                scores["owner_coverage"] = float(data["owner_score"])
            if data.get("lineage_score") is not None:
                scores["lineage_completeness"] = float(data["lineage_score"])
            # 실측 점수가 있으면 바로 반환
            if scores:
                return scores
    except Exception as exc:
        # Weaver 호출 실패 시 → 폴백으로 진행 (계약 임계치 기반)
        import logging
        logging.getLogger("synapse.quality").warning("weaver_quality_fetch_failed: %s", exc)

    # --- 2단계: 품질 계약 임계치 기반 보수적 기본값 (폴백) ---
    try:
        all_contracts = _store.list_quality_contracts(tenant_id, target_type="entity")
        contracts = [qc for qc in all_contracts if qc.get("target_id") == entity_id]
        if not contracts:
            # 품질 계약도 없으면 보수적 기본값
            return {"freshness": 60, "completeness": 60, "uniqueness": 70}

        # 계약 임계치를 기본 점수로 사용 (실측이 아닌 "최소 기대치")
        # 주의: 이 값은 실측이 아니므로 신뢰도가 낮다
        for qc in contracts:
            if qc.get("completeness_threshold") is not None:
                val = float(qc["completeness_threshold"])
                scores.setdefault("completeness", val if val > 1 else val * 100)
            if qc.get("uniqueness_threshold") is not None:
                val = float(qc["uniqueness_threshold"])
                scores.setdefault("uniqueness", val if val > 1 else val * 100)
            # freshness SLA는 점수로 변환하지 않음 (SLA ≠ 실측)
            # 대신 보수적 기본값 사용
            scores.setdefault("freshness", 60)

    except Exception:
        scores = {"freshness": 60, "completeness": 60, "uniqueness": 70}

    return scores

# ========================================
# P3 §5.3: ML/Feature Source 바인딩
# ========================================

@router.get("/features")
def list_feature_sources(
    request: Request,
    case_id: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """feature_source 타입 엔티티 목록 — ML 피처 소스 전용 조회"""
    data = _store.list_feature_sources(
        _tenant(request), case_id=case_id,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.post("/features/training-query")
def generate_training_query(request: Request, body: TrainingQueryRequest):
    """학습 데이터셋 SQL 생성 — feature_source 엔티티 기반

    feature_config의 training_query_template을 렌더링하여
    ML 팀이 바로 사용할 수 있는 학습용 SQL을 반환한다.
    """
    try:
        data = _store.generate_training_query(
            _tenant(request),
            body.entity_id,
            columns=body.columns,
            date_range=body.date_range,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/features/{entity_id}/consistency")
def check_feature_consistency(request: Request, entity_id: str):
    """BI-ML 피처 일관성 검증 — 동일 이름 지표의 sql_expression 비교

    feature_source 엔티티의 시멘틱 지표와 fact 엔티티의 지표를
    이름 기반으로 매칭하여 정의 불일치를 보고한다.
    """
    try:
        data = _store.check_feature_consistency(_tenant(request), entity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# 시멘틱 스냅샷 (Sprint 3)
# ========================================

@router.post("/snapshots/build", status_code=201)
def build_snapshot(request: Request, body: SnapshotBuildRequest):
    """스냅샷 빌드 — 현재 활성 시멘틱 계약을 immutable 스냅샷으로 물질화한다.

    빌드 완료 시 status=READY로 생성된다. 활성화는 별도 엔드포인트.
    """
    tenant_id = _tenant(request)
    user_id = _user(request) or "system"
    try:
        data = _snapshot_builder.build_from_release(
            tenant_id=tenant_id,
            release_id=body.release_id,
            release_version=body.release_version,
            created_by=user_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"스냅샷 빌드 실패: {exc}") from exc
    return {"success": True, "data": data}


@router.get("/snapshots/active")
def get_active_snapshot(request: Request, consumer_name: str | None = None):
    """현재 활성 스냅샷 조회 — 소비자 바인딩 우선, 없으면 최신 ACTIVE"""
    tenant_id = _tenant(request)
    data = _snapshot_registry.find_active(tenant_id, consumer_name=consumer_name)
    if not data:
        raise HTTPException(status_code=404, detail="활성 스냅샷이 없습니다")
    return {"success": True, "data": data}


@router.get("/snapshots")
def list_snapshots_endpoint(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """스냅샷 목록 조회 (최신순)"""
    tenant_id = _tenant(request)
    data = _snapshot_registry.list_snapshots(tenant_id, limit=limit, offset=offset)
    return {"success": True, "data": data, "count": len(data)}


@router.get("/snapshots/{version}")
def get_snapshot_detail(request: Request, version: str):
    """특정 스냅샷 상세 조회 (아티팩트 포함)"""
    _tenant(request)  # 인증 확인
    data = _snapshot_registry.get_snapshot(version)
    if not data:
        raise HTTPException(status_code=404, detail=f"snapshot_version '{version}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.post("/snapshots/{version}/activate")
def activate_snapshot_endpoint(request: Request, version: str):
    """스냅샷 활성화 — READY → ACTIVE 전환 (기존 ACTIVE는 READY로 강등)"""
    tenant_id = _tenant(request)
    try:
        data = _snapshot_registry.activate(version, tenant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/snapshots/{version}/invalidate")
def invalidate_snapshot_endpoint(request: Request, version: str, body: SnapshotInvalidateRequest):
    """스냅샷 무효화 — 더 이상 소비 불가"""
    tenant_id = _tenant(request)
    try:
        data = _snapshot_registry.invalidate(version, tenant_id, reason=body.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/consumers/bindings/heartbeat")
def consumer_binding_heartbeat(request: Request, body: ConsumerBindingHeartbeat):
    """소비자 바인딩 하트비트 — 주기적으로 호출하여 바인딩 갱신"""
    _tenant(request)  # 인증 확인
    try:
        data = _snapshot_registry.register_binding(
            consumer_name=body.consumer_name,
            instance_id=body.consumer_instance_id,
            snapshot_version=body.snapshot_version,
            mode=body.binding_mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"바인딩 등록 실패: {exc}") from exc
    return {"success": True, "data": data}


# ========================================
# 온톨로지 관계 (§5.1 Neo4j 보완 PG 메타데이터)
# ========================================

@router.post("/relations", status_code=201)
def create_relation(request: Request, body: OntologyRelationCreate):
    """온톨로지 관계 등록 — 두 개념 간 구조화된 관계 메타데이터 (PG)"""
    try:
        data = _store.create_relation(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/relations")
def list_relations(
    request: Request,
    subject_concept_id: str | None = None,
    object_concept_id: str | None = None,
    predicate_type: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """관계 목록 조회 — 주체/객체/술어 필터"""
    data = _store.list_relations(
        _tenant(request),
        subject_id=subject_concept_id,
        object_id=object_concept_id,
        predicate_type=predicate_type,
        limit=_clamp_limit(limit),
        offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/relations/{relation_id}")
def get_relation(request: Request, relation_id: str):
    """관계 단건 조회"""
    rel = _store.get_relation(_tenant(request), relation_id)
    if not rel:
        raise HTTPException(status_code=404, detail=f"relation_id '{relation_id}'를 찾을 수 없습니다")
    return {"success": True, "data": rel}


@router.put("/relations/{relation_id}")
def update_relation(request: Request, relation_id: str, body: OntologyRelationUpdate):
    """관계 수정 — None 필드 무시 (PATCH 방식)"""
    try:
        data = _store.update_relation(_tenant(request), relation_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/relations/{relation_id}")
def delete_relation(request: Request, relation_id: str):
    """관계 삭제"""
    deleted = _store.delete_relation(_tenant(request), relation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"relation_id '{relation_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


# ========================================
# 온톨로지 규칙 (L3)
# ========================================

@router.post("/rules", status_code=201)
def create_rule(request: Request, body: OntologyRuleCreate):
    """온톨로지 규칙 등록 — 개념에 바인딩되는 업무 규칙/정의/자격/제외/시간창/정책"""
    try:
        data = _store.create_rule(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/rules")
def list_rules(
    request: Request,
    concept_id: str | None = None,
    rule_type: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """규칙 목록 조회 — concept_id, rule_type 필터"""
    data = _store.list_rules(
        _tenant(request), concept_id=concept_id, rule_type=rule_type,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/rules/{rule_id}")
def get_rule(request: Request, rule_id: str):
    """단건 규칙 조회"""
    data = _store.get_rule(_tenant(request), rule_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"rule_id '{rule_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/rules/{rule_id}")
def update_rule(request: Request, rule_id: str, body: OntologyRuleUpdate):
    """규칙 수정 (PATCH 방식)"""
    try:
        data = _store.update_rule(_tenant(request), rule_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/rules/{rule_id}")
def delete_rule(request: Request, rule_id: str):
    """규칙 삭제"""
    deleted = _store.delete_rule(_tenant(request), rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"rule_id '{rule_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


# ========================================
# 온톨로지 정책 (L3)
# ========================================

@router.post("/policies", status_code=201)
def create_policy(request: Request, body: OntologyPolicyCreate):
    """온톨로지 정책 등록 — 접근/PII/보존/거주지/집계 거버넌스 정책"""
    try:
        data = _store.create_policy(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/policies")
def list_policies(
    request: Request,
    concept_id: str | None = None,
    policy_type: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """정책 목록 조회 — concept_id, policy_type, is_active 필터"""
    data = _store.list_policies(
        _tenant(request), concept_id=concept_id, policy_type=policy_type,
        is_active=is_active, limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.get("/policies/{policy_id}")
def get_policy(request: Request, policy_id: str):
    """단건 정책 조회"""
    data = _store.get_policy(_tenant(request), policy_id)
    if not data:
        raise HTTPException(status_code=404, detail=f"policy_id '{policy_id}'를 찾을 수 없습니다")
    return {"success": True, "data": data}


@router.put("/policies/{policy_id}")
def update_policy(request: Request, policy_id: str, body: OntologyPolicyUpdate):
    """정책 수정 (PATCH 방식)"""
    try:
        data = _store.update_policy(_tenant(request), policy_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.delete("/policies/{policy_id}")
def delete_policy(request: Request, policy_id: str):
    """정책 삭제"""
    deleted = _store.delete_policy(_tenant(request), policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"policy_id '{policy_id}'를 찾을 수 없습니다")
    return {"success": True, "deleted": True}


# ========================================
# Sprint 4: 별칭 그룹 (온톨로지 용어 클러스터링)
# ========================================

@router.post("/ontology/alias-groups", status_code=201)
def create_alias_group(request: Request, body: AliasGroupCreate):
    """별칭 그룹 등록 — 여러 alias를 하나의 정규 용어 클러스터로 묶는다"""
    try:
        data = _store.create_alias_group(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/ontology/alias-groups")
def list_alias_groups(
    request: Request,
    domain_id: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """별칭 그룹 목록 조회 — 도메인/상태 필터 지원"""
    data = _store.list_alias_groups(
        _tenant(request), domain_id=domain_id, status=status,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


# ========================================
# Sprint 4: 확장 규칙 (용어 매칭 규칙)
# ========================================

@router.post("/ontology/expansion-rules", status_code=201)
def create_expansion_rule(request: Request, body: ExpansionRuleCreate):
    """확장 규칙 등록 — exact/regex/time_alias 등 매칭 규칙 정의"""
    try:
        data = _store.create_expansion_rule(_tenant(request), body.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/ontology/expansion-rules")
def list_expansion_rules(
    request: Request,
    alias_group_id: str | None = None,
    rule_type: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """확장 규칙 목록 조회 — 그룹/타입/상태 필터 지원"""
    data = _store.list_expansion_rules(
        _tenant(request), alias_group_id=alias_group_id,
        rule_type=rule_type, status=status,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.patch("/ontology/expansion-rules/{rule_id}")
def update_expansion_rule(request: Request, rule_id: str, body: ExpansionRuleUpdate):
    """확장 규칙 수정 (PATCH) — 허용된 필드만 업데이트"""
    try:
        data = _store.update_expansion_rule(_tenant(request), rule_id, body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/ontology/expansion-rules/{rule_id}/activate")
def activate_expansion_rule(request: Request, rule_id: str):
    """확장 규칙 활성화 — DEPRECATED → ACTIVE 전환"""
    try:
        data = _store.activate_rule(_tenant(request), rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.post("/ontology/expansion-rules/{rule_id}/deprecate")
def deprecate_expansion_rule(request: Request, rule_id: str):
    """확장 규칙 비활성화 — ACTIVE → DEPRECATED 전환"""
    try:
        data = _store.deprecate_rule(_tenant(request), rule_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}


# ========================================
# Sprint 4: 의도 분류 모델 (런타임)
# ========================================

@router.post("/runtime/intent-models", status_code=201)
def create_intent_model(request: Request, body: IntentModelCreate):
    """의도 분류 모델 등록 — 버전별 모델 관리"""
    try:
        data = _store.create_intent_model(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/runtime/intent-models")
def list_intent_models(
    request: Request,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """의도 분류 모델 목록 조회"""
    data = _store.list_intent_models(
        _tenant(request), status=status,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


# ========================================
# Sprint 4: 추론 로그 (런타임)
# ========================================

@router.post("/runtime/inference-logs", status_code=201)
def create_inference_log(request: Request, body: InferenceLogCreate):
    """의도 추론 로그 기록 — Oracle에서 질의 시 자동 기록"""
    try:
        data = _store.create_inference_log(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/runtime/inference-logs")
def list_inference_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """추론 로그 목록 조회 — 최근순"""
    data = _store.list_inference_logs(
        _tenant(request), limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


# ========================================
# Sprint 4: 질문 이해 피드백 (런타임)
# ========================================

@router.post("/runtime/question-feedback", status_code=201)
def create_question_feedback(request: Request, body: QuestionFeedbackCreate):
    """질문 이해 피드백 등록 — 운영자 교정 기록"""
    try:
        data = _store.create_question_feedback(_tenant(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "data": data}


@router.get("/runtime/question-feedback")
def list_question_feedback(
    request: Request,
    resolved: bool | None = None,
    limit: int = Query(50, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """질문 피드백 목록 조회 — 해결 여부 필터 지원"""
    data = _store.list_question_feedback(
        _tenant(request), resolved=resolved,
        limit=_clamp_limit(limit), offset=offset,
    )
    return {"success": True, "data": data, "count": len(data)}


@router.post("/runtime/question-feedback/{feedback_id}/resolve")
def resolve_question_feedback(request: Request, feedback_id: str):
    """피드백 해결 완료 처리"""
    try:
        data = _store.resolve_feedback(_tenant(request), feedback_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "data": data}
