"""Mondrian XML 파서 단위 테스트.

xml_parser.py의 parse_mondrian_xml 함수를 다양한 XML 입력에 대해 검증한다.
XXE 공격 방어, 잘못된 XML, 공유 차원(DimensionUsage), 조인 추론 등을 포함한다.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.services.xml_parser import parse_mondrian_xml
from app.models.cube import CubeMetadata, DimensionDef, MeasureDef, JoinDef


# ──────────────────────────────────────────────
# 유효한 Mondrian XML 파싱 — 기본 시나리오
# ──────────────────────────────────────────────


VALID_XML_ONE_CUBE = """\
<Schema name="TestSchema">
  <Cube name="Sales">
    <Table name="fact_sales" schema="analytics"/>
    <Dimension name="Time" foreignKey="time_id">
      <Hierarchy name="TimeHier" hasAll="true" primaryKey="id">
        <Table name="dim_time"/>
        <Level name="Year" column="year_col"/>
        <Level name="Quarter" column="quarter_col" caption="분기"/>
      </Hierarchy>
    </Dimension>
    <Dimension name="Product" foreignKey="product_id">
      <Hierarchy name="ProductHier" hasAll="false" primaryKey="product_pk">
        <Table name="dim_product"/>
        <Level name="Category" column="cat_col"/>
      </Hierarchy>
    </Dimension>
    <Measure name="Revenue" column="revenue" aggregator="sum" formatString="#,###"/>
    <Measure name="Quantity" column="qty" aggregator="count" caption="수량"/>
  </Cube>
</Schema>
"""


class TestValidXmlParsing:
    """유효한 Mondrian XML → CubeMetadata 변환을 검증한다."""

    def test_parses_one_cube(self):
        """큐브 1개 → 리스트 길이 1."""
        cubes = parse_mondrian_xml(VALID_XML_ONE_CUBE)
        assert len(cubes) == 1

    def test_cube_name_and_fact_table(self):
        """큐브 이름과 팩트 테이블이 올바르게 추출된다."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        assert cube.name == "Sales"
        assert cube.fact_table == "fact_sales"
        assert cube.schema_prefix == "analytics"

    def test_dimensions_count(self):
        """차원이 2개 추출된다."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        assert len(cube.dimensions) == 2

    def test_dimension_time_properties(self):
        """Time 차원의 속성이 올바르다."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        time_dim = cube.dimensions[0]
        assert time_dim.name == "Time"
        assert time_dim.foreign_key == "time_id"
        assert time_dim.physical_table_name == "dim_time"

    def test_hierarchy_properties(self):
        """Time 계층의 has_all, primary_key가 올바르다."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        hier = cube.dimensions[0].hierarchies[0]
        assert hier.name == "TimeHier"
        assert hier.has_all is True
        assert hier.primary_key == "id"

    def test_hierarchy_levels(self):
        """Time 계층에 2개 레벨이 올바른 순서로 추출된다."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        levels = cube.dimensions[0].hierarchies[0].levels
        assert len(levels) == 2
        assert levels[0].name == "Year"
        assert levels[0].column == "year_col"
        assert levels[0].caption is None
        assert levels[1].name == "Quarter"
        assert levels[1].column == "quarter_col"
        assert levels[1].caption == "분기"

    def test_product_hierarchy_has_all_false(self):
        """Product 계층의 hasAll="false" → has_all=False."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        hier = cube.dimensions[1].hierarchies[0]
        assert hier.has_all is False
        assert hier.primary_key == "product_pk"

    def test_measures_count_and_properties(self):
        """측정값 2개가 올바르게 추출된다."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        assert len(cube.measures) == 2

        rev = cube.measures[0]
        assert rev.name == "Revenue"
        assert rev.column == "revenue"
        assert rev.aggregator == "SUM"  # 대문자 변환
        assert rev.format_string == "#,###"
        assert rev.caption is None

        qty = cube.measures[1]
        assert qty.name == "Quantity"
        assert qty.column == "qty"
        assert qty.aggregator == "COUNT"
        assert qty.caption == "수량"

    def test_auto_inferred_joins(self):
        """FK가 있는 차원 → 자동으로 JoinDef가 생성된다."""
        cube = parse_mondrian_xml(VALID_XML_ONE_CUBE)[0]
        assert len(cube.joins) == 2

        # Time 차원 조인
        time_join = cube.joins[0]
        assert time_join.left_table == "fact_sales"
        assert time_join.left_column == "time_id"
        assert time_join.right_table == "dim_time"
        assert time_join.right_column == "id"

        # Product 차원 조인
        prod_join = cube.joins[1]
        assert prod_join.left_table == "fact_sales"
        assert prod_join.left_column == "product_id"
        assert prod_join.right_table == "dim_product"
        assert prod_join.right_column == "id"


# ──────────────────────────────────────────────
# DimensionUsage (공유 차원) 테스트
# ──────────────────────────────────────────────


