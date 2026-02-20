# 비정형 문서 온톨로지 추출 파이프라인

## 이 문서가 답하는 질문

- 비정형 문서에서 온톨로지를 추출하는 전체 과정은?
- 각 파이프라인 단계에서 무엇이 입력되고 무엇이 출력되는가?
- HITL (Human-in-the-Loop) 검토는 어떤 기준으로 트리거되는가?
- GPT-4o Structured Output을 어떻게 활용하는가?

<!-- affects: backend, llm, api, frontend -->
<!-- requires-update: 05_llm/structured-output.md, 02_api/extraction-api.md -->

---

## 1. 파이프라인 개요

```
┌──────────────────────────────────────────────────────────────────┐
│                비정형 문서 → 온톨로지 추출 파이프라인               │
│                                                                    │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │ 1. 문서  │    │ 2. 텍스트│    │ 3. NER   │    │ 4. 관계  │   │
│  │    수집   │───▶│    추출  │───▶│ (개체명  │───▶│    추출  │   │
│  │          │    │  + 청킹  │    │  인식)   │    │          │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│                                                        │          │
│  ┌──────────┐    ┌──────────┐                         │          │
│  │ 6. Neo4j │    │ 5. 온톨  │                         │          │
│  │    반영   │◀───│ 로지 매핑│◀────────────────────────┘          │
│  └──────────┘    └──────────┘                                    │
│       │                                                           │
│       ▼                                                           │
│  ┌──────────┐                                                    │
│  │ 7. HITL  │  (신뢰도 < 0.75 필드)                              │
│  │    검토   │                                                    │
│  └──────────┘                                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 단계별 상세

### 2.1 단계 1: 문서 수집 (Document Ingestion)

**입력**: 문서 파일 (PDF, DOCX, HWP, 이미지)
**출력**: 원본 텍스트 + 메타데이터

#### 지원 문서 유형

| 문서 유형 | 예시 | 추출 방법 |
|----------|------|----------|
| 비즈니스 문서 | 사업계획서, 운영보고서 | PDF → pdfplumber |
| 분석 보고서 | 프로세스 분석 보고서 | PDF → pdfplumber |
| 이해관계자 보고서 | 이해관계자 의견서, 조직 현황서 | DOCX → python-docx |
| 재무제표 | 감사보고서, 재무상태표 | PDF → pdfplumber (표 추출) |
| 계약서 | 공급계약서, 서비스계약서 | PDF/HWP |
| 스캔 문서 | 수기 서류, 팩스 | 이미지 → GPT-4o Vision OCR |

#### 처리 흐름

```python
# Document Ingestion pseudo-code
async def ingest_document(doc_id: str, file_path: str) -> RawDocument:
    file_type = detect_file_type(file_path)

    if file_type == "pdf":
        text = extract_with_pdfplumber(file_path)
        tables = extract_tables_with_pdfplumber(file_path)
    elif file_type == "image":
        text = await extract_with_gpt4o_vision(file_path)
    elif file_type == "docx":
        text = extract_with_python_docx(file_path)

    return RawDocument(
        doc_id=doc_id,
        text=text,
        tables=tables,
        metadata=extract_metadata(file_path)
    )
```

---

### 2.2 단계 2: 텍스트 추출 및 청킹

**입력**: 원본 텍스트
**출력**: 청크 리스트 (각 800토큰)

#### 청킹 전략

| 파라미터 | 값 | 근거 |
|---------|---|------|
| 청크 크기 | 800 토큰 | GPT-4o 컨텍스트 윈도우 내 적정 입력 크기 |
| 오버랩 | 100 토큰 | 문장 경계에서의 개체 누락 방지 |
| 분할 기준 | 문단 → 문장 → 토큰 | 의미 단위 보존 우선 |

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " "],
    length_function=token_count  # tiktoken 기반
)

chunks = splitter.split_text(raw_text)
```

#### 표 데이터 처리

표 형식 데이터는 청킹하지 않고, Markdown 테이블 형태로 변환하여 별도 처리한다.

```python
def table_to_markdown(table: List[List[str]]) -> str:
    header = " | ".join(table[0])
    separator = " | ".join(["---"] * len(table[0]))
    rows = [" | ".join(row) for row in table[1:]]
    return f"{header}\n{separator}\n" + "\n".join(rows)
```

---

### 2.3 단계 3: 개체명 인식 (NER)

