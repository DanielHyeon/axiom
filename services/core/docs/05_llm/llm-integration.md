# Axiom Core - LLM 통합 아키텍처

## 이 문서가 답하는 질문

- LLM 프로바이더는 어떻게 통합되고 전환 가능한가?
- ClientFactory 패턴은 어떻게 동작하는가?
- LLM 호출의 에러 처리, 타임아웃, 재시도 정책은 무엇인가?
- LLM 비용과 모니터링은 어떻게 관리하는가?

<!-- affects: backend, agent -->
<!-- requires-update: 05_llm/agent-architecture.md -->

---

## 1. LLM 프로바이더 통합

### 1.1 ClientFactory 패턴

K-AIR의 process-gpt-completion-main에서 이식하는 핵심 패턴. 프로바이더에 독립적인 LLM 호출 인터페이스를 제공한다.

```python
# app/core/llm_factory.py
# K-AIR ClientFactory에서 이식

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from app.core.config import settings

class LLMFactory:
    """LLM 프로바이더 팩토리"""

    @staticmethod
    def create(
        provider: str = None,
        model: str = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        streaming: bool = False,
    ):
        provider = provider or settings.DEFAULT_LLM_PROVIDER
        model = model or settings.DEFAULT_LLM_MODEL

        match provider:
            case "openai":
                return ChatOpenAI(
                    model=model,                    # gpt-4o, gpt-4o-mini
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,
                    timeout=30,
                    max_retries=3,
                )
            case "anthropic":
                return ChatAnthropic(
                    model=model,                    # claude-sonnet-4-20250514
                    temperature=temperature,
                    max_tokens=max_tokens,
                    streaming=streaming,
                    timeout=30,
                    max_retries=3,
                )
            case "google":
                return ChatGoogleGenerativeAI(
                    model=model,                    # gemini-2.0-flash
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            case "ollama":
                return ChatOllama(
                    model=model,                    # llama3.2, mistral
                    temperature=temperature,
                    base_url=settings.OLLAMA_BASE_URL,
                )
            case _:
                raise ValueError(f"Unknown LLM provider: {provider}")

    @staticmethod
    def create_embeddings(provider: str = None):
        """임베딩 모델 생성"""
        provider = provider or settings.DEFAULT_EMBEDDING_PROVIDER
        match provider:
            case "openai":
                from langchain_openai import OpenAIEmbeddings
                return OpenAIEmbeddings(model="text-embedding-3-small")
            case "google":
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                return GoogleGenerativeAIEmbeddings(model="models/embedding-001")
```

### 1.2 프로바이더별 특성

| 프로바이더 | 모델 | 주 용도 | 비용(1M 토큰) | 지연 시간 |
|-----------|------|---------|-------------|----------|
| **OpenAI** | gpt-4o | 범용, Structured Output | $5 / $15 | 2-5초 |
| **OpenAI** | gpt-4o-mini | 간단한 분류/요약 | $0.15 / $0.60 | 1-2초 |
| **Anthropic** | claude-sonnet-4 | 복잡한 추론, 긴 문맥 | $3 / $15 | 3-8초 |
| **Google** | gemini-2.0-flash | 빠른 응답, 비용 효율 | $0.075 / $0.30 | 1-3초 |
| **Ollama** | llama3.2 | 로컬 개발/테스트 | 무료 | 가변 |

---

## 2. LLM 호출 정책

### 2.1 타임아웃과 재시도

```
[결정] 모든 LLM 호출에 30초 타임아웃을 적용한다.
[결정] 재시도는 최대 3회, Exponential Backoff (1초, 2초, 4초)를 적용한다.
[결정] 3회 재시도 후에도 실패하면 AgentExecutionError를 발생시킨다.
[결정] 스트리밍 응답은 첫 토큰 도착까지 15초 타임아웃을 적용한다.
```

### 2.2 Structured Output

```python
# LLM 출력의 구조적 검증 - Pydantic 모델 강제

from pydantic import BaseModel
from langchain_core.output_parsers import PydanticOutputParser

class DataClassification(BaseModel):
    """데이터 분류 결과"""
    data_type: str           # "일반", "핵심", "우선", "보조"
    confidence: float        # 0.0 ~ 1.0
    reasoning: str           # 분류 근거
    impact_area: str | None  # 영향 영역 (핵심 데이터인 경우)

# 사용
llm = LLMFactory.create(provider="openai", model="gpt-4o")
parser = PydanticOutputParser(pydantic_object=DataClassification)

result = await llm.ainvoke(
    f"다음 데이터를 분류하세요: ...\n{parser.get_format_instructions()}"
)
classification = parser.parse(result.content)
```

### 2.3 비용 관리

```
[결정] 모든 LLM 호출의 토큰 사용량을 기록한다.
[결정] 테넌트당 일일 토큰 한도를 설정한다 (기본 1M 토큰/일).
[결정] 한도 80% 도달 시 경고, 100% 도달 시 LLM 호출 차단 (MANUAL 모드로 전환).
```

---

## 3. 모니터링

### 3.1 LangSmith 통합

```python
# app/core/config.py
LANGCHAIN_TRACING_V2 = True
LANGCHAIN_API_KEY = "ls-..."
LANGCHAIN_PROJECT = "axiom-core"
```

### 3.2 추적 메트릭

| 메트릭 | 설명 | 알림 조건 |
|--------|------|----------|
| `llm_request_duration` | LLM 호출 소요 시간 | P95 > 15초 |
| `llm_token_usage` | 입력/출력 토큰 수 | 일일 한도 80% 도달 |
| `llm_error_rate` | LLM 호출 에러율 | 5분간 10% 초과 |
| `llm_cost_daily` | 일일 LLM 비용 | 예산 80% 도달 |

---

## 근거

- K-AIR process-gpt-completion-main (ClientFactory, LangChain 통합)
- K-AIR 역설계 보고서 섹션 7 (AI/LLM 아키텍처)
