"""Watch Agent -- LLM 기반 대화형 모니터링 설정.

KAIR text2sql의 watch-agent를 Axiom Core 패턴으로 이식.
사용자가 자연어로 모니터링 규칙을 설명하면 LLM이
SQL 쿼리 + 조건 + 임계값을 자동 생성한다.

흐름:
  사용자: "매출이 전월 대비 20% 이상 감소하면 알림"
  -> LLM: SQL 생성 + condition=change_rate + threshold=-0.2
  -> WatchRule 자동 생성 + 스케줄 등록
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger("watch_agent")

# LLM 팩토리 — 선택적 의존성
try:
    from langchain_openai import ChatOpenAI  # type: ignore
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    ChatOpenAI = None  # type: ignore


# ── 데이터 모델 ────────────────────────────────────────────────────


@dataclass
class WatchRuleProposal:
    """LLM이 생성한 모니터링 규칙 제안.

    사용자의 자연어 설명을 분석하여 SQL 쿼리, 조건, 임계값을 자동 결정한다.
    """
    name: str                           # 규칙 이름 (자동 생성)
    sql_query: str                      # 모니터링용 SQL 쿼리
    condition_type: str                 # 조건 유형: threshold, change_rate, anomaly, count
    threshold: float                    # 임계값 (조건별 의미 상이)
    severity: str = "medium"            # 심각도: low, medium, high, critical
    schedule_interval: str = "1h"       # 실행 주기: 5m, 15m, 1h, 6h, 1d
    explanation: str = ""               # LLM의 설명 (사용자에게 표시)
    datasource_id: str = ""             # 대상 데이터소스 ID
    columns_used: list[str] = field(default_factory=list)  # 사용된 컬럼 목록

    def to_dict(self) -> dict[str, Any]:
        """딕셔너리 변환"""
        return asdict(self)


@dataclass
class AvailabilityReport:
    """데이터 가용성 분석 결과.

    모니터링에 필요한 테이블/컬럼이 존재하는지 확인한다.
    """
    available: bool                     # 필요 데이터가 모두 존재하는지
    tables_found: list[str] = field(default_factory=list)
    tables_missing: list[str] = field(default_factory=list)
    columns_found: list[str] = field(default_factory=list)
    columns_missing: list[str] = field(default_factory=list)
    suggestion: str = ""                # 부족한 경우 대안 제안

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── LLM 프롬프트 템플릿 ────────────────────────────────────────────


# 규칙 생성용 시스템 프롬프트
_RULE_GENERATION_SYSTEM_PROMPT = """너는 데이터 모니터링 전문가야.
사용자가 자연어로 모니터링 조건을 설명하면, 아래 JSON 형식으로 응답해.

응답 형식 (JSON만 출력, 마크다운 없이):
{
  "name": "규칙 이름 (한글, 간결하게)",
  "sql_query": "SELECT ... FROM ... WHERE ...",
  "condition_type": "threshold|change_rate|anomaly|count",
  "threshold": 0.0,
  "severity": "low|medium|high|critical",
  "schedule_interval": "5m|15m|1h|6h|1d",
  "explanation": "이 규칙이 하는 일 설명",
  "columns_used": ["col1", "col2"]
}

condition_type 설명:
- threshold: 값이 임계값을 초과/미달하면 알림
- change_rate: 이전 주기 대비 변화율이 임계값을 초과하면 알림
- anomaly: 통계적 이상치 감지 (z-score 기반)
- count: 행 수가 임계값을 초과/미달하면 알림

SQL 작성 규칙:
- PostgreSQL 문법 사용
- 집계 쿼리로 단일 숫자 결과를 반환하도록 작성
- 날짜 필터는 NOW() - INTERVAL 사용
- 테이블명은 스키마.테이블 형식 사용
"""

# 데이터 가용성 분석 프롬프트
_AVAILABILITY_SYSTEM_PROMPT = """너는 데이터 분석 전문가야.
사용자의 모니터링 요구사항을 분석하여, 필요한 테이블과 컬럼을 추출해.

