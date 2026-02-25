import asyncio
import re
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


# ---------------------------------------------------------------------------
# Smart mock: parses the natural-language question and generates real SQL
# that runs against the demo sales / operations tables.
# ---------------------------------------------------------------------------

_COMPANIES = ["서울전자", "한국테크", "부산물산", "대전로보틱스", "인천소프트"]
_REGIONS = ["서울", "부산", "대전", "인천", "경기"]


def _extract_question(prompt: str) -> str:
    """Pull the user question from the LLM prompt text."""
    m = re.search(r"Question:\s*(.+?)(?:\n|$)", prompt)
    return m.group(1).strip() if m else prompt


def _detect_table(question: str, schema_ddl: str) -> str:
    """Determine which table the question is about."""
    q = question.lower()
    # operations keywords
    ops_kw = ["처리", "심사", "실사", "분석", "건수", "소요", "처리 시간", "operation", "case"]
    if any(k in q for k in ops_kw):
        return "operations"
    return "sales"


def _build_sales_sql(question: str, row_limit: int) -> str:
    """Build a SELECT for the sales table based on question patterns."""
    q = question
    conditions: list[str] = []
    select_cols: list[str] = []
    group_by: list[str] = []
    order_by = ""

    # --- Date extraction ---
    # Exact date: 2024-06-20
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", q)
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        conditions.append(f"sale_date = '{y}-{mo}-{d}'")
    else:
        # 2024년 6월 20일
        m = re.search(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", q)
        if m:
            y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
            conditions.append(f"sale_date = '{y}-{mo}-{d}'")
        else:
            # 2024년 6월  (month range)
            m = re.search(r"(\d{4})년\s*(\d{1,2})월", q)
            if m:
                y, mo = m.group(1), m.group(2).zfill(2)
                conditions.append(f"sale_date >= '{y}-{mo}-01'")
                # end of month
                mo_int = int(mo)
                if mo_int == 12:
                    conditions.append(f"sale_date < '{int(y)+1}-01-01'")
                else:
                    conditions.append(f"sale_date < '{y}-{str(mo_int+1).zfill(2)}-01'")
            else:
                # 2024년 (year range)
                m = re.search(r"(\d{4})년", q)
                if m:
                    y = m.group(1)
                    conditions.append(f"sale_date >= '{y}-01-01'")
                    conditions.append(f"sale_date < '{int(y)+1}-01-01'")

    # --- Recent N months ---
    m = re.search(r"최근\s*(\d+)\s*개월", q)
    if m and not conditions:
        months = int(m.group(1))
        conditions.append(f"sale_date >= CURRENT_DATE - INTERVAL '{months} months'")

    # --- Company filter ---
    for company in _COMPANIES:
        if company in q:
            conditions.append(f"company_name = '{company}'")
            break

    # --- Region filter ---
    for region in _REGIONS:
        if f"{region}지역" in q or f"{region} 지역" in q or f"'{region}'" in q:
            conditions.append(f"region = '{region}'")
            break

    # --- Product category filter ---
    cats = ["반도체", "디스플레이", "IT솔루션", "클라우드", "AI솔루션", "원자재", "건축자재",
            "산업로봇", "자동화장비", "ERP", "보안솔루션"]
    for cat in cats:
        if cat in q:
            conditions.append(f"product_category = '{cat}'")
            break

    # --- Determine aggregation / grouping ---
    has_group = False

    if "사업부별" in q or "부서별" in q:
        group_by.append("department")
        has_group = True
    if "회사별" in q or "업체별" in q or "기업별" in q:
        group_by.append("company_name")
        has_group = True
    if "지역별" in q:
        group_by.append("region")
        has_group = True
    if "월별" in q:
        group_by.append("TO_CHAR(sale_date, 'YYYY-MM')")
        has_group = True
    if "분기별" in q:
        group_by.append("EXTRACT(QUARTER FROM sale_date)")
        has_group = True
    if "카테고리별" in q or "제품별" in q:
        group_by.append("product_category")
        has_group = True

    # --- Determine metric ---
    metric = "revenue"
    metric_label = "총매출"
    if "이익" in q or "영업이익" in q or "이윤" in q:
        metric = "(revenue - cost)"
        metric_label = "이익"
    elif "비용" in q or "원가" in q:
        metric = "cost"
        metric_label = "총비용"
    elif "수량" in q or "판매량" in q:
        metric = "quantity"
        metric_label = "총수량"

    # --- Aggregation type ---
    agg = "SUM"
    if "평균" in q:
        agg = "AVG"
    elif "최대" in q or "최고" in q or "가장 높은" in q or "가장 많은" in q:
        agg = "MAX"
    elif "최소" in q or "가장 낮은" in q or "가장 적은" in q:
        agg = "MIN"
    elif "건수" in q or "몇 건" in q or "횟수" in q:
        agg = "COUNT"
        metric = "*"
        metric_label = "건수"

    # --- Growth rate special case ---
    if "성장률" in q or "증가율" in q:
        # Compare first half vs second half of the year (simplified)
        gb = group_by[0] if group_by else "company_name"
        gb_alias = gb.replace("'", "")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = (
            f"SELECT {gb} AS 구분, "
            f"SUM(CASE WHEN EXTRACT(MONTH FROM sale_date) <= 6 THEN revenue ELSE 0 END) AS 상반기매출, "
            f"SUM(CASE WHEN EXTRACT(MONTH FROM sale_date) > 6 THEN revenue ELSE 0 END) AS 하반기매출, "
            f"ROUND((SUM(CASE WHEN EXTRACT(MONTH FROM sale_date) > 6 THEN revenue ELSE 0 END) - "
            f"SUM(CASE WHEN EXTRACT(MONTH FROM sale_date) <= 6 THEN revenue ELSE 0 END))::NUMERIC / "
            f"NULLIF(SUM(CASE WHEN EXTRACT(MONTH FROM sale_date) <= 6 THEN revenue ELSE 0 END), 0) * 100, 2) AS 성장률_pct "
            f"FROM sales{where} GROUP BY {gb} ORDER BY 성장률_pct DESC LIMIT {row_limit};"
        )
        return sql

    # --- Build SELECT ---
    if has_group:
        select_cols = list(group_by)
        if agg == "COUNT" and metric == "*":
            select_cols.append("COUNT(*) AS 건수")
        else:
            select_cols.append(f"{agg}({metric}) AS {metric_label}")
        order_by = f" ORDER BY {metric_label} DESC"
    else:
        # No grouping — return raw rows
        select_cols = ["company_name", "department", "sale_date", "product_category",
                       "revenue", "cost", "quantity", "region"]
        if agg in ("MAX", "MIN") and metric != "*":
            # Return the row with max/min
            order_by = f" ORDER BY {metric} {'DESC' if agg == 'MAX' else 'ASC'}"

    select_part = ", ".join(select_cols)
    where_part = (" WHERE " + " AND ".join(conditions)) if conditions else ""
    group_part = (" GROUP BY " + ", ".join(group_by)) if has_group else ""
    limit_part = f" LIMIT {row_limit}"

    return f"SELECT {select_part} FROM sales{where_part}{group_part}{order_by}{limit_part};"


def _build_operations_sql(question: str, row_limit: int) -> str:
    """Build a SELECT for the operations table based on question patterns."""
    q = question
    conditions: list[str] = []
    group_by: list[str] = []
    has_group = False

    # --- Date extraction ---
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", q)
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        conditions.append(f"started_at::date = '{y}-{mo}-{d}'")
    else:
        m = re.search(r"(\d{4})년\s*(\d{1,2})월", q)
        if m:
            y, mo = m.group(1), m.group(2).zfill(2)
            conditions.append(f"started_at >= '{y}-{mo}-01'")
            mo_int = int(mo)
            if mo_int == 12:
                conditions.append(f"started_at < '{int(y)+1}-01-01'")
            else:
                conditions.append(f"started_at < '{y}-{str(mo_int+1).zfill(2)}-01'")

    # Recent N months
    m = re.search(r"최근\s*(\d+)\s*개월", q)
    if m and not conditions:
        months = int(m.group(1))
        conditions.append(f"started_at >= CURRENT_DATE - INTERVAL '{months} months'")

    # Region filter
    for region in _REGIONS:
        if f"{region}" in q and ("지역" in q or "별" in q):
            conditions.append(f"region = '{region}'")
            break

    # Operation type filter
    op_types = ["서류심사", "현장실사", "데이터분석"]
    for ot in op_types:
        if ot in q:
            conditions.append(f"operation_type = '{ot}'")
            break

    # --- Grouping ---
    if "지역별" in q:
        group_by.append("region")
        has_group = True
    if "유형별" in q or "종류별" in q:
        group_by.append("operation_type")
        has_group = True
    if "월별" in q:
        group_by.append("TO_CHAR(started_at, 'YYYY-MM')")
        has_group = True
    if "담당자별" in q:
        group_by.append("operator_name")
        has_group = True

    # --- Metric ---
    if "처리 시간" in q or "소요 시간" in q or "평균 시간" in q or "처리시간" in q:
        agg_col = "AVG(duration_minutes) AS 평균처리시간_분"
        order_col = "평균처리시간_분"
    elif "건수" in q or "처리 건수" in q or "몇 건" in q:
        agg_col = "COUNT(*) AS 건수"
        order_col = "건수"
    else:
        agg_col = "COUNT(*) AS 건수"
        order_col = "건수"

    # Trend query
    if "추이" in q or "트렌드" in q:
        if "TO_CHAR(started_at, 'YYYY-MM')" not in group_by:
            group_by.append("TO_CHAR(started_at, 'YYYY-MM')")
            has_group = True

    where_part = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    if has_group:
        select_cols = group_by + [agg_col]
        select_part = ", ".join(select_cols)
        group_part = " GROUP BY " + ", ".join(group_by)
        return f"SELECT {select_part} FROM operations{where_part}{group_part} ORDER BY {group_by[0]} LIMIT {row_limit};"
    else:
        return (
            f"SELECT case_ref, operation_type, started_at, completed_at, "
            f"duration_minutes, status, region, operator_name "
            f"FROM operations{where_part} ORDER BY started_at DESC LIMIT {row_limit};"
        )


def _generate_smart_sql(prompt: str) -> str:
    """Parse the LLM prompt and generate appropriate SQL."""
    question = _extract_question(prompt)

    # Extract row limit from system prompt if present
    row_limit = 1000
    m = re.search(r"LIMIT\s+(\d+)", prompt)
    if m:
        row_limit = int(m.group(1))
    # Also check for explicit limit in question
    m = re.search(r"(\d+)건", question)
    if m:
        row_limit = min(int(m.group(1)), 10000)

    table = _detect_table(question, prompt)
    if table == "operations":
        return _build_operations_sql(question, row_limit)
    return _build_sales_sql(question, row_limit)


class MockLLMClient(BaseLLMClient):
    """Smart mock LLM: generates context-aware SQL from Korean natural language."""

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1, max_tokens: int = 4096) -> str:
        logger.info("llm_smart_mock_generate", prompt_snippet=prompt[:80])

        # Quality judge prompt — return score JSON
        sp = (system_prompt or "").lower()
        if "quality" in sp or "심사관" in sp:
            return '{"score": 0.85, "is_complete": true, "feedback": "", "next_question": ""}'

        # Summary prompt — just summarize
        if "summarize" in prompt.lower() or "요약" in prompt.lower():
            question = _extract_question(prompt)
            return f"'{question}'에 대한 조회 결과입니다."

        # SQL generation
        sql = _generate_smart_sql(prompt)
        logger.info("llm_smart_mock_sql", sql=sql[:200])
        return sql

    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        return [0.0] * 1536

    async def stream(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.1) -> AsyncGenerator[str, None]:
        sql = _generate_smart_sql(prompt)
        # Stream in chunks for realistic UX
        chunk_size = 20
        for i in range(0, len(sql), chunk_size):
            yield sql[i:i+chunk_size]
            await asyncio.sleep(0.01)


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
