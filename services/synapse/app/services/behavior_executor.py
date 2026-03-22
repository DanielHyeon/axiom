"""BehaviorModel 실행 엔진 — 4가지 타입 지원.

KAIR ontology_behavior.py를 Axiom 패턴으로 이식.
BehaviorModel 노드에 정의된 행위를 실행한다.

지원 타입:
  - rest_api: 외부 HTTP 엔드포인트 호출 (SSRF 차단)
  - dmn: DMN 결정 테이블 실행
  - python: 샌드박스 내 Python 코드 실행 (AST 검증 + LLM 자동 수정 3회 + 타임아웃)
  - javascript: 미지원 (501)
"""
from __future__ import annotations

import ast
import asyncio
import concurrent.futures
import json
import sys
import traceback
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog

from app.services.code_generator import _extract_code_block
from app.services.dmn_engine import (
    execute_decision_table,
    create_table_from_dict,
)

logger = structlog.get_logger(__name__)

# ── 보안: Python 샌드박스 ────────────────────────────────────

# AST 기반 금지 이름 — 문자열 우회(concat, getattr 등) 차단
_FORBIDDEN_NAMES = frozenset({
    "eval", "exec", "compile", "open", "breakpoint",
    "getattr", "setattr", "delattr", "vars", "dir",
    "globals", "locals", "type", "super",
    "__build_class__",
})

# AST 기반 금지 속성 — 메타클래스 체인 탈출 차단
_FORBIDDEN_ATTRS = frozenset({
    "__class__", "__bases__", "__subclasses__", "__import__",
    "__builtins__", "__globals__", "__code__", "__getattribute__",
    "__dict__", "__mro__", "__func__", "__self__",
    "__qualname__", "__module__",
})

# 허용 빌트인 — 안전한 함수만 노출 (print 제외 — 서버 stdout 오염 방지)
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "format": format,
    "int": int, "len": len, "list": list, "map": map, "max": max, "min": min,
    "range": range, "round": round, "set": set, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "zip": zip,
    "isinstance": isinstance, "None": None, "True": True, "False": False,
}

# SSRF 차단 — 내부 네트워크/클라우드 메타데이터 접근 방지
_BLOCKED_HOSTS = frozenset({
    "localhost", "127.0.0.1", "0.0.0.0", "::1",
    "169.254.169.254",  # AWS/GCP 메타데이터
    "metadata.google.internal",
    "100.100.100.200",  # Alibaba 메타데이터
})

# Python 샌드박스 실행 타임아웃 (초)
_SANDBOX_TIMEOUT_SECONDS = 10.0

# 샌드박스 코드 최대 길이 (바이트) — LLM 생성 코드 포함
_MAX_CODE_LENGTH = 50_000


def _check_forbidden_ast(code: str) -> str | None:
    """AST 기반 금지 패턴 검사 — 문자열 우회(concat, getattr) 차단.

    코드를 파싱하여 AST 트리를 순회하며 import 문, 금지 이름,
    금지 속성 접근을 탐지한다. 위반 시 패턴 문자열을 반환한다.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    for node in ast.walk(tree):
        # import / from ... import 차단
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return "import"
        # 금지 이름 호출 차단 (eval, exec, getattr 등)
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            return node.id
        # 금지 속성 접근 차단 (__class__, __bases__ 등)
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_ATTRS:
            return node.attr
    return None


def _execute_python_sandbox(code: str, instance_data: dict) -> Any:
    """샌드박스 내에서 Python 코드를 실행한다.

    AST 기반 보안 검증 후 exec()로 실행한다.
    실행 후 exec_globals["result"] 값을 반환한다.
    코드에 result 변수를 설정하지 않으면 None을 반환한다.
    """
    # 코드 길이 제한
    if len(code) > _MAX_CODE_LENGTH:
        raise ValueError(f"코드가 너무 깁니다 (최대 {_MAX_CODE_LENGTH}바이트)")

    # AST 기반 보안 검증
    violation = _check_forbidden_ast(code)
    if violation:
        raise ValueError(f"보안 정책 위반: '{violation}' 사용 금지")

    exec_globals: dict[str, Any] = {"__builtins__": {}}
    exec_globals.update(_SAFE_BUILTINS)
    exec_globals["data"] = instance_data
    exec_globals["result"] = None

    exec(code, exec_globals, exec_globals)  # noqa: S102 — 의도적 샌드박스 실행

    return exec_globals.get("result")


def _validate_endpoint(url: str) -> None:
    """REST API 엔드포인트 URL을 검증한다 — SSRF 차단."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"허용되지 않는 프로토콜: {parsed.scheme}")
    hostname = (parsed.hostname or "").lower()
    if hostname in _BLOCKED_HOSTS:
        raise ValueError(f"차단된 호스트: {hostname}")
    # 내부 IP 대역 차단 (10.x, 172.16-31.x, 192.168.x)
    if hostname.startswith(("10.", "172.", "192.168.")):
        raise ValueError(f"내부 네트워크 접근 차단: {hostname}")


