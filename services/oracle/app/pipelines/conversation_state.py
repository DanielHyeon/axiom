"""대화 연속성 (Conversation State) 관리.

KAIR text2sql의 conversation_capsule을 Axiom 패턴으로 이식.
멀티턴 대화에서 이전 질문/SQL/결과 컨텍스트를 유지하여
후속 질문에서 테이블 재탐색 없이 정확한 SQL을 생성한다.

예시 흐름:
  Turn 1: "월별 매출 합계를 보여줘" → SELECT month, SUM(amount) ...
  Turn 2: "그 중에서 1억 이상만" → SELECT month, SUM(amount) ... HAVING SUM(amount) >= 100000000
  Turn 3: "서울 지역으로 필터링" → ... WHERE region = '서울' ...

conversation_state 토큰은 base64(HMAC 서명 JSON)으로 인코딩되어
클라이언트에 전달되고, 다음 요청에서 복원된다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

def _get_secret() -> bytes:
    """settings에서 서명 키를 가져온다 — 임포트 시점 고정 방지."""
    from app.core.config import settings
    return settings.JWT_SECRET_KEY.encode()

# 대화 이력 최대 턴 수 — 너무 길면 LLM 컨텍스트 낭비
MAX_CONVERSATION_TURNS = 10

# 대화 이력 최대 토큰 크기 (근사) — base64 인코딩 후 최대 크기 제한
MAX_STATE_BYTES = 32_000


_DANGEROUS_PATTERNS = ["ignore all", "forget all", "disregard", "system prompt", "new instruction"]


def _sanitize_for_prompt(text: str, max_len: int = 200) -> str:
    """프롬프트 삽입 전 위험 패턴을 제거한다 — 인젝션 방어."""
    sanitized = text[:max_len]
    lower = sanitized.lower()
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in lower:
            sanitized = sanitized.replace(pattern, "[FILTERED]").replace(
                pattern.title(), "[FILTERED]"
            )
    return sanitized


@dataclass
class ConversationTurn:
    """대화 한 턴의 정보."""
    question: str
    sql: str = ""
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    row_count: int | None = None
    summary: str = ""


@dataclass
class ConversationContext:
    """멀티턴 대화 전체 컨텍스트."""
    turns: list[ConversationTurn] = field(default_factory=list)
    datasource_id: str = ""
    case_id: str | None = None

    def add_turn(self, turn: ConversationTurn) -> None:
        """턴을 추가한다. 최대 턴 수를 초과하면 오래된 것부터 제거."""
        self.turns.append(turn)
        if len(self.turns) > MAX_CONVERSATION_TURNS:
            self.turns = self.turns[-MAX_CONVERSATION_TURNS:]

    def get_context_for_prompt(self) -> str:
        """LLM 프롬프트에 삽입할 대화 이력 문자열을 생성한다.

        이전 턴의 질문과 SQL을 간결하게 요약하여
        후속 질문의 맥락을 제공한다.
        프롬프트 인젝션 방어를 위해 위험 패턴을 제거한다.
        """
        if not self.turns:
            return ""

        lines = ["## 이전 대화 이력"]
        for i, turn in enumerate(self.turns, 1):
            lines.append(f"Turn {i}: Q: {_sanitize_for_prompt(turn.question)}")
            if turn.sql:
                sql_preview = turn.sql[:100] + ("..." if len(turn.sql) > 100 else "")
                lines.append(f"  SQL: {sql_preview}")
            if turn.tables:
                lines.append(f"  Tables: {', '.join(turn.tables)}")
        return "\n".join(lines)

    def get_recent_tables(self) -> list[str]:
        """최근 대화에서 사용된 테이블 목록을 반환한다.

        후속 질문에서 동일 테이블을 우선 검색하는 데 사용.
        """
        tables: list[str] = []
        for turn in reversed(self.turns):
            for t in turn.tables:
                if t not in tables:
                    tables.append(t)
        return tables


def encode_conversation_state(context: ConversationContext) -> str:
    """대화 컨텍스트를 HMAC 서명된 base64 토큰으로 인코딩한다.

    클라이언트는 이 토큰을 다음 요청의 conversation_state 필드에 전달한다.
    서버에서 복원 시 HMAC 서명을 검증하여 위변조를 탐지한다.
    """
    data = {
        "turns": [
            {
                "question": t.question,
                "sql": t.sql,
                "tables": t.tables,
                "columns": t.columns[:5],  # 컬럼은 축약
                "row_count": t.row_count,
            }
            for t in context.turns
        ],
        "datasource_id": context.datasource_id,
        "case_id": context.case_id,
    }

    payload = json.dumps(data, ensure_ascii=False).encode()

    # 크기 제한 — 너무 크면 오래된 턴 제거
    while len(payload) > MAX_STATE_BYTES and len(data["turns"]) > 1:
        data["turns"].pop(0)
        payload = json.dumps(data, ensure_ascii=False).encode()

    sig = hmac.new(_get_secret(), payload, hashlib.sha256).hexdigest()
    wrapper = json.dumps({"p": payload.decode(), "s": sig})
    return base64.b64encode(wrapper.encode()).decode()


def decode_conversation_state(token: str) -> ConversationContext | None:
    """HMAC 서명을 검증하고 대화 컨텍스트를 복원한다.

    위변조된 토큰은 None을 반환한다.
    """
    if not token:
        return None

    try:
        wrapper = json.loads(base64.b64decode(token).decode())
        payload = wrapper["p"].encode()
        expected_sig = hmac.new(_get_secret(), payload, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(wrapper["s"], expected_sig):
            logger.warning("conversation_state_tampered", msg="서명 불일치")
            return None

        data = json.loads(payload)
        context = ConversationContext(
            datasource_id=data.get("datasource_id", ""),
            case_id=data.get("case_id"),
        )
        for t in data.get("turns", []):
            context.turns.append(ConversationTurn(
                question=t.get("question", ""),
                sql=t.get("sql", ""),
                tables=t.get("tables", []),
                columns=t.get("columns", []),
                row_count=t.get("row_count"),
            ))
        return context

    except Exception as e:
        logger.warning("conversation_state_decode_failed", error=str(e))
        return None
