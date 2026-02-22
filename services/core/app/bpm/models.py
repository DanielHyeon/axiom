"""
BPM 도메인 Pydantic 모델 (bpm-engine.md §2).
DB 모델(ProcessDefinition, WorkItem)과 분리된, 실행 엔진용 정의 구조.
"""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    AUTONOMOUS = "AUTONOMOUS"
    SUPERVISED = "SUPERVISED"
    MANUAL = "MANUAL"
    SELF_VERIFY = "SELF_VERIFY"


class ActivityType(str, Enum):
    HUMAN_TASK = "humanTask"
    SERVICE_TASK = "serviceTask"
    SCRIPT_TASK = "scriptTask"
    SUB_PROCESS = "subProcess"


class GatewayType(str, Enum):
    EXCLUSIVE = "exclusiveGateway"
    PARALLEL = "parallelGateway"
    INCLUSIVE = "inclusiveGateway"


class ProcessData(BaseModel):
    name: str
    type: str = "api"
    source: str = ""
    fields: list[str] = []


class ProcessRole(BaseModel):
    name: str
    id: str
    assignment_rule: Optional[str] = None


class ProcessActivityModel(BaseModel):
    name: str
    id: str
    type: ActivityType = ActivityType.HUMAN_TASK
    instruction: str = ""
    input_data: list[ProcessData] = []
    output_data: list[ProcessData] = []
    python_code: Optional[str] = None
    agent: Optional[str] = None
    agent_mode: AgentMode = AgentMode.MANUAL
    orchestration: Optional[dict[str, Any]] = None
    compensation: Optional[str] = None


class Gateway(BaseModel):
    id: str
    name: str
    type: GatewayType
    conditions: dict[str, str] = {}


class Transition(BaseModel):
    id: str
    source: str
    target: str
    condition: Optional[str] = None


class ProcessDefinitionModel(BaseModel):
    """프로세스 정의 (BPMN 기반). definition JSON 역직렬화용."""
    process_definition_id: str = ""
    process_definition_name: str = ""
    description: str = ""
    data: list[ProcessData] = []
    roles: list[ProcessRole] = []
    activities: list[ProcessActivityModel] = []
    gateways: list[Gateway] = []
    transitions: list[Transition] = []
    version: int = 1
    tenant_id: str = ""
