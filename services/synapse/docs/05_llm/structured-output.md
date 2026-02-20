# GPT-4o Structured Output 활용

## 이 문서가 답하는 질문

- GPT-4o Structured Output이란 무엇이며 왜 사용하는가?
- Synapse에서 정의한 JSON 스키마는 어떤 것들인가?
- strict 모드의 제약사항과 대응 방법은?
- 비용/성능 최적화 전략은?

<!-- affects: backend, api -->
<!-- requires-update: 03_backend/ner-extractor.md -->

---

## 1. Structured Output 개요

### 1.1 정의

GPT-4o Structured Output은 LLM의 응답이 사전 정의된 JSON 스키마에 **100% 부합**하도록 보장하는 OpenAI 기능이다. `strict: true` 설정 시, 모델이 스키마를 위반하는 출력을 생성하는 것이 원천적으로 불가능하다.

### 1.2 왜 Synapse에서 사용하는가

| 이유 | 설명 |
|------|------|
| **파싱 안정성** | JSON 파싱 실패가 원천 차단됨 |
| **타입 안전성** | enum, number range 등 타입 제약 보장 |
| **신뢰도 필드 보장** | confidence 필드가 항상 0.0-1.0 범위로 반환됨 |
| **파이프라인 안정성** | NER -> 관계추출 -> 매핑 파이프라인에서 중간 단계 실패 방지 |
| **HITL 통합** | 구조화된 결과를 검토 UI에 바로 표시 가능 |

### 1.3 대안 비교 (결정 근거)

| 방식 | 파싱 성공률 | 타입 안전성 | 비용 | 선택 |
|------|-----------|-----------|------|------|
| **Structured Output (strict)** | **100%** | **완전 보장** | 기본 | **채택** |
| JSON Mode | ~95% | 부분 보장 | 기본 | 탈락 (안정성 부족) |
| Function Calling | ~99% | 높음 | 기본 | 탈락 (Structured Output이 더 직관적) |
| 프롬프트 + 파싱 | ~80% | 없음 | 기본 | 탈락 (불안정) |

---

## 2. Synapse에서 정의한 JSON 스키마

### 2.1 NER 추출 스키마

```json
{
  "name": "ner_extraction",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "entities": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "text": {"type": "string"},
            "entity_type": {
              "type": "string",
              "enum": [
                "COMPANY", "PERSON", "DEPARTMENT", "AMOUNT", "DATE",
                "ASSET_TYPE", "PROCESS_STEP", "METRIC", "CONTRACT",
                "FINANCIAL_METRIC", "REGULATION"
              ]
            },
            "normalized_value": {"type": "string"},
            "confidence": {"type": "number"},
            "context": {"type": "string"}
          },
          "required": ["text", "entity_type", "normalized_value", "confidence", "context"],
          "additionalProperties": false
        }
      }
    },
    "required": ["entities"],
    "additionalProperties": false
  }
}
```

### 2.2 관계 추출 스키마

```json
{
  "name": "relation_extraction",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "relations": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "subject": {"type": "string"},
            "subject_type": {"type": "string", "enum": ["COMPANY", "PERSON", "DEPARTMENT", "AMOUNT", "DATE", "ASSET_TYPE", "PROCESS_STEP", "METRIC", "CONTRACT", "FINANCIAL_METRIC", "REGULATION"]},
            "predicate": {"type": "string", "enum": ["INITIATED_PROCESS", "ASSIGNED_TO", "OWNS_ASSET", "HAS_CONTRACT_WITH", "SUPPLIES_TO", "APPOINTED_AS", "DECIDED", "MEASURED_AS", "IMPROVED_BY", "ALLOCATED_TO", "VALUED_AT", "OCCURRED_ON"]},
            "object": {"type": "string"},
            "object_type": {"type": "string", "enum": ["COMPANY", "PERSON", "DEPARTMENT", "AMOUNT", "DATE", "ASSET_TYPE", "PROCESS_STEP", "METRIC", "CONTRACT", "FINANCIAL_METRIC", "REGULATION"]},
            "confidence": {"type": "number"},
            "evidence": {"type": "string"}
          },
          "required": ["subject", "subject_type", "predicate", "object", "object_type", "confidence", "evidence"],
          "additionalProperties": false
        }
      }
    },
    "required": ["relations"],
    "additionalProperties": false
  }
}
```

### 2.3 온톨로지 매핑 스키마

```json
{
  "name": "ontology_mapping",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "mappings": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "entity_text": {"type": "string"},
            "ontology_layer": {"type": "string", "enum": ["resource", "process", "measure", "kpi"]},
            "ontology_type": {"type": "string"},
            "confidence": {"type": "number"},
            "reasoning": {"type": "string"}
          },
          "required": ["entity_text", "ontology_layer", "ontology_type", "confidence", "reasoning"],
          "additionalProperties": false
        }
      }
    },
    "required": ["mappings"],
    "additionalProperties": false
  }
}
```

