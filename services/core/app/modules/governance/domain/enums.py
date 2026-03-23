"""거버넌스 도메인 열거형."""
from enum import Enum


class OrgType(str, Enum):
    """조직 단위 유형."""
    HQ = "HQ"
    DIVISION = "DIVISION"
    DEPARTMENT = "DEPARTMENT"
    SUBSIDIARY = "SUBSIDIARY"
    CENTER = "CENTER"


class WorkspaceType(str, Enum):
    """워크스페이스 유형."""
    PROCESS = "PROCESS"
    ANALYTICS = "ANALYTICS"
    TWIN = "TWIN"
    SANDBOX = "SANDBOX"


class VisibilityPolicy(str, Enum):
    """워크스페이스 가시성 정책."""
    PRIVATE = "PRIVATE"
    ORG_SHARED = "ORG_SHARED"
    TENANT_SHARED = "TENANT_SHARED"


class MembershipScopeType(str, Enum):
    """멤버십 범위 유형."""
    TENANT = "TENANT"
    ORG_UNIT = "ORG_UNIT"
    WORKSPACE = "WORKSPACE"


class MembershipStatus(str, Enum):
    """멤버십 상태."""
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    EXPIRED = "EXPIRED"
