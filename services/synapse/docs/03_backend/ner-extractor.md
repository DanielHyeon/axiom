# NER + 관계 추출 엔진

## 이 문서가 답하는 질문

- GPT-4o Structured Output으로 NER을 어떻게 수행하는가?
- 관계 추출의 프롬프트 설계와 JSON 스키마는?
- 신뢰도 점수는 어떻게 산출/활용되는가?
- 비즈니스 프로세스 도메인 특화 NER의 고려사항은?

<!-- affects: llm, api -->
<!-- requires-update: 05_llm/entity-extraction.md, 05_llm/relation-extraction.md -->

---

## 1. NER 엔진 구현

### 1.1 아키텍처

```python
# app/extraction/ner_extractor.py
import asyncio
from openai import AsyncOpenAI
import structlog

logger = structlog.get_logger()


class NERExtractor:
    """
    Named Entity Recognition using GPT-4o Structured Output.
    Extracts business process domain entities from Korean business documents.
    """

    ENTITY_TYPES = [
        "COMPANY",           # Company names, legal entity names
        "PERSON",            # Person names (analysts, managers, representatives)
        "DEPARTMENT",        # Department/division names
        "AMOUNT",            # Monetary amounts
        "DATE",              # Dates
        "ASSET_TYPE",        # Asset classification
        "PROCESS_STEP",      # Business process steps
        "METRIC",            # Business metrics and KPI information
        "CONTRACT",          # Contract information
        "FINANCIAL_METRIC",  # Financial metrics
        "REGULATION",        # Regulatory references
    ]

    def __init__(self, llm_client: AsyncOpenAI, model: str = "gpt-4o"):
        self.client = llm_client
        self.model = model

    async def extract_entities(
        self,
        text: str,
        target_types: list[str] | None = None,
        max_entities: int = 50
    ) -> dict:
        """
        Extract named entities from a text chunk.

        Args:
            text: Input text chunk (typically 800 tokens)
            target_types: Entity types to extract (default: all)
            max_entities: Maximum entities per chunk

        Returns:
            Dict with entities list, each containing:
            - text, entity_type, normalized_value, confidence, context
        """
        types = target_types or self.ENTITY_TYPES

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._build_system_prompt(types)},
                {"role": "user", "content": f"다음 텍스트에서 개체를 추출하세요:\n\n{text}"}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "ner_extraction",
                    "schema": self._get_ner_schema(max_entities),
                    "strict": True
                }
            },
            temperature=0.0,  # Deterministic for NER
            max_tokens=4096
        )

        result = response.choices[0].message.content
        parsed = json.loads(result)

        logger.info("ner_extraction_complete",
                     entity_count=len(parsed.get("entities", [])),
                     input_length=len(text))

        return parsed
```

### 1.2 시스템 프롬프트

```python
def _build_system_prompt(self, target_types: list[str]) -> str:
    type_descriptions = {
        "COMPANY": "회사명, 법인명 (예: 'XYZ 주식회사', 'ABC 제조주식회사')",
        "PERSON": "인명 (예: '홍길동', '분석가 김모', '매니저 이영희')",
        "DEPARTMENT": "부서/팀명 (예: '기획팀', '생산부', '전략기획실')",
        "AMOUNT": "금액 (예: '100억원', '5,000,000,000원', '50만원')",
        "DATE": "일자 (예: '2024년 1월 15일', '2024.01.15', '2024-01-15')",
        "ASSET_TYPE": "자산 유형 (예: '부동산', '기계장비', '지적재산권', '재고자산')",
        "PROCESS_STEP": "비즈니스 프로세스 단계 (예: '데이터 수집', '프로세스 분석', '최적화', '실행')",
        "METRIC": "비즈니스 지표 (예: '매출 500억', '영업이익률', '생산 처리량')",
        "CONTRACT": "계약 정보 (예: '공급 계약', '서비스 계약', '파트너십 협약')",
        "FINANCIAL_METRIC": "재무 지표 (예: '매출액 30억', 'EBITDA 5억', 'ROI 15%')",
        "REGULATION": "규정 참조 (예: '산업안전보건법 제100조', '공정거래법 제23조')",
    }

    selected_types = "\n".join([
        f"- {t}: {type_descriptions[t]}"
        for t in target_types if t in type_descriptions
    ])

    return f"""당신은 한국 비즈니스 문서에서 개체명을 추출하는 전문가입니다.

추출 대상 개체 유형:
{selected_types}

규칙:
1. 원문에 명시적으로 등장하는 개체만 추출합니다
2. 추론이나 추측으로 만들어진 개체는 추출하지 않습니다
3. 금액은 반드시 숫자로 정규화합니다 (예: "100억원" → "10000000000")
4. 일자는 ISO 8601 형식으로 정규화합니다 (예: "2024년 1월 15일" → "2024-01-15")
5. 각 개체에 신뢰도 점수 (0.0-1.0)를 부여합니다:
   - 1.0: 명확하게 식별 가능 (고유명사, 정확한 금액)
   - 0.75-0.99: 높은 확률로 맞음 (문맥상 명확)
   - 0.5-0.74: 불확실 (약어, 불완전한 정보)
   - 0.5 미만: 추측 (문맥 부족)
6. 동일 개체가 다른 표현으로 반복되면 가장 완전한 형태를 normalized_value로 사용합니다"""
```

