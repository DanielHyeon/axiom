# LLMOps & 모델 포트폴리오 정책

<!-- affects: all-services, operations, llm -->
<!-- requires-update: 08_operations/deployment.md, 08_operations/configuration.md -->

## 이 문서가 답하는 질문

- Axiom 플랫폼 전체의 LLM 모델 포트폴리오는 어떻게 구성되는가?
- Primary/Fallback 모델 정책은 무엇인가?
- 서비스(노드)별 모델 매핑표는 어떻게 되는가?
- 모델 변경(교체) 절차는 어떻게 진행하는가?
- 모델 서빙 아키텍처와 장애 대응은 어떻게 동작하는가?
- LLM 비용 예산과 모니터링은 어떻게 관리하는가?

---

## 1. LLMOps 개요

### 1.1 Axiom LLM 레이어 아키텍처

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Axiom LLM Operations                             │
│                                                                          │
│  ┌─ 관측 계층 (Observability) ──────────────────────────────────────┐   │
│  │  LangSmith Tracing │ Prometheus Metrics │ Cost Dashboard          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─ 정책 계층 (Policy) ────────────────────────────────────────────┐   │
│  │  Token Budget │ Rate Limit │ Circuit Breaker │ Fallback Router    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─ 추상화 계층 (Abstraction) ─────────────────────────────────────┐   │
│  │                                                                    │   │
│  │  Core LLMFactory          Oracle LLMFactory       Vision/Synapse  │   │
│  │  (LangChain 기반)         (직접 API 클라이언트)   (LangChain)     │   │
│  │                                                                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─ 프로바이더 계층 (Provider) ────────────────────────────────────┐   │
│  │                                                                    │   │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌────────────────┐  │   │
│  │  │ OpenAI   │  │ Anthropic │  │ Google   │  │ Self-hosted    │  │   │
│  │  │ GPT-4o   │  │ Claude    │  │ Gemini   │  │ Ollama/vLLM   │  │   │
│  │  │ GPT-4o-  │  │ Sonnet 4  │  │ 2.0 Flash│  │ Llama/Mistral │  │   │
│  │  │ mini     │  │           │  │          │  │               │  │   │
│  │  └──────────┘  └───────────┘  └──────────┘  └────────────────┘  │   │
│  │                                                                    │   │
│  │  ┌──────────────────────────────┐                                 │   │
│  │  │ Embedding Models             │                                 │   │
│  │  │ text-embedding-3-small (OAI) │                                 │   │
│  │  │ embedding-001 (Google)       │                                 │   │
│  │  └──────────────────────────────┘                                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 설계 원칙

```
[원칙] 모든 LLM 호출은 LLMFactory를 통해서만 수행한다 (직접 API 호출 금지).
[원칙] 프론트엔드(Canvas)는 절대 LLM API를 직접 호출하지 않는다.
[원칙] 모든 LLM 호출은 토큰 사용량과 비용을 기록한다.
[원칙] 모델 교체는 코드 변경 없이 환경 변수만으로 가능해야 한다.
[원칙] Production 환경은 반드시 Primary + Fallback 모델을 설정한다.
```

---

## 2. 모델 포트폴리오

### 2.1 지원 모델 카탈로그

| 프로바이더 | 모델 | 용도 | 입력 비용 (1M tok) | 출력 비용 (1M tok) | 지연 시간 | 컨텍스트 |
|-----------|------|------|-------------------|-------------------|----------|---------|
| **OpenAI** | gpt-4o | 정확도 중심 범용 | $5.00 | $15.00 | 2-5초 | 128K |
| **OpenAI** | gpt-4o-mini | 속도/비용 중심 | $0.15 | $0.60 | 1-2초 | 128K |
| **Anthropic** | claude-sonnet-4 | 복잡 추론, Fallback | $3.00 | $15.00 | 3-8초 | 200K |
| **Google** | gemini-2.0-flash | 초저비용, 고속 | $0.075 | $0.30 | 1-3초 | 1M |
| **Ollama** | llama3.2 | 로컬 개발/테스트 | 무료 | 무료 | 가변 | 128K |
| **Compatible** | vLLM/LiteLLM 호스팅 | 자체 호스팅 | 인프라 비용 | 인프라 비용 | 가변 | 가변 |

