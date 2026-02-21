from pydantic import BaseModel, Field
from typing import List, Optional

class ExtractedEntity(BaseModel):
    name: str
    type: str # Resource, Process, Measure
    confidence: float = Field(..., ge=0, le=1)

class OntologyMapper:
    """
    Maps LLM structured outputs (NER, Relations) into the 4-layer Graph schema.
    Applies the 0.75 HITL confidence routing.
    """
    def route_for_human_review(self, entity: ExtractedEntity) -> bool:
        if entity.confidence < 0.75:
            return True
        return False
