"""API 응답 래퍼 — 일관된 응답 형식 보장.

모든 엔드포인트가 동일한 응답 구조를 사용하도록 한다:
  성공: {"success": true, "data": ..., "meta": {...}}
  실패: {"success": false, "error": {"code": "...", "message": "..."}}
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """에러 상세 정보."""
    code: str = "INTERNAL_ERROR"
    message: str = ""
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel, Generic[T]):
    """표준 API 응답 래퍼.

    FastAPI의 response_model로 사용할 수 있다:
        @router.get("/items", response_model=ApiResponse[list[Item]])
    """
    success: bool = True
    data: T | None = None
    meta: dict[str, Any] | None = None
    error: ErrorDetail | None = None


def ok(data: Any = None, meta: dict | None = None) -> dict:
    """성공 응답을 생성한다.

    사용 예시:
        return ok(data={"id": 1, "name": "테스트"})
        return ok(data=items, meta={"cached": True})
    """
    result: dict[str, Any] = {"success": True, "data": data}
    if meta:
        result["meta"] = meta
    return result


def fail(
    message: str,
    code: str = "INTERNAL_ERROR",
    status_code: int = 400,
    details: dict | None = None,
) -> dict:
    """실패 응답을 생성한다.

    HTTPException과 함께 사용:
        raise HTTPException(status_code=404, detail=fail("항목 없음", code="NOT_FOUND"))

    또는 직접 반환:
        return JSONResponse(status_code=400, content=fail("잘못된 요청"))
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            **({"details": details} if details else {}),
        },
    }


def paginated(
    data: list,
    total: int,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """페이지네이션 응답을 생성한다.

    사용 예시:
        items = await fetch_items(offset, limit)
        total = await count_items()
        return paginated(data=items, total=total, page=page, page_size=limit)
    """
    return {
        "success": True,
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "pageSize": page_size,
            "totalPages": (total + page_size - 1) // page_size,
        },
    }