### 1.3 JSON 스키마

```python
def _get_ner_schema(self, max_entities: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "entities": {
                "type": "array",
                "maxItems": max_entities,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "원문에서 추출된 텍스트 그대로"
                        },
                        "entity_type": {
                            "type": "string",
                            "enum": self.ENTITY_TYPES
                        },
                        "normalized_value": {
                            "type": "string",
                            "description": "정규화된 값 (금액은 숫자, 일자는 ISO)"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0
                        },
                        "context": {
                            "type": "string",
                            "description": "개체가 등장한 원문 문장"
                        }
                    },
                    "required": [
                        "text", "entity_type", "normalized_value",
                        "confidence", "context"
                    ],
                    "additionalProperties": False
                }
            }
        },
        "required": ["entities"],
        "additionalProperties": False
    }
```

---

## 2. 관계 추출 엔진

### 2.1 구현

```python
# app/extraction/relation_extractor.py
class RelationExtractor:
    """
    Relation Extraction using GPT-4o Structured Output.
    Identifies relationships between previously extracted entities.
    """

    RELATION_TYPES = [
        "INITIATED_PROCESS",   # Company initiated a process
        "ASSIGNED_TO",         # Resource assigned to process/metric
        "OWNS_ASSET",          # Company owns Asset
        "HAS_CONTRACT_WITH",   # Company has contract with Company
        "SUPPLIES_TO",         # Company supplies to Company
        "APPOINTED_AS",        # Person appointed as Role
        "DECIDED",             # Department/Person made decision
        "MEASURED_AS",         # Process measured as Metric
        "IMPROVED_BY",         # Metric improved by Process
        "ALLOCATED_TO",        # Amount allocated to Process
        "VALUED_AT",           # Asset valued at Amount
        "OCCURRED_ON",         # Process step occurred on Date
    ]

    async def extract_relations(
        self,
        text: str,
        entities: list[dict]
    ) -> dict:
        """
        Extract relations between entities.

        Args:
            text: Original text chunk
            entities: Previously extracted entities from NER step

        Returns:
            Dict with relations list
        """
        entity_summary = self._format_entities_for_prompt(entities)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._build_relation_prompt()},
                {"role": "user", "content": (
                    f"텍스트:\n{text}\n\n"
                    f"추출된 개체:\n{entity_summary}\n\n"
                    "위 개체 간의 관계를 추출하세요."
                )}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "relation_extraction",
                    "schema": self._get_relation_schema(),
                    "strict": True
                }
            },
            temperature=0.0,
            max_tokens=4096
        )

        return json.loads(response.choices[0].message.content)
```

### 2.2 관계 프롬프트

```python
def _build_relation_prompt(self) -> str:
    return """당신은 한국 비즈니스 문서에서 개체 간 관계를 추출하는 전문가입니다.

주어진 개체 목록과 원문을 분석하여, 개체 간 관계를 식별하세요.

추출 가능한 관계 유형:
- INITIATED_PROCESS: 조직이 프로세스를 개시/시작
- ASSIGNED_TO: 리소스가 프로세스/지표에 배정
- OWNS_ASSET: 회사/개인이 자산을 소유
- HAS_CONTRACT_WITH: 조직이 다른 조직과 계약 관계
- SUPPLIES_TO: 조직이 다른 조직에 공급
- APPOINTED_AS: 인물이 직위에 임명
- DECIDED: 부서/인물이 의사결정을 수행
- MEASURED_AS: 프로세스가 특정 지표로 측정
- IMPROVED_BY: 지표가 프로세스에 의해 개선
- ALLOCATED_TO: 금액이 프로세스에 배분
- VALUED_AT: 자산이 특정 가액으로 평가
- OCCURRED_ON: 프로세스 단계가 특정 일자에 발생

규칙:
1. 원문에 근거가 있는 관계만 추출합니다
2. 추론에 의한 관계는 추출하지 않습니다
3. 각 관계에 evidence (근거 문장)를 반드시 포함합니다
4. 신뢰도 점수를 부여합니다 (NER과 동일 기준)"""
```

### 2.3 관계 JSON 스키마

