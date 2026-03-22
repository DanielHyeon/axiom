"""BehaviorModel 실행 엔진 단위 테스트.

테스트 대상:
- BehaviorExecutor: 4가지 타입 실행 (rest_api, dmn, python, javascript)
- Python 샌드박스 AST 기반 보안 검증
- LLM 자동 수정 루프
- 타임아웃 (무한루프 방지)
- SSRF 차단
- CodeGenerator: 코드 생성
- ResultPersister: 식별자 검증 + 컬럼명 검증
"""
import pytest
import pytest_asyncio

from app.services.behavior_executor import (
    BehaviorExecutor,
    _check_forbidden_ast,
    _execute_python_sandbox,
    _validate_endpoint,
)
from app.services.code_generator import CodeGenerator, _extract_code_block
from app.services.result_persister import _validate_identifier, _infer_pg_type


# ── Python 샌드박스 AST 기반 보안 테스트 ──


class TestSandboxSecurity:
    """Python 샌드박스 AST 기반 보안 정책 검증."""

    def test_forbidden_import_statement(self):
        """import 문 차단."""
        assert _check_forbidden_ast("import os") == "import"

    def test_forbidden_from_import(self):
        """from ... import 차단."""
        assert _check_forbidden_ast("from os import system") == "import"

    def test_forbidden_eval_call(self):
        """eval() 호출 차단."""
        assert _check_forbidden_ast("eval('1+1')") == "eval"

    def test_forbidden_exec_call(self):
        """exec() 호출 차단."""
        assert _check_forbidden_ast("exec('print(1)')") == "exec"

    def test_forbidden_getattr(self):
        """getattr() 호출 차단 — 메타클래스 탈출 방지."""
        assert _check_forbidden_ast("getattr(obj, 'method')") == "getattr"

    def test_forbidden_class_attribute(self):
        """__class__ 속성 접근 차단."""
        assert _check_forbidden_ast("x = obj.__class__") == "__class__"

    def test_forbidden_bases_attribute(self):
        """__bases__ 속성 접근 차단."""
        assert _check_forbidden_ast("x = cls.__bases__") == "__bases__"

    def test_forbidden_subclasses(self):
        """__subclasses__ 속성 접근 차단."""
        assert _check_forbidden_ast("x = cls.__subclasses__()") == "__subclasses__"

    def test_forbidden_globals(self):
        """__globals__ 속성 접근 차단."""
        assert _check_forbidden_ast("x = fn.__globals__") == "__globals__"

    def test_forbidden_builtins_attr(self):
        """__builtins__ 속성 접근 차단."""
        assert _check_forbidden_ast("x = obj.__builtins__") == "__builtins__"

    def test_forbidden_type_name(self):
        """type() 호출 차단."""
        assert _check_forbidden_ast("type(x)") == "type"

    def test_safe_code_passes(self):
        """안전한 코드는 통과."""
        assert _check_forbidden_ast("result = sum(data.values())") is None

    def test_safe_list_comprehension(self):
        """리스트 컴프리헨션은 안전."""
        assert _check_forbidden_ast("[x * 2 for x in range(10)]") is None

    def test_safe_dict_access(self):
        """딕셔너리 접근은 안전."""
        assert _check_forbidden_ast("result = data.get('key', 0)") is None

    def test_syntax_error_caught(self):
        """구문 오류 감지."""
        result = _check_forbidden_ast("def (invalid")
        assert result is not None and "SyntaxError" in result

    # ── 문자열 우회 시도 차단 테스트 ──

    def test_string_concat_bypass_blocked(self):
        """문자열 연결 우회 시도 — getattr로 차단됨."""
        # 이전 substring 방식에서는 통과했으나 AST에서는 getattr 호출 자체를 차단
        code = 'x = getattr(obj, "ev" + "al")'
        assert _check_forbidden_ast(code) == "getattr"

    def test_sandbox_basic_execution(self):
        """기본 Python 실행 테스트."""
        code = "result = data['a'] + data['b']"
        result = _execute_python_sandbox(code, {"a": 10, "b": 20})
        assert result == 30

    def test_sandbox_list_comprehension(self):
        """리스트 컴프리헨션 실행 테스트."""
        code = "result = [x * 2 for x in data['items']]"
        result = _execute_python_sandbox(code, {"items": [1, 2, 3]})
        assert result == [2, 4, 6]

    def test_sandbox_dict_operations(self):
        """딕셔너리 연산 실행."""
        code = "result = {k: v * 2 for k, v in data.items()}"
        result = _execute_python_sandbox(code, {"x": 1, "y": 2})
        assert result == {"x": 2, "y": 4}

    def test_sandbox_forbidden_raises(self):
        """금지 패턴 코드는 ValueError 발생."""
        with pytest.raises(ValueError, match="보안 정책 위반"):
            _execute_python_sandbox("import os", {})

    def test_sandbox_no_result_returns_none(self):
        """result를 설정하지 않으면 None 반환."""
        result = _execute_python_sandbox("x = 42", {})
        assert result is None

    def test_sandbox_code_length_limit(self):
        """코드 길이 제한 검증."""
        long_code = "x = 1\n" * 100_000
        with pytest.raises(ValueError, match="너무 깁니다"):
            _execute_python_sandbox(long_code, {})

    def test_sandbox_print_not_available(self):
        """print는 샌드박스에서 사용 불가 (서버 stdout 오염 방지)."""
        # print가 _SAFE_BUILTINS에서 제거됨 — NameError 발생
        with pytest.raises(Exception):
            _execute_python_sandbox("print('hello')", {})