#### 임베딩 모델

| 프로바이더 | 모델 | 차원 | 비용 (1M tok) | 용도 |
|-----------|------|------|-------------|------|
| **OpenAI** | text-embedding-3-small | 1536 | $0.02 | Primary (모든 서비스) |
| **Google** | embedding-001 | 768 | $0.00 (무료 티어) | Fallback / 개발 |

### 2.2 Primary / Fallback 정책

```
┌─ 모델 라우팅 정책 ──────────────────────────────────────────────────┐
│                                                                       │
│  요청 ──→ Primary 모델 ──→ 성공 ──→ 응답 반환                       │
│              │                                                        │
│              ├── 실패 (429/5xx/Timeout)                               │
│              │         │                                              │
│              │         ▼                                              │
│              │    3회 재시도 (Exponential Backoff: 1s, 2s, 4s)        │
│              │         │                                              │
│              │         ├── 재시도 성공 ──→ 응답 반환                  │
│              │         │                                              │
│              │         └── 재시도 실패                                │
│              │                  │                                     │
│              │                  ▼                                     │
│              │         Fallback 모델 호출                             │
│              │                  │                                     │
│              │                  ├── 성공 ──→ 응답 반환               │
│              │                  │           (fallback=true 메타데이터)│
│              │                  │                                     │
│              │                  └── 실패 ──→ 에러 반환               │
│              │                               (수동 모드 전환 안내)   │
│              │                                                        │
│              └── 실패 (4xx 비재시도) ──→ 즉시 에러 반환              │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

#### 환경별 Primary / Fallback

| 환경 | Primary | Fallback | 비고 |
|------|---------|----------|------|
| **Local (dev)** | Ollama (llama3.2) | OpenAI (gpt-4o) | 비용 절감, 오프라인 개발 |
| **Staging** | OpenAI (gpt-4o) | — (없음) | 단일 프로바이더로 충분 |
| **Production** | OpenAI (gpt-4o) | Anthropic (claude-sonnet-4) | 이중화 필수 |

---

## 3. 서비스(노드)별 모델 매핑표

### 3.1 전체 매핑 종합표

| 서비스 | 기능(노드) | Primary 모델 | Fallback 모델 | Temp | Max Tokens | 정확도 요구 |
|--------|-----------|-------------|--------------|------|-----------|-----------|
| **Core** | 프로세스 정의 생성 (NL→BPMN) | gpt-4o | claude-sonnet-4 | 0.0 | 4096 | 높음 |
| **Core** | ReAct 에이전트 태스크 실행 | gpt-4o | claude-sonnet-4 | 0.0 | 4096 | 높음 |
| **Core** | 피드백→지식 학습 | gpt-4o | claude-sonnet-4 | 0.0 | 4096 | 높음 |
| **Core** | 문서 구조화 (PDF/HWP) | gpt-4o (Vision) | — | 0.0 | 4096 | 높음 |
| **Core** | BPMN 추출 (업무 매뉴얼) | gpt-4o | claude-sonnet-4 | 0.0 | 4096 | 높음 |
| **Core** | MCP 도구 실행 | gpt-4o | claude-sonnet-4 | 0.0 | 4096 | 높음 |
| **Core** | Saga 보상 결정 | gpt-4o | claude-sonnet-4 | 0.0 | 4096 | 높음 |
| **Core** | 데이터 분류 | gpt-4o | gpt-4o-mini | 0.0 | 4096 | 중간 |
| | | | | | | |
| **Oracle** | SQL 생성 | gpt-4o | claude-sonnet-4 | 0.1 | 4096 | **최고** |
| **Oracle** | HyDE 생성 | gpt-4o-mini | gemini-2.0-flash | 0.3 | 1024 | 낮음 |
| **Oracle** | 의도 분류 | gpt-4o-mini | gemini-2.0-flash | 0.1 | 512 | 중간 |
| **Oracle** | 품질 심사 (Quality Gate) | gpt-4o | claude-sonnet-4 | 0.3~0.7 | 1024 | 높음 |
| **Oracle** | 시각화 추천 | — (규칙 기반) | — | — | — | N/A |
| **Oracle** | 결과 요약 | gpt-4o-mini | gemini-2.0-flash | 0.3 | 1024 | 낮음 |
| **Oracle** | 값 매핑 추출 | gpt-4o | claude-sonnet-4 | 0.1 | 2048 | 높음 |
| **Oracle** | 임베딩 (RAG 검색) | text-embedding-3-small | embedding-001 | — | — | 높음 |
| | | | | | | |
| **Vision** | NL→피벗 파라미터 변환 | gpt-4o | — | 0.0 | 4096 | 높음 |
| **Vision** | 인과관계 설명 생성 | gpt-4o | claude-sonnet-4 | 0.0 | 4096 | 중간 |
| | | | | | | |
| **Synapse** | 개체명 추출 (NER) | gpt-4o (Structured) | — | 0.0 | 4096 | **최고** |
| **Synapse** | 관계 추출 | gpt-4o (Structured) | — | 0.0 | 4096 | **최고** |
| | | | | | | |
| **Weaver** | 메타데이터 설명 보강 | gpt-4o | gpt-4o-mini | 0.1 | 4096 | 중간 |
| **Weaver** | FK 관계 추론 | gpt-4o | gpt-4o-mini | 0.1 | 4096 | 낮음 |

### 3.2 모델 선택 기준

```
정확도 최고 (SQL 생성, NER, 관계 추출)
  → gpt-4o (Structured Output strict: true)
  → Fallback: claude-sonnet-4 (strict 100% 미보장, 제한적 사용)

