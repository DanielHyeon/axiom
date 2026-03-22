"""레이어별 온톨로지 추출 에이전트 — 5계층 각각에 특화된 LLM 프롬프트.

각 에이전트는 입력 텍스트에서 해당 레이어에 맞는 노드와 관계를 추출한다.
LLM이 없을 때도 동작하도록 generate_fn 파라미터를 받는다.

계층 구조:
  BaseLayerAgent (추상)
    ├── KPIAgent       — 핵심 성과 지표 추출
    ├── MeasureAgent   — 측정 항목 추출
    ├── DriverAgent    — 변동 요인 추출
    ├── ProcessAgent   — 업무 프로세스 추출
    └── ResourceAgent  — 자원(장비/인력/재료) 추출
"""
from __future__ import annotations

import json
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

import structlog

logger = structlog.get_logger(__name__)


# ─── 결과 데이터 구조 ──────────────────────────────────────────


@dataclass
class LayerSchema:
    """한 레이어에서 추출된 노드와 관계 목록."""

    layer: str  # kpi, measure, driver, process, resource
    nodes: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)


# ─── 프로퍼티 타입 정규화 ──────────────────────────────────────


# LLM이 반환할 수 있는 다양한 타입 표현을 통일된 형태로 바꾼다
_TYPE_MAP = {
    "string": "string",
    "str": "string",
    "text": "string",
    "varchar": "string",
    "number": "number",
    "int": "number",
    "integer": "number",
    "float": "number",
    "double": "number",
    "decimal": "number",
    "numeric": "number",
    "bool": "boolean",
    "boolean": "boolean",
    "date": "date",
    "datetime": "datetime",
    "timestamp": "datetime",
    "percent": "percent",
    "percentage": "percent",
    "%": "percent",
    "currency": "currency",
    "money": "currency",
}


def normalize_property_type(raw_type: str) -> str:
    """LLM이 반환한 프로퍼티 타입을 표준 형식으로 바꾼다.

    예: "VARCHAR" → "string", "INTEGER" → "number", "%" → "percent"
    매핑에 없으면 원본을 소문자로 반환한다.
    """
    key = raw_type.strip().lower()
    return _TYPE_MAP.get(key, key)


# ─── LLM 응답 파서 ─────────────────────────────────────────────


def _parse_llm_json(raw: str) -> dict:
    """LLM 응답에서 JSON 객체를 추출한다.

    마크다운 코드 펜스(```json ... ```)가 있으면 제거하고 파싱한다.
    """
    cleaned = raw.strip()
    # 코드 펜스 제거
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # 첫 줄(```json)과 마지막 줄(```) 제거
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(cleaned)


# ─── 시스템 프롬프트 ───────────────────────────────────────────

# 각 레이어 에이전트가 사용할 공통 JSON 출력 형식 안내
_OUTPUT_FORMAT = """
Respond in JSON only (no markdown fencing):
{
  "nodes": [
    {"id": "unique-id", "name": "Node Name", "description": "설명", "properties": {"unit": "...", "type": "..."}}
  ],
  "relationships": [
    {"source_id": "id1", "target_id": "id2", "type": "RELATION_TYPE", "properties": {}}
  ]
}
"""

_KPI_SYSTEM_PROMPT = f"""You are an expert at identifying Key Performance Indicators (KPIs) from business text.
Extract KPIs like OEE, throughput, defect rate, revenue, cost, etc.
Each KPI node should have: name, unit, target (if mentioned), description.
Relationships between KPIs use DERIVED_FROM or INFLUENCES.
{_OUTPUT_FORMAT}"""

_MEASURE_SYSTEM_PROMPT = f"""You are an expert at identifying measurable metrics from business text.
Extract measures like availability, quality rate, cycle time, MTBF, etc.
Each measure node should have: name, formula (if mentioned), unit, description.
Relationships between measures use DERIVED_FROM.
Relationships from measures to processes use OBSERVED_IN.
{_OUTPUT_FORMAT}"""

_DRIVER_SYSTEM_PROMPT = f"""You are an expert at identifying business drivers and influencing factors from text.
Extract drivers like exchange rate, demand fluctuation, oil price, seasonal effect, etc.
Each driver node should have: name, category (external/internal), description.
Relationships from drivers to KPIs use INFLUENCES or CAUSES.
{_OUTPUT_FORMAT}"""

_PROCESS_SYSTEM_PROMPT = f"""You are an expert at identifying business processes from text.
Extract processes like assembly, inspection, packaging, maintenance, etc.
Each process node should have: name, stage (pre-production/production/quality/logistics/support), description.
Relationships between processes use PRECEDES or SUPPORTS.
{_OUTPUT_FORMAT}"""

_RESOURCE_SYSTEM_PROMPT = f"""You are an expert at identifying resources (equipment, people, materials) from text.
Extract resources like machines, operators, raw materials, sensors, etc.
Each resource node should have: name, type (equipment/human/material/system), description.
Relationships from resources to processes use SUPPORTS.
{_OUTPUT_FORMAT}"""


# ─── generate_fn 타입 정의 ─────────────────────────────────────

