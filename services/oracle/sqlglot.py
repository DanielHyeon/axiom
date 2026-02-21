from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Iterable, List


class errors:
    class ParseError(Exception):
        pass

    class TokenError(Exception):
        pass


class exp:
    @dataclass
    class Expression:
        args: dict = field(default_factory=dict)

        def find_all(self, kind):
            return []

        def copy(self):
            return copy.deepcopy(self)

        def sql(self, dialect: str = "postgres") -> str:
            _ = dialect
            return ""

    @dataclass
    class Join(Expression):
        pass

    @dataclass
    class Subquery(Expression):
        pass

    @dataclass
    class Select(Expression):
        raw_sql: str = ""
        _joins: List["exp.Join"] = field(default_factory=list)
        _subqueries: List["exp.Subquery"] = field(default_factory=list)

        def find_all(self, kind):
            if kind is exp.Join:
                return iter(self._joins)
            if kind is exp.Subquery:
                return iter(self._subqueries)
            return iter(())

        def limit(self, n: int):
            self.args["limit"] = n
            return self

        def sql(self, dialect: str = "postgres") -> str:
            _ = dialect
            text = self.raw_sql.strip().rstrip(";")
            if "limit" in self.args and not re.search(r"\blimit\s+\d+\b", text, flags=re.IGNORECASE):
                text = f"{text} LIMIT {int(self.args['limit'])}"
            return text


def _count_subqueries(sql: str) -> int:
    return len(re.findall(r"\(\s*select\b", sql, flags=re.IGNORECASE))


def _iter_joins(sql: str) -> Iterable[exp.Join]:
    count = len(re.findall(r"\bjoin\b", sql, flags=re.IGNORECASE))
    for _ in range(count):
        yield exp.Join()


def parse_one(sql_query: str, dialect: str = "postgres"):
    _ = dialect
    text = (sql_query or "").strip()
    if not text:
        raise errors.ParseError("empty sql")
    if not re.match(r"^\s*select\b", text, flags=re.IGNORECASE):
        return exp.Expression()
    joins = list(_iter_joins(text))
    subqueries = [exp.Subquery() for _ in range(_count_subqueries(text))]
    has_limit = bool(re.search(r"\blimit\s+\d+\b", text, flags=re.IGNORECASE))
    node = exp.Select(raw_sql=text, _joins=joins, _subqueries=subqueries)
    if has_limit:
        node.args["limit"] = True
    return node
