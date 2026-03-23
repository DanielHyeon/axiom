"""G07: AI 온톨로지 자동 생성 API.

DDL 텍스트, 문서 텍스트, 또는 Weaver 메타데이터에서
온톨로지 5계층 노드·관계를 자동 추출하여 프리뷰를 반환한다.

사용자가 프리뷰를 확인·수정한 후 '확정' 시 Neo4j에 저장한다.
"""

from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v3/synapse/ontology/generate", tags=["온톨로지 생성"])

logger = logging.getLogger("axiom.synapse.ontology_generation")


# ── 요청/응답 모델 ── #

class OntologyGenerationRequest(BaseModel):
    """온톨로지 자동 생성 요청"""
    source_type: Literal["ddl", "document", "metadata"] = "ddl"
    ddl_text: str = Field(default="", max_length=500_000)       # C-3: 500KB 제한
    document_text: str = Field(default="", max_length=500_000)  # C-3: 500KB 제한
    metadata_json: dict | None = None     # Weaver StandardMetadata JSON
    target_layers: list[str] = Field(
        default_factory=lambda: ["kpi", "measure", "process", "resource"],
    )
    language: str = "ko"                  # 생성 언어 (ko/en)
    max_nodes: int = Field(default=50, ge=1, le=200)


class GeneratedNode(BaseModel):
    """생성된 온톨로지 노드 프리뷰"""
    temp_id: str                          # 임시 ID (확정 전)
    name: str
    layer: str                            # kpi, driver, measure, process, resource
    description: str = ""
    properties: dict = Field(default_factory=dict)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    source_hint: str = ""                 # 생성 근거 (DDL 테이블명, 문서 구절 등)


class GeneratedRelation(BaseModel):
    """생성된 온톨로지 관계 프리뷰"""
    source_temp_id: str
    target_temp_id: str
    relation_type: str                    # DERIVED_FROM, OBSERVED_IN, USES 등
    weight: float = 0.5
    confidence: float = 0.6


class GeneratedOntologyPreview(BaseModel):
    """온톨로지 생성 프리뷰 — 사용자 확인 후 확정"""
    nodes: list[GeneratedNode] = Field(default_factory=list)
    relations: list[GeneratedRelation] = Field(default_factory=list)
    source_type: str = ""
    generation_method: str = ""           # "rule_based", "llm", "hybrid"
    warnings: list[str] = Field(default_factory=list)


class ConfirmGenerationRequest(BaseModel):
    """생성 결과 확정 요청 — 수정된 노드/관계 포함"""
    case_id: str
    # C-2: tenant_id는 request.state에서 추출 — 클라이언트 제공 불가
    nodes: list[GeneratedNode]
    relations: list[GeneratedRelation]


# ── 규칙 기반 추출기 (MVP — LLM 호출 없이 패턴 매칭) ── #

# DDL 테이블명 → 온톨로지 계층 매핑 힌트
_LAYER_HINTS: dict[str, list[str]] = {
    "kpi": ["kpi", "metric", "indicator", "score", "rate", "ratio", "index"],
    "driver": ["driver", "factor", "cause", "variable", "influence"],  # N-4: driver 계층 추가
    "measure": ["measure", "stat", "count", "amount", "quantity", "total", "avg", "sum"],
    "process": ["process", "workflow", "step", "stage", "task", "activity", "operation", "batch"],
    "resource": ["machine", "equipment", "operator", "material", "sensor", "device", "worker", "tool"],
}

# 관계 추론 규칙 (테이블명 패턴)
_RELATION_RULES: list[tuple[str, str, str]] = [
    # (source_pattern, target_pattern, relation_type)
    ("kpi", "measure", "DERIVED_FROM"),
    ("measure", "process", "OBSERVED_IN"),
    ("process", "resource", "USES"),
    ("kpi", "driver", "DERIVED_FROM"),
]


def _infer_layer(table_name: str) -> str:
    """테이블명에서 온톨로지 계층 추론"""
    name_lower = table_name.lower()
    for layer, keywords in _LAYER_HINTS.items():
        for kw in keywords:
            if kw in name_lower:
                return layer
    # 기본: process 계층 (가장 일반적)
    return "process"


def _generate_from_ddl(ddl_text: str, max_nodes: int) -> GeneratedOntologyPreview:
    """DDL 텍스트에서 규칙 기반 온톨로지 노드 생성"""
    # CREATE TABLE 추출
    table_pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:"?\w+"?\.)?("?\w+"?)\s*\(',
        re.IGNORECASE,
    )

    nodes: list[GeneratedNode] = []
    seen_names: set[str] = set()

    for match in table_pattern.finditer(ddl_text):
        table_name = match.group(1).strip('"')
        if table_name.lower() in seen_names:
            continue
        seen_names.add(table_name.lower())

        layer = _infer_layer(table_name)
        # 사람이 읽기 좋은 이름 생성 (언더스코어 → 공백, 첫 글자 대문자)
        display_name = table_name.replace("_", " ").title()

        nodes.append(GeneratedNode(
            temp_id=uuid.uuid4().hex[:12],  # M-3: MD5 대신 uuid4
            name=display_name,
            layer=layer,
            description=f"DDL에서 추출: {table_name} 테이블",
            properties={"source_table": table_name},
            confidence=0.75,
            source_hint=f"CREATE TABLE {table_name}",
        ))

        if len(nodes) >= max_nodes:
            break

    # 관계 생성 (같은 계층 또는 인접 계층 간)
    relations = _infer_relations(nodes)

    return GeneratedOntologyPreview(
        nodes=nodes,
        relations=relations,
        source_type="ddl",
        generation_method="rule_based",
    )