**입력**: 텍스트 청크
**출력**: 추출된 개체 리스트 (유형, 값, 신뢰도)

#### GPT-4o Structured Output JSON 스키마

```json
{
  "type": "object",
  "properties": {
    "entities": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "text": {"type": "string", "description": "원문에서 추출된 텍스트"},
          "entity_type": {
            "type": "string",
            "enum": [
              "COMPANY", "PERSON", "DEPARTMENT", "AMOUNT", "DATE",
              "ASSET_TYPE", "PROCESS_STEP", "METRIC", "CONTRACT",
              "FINANCIAL_METRIC", "REFERENCE"
            ]
          },
          "normalized_value": {"type": "string", "description": "정규화된 값"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "span_start": {"type": "integer"},
          "span_end": {"type": "integer"},
          "context": {"type": "string", "description": "개체가 등장한 문맥 문장"}
        },
        "required": ["text", "entity_type", "normalized_value", "confidence"]
      }
    }
  },
  "required": ["entities"]
}
```

#### NER 프롬프트 전략

```
시스템 프롬프트:
당신은 비즈니스 문서에서 개체명을 추출하는 전문가입니다.
다음 텍스트에서 개체를 추출하세요.

추출 대상:
- COMPANY: 기업명, 조직명 (예: "XYZ 주식회사", "ABC 제조")
- PERSON: 인명 (예: "홍길동", "분석가 김모")
- DEPARTMENT: 부서명 (예: "생산부", "마케팅팀")
- AMOUNT: 금액 (예: "100억원", "5,000,000,000원")
- DATE: 일자 (예: "2024년 1월 15일", "2024.01.15")
- ASSET_TYPE: 자산 유형 (예: "부동산", "설비", "지적재산권")
- PROCESS_STEP: 프로세스 단계 (예: "데이터 수집", "프로세스 분석", "최적화")
- METRIC: 비즈니스 지표 (예: "처리량 10,000건", "사이클 타임 48시간")
- CONTRACT: 계약 정보 (예: "공급계약 100억", "서비스계약")
- FINANCIAL_METRIC: 재무 지표 (예: "매출액 500억", "EBITDA 50억")
- REFERENCE: 참조 문서 (예: "2024년도 사업계획서")

각 개체에 신뢰도 점수 (0.0-1.0)를 부여하세요.
- 1.0: 명확하게 식별 가능
- 0.75-0.99: 높은 확률로 맞음
- 0.5-0.74: 불확실, 인간 확인 필요
- 0.5 미만: 추측, 인간 확인 필수
```

#### NER 결과 예시

```json
{
  "entities": [
    {
      "text": "XYZ 주식회사",
      "entity_type": "COMPANY",
      "normalized_value": "XYZ 주식회사",
      "confidence": 0.98,
      "span_start": 15,
      "span_end": 25,
      "context": "대상 조직 XYZ 주식회사는 2024년 1월 15일 프로세스 개선 프로젝트를 시작하였다."
    },
    {
      "text": "500억원",
      "entity_type": "AMOUNT",
      "normalized_value": "50000000000",
      "confidence": 0.95,
      "span_start": 89,
      "span_end": 93,
      "context": "총 매출액은 500억원이며, 이 중 영업이익은 50억원이다."
    },
    {
      "text": "분석가 김모",
      "entity_type": "PERSON",
      "normalized_value": "김모",
      "confidence": 0.65,
      "span_start": 120,
      "span_end": 126,
      "context": "프로세스 분석가 김모는 보고서에서 다음과 같이 보고하였다."
    }
  ]
}
```

---

### 2.4 단계 4: 관계 추출 (Relation Extraction)

**입력**: 추출된 개체 리스트 + 원문 청크
**출력**: 관계 리스트 (주체, 객체, 관계 유형, 신뢰도)

#### GPT-4o 관계 추출 JSON 스키마

```json
{
  "type": "object",
  "properties": {
    "relations": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "subject": {"type": "string", "description": "주체 개체"},
          "subject_type": {"type": "string"},
          "predicate": {
            "type": "string",
            "enum": [
              "INITIATED_PROCESS", "ASSIGNED_TO", "OWNS_ASSET",
              "HAS_CONTRACT_WITH", "ALLOCATED_TO", "MANAGED_BY",
              "APPROVED", "MEASURED_AT", "RESULTED_IN",
              "PRODUCED_BY", "VALUED_AT", "OCCURRED_ON"
            ]
          },
          "object": {"type": "string", "description": "객체 개체"},
          "object_type": {"type": "string"},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "evidence": {"type": "string", "description": "관계의 근거 문장"}
        },
        "required": ["subject", "predicate", "object", "confidence"]
      }
    }
  },
  "required": ["relations"]
}
```