---

## 3. strict 모드 제약사항

### 3.1 알려진 제약

| 제약 | 영향 | 대응 |
|------|------|------|
| `additionalProperties: false` 필수 | 동적 필드 불가 | 모든 필드를 스키마에 명시 |
| 중첩 깊이 제한 (5단계) | 복잡한 구조 불가 | 구조 평탄화(flatten) |
| enum 값 최대 500개 | 대규모 enum 불가 | 현재 11-12개 수준으로 충분 |
| 재귀적 스키마 불가 | 트리 구조 직접 표현 불가 | 평탄화된 배열로 표현 |
| 첫 요청 시 캐싱 지연 | 첫 호출 1-2초 추가 | 서버 시작 시 워밍업 호출 |

### 3.2 스키마 워밍업

```python
async def warmup_schemas(self):
    """
    Send a minimal warmup request to cache the JSON schema.
    This avoids the 1-2 second penalty on the first real extraction.
    """
    warmup_text = "ABC 제조 주식회사의 2024년 프로세스 분석 보고서"
    try:
        await self.extract_entities(warmup_text, max_entities=1)
        logger.info("schema_warmup_complete", schema="ner_extraction")
    except Exception:
        pass  # Warmup failure is non-critical
```

---

## 4. 비용/성능 최적화

### 4.1 토큰 사용량 추정

| 작업 | 입력 토큰 | 출력 토큰 | 비용/요청 (GPT-4o) |
|------|----------|----------|-------------------|
| NER (800토큰 청크) | ~1,200 | ~800 | ~$0.008 |
| 관계 추출 | ~1,500 | ~600 | ~$0.007 |
| 온톨로지 매핑 | ~800 | ~400 | ~$0.004 |
| **문서 1건 (10청크)** | | | **~$0.19** |

### 4.2 최적화 전략

| 전략 | 절감 효과 | 구현 방법 |
|------|----------|----------|
| 청크 병렬 처리 | 시간 -70% | asyncio.gather + Semaphore(3) |
| 빈 청크 스킵 | 비용 -10-20% | 텍스트 길이 임계값 확인 |
| 캐시 | 비용 -30-50% | 동일 청크 재추출 시 PostgreSQL 캐시 활용 |
| NER+관계 결합 | 비용 -40% | 단일 프롬프트로 개체+관계 동시 추출 (향후 최적화) |

### 4.3 Rate Limit 관리

```python
# GPT-4o rate limits (Tier 4)
# RPM: 10,000, TPM: 2,000,000
# Synapse target: max 3 concurrent requests

SEMAPHORE = asyncio.Semaphore(3)

async def rate_limited_call(self, func, *args, **kwargs):
    async with SEMAPHORE:
        return await func(*args, **kwargs)
```

---

## 5. 프롬프트 버전 관리

### 5.1 버전 관리 전략

```python
PROMPT_VERSIONS = {
    "ner_v1": {
        "version": "1.0.0",
        "created": "2024-06-01",
        "model": "gpt-4o",
        "description": "Initial NER prompt for business process domain"
    },
    "relation_v1": {
        "version": "1.0.0",
        "created": "2024-06-01",
        "model": "gpt-4o",
        "description": "Initial relation extraction prompt"
    }
}
```

### 5.2 결과에 프롬프트 버전 기록

모든 추출 결과에 사용된 프롬프트 버전을 기록하여, 프롬프트 변경 시 영향 범위를 추적한다.

```json
{
  "extraction_metadata": {
    "ner_prompt_version": "1.0.0",
    "relation_prompt_version": "1.0.0",
    "model": "gpt-4o-2024-05-13",
    "timestamp": "2024-06-16T10:00:00Z"
  }
}
```

---

## 금지 규칙

- strict: false로 Structured Output을 사용하지 않는다
- 프롬프트에 JSON 예시를 넣어 출력 형식을 유도하지 않는다 (스키마가 보장)
- 스키마 변경 시 버전을 올리지 않고 배포하지 않는다

## 필수 규칙

- 모든 LLM 호출에 temperature=0.0을 사용한다 (NER/RE는 결정론적)
- 스키마에 `additionalProperties: false`를 항상 포함한다
- 추출 결과에 프롬프트 버전과 모델 정보를 기록한다

---

## 근거 문서

- ADR-003: GPT-4o Structured Output 선택 (`99_decisions/ADR-003-gpt4o-extraction.md`)
- `03_backend/ner-extractor.md` (NER 엔진 구현)