def _generate_from_metadata(metadata: dict, max_nodes: int) -> GeneratedOntologyPreview:
    """Weaver StandardMetadata에서 규칙 기반 온톨로지 노드 생성"""
    nodes: list[GeneratedNode] = []
    schemas = metadata.get("schemas", [])

    for schema in schemas:
        for table in schema.get("tables", []):
            table_name = table.get("name", "")
            layer = _infer_layer(table_name)
            display_name = table_name.replace("_", " ").title()

            nodes.append(GeneratedNode(
                temp_id=uuid.uuid4().hex[:12],  # M-3: MD5 대신 uuid4
                name=display_name,
                layer=layer,
                description=f"메타데이터에서 추출: {table_name} ({len(table.get('columns', []))} 컬럼)",
                properties={"source_table": table_name, "column_count": len(table.get("columns", []))},
                confidence=0.8,
                source_hint=f"schema={schema.get('schema_name', '')}",
            ))

            if len(nodes) >= max_nodes:
                break
        if len(nodes) >= max_nodes:
            break

    relations = _infer_relations(nodes)
    return GeneratedOntologyPreview(
        nodes=nodes,
        relations=relations,
        source_type="metadata",
        generation_method="rule_based",
    )


def _infer_relations(nodes: list[GeneratedNode]) -> list[GeneratedRelation]:
    """노드 간 관계 추론 — 계층 인접성 기반"""
    relations: list[GeneratedRelation] = []
    layer_order = ["kpi", "driver", "measure", "process", "resource"]

    # 같은 계층 또는 인접 계층 간 관계 후보
    for i, n1 in enumerate(nodes):
        for n2 in nodes[i + 1:]:
            idx1 = layer_order.index(n1.layer) if n1.layer in layer_order else -1
            idx2 = layer_order.index(n2.layer) if n2.layer in layer_order else -1

            if idx1 < 0 or idx2 < 0:
                continue

            diff = abs(idx1 - idx2)
            if diff == 1:
                # 인접 계층 — 상위→하위 관계
                upper = n1 if idx1 < idx2 else n2
                lower = n2 if idx1 < idx2 else n1
                rtype = _RELATION_RULES[min(idx1, idx2)][2] if min(idx1, idx2) < len(_RELATION_RULES) else "RELATED_TO"
                relations.append(GeneratedRelation(
                    source_temp_id=upper.temp_id,
                    target_temp_id=lower.temp_id,
                    relation_type=rtype,
                    weight=0.5,
                    confidence=0.5,
                ))

            if len(relations) >= 100:  # 관계 수 상한
                break
        if len(relations) >= 100:
            break

    return relations


# ── 엔드포인트 ── #

@router.post("")
async def generate_ontology(
    request: OntologyGenerationRequest,
    req: Request,
) -> dict:
    """DDL/문서/메타데이터에서 온톨로지 노드·관계 자동 생성 프리뷰.

    MVP: 규칙 기반 패턴 매칭. Phase 4에서 LLM 호출 추가.
    """
    if request.source_type == "ddl" and request.ddl_text:
        preview = _generate_from_ddl(request.ddl_text, request.max_nodes)
    elif request.source_type == "metadata" and request.metadata_json:
        preview = _generate_from_metadata(request.metadata_json, request.max_nodes)
    elif request.source_type == "document" and request.document_text:
        # 문서 기반 생성은 Phase 4 LLM 호출 필요 — 현재는 빈 프리뷰
        preview = GeneratedOntologyPreview(
            source_type="document",
            generation_method="pending_llm",
            warnings=["문서 기반 온톨로지 생성은 LLM 연동 후 지원됩니다 (Phase 4)"],
        )
    else:
        preview = GeneratedOntologyPreview(warnings=["입력 데이터가 비어있습니다"])

    return {
        "success": True,
        "data": preview.model_dump(),
    }


@router.post("/confirm")
async def confirm_ontology_generation(
    request: ConfirmGenerationRequest,
    req: Request,
) -> dict:
    """생성 프리뷰 확정 → Neo4j에 노드·관계 저장.

    TODO: Neo4j 저장 로직 구현 (기존 ontology_service.create_node 활용).
    현재는 확정 요청을 검증만 하고 응답한다.
    """
    if not request.nodes:
        return {"success": False, "error": "노드가 비어있습니다"}

    # C-2: tenant_id는 미들웨어에서 추출
    tenant_id = getattr(req.state, "tenant_id", "")

    logger.info(
        "온톨로지 생성 확정: case=%s, tenant=%s, nodes=%d, relations=%d",
        request.case_id, tenant_id, len(request.nodes), len(request.relations),
    )

    # M-4: Neo4j 미구현 상태를 명확히 전달
    return {
        "success": True,
        "data": {
            "case_id": request.case_id,
            "tenant_id": tenant_id,
            "nodes_pending": len(request.nodes),
            "relations_pending": len(request.relations),
            "status": "pending_neo4j",
        },
        "warnings": ["Neo4j 저장은 아직 구현되지 않았습니다. 프리뷰 데이터는 저장되지 않습니다."],
    }