#### 관계 추출 결과 예시

```json
{
  "relations": [
    {
      "subject": "XYZ 주식회사",
      "subject_type": "COMPANY",
      "predicate": "INITIATED_PROCESS",
      "object": "프로세스 분석",
      "object_type": "PROCESS_STEP",
      "confidence": 0.97,
      "evidence": "대상 조직 XYZ 주식회사는 2024년 1월 15일 프로세스 분석을 시작하였다."
    },
    {
      "subject": "XYZ 주식회사",
      "subject_type": "COMPANY",
      "predicate": "HAS_CONTRACT_WITH",
      "object": "원자재 공급사",
      "object_type": "COMPANY",
      "confidence": 0.92,
      "evidence": "대상 조직은 원자재 공급사에 대하여 연간 100억원의 공급 계약을 체결하고 있다."
    }
  ]
}
```

---

### 2.5 단계 5: 온톨로지 매핑

**입력**: 추출된 개체 + 관계
**출력**: 4계층 온톨로지 노드 + 관계 매핑

#### 매핑 규칙

| NER 개체 유형 | 온톨로지 계층 | 노드 레이블 |
|-------------|------------|-----------|
| COMPANY | Resource | `:Company:Resource` |
| PERSON | Resource | `:Employee:Resource` 또는 별도 `:Person` |
| ASSET_TYPE | Resource | `:Asset:Resource` |
| CONTRACT | Resource | `:Contract:Resource` |
| FINANCIAL_METRIC | Resource | `:Financial:Resource` |
| PROCESS_STEP | Process | `:Process` (하위 유형 자동 분류) |
| METRIC | Measure | `:Measure` (하위 유형 자동 분류) |
| AMOUNT (프로세스 결과) | Measure | 해당 Measure 속성값 |
| AMOUNT (KPI) | KPI | 해당 KPI 속성값 |

#### 관계 매핑 규칙

| 추출된 관계 | 온톨로지 관계 | 방향 |
|-----------|------------|------|
| INITIATED_PROCESS | PARTICIPATES_IN | Resource → Process |
| ASSIGNED_TO | PARTICIPATES_IN | Resource → Process |
| OWNS_ASSET | OWNS | Company → Asset |
| HAS_CONTRACT_WITH | HAS_CONTRACT | Company → Contract |
| ALLOCATED_TO | ALLOCATED_TO | Contract → Resource |
| MEASURED_AT | PRODUCES | Process → Measure |
| PRODUCED_BY | PRODUCES | Process → Measure |

#### 매핑 신뢰도 산출

```python
def calculate_mapping_confidence(
    ner_confidence: float,
    relation_confidence: float,
    mapping_rule_confidence: float = 0.9  # rule-based mapping default
) -> float:
    """
    Three-way confidence multiplication
    - NER confidence: how sure are we about the entity?
    - Relation confidence: how sure about the relationship?
    - Mapping rule confidence: how sure about the ontology mapping?
    """
    return ner_confidence * relation_confidence * mapping_rule_confidence
```

---

### 2.6 단계 6: Neo4j 반영

**입력**: 온톨로지 매핑 결과 (신뢰도 >= 0.75)
**출력**: Neo4j 노드/관계 생성

#### 반영 전략

```cypher
// MERGE 패턴: 기존 노드가 있으면 업데이트, 없으면 생성
MERGE (c:Company:Resource {
  case_id: $case_id,
  name: $company_name
})
ON CREATE SET
  c.id = randomUUID(),
  c.org_id = $org_id,
  c.source = 'extracted',
  c.confidence = $confidence,
  c.verified = false,
  c.created_at = datetime()
ON MATCH SET
  c.confidence = CASE WHEN $confidence > c.confidence THEN $confidence ELSE c.confidence END,
  c.updated_at = datetime()
```

---

### 2.7 단계 7: HITL 검토

**트리거 조건**: 매핑 신뢰도 < 0.75

#### HITL 상태 머신