```python
def _get_relation_schema(self) -> dict:
    return {
        "type": "object",
        "properties": {
            "relations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "subject": {"type": "string"},
                        "subject_type": {"type": "string", "enum": NERExtractor.ENTITY_TYPES},
                        "predicate": {"type": "string", "enum": self.RELATION_TYPES},
                        "object": {"type": "string"},
                        "object_type": {"type": "string", "enum": NERExtractor.ENTITY_TYPES},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "evidence": {"type": "string"}
                    },
                    "required": [
                        "subject", "subject_type", "predicate",
                        "object", "object_type", "confidence", "evidence"
                    ],
                    "additionalProperties": False
                }
            }
        },
        "required": ["relations"],
        "additionalProperties": False
    }
```

---

## 3. 신뢰도 산출 체계

### 3.1 개체 신뢰도

| 수준 | 범위 | 예시 | 처리 |
|------|------|------|------|
| 확실 | 0.90-1.00 | "기획팀" (고유명사) | 자동 반영 |
| 높음 | 0.75-0.89 | "매출 100억원" (문맥 명확) | 자동 반영 |
| 보통 | 0.50-0.74 | "분석가 김모" (약칭) | HITL 검토 |
| 낮음 | 0.00-0.49 | "해당 금액" (불확실) | HITL 필수 + 경고 |

### 3.2 관계 신뢰도

개체 신뢰도와 독립적으로 산출된다. 두 개체가 모두 높은 신뢰도여도 관계 추론이 불확실할 수 있다.

### 3.3 매핑 신뢰도 (복합)

```python
def calculate_final_confidence(
    entity_confidence: float,
    relation_confidence: float,
    mapping_rule_confidence: float = 0.9
) -> float:
    """
    Final confidence = entity * relation * mapping_rule

    Example:
      entity=0.95 * relation=0.90 * mapping=0.90 = 0.77 (auto-commit)
      entity=0.65 * relation=0.80 * mapping=0.90 = 0.47 (HITL required)
    """
    return entity_confidence * relation_confidence * mapping_rule_confidence
```

---

## 4. 비즈니스 도메인 특화 처리

### 4.1 한국어 금액 정규화

```python
KOREAN_AMOUNT_MAP = {
    "만": 10_000,
    "십만": 100_000,
    "백만": 1_000_000,
    "천만": 10_000_000,
    "억": 100_000_000,
    "십억": 1_000_000_000,
    "백억": 10_000_000_000,
    "천억": 100_000_000_000,
    "조": 1_000_000_000_000,
}

def normalize_korean_amount(text: str) -> int:
    """
    "100억원" -> 10000000000
    "50만원" -> 500000
    "3조 5천억원" -> 3500000000000
    """
    # Implementation handles compound amounts
    ...
```

### 4.2 비즈니스 용어 사전

```python
BUSINESS_TERMS = {
    "프로세스 분석가": {"entity_type": "PERSON", "role": "analyst"},
    "프로젝트 매니저": {"entity_type": "PERSON", "role": "manager"},
    "대상 조직": {"entity_type": "COMPANY", "role": "subject_organization"},
    "이해관계자": {"entity_type": "COMPANY", "role": "stakeholder"},
    "공급업체": {"entity_type": "COMPANY", "role": "supplier"},
    "데이터 수집": {"entity_type": "PROCESS_STEP", "type": "DataCollection"},
    "프로세스 분석": {"entity_type": "PROCESS_STEP", "type": "ProcessAnalysis"},
    "최적화": {"entity_type": "PROCESS_STEP", "type": "Optimization"},
    "실행": {"entity_type": "PROCESS_STEP", "type": "Execution"},
}
```

---

## 5. 에러 처리 및 재시도

```python
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 3

async def extract_with_retry(self, text: str) -> dict:
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await self.extract_entities(text)
            return result
        except openai.RateLimitError:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
            else:
                raise
        except openai.APITimeoutError:
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                raise
        except json.JSONDecodeError as e:
            logger.error("invalid_json_response", error=str(e))
            if attempt < MAX_RETRIES:
                continue
            else:
                return {"entities": []}  # Return empty on persistent JSON errors
```

---

## 금지 규칙

- temperature를 0 초과로 설정하지 않는다 (NER은 결정론적이어야 함)
- 원문에 없는 개체를 추출하지 않는다 (프롬프트에 명시)
- 신뢰도 점수 없이 개체를 반환하지 않는다

## 필수 규칙

- 모든 개체에 context (근거 문장)를 포함한다
- 금액은 숫자로, 일자는 ISO 8601로 정규화한다
- LLM 응답은 항상 Structured Output (strict: true)으로 받는다

---

## 근거 문서

- ADR-003: GPT-4o Structured Output 선택 (`99_decisions/ADR-003-gpt4o-extraction.md`)
- `05_llm/structured-output.md` (Structured Output 상세)
- `05_llm/entity-extraction.md` (개체 추출 상세)
- `01_architecture/extraction-pipeline.md` (파이프라인 전체)
