"""관계 추론 엔진 — LLM 기반 엔티티 간 관계 발견.

KAIR의 relation_inference.py를 참조하여 Axiom 패턴으로 이식.
온톨로지 엔티티 간의 의미적 관계를 LLM으로 추론하고 신뢰도를 평가한다.

지원 기능:
  - 엔티티 쌍 간 관계 추론 (DERIVED_FROM, INFLUENCES, CAUSES 등)
  - Cross-layer 관계 발견 (KPI → Measure → Driver)
  - 신뢰도 점수 기반 필터링
  - LLM 미사용 시 레이어 규칙 기반 폴백
"""
from __future__ import annotations

import json
import re

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


# ─── 관계 타입 ─────────────────────────────────────────────

VALID_RELATION_TYPES = {
    "DERIVED_FROM", "OBSERVED_IN", "PRECEDES", "SUPPORTS",
    "USES", "CAUSES", "INFLUENCES", "RELATED_TO",
}

# LLM 시스템 프롬프트 — 관계 추론 전문가 역할
INFERENCE_SYSTEM_PROMPT = """You are an expert ontology engineer analyzing relationships between business entities.

Given two entities from a 5-layer ontology (KPI, Driver, Measure, Process, Resource),
determine their relationship type and confidence.

Valid relationship types:
- DERIVED_FROM: Target is mathematically derived from source
- OBSERVED_IN: Metric is measured/observed in a process
- PRECEDES: Source process happens before target process
- SUPPORTS: Source supports target operation
- USES: Process uses a resource
- CAUSES: Source directly causes change in target
- INFLUENCES: Source indirectly influences target
- RELATED_TO: General association (lowest specificity)

Respond in JSON format only (no markdown fencing):
{
  "relation_type": "CAUSES",
  "confidence": 0.85,
  "reasoning": "Explanation of why this relation exists",
  "direction": "source_to_target"
}
"""


def _sanitize_for_prompt(text: str, max_len: int = 200) -> str:
    """프롬프트 인젝션 방지를 위해 사용자 입력을 정제한다.

    - 최대 길이 제한
    - 잠재적 인젝션 마커(시스템 프롬프트 덮어쓰기 시도) 제거
    """
    if not isinstance(text, str):
        return ""
    # 길이 제한
    text = text[:max_len]
    # 인젝션 패턴 제거: 시스템/어시스턴트 역할 주입 시도, 구분자 등
    injection_patterns = [
        r"(?i)\b(system|assistant|user)\s*:",
        r"```",
        r"<\|.*?\|>",
        r"\{%.*?%\}",
        r"<<.*?>>",
    ]
    for pattern in injection_patterns:
        text = re.sub(pattern, "", text)
    return text.strip()