```
PENDING → REVIEWING → APPROVED | REJECTED | MODIFIED
```

#### HITL 검토 대상 분류

| 신뢰도 범위 | 처리 | UI 표시 |
|------------|------|---------|
| 0.75 - 1.0 | 자동 반영 | 녹색 (확인됨) |
| 0.50 - 0.74 | HITL 검토 필요 | 황색 (검토 필요) |
| 0.00 - 0.49 | HITL 검토 필수 + 경고 | 적색 (저신뢰) |

#### HITL 검토 항목

```json
{
  "review_item": {
    "entity_id": "uuid",
    "original_text": "분석가 김모",
    "extracted_type": "PERSON",
    "suggested_mapping": "Employee:Resource",
    "confidence": 0.65,
    "context": "프로세스 분석가 김모는 보고서에서...",
    "actions": ["APPROVE", "REJECT", "MODIFY"],
    "modify_options": {
      "correct_type": ["COMPANY", "PERSON", "DEPARTMENT", "..."],
      "correct_value": "string",
      "correct_mapping": ["Resource", "Process", "Measure", "KPI"]
    }
  }
}
```

---

## 3. 오류 처리

### 3.1 파이프라인 단계별 실패 처리

| 단계 | 실패 유형 | 처리 방법 |
|------|----------|----------|
| 문서 수집 | 파일 손상, 지원되지 않는 형식 | 작업 FAILED + 사유 기록 |
| 텍스트 추출 | OCR 실패, 빈 텍스트 | 재시도 1회 → 실패 시 수동 입력 요청 |
| NER | LLM 타임아웃, 비정상 JSON | 재시도 2회 → 실패 시 부분 결과 저장 |
| 관계 추출 | LLM 타임아웃 | 재시도 2회 → NER 결과만 저장 |
| 온톨로지 매핑 | 매핑 규칙 미매칭 | HITL 대기열로 전달 |
| Neo4j 반영 | 쓰기 실패 | 트랜잭션 롤백 + 재시도 |

### 3.2 멱등성 보장

- 동일 문서 재추출 시 기존 결과를 MERGE (덮어쓰기가 아닌 합산)
- task_id 기반 중복 실행 방지
- 각 단계 결과를 PostgreSQL에 저장하여 중간 재시작 가능

---

## 4. 성능 고려사항

| 항목 | 예상 값 | 병목 |
|------|--------|------|
| 10페이지 PDF 처리 | 30-60초 | GPT-4o API 호출 (NER + 관계 추출) |
| 100페이지 보고서 | 5-10분 | 청크 수 비례, 병렬 NER 가능 |
| 동시 추출 작업 | 최대 5개 | GPT-4o Rate Limit |
| Neo4j 반영 | < 1초/문서 | 배치 MERGE |

### 청크 병렬 처리

```python
async def extract_entities_parallel(chunks: List[str]) -> List[NERResult]:
    """
    Parallel NER extraction with rate limiting
    """
    semaphore = asyncio.Semaphore(3)  # max 3 concurrent GPT-4o calls

    async def extract_one(chunk: str) -> NERResult:
        async with semaphore:
            return await ner_extractor.extract(chunk)

    results = await asyncio.gather(
        *[extract_one(chunk) for chunk in chunks],
        return_exceptions=True
    )
    return [r for r in results if not isinstance(r, Exception)]
```

---

## 결정 사항

| 결정 | 근거 |
|------|------|
| GPT-4o Structured Output 사용 | JSON 스키마 100% 준수 보장 (ADR-003) |
| 신뢰도 임계값 0.75 | 비즈니스 도메인 정확도 요구 + 리뷰 비용 균형 (ADR-004) |
| 비동기 파이프라인 | LLM 호출 포함 장시간 작업, 동기 처리 부적합 |
| 800토큰 청킹 | GPT-4o 입력 효율 + 개체 경계 보존 최적점 |

---

## 근거 문서

- ADR-003: GPT-4o Structured Output 선택 (`99_decisions/ADR-003-gpt4o-extraction.md`)
- ADR-004: HITL 신뢰도 임계값 결정 (`99_decisions/ADR-004-hitl-threshold.md`)
- K-AIR 역설계 분석 보고서 섹션 4.7.3
- `05_llm/structured-output.md` (GPT-4o 활용 상세)
- `05_llm/entity-extraction.md` (NER 상세)
