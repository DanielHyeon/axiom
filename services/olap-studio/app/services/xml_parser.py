"""Mondrian XML 파서 — XML 스키마를 CubeMetadata로 변환한다.

KAIR data-platform-olap의 xml_parser.py를 참조하여 Axiom 패턴으로 재구현.
"""
from __future__ import annotations

from lxml import etree
import structlog

from app.models.cube import (
    CubeMetadata, DimensionDef, MeasureDef, Hierarchy,
    DimensionLevel, JoinDef,
)

logger = structlog.get_logger(__name__)


def parse_mondrian_xml(xml_content: str) -> list[CubeMetadata]:
    """Mondrian XML 문자열을 파싱하여 CubeMetadata 목록을 반환한다.

    <Schema> > <Cube> > <Table>, <Dimension>, <Measure> 구조를 지원한다.
    XXE(외부 엔티티 확장) 공격을 방지하기 위해 안전한 파서 설정을 사용한다.
    """
    # XXE 방지 — 외부 엔티티 해석 및 네트워크 접근 차단
    safe_parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(xml_content.encode("utf-8"), parser=safe_parser)
    except etree.XMLSyntaxError as e:
        logger.error("mondrian_xml_parse_failed", error=str(e))
        return []
    cubes: list[CubeMetadata] = []

    for cube_el in root.findall(".//Cube"):
        cube_name = cube_el.get("name", "Unnamed")

        # 팩트 테이블
        table_el = cube_el.find("Table")
        fact_table = table_el.get("name", "") if table_el is not None else ""
        schema_prefix = table_el.get("schema", "dw") if table_el is not None else "dw"

        # 차원
        dimensions: list[DimensionDef] = []
        for dim_el in cube_el.findall("Dimension"):
            dim_name = dim_el.get("name", "")
            fk = dim_el.get("foreignKey", "")
            hierarchies: list[Hierarchy] = []

            for hier_el in dim_el.findall("Hierarchy"):
                hier_name = hier_el.get("name", dim_name)
                has_all = hier_el.get("hasAll", "true").lower() == "true"
                pk = hier_el.get("primaryKey", "id")

                # 차원 테이블
                dim_table_el = hier_el.find("Table")
                dim_table = dim_table_el.get("name", "") if dim_table_el is not None else ""

                # 레벨
                levels: list[DimensionLevel] = []
                for level_el in hier_el.findall("Level"):
                    levels.append(DimensionLevel(
                        name=level_el.get("name", ""),
                        column=level_el.get("column", ""),
                        caption=level_el.get("caption"),
                    ))

                hierarchies.append(Hierarchy(
                    name=hier_name, has_all=has_all, primary_key=pk, levels=levels,
                ))

            dimensions.append(DimensionDef(
                name=dim_name,
                physical_table_name=dim_table if hierarchies and dim_table_el is not None else "",
                foreign_key=fk,
                hierarchies=hierarchies,
            ))

        # DimensionUsage (공유 차원)
        for usage_el in cube_el.findall("DimensionUsage"):
            dim_name = usage_el.get("name", "")
            fk = usage_el.get("foreignKey", "")
            source = usage_el.get("source", dim_name)
            dimensions.append(DimensionDef(
                name=dim_name,
                physical_table_name="",  # 공유 차원은 별도 테이블 미지정
                foreign_key=fk,
            ))

        # 측정값
        measures: list[MeasureDef] = []
        for msr_el in cube_el.findall("Measure"):
            measures.append(MeasureDef(
                name=msr_el.get("name", ""),
                column=msr_el.get("column", ""),
                aggregator=msr_el.get("aggregator", "sum").upper(),
                format_string=msr_el.get("formatString"),
                caption=msr_el.get("caption"),
            ))

        # 조인 관계 추론 (차원의 FK → 팩트 테이블)
        joins: list[JoinDef] = []
        for dim in dimensions:
            if dim.foreign_key and dim.physical_table_name:
                joins.append(JoinDef(
                    left_table=fact_table,
                    left_column=dim.foreign_key,
                    right_table=dim.physical_table_name,
                    right_column="id",
                ))

        cubes.append(CubeMetadata(
            name=cube_name,
            fact_table=fact_table,
            dimensions=dimensions,
            measures=measures,
            joins=joins,
            schema_prefix=schema_prefix,
        ))

    logger.info("mondrian_xml_parsed", cube_count=len(cubes))
    return cubes
