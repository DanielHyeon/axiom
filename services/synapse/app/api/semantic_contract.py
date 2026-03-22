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
)
from app.services.semantic_store import SemanticStore
from app.services.semantic_compiler import SemanticCompiler

router = APIRouter(
    prefix="/api/v3/synapse/semantic",
    tags=["Semantic Contract"],
)

# 모듈 레벨 싱글턴 (기존 Synapse 패턴)
_store = SemanticStore()
_compiler = SemanticCompiler(_store)

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
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    """개념 목록 조회 — 상태/케이스 필터 지원"""
    data = _store.list_concepts(_tenant(request), case_id=case_id, status=status, limit=_clamp_limit(limit), offset=offset)
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
    """개념 상태 전이 — draft→review→approved→deprecated (규칙 기반)"""
    try:
        data = _store.change_concept_status(_tenant(request), concept_id, body.status)
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
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    data = _store.list_entities(_tenant(request), case_id=case_id, limit=_clamp_limit(limit), offset=offset)
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
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    data = _store.list_measures(_tenant(request), case_id=case_id, entity_id=entity_id, limit=_clamp_limit(limit), offset=offset)
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
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    data = _store.list_dimensions(_tenant(request), case_id=case_id, entity_id=entity_id, limit=_clamp_limit(limit), offset=offset)
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
    limit: int = Query(100, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
    data = _store.list_join_contracts(
        _tenant(request), case_id=case_id, allowed_for_ai=allowed_for_ai,
        limit=_clamp_limit(limit), offset=offset,
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