정확도 높음 (에이전트, BPMN, 품질 심사)
  → gpt-4o
  → Fallback: claude-sonnet-4

속도/비용 우선 (HyDE, 의도 분류, 요약)
  → gpt-4o-mini
  → Fallback: gemini-2.0-flash

임베딩
  → text-embedding-3-small (Primary)
  → embedding-001 (Fallback)

로컬 개발
  → Ollama (llama3.2, mistral)
  → 무료, 오프라인, API 키 불필요
```

### 3.3 Structured Output 의존도 맵

Structured Output `strict: true`를 사용하는 노드는 모델 교체 시 특별한 주의가 필요하다. 이 기능은 현재 OpenAI GPT-4o만 100% 보장한다.

| 서비스 | 노드 | Structured Output | Fallback 제약 |
|--------|------|-------------------|-------------|
| Synapse | NER 추출 | strict: true **필수** | Claude Tool Use ~99% (간헐적 스키마 위반) |
| Synapse | 관계 추출 | strict: true **필수** | 동일 |
| Vision | NL→피벗 파라미터 | json_object 모드 | 대부분 프로바이더 지원 |
| Oracle | SQL 생성 | 텍스트 → SQLGlot 검증 | 모델 독립적 |
| Core | 데이터 분류 | PydanticOutputParser | 파서가 보완 |

```
[결정] Synapse NER/관계 추출은 GPT-4o에서만 운영한다.
[결정] Claude가 Structured Output 100% 보장 기능을 제공하면 재평가한다.
[결정] 그 외 노드는 Primary/Fallback 이중화를 적용한다.
```

---

## 4. 모델 서빙 아키텍처

### 4.1 LLMFactory 패턴 (서비스별)

```
┌─ Core LLMFactory ──────────────────┐  ┌─ Oracle LLMFactory ──────────────┐
│ langchain_openai.ChatOpenAI        │  │ OpenAIClient (AsyncOpenAI)       │
│ langchain_anthropic.ChatAnthropic  │  │ GoogleClient (genai)             │
│ langchain_google_genai.ChatGoogleAI│  │ CompatibleClient (vLLM/Ollama)   │
│ langchain_community.ChatOllama     │  │                                   │
│                                     │  │ 공통 인터페이스:                  │
│ LangChain 통합 → LangGraph 호환   │  │ generate() / embed() / stream()  │
└─────────────────────────────────────┘  └───────────────────────────────────┘

┌─ Vision/Synapse ──────────────────┐
│ langchain_openai.ChatOpenAI 직접  │
│ (settings.OPENAI_MODEL 참조)      │
└────────────────────────────────────┘
```

### 4.2 환경 변수 구조

#### Core 서비스

```bash
# Primary LLM
DEFAULT_LLM_PROVIDER=openai              # openai | anthropic | google | ollama
DEFAULT_LLM_MODEL=gpt-4o                 # 모델명
OPENAI_API_KEY=sk-...

