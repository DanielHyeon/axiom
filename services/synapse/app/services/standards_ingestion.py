"""G39: Standards Ingestion Pipeline — 산업 표준/규정/KPI 사전 수집 + 온톨로지 연결.

4대 정보 소스 중 "산업 표준"을 수집하고 온톨로지/시맨틱 계약과 연결하는 파이프라인.
CSV/JSON 형태의 표준 문서를 파싱하여 StandardConcept를 생성하고,
기존 온톨로지 노드와 자동 매핑을 제안한다.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger("axiom.synapse.standards_ingestion")


# ── 모델 ── #

class StandardsCorpusType(str, Enum):
    """표준 문서 유형"""
    REGULATION = "regulation"             # 규정 문서 (법률, 지침)
    TERMINOLOGY = "terminology"           # 산업 표준 용어집 (ISO, KS 등)
    KPI_DICTIONARY = "kpi_dictionary"     # 산업별 KPI 사전
    CODEBOOK = "codebook"                 # 코드북 (산업 분류 코드, 통화 코드 등)


class StandardConcept(BaseModel):
    """산업 표준에서 추출한 개념"""
    concept_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    corpus_type: StandardsCorpusType
    source_document: str = ""             # 출처 문서명
    definition: str = ""                  # 정의 (원문)
    category: str | None = None           # 분류 (예: "재무", "제조", "품질")
    suggested_layer: str | None = None    # 온톨로지 5계층 중 매핑 제안
    language: str = "ko"
    tags: list[str] = Field(default_factory=list)


class MappingSuggestion(BaseModel):
    """표준 개념 → 기존 온톨로지 노드 매핑 제안"""
    concept_id: str
    concept_name: str
    ontology_node_id: str | None = None   # 기존 노드 매핑 (있으면)
    ontology_node_name: str = ""
    confidence: float = 0.5
    action: Literal["map_existing", "create_new", "add_synonym"] = "create_new"
    reasoning: str = ""


class IngestionResult(BaseModel):
    """표준 수집 결과"""
    source_document: str = ""
    corpus_type: StandardsCorpusType = StandardsCorpusType.TERMINOLOGY
    concepts: list[StandardConcept] = Field(default_factory=list)
    mappings: list[MappingSuggestion] = Field(default_factory=list)
    concept_count: int = 0
    errors: list[str] = Field(default_factory=list)


# ── 파서 ── #

class StandardsParser:
    """표준 문서 파싱 — CSV/JSON 지원"""

    def parse_csv(
        self,
        content: str,
        corpus_type: StandardsCorpusType,
        source_document: str = "",
    ) -> list[StandardConcept]:
        """CSV 형식 표준 문서 파싱.

        기대 컬럼: name, definition, category (선택), layer (선택), tags (선택)
        """
        concepts = []
        reader = csv.DictReader(io.StringIO(content))

        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue

            concepts.append(StandardConcept(
                name=name,
                corpus_type=corpus_type,
                source_document=source_document,
                definition=row.get("definition", "").strip(),
                category=row.get("category", "").strip() or None,
                suggested_layer=row.get("layer", "").strip() or None,
                tags=[t.strip() for t in row.get("tags", "").split(",") if t.strip()],
            ))

            if len(concepts) >= 10000:  # 최대 1만 개
                break

        return concepts

    def parse_json(
        self,
        content: str,
        corpus_type: StandardsCorpusType,
        source_document: str = "",
    ) -> list[StandardConcept]:
        """JSON 형식 표준 문서 파싱.

        기대 구조: [{"name": ..., "definition": ..., ...}] 또는 {"concepts": [...]}
        """
        data = json.loads(content)

        if isinstance(data, dict):
            items = data.get("concepts", data.get("items", data.get("data", [])))
        elif isinstance(data, list):
            items = data
        else:
            return []

        concepts = []
        for item in items[:10000]:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            if not name:
                continue

            concepts.append(StandardConcept(
                name=name,
                corpus_type=corpus_type,
                source_document=source_document,
                definition=str(item.get("definition", "")),
                category=item.get("category"),
                suggested_layer=item.get("layer") or item.get("suggested_layer"),
                tags=item.get("tags", []) if isinstance(item.get("tags"), list) else [],
            ))

        return concepts


# ── 매핑 엔진 ── #

# 간단한 이름 매칭 기반 매핑 제안 (MVP — Phase 4에서 임베딩 유사도 추가)
_LAYER_KEYWORDS: dict[str, list[str]] = {
    "kpi": ["kpi", "지표", "성과", "효율", "비율", "rate", "ratio", "index", "metric"],
    "measure": ["측정", "수치", "양", "measure", "count", "amount"],
    "process": ["공정", "프로세스", "절차", "단계", "process", "step", "workflow"],
    "resource": ["설비", "자원", "인력", "자재", "machine", "resource", "material"],
}


class StandardsMappingEngine:
    """표준 개념 → 온톨로지 매핑 제안 엔진"""

    def suggest_mappings(
        self,
        concepts: list[StandardConcept],
        existing_nodes: list[dict] | None = None,
    ) -> list[MappingSuggestion]:
        """개념별 매핑 제안 생성.

        existing_nodes: [{"id": ..., "name": ..., "layer": ...}] — Neo4j 조회 결과
        """
        suggestions = []

        for concept in concepts:
            # 1. 기존 노드에서 이름 매칭
            if existing_nodes:
                match = self._find_name_match(concept.name, existing_nodes)
                if match:
                    suggestions.append(MappingSuggestion(
                        concept_id=concept.concept_id,
                        concept_name=concept.name,
                        ontology_node_id=match["id"],
                        ontology_node_name=match["name"],
                        confidence=0.8,
                        action="map_existing",
                        reasoning=f"이름 매칭: '{concept.name}' ≈ '{match['name']}'",
                    ))
                    continue

            # 2. 계층 추론 + 신규 생성 제안
            layer = concept.suggested_layer or self._infer_layer(concept.name)
            suggestions.append(MappingSuggestion(
                concept_id=concept.concept_id,
                concept_name=concept.name,
                confidence=0.5,
                action="create_new",
                reasoning=f"신규 노드 생성 제안 (계층: {layer})",
            ))

        return suggestions

    def _find_name_match(self, name: str, nodes: list[dict]) -> dict | None:
        """이름 기반 매칭 (정확 + 부분)"""
        name_lower = name.lower()
        for node in nodes:
            node_name = node.get("name", "").lower()
            if node_name == name_lower:
                return node
            if name_lower in node_name or node_name in name_lower:
                return node
        return None

    def _infer_layer(self, name: str) -> str:
        """개념명에서 온톨로지 계층 추론"""
        name_lower = name.lower()
        for layer, keywords in _LAYER_KEYWORDS.items():
            for kw in keywords:
                if kw in name_lower:
                    return layer
        return "measure"  # 기본 계층


# 모듈 수준 인스턴스
standards_parser = StandardsParser()
standards_mapper = StandardsMappingEngine()
