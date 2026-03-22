"""온톨로지 스키마 피드백 & 반복 개선 서비스.

KAIR schema_generator.py의 feedback 처리 로직을 Axiom 패턴으로 이식.
사용자 피드백을 받아 LLM으로 온톨로지 스키마를 재생성/수정한다.

피드백 타입:
  - add_node: 새 노드 추가
  - update_node: 노드 속성 수정 (이름, 설명, 레이어)
  - delete_node: 노드 삭제
  - add_relation: 관계 추가
  - delete_relation: 관계 삭제
  - move_layer: 노드를 다른 레이어로 이동
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FeedbackItem:
    """피드백 항목 — 사용자가 제출한 개별 수정 요청."""
    type: str  # add_node, update_node, delete_node, add_relation, delete_relation, move_layer
    target_id: str = ""  # 수정 대상 노드/관계 ID
    content: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackResult:
    """피드백 처리 결과."""
    applied: list[dict[str, Any]] = field(default_factory=list)  # 적용된 변경사항
    rejected: list[dict[str, Any]] = field(default_factory=list)  # 거부된 변경사항
    new_version: str = ""  # 새 스키마 버전 ID


class SchemaRefiner:
    """온톨로지 스키마를 피드백 기반으로 반복 개선한다.

    OntologyService와 협력하여 Neo4j에 변경사항을 반영한다.
    LLM이 사용 가능하면 자연어 피드백도 처리한다.
    """

    def __init__(self, ontology_service=None, llm_generate_fn=None):
        self._ontology = ontology_service
        self._llm_fn = llm_generate_fn

    async def apply_feedback(
        self,
        case_id: str,
        tenant_id: str,
        feedback_items: list[dict[str, Any]],
    ) -> FeedbackResult:
        """피드백 항목 목록을 순서대로 적용한다.

        각 항목은 type에 따라 다른 처리 로직을 수행:
        - add_node: OntologyService.create_node 호출
        - update_node: OntologyService.update_node 호출
        - delete_node: OntologyService.delete_node 호출
        - add_relation: OntologyService.create_relation 호출
        - delete_relation: OntologyService.delete_relation 호출
        - move_layer: 노드의 layer 속성 변경

        Args:
            case_id: 대상 케이스 ID
            tenant_id: 테넌트 ID
            feedback_items: 피드백 항목 리스트

        Returns:
            FeedbackResult — 적용/거부 내역 + 새 버전 ID
        """
        result = FeedbackResult(new_version=str(uuid.uuid4()))
        applied: list[dict] = []
        rejected: list[dict] = []

        for item_dict in feedback_items:
            item = FeedbackItem(
                type=item_dict.get("type", ""),
                target_id=item_dict.get("target_id", ""),
                content=item_dict.get("content", {}),
            )

            try:
                change = await self._apply_single_feedback(case_id, tenant_id, item)
                applied.append(change)
            except Exception as e:
                logger.warning(
                    "feedback_item_rejected",
                    type=item.type,
                    target=item.target_id,
                    error=str(e),
                )
                rejected.append({
                    "type": item.type,
                    "target_id": item.target_id,
                    "error": str(e),
                })

        result.applied = applied
        result.rejected = rejected

        logger.info(
            "feedback_applied",
            case_id=case_id,
            applied_count=len(applied),
            rejected_count=len(rejected),
            version=result.new_version,
        )

        return result

    async def _apply_single_feedback(
        self, case_id: str, tenant_id: str, item: FeedbackItem
    ) -> dict[str, Any]:
        """단일 피드백 항목을 적용한다."""
        if not self._ontology:
            raise RuntimeError("OntologyService가 연결되지 않았습니다.")

        if item.type == "add_node":
            # 노드 추가
            payload = {
                "case_id": case_id,
                "id": item.content.get("id", str(uuid.uuid4())),
                "layer": item.content.get("layer", "resource"),
                "label": item.content.get("label", "Resource"),
                "properties": item.content.get("properties", {}),
            }
            await self._ontology.create_node(tenant_id, payload)
            return {"type": "add_node", "node_id": payload["id"], "status": "applied"}

        elif item.type == "update_node":
            # 노드 속성 수정
            payload = {
                "properties": item.content.get("properties", {}),
            }
            if "layer" in item.content:
                payload["layer"] = item.content["layer"]
            await self._ontology.update_node(tenant_id, item.target_id, payload)
            return {"type": "update_node", "node_id": item.target_id, "status": "applied"}

        elif item.type == "delete_node":
            # 노드 삭제
            await self._ontology.delete_node(item.target_id, tenant_id)
            return {"type": "delete_node", "node_id": item.target_id, "status": "applied"}

        elif item.type == "add_relation":
            # 관계 추가
            payload = {
                "case_id": case_id,
                "source_id": item.content.get("source_id", ""),
                "target_id": item.content.get("target_id", ""),
                "type": item.content.get("relation_type", "RELATED_TO"),
            }
            if not payload["source_id"] or not payload["target_id"]:
                raise ValueError("source_id와 target_id가 필요합니다.")
            await self._ontology.create_relation(tenant_id, payload)
            return {"type": "add_relation", "status": "applied", **payload}

        elif item.type == "delete_relation":
            # 관계 삭제
            await self._ontology.delete_relation(item.target_id, tenant_id)
            return {"type": "delete_relation", "relation_id": item.target_id, "status": "applied"}

        elif item.type == "move_layer":
            # 레이어 이동
            new_layer = item.content.get("layer", "")
            if not new_layer:
                raise ValueError("이동할 layer가 지정되지 않았습니다.")
            await self._ontology.update_node(tenant_id, item.target_id, {"layer": new_layer})
            return {"type": "move_layer", "node_id": item.target_id, "new_layer": new_layer, "status": "applied"}

        else:
            raise ValueError(f"알 수 없는 피드백 타입: {item.type}")

    async def refine_with_llm(
        self,
        case_id: str,
        tenant_id: str,
        natural_feedback: str,
    ) -> FeedbackResult:
        """자연어 피드백을 LLM으로 해석하여 스키마를 수정한다.

        사용자가 자유 형식으로 피드백을 제출하면 LLM이
        구조화된 피드백 항목으로 변환하여 apply_feedback으로 처리한다.

        Args:
            case_id: 대상 케이스 ID
            tenant_id: 테넌트 ID
            natural_feedback: 자연어 피드백 텍스트

        Returns:
            FeedbackResult
        """
        if not self._llm_fn:
            return FeedbackResult(
                rejected=[{"error": "LLM이 사용 불가하여 자연어 피드백을 처리할 수 없습니다."}]
            )

        # 현재 온톨로지 요약 조회
        current = await self._ontology.get_case_ontology(case_id, limit=50)
        node_names = [
            n.get("properties", {}).get("name", n.get("id", ""))
            for n in current.get("nodes", [])
        ]

        prompt = f"""다음 온톨로지에 대한 사용자 피드백을 구조화된 변경사항으로 변환하세요.

