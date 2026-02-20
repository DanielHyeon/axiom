# LLM 기반 메타데이터 보강

<!-- affects: llm, data, backend -->
<!-- requires-update: 03_backend/neo4j-metadata.md, 06_data/neo4j-schema.md -->

## 이 문서가 답하는 질문

- LLM이 메타데이터를 어떻게 보강하는가?
- 테이블/컬럼 설명 자동 생성은 어떤 프롬프트를 사용하는가?
- LLM 보강 결과는 어디에 저장되는가?
- LLM 실패 시 어떻게 처리하는가?
- Oracle(NL2SQL)은 보강된 메타데이터를 어떻게 활용하는가?

---

## 1. 메타데이터 보강이란

스키마 인트로스펙션으로 추출한 메타데이터(테이블명, 컬럼명, 타입)는 **기계적 정보**이다. LLM 보강은 이 기계적 정보에 **의미론적 설명**을 추가하는 과정이다.

### 1.1 보강 전후 비교

**보강 전** (스키마 인트로스펙션 결과):

```json
{
  "table": "biz_proc_metrics",
  "columns": [
    {"name": "mtr_id", "type": "bigint", "description": null},
    {"name": "org_id", "type": "bigint", "description": null},
    {"name": "mtr_type_cd", "type": "varchar(10)", "description": null},
    {"name": "mtr_value", "type": "decimal(18,2)", "description": null},
    {"name": "active_yn", "type": "char(1)", "description": null}
  ]
}
```

**보강 후** (LLM 설명 추가):

```json
{
  "table": "biz_proc_metrics",
  "description": "비즈니스 프로세스 성과 지표. 각 조직의 프로세스별 측정 유형, 수치, 활성 상태를 관리한다.",
  "columns": [
    {"name": "mtr_id", "type": "bigint", "description": "지표 고유 ID (PK)"},
    {"name": "org_id", "type": "bigint", "description": "조직 ID (FK → organizations.org_id)"},
    {"name": "mtr_type_cd", "type": "varchar(10)", "description": "지표 유형 코드 (REV: 매출, COST: 비용, PERF: 성과, KPI: 핵심지표)"},
    {"name": "mtr_value", "type": "decimal(18,2)", "description": "지표 측정값 (원). 해당 기간의 집계 수치"},
    {"name": "active_yn", "type": "char(1)", "description": "활성 여부 (Y: 활성, N: 비활성)"}
  ]
}
```

---

## 2. LLM 보강 파이프라인

