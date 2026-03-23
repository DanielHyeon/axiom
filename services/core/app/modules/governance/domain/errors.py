"""거버넌스 도메인 예외."""


class GovernanceError(Exception):
    """거버넌스 도메인 기본 예외."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class OrgUnitNotFoundError(GovernanceError):
    def __init__(self, org_unit_id: str):
        super().__init__("ORG_UNIT_NOT_FOUND", f"OrgUnit '{org_unit_id}' not found", 404)


class WorkspaceNotFoundError(GovernanceError):
    def __init__(self, workspace_id: str):
        super().__init__("WORKSPACE_NOT_FOUND", f"Workspace '{workspace_id}' not found", 404)


class WorkspaceAccessDeniedError(GovernanceError):
    def __init__(self, workspace_id: str):
        super().__init__("WORKSPACE_ACCESS_DENIED", f"Access denied to workspace '{workspace_id}'", 403)


class DuplicateCodeError(GovernanceError):
    def __init__(self, entity_type: str, code: str):
        super().__init__("NAMESPACE_DUPLICATED", f"{entity_type} code '{code}' already exists", 409)


class MembershipOverlapError(GovernanceError):
    def __init__(self):
        super().__init__("MEMBERSHIP_OVERLAP", "Membership period overlaps with existing active membership", 422)