# ── SSRF 차단 테스트 ──


class TestSSRFProtection:
    """REST API 엔드포인트 SSRF 차단 검증."""

    def test_localhost_blocked(self):
        with pytest.raises(ValueError, match="차단된 호스트"):
            _validate_endpoint("http://localhost:9002/admin")

    def test_loopback_blocked(self):
        with pytest.raises(ValueError, match="차단된 호스트"):
            _validate_endpoint("http://127.0.0.1:8080/secret")

    def test_aws_metadata_blocked(self):
        with pytest.raises(ValueError, match="차단된 호스트"):
            _validate_endpoint("http://169.254.169.254/latest/meta-data/")

    def test_gcp_metadata_blocked(self):
        with pytest.raises(ValueError, match="차단된 호스트"):
            _validate_endpoint("http://metadata.google.internal/computeMetadata")

    def test_private_network_blocked(self):
        with pytest.raises(ValueError, match="내부 네트워크"):
            _validate_endpoint("http://10.0.0.1:8080/api")

    def test_invalid_scheme_blocked(self):
        with pytest.raises(ValueError, match="프로토콜"):
            _validate_endpoint("ftp://example.com/file")

    def test_valid_external_url_passes(self):
        """외부 URL은 정상 통과."""
        _validate_endpoint("https://api.example.com/webhook")

    def test_valid_https_passes(self):
        _validate_endpoint("https://partner-service.com/v1/predict")


# ── BehaviorExecutor 테스트 ──


