"""
SafeToolLoader (mcp-integration.md, agent-orchestration.md §3).
테넌트별 도구 격리·차단 목록 적용. agent_service.list_mcp_tools 기반 도구 로드.
"""
from __future__ import annotations

from typing import Any

# 설계 문서 기준 차단 도구 (mcp-integration.md §2.1)
BLOCKED_TOOLS = frozenset({
    "shell_execute",
    "file_delete",
    "file_write",
    "db_drop",
    "db_truncate",
    "network_scan",
    "credential_access",
})


class SafeToolLoader:
    """도구 우선순위·보안 정책 적용. MCP(agent_service) 도구 목록 로드 후 BLOCKED_TOOLS 제외."""

    @staticmethod
    async def create_tools_for_activity(
        activity: dict[str, Any],
        tenant_id: str,
    ) -> list[dict[str, Any]]:
        """
        액티비티에 사용할 도구 목록 생성.
        agent_service.list_mcp_tools(tenant_id)로 MCP 도구 조회 후 차단 목록 제외.
        반환: [{"tool_name": str, "server_name": str, "run": callable}, ...]
        """
        from app.services.agent_service import agent_service
        try:
            out = agent_service.list_mcp_tools(tenant_id)
            tools = out.get("tools") or []
        except Exception:
            return []
        result: list[dict[str, Any]] = []
        for t in tools:
            name = (t or {}).get("tool_name")
            server = (t or {}).get("server_name")
            if not name or SafeToolLoader.is_blocked(name):
                continue

            def _make_run(n: str, s: str) -> Any:
                async def _run(parameters: dict[str, Any] | None = None) -> dict[str, Any]:
                    return agent_service.execute_tool(
                        tenant_id,
                        {"tool_name": n, "server_name": s, "parameters": parameters or {}},
                    )
                return _run

            result.append({
                "tool_name": name,
                "server_name": server or "",
                "run": _make_run(name, server or ""),
            })
        return result

    @staticmethod
    def is_blocked(tool_name: str) -> bool:
        return tool_name in BLOCKED_TOOLS