응답 형식 (JSON만 출력):
{
  "required_tables": ["schema.table1", "schema.table2"],
  "required_columns": ["table1.column1", "table2.column2"],
  "suggestion": "데이터가 부족한 경우 대안 제안"
}
"""


# ── Watch Agent 메인 클래스 ─────────────────────────────────────────


class WatchAgent:
    """LLM 기반 모니터링 규칙 자동 생성 에이전트.

    사용자의 자연어 설명을 분석하여 WatchRule을 생성한다.
    LLM 미설치 시 기본 규칙 템플릿으로 폴백한다.
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.1,
        schema_context: dict[str, Any] | None = None,
    ):
        self._model_name = model_name
        self._temperature = temperature
        # 스키마 컨텍스트 — 사용 가능한 테이블/컬럼 정보
        self._schema_context = schema_context or {}
        self._llm = None

        if HAS_LANGCHAIN:
            try:
                self._llm = ChatOpenAI(
                    model=model_name,
                    temperature=temperature,
                )
            except Exception as exc:
                logger.warning("LLM 초기화 실패 (폴백 사용): %s", exc)

    def _build_user_prompt(self, description: str, datasource_id: str) -> str:
        """사용자 프롬프트 구성 — 스키마 컨텍스트 포함"""
        schema_info = ""
        if self._schema_context:
            schema_info = f"\n\n사용 가능한 테이블/컬럼:\n{json.dumps(self._schema_context, ensure_ascii=False, indent=2)}"

        return (
            f"데이터소스 ID: {datasource_id}\n"
            f"모니터링 요구사항: {description}"
            f"{schema_info}"
        )

    def _parse_llm_json(self, text: str) -> dict[str, Any] | None:
        """LLM 응답에서 JSON을 추출한다."""
        # 마크다운 코드블록 제거
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # 첫 줄(```json)과 마지막 줄(```) 제거
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # JSON 부분만 추출 시도
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    pass
        logger.warning("LLM 응답 JSON 파싱 실패")
        return None

    async def generate_rule_from_text(
        self,
        description: str,
        datasource_id: str,
    ) -> WatchRuleProposal:
        """자연어 설명에서 모니터링 규칙을 자동 생성한다.

        Args:
            description: 사용자의 모니터링 요구사항 (자연어)
            datasource_id: 대상 데이터소스 ID

        Returns:
            WatchRuleProposal — 생성된 규칙 제안
        """
        if not description or not description.strip():
            raise ValueError("모니터링 설명이 비어있습니다")

        if self._llm is not None:
            return await self._generate_with_llm(description, datasource_id)
        else:
            return self._generate_fallback(description, datasource_id)

    async def _generate_with_llm(
        self,
        description: str,
        datasource_id: str,
    ) -> WatchRuleProposal:
        """LLM을 사용하여 규칙 생성"""
        from langchain_core.messages import SystemMessage, HumanMessage  # type: ignore

        messages = [
            SystemMessage(content=_RULE_GENERATION_SYSTEM_PROMPT),
            HumanMessage(content=self._build_user_prompt(description, datasource_id)),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            result = self._parse_llm_json(response.content)
        except Exception as exc:
            logger.error("LLM 호출 실패: %s — 폴백 사용", exc)
            return self._generate_fallback(description, datasource_id)

        if result is None:
            logger.warning("LLM 응답 파싱 실패 — 폴백 사용")
            return self._generate_fallback(description, datasource_id)

        return WatchRuleProposal(
            name=result.get("name", f"Auto: {description[:40]}"),
            sql_query=result.get("sql_query", "SELECT 1"),
            condition_type=result.get("condition_type", "threshold"),
            threshold=float(result.get("threshold", 0.0)),
            severity=result.get("severity", "medium"),
            schedule_interval=result.get("schedule_interval", "1h"),
            explanation=result.get("explanation", ""),
            datasource_id=datasource_id,
            columns_used=result.get("columns_used", []),
        )

    def _generate_fallback(
        self,
        description: str,
        datasource_id: str,
    ) -> WatchRuleProposal:
        """LLM 없이 키워드 기반 규칙 생성 (폴백).

        간단한 키워드 매칭으로 기본적인 규칙을 생성한다.
        """
        desc_lower = description.lower()

        # 조건 유형 추론
        if any(kw in desc_lower for kw in ["변화", "증가", "감소", "대비", "change", "rate"]):
            condition_type = "change_rate"
        elif any(kw in desc_lower for kw in ["이상치", "비정상", "anomal"]):
            condition_type = "anomaly"
        elif any(kw in desc_lower for kw in ["건수", "횟수", "count", "개수"]):
            condition_type = "count"
        else:
            condition_type = "threshold"

        # 심각도 추론
        if any(kw in desc_lower for kw in ["긴급", "critical", "심각"]):
            severity = "critical"
        elif any(kw in desc_lower for kw in ["높", "high", "중요"]):
            severity = "high"
        elif any(kw in desc_lower for kw in ["낮", "low", "경미"]):
            severity = "low"
        else:
            severity = "medium"

        # 임계값 추론 — 숫자 추출 시도
        threshold = 0.0
        import re
        numbers = re.findall(r"[-+]?\d*\.?\d+", description)
        if numbers:
            # 가장 의미 있는 숫자 (보통 퍼센트나 절대값)
            threshold = float(numbers[-1])
            # 퍼센트 언급 시 소수점 변환
            if "%" in description or "퍼센트" in description:
                threshold = threshold / 100.0

        return WatchRuleProposal(
            name=f"자동 감지: {description[:50]}",
            sql_query="SELECT COUNT(*) AS value FROM information_schema.tables WHERE 1=1",
            condition_type=condition_type,
            threshold=threshold,
            severity=severity,
            schedule_interval="1h",
            explanation=(
                "LLM이 사용 불가하여 키워드 기반으로 기본 규칙을 생성했습니다. "
                "SQL 쿼리를 직접 수정해주세요."
            ),
            datasource_id=datasource_id,
            columns_used=[],
        )

    async def analyze_data_availability(
        self,
        datasource_id: str,
        question: str,
    ) -> AvailabilityReport:
        """모니터링에 필요한 데이터가 존재하는지 확인한다.

        Args:
            datasource_id: 데이터소스 ID
            question: 사용자의 모니터링 요구사항

        Returns:
            AvailabilityReport — 데이터 가용성 분석 결과
        """
        if not question or not question.strip():
            return AvailabilityReport(
                available=False,
                suggestion="모니터링 요구사항이 비어있습니다.",
            )

        if self._llm is not None:
            return await self._analyze_with_llm(datasource_id, question)
        else:
            return self._analyze_fallback(datasource_id, question)

    async def _analyze_with_llm(
        self,
        datasource_id: str,
        question: str,
    ) -> AvailabilityReport:
        """LLM으로 데이터 가용성 분석"""
        from langchain_core.messages import SystemMessage, HumanMessage  # type: ignore

        schema_info = ""
        if self._schema_context:
            schema_info = f"\n사용 가능한 스키마:\n{json.dumps(self._schema_context, ensure_ascii=False)}"

        messages = [
            SystemMessage(content=_AVAILABILITY_SYSTEM_PROMPT),
            HumanMessage(content=f"데이터소스: {datasource_id}\n질문: {question}{schema_info}"),
        ]

        try:
            response = await self._llm.ainvoke(messages)
            result = self._parse_llm_json(response.content)
        except Exception as exc:
            logger.error("LLM 가용성 분석 실패: %s", exc)
            return self._analyze_fallback(datasource_id, question)

        if result is None:
            return self._analyze_fallback(datasource_id, question)

        required_tables = result.get("required_tables", [])
        required_columns = result.get("required_columns", [])

        # 스키마 컨텍스트와 대조하여 존재 여부 확인
        available_tables = set()
        if self._schema_context:
            for table_info in self._schema_context.get("tables", []):
                tname = table_info if isinstance(table_info, str) else table_info.get("name", "")
                available_tables.add(tname)

        tables_found = [t for t in required_tables if t in available_tables]
        tables_missing = [t for t in required_tables if t not in available_tables]

        return AvailabilityReport(
            available=len(tables_missing) == 0,
            tables_found=tables_found,
            tables_missing=tables_missing,
            columns_found=[],  # 컬럼 레벨 검증은 추후 구현
            columns_missing=[],
            suggestion=result.get("suggestion", ""),
        )

    def _analyze_fallback(
        self,
        datasource_id: str,
        question: str,
    ) -> AvailabilityReport:
        """LLM 없이 기본 가용성 보고서 생성"""
        return AvailabilityReport(
            available=True,
            tables_found=[],
            tables_missing=[],
            suggestion="LLM 미사용 — 데이터 가용성을 자동 검증할 수 없습니다. 직접 확인해주세요.",
        )