XML_WITH_DIMENSION_USAGE = """\
<Schema name="SharedDimSchema">
  <Dimension name="SharedTime" type="TimeDimension">
    <Hierarchy name="TimeHier" hasAll="true" primaryKey="id">
      <Table name="dim_shared_time"/>
      <Level name="Year" column="year_col"/>
    </Hierarchy>
  </Dimension>
  <Cube name="OrderCube">
    <Table name="fact_orders" schema="dw"/>
    <DimensionUsage name="OrderTime" source="SharedTime" foreignKey="order_time_id"/>
    <Measure name="OrderCount" column="order_cnt" aggregator="count"/>
  </Cube>
</Schema>
"""


class TestDimensionUsage:
    """DimensionUsage(공유 차원) 파싱을 검증한다."""

    def test_dimension_usage_parsed(self):
        """DimensionUsage가 차원 목록에 포함된다."""
        cubes = parse_mondrian_xml(XML_WITH_DIMENSION_USAGE)
        assert len(cubes) == 1
        cube = cubes[0]

        # DimensionUsage → DimensionDef로 변환
        assert len(cube.dimensions) == 1
        dim = cube.dimensions[0]
        assert dim.name == "OrderTime"
        assert dim.foreign_key == "order_time_id"
        # 공유 차원은 물리 테이블 미지정
        assert dim.physical_table_name == ""

    def test_shared_dimension_no_join_generated(self):
        """공유 차원은 physical_table_name이 비어있으므로 조인이 생성되지 않는다."""
        cube = parse_mondrian_xml(XML_WITH_DIMENSION_USAGE)[0]
        # FK는 있지만 physical_table_name이 비어있으면 조인 안 함
        assert len(cube.joins) == 0


# ──────────────────────────────────────────────
# 큐브 여러 개 포함 XML
# ──────────────────────────────────────────────


XML_MULTI_CUBES = """\
<Schema name="MultiSchema">
  <Cube name="CubeA">
    <Table name="fact_a"/>
    <Measure name="MetricA" column="val_a" aggregator="sum"/>
  </Cube>
  <Cube name="CubeB">
    <Table name="fact_b"/>
    <Measure name="MetricB" column="val_b" aggregator="avg"/>
  </Cube>
</Schema>
"""


class TestMultipleCubes:
    """여러 큐브가 포함된 스키마를 검증한다."""

    def test_multiple_cubes_parsed(self):
        """큐브 2개 → 리스트 길이 2."""
        cubes = parse_mondrian_xml(XML_MULTI_CUBES)
        assert len(cubes) == 2
        assert cubes[0].name == "CubeA"
        assert cubes[1].name == "CubeB"

    def test_default_schema_prefix(self):
        """Table에 schema 속성이 없으면 기본값 'dw'."""
        cubes = parse_mondrian_xml(XML_MULTI_CUBES)
        assert cubes[0].schema_prefix == "dw"


# ──────────────────────────────────────────────
# 다중 계층과 레벨 테스트
# ──────────────────────────────────────────────


XML_MULTI_HIERARCHY = """\
<Schema name="HierSchema">
  <Cube name="HR">
    <Table name="fact_hr" schema="hr"/>
    <Dimension name="Geography" foreignKey="geo_id">
      <Hierarchy name="Standard" hasAll="true" primaryKey="id">
        <Table name="dim_geo"/>
        <Level name="Country" column="country"/>
        <Level name="State" column="state"/>
        <Level name="City" column="city"/>
      </Hierarchy>
      <Hierarchy name="Regional" hasAll="false" primaryKey="region_id">
        <Table name="dim_region"/>
        <Level name="Region" column="region_name"/>
      </Hierarchy>
    </Dimension>
    <Measure name="Headcount" column="head_count" aggregator="count"/>
  </Cube>
</Schema>
"""


class TestMultipleHierarchies:
    """하나의 차원에 여러 계층이 있는 경우를 검증한다."""

    def test_two_hierarchies(self):
        """Geography 차원에 2개 계층이 파싱된다."""
        cube = parse_mondrian_xml(XML_MULTI_HIERARCHY)[0]
        dim = cube.dimensions[0]
        assert len(dim.hierarchies) == 2

    def test_first_hierarchy_three_levels(self):
        """Standard 계층에 3개 레벨."""
        cube = parse_mondrian_xml(XML_MULTI_HIERARCHY)[0]
        hier = cube.dimensions[0].hierarchies[0]
        assert hier.name == "Standard"
        assert len(hier.levels) == 3
        assert [l.name for l in hier.levels] == ["Country", "State", "City"]

    def test_second_hierarchy_one_level(self):
        """Regional 계층에 1개 레벨."""
        cube = parse_mondrian_xml(XML_MULTI_HIERARCHY)[0]
        hier = cube.dimensions[0].hierarchies[1]
        assert hier.name == "Regional"
        assert hier.has_all is False
        assert len(hier.levels) == 1


# ──────────────────────────────────────────────
# 에러 케이스 — 잘못된 XML
# ──────────────────────────────────────────────


