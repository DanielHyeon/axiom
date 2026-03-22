"""멀티레이어 온톨로지 생성 API — SSE 스트리밍 + 동기 엔드포인트.

Deep Agents 오케스트레이터를 통해 5계층 온톨로지를 자동 생성한다.
SSE 버전은 진행 상황을 실시간으로 전달하고,
동기 버전은 결과를 한 번에 반환한다.

라우트:
  POST /api/v3/synapse/ontology/generate-multi-layer       — SSE (NDJSON)
  POST /api/v3/synapse/ontology/generate-multi-layer/sync  — 동기 JSON
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.sse_stream import SSEStream
from app.services.deep_agents.layer_agents import DEFAULT_LAYER_ORDER, GenerateFn
from app.services.deep_agents.orchestrator import DeepAgentsOrchestrator

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/v3/synapse/ontology",
    tags=["deep-agents"],
)


# ─── 요청/응답 모델 ───────────────────────────────────────────


class MultiLayerRequest(BaseModel):
    """멀티레이어 생성 요청 스키마."""

    # 분석할 텍스트 (필수)
    input_text: str = Field(
        ...,
        min_length=10,
        max_length=50_000,
        description="온톨로지를 추출할 원문 텍스트",
    )
    # 도메인 힌트 (선택) — 예: "제조업", "금융", "물류"
    domain_hint: str = Field(
        default="",
        max_length=200,
        description="도메인 힌트",
    )
    # 추출할 레이어 목록 (선택) — 비어 있으면 전체 5계층
    target_layers: list[str] = Field(
        default_factory=list,
        description="추출할 레이어 목록 (예: ['kpi', 'measure']). 비어 있으면 전체.",
    )
    # 병렬 실행 여부
    parallel: bool = Field(
        default=True,
        description="True면 에이전트를 병렬 실행 (빠름), False면 순차 실행 (더 정확)",
    )


class MultiLayerResponse(BaseModel):
    """동기 엔드포인트의 응답 스키마."""

    layers: dict[str, Any]
    cross_layer_relations: list[dict[str, Any]]
    total_nodes: int
    total_relations: int
    elapsed_seconds: float


# ─── LLM generate_fn 팩토리 ───────────────────────────────────


def _create_openai_generate_fn() -> GenerateFn | None:
    """OpenAI API 키가 설정되어 있으면 LLM 호출 함수를 반환한다.

    키가 없거나 openai 패키지가 없으면 None을 반환한다.
    """
    if not settings.OPENAI_API_KEY:
        logger.info("openai_key_not_set_using_empty_results")
        return None

    try:
        from openai import AsyncOpenAI  # noqa: WPS433
    except ImportError:
        logger.warning("openai_package_not_installed")
        return None

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def _generate(system_prompt: str, user_prompt: str) -> str:
        """OpenAI ChatCompletion 호출 — JSON 응답을 원문 문자열로 반환."""
        response = await client.chat.completions.create(
            model=settings.EXTRACTION_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2000,
            temperature=0.2,
        )
        return response.choices[0].message.content or "{}"

    return _generate


# ─── SSE 스트리밍 엔드포인트 ───────────────────────────────────


@router.post(
    "/generate-multi-layer",
    summary="멀티레이어 온톨로지 생성 (SSE 스트리밍)",
    description="5계층 온톨로지를 생성하면서 진행 상황을 NDJSON 스트리밍으로 전달한다.",
    response_class=StreamingResponse,
)
async def generate_multi_layer_sse(req: MultiLayerRequest):
    """SSE 스트리밍 멀티레이어 생성.

    이벤트 타입:
      - start: 생성 시작 (레이어 목록 포함)
      - layer_progress: 레이어 추출 진행 중
      - layer_complete: 레이어 추출 완료 (노드 수, 신뢰도)
      - cross_layer_start: 교차 레이어 관계 추론 시작
      - complete: 전체 완료 (총계, 소요 시간)
      - error: 에러 발생
    """
    # 입력 검증 — 대상 레이어가 유효한지 확인
    if req.target_layers:
        invalid = [l for l in req.target_layers if l not in DEFAULT_LAYER_ORDER]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"유효하지 않은 레이어: {invalid}. "
                       f"허용 값: {DEFAULT_LAYER_ORDER}",
            )

    stream = SSEStream()
    generate_fn = _create_openai_generate_fn()

    async def _run_generation():
        """백그라운드에서 생성을 실행하고 결과를 스트림에 전달한다."""
        try:
            orchestrator = DeepAgentsOrchestrator(generate_fn=generate_fn)
            result = await orchestrator.generate_multi_layer(
                input_text=req.input_text,
                domain_hint=req.domain_hint,
                target_layers=req.target_layers or None,
                parallel=req.parallel,
                on_progress=stream.emit,
            )
            # 최종 결과를 별도 이벤트로 전송
            stream.emit({
                "type": "result",
                "data": result.to_dict(),
            })
        except Exception as exc:
            logger.error("multi_layer_generation_error", error=str(exc))
            stream.emit({
                "type": "error",
                "message": str(exc),
            })
        finally:
            # 스트림 종료 — 클라이언트 연결이 닫힌다
            stream.complete()

    # 백그라운드 태스크로 생성 시작
    asyncio.create_task(_run_generation())

    return StreamingResponse(
        stream,
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
        },
    )


# ─── 동기 엔드포인트 ──────────────────────────────────────────


@router.post(
    "/generate-multi-layer/sync",
    summary="멀티레이어 온톨로지 생성 (동기)",
    description="5계층 온톨로지를 생성하고 결과를 한 번에 JSON으로 반환한다.",
    response_model=MultiLayerResponse,
)
async def generate_multi_layer_sync(req: MultiLayerRequest):
    """동기 멀티레이어 생성 — 결과를 기다렸다가 한 번에 반환한다."""
    # 입력 검증
    if req.target_layers:
        invalid = [l for l in req.target_layers if l not in DEFAULT_LAYER_ORDER]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"유효하지 않은 레이어: {invalid}. "
                       f"허용 값: {DEFAULT_LAYER_ORDER}",
            )

    generate_fn = _create_openai_generate_fn()
    orchestrator = DeepAgentsOrchestrator(generate_fn=generate_fn)

    try:
        result = await orchestrator.generate_multi_layer(
            input_text=req.input_text,
            domain_hint=req.domain_hint,
            target_layers=req.target_layers or None,
            parallel=req.parallel,
        )
    except Exception as exc:
        logger.error("sync_generation_error", error=str(exc))
        raise HTTPException(status_code=500, detail=f"생성 실패: {exc}")

    return result.to_dict()
