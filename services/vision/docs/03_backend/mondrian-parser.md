# Mondrian XML 파서 + SQL 생성기 이식 상세

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 3.6
> **이식 원본**: K-AIR data-platform-olap-main
> **근거**: ADR-002, 01_architecture/olap-engine.md

---

## 이 문서가 답하는 질문

- K-AIR의 xml_parser.py를 어떻게 이식하는가?
- K-AIR의 sql_generator.py를 어떻게 이식하는가?
- 이식 시 어떤 부분을 변경해야 하는가?
- 메타데이터 저장소를 인메모리에서 DB로 어떻게 전환하는가?

---

## 1. K-AIR 원본 분석

### 1.1 xml_parser.py (원본 구조)

```python
# K-AIR 원본: data-platform-olap-main/xml_parser.py
class MondrianXMLParser:
    """
    Parses Mondrian Schema XML files to extract cube metadata.
    """
    def parse_file(self, xml_path: str) -> dict:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        cubes = []
        for cube_elem in root.findall('Cube'):
            cube = {
                'name': cube_elem.get('name'),
                'factTable': cube_elem.get('factTable'),
                'dimensions': self._parse_dimensions(cube_elem),
                'measures': self._parse_measures(cube_elem),
            }
            cubes.append(cube)

        return {'schema_name': root.get('name'), 'cubes': cubes}

    def _parse_dimensions(self, cube_elem) -> list[dict]:
        # ... dimension parsing logic
        pass

    def _parse_measures(self, cube_elem) -> list[dict]:
        # ... measure parsing logic
        pass
```

### 1.2 sql_generator.py (원본 구조)

```python
# K-AIR 원본: data-platform-olap-main/sql_generator.py
class SQLGenerator:
    def __init__(self, cube_metadata: dict):
        self.cube = cube_metadata

    def generate_query(self, pivot_request: dict) -> str:
        select_parts = []
        join_parts = []
        where_parts = []
        group_by_parts = []

        # Build SELECT, JOIN, WHERE, GROUP BY
        for row in pivot_request['rows']:
            # ... column resolution logic
            pass

        sql = f"""
        SELECT {', '.join(select_parts)}
        FROM {self.cube['factTable']} f
        {chr(10).join(join_parts)}
        {"WHERE " + " AND ".join(where_parts) if where_parts else ""}
        GROUP BY {', '.join(group_by_parts)}
        """
        return sql
```

---

## 2. 이식 변경 사항

### 2.1 변경 매트릭스

| 영역 | K-AIR 원본 | Axiom Vision | 변경 이유 |
|------|-----------|-------------|----------|
| 파일명 | `xml_parser.py` | `mondrian_parser.py` | 역할 명확화 |
| 파일명 | `sql_generator.py` | `pivot_engine.py` | 역할 명확화 |
| 데이터 클래스 | `dict` | `dataclass` (CubeMetadata) | 타입 안전성 |
| 메타 저장소 | 인메모리 + JSON 파일 | DB (PostgreSQL) | 영속성, 멀티 인스턴스 |
| SQL 대상 | 원본 테이블 | Materialized View | ADR-003 |
| 검증 | 없음 | SQLGlot 검증 | SQL injection 방지 |
| 비동기 | 동기 | async/await | FastAPI 호환 |
| 에러 처리 | 기본 예외 | 구조화된 도메인 예외 | 에러 추적 |

### 2.2 이식된 mondrian_parser.py

```python
# vision/app/engines/mondrian_parser.py
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class LevelMeta:
    name: str
    column: str
    level_type: str = "String"
    cardinality: int | None = None

@dataclass
class DimensionMeta:
    name: str
    foreign_key: str
    table: str
    primary_key: str = "id"
    has_all: bool = True
    levels: list[LevelMeta] = field(default_factory=list)

    def get_level(self, level_name: str) -> LevelMeta:
        for level in self.levels:
            if level.name == level_name:
                return level
        raise ValueError(f"Level '{level_name}' not found in dimension '{self.name}'")

@dataclass
class MeasureMeta:
    name: str
    column: str
    aggregator: str  # "sum", "avg", "distinct-count", "count", "min", "max"
    format_string: str | None = None

@dataclass
class JoinMeta:
    left_table: str
    left_key: str
    right_table: str
    right_key: str

@dataclass
class CubeMetadata:
    name: str
    fact_table: str
    dimensions: list[DimensionMeta] = field(default_factory=list)
    measures: list[MeasureMeta] = field(default_factory=list)
    joins: list[JoinMeta] = field(default_factory=list)

    def get_dimension(self, name: str) -> DimensionMeta:
        for dim in self.dimensions:
            if dim.name == name:
                return dim
        raise ValueError(f"Dimension '{name}' not found in cube '{self.name}'")

    def get_measure(self, name: str) -> MeasureMeta:
        for measure in self.measures:
            if measure.name == name:
                return measure
        raise ValueError(f"Measure '{name}' not found in cube '{self.name}'")


class MondrianParser:
    """
    Parses Mondrian XML schema files into CubeMetadata dataclasses.

    Ported from: K-AIR data-platform-olap-main/xml_parser.py
    Changes:
    - dict → dataclass (type safety)
    - Added validation
    - Added async file loading
    """

    def parse_file(self, xml_path: str | Path) -> list[CubeMetadata]:
        """Parse a Mondrian XML schema file."""
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        return self._parse_schema(root)

    def parse_string(self, xml_string: str) -> list[CubeMetadata]:
        """Parse Mondrian XML from string (for API upload)."""
        root = ET.fromstring(xml_string)
        return self._parse_schema(root)

    def _parse_schema(self, root: ET.Element) -> list[CubeMetadata]:
        cubes = []
        for cube_elem in root.findall('Cube'):
            cube = CubeMetadata(
                name=cube_elem.get('name', ''),
                fact_table=cube_elem.get('factTable', ''),
                dimensions=self._parse_dimensions(cube_elem),
                measures=self._parse_measures(cube_elem),
            )
            self._validate_cube(cube)
            cubes.append(cube)
        return cubes

    def _parse_dimensions(self, cube_elem: ET.Element) -> list[DimensionMeta]:
        dimensions = []
        for dim_elem in cube_elem.findall('Dimension'):
            hierarchy = dim_elem.find('Hierarchy')
            if hierarchy is None:
                continue

            levels = []
            for level_elem in hierarchy.findall('Level'):
                levels.append(LevelMeta(
                    name=level_elem.get('name', ''),
                    column=level_elem.get('column', ''),
                    level_type=level_elem.get('type', 'String'),
                ))

            dimensions.append(DimensionMeta(
                name=dim_elem.get('name', ''),
                foreign_key=dim_elem.get('foreignKey', ''),
                table=hierarchy.get('table', ''),
                primary_key=hierarchy.get('primaryKey', 'id'),
                has_all=hierarchy.get('hasAll', 'true').lower() == 'true',
                levels=levels,
            ))
        return dimensions

    def _parse_measures(self, cube_elem: ET.Element) -> list[MeasureMeta]:
        measures = []
        for measure_elem in cube_elem.findall('Measure'):
            measures.append(MeasureMeta(
                name=measure_elem.get('name', ''),
                column=measure_elem.get('column', ''),
                aggregator=measure_elem.get('aggregator', 'sum'),
                format_string=measure_elem.get('formatString'),
            ))
        return measures

    def _validate_cube(self, cube: CubeMetadata) -> None:
        """Validate parsed cube metadata."""
        if not cube.name:
            raise ValueError("Cube must have a name")
        if not cube.fact_table:
            raise ValueError(f"Cube '{cube.name}' must have a factTable")
        if not cube.dimensions:
            raise ValueError(f"Cube '{cube.name}' must have at least one dimension")
        if not cube.measures:
            raise ValueError(f"Cube '{cube.name}' must have at least one measure")
```