class TestMalformedXml:
    """잘못된 XML 입력 시 안전하게 처리한다."""

    def test_malformed_xml_returns_empty_list(self):
        """문법 오류 XML → 빈 리스트 (예외 발생 안 함)."""
        result = parse_mondrian_xml("<Schema><Cube><broken")
        assert result == []

    def test_empty_string_returns_empty_list(self):
        """빈 문자열 → 빈 리스트."""
        result = parse_mondrian_xml("")
        assert result == []

    def test_xml_without_cubes_returns_empty_list(self):
        """Cube 요소 없는 유효한 XML → 빈 리스트."""
        result = parse_mondrian_xml("<Schema name='Empty'></Schema>")
        assert result == []


# ──────────────────────────────────────────────
# XXE 공격 방어 테스트
# ──────────────────────────────────────────────


class TestXxeSafety:
    """XXE(외부 엔티티 확장) 공격에 대한 방어를 검증한다."""

    def test_xxe_entity_not_resolved(self):
        """외부 엔티티 선언이 포함된 XML → 엔티티가 해석되지 않아야 한다.

        안전한 파서(resolve_entities=False)가 엔티티 해석을 차단한다.
        lxml은 resolve_entities=False일 때 일반적으로 에러를 발생시키지 않고
        엔티티 참조를 그대로 두거나 무시한다.
        """
        xxe_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<Schema name="Evil">
  <Cube name="&xxe;">
    <Table name="fact"/>
    <Measure name="m" column="c" aggregator="sum"/>
  </Cube>
</Schema>
"""
        # lxml의 resolve_entities=False는 엔티티 참조를 해석하지 않는다.
        # 큐브 이름에 /etc/passwd 내용이 들어가지 않아야 한다.
        cubes = parse_mondrian_xml(xxe_xml)
        if len(cubes) > 0:
            # 엔티티가 해석되었다면 큐브 이름에 passwd 내용이 포함됨
            assert "root:" not in cubes[0].name
            # 엔티티 참조가 해석되지 않았으므로 이름은 비어있거나 원문 그대로
            assert cubes[0].name != ""  # lxml은 entity ref를 텍스트로 남겨둠
        # 파싱 자체가 실패해도 안전 (빈 리스트 반환)


    def test_xxe_no_network_access(self):
        """네트워크를 통한 외부 엔티티 접근 시도 → 차단.

        no_network=True 옵션으로 네트워크 접근을 원천 차단한다.
        """
        xxe_net_xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE foo [
  <!ENTITY xxe SYSTEM "http://evil.example.com/steal">
]>
<Schema name="NetEvil">
  <Cube name="&xxe;">
    <Table name="fact"/>
    <Measure name="m" column="c" aggregator="sum"/>
  </Cube>
</Schema>
"""
        # 네트워크 접근 없이 안전하게 처리되어야 한다
        cubes = parse_mondrian_xml(xxe_net_xml)
        # 결과가 있더라도 외부 데이터가 주입되지 않아야 한다
        if len(cubes) > 0:
            assert "evil" not in cubes[0].name.lower()


# ──────────────────────────────────────────────
# 기본값 처리 테스트
# ──────────────────────────────────────────────


class TestDefaults:
    """속성 누락 시 기본값이 올바르게 적용되는지 검증한다."""

    def test_unnamed_cube(self):
        """name 속성 없는 큐브 → 'Unnamed'."""
        xml = '<Schema><Cube><Table name="ft"/><Measure name="m" column="c" aggregator="sum"/></Cube></Schema>'
        cubes = parse_mondrian_xml(xml)
        assert cubes[0].name == "Unnamed"

    def test_missing_table_element(self):
        """Table 요소 없는 큐브 → fact_table 빈 문자열."""
        xml = '<Schema><Cube name="NoTable"><Measure name="m" column="c" aggregator="sum"/></Cube></Schema>'
        cubes = parse_mondrian_xml(xml)
        assert cubes[0].fact_table == ""

    def test_hierarchy_default_primary_key(self):
        """primaryKey 속성 없는 계층 → 기본값 'id'."""
        xml = """\
<Schema>
  <Cube name="Test">
    <Table name="ft"/>
    <Dimension name="D" foreignKey="d_id">
      <Hierarchy name="H" hasAll="true">
        <Table name="dim_d"/>
        <Level name="L" column="l_col"/>
      </Hierarchy>
    </Dimension>
    <Measure name="m" column="c" aggregator="sum"/>
  </Cube>
</Schema>
"""
        cube = parse_mondrian_xml(xml)[0]
        assert cube.dimensions[0].hierarchies[0].primary_key == "id"

    def test_measure_aggregator_uppercase(self):
        """aggregator가 소문자로 입력되어도 대문자로 변환된다."""
        xml = '<Schema><Cube name="T"><Table name="ft"/><Measure name="m" column="c" aggregator="avg"/></Cube></Schema>'
        cube = parse_mondrian_xml(xml)[0]
        assert cube.measures[0].aggregator == "AVG"
