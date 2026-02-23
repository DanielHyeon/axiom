import asyncio
from typing import AsyncGenerator, Optional
import structlog

logger = structlog.get_logger()

class BaseLLMClient:
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        raise NotImplementedError

    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        raise NotImplementedError

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1) -> AsyncGenerator[str, None]:
        raise NotImplementedError
        yield ""

class MockLLMClient(BaseLLMClient):
    """Fallback LLM mock for offline pipeline testing without active provider keys."""
    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        logger.info("llm_mock_generate", prompt_snippet=prompt[:20])
        if "quality" in (system_prompt or "").lower() or "심사관" in (system_prompt or "").lower():
            return '{"score": 0.85, "is_complete": true, "feedback": "", "next_question": ""}'
        elif "fix" in prompt.lower() or "수정" in prompt.lower():
            return "SELECT * FROM sales_records LIMIT 1000;"
        return "SELECT * FROM sales_records LIMIT 1000;"

    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """Mock embedding: fixed-dimension vector for pipeline step (e.g. 1536 for text-embedding-3-small)."""
        return [0.0] * 1536

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1) -> AsyncGenerator[str, None]:
        yield "SELECT "
        await asyncio.sleep(0.01)
        yield "* FROM "
        await asyncio.sleep(0.01)
        yield "sales_records LIMIT 1000;"

class LLMClientWithRetry:
    def __init__(self, client: BaseLLMClient, max_retries: int = 3, retry_delay: float = 1.0):
        self._client = client
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def generate(self, prompt: str, **kwargs) -> str:
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return await self._client.generate(prompt, **kwargs)
            except Exception as e:
                last_error = e
                await asyncio.sleep(self._retry_delay)
        raise RuntimeError(f"LLM 호출 실패 ({self._max_retries}회 재시도): {last_error}")

    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return await self._client.embed(text, model=model)
            except Exception as e:
                last_error = e
                await asyncio.sleep(self._retry_delay)
        raise RuntimeError(f"Embedding 호출 실패 ({self._max_retries}회 재시도): {last_error}")

    async def stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        async for chunk in self._client.stream(prompt, **kwargs):
            yield chunk

class LLMFactory:
    _registry = {
        "mock": MockLLMClient
    }

    @classmethod
    def create(cls, provider: str = "mock") -> BaseLLMClient:
        client_class = cls._registry.get(provider, MockLLMClient)
        return LLMClientWithRetry(client_class())

llm_factory = LLMFactory.create()