```
┌─ 메타데이터 추출 완료 ──────────────────────────────────────┐
│  Neo4j에 스키마/테이블/컬럼 노드 저장 완료                    │
└────────────┬─────────────────────────────────────────────────┘
             │
             ▼
┌─ LLM 보강 시작 ─────────────────────────────────────────────┐
│                                                               │
│  1. Neo4j에서 description이 null인 테이블/컬럼 추출           │
│  2. 테이블별 배치 구성 (테이블명 + 모든 컬럼명/타입)          │
│  3. LLM 호출 (배치별)                                        │
│  4. 응답 파싱 및 검증                                         │
│  5. Neo4j description 필드 업데이트                           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. LLM 프롬프트

### 3.1 테이블 + 컬럼 설명 생성 프롬프트

```python
TABLE_DESCRIPTION_PROMPT = """
당신은 엔터프라이즈 비즈니스 프로세스 도메인의 데이터베이스 전문가입니다.
아래 테이블의 이름, 컬럼명, 데이터 타입을 분석하여 각 항목의 한국어 설명을 생성하세요.

## 도메인 컨텍스트
- 이 데이터베이스는 비즈니스 프로세스 인텔리전스 시스템입니다
- 주요 개체: 프로세스(process), 조직(organization), 이해관계자(stakeholder), 거래(transaction), 지표(metric)
- 약어 관례: biz=business(비즈니스), proc=process(프로세스), org=organization(조직), stk=stakeholder(이해관계자), mtr=metric(지표), txn=transaction(거래)

## 입력
테이블: {table_name}
스키마: {schema_name}
컬럼:
{columns_text}

샘플 데이터 (참고용):
{sample_data}

## 출력 형식 (JSON)
{{
  "table_description": "테이블에 대한 한국어 설명 (1-2문장)",
  "columns": [
    {{
      "name": "컬럼명",
      "description": "컬럼에 대한 한국어 설명. 가능한 값 범위나 enum 포함"
    }}
  ]
}}

## 규칙
1. 설명은 반드시 한국어로 작성
2. 약어가 포함된 컬럼명은 약어의 의미를 포함하여 설명
3. FK로 추정되는 컬럼은 "FK → {추정 대상 테이블}" 형식 포함
4. 코드/타입 컬럼은 가능한 값 목록 포함 (추정)
5. 날짜/금액 컬럼은 단위 명시
6. 확실하지 않은 경우 "(추정)" 표시
"""
```

### 3.2 FK 관계 추론 프롬프트 (보조)

```python
FK_INFERENCE_PROMPT = """
아래 테이블 목록에서 외래 키(FK) 관계를 추론하세요.
스키마 인트로스펙션으로 발견되지 않은 논리적 FK 관계를 찾습니다.

## 테이블 목록
{tables_with_columns}

## 규칙
1. 컬럼명 패턴으로 FK 추론 (예: org_id → organizations.org_id)
2. 이미 발견된 FK는 제외: {existing_fks}
3. confidence를 high/medium/low로 표시

## 출력 형식 (JSON)
{{
  "inferred_fks": [
    {{
      "source_table": "...",
      "source_column": "...",
      "target_table": "...",
      "target_column": "...",
      "confidence": "high|medium|low",
      "reasoning": "추론 근거"
    }}
  ]
}}
"""
```

---

## 4. 구현 설계

```python
# app/services/enrichment_service.py (계획)

