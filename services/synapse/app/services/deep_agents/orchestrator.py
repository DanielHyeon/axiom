"""Deep Agents 오케스트레이터 — 5계층 에이전트를 조율하여 멀티레이어 온톨로지를 생성한다.

병렬/순차 실행 모드를 지원하며, 진행 상황을 콜백으로 전달한다.
순차 모드에서는 이전 레이어 결과를 다음 레이어 컨텍스트로 제공하여
교차 레이어 참조가 가능하다.

사용 예:
    orchestrator = DeepAgentsOrchestrator()
    result = await orchestrator.generate_multi_layer(
        input_text="공장의 OEE를 높이기 위해...",
        domain_hint="제조업",
        target_layers=["kpi", "measure", "process"],
        parallel=True,
        on_progress=lambda data: stream.emit(data),
    )
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

import structlog

from app.services.deep_agents.layer_agents import (
    DEFAULT_LAYER_ORDER,
    LAYER_AGENTS,
    GenerateFn,
    LayerSchema,
)
from app.services.deep_agents.quality_evaluator import QualityResult, evaluate_layer

logger = structlog.get_logger(__name__)


# ─── 결과 데이터 구조 ──────────────────────────────────────────


@dataclass
class MultiLayerResult:
    """멀티레이어 생성 결과 — 모든 레이어의 추출 결과를 담는다."""

    layer_schemas: dict[str, LayerSchema] = field(default_factory=dict)
    quality_scores: dict[str, QualityResult] = field(default_factory=dict)
    cross_layer_relations: list[dict[str, Any]] = field(default_factory=list)
    total_nodes: int = 0
    total_relations: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """API 응답용 딕셔너리로 변환한다."""
        layers = {}
        for layer_name, schema in self.layer_schemas.items():
            quality = self.quality_scores.get(layer_name)
            layers[layer_name] = {
                "nodes": schema.nodes,
                "relationships": schema.relationships,
                "quality": {
                    "confidence": quality.confidence if quality else 0.0,
                    "node_count": quality.node_count if quality else 0,
                    "relation_count": quality.relation_count if quality else 0,
                    "missing_info": quality.missing_info if quality else [],
                } if quality else None,
            }
        return {
            "layers": layers,
            "cross_layer_relations": self.cross_layer_relations,
            "total_nodes": self.total_nodes,
            "total_relations": self.total_relations,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


# ─── 진행 콜백 타입 ────────────────────────────────────────────

ProgressCallback = Callable[[dict[str, Any]], None]


# ─── 교차 레이어 관계 추론 ─────────────────────────────────────


async def _infer_cross_layer_relations(
    layer_schemas: dict[str, LayerSchema],
) -> list[dict[str, Any]]:
    """서로 다른 레이어의 노드 간 관계를 규칙 기반으로 추론한다.

    LLM 호출 없이 레이어 쌍 매핑 규칙을 사용한다.
    (relation_inference.py의 _rule_based_inference 로직과 동일)
    """
    try:
        from app.services.relation_inference import _rule_based_inference
    except ImportError:
        logger.warning("relation_inference_import_failed")
        return []

    results: list[dict[str, Any]] = []

    # 모든 노드를 레이어별로 모은다
    all_nodes: list[dict[str, Any]] = []
    for schema in layer_schemas.values():
        all_nodes.extend(schema.nodes)

    # 서로 다른 레이어에 속한 노드 쌍만 비교한다
    for i, src in enumerate(all_nodes):
        for j, tgt in enumerate(all_nodes):
            if i >= j:
                continue
            src_layer = src.get("layer", "")
            tgt_layer = tgt.get("layer", "")
            # 같은 레이어면 건너뛴다 (레이어 내부 관계는 에이전트가 처리)
            if src_layer == tgt_layer:
                continue

            relation = _rule_based_inference(
                {"name": src.get("name", ""), "layer": src_layer},
                {"name": tgt.get("name", ""), "layer": tgt_layer},
            )
            # 신뢰도 0.5 이상만 포함
            if relation["confidence"] >= 0.5:
                results.append({
                    "source_id": src.get("id", ""),
                    "target_id": tgt.get("id", ""),
                    "type": relation["relation_type"],
                    "confidence": relation["confidence"],
                    "reasoning": relation["reasoning"],
                })

    logger.info(
        "cross_layer_inference_done",
        pairs_checked=len(all_nodes) * (len(all_nodes) - 1) // 2,
        results_count=len(results),
    )
    return results


# ─── 오케스트레이터 ────────────────────────────────────────────


class DeepAgentsOrchestrator:
    """5계층 온톨로지 생성 오케스트레이터.

    에이전트를 순차 또는 병렬로 실행하고,
    교차 레이어 관계를 추론한 뒤 통합 결과를 반환한다.
    """

    def __init__(self, generate_fn: GenerateFn | None = None):
        """
        Args:
            generate_fn: LLM 호출 함수. None이면 에이전트가 빈 결과를 반환한다.
        """
        self._generate_fn = generate_fn

    async def generate_multi_layer(
        self,
        input_text: str,
        domain_hint: str = "",
        target_layers: list[str] | None = None,
        parallel: bool = True,
        on_progress: ProgressCallback | None = None,
    ) -> MultiLayerResult:
        """멀티레이어 온톨로지를 생성한다.

        Args:
            input_text: 분석할 원문 텍스트
            domain_hint: 도메인 힌트 (예: "제조업")
            target_layers: 추출할 레이어 목록. None이면 전체 5계층.
            parallel: True면 에이전트를 동시에, False면 순서대로 실행
            on_progress: 진행 이벤트 콜백 (SSE 스트리밍에 사용)

        Returns:
            MultiLayerResult — 통합 추출 결과
        """
        start_time = time.monotonic()

        # 대상 레이어 결정 — 순서 유지
        if target_layers:
            layers = [l for l in DEFAULT_LAYER_ORDER if l in target_layers]
        else:
            layers = list(DEFAULT_LAYER_ORDER)

        # 존재하지 않는 레이어 걸러내기
        layers = [l for l in layers if l in LAYER_AGENTS]

        if not layers:
            logger.warning("no_valid_layers_requested")
            return MultiLayerResult()

        _emit(on_progress, {
            "type": "start",
            "layers": layers,
            "parallel": parallel,
            "total_layers": len(layers),
        })

        result = MultiLayerResult()

        if parallel:
            await self._run_parallel(input_text, domain_hint, layers, on_progress, result)
        else:
            await self._run_sequential(input_text, domain_hint, layers, on_progress, result)

        # 교차 레이어 관계 추론
        _emit(on_progress, {"type": "cross_layer_start"})
        cross_rels = await _infer_cross_layer_relations(result.layer_schemas)
        result.cross_layer_relations = cross_rels

        # 총계 집계
        result.total_nodes = sum(len(s.nodes) for s in result.layer_schemas.values())
        result.total_relations = (
            sum(len(s.relationships) for s in result.layer_schemas.values())
            + len(cross_rels)
        )
        result.elapsed_seconds = time.monotonic() - start_time

        _emit(on_progress, {
            "type": "complete",
            "total_nodes": result.total_nodes,
            "total_relations": result.total_relations,
            "elapsed_seconds": round(result.elapsed_seconds, 2),
            "quality_scores": {
                name: {"confidence": q.confidence, "node_count": q.node_count}
                for name, q in result.quality_scores.items()
            },
        })

        logger.info(
            "multi_layer_generation_done",
            total_nodes=result.total_nodes,
            total_relations=result.total_relations,
            elapsed=round(result.elapsed_seconds, 2),
        )

        return result

    async def _run_parallel(
        self,
        input_text: str,
        domain_hint: str,
        layers: list[str],
        on_progress: ProgressCallback | None,
        result: MultiLayerResult,
    ) -> None:
        """모든 에이전트를 동시에 실행한다.

        병렬 모드에서는 교차 레이어 컨텍스트를 제공하지 않는다.
        빠르지만 에이전트 간 참조가 불가능하다.
        """

        async def _run_one(layer_name: str) -> tuple[str, LayerSchema]:
            _emit(on_progress, {
                "type": "layer_progress",
                "layer": layer_name,
                "status": "running",
            })
            agent = LAYER_AGENTS[layer_name]
            schema = await agent.extract(
                input_text=input_text,
                domain_hint=domain_hint,
                generate_fn=self._generate_fn,
            )
            quality = evaluate_layer(schema)
            _emit(on_progress, {
                "type": "layer_complete",
                "layer": layer_name,
                "node_count": len(schema.nodes),
                "relation_count": len(schema.relationships),
                "confidence": quality.confidence,
            })
            return layer_name, schema

        # asyncio.gather로 동시 실행
        tasks = [_run_one(l) for l in layers]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        for item in completed:
            if isinstance(item, Exception):
                logger.error("parallel_agent_error", error=str(item))
                continue
            layer_name, schema = item
            result.layer_schemas[layer_name] = schema
            result.quality_scores[layer_name] = evaluate_layer(schema)

    async def _run_sequential(
        self,
        input_text: str,
        domain_hint: str,
        layers: list[str],
        on_progress: ProgressCallback | None,
        result: MultiLayerResult,
    ) -> None:
        """에이전트를 순서대로 실행한다.

        이전 레이어의 노드 이름을 다음 에이전트의 컨텍스트로 제공하여
        교차 참조 정확도를 높인다.
        """
        context: dict[str, Any] = {}

        for idx, layer_name in enumerate(layers):
            _emit(on_progress, {
                "type": "layer_progress",
                "layer": layer_name,
                "status": "running",
                "step": idx + 1,
                "total_steps": len(layers),
            })

            agent = LAYER_AGENTS[layer_name]
            schema = await agent.extract(
                input_text=input_text,
                domain_hint=domain_hint,
                context=context if context else None,
                generate_fn=self._generate_fn,
            )
            quality = evaluate_layer(schema)

            result.layer_schemas[layer_name] = schema
            result.quality_scores[layer_name] = quality

            # 다음 에이전트에 현재 레이어 노드 이름을 컨텍스트로 전달
            context[layer_name] = [n.get("name", "") for n in schema.nodes]

            _emit(on_progress, {
                "type": "layer_complete",
                "layer": layer_name,
                "node_count": len(schema.nodes),
                "relation_count": len(schema.relationships),
                "confidence": quality.confidence,
            })


def _emit(callback: ProgressCallback | None, data: dict[str, Any]) -> None:
    """콜백이 있으면 호출한다. 없으면 무시."""
    if callback is not None:
        try:
            callback(data)
        except Exception as exc:
            logger.warning("progress_callback_error", error=str(exc))
