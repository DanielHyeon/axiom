import uuid
from datetime import datetime, timedelta, timezone
import os
from typing import Any

import httpx

from app.core.config import settings
from app.modules.agent.infrastructure.state.agent_state_store import AgentStateStore


class AgentDomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentService:
    def __init__(self, store: AgentStateStore | None = None) -> None:
        self.store = store or AgentStateStore(
            os.getenv("CORE_AGENT_STATE_DATABASE_URL", settings.DATABASE_URL)
        )
        loaded = self.store.load_state()
        self._feedback_by_tenant: dict[str, dict[str, dict[str, Any]]] = loaded.get("feedback_by_tenant", {})
        self._mcp_by_tenant: dict[str, dict[str, Any]] = loaded.get("mcp_by_tenant", {})
        self._knowledge_by_tenant: dict[str, dict[str, dict[str, Any]]] = loaded.get("knowledge_by_tenant", {})

    def clear(self) -> None:
        self._feedback_by_tenant.clear()
        self._mcp_by_tenant.clear()
        self._knowledge_by_tenant.clear()
        self.store.clear()

    def _feedback_bucket(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        return self._feedback_by_tenant.setdefault(tenant_id, {})

    def _knowledge_bucket(self, tenant_id: str) -> dict[str, dict[str, Any]]:
        return self._knowledge_by_tenant.setdefault(tenant_id, {})

    def _mcp_bucket(self, tenant_id: str) -> dict[str, Any]:
        return self._mcp_by_tenant.setdefault(tenant_id, {"servers": []})

    def submit_feedback(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        workitem_id = str(payload.get("workitem_id") or "").strip()
        content = str(payload.get("content") or "").strip()
        feedback_type = str(payload.get("feedback_type") or "suggestion")
        priority = str(payload.get("priority") or "medium").lower()
        corrected_output = payload.get("corrected_output") or {}
        if not workitem_id or not content:
            raise AgentDomainError(400, "INVALID_FEEDBACK", "workitem_id and content are required")
        if feedback_type not in {"correction", "suggestion", "approval"}:
            raise AgentDomainError(400, "INVALID_FEEDBACK", "invalid feedback_type")
        if priority not in {"low", "medium", "high"}:
            raise AgentDomainError(400, "INVALID_FEEDBACK", "invalid priority")
        if corrected_output and not isinstance(corrected_output, dict):
            raise AgentDomainError(400, "INVALID_FEEDBACK", "corrected_output must be object")
        if feedback_type == "correction" and not corrected_output:
            raise AgentDomainError(400, "INVALID_FEEDBACK", "corrected_output is required for correction")

        conflict_level = "HIGH" if priority == "high" else "LOW"
        confidence = 0.55 if conflict_level == "HIGH" else 0.85
        feedback_id = f"fb-{uuid.uuid4()}"
        bucket = self._feedback_bucket(tenant_id)

        if conflict_level == "HIGH":
            review_record = {
                "feedback_id": feedback_id,
                "workitem_id": workitem_id,
                "status": "NEEDS_REVIEW",
                "analysis": {
                    "conflict_level": conflict_level,
                    "operation": "REVIEW_REQUIRED",
                    "confidence": confidence,
                },
                "committed_to": [],
                "created_at": _now(),
            }
            records = list(bucket.get(workitem_id, {}).get("records", []))
            records.append(review_record)
            bucket[workitem_id] = {"latest": review_record, "records": records}
            self.store.upsert_feedback(tenant_id, workitem_id, bucket[workitem_id])
            raise AgentDomainError(422, "KNOWLEDGE_CONFLICT_HIGH", "high-conflict feedback requires manual review")

        record = {
            "feedback_id": feedback_id,
            "workitem_id": workitem_id,
            "status": "COMPLETED",
            "analysis": {
                "conflict_level": conflict_level,
                "operation": "UPDATE" if feedback_type != "approval" else "UPSERT",
                "confidence": confidence,
            },
            "committed_to": [
                {"type": "MEMORY", "action": "UPDATE", "content_preview": content[:120]},
                {"type": "DMN_RULE", "action": "UPDATE", "rule_name": "feedback_rule", "changed_rows": 1},
            ],
            "created_at": _now(),
        }
        records = list(bucket.get(workitem_id, {}).get("records", []))
        records.append(record)
        bucket[workitem_id] = {"latest": record, "records": records}
        self.store.upsert_feedback(tenant_id, workitem_id, bucket[workitem_id])

        knowledge_id = f"kn-{uuid.uuid4()}"
        knowledge_payload = {
            "id": knowledge_id,
            "type": "MEMORY",
            "title": f"Feedback:{workitem_id}",
            "content": content,
            "created_at": _now(),
        }
        self._knowledge_bucket(tenant_id)[knowledge_id] = knowledge_payload
        self.store.upsert_knowledge(tenant_id, knowledge_id, knowledge_payload)
        return {
            "feedback_id": feedback_id,
            "status": "PROCESSING",
            "estimated_completion": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat(),
            "message": "피드백을 분석하여 지식에 반영합니다.",
        }

    def get_feedback(self, tenant_id: str, workitem_id: str) -> dict[str, Any]:
        feed = self._feedback_bucket(tenant_id).get(workitem_id) or {}
        record = feed.get("latest")
        if not record:
            raise AgentDomainError(404, "INVALID_FEEDBACK", "feedback not found")
        return {
            "feedback_id": record["feedback_id"],
            "status": record["status"],
            "analysis": record["analysis"],
            "committed_to": record["committed_to"],
            "history_count": len(feed.get("records", [])),
        }

    def configure_mcp(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        servers = payload.get("servers")
        if not isinstance(servers, list) or not servers:
            raise AgentDomainError(400, "INVALID_REQUEST", "servers is required")
        normalized = []
        total_tools = 0
        for server in servers:
            name = str((server or {}).get("name") or "").strip()
            url = str((server or {}).get("url") or "").strip()
            if not name or not url:
                raise AgentDomainError(400, "INVALID_REQUEST", "server name/url are required")
            auth = (server or {}).get("auth") or {}
            auth_type = str(auth.get("type") or "none")
            auth_token = auth.get("token")
            if auth_type not in {"none", "bearer", "api_key"}:
                raise AgentDomainError(400, "INVALID_REQUEST", "invalid auth.type")
            if auth_type in {"bearer", "api_key"} and not auth_token:
                raise AgentDomainError(400, "INVALID_REQUEST", "auth.token is required")
            filter_tools = (server or {}).get("tool_filter") or ["search_records", "calculate_optimization_rate"]
            tools = [str(item) for item in filter_tools]
            total_tools += len(tools)
            normalized.append(
                {
                    "name": name,
                    "url": url,
                    "enabled": bool((server or {}).get("enabled", True)),
                    "tools": tools,
                    "status": "CONNECTED",
                    "auth": {"type": auth_type, "token": auth_token} if auth_type != "none" else {"type": "none"},
                }
            )
        self._mcp_by_tenant[tenant_id] = {"servers": normalized}
        self.store.upsert_mcp(tenant_id, self._mcp_by_tenant[tenant_id])
        return {
            "tenant_id": tenant_id,
            "servers_count": len(normalized),
            "total_tools_available": total_tools,
            "servers": [
                {"name": item["name"], "url": item["url"], "status": item["status"], "tools_count": len(item["tools"])}
                for item in normalized
            ],
        }

    def list_mcp_tools(self, tenant_id: str) -> dict[str, Any]:
        servers = self._mcp_bucket(tenant_id).get("servers", [])
        tools = []
        for server in servers:
            if not server.get("enabled", True):
                continue
            for tool in server.get("tools", []):
                tools.append({"tool_name": tool, "server_name": server["name"]})
        return {"tools": tools, "total": len(tools)}

    def execute_tool(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        tool_name = str(payload.get("tool_name") or "").strip()
        if not tool_name:
            raise AgentDomainError(400, "MCP_TOOL_NOT_FOUND", "tool_name is required")
        server_name = payload.get("server_name")
        servers = self._mcp_bucket(tenant_id).get("servers", [])
        target = None
        for server in servers:
            if server_name and server["name"] != server_name:
                continue
            if tool_name in server.get("tools", []):
                target = server
                break
        if server_name and not any(s["name"] == server_name for s in servers):
            raise AgentDomainError(404, "MCP_SERVER_NOT_FOUND", "server not found")
        if not target:
            raise AgentDomainError(404, "MCP_TOOL_NOT_FOUND", "tool not found")
        url = str(target.get("url") or "").strip()
        if url:
            return self._execute_tool_external(url, tool_name, payload.get("parameters", {}), target.get("auth"))
        return {
            "tool_name": tool_name,
            "server": target["name"],
            "result": {"ok": True, "echo": payload.get("parameters", {})},
            "execution_time_ms": 32,
            "cached": False,
        }

    def complete(self, _tenant_id: str, payload: dict[str, Any], vision: bool = False) -> dict[str, Any]:
        prompt = str(payload.get("prompt") or payload.get("message") or "").strip()
        if not prompt:
            raise AgentDomainError(400, "INVALID_REQUEST", "prompt is required")
        if settings.LLM_COMPLETION_URL:
            return self._complete_external(prompt=prompt, payload=payload, vision=vision)
        model = "gpt-4o-mini" if vision else "gpt-4o"
        return {
            "response": f"[{model}] {prompt[:120]}",
            "usage": {"model": model, "prompt_tokens": max(1, len(prompt) // 4), "completion_tokens": 64},
        }

    def chat(self, _tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        message = str(payload.get("message") or "").strip()
        if not message:
            raise AgentDomainError(400, "INVALID_REQUEST", "message is required")
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        case_id = context.get("case_id")
        tool_query = "SELECT count(*) FROM records"
        if case_id:
            tool_query = f"SELECT count(*) FROM records WHERE case_id = '{case_id}'"
        return {
            "response": f"요청을 처리했습니다: {message[:100]}",
            "tools_used": ["search_records"] if context else [],
            "confidence": 0.95,
            "sources": [{"type": "database", "query": tool_query}] if context else [],
            "usage": {"model": "gpt-4o", "prompt_tokens": 128, "completion_tokens": 64},
        }

    def chat_stream(self, _tenant_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        message = str(payload.get("message") or "").strip()
        if not message:
            raise AgentDomainError(400, "INVALID_REQUEST", "message is required")
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        result = self.chat(_tenant_id, payload)
        events = [{"type": "thinking", "content": "요청을 분석 중입니다."}]
        if context:
            events.extend(
                [
                    {"type": "tool_call", "tool": "search_records", "input": context},
                    {"type": "tool_result", "tool": "search_records", "output": {"count": 1}},
                ]
            )
        events.append({"type": "response", "content": result["response"]})
        events.append(
            {
                "type": "done",
                "total_tokens": result["usage"]["prompt_tokens"] + result["usage"]["completion_tokens"],
                "model": result["usage"]["model"],
            }
        )
        return events

    def list_knowledge(self, tenant_id: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        items = list(self._knowledge_bucket(tenant_id).values())
        items.sort(key=lambda item: item["created_at"], reverse=True)
        safe_limit = min(max(limit, 1), 100)
        safe_offset = max(offset, 0)
        page = items[safe_offset : safe_offset + safe_limit]
        return {"data": page, "total": len(items)}

    def delete_knowledge(self, tenant_id: str, knowledge_id: str) -> dict[str, Any]:
        bucket = self._knowledge_bucket(tenant_id)
        if knowledge_id not in bucket:
            raise AgentDomainError(404, "KNOWLEDGE_NOT_FOUND", "knowledge not found")
        del bucket[knowledge_id]
        self.store.delete_knowledge(tenant_id, knowledge_id)
        return {"deleted": True, "id": knowledge_id}

    def _execute_tool_external(
        self,
        server_url: str,
        tool_name: str,
        parameters: dict[str, Any],
        auth: dict[str, Any] | None,
    ) -> dict[str, Any]:
        endpoint = f"{server_url.rstrip('/')}{settings.MCP_EXECUTE_PATH}"
        headers = {}
        auth_type = str((auth or {}).get("type") or "none")
        token = (auth or {}).get("token")
        if auth_type == "bearer" and token:
            headers["Authorization"] = f"Bearer {token}"
        if auth_type == "api_key" and token:
            headers["X-API-Key"] = str(token)

        started = datetime.now(timezone.utc)
        try:
            resp = httpx.post(
                endpoint,
                json={"tool_name": tool_name, "parameters": parameters},
                headers=headers,
                timeout=settings.MCP_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise AgentDomainError(408, "AGENT_TIMEOUT", "MCP tool execution timed out") from exc
        except httpx.RequestError as exc:
            raise AgentDomainError(503, "MCP_SERVER_UNAVAILABLE", f"cannot connect MCP server: {exc}") from exc

        if resp.status_code >= 500:
            raise AgentDomainError(503, "MCP_SERVER_UNAVAILABLE", "MCP server error")
        if resp.status_code >= 400:
            raise AgentDomainError(404, "MCP_TOOL_NOT_FOUND", "tool execution failed")
        data = resp.json() if resp.content else {}
        elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return {
            "tool_name": tool_name,
            "server": server_url,
            "result": data.get("result", data),
            "execution_time_ms": max(1, elapsed),
            "cached": bool(data.get("cached", False)),
        }

    def _complete_external(self, prompt: str, payload: dict[str, Any], vision: bool) -> dict[str, Any]:
        headers = {}
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
        req = {
            "prompt": prompt,
            "vision": vision,
            "model": payload.get("model") or (settings.DEFAULT_LLM_MODEL if not vision else "gpt-4o-mini"),
            "temperature": payload.get("temperature", 0.0),
            "max_tokens": payload.get("max_tokens", 1024),
        }
        try:
            resp = httpx.post(
                settings.LLM_COMPLETION_URL,
                json=req,
                headers=headers,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            raise AgentDomainError(408, "AGENT_TIMEOUT", "LLM response timeout") from exc
        except httpx.RequestError as exc:
            raise AgentDomainError(502, "LLM_PROVIDER_ERROR", f"LLM provider request failed: {exc}") from exc

        if resp.status_code >= 500:
            raise AgentDomainError(502, "LLM_PROVIDER_ERROR", "LLM provider server error")
        if resp.status_code >= 400:
            raise AgentDomainError(400, "INVALID_REQUEST", "LLM request rejected")
        data = resp.json() if resp.content else {}
        return {
            "response": data.get("response") or data.get("text") or "",
            "usage": data.get(
                "usage",
                {
                    "model": req["model"],
                    "prompt_tokens": max(1, len(prompt) // 4),
                    "completion_tokens": max(1, len(str(data.get("response") or "")) // 4),
                },
            ),
        }


agent_service = AgentService()
