"""G34: Evidence Redaction — LLM 분석 근거의 민감정보 마스킹.

코드 조각(code_snippet)에 포함될 수 있는 비밀번호, API 키, 토큰,
이메일, 주민등록번호 등을 저장 전 마스킹 처리한다.

설계 원칙:
- Evidence 저장 전 반드시 redact() 호출
- 패턴 기반 마스킹 (정규식)
- 마스킹 후에도 코드 구조는 유지 (분석 근거 이해 가능)
"""

from __future__ import annotations

import re
from typing import Any

from app.models.evidence import AnalysisEvidence


# ── 마스킹 패턴 ── #

_REDACTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 비밀번호/토큰/키 할당 (password = "xxx", token: "xxx")
    (re.compile(r'(?i)(password|passwd|pwd|secret|token|api_key|secret_key|access_key)\s*[=:]\s*["\']?[^\s"\']{3,}'),
     r'\1=***REDACTED***'),
    # JDBC URL 내 password 파라미터
    (re.compile(r'(?i)jdbc:[^\s]+password=[^\s&]+'), 'jdbc:***REDACTED***'),
    # 커넥션 스트링 (M5: postgresql/mysql/mongodb/redis URI)
    (re.compile(r'(?i)(?:postgresql|mysql|mongodb|redis|amqp)(?:\+\w+)?://[^\s]+'), '***CONNECTION_STRING_REDACTED***'),
    # Bearer/Basic 토큰
    (re.compile(r'(?i)(bearer|basic)\s+[A-Za-z0-9+/=._\-]{8,}'), r'\1 ***REDACTED***'),
    # GitHub/GitLab 토큰 (M5)
    (re.compile(r'\b(?:ghp_|gho_|ghs_|glpat-)[A-Za-z0-9_]{16,}'), '***GIT_TOKEN_REDACTED***'),
    # 이메일 주소 (C1: ReDoS 수정 — 도메인 부분 비중첩 패턴)
    (re.compile(r'[a-zA-Z0-9_.%+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}'), '***@***.***'),
    # 주민등록번호 패턴 (C2: 정밀 패턴 — 성별 코드 1~4)
    (re.compile(r'\b\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[-\s]?[1-4]\d{6}\b'), '***-*******'),
    # AWS 키 패턴 (AKIA로 시작하는 20자)
    (re.compile(r'\bAKIA[A-Z0-9]{16}\b'), 'AKIA***REDACTED***'),
    # Private Key 블록 (M5)
    (re.compile(r'-----BEGIN\s+\w+\s+PRIVATE\s+KEY-----[\s\S]*?-----END\s+\w+\s+PRIVATE\s+KEY-----'),
     '-----REDACTED PRIVATE KEY-----'),
    # 긴 Base64/hex 문자열 (40자 이상 — 암호화 키/토큰일 가능성)
    (re.compile(r'["\'][A-Za-z0-9+/=]{40,}["\']'), '"***LONG_TOKEN_REDACTED***"'),
]

# 코드 조각 최대 길이
_MAX_SNIPPET_LENGTH = 500


class EvidenceRedactor:
    """Evidence JSON 저장 전 민감정보 마스킹.

    사용법:
        redactor = EvidenceRedactor()
        safe_evidence = redactor.redact_evidence(evidence)
    """

    def redact(self, snippet: str) -> str:
        """코드 조각에서 민감정보 마스킹 — C1: 길이 제한을 정규식 전에 적용"""
        # ReDoS 방지: 정규식 매칭 전에 길이 제한 (C1 수정)
        if len(snippet) > _MAX_SNIPPET_LENGTH:
            snippet = f"{snippet[:_MAX_SNIPPET_LENGTH]}...[truncated]"
        for pattern, replacement in _REDACTION_PATTERNS:
            snippet = pattern.sub(replacement, snippet)
        return snippet

    def redact_evidence(self, evidence: AnalysisEvidence) -> AnalysisEvidence:
        """Evidence 객체 전체 마스킹 — code_snippet + reasoning"""
        return evidence.model_copy(update={
            "code_snippet": self.redact(evidence.code_snippet),
            "reasoning": self.redact(evidence.reasoning),
        })


# 모듈 수준 싱글톤
evidence_redactor = EvidenceRedactor()
