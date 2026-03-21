"""LLM 클라이언트 -- OpenAI GPT 호출 래퍼.

OLAP Studio의 AI 기능(큐브 생성, NL2SQL, DDL 생성)에서 공통으로 사용한다.
API 키가 없으면 graceful하게 실패한다.
"""
from __future__ import annotations

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# LLM 사용 가능 여부 -- API 키가 설정되어 있을 때만 활성화
LLM_AVAILABLE = bool(settings.OPENAI_API_KEY)

# 모듈 수준 싱글턴 -- 매 호출마다 AsyncOpenAI를 생성하지 않고 재사용
_client = None


def _get_client():
    """AsyncOpenAI 싱글턴을 지연 초기화하여 반환한다."""
    global _client
    if _client is None:
        from openai import AsyncOpenAI
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


async def generate_text(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> str:
    """LLM으로 텍스트를 생성한다.

    Args:
        system_prompt: 시스템 역할 지시문
        user_prompt: 사용자 질문/요청
        model: 사용할 모델 (None이면 settings.OPENAI_MODEL)
        max_tokens: 최대 생성 토큰 수
        temperature: 생성 다양성 (0.0 = 결정적, 1.0 = 창의적)

    Returns:
        생성된 텍스트. API 키 미설정 또는 오류 시 빈 문자열.
    """
    if not LLM_AVAILABLE:
        logger.warning("llm_unavailable", reason="OPENAI_API_KEY 미설정")
        return ""

    resolved_model = model or settings.OPENAI_MODEL

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        result = response.choices[0].message.content or ""
        token_count = response.usage.total_tokens if response.usage else 0
        logger.info(
            "llm_generated",
            model=resolved_model,
            tokens=token_count,
            result_length=len(result),
        )
        return result.strip()

    except ImportError:
        logger.error(
            "llm_import_failed",
            hint="openai 패키지가 설치되지 않았습니다. pip install openai 실행 필요",
        )
        return ""
    except Exception as e:  # noqa: BLE001 – LLM 장애가 서비스 전체를 중단시키지 않도록
        logger.error("llm_generation_failed", error=str(e), model=resolved_model)
        return ""
