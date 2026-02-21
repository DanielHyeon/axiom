from pydantic import BaseModel, Field
from typing import List, Optional

class PropertyDefinition(BaseModel):
    name: str
    type: str
    description: Optional[str] = None

class NodeDefinition(BaseModel):
    label: str
    properties: List[PropertyDefinition]
    source_table: str
    
class EdgeDefinition(BaseModel):
    type: str
    source_label: str
    target_label: str
    properties: List[PropertyDefinition] = Field(default_factory=list)

class GraphSchema(BaseModel):
    version: str = "2.0"
    nodes: List[NodeDefinition]
    edges: List[EdgeDefinition]
    created_by: str = "Weaver"