# Fallback LLM (Production 전용)
FALLBACK_LLM_PROVIDER=anthropic
FALLBACK_LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...

# Embedding
DEFAULT_EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=sk-...                     # 공유

# Local 개발
OLLAMA_BASE_URL=http://localhost:11434

# 관측성
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=axiom-core
```

#### Oracle 서비스

```bash
ORACLE_LLM_PROVIDER=openai               # openai | google | compatible
ORACLE_LLM_MODEL=gpt-4o
ORACLE_LLM_API_KEY=sk-...
ORACLE_LLM_BASE_URL=                      # compatible 프로바이더용

ORACLE_EMBEDDING_PROVIDER=openai
ORACLE_EMBEDDING_MODEL=text-embedding-3-small

ORACLE_SQL_TIMEOUT=30
ORACLE_JUDGE_ROUNDS=2                     # 품질 심사 라운드
ORACLE_CONF_THRESHOLD=0.90                # 캐시 승인 임계값
```

#### Vision/Synapse 서비스

```bash
OPENAI_API_KEY=sk-...                     # GPT-4o 직접 사용
OPENAI_MODEL=gpt-4o                       # 모델 선택
```

### 4.3 토큰 예산 & Rate Limit 관리

```
┌─ 토큰 예산 정책 ─────────────────────────────────────────────────────┐
│                                                                       │
│  테넌트당 일일 한도: 1,000,000 토큰 (기본값)                        │
│                                                                       │
│  ┌─ 사용량 단계 ─────────────────────────────────────────────────┐  │
│  │                                                                │  │
│  │  0% ─────── 80% ──────── 100%                                 │  │
│  │  │  정상 운영  │  경고 발생  │  LLM 차단 (MANUAL 모드 전환)  │  │
│  │                                                                │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  GPT-4o Rate Limit (Tier 4):                                         │
│  - RPM: 10,000  │  TPM: 2,000,000                                   │
│                                                                       │
│  Synapse 동시 호출 제한: Semaphore(3)                                │
│  Oracle 동시 호출 제한: 설정 가능 (기본 5)                           │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 5. 모델 변경 절차

### 5.1 모델 변경 유형

| 유형 | 예시 | 위험도 | 절차 |
|------|------|--------|------|
| **마이너 업데이트** | gpt-4o-2024-05-13 → gpt-4o-2024-08-06 | 낮음 | Staging 테스트 → Prod 적용 |
| **동일 프로바이더 모델 교체** | gpt-4o → gpt-4o-mini (비용 최적화) | 중간 | 벤치마크 → A/B 테스트 → 단계적 전환 |
| **프로바이더 전환** | OpenAI → Anthropic | 높음 | 전체 파이프라인 검증 → 카나리 배포 |
| **자체 호스팅 전환** | OpenAI → vLLM(Llama) | 최고 | 인프라 준비 → 벤치마크 → 병렬 운영 |

### 5.2 모델 변경 프로세스

