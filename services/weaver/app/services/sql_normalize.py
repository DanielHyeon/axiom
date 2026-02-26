from __future__ import annotations

import re


_COMMENT_LINE = re.compile(r"--[^\n]*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.DOTALL)
_STRING_LITERAL = re.compile(r"'[^']*'")
_NUMERIC_LITERAL = re.compile(r"\b\d+(?:\.\d+)?\b")
_WHITESPACE = re.compile(r"\s+")

# PII patterns — applied before literal masking
_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"\b\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{4}\b")
_SSN = re.compile(r"\b\d{6}[-]?\d{7}\b")


def normalize_sql(raw: str) -> str:
    """Lowercase, strip comments, collapse whitespace.

    This is the *fast-path* normalizer used at ingest time (before the
    full sqlglot parse in the worker).
    """
    s = _COMMENT_LINE.sub("", raw)
    s = _COMMENT_BLOCK.sub("", s)
    s = s.lower().strip()
    s = _WHITESPACE.sub(" ", s)
    return s


def mask_pii(sql: str) -> str:
    """Replace PII and literals with placeholders.

    Order: PII patterns first (email/phone/SSN), then string and numeric
    literals.  Prevents PII embedded in WHERE clauses from reaching the
    ``normalized_sql`` column.
    """
    s = _EMAIL.sub("'?'", sql)
    s = _PHONE.sub("?", s)
    s = _SSN.sub("?", s)
    s = _STRING_LITERAL.sub("'?'", s)
    s = _NUMERIC_LITERAL.sub("?", s)
    return s