### 2.3 메타데이터 저장소 전환

```python
# K-AIR: In-memory + JSON file persistence
# Axiom: DB-backed with in-memory cache

class CubeMetadataStore:
    """
    Stores cube metadata in PostgreSQL with in-memory cache.
    Cache invalidated on cube definition upload.
    """

    def __init__(self, db_session_factory):
        self._cache: dict[str, CubeMetadata] = {}
        self._session_factory = db_session_factory

    async def load_cube(self, cube_name: str) -> CubeMetadata:
        # Check cache first
        if cube_name in self._cache:
            return self._cache[cube_name]

        # Load from DB
        async with self._session_factory() as db:
            result = await db.execute(
                select(CubeDefinition).where(CubeDefinition.name == cube_name)
            )
            row = result.scalar_one_or_none()
            if not row:
                raise ValueError(f"Cube '{cube_name}' not found")

            # Parse XML from DB
            parser = MondrianParser()
            cubes = parser.parse_string(row.xml_content)
            cube = next(c for c in cubes if c.name == cube_name)

            self._cache[cube_name] = cube
            return cube

    async def save_cube(self, xml_content: str) -> list[CubeMetadata]:
        parser = MondrianParser()
        cubes = parser.parse_string(xml_content)

        async with self._session_factory() as db:
            async with db.begin():
                for cube in cubes:
                    await db.merge(CubeDefinition(
                        name=cube.name,
                        xml_content=xml_content,
                        fact_table=cube.fact_table,
                        dimension_count=len(cube.dimensions),
                        measure_count=len(cube.measures),
                    ))

        # Invalidate cache
        for cube in cubes:
            self._cache.pop(cube.name, None)

        return cubes
```

---

## 3. SQL 생성기 (pivot_engine.py) 이식

### 3.1 주요 변경점

```python
# K-AIR: References source tables directly
# Axiom: References Materialized Views only

# K-AIR:   FROM sales_fact f
# Axiom:   FROM mv_business_fact f

# Allowed tables whitelist
ALLOWED_TABLES = {
    "mv_business_fact",
    "mv_cashflow_fact",
    "dim_case_type",
    "dim_org",
    "dim_time",
    "dim_stakeholder_type",
}
```

### 3.2 집계 함수 매핑

```python
AGGREGATOR_MAP = {
    "sum": "SUM",
    "avg": "AVG",
    "count": "COUNT",
    "distinct-count": "COUNT(DISTINCT {column})",
    "min": "MIN",
    "max": "MAX",
}

def build_aggregation(measure: MeasureMeta) -> str:
    template = AGGREGATOR_MAP.get(measure.aggregator)
    if "{column}" in template:
        return template.format(column=f"f.{measure.column}")
    return f"{template}(f.{measure.column})"
```

---

## 4. 이식 체크리스트

- [ ] xml_parser.py → mondrian_parser.py (타입 안전 dataclass)
- [ ] sql_generator.py → pivot_engine.py (MV 참조, SQLGlot 검증 추가)
- [ ] 인메모리 저장소 → DB 저장소 (CubeMetadataStore)
- [ ] 동기 → 비동기 전환 (async/await)
- [ ] 단위 테스트 이식 (K-AIR 테스트 케이스 기반)
- [ ] LangGraph 5노드 워크플로우 이식 (nl_pivot_workflow.py)
- [ ] ETL 서비스 이식 (MV REFRESH 방식으로 변경)

<!-- affects: 01_architecture/olap-engine.md, 06_data/cube-definitions.md -->
