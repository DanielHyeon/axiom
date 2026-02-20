# LLM 팩토리 패턴

## 이 문서가 답하는 질문

- LLM 프로바이더 추상화는 어떻게 구현되는가?
- 어떤 LLM 프로바이더를 지원하는가?
- 프로바이더 교체/추가 시 어떻게 해야 하는가?
- LLM 호출 시 에러 처리와 폴백은 어떻게 동작하는가?

<!-- affects: 03_backend -->
<!-- requires-update: 08_operations/deployment.md -->

---

## 1. 팩토리 패턴 개요

`llm_factory.py`(213줄)는 다양한 LLM 프로바이더(OpenAI, Google, 호환 API)를 통일된 인터페이스로 추상화한다.

```
┌──────────────────────────────────────────────────────┐
│  LLM Factory                                          │
│                                                        │
│  ┌──────────────┐                                     │
│  │ LLMFactory   │  create(provider, model) → LLMClient│
│  └──────┬───────┘                                     │
│         │                                              │
│    ┌────┼────────────┬──────────────┐                 │
│    ▼    ▼            ▼              ▼                 │
│  ┌────────┐ ┌──────────┐ ┌──────────────────┐       │
│  │OpenAI  │ │ Google   │ │ Compatible       │       │
│  │Client  │ │ Client   │ │ Client           │       │
│  │GPT-4o  │ │ Gemini   │ │ (OpenAI API 호환)│       │
│  └────────┘ └──────────┘ └──────────────────┘       │
│                                                        │
│  공통 인터페이스:                                      │
│  - generate(prompt, temperature, max_tokens) -> str   │
│  - embed(text) -> list[float]                          │
│  - stream(prompt) -> AsyncGenerator[str]               │
└──────────────────────────────────────────────────────┘
```

---

## 2. 프로바이더 추상화

### 2.1 기본 인터페이스

```python
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    """LLM 클라이언트 기본 인터페이스."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict | None = None
    ) -> str:
        """텍스트 생성."""
        pass

    @abstractmethod
    async def embed(
        self,
        text: str,
        model: str | None = None
    ) -> list[float]:
        """텍스트 임베딩."""
        pass

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1
    ) -> AsyncGenerator[str, None]:
        """스트리밍 생성."""
        pass
```

### 2.2 OpenAI 클라이언트

```python
class OpenAIClient(BaseLLMClient):
    """OpenAI API 클라이언트 (GPT-4o, GPT-4o-mini 등)."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: dict | None = None
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        return response.choices[0].message.content

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        model = model or "text-embedding-3-small"
        response = await self._client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
```

### 2.3 Google 클라이언트

```python
class GoogleClient(BaseLLMClient):
    """Google Generative AI 클라이언트 (Gemini 등)."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model)

    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self._model.generate_content_async(prompt)
        return response.text
```

### 2.4 호환 클라이언트

```python
class CompatibleClient(BaseLLMClient):
    """OpenAI API 호환 클라이언트 (vLLM, Ollama, LiteLLM 등)."""

    def __init__(self, base_url: str, api_key: str, model: str):
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self._model = model

    # OpenAI와 동일한 구현, base_url만 다름
```

---

## 3. 팩토리 메서드

```python
class LLMFactory:
    """LLM 클라이언트 팩토리."""

    _registry: dict[str, type[BaseLLMClient]] = {
        "openai": OpenAIClient,
        "google": GoogleClient,
        "compatible": CompatibleClient,
    }

    @classmethod
    def create(cls, config: OracleSettings) -> BaseLLMClient:
        """설정에 따라 적절한 LLM 클라이언트 생성."""
        provider = config.llm_provider
        if provider not in cls._registry:
            raise ValueError(f"Unknown LLM provider: {provider}")

        client_class = cls._registry[provider]

        if provider == "openai":
            return client_class(
                api_key=config.llm_api_key,
                model=config.llm_model
            )
        elif provider == "google":
            return client_class(
                api_key=config.llm_api_key,
                model=config.llm_model
            )
        elif provider == "compatible":
            return client_class(
                base_url=config.llm_base_url,
                api_key=config.llm_api_key,
                model=config.llm_model
            )

    @classmethod
    def register(cls, name: str, client_class: type[BaseLLMClient]):
        """커스텀 프로바이더 등록."""
        cls._registry[name] = client_class
```