async def infer_relation(
    source_entity: dict,
    target_entity: dict,
) -> dict:
    """두 엔티티 간의 관계를 LLM으로 추론한다.

    Args:
        source_entity: {"name": str, "layer": str, "description": str}
        target_entity: {"name": str, "layer": str, "description": str}

    Returns:
        {"relation_type": str, "confidence": float, "reasoning": str, "direction": str}
    """
    # LLM API 키가 없으면 규칙 기반 폴백
    if not settings.OPENAI_API_KEY:
        return _rule_based_inference(source_entity, target_entity)

    try:
        # openai 패키지가 없을 수 있으므로 조건부 임포트
        from openai import AsyncOpenAI  # noqa: WPS433
    except ImportError:
        logger.warning("openai_package_not_installed", fallback="rule_based")
        return _rule_based_inference(source_entity, target_entity)

    try:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # 사용자 입력 정제 — 프롬프트 인젝션 방지
        src_name = _sanitize_for_prompt(source_entity.get("name", ""))
        src_layer = _sanitize_for_prompt(source_entity.get("layer", ""), max_len=50)
        src_desc = _sanitize_for_prompt(source_entity.get("description", ""))
        tgt_name = _sanitize_for_prompt(target_entity.get("name", ""))
        tgt_layer = _sanitize_for_prompt(target_entity.get("layer", ""), max_len=50)
        tgt_desc = _sanitize_for_prompt(target_entity.get("description", ""))

        user_prompt = (
            f"Source entity: {src_name} "
            f"(layer: {src_layer}, "
            f"description: {src_desc})\n"
            f"Target entity: {tgt_name} "
            f"(layer: {tgt_layer}, "
            f"description: {tgt_desc})\n"
            f"What is the relationship between these entities?"
        )

        response = await client.chat.completions.create(
            model=settings.EXTRACTION_LLM_MODEL,
            messages=[
                {"role": "system", "content": INFERENCE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or ""

        # JSON 파싱 — 마크다운 코드펜스 제거
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # ```json ... ``` 형태 처리
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        result = json.loads(cleaned)

        relation_type = result.get("relation_type", "RELATED_TO")
        if relation_type not in VALID_RELATION_TYPES:
            relation_type = "RELATED_TO"

        return {
            "relation_type": relation_type,
            "confidence": min(1.0, max(0.0, float(result.get("confidence", 0.5)))),
            "reasoning": result.get("reasoning", ""),
            "direction": result.get("direction", "source_to_target"),
        }

    except Exception as e:
        logger.warning("llm_relation_inference_failed", error=str(e))
        return _rule_based_inference(source_entity, target_entity)


def _rule_based_inference(
    source: dict,
    target: dict,
) -> dict:
    """LLM 미사용 시 레이어 기반 규칙으로 관계를 추론한다.

    온톨로지 5계층 간의 자연스러운 관계를 레이어 쌍으로 매핑한다.
    """
    src_layer = source.get("layer", "").lower()
    tgt_layer = target.get("layer", "").lower()

    # 레이어 쌍 기반 기본 관계 매핑
    layer_relations: dict[tuple[str, str], str] = {
        ("kpi", "measure"): "DERIVED_FROM",
        ("kpi", "driver"): "DERIVED_FROM",
        ("measure", "process"): "OBSERVED_IN",
        ("process", "process"): "PRECEDES",
        ("process", "resource"): "USES",
        ("resource", "process"): "SUPPORTS",
        ("driver", "kpi"): "INFLUENCES",
        ("driver", "measure"): "CAUSES",
        ("measure", "resource"): "OBSERVED_IN",
        ("kpi", "process"): "OBSERVED_IN",
    }

    relation = layer_relations.get((src_layer, tgt_layer), "RELATED_TO")
    # 매핑된 관계는 0.7, 폴백은 0.3으로 신뢰도 차등 부여
    confidence = 0.7 if relation != "RELATED_TO" else 0.3

    return {
        "relation_type": relation,
        "confidence": confidence,
        "reasoning": f"레이어 규칙 기반 추론: {src_layer} → {tgt_layer}",
        "direction": "source_to_target",
    }


async def infer_relations_batch(
    entities: list[dict],
    min_confidence: float = 0.5,
) -> list[dict]:
    """엔티티 목록 간의 모든 가능한 관계를 추론한다.

    O(n^2) 쌍별 비교를 수행한다. 대규모 목록에서는 min_confidence로 필터링하여
    노이즈를 줄인다.

    Args:
        entities: 엔티티 딕셔너리 리스트
        min_confidence: 최소 신뢰도 (이 값 미만의 관계는 결과에서 제외)

    Returns:
        추론된 관계 리스트
    """
    results: list[dict] = []

    for i, src in enumerate(entities):
        for j, tgt in enumerate(entities):
            if i >= j:
                # 자기 자신 + 이미 검사한 쌍 건너뛰기
                continue

            relation = await infer_relation(src, tgt)
            if relation["confidence"] >= min_confidence:
                results.append({
                    "source": src,
                    "target": tgt,
                    **relation,
                })

    logger.info(
        "batch_inference_complete",
        pairs_checked=len(entities) * (len(entities) - 1) // 2,
        results_count=len(results),
    )
    return results
