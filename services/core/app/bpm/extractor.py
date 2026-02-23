"""
BPMN/DMN 추출기 (bpm-engine.md §6).
PDF → 텍스트 → 청킹 → EntityExtractor → BPMNGenerator → DMNGenerator → HITL.
최소 동작: 파일 검증·텍스트 추출(pdfplumber 선택)·스텁 반환. LLM 파이프라인은 추후 연동.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("axiom.bpm")

# PDF 매직 바이트
PDF_MAGIC = b"%PDF"


def _extract_text_pdfplumber(pdf_path: str) -> str | None:
    """pdfplumber가 있으면 텍스트 추출, 없으면 None."""
    try:
        import pdfplumber
    except ImportError:
        return None
    try:
        with pdfplumber.open(pdf_path) as pdf:
            parts = [t for p in pdf.pages if (t := p.extract_text())]
            return "\n".join(parts) if parts else ""
    except Exception as e:
        logger.warning("pdfplumber extract failed for %s: %s", pdf_path, e)
        return None


def _chunk_text(text: str, max_tokens: int = 800) -> list[str]:
    """간단 청킹: 공백/줄 단위로 잘라 대략 max_tokens 이하로. (실제 토큰 카운트는 LLM 토크나이저 사용 시 교체)"""
    if not text or max_tokens <= 0:
        return []
    # 대략 4자 = 1토큰 가정
    approx_chars = max_tokens * 4
    chunks = []
    current = []
    current_len = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line_len = len(line) + 1
        if current_len + line_len > approx_chars and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append("\n".join(current))
    return chunks


def extract_from_pdf(pdf_path: str) -> dict:
    """
    PDF에서 프로세스 엔티티·BPMN/DMN 추출 (bpm-engine.md §6.1).

    반환: {
        "ok": bool,
        "text_extract": str | None,
        "chunks": list[str],
        "process_definition": dict | None,  # ProcessDefinition JSON
        "bpmn_xml": str | None,
        "dmn_xml": str | None,
        "confidence": float,
        "errors": list[str],
    }
    """
    errors: list[str] = []
    if not pdf_path or not isinstance(pdf_path, str):
        return {
            "ok": False,
            "text_extract": None,
            "chunks": [],
            "process_definition": None,
            "bpmn_xml": None,
            "dmn_xml": None,
            "confidence": 0.0,
            "errors": ["pdf_path is required and must be a non-empty string"],
        }
    if not os.path.isfile(pdf_path):
        return {
            "ok": False,
            "text_extract": None,
            "chunks": [],
            "process_definition": None,
            "bpmn_xml": None,
            "dmn_xml": None,
            "confidence": 0.0,
            "errors": [f"File not found: {pdf_path}"],
        }

    try:
        with open(pdf_path, "rb") as f:
            head = f.read(8)
        if not head.startswith(PDF_MAGIC):
            return {
                "ok": False,
                "text_extract": None,
                "chunks": [],
                "process_definition": None,
                "bpmn_xml": None,
                "dmn_xml": None,
                "confidence": 0.0,
                "errors": ["File is not a PDF (invalid magic bytes)"],
            }
    except OSError as e:
        return {
            "ok": False,
            "text_extract": None,
            "chunks": [],
            "process_definition": None,
            "bpmn_xml": None,
            "dmn_xml": None,
            "confidence": 0.0,
            "errors": [f"Cannot read file: {e}"],
        }

    # 1) 텍스트 추출 (pdfplumber 선택)
    text = _extract_text_pdfplumber(pdf_path)
    if text is None:
        text = ""
        errors.append("PDF text extraction skipped (install pdfplumber for extraction)")

    # 2) 청킹
    chunks = _chunk_text(text, 800)

    # 3) EntityExtractor / BPMNGenerator / DMNGenerator — 미구현 시 스텁
    process_definition = None
    bpmn_xml = None
    dmn_xml = None
    confidence = 0.0
    if not chunks and not text:
        errors.append("No text extracted; EntityExtractor and BPMN/DMN generation not run")
    else:
        # 스텁: 실제 LLM 호출은 추후 연동
        process_definition = {
            "name": "Extracted from PDF (stub)",
            "activities": [],
            "gateways": [],
        }
        bpmn_xml = '<?xml version="1.0"?><bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"/>'
        dmn_xml = None
        confidence = 0.0

    return {
        "ok": not errors or bool(text),
        "text_extract": text or None,
        "chunks": chunks,
        "process_definition": process_definition,
        "bpmn_xml": bpmn_xml,
        "dmn_xml": dmn_xml,
        "confidence": confidence,
        "errors": errors,
    }