class MetadataEnrichmentService:
    """LLM-based metadata enrichment

    테이블/컬럼의 description 필드를 LLM으로 자동 생성한다.
    """

    def __init__(self, llm_client, metadata_store: MetadataStore):
        self.llm = llm_client
        self.metadata_store = metadata_store

    async def enrich_datasource(
        self,
        datasource_name: str,
        batch_size: int = 5,
    ) -> dict:
        """Enrich all tables in a datasource

        Args:
            datasource_name: Target datasource
            batch_size: Number of tables per LLM call

        Returns:
            dict with enriched_tables, enriched_columns, failed_tables
        """
        # 1. Get tables without descriptions
        metadata = await self.metadata_store.get_datasource_metadata(datasource_name)
        tables_to_enrich = []

        for schema in metadata["schemas"]:
            for table in schema["tables"]:
                if not table.get("description"):
                    tables_to_enrich.append({
                        "schema": schema["name"],
                        "table": table["name"],
                        "columns": table["columns"],
                    })

        # 2. Process in batches
        enriched_tables = 0
        enriched_columns = 0
        failed_tables = []

        for i in range(0, len(tables_to_enrich), batch_size):
            batch = tables_to_enrich[i:i + batch_size]

            for table_info in batch:
                try:
                    result = await self._enrich_single_table(
                        datasource_name, table_info
                    )
                    enriched_tables += 1
                    enriched_columns += result["columns_enriched"]
                except Exception as e:
                    failed_tables.append({
                        "table": table_info["table"],
                        "error": str(e),
                    })

        return {
            "enriched_tables": enriched_tables,
            "enriched_columns": enriched_columns,
            "failed_tables": failed_tables,
        }

    async def _enrich_single_table(self, datasource: str, table_info: dict) -> dict:
        """Enrich a single table using LLM"""

        # Build prompt
        columns_text = "\n".join(
            f"  - {col['name']} ({col['dtype']}, nullable={col['nullable']})"
            for col in table_info["columns"]
        )

        prompt = TABLE_DESCRIPTION_PROMPT.format(
            table_name=table_info["table"],
            schema_name=table_info["schema"],
            columns_text=columns_text,
            sample_data="(not available)",
        )

        # Call LLM
        response = await self.llm.generate(prompt)
        result = self._parse_llm_response(response)

        # Save to Neo4j
        await self.metadata_store.update_table_description(
            datasource,
            table_info["schema"],
            table_info["table"],
            result["table_description"],
        )

        columns_enriched = 0
        for col_desc in result.get("columns", []):
            await self.metadata_store.update_column_description(
                datasource,
                table_info["schema"],
                table_info["table"],
                col_desc["name"],
                col_desc["description"],
            )
            columns_enriched += 1

        return {"columns_enriched": columns_enriched}

    def _parse_llm_response(self, response: str) -> dict:
        """Parse LLM JSON response with fallback"""
        import json
        try:
            # Try direct JSON parse
            return json.loads(response)
        except json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            import re
            match = re.search(r'```json?\s*(.*?)\s*```', response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            raise ValueError(f"Cannot parse LLM response as JSON: {response[:200]}")
```

---

## 5. LLM 실패 처리

| 실패 유형 | 처리 | 설명 |
|-----------|------|------|
| LLM API 타임아웃 | 해당 테이블 건너뛰기, 로그 기록 | description은 null로 유지 |
| JSON 파싱 실패 | 재시도 1회, 실패 시 건너뛰기 | 프롬프트에 JSON 형식 재강조 |
| description이 영어 | 한국어 재생성 요청 | 프롬프트에 "반드시 한국어" 강조 |
| 할루시네이션 | 수동 검수 필요 | "(추정)" 태그로 구분 |

### 금지사항

- LLM 보강 실패가 전체 메타데이터 추출을 실패시키지 않는다
- LLM 보강은 기존 수동 설명을 덮어쓰지 않는다 (description이 null인 경우만)
- LLM 호출 횟수/비용을 추적한다

---

## 6. Oracle(NL2SQL) 모듈 활용

보강된 메타데이터는 Oracle 모듈의 **NL2SQL RAG 파이프라인**에서 활용된다.

```
사용자: "활성 프로세스의 조직별 총 매출 금액을 보여줘"
                │
                ▼
┌─ Oracle (NL2SQL) ─────────────────────────────────────────┐
│                                                            │
│  1. Neo4j에서 관련 테이블 검색                              │
│     → "processes", "biz_proc_metrics" 테이블 발견           │
│                                                            │
│  2. 메타데이터 컨텍스트 구성                                │
│     → table: biz_proc_metrics                              │
│       description: "비즈니스 프로세스 성과 지표..."          │
│       columns:                                             │
│         - mtr_value: "지표 측정값 (원)"                     │
│         - active_yn: "활성 여부 (Y: 활성, N: 비활성)"       │
│                                                            │
│  3. SQL 생성 (설명 기반)                                   │
│     → SELECT org_id, SUM(mtr_value) as total_revenue       │
│       FROM biz_proc_metrics                                │
│       WHERE process_id IN (SELECT process_id FROM processes │
│                          WHERE process_status = 'active')  │
│       GROUP BY org_id                                      │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**핵심 가치**: LLM 보강된 description이 없으면, Oracle은 `mtr_value`가 "측정값"인지, `active_yn`이 "활성 여부"인지 알 수 없다. 결국 잘못된 SQL을 생성하거나 테이블을 찾지 못한다.

---

## 7. 관련 문서

| 문서 | 설명 |
|------|------|
| `03_backend/neo4j-metadata.md` | Neo4j 메타데이터 CRUD |
| `06_data/neo4j-schema.md` | Neo4j 그래프 스키마 |
| `02_api/metadata-api.md` | 메타데이터 추출 API |