# ── 실행 엔진 ────────────────────────────────────────────────

class BehaviorExecutor:
    """BehaviorModel 정의에 따라 4가지 타입의 실행을 수행한다."""

    MAX_AUTO_FIX_ATTEMPTS = 3

    async def execute(
        self,
        behavior: dict[str, Any],
        instance_data: dict[str, Any],
        *,
        llm_generate_fn=None,
    ) -> dict[str, Any]:
        """behavior 정의와 입력 데이터로 실행 결과를 반환한다.

        Args:
            behavior: Neo4j에서 조회한 behavior 정보
                      (behaviorType, config, name, outputField 등)
            instance_data: 실행에 전달할 입력 데이터
            llm_generate_fn: LLM 텍스트 생성 함수 (Python 자동 수정용, 선택)

        Returns:
            { success, result, message, ... } dict
        """
        behavior_type = behavior.get("behaviorType", "rest_api")
        config = behavior.get("config", {})
        name = behavior.get("name", "unknown")

        if behavior_type == "rest_api":
            return await self._execute_rest_api(name, config, instance_data)
        elif behavior_type == "dmn":
            return self._execute_dmn(name, config, instance_data, behavior)
        elif behavior_type == "python":
            return await self._execute_python(
                name, config, instance_data, behavior, llm_generate_fn
            )
        elif behavior_type == "javascript":
            return {
                "success": False,
                "behaviorName": name,
                "error": "JavaScript 실행은 아직 지원되지 않습니다.",
                "message": "미지원 타입",
            }
        else:
            return {
                "success": False,
                "behaviorName": name,
                "error": f"지원하지 않는 behavior 타입: {behavior_type}",
                "message": "알 수 없는 타입",
            }

    # ── REST API 실행 (SSRF 차단 포함) ──

    async def _execute_rest_api(
        self, name: str, config: dict, instance_data: dict
    ) -> dict[str, Any]:
        endpoint = config.get("endpoint")
        if not endpoint:
            return {"success": False, "behaviorName": name, "error": "REST API endpoint가 설정되지 않았습니다."}

        # SSRF 차단 — 내부 호스트/클라우드 메타데이터 접근 방지
        try:
            _validate_endpoint(endpoint)
        except ValueError as e:
            return {"success": False, "behaviorName": name, "error": f"SSRF 차단: {e}"}

        method = config.get("method", "POST").upper()
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "POST":
                resp = await client.post(
                    endpoint,
                    json={
                        "behavior_name": name,
                        "instance_data": instance_data,
                        "parameters": config.get("parameters", {}),
                    },
                )
            elif method == "GET":
                resp = await client.get(endpoint, params=instance_data)
            else:
                return {"success": False, "behaviorName": name, "error": f"지원하지 않는 HTTP 메서드: {method}"}

            if resp.status_code != 200:
                return {"success": False, "behaviorName": name, "error": f"HTTP {resp.status_code}: {resp.text}"}

            result_data = resp.json()
            return {
                "success": True,
                "behaviorName": name,
                "result": result_data.get("result", result_data),
                "message": result_data.get("message", "REST API 실행 완료"),
            }

    # ── DMN 실행 ──

    def _execute_dmn(
        self, name: str, config: dict, instance_data: dict, behavior: dict
    ) -> dict[str, Any]:
        dmn_xml = config.get("dmnXml")
        if not dmn_xml:
            return {"success": False, "behaviorName": name, "error": "DMN XML이 설정되지 않았습니다."}

        try:
            table_dict = config.get("decisionTable")
            table = create_table_from_dict(table_dict or config)
            dmn_result = execute_decision_table(table, instance_data)

            return {
                "success": True,
                "behaviorName": name,
                "result": dmn_result,
                "outputField": behavior.get("outputField"),
                "message": "DMN 규칙 실행 완료",
            }
        except Exception as e:
            logger.error("dmn_execution_error", behavior=name, error=str(e))
            return {"success": False, "behaviorName": name, "error": f"DMN 실행 오류: {e}"}

    # ── Python 샌드박스 실행 (AST 검증 + 타임아웃 + LLM 자동 수정) ──

    async def _execute_python(
        self,
        name: str,
        config: dict,
        instance_data: dict,
        behavior: dict,
        llm_generate_fn,
    ) -> dict[str, Any]:
        original_code = config.get("code")
        if not original_code:
            return {"success": False, "behaviorName": name, "error": "Python 코드가 설정되지 않았습니다."}

        current_code = original_code
        attempts: list[dict] = []

        for attempt_idx in range(self.MAX_AUTO_FIX_ATTEMPTS):
            attempt_info: dict[str, Any] = {
                "attempt": attempt_idx + 1,
                "code": current_code,
                "status": "pending",
            }
            try:
                # 타임아웃 적용 — 무한루프 방지 (ThreadPool + asyncio.wait_for)
                exec_result = await self._run_sandbox_with_timeout(
                    current_code, instance_data
                )
                attempt_info["status"] = "success"
                attempt_info["result"] = exec_result
                attempts.append(attempt_info)

                auto_fixed = attempt_idx > 0
                return {
                    "success": True,
                    "behaviorName": name,
                    "result": exec_result,
                    "outputField": behavior.get("outputField"),
                    "message": f"Python 코드 실행 완료"
                    + (f" (자동 수정 {attempt_idx}회)" if auto_fixed else ""),
                    "code": current_code,
                    "originalCode": original_code if auto_fixed else None,
                    "attempts": attempts,
                    "autoFixed": auto_fixed,
                }
            except Exception as exec_err:
                exc_type, _, exc_tb = sys.exc_info()
                error_lineno, error_line = self._extract_error_location(
                    exc_tb, current_code
                )
                error_info = {
                    "error": str(exec_err),
                    "errorType": exc_type.__name__ if exc_type else "Unknown",
                    "errorLine": error_lineno,
                    "errorLineContent": error_line,
                    "traceback": traceback.format_exc(),
                }
                attempt_info["status"] = "error"
                attempt_info["error"] = error_info
                attempts.append(attempt_info)

                logger.warning(
                    "python_sandbox_error",
                    behavior=name,
                    attempt=attempt_idx + 1,
                    error=str(exec_err),
                )

                # LLM 자동 수정 시도 (마지막 시도가 아닐 때만)
                if attempt_idx < self.MAX_AUTO_FIX_ATTEMPTS - 1 and llm_generate_fn:
                    fixed = await self._fix_code_with_llm(
                        llm_generate_fn, current_code, error_info, instance_data
                    )
                    if fixed and fixed != current_code:
                        current_code = fixed
                        continue

                # 모든 시도 실패
                return {
                    "success": False,
                    "behaviorName": name,
                    "error": str(exec_err),
                    "errorType": exc_type.__name__ if exc_type else "Unknown",
                    "code": current_code,
                    "originalCode": original_code,
                    "message": f"Python 실행 오류 (자동 수정 {attempt_idx + 1}회 시도 후 실패)",
                    "attempts": attempts,
                }

        return {"success": False, "behaviorName": name, "error": "실행 실패"}

    @staticmethod
    async def _run_sandbox_with_timeout(
        code: str, instance_data: dict, timeout: float = _SANDBOX_TIMEOUT_SECONDS
    ) -> Any:
        """타임아웃 적용 샌드박스 실행 — 무한루프 방지.

        별도 스레드에서 exec을 실행하고 asyncio.wait_for로 타임아웃을 건다.
        """
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = loop.run_in_executor(
                pool, _execute_python_sandbox, code, instance_data
            )
            try:
                return await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"Python 코드 실행 시간 초과 ({timeout}초)"
                ) from None

    @staticmethod
    def _extract_error_location(exc_tb, code: str) -> tuple[int | None, str | None]:
        """traceback에서 <string> 실행 위치의 라인 번호와 내용을 추출한다."""
        if exc_tb is None:
            return None, None
        tb_list = traceback.extract_tb(exc_tb)
        for frame in tb_list:
            if frame.filename == "<string>":
                code_lines = code.split("\n")
                line_content = (
                    code_lines[frame.lineno - 1]
                    if 0 < frame.lineno <= len(code_lines)
                    else None
                )
                return frame.lineno, line_content
        return None, None

    @staticmethod
    async def _fix_code_with_llm(
        llm_fn, code: str, error_info: dict, instance_data: dict
    ) -> str | None:
        """LLM을 사용하여 오류 코드를 자동 수정한다."""
        prompt = f"""다음 Python 코드에서 오류가 발생했습니다. 오류를 수정해주세요.

## 원본 코드:
```python
{code}
```

## 에러 정보:
- 에러 타입: {error_info.get('errorType')}
- 에러 메시지: {error_info.get('error')}
- 에러 라인: {error_info.get('errorLine')}

## 입력 데이터 (샘플):
{json.dumps(instance_data, ensure_ascii=False, indent=2)[:500]}

## 요구사항:
1. 입력 데이터의 타입을 안전하게 처리
2. 기존 로직 최대한 유지
3. 수정된 전체 Python 코드만 출력 (설명 없이)
"""
        try:
            fixed_code = await llm_fn(
                system_prompt="당신은 Python 코드 오류를 수정하는 전문가입니다. 수정된 코드만 출력하세요.",
                user_prompt=prompt,
                purpose="fix_behavior_code",
                temperature=0.2,
                max_output_tokens=2000,
                use_light=True,
            )
            return _extract_code_block(fixed_code)
        except Exception as e:
            logger.warning("llm_code_fix_failed", error=str(e))
            return None
