# Axiom Core - MCP 프로토콜 통합

## 이 문서가 답하는 질문

- MCP(Model Context Protocol)는 무엇이고 왜 사용하는가?
- SafeToolLoader의 보안 정책과 도구 필터링은 어떻게 동작하는가?
- MCP 서버를 추가/관리하는 절차는 무엇인가?

<!-- affects: backend, security -->
<!-- requires-update: 02_api/agent-api.md -->

---

## 1. MCP 개요

### 1.1 MCP 선택 근거

```
[결정] LLM 에이전트의 도구(Tool) 관리를 MCP 프로토콜로 표준화한다.
[근거] K-AIR는 MCP를 전면 채택하여 에이전트 도구를 MCP 서버로 격리하고 있다.
       이를 통해:
       1. 도구 교체 시 에이전트 코드 변경 불필요
       2. 도구별 보안 정책 적용 (위험한 도구 차단)
       3. 테넌트별 도구 구성 가능
       4. 도구의 동적 발견 (서버 등록만으로 새 도구 사용)
```

### 1.2 MCP 서버 구성

```
Axiom Core (MCP 클라이언트)
     |
     +---> axiom-skills (MCP 서버) - 비즈니스 프로세스 전용 도구
     |       ├── calculate_optimization_rate
     |       ├── classify_data
     |       ├── validate_data_quality
     |       └── generate_optimization_schedule
     |
     +---> axiom-tools (MCP 서버) - 범용 도구
     |       ├── search_database
     |       ├── read_document
     |       ├── send_email
     |       └── create_pdf
     |
     +---> (테넌트 커스텀 MCP 서버)
             ├── (테넌트별 커스텀 도구)
             └── ...
```

---

## 2. SafeToolLoader 보안 정책

### 2.1 차단 도구 목록

```python
BLOCKED_TOOLS = [
    "shell_execute",       # 운영체제 명령 실행
    "file_delete",         # 파일 삭제
    "file_write",          # 임의 파일 쓰기
    "db_drop",             # DB/테이블 드롭
    "db_truncate",         # 테이블 전체 삭제
    "network_scan",        # 네트워크 스캔
    "credential_access",   # 인증 정보 접근
]
```

### 2.2 테넌트별 도구 격리

```
[결정] 각 테넌트는 자신이 등록한 MCP 서버의 도구만 사용할 수 있다.
[결정] axiom-skills, axiom-tools는 모든 테넌트가 공유하는 기본 서버이다.
[결정] 테넌트 커스텀 MCP 서버는 해당 테넌트만 접근 가능하다.
[금지] 한 테넌트의 MCP 서버를 다른 테넌트가 호출하는 것은 금지한다.
```

---

## 3. MCP 클라이언트 구현

```python
# app/orchestrator/mcp_client.py

from fastmcp import FastMCP
from langchain_core.tools import StructuredTool

class MCPClient:
    """MCP 프로토콜 클라이언트"""

    @staticmethod
    async def list_tools(server_url: str) -> list:
        """MCP 서버에서 사용 가능한 도구 목록 조회"""
        async with FastMCP(server_url) as client:
            tools = await client.list_tools()
            return tools

    @staticmethod
    def create_langchain_tool(
        tool_def: dict,
        source_server: str,
    ) -> StructuredTool:
        """MCP 도구 정의를 LangChain Tool로 변환"""
        async def _execute(**kwargs):
            async with FastMCP(tool_def["server_url"]) as client:
                result = await client.call_tool(
                    tool_def["name"],
                    arguments=kwargs,
                )
                return result

        return StructuredTool.from_function(
            func=_execute,
            name=tool_def["name"],
            description=f"[{source_server}] {tool_def['description']}",
            args_schema=tool_def.get("input_schema"),
            coroutine=_execute,
        )
```

---

## 4. 도구 우선순위 결정 근거

```
Skills (100) > DMN (80) > Mem0 (60) > MCP (40) > General (20)

이유:
  - Skills: 도메인 전문가가 검증한 도구 -> 가장 정확
  - DMN: 형식화된 규칙 -> 결정적 결과
  - Mem0: 과거 경험 -> 참고용
  - MCP: 범용 도구 -> 폴백
  - General: 기본 도구 -> 최후 수단
```

---

## 근거

- K-AIR process-gpt-agent-utils-main (SafeToolLoader)
- K-AIR process-gpt-langchain-react-main (MCP 클라이언트 통합)
- K-AIR 역설계 보고서 섹션 8.3 (MCP 통합)
