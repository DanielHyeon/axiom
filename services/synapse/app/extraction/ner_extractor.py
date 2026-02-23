from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ExtractedCompany(BaseModel):
    type: str = "COMPANY"
    name: str
    registration_no: str | None = None
    confidence: float = Field(..., ge=0, le=1.0)


class ExtractedPerson(BaseModel):
    type: str = "PERSON"
    name: str
    role: str | None = None
    confidence: float = Field(..., ge=0, le=1.0)


class ExtractedAmount(BaseModel):
    type: str = "AMOUNT"
    raw_text: str
    normalized_amount: int
    confidence: float = Field(..., ge=0, le=1.0)

    @field_validator("normalized_amount", mode="before")
    @classmethod
    def parse_korean_money(cls, v: Any) -> int:
        if isinstance(v, str):
            v_parsed = re.sub(r"\D", "", v)
            if v_parsed == "":
                return 0
            return int(v_parsed)
        return int(v) if v is not None else 0


class DocumentExtractionResponse(BaseModel):
    companies: list[ExtractedCompany] = []
    persons: list[ExtractedPerson] = []
    amounts: list[ExtractedAmount] = []


def _call_openai_ner(text: str, api_key: str, model: str) -> DocumentExtractionResponse:
    """OpenAI Chat Completions로 NER 구조화 출력 요청. 실패 시 빈 응답."""
    try:
        import httpx
    except ImportError:
        return DocumentExtractionResponse()
    prompt = """다음 텍스트에서 조직(회사명), 인물(이름·직책), 금액(원화·숫자)을 추출하라.
각 항목에 confidence(0.0~1.0)를 부여하라. 금액은 normalized_amount에 숫자만 넣어라.
JSON만 출력하라. 키: companies, persons, amounts. 각 배열 요소: type, name 또는 raw_text/normalized_amount, confidence."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You output only valid JSON with keys companies, persons, amounts."},
            {"role": "user", "content": f"{prompt}\n\n텍스트:\n{text[:12000]}"},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 2000,
    }
    try:
        resp = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
        out = json.loads(content)
        companies = [ExtractedCompany(**c) for c in (out.get("companies") or []) if isinstance(c, dict)]
        persons = [ExtractedPerson(**p) for p in (out.get("persons") or []) if isinstance(p, dict)]
        amounts = []
        for a in out.get("amounts") or []:
            if isinstance(a, dict):
                try:
                    amounts.append(ExtractedAmount(**a))
                except Exception:
                    pass
        return DocumentExtractionResponse(companies=companies, persons=persons, amounts=amounts)
    except Exception:
        return DocumentExtractionResponse()


class NERExtractor:
    """
    NER: 설정 시 OpenAI 구조화 출력, 미설정 시 Mock.
    """

    def extract_entities_sync(self, text: str) -> DocumentExtractionResponse:
        """동기 NER (파이프라인에서 호출)."""
        if not text or not text.strip():
            return DocumentExtractionResponse()
        from app.core.config import settings
        if settings.EXTRACTION_LLM_ENABLED and settings.OPENAI_API_KEY:
            return _call_openai_ner(
                text,
                api_key=settings.OPENAI_API_KEY,
                model=settings.EXTRACTION_LLM_MODEL,
            )
        return DocumentExtractionResponse()

    async def extract_entities(self, text: str) -> DocumentExtractionResponse:
        """비동기 NER (extract_entities_sync와 동일 동작)."""
        return self.extract_entities_sync(text)
