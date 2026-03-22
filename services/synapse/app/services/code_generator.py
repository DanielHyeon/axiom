"""LLM 기반 코드 생성 서비스.

KAIR ontology_behavior.py의 generate-code 엔드포인트를 서비스 레이어로 분리.
사용자 프롬프트에서 지정된 언어의 코드를 LLM으로 생성한다.
"""
from __future__ import annotations

from typing import Any, Callable, Coroutine

import structlog

logger = structlog.get_logger(__name__)


def _extract_code_block(text: str) -> str:
    """LLM 응답에서 코드 블록을 추출한다.

    ```python ... ``` 또는 ``` ... ``` 형태의 마크다운 코드 블록에서
    순수 코드만 추출한다. 코드 블록이 없으면 원본 텍스트를 반환한다.
    """
    text = text.strip()
    if not text.startswith("```"):
        return text

    lines = text.split("\n")
    # 첫 줄이 ```python 또는 ```javascript 등이면 제거
    if lines[0].startswith("```"):
        lines = lines[1:]
    # 마지막 줄이 ``` 이면 제거
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


# LLM 생성 함수 타입 (app.core.llm_factory.generate_text 호환)
LLMGenerateFn = Callable[..., Coroutine[Any, Any, str]]


class CodeGenerator:
    """LLM을 사용하여 다양한 언어의 코드를 생성한다."""

    def __init__(self, llm_generate_fn: LLMGenerateFn | None = None):
        self._llm_fn = llm_generate_fn

    async def generate(
        self,
        prompt: str,
        language: str = "python",
        temperature: float = 0.5,
        max_output_tokens: int = 4000,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """사용자 프롬프트로부터 코드를 생성한다.

        Args:
            prompt: 코드 생성 요청 설명
            language: 생성 언어 (python, javascript, sql 등)
            temperature: 생성 온도 (0.0~1.0, 높을수록 창의적)
            max_output_tokens: 최대 출력 토큰 수
            context: 추가 컨텍스트 (데이터 스키마, 사용 가능한 필드 등)

        Returns:
            { success, code, language } dict
        """
        if not self._llm_fn:
            return {
                "success": False,
                "error": "LLM 생성 함수가 설정되지 않았습니다.",
                "language": language,
            }

        system_prompt = self._build_system_prompt(language, context)

        try:
            raw = await self._llm_fn(
                system_prompt=system_prompt,
                user_prompt=prompt,
                purpose="generate_code",
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                use_light=True,
            )
            code = _extract_code_block(raw)
            logger.info(
                "code_generated",
                language=language,
                code_length=len(code),
                prompt_length=len(prompt),
            )
            return {"success": True, "code": code, "language": language}
        except Exception as e:
            logger.error("code_generation_failed", error=str(e), language=language)
            return {
                "success": False,
                "error": f"코드 생성 오류: {e}",
                "language": language,
            }

    @staticmethod
    def _build_system_prompt(language: str, context: dict | None = None) -> str:
        """언어별 시스템 프롬프트를 생성한다."""
        base = (
            f"You are a {language} code generator. "
            "Generate clean, well-commented code. "
            "Output only the code without markdown code blocks or explanations."
        )
        if context:
            schema_info = context.get("schema")
            if schema_info:
                base += f"\n\nAvailable data schema:\n{schema_info}"
            fields = context.get("fields")
            if fields:
                base += f"\n\nAvailable fields: {', '.join(fields)}"
        return base

    async def generate_behavior_code(
        self,
        behavior_name: str,
        input_fields: list[str],
        output_field: str,
        description: str = "",
        language: str = "python",
    ) -> dict[str, Any]:
        """BehaviorModel 정의에 맞는 실행 코드를 자동 생성한다.

        BehaviorModel의 READS_FIELD/PREDICTS_FIELD 링크 정보를 기반으로
        입력 필드를 읽어 출력 필드를 예측하는 코드를 생성한다.

        Args:
            behavior_name: BehaviorModel 이름
            input_fields: 입력 필드 목록 (READS_FIELD)
            output_field: 출력 필드 (PREDICTS_FIELD)
            description: 행위 설명 (자연어)
            language: 생성 언어

        Returns:
            { success, code, language } dict
        """
        prompt = f"""BehaviorModel '{behavior_name}' 실행 코드를 생성하세요.

## 행위 설명
{description or '(없음)'}

## 입력 필드 (data 딕셔너리에서 읽기)
{', '.join(input_fields) if input_fields else '(없음)'}

## 출력 필드 (result 변수에 할당)
{output_field or '(없음)'}

## 코드 요구사항
1. `data` 딕셔너리에서 입력 필드를 안전하게 읽기 (KeyError 방지)
2. 비즈니스 로직 처리 후 `result` 변수에 결과 할당
3. 숫자 연산 시 None/빈값 처리
4. 간단한 한글 주석 추가
"""
        context = {"fields": input_fields}
        return await self.generate(
            prompt=prompt,
            language=language,
            temperature=0.3,
            context=context,
        )
