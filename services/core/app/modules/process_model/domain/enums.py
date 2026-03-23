"""프로세스 모델 도메인 열거형."""
from enum import Enum


class ProcessType(str, Enum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    HYBRID = "HYBRID"
    AI_AGENT = "AI_AGENT"
    PIPELINE = "PIPELINE"


class LifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class StepType(str, Enum):
    START = "START"
    TASK = "TASK"
    DECISION = "DECISION"
    WAIT = "WAIT"
    END = "END"
    SUBPROCESS = "SUBPROCESS"
    CHECKPOINT = "CHECKPOINT"


class ActorType(str, Enum):
    USER = "USER"
    ROLE = "ROLE"
    SYSTEM = "SYSTEM"
    AGENT = "AGENT"
    EXTERNAL = "EXTERNAL"


class AutomationLevel(str, Enum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    AUTOMATED = "AUTOMATED"
    AI_AUTONOMOUS = "AI_AUTONOMOUS"


class RelationType(str, Enum):
    TRIGGERS = "TRIGGERS"
    CONSUMES = "CONSUMES"
    PRODUCES = "PRODUCES"
    BLOCKS = "BLOCKS"
    DEPENDS_ON = "DEPENDS_ON"
    HANDOFF_TO = "HANDOFF_TO"
    GOVERNED_BY = "GOVERNED_BY"
    MEASURED_BY = "MEASURED_BY"
    INFLUENCES_KPI = "INFLUENCES_KPI"


class Criticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TransitionType(str, Enum):
    NEXT = "NEXT"
    YES = "YES"
    NO = "NO"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    ESCALATE = "ESCALATE"


class ContractType(str, Enum):
    EVENT = "EVENT"
    DOCUMENT = "DOCUMENT"
    API = "API"
    DATASET = "DATASET"
    MESSAGE = "MESSAGE"


class RuleType(str, Enum):
    BUSINESS_RULE = "BUSINESS_RULE"
    POLICY = "POLICY"
    THRESHOLD = "THRESHOLD"
    ROUTING = "ROUTING"
    VALIDATION = "VALIDATION"
    AI_GUARDRAIL = "AI_GUARDRAIL"


class TargetDirection(str, Enum):
    HIGHER_BETTER = "HIGHER_BETTER"
    LOWER_BETTER = "LOWER_BETTER"
    TARGET_VALUE = "TARGET_VALUE"


class AggregationType(str, Enum):
    SUM = "SUM"
    AVG = "AVG"
    COUNT = "COUNT"
    RATE = "RATE"
    P95 = "P95"