```
┌─ 모델 변경 프로세스 ──────────────────────────────────────────────────┐
│                                                                        │
│  Phase 1: 평가 (1-2일)                                                │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ 1. 변경 사유 문서화 (비용 절감? 성능 개선? 장애 대응?)          │ │
│  │ 2. 대상 노드 식별 (섹션 3.1 매핑표 참조)                       │ │
│  │ 3. Structured Output 의존도 확인 (섹션 3.3 참조)                │ │
│  │ 4. 프롬프트 호환성 확인 (프로바이더별 시스템 프롬프트 차이)     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  Phase 2: 벤치마크 (2-3일)                                            │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ 1. 테스트 데이터셋 준비 (노드별 최소 50건)                      │ │
│  │ 2. 현재 모델 기준 성능 측정 (정확도, 지연시간, 비용)            │ │
│  │ 3. 새 모델 동일 데이터셋 실행                                   │ │
│  │ 4. 비교 리포트 작성                                              │ │
│  │                                                                    │ │
│  │  합격 기준:                                                       │ │
│  │  - 정확도: 기존 대비 95% 이상 유지                               │ │
│  │  - 지연시간: P95 < 15초                                          │ │
│  │  - Structured Output 파싱 성공률: 100% (strict 의존 노드)        │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  Phase 3: Staging 검증 (1-2일)                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ 1. Staging 환경 변수 업데이트                                    │ │
│  │ 2. 통합 테스트 실행                                              │ │
│  │ 3. E2E 시나리오 검증 (HITL 포함)                                │ │
│  │ 4. LangSmith에서 trace 비교                                     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  Phase 4: Production 배포 (1일)                                       │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ 1. 카나리 배포 (10% 트래픽)                                     │ │
│  │ 2. 30분 관찰 → 에러율, 지연시간, 토큰 비용 모니터링             │ │
│  │ 3. 이상 없으면 50% → 100% 단계적 확대                           │ │
│  │ 4. 24시간 안정성 확인 후 완료 선언                               │ │
│  │                                                                    │ │
│  │  롤백 트리거:                                                     │ │
│  │  - 에러율 > 10% (5분간)                                          │ │
│  │  - P95 지연시간 > 30초                                           │ │
│  │  - Structured Output 파싱 실패 1건이라도 발생 (strict 노드)      │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
│  Phase 5: 롤백 (즉시)                                                 │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │ 1. 환경 변수를 이전 모델로 복원                                  │ │
│  │ 2. 서비스 재시작 (K8s ConfigMap 업데이트 → Rolling Restart)      │ │
│  │ 3. 롤백 사유 문서화                                              │ │
│  │                                                                    │ │
│  │  롤백 시간 목표: < 5분 (환경 변수 변경 + Pod 재시작)             │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.3 모델 변경이 코드 변경 없이 가능한 이유

```python
# 모든 서비스의 LLMFactory가 환경 변수로 모델을 결정
#
# Core:
#   DEFAULT_LLM_PROVIDER=openai   →  DEFAULT_LLM_PROVIDER=anthropic
#   DEFAULT_LLM_MODEL=gpt-4o     →  DEFAULT_LLM_MODEL=claude-sonnet-4-20250514
#
# Oracle:
#   ORACLE_LLM_PROVIDER=openai   →  ORACLE_LLM_PROVIDER=google
#   ORACLE_LLM_MODEL=gpt-4o      →  ORACLE_LLM_MODEL=gemini-2.0-flash
#
# K8s ConfigMap 업데이트 → Rolling Restart 로 무중단 전환 가능

# 단, 아래 경우는 코드 변경이 필요할 수 있다:
# - Structured Output strict 모드 의존 노드의 프로바이더 전환
# - 프롬프트 형식이 프로바이더별로 달라지는 경우 (시스템 프롬프트 위치 등)
# - 새로운 프로바이더 추가 시 LLMFactory에 클래스 등록 필요
```

### 5.4 프롬프트 버전 관리

모델 변경 시 프롬프트 호환성을 보장하기 위해 버전 관리를 적용한다.

```python
# Synapse 예시: 추출 결과에 모델/프롬프트 버전 포함
PROMPT_VERSIONS = {
    "ner_v1": {"version": "1.0.0", "model": "gpt-4o", "hash": "abc123"},
    "relation_v1": {"version": "1.0.0", "model": "gpt-4o", "hash": "def456"},
}

