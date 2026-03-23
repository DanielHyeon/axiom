"""G39: Standards Ingestion API — 산업 표준 문서 업로드 + 개념 추출 + 매핑 제안.

CSV/JSON 형태의 표준 문서를 파싱하여 StandardConcept를 생성하고
기존 온톨로지 노드와 자동 매핑을 제안한다.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.services.standards_ingestion import (
    StandardsCorpusType,
    StandardConcept,
    IngestionResult,
    standards_parser,
    standards_mapper,
)

logger = logging.getLogger("axiom.synapse.api.standards_import")

router = APIRouter(prefix="/api/v3/synapse/standards", tags=["산업 표준"])


# ── 엔드포인트 ── #

@router.post("/ingest")
async def ingest_standards_document(
    req: Request,
    file: UploadFile = File(...),
    corpus_type: StandardsCorpusType = Form(StandardsCorpusType.TERMINOLOGY),
) -> dict:
    """산업 표준 문서 업로드 → 개념 추출 + 매핑 제안.

    지원 형식: CSV, JSON
    CSV 기대 컬럼: name, definition, category, layer, tags
    JSON: [{"name": ..., "definition": ..., ...}]
    """
    tenant_id = getattr(req.state, "tenant_id", "")

    try:
        _MAX_SIZE = 5 * 1024 * 1024
        raw = await file.read(_MAX_SIZE + 1)
        if len(raw) > _MAX_SIZE:
            raise HTTPException(status_code=413, detail="파일 크기 초과 (최대 5MB)")
        content = raw.decode("utf-8", errors="ignore")
        filename = file.filename or "upload"

        # 형식 감지 + 파싱
        if filename.endswith(".json"):
            concepts = standards_parser.parse_json(content, corpus_type, filename)
        elif filename.endswith(".csv"):
            concepts = standards_parser.parse_csv(content, corpus_type, filename)
        else:
            raise HTTPException(status_code=400, detail="지원 형식: CSV, JSON")

        # 매핑 제안 (기존 노드 없이 — Phase 4에서 Neo4j 조회 추가)
        mappings = standards_mapper.suggest_mappings(concepts)

        result = IngestionResult(
            source_document=filename,
            corpus_type=corpus_type,
            concepts=concepts,
            mappings=mappings,
            concept_count=len(concepts),
        )

        logger.info(
            "표준 수집 완료: tenant=%s, file=%s, concepts=%d, mappings=%d",
            tenant_id, filename, len(concepts), len(mappings),
        )

        return {
            "success": True,
            "data": result.model_dump(mode="json"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("표준 수집 실패: %s", e)
        raise HTTPException(status_code=500, detail="표준 문서 처리 중 내부 오류 발생") from e
