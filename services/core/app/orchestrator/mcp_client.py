"""
MCP(Model Context Protocol) 클라이언트 (mcp-integration.md).
Saga 보상 및 에이전트 도구 호출용. MCP 서버 미연동 시 no-op 반환.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("axiom.orchestrator")


async def execute_mcp_tool(
    tool_name: str,
    parameters: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    MCP 도구 1회 실행.
    MCP 서버 URL이 설정되지 않았거나 호출 실패 시 빈 dict 반환.
    """
    base_url = getattr(settings, "MCP_BASE_URL", None) or ""
    if not base_url:
        logger.debug("MCP_BASE_URL not set, skipping tool %s", tool_name)
        return {}
    path = (getattr(settings, "MCP_EXECUTE_PATH", None) or "/tools/execute").strip()
    url = f"{base_url.rstrip('/')}{path}"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout or settings.MCP_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                url,
                json={"tool": tool_name, "parameters": parameters or {}},
            )
            if resp.status_code >= 400:
                logger.warning("MCP tool %s failed: %s %s", tool_name, resp.status_code, resp.text)
                return {}
            return resp.json() if resp.content else {}
    except Exception as e:
        logger.warning("MCP execute_mcp_tool error for %s: %s", tool_name, e)
        return {}