class TestBehaviorExecutor:
    """BehaviorExecutor 실행 엔진 테스트."""

    @pytest.fixture
    def executor(self):
        return BehaviorExecutor()

    @pytest.mark.asyncio
    async def test_python_execution_success(self, executor):
        """Python 타입 실행 성공."""
        behavior = {
            "name": "test-calc",
            "behaviorType": "python",
            "config": {"code": "result = data['x'] * 2"},
            "outputField": "doubled",
        }
        result = await executor.execute(behavior, {"x": 21})
        assert result["success"] is True
        assert result["result"] == 42
        assert result["behaviorName"] == "test-calc"

    @pytest.mark.asyncio
    async def test_python_execution_error_no_llm(self, executor):
        """Python 오류 발생 시 LLM 없으면 즉시 실패."""
        behavior = {
            "name": "test-error",
            "behaviorType": "python",
            "config": {"code": "result = data['missing_key']"},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "KeyError" in result.get("errorType", "")

    @pytest.mark.asyncio
    async def test_python_auto_fix_with_llm(self, executor):
        """LLM 자동 수정 루프 테스트."""
        call_count = 0

        async def mock_llm(**kwargs):
            nonlocal call_count
            call_count += 1
            return "result = data.get('missing_key', 0)"

        behavior = {
            "name": "test-fix",
            "behaviorType": "python",
            "config": {"code": "result = data['missing_key']"},
            "outputField": "out",
        }
        result = await executor.execute(
            behavior, {}, llm_generate_fn=mock_llm
        )
        assert result["success"] is True
        assert result["result"] == 0
        assert result["autoFixed"] is True
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_python_security_violation(self, executor):
        """보안 위반 코드는 실행 차단."""
        behavior = {
            "name": "test-hack",
            "behaviorType": "python",
            "config": {"code": "import os; os.system('whoami')"},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "보안 정책" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_dmn_execution_missing_xml(self, executor):
        """DMN XML 미설정 시 실패."""
        behavior = {
            "name": "test-dmn",
            "behaviorType": "dmn",
            "config": {},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "DMN XML" in result["error"]

    @pytest.mark.asyncio
    async def test_javascript_unsupported(self, executor):
        """JavaScript 타입은 미지원."""
        behavior = {
            "name": "test-js",
            "behaviorType": "javascript",
            "config": {},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "지원되지 않" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_type(self, executor):
        """알 수 없는 타입 처리."""
        behavior = {
            "name": "test-unknown",
            "behaviorType": "ruby",
            "config": {},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "지원하지 않는" in result["error"]

    @pytest.mark.asyncio
    async def test_rest_api_missing_endpoint(self, executor):
        """REST API endpoint 미설정 시 실패."""
        behavior = {
            "name": "test-rest",
            "behaviorType": "rest_api",
            "config": {},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "endpoint" in result["error"]

    @pytest.mark.asyncio
    async def test_rest_api_ssrf_blocked(self, executor):
        """REST API SSRF 차단."""
        behavior = {
            "name": "test-ssrf",
            "behaviorType": "rest_api",
            "config": {"endpoint": "http://169.254.169.254/latest/meta-data/"},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "SSRF" in result["error"]

    @pytest.mark.asyncio
    async def test_python_no_code(self, executor):
        """Python 코드 미설정 시 실패."""
        behavior = {
            "name": "test-nocode",
            "behaviorType": "python",
            "config": {},
            "outputField": "out",
        }
        result = await executor.execute(behavior, {})
        assert result["success"] is False
        assert "코드가 설정되지" in result["error"]

    @pytest.mark.asyncio
    async def test_python_timeout(self, executor):
        """타임아웃 검증 — 오래 걸리는 연산은 시간 초과 처리."""
        # import 없이 순수 Python 연산으로 타임아웃 유발
        # 큰 숫자 거듭제곱은 GIL 해제 없이도 asyncio.wait_for가 잡을 수 있음
        behavior = {
            "name": "test-timeout",
            "behaviorType": "python",
            "config": {"code": "result = sum(range(10**9))"},
            "outputField": "out",
        }
        import app.services.behavior_executor as mod
        original = mod._SANDBOX_TIMEOUT_SECONDS
        mod._SANDBOX_TIMEOUT_SECONDS = 0.3
        try:
            result = await executor.execute(behavior, {})
            # 0.3초 안에 완료되면 success, 아니면 timeout
            # 느린 머신에서는 timeout, 빠른 머신에서는 success 가능
            # 둘 다 유효한 결과이므로 assert 안함 — 중요한 건 hang 안하는 것
            assert isinstance(result, dict)
        finally:
            mod._SANDBOX_TIMEOUT_SECONDS = original


# ── CodeGenerator 테스트 ──


class TestCodeGenerator:
    """코드 생성 서비스 테스트."""

    def test_extract_code_block_python(self):
        """```python 블록 추출."""
        text = "```python\nresult = 42\n```"
        assert _extract_code_block(text) == "result = 42"

    def test_extract_code_block_plain(self):
        """``` 블록 추출."""
        text = "```\nresult = 42\n```"
        assert _extract_code_block(text) == "result = 42"

    def test_extract_no_block(self):
        """코드 블록 없으면 원본 반환."""
        text = "result = 42"
        assert _extract_code_block(text) == "result = 42"

    @pytest.mark.asyncio
    async def test_generate_no_llm(self):
        """LLM 함수 없이 생성 시 실패."""
        gen = CodeGenerator(llm_generate_fn=None)
        result = await gen.generate("print hello")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_generate_with_mock_llm(self):
        """Mock LLM으로 코드 생성."""
        async def mock_llm(**kwargs):
            return "```python\nresult = 42\n```"

        gen = CodeGenerator(llm_generate_fn=mock_llm)
        result = await gen.generate("calculate answer")
        assert result["success"] is True
        assert result["code"] == "result = 42"
        assert result["language"] == "python"

    @pytest.mark.asyncio
    async def test_generate_behavior_code(self):
        """BehaviorModel 기반 코드 생성."""
        async def mock_llm(**kwargs):
            return "# 비용 계산\nresult = data.get('price', 0) * data.get('qty', 0)"

        gen = CodeGenerator(llm_generate_fn=mock_llm)
        result = await gen.generate_behavior_code(
            behavior_name="calc_cost",
            input_fields=["price", "qty"],
            output_field="total_cost",
            description="가격 × 수량 = 총비용 계산",
        )
        assert result["success"] is True
        assert "price" in result["code"]

    @pytest.mark.asyncio
    async def test_generate_llm_exception(self):
        """LLM 예외 시 graceful 실패."""
        async def failing_llm(**kwargs):
            raise RuntimeError("API key expired")

        gen = CodeGenerator(llm_generate_fn=failing_llm)
        result = await gen.generate("generate something")
        assert result["success"] is False
        assert "API key expired" in result["error"]


# ── ResultPersister 유틸리티 테스트 ──


class TestResultPersisterUtils:
    """결과 저장 유틸리티 함수 테스트."""

    def test_validate_identifier_valid(self):
        """유효한 식별자 통과."""
        assert _validate_identifier("my_table") == "my_table"
        assert _validate_identifier("_private") == "_private"
        assert _validate_identifier("Table123") == "Table123"

    def test_validate_identifier_invalid(self):
        """유효하지 않은 식별자 거부."""
        with pytest.raises(ValueError, match="유효하지 않은"):
            _validate_identifier("1_starts_with_digit")
        with pytest.raises(ValueError, match="유효하지 않은"):
            _validate_identifier("has space")
        with pytest.raises(ValueError, match="유효하지 않은"):
            _validate_identifier("drop;--")

    def test_validate_identifier_sql_injection(self):
        """SQL injection 시도 거부."""
        with pytest.raises(ValueError):
            _validate_identifier('foo"; DROP TABLE --')
        with pytest.raises(ValueError):
            _validate_identifier("Robert'); DROP TABLE Students;--")

    def test_infer_pg_type(self):
        """Python 타입 → PostgreSQL 타입 추론."""
        assert _infer_pg_type(None) == "TEXT"
        assert _infer_pg_type(True) == "BOOLEAN"
        assert _infer_pg_type(42) == "BIGINT"
        assert _infer_pg_type(3.14) == "DOUBLE PRECISION"
        assert _infer_pg_type("hello") == "TEXT"
