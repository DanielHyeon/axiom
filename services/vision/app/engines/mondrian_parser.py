# Mondrian XML 파서 (mondrian-parser.md, V3-1)
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_string(xml_string: str) -> dict[str, Any]:
    """
    Mondrian XML 문자열을 파싱하여 schema_name과 cubes 메타 반환.
    Returns: {"schema_name": str, "cubes": [{"name", "fact_table", "dimensions", "measures", "dimension_details", "measure_details"}]}
    """
    root = ET.fromstring(xml_string)
    schema_name = root.get("name", "default")
    cubes = []
    for cube_elem in root.findall("Cube"):
        _append_cube(cubes, cube_elem)
    if not cubes and root.tag == "Cube":
        _append_cube(cubes, root)
    return {"schema_name": schema_name, "cubes": cubes}


def _append_cube(cubes: list[dict[str, Any]], cube_elem: ET.Element) -> None:
    fact_table = cube_elem.get("factTable", "")
    dimensions = _parse_dimensions(cube_elem)
    measures = _parse_measures(cube_elem)
    dim_names = [d["name"] for d in dimensions]
    measure_names = [m["name"] for m in measures]
    cubes.append({
        "name": cube_elem.get("name", ""),
        "fact_table": fact_table,
        "dimensions": dim_names,
        "measures": measure_names,
        "dimension_details": dimensions,
        "measure_details": measures,
    })


def parse_file(xml_path: str | Path) -> dict[str, Any]:
    """Mondrian XML 파일 경로를 파싱."""
    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    schema_name = root.get("name", "default")
    cubes = []
    for cube_elem in root.findall("Cube"):
        fact_table = cube_elem.get("factTable", "")
        dimensions = _parse_dimensions(cube_elem)
        measures = _parse_measures(cube_elem)
        dim_names = [d["name"] for d in dimensions]
        measure_names = [m["name"] for m in measures]
        cubes.append({
            "name": cube_elem.get("name", ""),
            "fact_table": fact_table,
            "dimensions": dim_names,
            "measures": measure_names,
            "dimension_details": dimensions,
            "measure_details": measures,
        })
    return {"schema_name": schema_name, "cubes": cubes}


def _parse_dimensions(cube_elem: ET.Element) -> list[dict[str, Any]]:
    out = []
    for dim_elem in cube_elem.findall("Dimension"):
        hierarchy = dim_elem.find("Hierarchy")
        if hierarchy is None:
            continue
        levels = []
        for level_elem in hierarchy.findall("Level"):
            levels.append({
                "name": level_elem.get("name", ""),
                "column": level_elem.get("column", ""),
                "type": level_elem.get("type", "String"),
            })
        out.append({
            "name": dim_elem.get("name", ""),
            "foreign_key": dim_elem.get("foreignKey", ""),
            "table": hierarchy.get("table", ""),
            "primary_key": hierarchy.get("primaryKey", "id"),
            "levels": levels,
        })
    return out


def _parse_measures(cube_elem: ET.Element) -> list[dict[str, Any]]:
    out = []
    for measure_elem in cube_elem.findall("Measure"):
        out.append({
            "name": measure_elem.get("name", ""),
            "column": measure_elem.get("column", ""),
            "aggregator": measure_elem.get("aggregator", "sum"),
            "format_string": measure_elem.get("formatString"),
        })
    return out


def validate_parsed(cube: dict[str, Any]) -> list[str]:
    """파싱된 큐브 검증. 경고/오류 메시지 리스트 반환 (빈 리스트면 유효)."""
    warnings = []
    if not cube.get("name"):
        warnings.append("Cube name is empty")
    if not cube.get("fact_table"):
        warnings.append(f"Cube '{cube.get('name')}' has no factTable")
    if not cube.get("dimensions"):
        warnings.append(f"Cube '{cube.get('name')}' has no dimensions")
    if not cube.get("measures"):
        warnings.append(f"Cube '{cube.get('name')}' has no measures")
    return warnings