# API 응답에 메타데이터 포함
{
    "extraction_metadata": {
        "ner_prompt_version": "1.0.0",
        "relation_prompt_version": "1.0.0",
        "model": "gpt-4o-2024-05-13",
        "timestamp": "2026-02-20T10:00:00Z"
    }
}
```

---

## 6. 장애 대응

### 6.1 Circuit Breaker 정책

| 서비스 | 조건 | 차단 시간 | 복구 |
|--------|------|----------|------|
| **Core** | 3회 연속 실패 | 30초 | Half-open (1건 시도) |
| **Oracle** | 3회 연속 실패 | 30초 | Half-open |
| **Vision** | 5회 연속 실패 | 30초 | Half-open |
| **Synapse** | Rate Limit 도달 | Retry-After 헤더 | 자동 |
| **Weaver** | LLM 실패 | 건너뛰기 (non-blocking) | 다음 배치에서 재시도 |

### 6.2 서비스별 Graceful Degradation

```
┌─ LLM 장애 시 서비스별 Graceful Degradation ──────────────────────────┐
│                                                                        │
│  Core (에이전트)                                                       │
│  ├── LLM 타임아웃 → 3회 재시도 → Workitem을 TODO로 복원 + 알림      │
│  ├── LLM 파싱 실패 → 1회 재시도 (프롬프트 수정) → TODO 복원         │
│  └── 낮은 신뢰도 → SUBMITTED 상태 (HITL 큐) → 사람이 직접 처리      │
│                                                                        │
│  Oracle (NL2SQL)                                                       │
│  ├── LLM 장애 → 503 LLM_UNAVAILABLE 에러 반환                       │
│  ├── SQL 생성 실패 → ReAct 루프 재시도 (최대 5 iterations)           │
│  └── UI: "SQL 직접 입력 모드"로 전환 안내                            │
│                                                                        │
│  Vision (NL→피벗)                                                      │
│  ├── LLM 장애 → "수동 피벗 쿼리 빌더"로 안내                        │
│  ├── 검증 실패 → Node 2로 재시도 (최대 2회)                          │
│  └── Circuit breaker: 5회 연속 실패 시 30초 차단                     │
│                                                                        │
│  Synapse (NER)                                                         │
│  ├── LLM 장애 → 추출 작업 실패 + 재시도 큐 등록                     │
│  └── Rate Limit → Semaphore(3) + 지수 백오프                         │
│                                                                        │
│  Weaver (메타데이터 보강)                                              │
│  ├── LLM 실패 → 해당 테이블 건너뛰기 (description=null 유지)        │
│  ├── 전체 메타데이터 추출은 영향받지 않음 (non-blocking)              │
│  └── 다음 보강 배치에서 재시도                                        │
│                                                                        │
│  Canvas (UI)                                                           │
│  ├── AI 실패 → [다시 시도] 버튼 (최대 2회)                           │
│  ├── NL2SQL 실패 → SQL 직접 입력 모드                                │
│  ├── AI 문서 생성 실패 → 빈 문서 템플릿 제공                        │
│  └── 차트 추천 실패 → 기본 테이블 뷰 표시                           │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 6.3 재시도 정책 종합

| 에러 유형 | 재시도 | 전략 | 적용 서비스 |
|----------|--------|------|-----------|
| Rate Limit (429) | Yes | 지수 백오프 (1s, 2s, 4s) | 전체 |
| Server Error (5xx) | Yes | 고정 간격 (1s) | 전체 |
| Connection Error | Yes | 고정 간격 (1s) | 전체 |
| Invalid Request (4xx) | No | 즉시 예외 | 전체 |
| Auth Error (401/403) | No | 즉시 예외 + 알림 | 전체 |
| Timeout (>30s) | Yes | 최대 3회 | Core, Oracle |
| Streaming 첫 토큰 (>15s) | Yes | 최대 2회 | Oracle (SSE) |

---

## 7. 비용 관리

### 7.1 월간 비용 예측 (Production)

| 서비스 | 노드 | 예상 호출/월 | 모델 | 예상 비용/월 |
|--------|------|------------|------|------------|
| **Core** | 에이전트 실행 | 5,000 | gpt-4o | ~$150 |
| **Core** | 문서 구조화 | 500 | gpt-4o | ~$25 |
| **Oracle** | SQL 생성 | 10,000 | gpt-4o | ~$200 |
| **Oracle** | HyDE/의도/요약 | 30,000 | gpt-4o-mini | ~$15 |
| **Oracle** | 품질 심사 | 10,000 | gpt-4o | ~$100 |
| **Oracle** | 임베딩 | 50,000 | text-embedding-3-small | ~$5 |
| **Vision** | NL→피벗 | 3,000 | gpt-4o | ~$60 |
| **Vision** | 인과관계 설명 | 1,000 | gpt-4o | ~$20 |
| **Synapse** | NER + 관계 추출 | 2,000 | gpt-4o | ~$40 |
| **Weaver** | 메타데이터 보강 | 500 | gpt-4o | ~$10 |
| | | | **합계** | **~$625/월** |

### 7.2 비용 최적화 전략

