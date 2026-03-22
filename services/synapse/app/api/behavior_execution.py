"""BehaviorModel 실행 API 라우터.

KAIR ontology_behavior.py에서 이식한 4개 엔드포인트:
  - POST /behaviors/{behavior_id}/execute — 모델 실행 (4가지 타입)
  - POST /behaviors/generate-code — LLM 코드 생성
  - POST /behaviors/generate-behavior-code — BehaviorModel 정의 기반 코드 자동 생성
  - POST /behaviors/save-result — 실행 결과 PostgreSQL 저장
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import structlog

from app.core.neo4j_client import neo4j_client
from app.services.behavior_executor import BehaviorExecutor
from app.services.code_generator import CodeGenerator
from app.services.result_persister import ResultPersister

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v3/synapse/behaviors", tags=["behaviors"])

# ── 서비스 인스턴스 ──
_executor = BehaviorExecutor()
_persister = ResultPersister()


# ── LLM 생성 함수 팩토리 ──
def _get_llm_generate_fn():
    """LLM generate_text 함수를 지연 임포트로 반환한다.

    Synapse 설정에 OPENAI_API_KEY가 있을 때만 활성화.
    kair_common 미설치 환경에서도 안전하게 None 반환.
    """
    from app.core.config import settings
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from kair_common.llm_factory import generate_text
        return generate_text
    except ImportError:
        logger.debug("kair_common_not_installed", msg="LLM 코드 수정/생성 비활성화")
        return None


def _get_code_generator() -> CodeGenerator:
    """CodeGenerator 인스턴스를 LLM 함수와 함께 생성한다."""
    return CodeGenerator(llm_generate_fn=_get_llm_generate_fn())


# ── 요청 모델 ──

class ExecuteBehaviorRequest(BaseModel):
    """BehaviorModel 실행 요청."""
    model_config = ConfigDict(populate_by_name=True)

    instance_data: dict[str, Any] = Field(default_factory=dict, alias="instanceData")
    options: dict[str, Any] = Field(default_factory=dict)


class GenerateCodeRequest(BaseModel):
    """코드 생성 요청."""
    prompt: str
    language: str = "python"
    temperature: float = Field(default=0.5, ge=0.0, le=1.0)
    max_output_tokens: int = Field(default=4000, ge=100, le=16000)
    context: dict[str, Any] | None = None


class GenerateBehaviorCodeRequest(BaseModel):
    """BehaviorModel 정의 기반 코드 생성 요청."""
    behavior_name: str
    input_fields: list[str] = Field(default_factory=list)
    output_field: str = ""
    description: str = ""
    language: str = "python"


class SaveResultRequest(BaseModel):
    """실행 결과 저장 요청."""
    table_name: str
    schema_name: str = "public"
    data: list[dict[str, Any]]


# ── 엔드포인트 ──

@router.post("/{behavior_id}/execute")
async def execute_behavior(behavior_id: str, body: ExecuteBehaviorRequest):
    """BehaviorModel을 실행한다.

    Neo4j에서 behavior 정의를 조회한 후 타입에 따라 실행:
    - rest_api: 외부 HTTP 엔드포인트 호출 (SSRF 차단 적용)
    - dmn: DMN 결정 테이블 실행
    - python: 샌드박스 코드 실행 (AST 검증 + 타임아웃 + LLM 자동 수정 3회)
    - javascript: 미지원 (501)
    """
    behavior = await _fetch_behavior(behavior_id)

    llm_fn = _get_llm_generate_fn()
    result = await _executor.execute(
        behavior=behavior,
        instance_data=body.instance_data,
        llm_generate_fn=llm_fn,
    )

    if not result.get("success") and result.get("error", "").startswith("지원하지 않는"):
        raise HTTPException(status_code=501, detail=result["error"])

    return result


@router.post("/generate-code")
async def generate_code(body: GenerateCodeRequest):
    """LLM을 사용하여 코드를 생성한다.

    사용자 프롬프트에서 지정된 언어의 코드를 생성한다.
    temperature를 높이면 더 창의적인 결과를 얻을 수 있다.
    """
    gen = _get_code_generator()
    result = await gen.generate(
        prompt=body.prompt,
        language=body.language,
        temperature=body.temperature,
        max_output_tokens=body.max_output_tokens,
        context=body.context,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "코드 생성 실패"))

    return result


@router.post("/generate-behavior-code")
async def generate_behavior_code(body: GenerateBehaviorCodeRequest):
    """BehaviorModel 정의(READS_FIELD/PREDICTS_FIELD)에 맞는 실행 코드를 자동 생성한다.

    BehaviorModel의 입출력 필드 정보로부터 학습/추론 코드를 LLM이 생성한다.
    """
    gen = _get_code_generator()
    result = await gen.generate_behavior_code(
        behavior_name=body.behavior_name,
        input_fields=body.input_fields,
        output_field=body.output_field,
        description=body.description,
        language=body.language,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "코드 생성 실패"))

    return result


@router.post("/save-result")
async def save_result(body: SaveResultRequest):
    """BehaviorModel 실행 결과를 PostgreSQL 테이블에 저장한다.

    테이블이 없으면 첫 번째 행의 키/타입으로 자동 생성한다.
    schema_name으로 대상 스키마를 지정할 수 있다.
    """
    if not body.data:
        raise HTTPException(status_code=400, detail="저장할 데이터가 없습니다.")

    result = await _persister.save(
        table_name=body.table_name,
        data=body.data,
        schema_name=body.schema_name,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "저장 실패"))

    return result


# ── 내부 함수 ──

async def _fetch_behavior(behavior_id: str) -> dict[str, Any]:
    """Neo4j에서 behavior_id로 BehaviorModel을 조회한다.

    behavior_id는 Neo4j 노드의 id 속성을 의미한다.
    조회 실패 시 404/502 HTTPException을 발생시킨다.
    """
    query = """
    MATCH (b:OntologyBehavior)
    WHERE b.id = $bid OR elementId(b) = $bid
    RETURN b.id AS id, b.name AS name,
           b.behaviorType AS behaviorType,
           b.config AS config,
           b.inputFields AS inputFields,
           b.outputField AS outputField,
           b.description AS description
    LIMIT 1
    """
    try:
        async with neo4j_client.session() as session:
            result = await session.run(query, bid=behavior_id)
            record = await result.single()
    except Exception as e:
        logger.error("behavior_fetch_error", behavior_id=behavior_id, error=str(e))
        raise HTTPException(
            status_code=502,
            detail="BehaviorModel 조회 중 인프라 오류가 발생했습니다.",
        ) from e

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Behavior '{behavior_id}'를 찾을 수 없습니다.",
        )

    # config JSON 파싱 — 유효하지 않은 JSON은 422 반환
    try:
        config = json.loads(record.get("config") or "{}")
    except json.JSONDecodeError as e:
        logger.error("behavior_config_invalid_json", behavior_id=behavior_id, error=str(e))
        raise HTTPException(
            status_code=422,
            detail=f"BehaviorModel config JSON이 유효하지 않습니다: {e}",
        ) from e

    try:
        input_fields = json.loads(record.get("inputFields") or "[]")
    except json.JSONDecodeError:
        input_fields = []

    return {
        "id": record.get("id"),
        "name": record.get("name"),
        "behaviorType": record.get("behaviorType", "rest_api"),
        "config": config,
        "inputFields": input_fields,
        "outputField": record.get("outputField", ""),
        "description": record.get("description", ""),
    }
