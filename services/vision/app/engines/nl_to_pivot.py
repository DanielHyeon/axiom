# 자연어 → 피벗 파라미터 (nl-to-pivot.md, V3-4)
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

NL_TO_PIVOT_SYSTEM = """당신은 비즈니스 프로세스 인텔리전스 도메인의 OLAP 분석 전문가입니다.
사용자의 자연어 질의를 피벗 테이블 파라미터로 변환합니다.

## 사용 가능한 큐브 메타데이터
{cube_context}

## 출력 형식 (반드시 유효한 JSON만 출력)
{{
  "cube_name": "큐브 이름 (위 메타데이터에 있는 것)",
  "rows": ["Dimension.Level", ...],
  "columns": ["Dimension.Level", ...],
  "measures": ["MeasureName", ...],
  "filters": [
    {{"dimension_level": "Dimension.Level", "operator": "=", "values": [...]}}
  ]
}}

## 규칙
1. rows, columns, measures는 반드시 큐브 메타데이터에 존재하는 이름만 사용
2. "~별"은 rows로, "추이"는 columns의 Time 차원으로 해석
3. "성과율"은 AvgPerformanceRate, "건수"는 CaseCount 측도로 매핑
4. 연도, 유형 등 명시적 필터가 있으면 filters에 추가 (operator: =, !=, in, >=, <=, between)
5. 명확하지 않은 부분은 가장 합리적인 해석을 선택
6. rows와 measures는 최소 1개 이상 포함
"""


def _build_cube_context(cubes: dict[str, Any]) -> str:
    """vision_runtime.cubes를 LLM용 문자열로 포맷."""
    parts = []
    for name, cube in cubes.items():
        parts.append(f"## Cube: {name}")
        parts.append(f"Fact Table: {cube.get('fact_table', '')}")
        parts.append("\n### Dimensions (rows/columns에 사용):")
        for d in cube.get("dimension_details") or []:
            levels = ", ".join(
                f"{lev.get('name', '')}({lev.get('column', '')})"
                for lev in d.get("levels") or []
            )
            parts.append(f"- {d.get('name', '')}: [{levels}]")
        if not cube.get("dimension_details"):
            for dim in cube.get("dimensions") or []:
                parts.append(f"- {dim}")
        parts.append("\n### Measures:")
        for m in cube.get("measure_details") or []:
            parts.append(f"- {m.get('name', '')}: {m.get('aggregator', 'sum')}({m.get('column', '')})")
        if not cube.get("measure_details"):
            for me in cube.get("measures") or []:
                parts.append(f"- {me}")
        parts.append("")
    return "\n".join(parts)


def _call_openai_nl_to_pivot(
    query: str,
    cube_context: str,
    cube_name_hint: str | None,
    api_key: str,
    model: str,
) -> tuple[dict[str, Any], float]:
    """OpenAI Chat Completions로 JSON 구조화 출력 요청. (pivot_params, confidence) 반환."""
    system = NL_TO_PIVOT_SYSTEM.format(cube_context=cube_context)
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI API error: {resp.status_code} {resp.text[:200]}")
    data = resp.json()
    choice = (data.get("choices") or [{}])[0]
    content = (choice.get("message") or {}).get("content") or "{}"
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    pivot_params = json.loads(text)
    if cube_name_hint and not pivot_params.get("cube_name"):
        pivot_params["cube_name"] = cube_name_hint
    if not pivot_params.get("rows"):
        pivot_params["rows"] = list((pivot_params.get("dimensions") or [])[:1]) or ["region"]
    if not pivot_params.get("measures"):
        pivot_params["measures"] = list((pivot_params.get("metrics") or [])[:1]) or ["CaseCount"]
    pivot_params.setdefault("dimensions", pivot_params.get("rows", []))
    pivot_params.setdefault("metrics", pivot_params.get("measures", []))
    confidence = 0.85 if pivot_params.get("cube_name") and pivot_params.get("measures") else 0.5
    return pivot_params, confidence


def _stub_translate(
    query: str,
    cube_context: str,
    cube_name_hint: str | None,
) -> tuple[dict[str, Any], float]:
    """API 키 없을 때 휴리스틱 스텁. (pivot_params, confidence) 반환."""
    query_lower = query.lower()
    rows = ["CaseType.CaseCategory"]
    columns = []
    measures = ["CaseCount"]
    filters = []
    if "region" in query_lower:
        rows = ["region"]
    if "sales" in query_lower:
        measures = ["sales"]
    if "profit" in query_lower:
        measures = ["profit"]
    if "성과" in query or "performance" in query_lower:
        measures = ["AvgPerformanceRate", "CaseCount"] if "profit" not in query_lower else ["profit"]
    if "연도" in query or "년" in query or "year" in query_lower:
        columns = ["Time.Year"]
    if "이해관계자" in query or "stakeholder" in query_lower:
        rows = ["Stakeholder.StakeholderType"]
    if "2024" in query:
        filters.append({"dimension_level": "Time.Year", "operator": "=", "values": [2024]})
    return {
        "cube_name": cube_name_hint or "BusinessAnalysisCube",
        "rows": rows,
        "columns": columns,
        "measures": measures,
        "filters": filters,
        "dimensions": rows,
        "metrics": measures,
    }, 0.7


class NLToPivot:
    """자연어 질의 → 피벗 파라미터 (LLM 또는 스텁)."""

    async def translate(
        self,
        natural_language: str,
        cube_context: str = "",
        cube_name_hint: str | None = None,
    ) -> dict[str, Any]:
        """
        자연어를 피벗 파라미터로 변환.
        Returns: { cube_name, rows, columns, measures, filters [, confidence] }
        """
        api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
        model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
        if api_key and cube_context:
            try:
                params, confidence = _call_openai_nl_to_pivot(
                    natural_language, cube_context, cube_name_hint, api_key, model
                )
                params["confidence"] = confidence
                return params
            except Exception:
                pass
        params, confidence = _stub_translate(natural_language, cube_context, cube_name_hint)
        params["confidence"] = confidence
        return params

    def build_cube_context(self, cubes: dict[str, Any]) -> str:
        """큐브 메타로 LLM용 컨텍스트 문자열 생성."""
        return _build_cube_context(cubes)


nl_to_pivot = NLToPivot()