---

## 4. 용도별 LLM 사용

Oracle 내에서 LLM은 여러 용도로 사용되며, 각 용도별 설정이 다를 수 있다.

| 용도 | 모델 | Temperature | Max Tokens |
|------|------|-------------|------------|
| SQL 생성 | gpt-4o | 0.1 | 4096 |
| HyDE 생성 | gpt-4o-mini | 0.3 | 1024 |
| 의도 분류 | gpt-4o-mini | 0.1 | 512 |
| 품질 심사 | gpt-4o | 0.3~0.7 | 1024 |
| 시각화 추천 | gpt-4o-mini | 0.1 | 512 |
| 결과 요약 | gpt-4o-mini | 0.3 | 1024 |
| 값 매핑 추출 | gpt-4o | 0.1 | 2048 |

### 4.1 모델 선택 기준

```
정확도 중요 (SQL 생성, 품질 심사, 값 매핑) → gpt-4o
속도/비용 우선 (HyDE, 의도 분류, 요약)     → gpt-4o-mini
```

---

## 5. 에러 처리와 재시도

```python
class LLMClientWithRetry:
    """재시도 로직이 포함된 LLM 클라이언트 래퍼."""

    def __init__(
        self,
        client: BaseLLMClient,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self._client = client
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def generate(self, prompt: str, **kwargs) -> str:
        last_error = None
        for attempt in range(self._max_retries):
            try:
                return await self._client.generate(prompt, **kwargs)
            except RateLimitError:
                # Rate limit: 지수 백오프
                delay = self._retry_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                last_error = "Rate limit exceeded"
            except APIConnectionError:
                # 네트워크 에러: 재시도
                await asyncio.sleep(self._retry_delay)
                last_error = "API connection failed"
            except APIError as e:
                # 서버 에러 (5xx): 재시도
                if e.status_code >= 500:
                    await asyncio.sleep(self._retry_delay)
                    last_error = str(e)
                else:
                    raise LLMUnavailableError(str(e))

        raise LLMUnavailableError(
            f"LLM 호출 실패 ({self._max_retries}회 재시도 후): {last_error}"
        )
```

### 5.1 재시도 대상

| 에러 유형 | 재시도 여부 | 전략 |
|----------|-----------|------|
| Rate Limit (429) | Yes | 지수 백오프 (1s, 2s, 4s) |
| Server Error (5xx) | Yes | 고정 간격 (1s) |
| Connection Error | Yes | 고정 간격 (1s) |
| Invalid Request (4xx) | No | 즉시 예외 발생 |
| Authentication Error | No | 즉시 예외 발생 |

---

## 6. 비용 추적

```python
class UsageTracker:
    """LLM 사용량 추적."""

    async def track(
        self,
        provider: str,
        model: str,
        purpose: str,  # sql_generate, quality_judge, etc.
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int
    ):
        """
        사용량을 메트릭으로 기록.
        - 프로바이더/모델별 토큰 사용량
        - 용도별 비용 추적
        - 지연시간 모니터링
        """
```

---

## 금지 사항

- LLM 클라이언트를 코어 모듈에서 직접 생성하지 않음 (팩토리를 통해서만)
- API 키를 코드에 하드코딩하지 않음 (환경 변수 필수)
- LLM 응답을 검증 없이 SQL 실행에 전달하지 않음

## 관련 문서

- [05_llm/prompt-engineering.md](./prompt-engineering.md): 프롬프트 설계
- [08_operations/deployment.md](../08_operations/deployment.md): API 키 설정
- [99_decisions/ADR-001-langchain-sql.md](../99_decisions/ADR-001-langchain-sql.md): LangChain 선택