## 현재 노드 목록
{', '.join(node_names[:20])}

## 사용자 피드백
{natural_feedback}

## 출력 형식 (JSON 배열)
[
  {{"type": "add_node", "content": {{"id": "new-id", "layer": "kpi", "properties": {{"name": "이름"}}}} }},
  {{"type": "update_node", "target_id": "existing-id", "content": {{"properties": {{"name": "수정된 이름"}}}} }},
  {{"type": "delete_node", "target_id": "node-to-delete"}},
  {{"type": "add_relation", "content": {{"source_id": "src", "target_id": "tgt", "relation_type": "DERIVED_FROM"}}}}
]
"""
        try:
            import json
            raw = await self._llm_fn(
                system_prompt="당신은 온톨로지 전문가입니다. 사용자 피드백을 JSON 변경사항 목록으로 변환하세요.",
                user_prompt=prompt,
                purpose="schema_refine",
                temperature=0.2,
                max_output_tokens=2000,
                use_light=True,
            )

            # JSON 배열 추출
            raw = raw.strip()
            if "[" in raw:
                json_str = raw[raw.index("["):raw.rindex("]") + 1]
                items = json.loads(json_str)
            else:
                return FeedbackResult(
                    rejected=[{"error": "LLM이 유효한 JSON을 반환하지 않았습니다."}]
                )

            return await self.apply_feedback(case_id, tenant_id, items)

        except Exception as e:
            logger.error("llm_refine_failed", error=str(e))
            return FeedbackResult(
                rejected=[{"error": f"LLM 처리 오류: {e}"}]
            )