# generate_fn(system_prompt, user_prompt) -> str (LLM 원문 응답)
GenerateFn = Callable[[str, str], Coroutine[Any, Any, str]]


# ─── 기본 에이전트 ─────────────────────────────────────────────


class BaseLayerAgent(ABC):
    """레이어 에이전트 기본 클래스 — 공통 추출 로직 제공.

    하위 클래스는 layer_type 과 system_prompt 를 정의하면 된다.
    """

    @property
    @abstractmethod
    def layer_type(self) -> str:
        """이 에이전트가 담당하는 레이어 이름 (예: "kpi")."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """LLM에 보낼 시스템 프롬프트."""
        ...

    async def extract(
        self,
        input_text: str,
        domain_hint: str = "",
        context: dict[str, Any] | None = None,
        generate_fn: GenerateFn | None = None,
    ) -> LayerSchema:
        """입력 텍스트에서 이 레이어의 노드와 관계를 추출한다.

        Args:
            input_text: 분석할 원문 텍스트
            domain_hint: 도메인 힌트 (예: "제조업", "금융")
            context: 다른 레이어 결과 등 추가 맥락
            generate_fn: LLM 호출 함수. None이면 빈 결과 반환.

        Returns:
            LayerSchema — 추출된 노드와 관계
        """
        if generate_fn is None:
            # LLM 없으면 빈 스키마 반환 (테스트에서 활용)
            logger.warning("no_generate_fn", layer=self.layer_type)
            return LayerSchema(layer=self.layer_type)

        # 사용자 프롬프트 구성
        user_prompt = f"Domain: {domain_hint}\n\n" if domain_hint else ""
        if context:
            # 다른 레이어에서 이미 추출한 노드 이름을 알려주어 참조하게 한다
            user_prompt += f"Context from other layers: {json.dumps(context, ensure_ascii=False, default=str)}\n\n"
        user_prompt += f"Text to analyze:\n{input_text}"

        try:
            raw_response = await generate_fn(self.system_prompt, user_prompt)
            parsed = _parse_llm_json(raw_response)
        except (json.JSONDecodeError, Exception) as exc:
            logger.error(
                "layer_agent_parse_error",
                layer=self.layer_type,
                error=str(exc),
            )
            return LayerSchema(layer=self.layer_type)

        # 노드에 레이어 정보와 고유 ID 보장
        nodes = parsed.get("nodes", [])
        for node in nodes:
            node.setdefault("id", f"{self.layer_type}-{uuid.uuid4().hex[:8]}")
            node["layer"] = self.layer_type
            # 프로퍼티 타입 정규화
            props = node.get("properties", {})
            if "type" in props:
                props["type"] = normalize_property_type(str(props["type"]))

        relationships = parsed.get("relationships", [])

        logger.info(
            "layer_extraction_done",
            layer=self.layer_type,
            node_count=len(nodes),
            rel_count=len(relationships),
        )

        return LayerSchema(
            layer=self.layer_type,
            nodes=nodes,
            relationships=relationships,
        )


# ─── 구체 에이전트 5개 ─────────────────────────────────────────


class KPIAgent(BaseLayerAgent):
    """KPI 레이어 에이전트 — 핵심 성과 지표를 추출한다."""

    @property
    def layer_type(self) -> str:
        return "kpi"

    @property
    def system_prompt(self) -> str:
        return _KPI_SYSTEM_PROMPT


class MeasureAgent(BaseLayerAgent):
    """Measure 레이어 에이전트 — 측정 항목을 추출한다."""

    @property
    def layer_type(self) -> str:
        return "measure"

    @property
    def system_prompt(self) -> str:
        return _MEASURE_SYSTEM_PROMPT


class DriverAgent(BaseLayerAgent):
    """Driver 레이어 에이전트 — 변동 요인(원인)을 추출한다."""

    @property
    def layer_type(self) -> str:
        return "driver"

    @property
    def system_prompt(self) -> str:
        return _DRIVER_SYSTEM_PROMPT


class ProcessAgent(BaseLayerAgent):
    """Process 레이어 에이전트 — 업무 프로세스를 추출한다."""

    @property
    def layer_type(self) -> str:
        return "process"

    @property
    def system_prompt(self) -> str:
        return _PROCESS_SYSTEM_PROMPT


class ResourceAgent(BaseLayerAgent):
    """Resource 레이어 에이전트 — 자원(장비/인력/재료)을 추출한다."""

    @property
    def layer_type(self) -> str:
        return "resource"

    @property
    def system_prompt(self) -> str:
        return _RESOURCE_SYSTEM_PROMPT


# ─── 에이전트 레지스트리 ───────────────────────────────────────

# 레이어 이름으로 에이전트 인스턴스를 가져올 수 있는 딕셔너리
LAYER_AGENTS: dict[str, BaseLayerAgent] = {
    "kpi": KPIAgent(),
    "measure": MeasureAgent(),
    "driver": DriverAgent(),
    "process": ProcessAgent(),
    "resource": ResourceAgent(),
}

# 기본 실행 순서 — 상위 레이어부터 추출하면 하위 에이전트에 맥락 제공 가능
DEFAULT_LAYER_ORDER = ["kpi", "driver", "measure", "process", "resource"]