| 전략 | 적용 대상 | 예상 절감 |
|------|----------|----------|
| gpt-4o → gpt-4o-mini 전환 | HyDE, 의도 분류, 결과 요약 | 90% (해당 노드) |
| 캐시 활용 (동일 쿼리 재사용) | Oracle SQL 생성, Weaver 보강 | 30-50% |
| Gemini 2.0 Flash 활용 | Fallback / 비정확도 중심 노드 | 95% (해당 노드) |
| 프롬프트 토큰 최적화 | 전체 | 10-20% |
| Oracle 품질 심사 gpt-4o-mini 전환 | Quality Gate | 90% (~$100→$10) |
| 배치 처리 (Weaver) | 메타데이터 보강 | 20% (API 호출 횟수 감소) |

### 7.3 비용 알림 정책

```
[결정] 일일 비용 예산: 테넌트당 $30 (기본값, 조정 가능)
[결정] 80% 도달 → Slack 경고 + 관리자 이메일
[결정] 100% 도달 → LLM 호출 차단, MANUAL 모드 전환
[결정] 월간 비용 리포트 자동 생성 (서비스별, 노드별 breakdown)
```

---

## 8. 모니터링 & 관측성

### 8.1 LangSmith 통합

```
┌─ LangSmith 프로젝트 구조 ────────────────────────────────────────────┐
│                                                                        │
│  axiom-core                                                            │
│  ├── agent-execution         (ReAct 에이전트 트레이스)                │
│  ├── document-structuring    (문서 AI 생성 트레이스)                  │
│  └── knowledge-learning      (피드백→학습 트레이스)                   │
│                                                                        │
│  axiom-oracle                                                          │
│  ├── nl2sql-pipeline         (SQL 생성 전체 파이프라인)               │
│  ├── quality-gate            (품질 심사 트레이스)                     │
│  └── embedding               (RAG 검색 트레이스)                     │
│                                                                        │
│  axiom-vision                                                          │
│  ├── nl-to-pivot             (NL→피벗 워크플로우)                    │
│  └── causal-explanation      (인과관계 설명)                          │
│                                                                        │
│  axiom-synapse                                                         │
│  ├── ner-extraction          (개체명 추출)                            │
│  └── relation-extraction     (관계 추출)                              │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Prometheus 메트릭

| 메트릭 | 타입 | 레이블 | 알림 조건 |
|--------|------|--------|----------|
| `llm_request_duration_seconds` | Histogram | service, node, provider, model | P95 > 15초 |
| `llm_request_total` | Counter | service, node, provider, model, status | — |
| `llm_token_usage_total` | Counter | service, node, provider, model, direction(in/out) | 일일 한도 80% |
| `llm_error_rate` | Gauge | service, node, provider | 5분간 10% 초과 |
| `llm_cost_daily_usd` | Gauge | service, tenant | 예산 80% 도달 |
| `llm_circuit_breaker_state` | Gauge | service, node | open 상태 진입 |
| `llm_fallback_total` | Counter | service, node | Fallback 호출 발생 |

### 8.3 알림 대시보드

```
┌─ LLMOps Dashboard ──────────────────────────────────────────────────┐
│                                                                      │
│  ┌─ 실시간 상태 ────────────────────────────────────────────────┐  │
│  │ OpenAI:    ●  정상   │ 지연: 2.1s   │ 에러율: 0.2%          │  │
│  │ Anthropic: ●  정상   │ 지연: 3.5s   │ 에러율: 0.0%          │  │
│  │ Google:    ●  정상   │ 지연: 1.2s   │ 에러율: 0.1%          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ 오늘 비용 ──────────────────────────────────────────────────┐  │
│  │ Core: $5.20  │ Oracle: $12.40  │ Vision: $2.80  │ 합계: $21.40│ │
│  │ ████████████████████░░░░░░░░░░░░░░░░░░░░ 71% of $30 budget  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ 서비스별 호출 현황 (24h) ──────────────────────────────────┐  │
│  │ Core    │████████████████████        │ 1,247 calls │ $5.20   │  │
│  │ Oracle  │████████████████████████████│ 3,891 calls │ $12.40  │  │
│  │ Vision  │████████████               │   487 calls │ $2.80   │  │
│  │ Synapse │██████                     │   156 calls │ $0.80   │  │
│  │ Weaver  │██                         │    32 calls │ $0.20   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 9. 향후 로드맵

### 9.1 단기 (MVP ~ 3개월)

