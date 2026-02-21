from pydantic import BaseModel, Field
from typing import List, Optional
import structlog

logger = structlog.get_logger()

class ValueMapping(BaseModel):
    natural_value: str = Field(description="Phrase from natural language user input")
    db_value: str = Field(description="Precise SQL value expected by Target DB")
    column_fqn: str = Field(description="Fully qualified column name e.g public.table.column")
    confidence: float = Field(default=1.0, description="1.0 for manually overridden or enums, < 1.0 for auto inferences")

class ValueMappingExtractor:
    """
    LLM driven wrapper to align raw questions into known discrete database identities.
    Prioritizes explicit configurations like user-overrides mapping '성공' -> 'SUCCESS'.
    """
    async def extract_value_mappings(self, question: str, sql: str) -> List[ValueMapping]:
        logger.info("extracting_value_mappings", question=question)
        # LLM Simulation inference
        if "성공" in question or "SUCCESS" in sql:
            return [
                ValueMapping(
                    natural_value="성공",
                    db_value="SUCCESS",
                    column_fqn="public.process_metrics.status",
                    confidence=0.95
                )
            ]
        return []

value_mapping_extractor = ValueMappingExtractor()
