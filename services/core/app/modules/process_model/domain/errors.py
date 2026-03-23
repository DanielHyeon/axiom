"""프로세스 모델 도메인 예외."""


class ProcessModelError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProcessDefinitionNotFoundError(ProcessModelError):
    def __init__(self, definition_id: str):
        super().__init__("ENTITY_NOT_FOUND", f"ProcessDefinition '{definition_id}' not found", 404)


class ProcessVersionNotFoundError(ProcessModelError):
    def __init__(self, version_id: str):
        super().__init__("ENTITY_NOT_FOUND", f"ProcessVersion '{version_id}' not found", 404)


class NamespaceDuplicatedError(ProcessModelError):
    def __init__(self, namespace: str):
        super().__init__("NAMESPACE_DUPLICATED", f"Namespace '{namespace}' already exists", 409)


class VersionNotEditableError(ProcessModelError):
    def __init__(self, version_id: str, status: str):
        super().__init__(
            "PROCESS_VERSION_NOT_EDITABLE",
            f"Version '{version_id}' is {status}, cannot edit. Clone to create a new version.",
            409,
        )


class PublishValidationError(ProcessModelError):
    def __init__(self, failures: list[dict]):
        super().__init__(
            "PROCESS_PUBLISH_VALIDATION_FAILED",
            f"{len(failures)} validation rules failed",
            422,
        )
        self.failures = failures


class RelationTypeInvalidError(ProcessModelError):
    def __init__(self, rel_type: str):
        super().__init__("RELATION_TYPE_INVALID", f"Invalid relation type: '{rel_type}'", 422)


class VersionConflictError(ProcessModelError):
    def __init__(self, current_version: int, expected_version: int):
        super().__init__(
            "VERSION_CONFLICT",
            f"Version conflict: current={current_version}, expected={expected_version}",
            409,
        )
