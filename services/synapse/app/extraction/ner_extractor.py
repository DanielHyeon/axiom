from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import re

class ExtractedCompany(BaseModel):
    type: str = "COMPANY"
    name: str
    registration_no: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1.0)

class ExtractedPerson(BaseModel):
    type: str = "PERSON"
    name: str # e.g 홍길동
    role: Optional[str] = None # e.g 매니저
    confidence: float = Field(..., ge=0, le=1.0)

class ExtractedAmount(BaseModel):
    type: str = "AMOUNT"
    raw_text: str
    normalized_amount: int
    confidence: float = Field(..., ge=0, le=1.0)
    
    @field_validator('normalized_amount', mode='before')
    def parse_korean_money(cls, v, info):
        # In a real app, this logic converts "100억원" into 10000000000.
        # This validator acts as the boundary
        if isinstance(v, str):
            v_parsed = re.sub(r'\\D', '', v)
            if v_parsed == '': return 0
            return int(v_parsed)
        return v

class DocumentExtractionResponse(BaseModel):
    companies: List[ExtractedCompany] = []
    persons: List[ExtractedPerson] = []
    amounts: List[ExtractedAmount] = []

class NERExtractor:
    """
    Handles prompt execution for GPT-4o based NER Entity mapping.
    """
    async def extract_entities(self, text: str) -> DocumentExtractionResponse:
        """
        Mock extraction returning empty defaults.
        """
        return DocumentExtractionResponse()