- [x] LLMFactory 패턴 구현 (Core, Oracle)
- [ ] 환경 변수 기반 모델 전환 구현
- [ ] LangSmith 트레이싱 통합
- [ ] 기본 비용 추적 (UsageTracker)
- [ ] Circuit Breaker 구현

### 9.2 중기 (3~6개월)

- [ ] Production Fallback 라우터 구현 (Primary→Fallback 자동 전환)
- [ ] Prometheus 메트릭 연동
- [ ] LLMOps 대시보드 구축
- [ ] A/B 테스트 프레임워크 (모델 비교 자동화)
- [ ] Oracle 품질 심사 gpt-4o-mini 전환 검증

### 9.3 장기 (6개월+)

- [ ] 자체 호스팅 모델 평가 (vLLM + Llama 계열)
- [ ] 모델 라우팅 자동화 (비용/정확도 트레이드오프 기반 동적 선택)
- [ ] 한국어 비즈니스 도메인 Fine-tuned 모델 평가
- [ ] Multi-region LLM 엔드포인트 (글로벌 배포 시)
- [ ] FinOps 대시보드 (LLM 비용 최적화 추천 엔진)

---

## 결정 사항 (Decisions)

- GPT-4o를 Axiom 전체 Primary 모델로 통일
  - 근거: Structured Output 100% 보장, 한국어 비즈니스 NER F1 ~0.87, K-AIR 기술 스택 일관성
  - ADR 참조: Synapse ADR-003 (GPT-4o Structured Output 선택)

- Production 환경에서 Anthropic Claude를 Fallback으로 운영
  - 근거: OpenAI 장애 시 서비스 연속성 보장, Claude의 긴 컨텍스트(200K) 활용
  - Structured Output strict 의존 노드(Synapse NER)는 Fallback 미적용

- 모델 변경은 코드 변경 없이 환경 변수만으로 수행
  - 근거: LLMFactory 추상화로 프로바이더 독립적 인터페이스 보장
  - 롤백 시간 목표: 5분 이내

- 일일 토큰 예산 정책 적용 (테넌트당 기본 1M 토큰/일)
  - 근거: 예측 불가능한 LLM 비용 폭증 방지
  - 한도 초과 시 MANUAL 모드로 전환 (AI 기능 비활성화, 수동 조작 가능)

---

## 관련 문서

| 문서 | 위치 | 설명 |
|------|------|------|
| Core LLM 통합 | `services/core/docs/05_llm/llm-integration.md` | Core LLMFactory, 재시도 정책 |
| Core 에이전트 아키텍처 | `services/core/docs/05_llm/agent-architecture.md` | ReAct 에이전트, HITL 3단계 |
| Oracle LLM 팩토리 | `services/oracle/docs/05_llm/llm-factory.md` | Oracle LLMFactory, 용도별 모델 |
| Oracle ReAct 에이전트 | `services/oracle/docs/05_llm/react-agent.md` | NL2SQL 8단계 파이프라인 |
| Oracle 품질 게이트 ADR | `services/oracle/docs/99_decisions/ADR-005-quality-gate.md` | N-Round LLM 품질 심사 |
| Vision NL→피벗 | `services/vision/docs/05_llm/nl-to-pivot.md` | LangGraph 5노드 워크플로우 |
| Synapse GPT-4o ADR | `services/synapse/docs/99_decisions/ADR-003-gpt4o-extraction.md` | GPT-4o Structured Output 선택 |
| Weaver 메타데이터 보강 | `services/weaver/docs/05_llm/metadata-enrichment.md` | LLM 기반 설명 생성 |
| Canvas AI 기능 | `apps/canvas/docs/05_llm/ai-features.md` | UI AI 패턴, HITL, 실패 처리 |
| Core 배포 | `services/core/docs/08_operations/deployment.md` | 환경별 LLM 구성 |
| Core 설정 | `services/core/docs/08_operations/configuration.md` | 환경 변수 전체 목록 |
| 성능·모니터링 종합 | `services/core/docs/08_operations/performance-monitoring.md` | SLO/SLA, LLM 메트릭, 알림 규칙, Grafana LLM Operations 대시보드 |
| 로깅 체계 | `services/core/docs/08_operations/logging-system.md` | LLM 호출 로그 표준, AI 로그 분석 (gpt-4o 사용), 감사 로그 |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 — 전 서비스 LLMOps 종합 |
