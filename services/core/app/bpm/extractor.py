"""
BPMN/DMN 추출기 (bpm-engine.md, process-gpt-bpmn-extractor-main 이식 예정).
PDF → 엔티티 → BPMN/DMN 생성. 우선순위 낮음 — 구현 예정.
"""
from __future__ import annotations


def extract_from_pdf(pdf_path: str) -> dict:
    """PDF에서 프로세스 엔티티 추출. 현재 미구현."""
    raise NotImplementedError("BPMN extractor (PDF→entity→BPMN/DMN) is planned; not yet implemented.")
