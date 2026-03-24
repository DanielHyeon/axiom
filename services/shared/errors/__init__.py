"""공통 에러 코드 모듈.

AXIOM_XXXX 에러 코드 체계를 정의하여
프론트엔드, 백엔드, 운영 팀이 동일한 에러 분류를 사용한다.
"""

from .error_codes import AxiomError, AxiomErrorCode, axiom_error_handler  # noqa: F401

__all__ = ["AxiomError", "AxiomErrorCode", "axiom_error_handler"]
